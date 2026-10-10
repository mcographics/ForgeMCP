#include "ForgeBlueprintEdits.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Components/ActorComponent.h"
#include "Engine/World.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_Event.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_Self.h"
#include "K2Node_Knot.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Logging/TokenizedMessage.h"
#include "ScopedTransaction.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/FeedbackContext.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#include "ForgeGameplayAbilities.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;
FString Text(const JObject& Object, const TCHAR* Field, const TCHAR* Fallback=TEXT(""))
{ FString Value; return Object->TryGetStringField(Field,Value) ? Value : FString(Fallback); }
FString Serialize(const JObject& Object)
{ FString Value; FJsonSerializer::Serialize(Object,TJsonWriterFactory<>::Create(&Value)); return Value; }
bool Identifier(const FString& Value)
{
    if (Value.IsEmpty() || Value.Len()>64 || !(FChar::IsAlpha(Value[0]) || Value[0]=='_')) return false;
    for (TCHAR Character : Value) if (!(FChar::IsAlnum(Character) || Character=='_')) return false;
    return true;
}
FEdGraphPinType VariablePinType(const FString& Type)
{
    FEdGraphPinType Pin;
    if (Type==TEXT("bool")) Pin.PinCategory=UEdGraphSchema_K2::PC_Boolean;
    else if (Type==TEXT("int")) Pin.PinCategory=UEdGraphSchema_K2::PC_Int;
    else if (Type==TEXT("float")) { Pin.PinCategory=UEdGraphSchema_K2::PC_Real; Pin.PinSubCategory=UEdGraphSchema_K2::PC_Double; }
    else if (Type==TEXT("string")) Pin.PinCategory=UEdGraphSchema_K2::PC_String;
    else if (Type==TEXT("name")) Pin.PinCategory=UEdGraphSchema_K2::PC_Name;
    else if (Type==TEXT("vector") || Type==TEXT("rotator")) { Pin.PinCategory=UEdGraphSchema_K2::PC_Struct; Pin.PinSubCategoryObject=Type==TEXT("vector")?TBaseStructure<FVector>::Get():TBaseStructure<FRotator>::Get(); }
    return Pin;
}
UEdGraphNode* FindNode(UBlueprint* BP, const FString& GraphName, const FString& Id)
{
    FGuid Guid; if (!FGuid::Parse(Id,Guid)) return nullptr;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs) if (Graph->GetName()==GraphName)
        for (UEdGraphNode* Node : Graph->Nodes) if (Node->NodeGuid==Guid) return Node;
    return nullptr;
}
bool EditableNode(UEdGraphNode* Node)
{
    const FString Class=Node->GetClass()->GetPathName();
    static const TSet<FString> Classes{
        TEXT("/Script/BlueprintGraph.K2Node_IfThenElse"), TEXT("/Script/BlueprintGraph.K2Node_ExecutionSequence"),
        TEXT("/Script/BlueprintGraph.K2Node_Self"), TEXT("/Script/BlueprintGraph.K2Node_Knot"),
        TEXT("/Script/BlueprintGraph.K2Node_Event"), TEXT("/Script/BlueprintGraph.K2Node_CustomEvent"),
        TEXT("/Script/BlueprintGraph.K2Node_VariableGet"), TEXT("/Script/BlueprintGraph.K2Node_VariableSet")};
    if (Classes.Contains(Class)) return true;
    if (Class!=TEXT("/Script/BlueprintGraph.K2Node_CallFunction")) return false;
    UFunction* Function=CastChecked<UK2Node_CallFunction>(Node)->GetTargetFunction();
    if (!Function) return false;
    const FString Owner=Function->GetOuterUClass()->GetPathName(), Name=Function->GetName();
    if ((Owner==TEXT("/Script/Engine.KismetMathLibrary") || Owner==TEXT("/Script/Engine.KismetStringLibrary")) && Function->HasAnyFunctionFlags(FUNC_BlueprintPure)) return true;
    if (Owner==TEXT("/Script/Engine.KismetSystemLibrary")) return Name==TEXT("PrintString") || Name==TEXT("PrintText") || Name==TEXT("IsValid");
    if (Owner==TEXT("/Script/Engine.Actor")) return Name==TEXT("K2_GetActorLocation") || Name==TEXT("K2_GetActorRotation") || Name==TEXT("GetActorScale3D") || Name==TEXT("K2_SetActorLocation") || Name==TEXT("K2_SetActorRotation") || Name==TEXT("SetActorScale3D") || Name==TEXT("SetActorHiddenInGame");
    return false;
}
UEdGraphNode* CreateNode(UBlueprint* BP, UEdGraph* Graph, const JObject& Definition)
{
    const FString Kind=Text(Definition,TEXT("kind")), Name=Text(Definition,TEXT("name"));
    UEdGraphNode* Node=nullptr;
    if (Kind==TEXT("branch")) Node=NewObject<UK2Node_IfThenElse>(Graph);
    else if (Kind==TEXT("sequence")) Node=NewObject<UK2Node_ExecutionSequence>(Graph);
    else if (Kind==TEXT("self")) Node=NewObject<UK2Node_Self>(Graph);
    else if (Kind==TEXT("reroute")) Node=NewObject<UK2Node_Knot>(Graph);
    else if (Kind==TEXT("custom_event"))
    { if (Graph!=FBlueprintEditorUtils::FindEventGraph(BP) || BP->GeneratedClass->FindFunctionByName(*Name)) return nullptr; auto* Event=NewObject<UK2Node_CustomEvent>(Graph); Event->CustomFunctionName=*Name; Node=Event; }
    else if (Kind==TEXT("event"))
    { UFunction* Event=BP->ParentClass->FindFunctionByName(*Name); if (Graph!=FBlueprintEditorUtils::FindEventGraph(BP) || !Event || !Event->HasAnyFunctionFlags(FUNC_BlueprintEvent)) return nullptr; auto* Override=NewObject<UK2Node_Event>(Graph); Override->EventReference.SetExternalMember(*Name,BP->ParentClass); Override->bOverrideFunction=true; Node=Override; }
    else if (Kind==TEXT("variable_get") || Kind==TEXT("variable_set"))
    { bool Found=false; for (const auto& Variable : BP->NewVariables) if (Variable.VarName==FName(*Name)) Found=true; if (!Found) return nullptr; if (Kind==TEXT("variable_get")) { auto* Get=NewObject<UK2Node_VariableGet>(Graph); Get->VariableReference.SetSelfMember(*Name); Node=Get; } else { auto* Set=NewObject<UK2Node_VariableSet>(Graph); Set->VariableReference.SetSelfMember(*Name); Node=Set; } }
    else if (Kind==TEXT("call_function"))
    { FString OwnerPath=Text(Definition,TEXT("owner_class"),TEXT("/Script/Engine.Actor")); static const TSet<FString> Owners{TEXT("/Script/Engine.Actor"),TEXT("/Script/Engine.KismetMathLibrary"),TEXT("/Script/Engine.KismetStringLibrary"),TEXT("/Script/Engine.KismetSystemLibrary")}; if (!Owners.Contains(OwnerPath)) return nullptr; UClass* Owner=LoadObject<UClass>(nullptr,*OwnerPath); UFunction* Function=Owner ? Owner->FindFunctionByName(*Name) : nullptr; if (!Function) return nullptr; const FString OwnerName=Function->GetOuterUClass()->GetPathName(); const bool Allowed=((OwnerName==TEXT("/Script/Engine.KismetMathLibrary") || OwnerName==TEXT("/Script/Engine.KismetStringLibrary")) && Function->HasAnyFunctionFlags(FUNC_BlueprintPure)) || (OwnerName==TEXT("/Script/Engine.KismetSystemLibrary") && (Name==TEXT("PrintString") || Name==TEXT("PrintText") || Name==TEXT("IsValid"))) || (OwnerName==TEXT("/Script/Engine.Actor") && (Name==TEXT("K2_GetActorLocation") || Name==TEXT("K2_GetActorRotation") || Name==TEXT("GetActorScale3D") || Name==TEXT("K2_SetActorLocation") || Name==TEXT("K2_SetActorRotation") || Name==TEXT("SetActorScale3D") || Name==TEXT("SetActorHiddenInGame"))); if (!Allowed) return nullptr; auto* Call=NewObject<UK2Node_CallFunction>(Graph); Call->SetFromFunction(Function); Node=Call; }
    if (!Node) return nullptr;
    Node->SetFlags(RF_Transactional); Graph->AddNode(Node,false,false); Node->CreateNewGuid(); Node->PostPlacedNewNode(); Node->AllocateDefaultPins();
    if (auto* Sequence=Cast<UK2Node_ExecutionSequence>(Node)) { double Count=2; Definition->TryGetNumberField(TEXT("execution_outputs"),Count); for (int32 I=2; I<static_cast<int32>(Count); ++I) Sequence->AddInputPin(); }
    double X=0,Y=0; Definition->TryGetNumberField(TEXT("x"),X); Definition->TryGetNumberField(TEXT("y"),Y); Node->NodePosX=static_cast<int32>(X); Node->NodePosY=static_cast<int32>(Y);
    return Node;
}
JObject Snapshot(UBlueprint* BP)
{
    auto State=MakeShared<FJsonObject>(); State->SetStringField(TEXT("asset_path"),BP->GetPathName());
    State->SetNumberField(TEXT("compile_status"),static_cast<int32>(BP->Status));
    State->SetBoolField(TEXT("dirty"),BP->GetOutermost()->IsDirty());
    if (BP->NewVariables.Num()>512 || (BP->SimpleConstructionScript && BP->SimpleConstructionScript->GetAllNodes().Num()>512)) return State;
    TArray<TSharedPtr<FJsonValue>> Variables;
    for (const FBPVariableDescription& Variable : BP->NewVariables)
    {
        auto V=MakeShared<FJsonObject>(); V->SetStringField(TEXT("name"),Variable.VarName.ToString()); V->SetStringField(TEXT("guid"),Variable.VarGuid.ToString());
        FString DefaultValue=Variable.DefaultValue; UObject* Defaults=BP->GeneratedClass?BP->GeneratedClass->GetDefaultObject():nullptr;
        if (Defaults) if (FProperty* Property=BP->GeneratedClass->FindPropertyByName(Variable.VarName)) Property->ExportTextItem_Direct(DefaultValue,Property->ContainerPtrToValuePtr<void>(Defaults),nullptr,Defaults,PPF_None);
        V->SetStringField(TEXT("default"),DefaultValue); V->SetStringField(TEXT("flags"),LexToString(Variable.PropertyFlags)); V->SetStringField(TEXT("friendly_name"),Variable.FriendlyName);
        V->SetStringField(TEXT("rep_notify"),Variable.RepNotifyFunc.ToString()); V->SetNumberField(TEXT("replication_condition"),Variable.ReplicationCondition.GetValue());
        FString Type,Category; FEdGraphPinType::StaticStruct()->ExportText(Type,&Variable.VarType,nullptr,nullptr,PPF_None,nullptr); FTextStringHelper::WriteToBuffer(Category,Variable.Category); V->SetStringField(TEXT("type"),Type); V->SetStringField(TEXT("category"),Category);
        TArray<TSharedPtr<FJsonValue>> Metadata; for (const auto& Entry : Variable.MetaDataArray) { auto M=MakeShared<FJsonObject>(); M->SetStringField(TEXT("key"),Entry.DataKey.ToString()); M->SetStringField(TEXT("value"),Entry.DataValue); Metadata.Add(MakeShared<FJsonValueObject>(M)); } V->SetArrayField(TEXT("metadata"),Metadata); Variables.Add(MakeShared<FJsonValueObject>(V));
    }
    State->SetArrayField(TEXT("variables"),Variables);
    TArray<TSharedPtr<FJsonValue>> Components;
    if (BP->SimpleConstructionScript) for (USCS_Node* Component : BP->SimpleConstructionScript->GetAllNodes()) if (Component)
    {
        auto C=MakeShared<FJsonObject>(); C->SetStringField(TEXT("guid"),Component->VariableGuid.ToString()); C->SetStringField(TEXT("name"),Component->GetVariableName().ToString()); C->SetStringField(TEXT("class"),Component->ComponentClass ? Component->ComponentClass->GetPathName() : TEXT(""));
        const USCS_Node* Parent=BP->SimpleConstructionScript->FindParentNode(Component); C->SetStringField(TEXT("parent"),Parent?Parent->VariableGuid.ToString():TEXT("")); Components.Add(MakeShared<FJsonValueObject>(C));
    }
    State->SetArrayField(TEXT("components"),Components);
    TArray<TSharedPtr<FJsonValue>> GraphData;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    int32 TotalPins=0;
    if (Graphs.Num()>64) return State;
    for (UEdGraph* Graph : Graphs)
    {
        if (Graph->Nodes.Num()>512) return State;
        auto G=MakeShared<FJsonObject>(); G->SetStringField(TEXT("name"),Graph->GetName());
        TArray<TSharedPtr<FJsonValue>> Nodes;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            auto N=MakeShared<FJsonObject>(); N->SetStringField(TEXT("id"),Node->NodeGuid.ToString());
            N->SetStringField(TEXT("class"),Node->GetClass()->GetPathName());
            N->SetNumberField(TEXT("x"),Node->NodePosX); N->SetNumberField(TEXT("y"),Node->NodePosY);
            TArray<TSharedPtr<FJsonValue>> Pins;
            for (UEdGraphPin* Pin : Node->Pins)
            {
                if (++TotalPins>8192) return State;
                auto P=MakeShared<FJsonObject>(); P->SetStringField(TEXT("name"),Pin->PinName.ToString());
                P->SetNumberField(TEXT("direction"),Pin->Direction);
                P->SetStringField(TEXT("default"),Pin->DefaultValue);
                P->SetStringField(TEXT("object"),Pin->DefaultObject ? Pin->DefaultObject->GetPathName() : TEXT(""));
                FString TextValue; FTextStringHelper::WriteToBuffer(TextValue,Pin->DefaultTextValue);
                P->SetStringField(TEXT("text"),TextValue);
                FString TypeValue; FEdGraphPinType::StaticStruct()->ExportText(TypeValue,&Pin->PinType,nullptr,nullptr,PPF_None,nullptr);
                P->SetStringField(TEXT("pin_type"),TypeValue);
                TArray<TSharedPtr<FJsonValue>> Links;
                for (UEdGraphPin* Link : Pin->LinkedTo)
                {
                    auto L=MakeShared<FJsonObject>(); L->SetStringField(TEXT("node"),Link->GetOwningNode()->NodeGuid.ToString());
                    L->SetStringField(TEXT("pin"),Link->PinName.ToString()); Links.Add(MakeShared<FJsonValueObject>(L));
                }
                P->SetArrayField(TEXT("links"),Links); Pins.Add(MakeShared<FJsonValueObject>(P));
            }
            N->SetArrayField(TEXT("pins"),Pins); Nodes.Add(MakeShared<FJsonValueObject>(N));
        }
        G->SetArrayField(TEXT("nodes"),Nodes); GraphData.Add(MakeShared<FJsonValueObject>(G));
    }
    State->SetArrayField(TEXT("graphs"),GraphData); return State;
}
bool Restore(UBlueprint* BP, const JObject& State)
{
    TSet<FName> OriginalVariables; for (const auto& V : State->GetArrayField(TEXT("variables"))) OriginalVariables.Add(FName(*Text(V->AsObject().ToSharedRef(),TEXT("name"))));
    for (int32 Index=BP->NewVariables.Num()-1;Index>=0;--Index) if (!OriginalVariables.Contains(BP->NewVariables[Index].VarName)) FBlueprintEditorUtils::RemoveMemberVariable(BP,BP->NewVariables[Index].VarName);
    TSet<FGuid> OriginalComponents; for (const auto& C : State->GetArrayField(TEXT("components"))) { FGuid Guid; if (FGuid::Parse(Text(C->AsObject().ToSharedRef(),TEXT("guid")),Guid)) OriginalComponents.Add(Guid); }
    if (!BP->SimpleConstructionScript && OriginalComponents.Num()) return false;
    if (BP->SimpleConstructionScript)
    {
        const TArray<USCS_Node*> ExistingComponents=BP->SimpleConstructionScript->GetAllNodes();
        for (USCS_Node* Component : ExistingComponents) if (Component && !OriginalComponents.Contains(Component->VariableGuid)) BP->SimpleConstructionScript->RemoveNode(Component,false);
    }
    const auto& Graphs=State->GetArrayField(TEXT("graphs"));
    // Schema connections can insert conversion nodes. Remove those before restoring links.
    TArray<UEdGraph*> CurrentGraphs;
    BP->GetAllGraphs(CurrentGraphs);
    for (const auto& GV : Graphs)
    {
        const auto G=GV->AsObject().ToSharedRef();
        TSet<FString> OriginalIds;
        for (const auto& NV : G->GetArrayField(TEXT("nodes"))) OriginalIds.Add(Text(NV->AsObject().ToSharedRef(),TEXT("id")));
        for (UEdGraph* Graph : CurrentGraphs) if (Graph && Graph->GetName()==Text(G,TEXT("name")))
        {
            const TArray<UEdGraphNode*> Nodes=Graph->Nodes;
            for (UEdGraphNode* Node : Nodes) if (Node && !OriginalIds.Contains(Node->NodeGuid.ToString()))
                FBlueprintEditorUtils::RemoveNode(BP,Node,true);
        }
    }
    // Resolve pins afresh after compilation; do not keep raw pin pointers across it.
    for (const auto& GV : Graphs) for (const auto& NV : GV->AsObject()->GetArrayField(TEXT("nodes")))
    {
        const auto G=GV->AsObject().ToSharedRef(), N=NV->AsObject().ToSharedRef();
        UEdGraphNode* Node=FindNode(BP,Text(G,TEXT("name")),Text(N,TEXT("id")));
        if (!Node) return false;
        Node->NodePosX=N->GetIntegerField(TEXT("x")); Node->NodePosY=N->GetIntegerField(TEXT("y"));
        for (const auto& PV : N->GetArrayField(TEXT("pins")))
        {
            const auto P=PV->AsObject().ToSharedRef();
            UEdGraphPin* Pin=Node->FindPin(*Text(P,TEXT("name")),static_cast<EEdGraphPinDirection>(P->GetIntegerField(TEXT("direction"))));
            if (!Pin) return false;
            Pin->BreakAllPinLinks(); Pin->DefaultValue=Text(P,TEXT("default"));
            if (!FEdGraphPinType::StaticStruct()->ImportText(*Text(P,TEXT("pin_type")),&Pin->PinType,nullptr,PPF_None,GWarn,TEXT("ForgeRecovery"))) return false;
            Pin->DefaultObject=Text(P,TEXT("object")).IsEmpty() ? nullptr : FindObject<UObject>(nullptr,*Text(P,TEXT("object")));
            FTextStringHelper::ReadFromBuffer(*Text(P,TEXT("text")),Pin->DefaultTextValue);
        }
    }
    for (const auto& GV : Graphs) for (const auto& NV : GV->AsObject()->GetArrayField(TEXT("nodes")))
    {
        const auto G=GV->AsObject().ToSharedRef(), N=NV->AsObject().ToSharedRef();
        UEdGraphNode* Node=FindNode(BP,Text(G,TEXT("name")),Text(N,TEXT("id")));
        for (const auto& PV : N->GetArrayField(TEXT("pins")))
        {
            const auto P=PV->AsObject().ToSharedRef();
            if (P->GetIntegerField(TEXT("direction"))!=EGPD_Output) continue;
            UEdGraphPin* Pin=Node->FindPin(*Text(P,TEXT("name")),EGPD_Output);
            for (const auto& LV : P->GetArrayField(TEXT("links")))
            {
                const auto L=LV->AsObject().ToSharedRef();
                UEdGraphNode* Target=FindNode(BP,Text(G,TEXT("name")),Text(L,TEXT("node")));
                UEdGraphPin* Other=Target ? Target->FindPin(*Text(L,TEXT("pin")),EGPD_Input) : nullptr;
                if (!Other) return false;
                Pin->MakeLinkTo(Other);
            }
        }
    }
    return true;
}
}

bool FForgeBlueprintEdits::Handle(const FString& Command, const JObject& Args, JObject Data, FString& Code, FString& Message)
{
    auto Fail=[&](const TCHAR* Error,const FString& Detail){ Code=Error; Message=Detail; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld) return Fail(TEXT("invalid_context"),TEXT("An idle editor is required."));
    TSharedPtr<FJsonObject> Recipe; FPreview Plan;
    if (Command==TEXT("blueprint_edit_apply"))
    {
        FString Id=Text(Args,TEXT("preview_id"));
        if (Args->Values.Num()!=2 || Id.IsEmpty() || Text(Args,TEXT("confirmation"))!=Id)
            return Fail(TEXT("confirmation_required"),TEXT("confirmation must equal reviewed preview_id."));
        if (!Previews.RemoveAndCopyValue(Id,Plan) || Plan.Expires<=FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"),TEXT("Preview expired, consumed or belongs to another session."));
        Recipe=Plan.Recipe;
    }
    else
    {
        const TSharedPtr<FJsonObject>* R;
        if (Args->Values.Num()!=1 || !Args->TryGetObjectField(TEXT("recipe"),R)) return Fail(TEXT("invalid_arguments"),TEXT("Expected recipe."));
        Recipe=*R;
    }
    FString Path; const TArray<TSharedPtr<FJsonValue>>* Ops; const TArray<TSharedPtr<FJsonValue>>* VariableDefinitions; const TArray<TSharedPtr<FJsonValue>>* ComponentDefinitions; const TArray<TSharedPtr<FJsonValue>>* NodeDefinitions; const TArray<TSharedPtr<FJsonValue>>* ConnectionDefinitions;
    if (Recipe->Values.Num()!=6 || !Recipe->TryGetStringField(TEXT("asset_path"),Path) || !Path.StartsWith(TEXT("/Game/")) || Path.Contains(TEXT("..")) || Path.Len()>240 || !FPackageName::IsValidLongPackageName(Path) || !Recipe->TryGetArrayField(TEXT("operations"),Ops) || !Recipe->TryGetArrayField(TEXT("variables"),VariableDefinitions) || !Recipe->TryGetArrayField(TEXT("components"),ComponentDefinitions) || !Recipe->TryGetArrayField(TEXT("nodes"),NodeDefinitions) || !Recipe->TryGetArrayField(TEXT("connections"),ConnectionDefinitions))
        return Fail(TEXT("invalid_arguments"),TEXT("Expected a /Game Blueprint and typed edit recipe."));
    const auto& Variables=*VariableDefinitions; const auto& Components=*ComponentDefinitions; const auto& Nodes=*NodeDefinitions; const auto& Connections=*ConnectionDefinitions;
    if (Ops->Num()>32 || Variables.Num()>32 || Components.Num()>32 || Nodes.Num()>32 || Connections.Num()>64 || (Ops->Num()+Variables.Num()+Components.Num()+Nodes.Num()+Connections.Num())<1 || (Ops->Num()+Variables.Num()+Components.Num()+Nodes.Num()+Connections.Num())>128)
        return Fail(TEXT("invalid_arguments"),TEXT("Recipe exceeds operation/node/connection bounds."));
    UBlueprint* BP=LoadObject<UBlueprint>(nullptr,*(Path+TEXT(".")+FPackageName::GetLongPackageAssetName(Path)));
    if (!BP) return Fail(TEXT("asset_not_found"),TEXT("Blueprint was not found."));
    if ((BP->Status!=BS_UpToDate && BP->Status!=BS_UpToDateWithWarnings) || BP->BlueprintType!=BPTYPE_Normal)
        return Fail(TEXT("invalid_context"),TEXT("Use a normal Blueprint with a successfully compiled baseline."));
    auto Before=Snapshot(BP);
    if (!Before->HasField(TEXT("graphs"))) return Fail(TEXT("asset_too_large"),TEXT("Blueprint exceeds edit snapshot bounds."));
    auto Identity=MakeShared<FJsonObject>(); Identity->SetObjectField(TEXT("state"),Before);
    Identity->SetStringField(TEXT("instance"),FString::Printf(TEXT("%p"),BP));
    Identity->SetStringField(TEXT("world_instance"),FString::Printf(TEXT("%p"),GEditor->GetEditorWorldContext().World()));
    FString Fingerprint=Serialize(Identity);
    if (Fingerprint.Len()>4*1024*1024) return Fail(TEXT("asset_too_large"),TEXT("Snapshot exceeds 4 MiB."));
    const TSet<FString> Fields{TEXT("op"),TEXT("graph"),TEXT("node_id"),TEXT("pin"),TEXT("value"),TEXT("x"),TEXT("y"),TEXT("to_node"),TEXT("to_pin")};
    TMap<FString,JObject> Definitions; TSet<FString> GraphNames; TArray<UEdGraph*> ExistingGraphs; BP->GetAllGraphs(ExistingGraphs); for (UEdGraph* ExistingGraph : ExistingGraphs) GraphNames.Add(ExistingGraph->GetName());
    TSet<FName> MemberNames;
    for (const FBPVariableDescription& Variable : BP->NewVariables) MemberNames.Add(Variable.VarName);
    for (TFieldIterator<FProperty> Property(BP->GeneratedClass);Property;++Property) MemberNames.Add(Property->GetFName());
    if (BP->SimpleConstructionScript) for (USCS_Node* Component : BP->SimpleConstructionScript->GetAllNodes()) if (Component) MemberNames.Add(Component->GetVariableName());
    TSet<FName> RequestedVariables;
    for (const auto& V : Variables)
    {
        if (V->Type!=EJson::Object) return Fail(TEXT("invalid_arguments"),TEXT("New Blueprint variables must be objects."));
        JObject Definition=V->AsObject().ToSharedRef(); const FString Name=Text(Definition,TEXT("name")), Type=Text(Definition,TEXT("type"));
        const TSet<FString> VariableFields{TEXT("name"),TEXT("type"),TEXT("default")};
        for (const auto& Pair : Definition->Values) if (!VariableFields.Contains(Pair.Key) || Pair.Value->Type!=EJson::String) return Fail(TEXT("invalid_arguments"),TEXT("Variable contains an unknown field or non-string value."));
        if (!Identifier(Name) || MemberNames.Contains(FName(*Name)) || !Identifier(Type) || VariablePinType(Type).PinCategory.IsNone() || Text(Definition,TEXT("default")).Len()>512) return Fail(TEXT("invalid_arguments"),TEXT("Variable name, native primitive type or default is invalid or conflicts with a member."));
        MemberNames.Add(FName(*Name)); RequestedVariables.Add(FName(*Name));
    }
    for (const auto& V : Components)
    {
        if (V->Type!=EJson::Object) return Fail(TEXT("invalid_arguments"),TEXT("New Blueprint components must be objects."));
        JObject Definition=V->AsObject().ToSharedRef(); const FString Name=Text(Definition,TEXT("name")), ClassPath=Text(Definition,TEXT("class_path"));
        for (const auto& Pair : Definition->Values)
            if ((Pair.Key!=TEXT("name") && Pair.Key!=TEXT("class_path") && Pair.Key!=TEXT("replication_mode") && Pair.Key!=TEXT("gas_setup")) ||
                ((Pair.Key==TEXT("name") || Pair.Key==TEXT("class_path")) && Pair.Value->Type!=EJson::String) ||
                (Pair.Key==TEXT("gas_setup") && Pair.Value->Type!=EJson::Null && Pair.Value->Type!=EJson::Object))
                return Fail(TEXT("invalid_arguments"),TEXT("Component contains an unknown field or incorrect value type."));
        if (!Identifier(Name) || MemberNames.Contains(FName(*Name)) || !ClassPath.StartsWith(TEXT("/Script/")) || ClassPath.Contains(TEXT(".."))) return Fail(TEXT("invalid_arguments"),TEXT("Component needs a unique identifier and native class path."));
        UClass* ComponentClass=LoadObject<UClass>(nullptr,*ClassPath);
        if (!ComponentClass || !ComponentClass->IsChildOf(UActorComponent::StaticClass()) || ComponentClass->HasAnyClassFlags(CLASS_Abstract|CLASS_Deprecated)) return Fail(TEXT("invalid_arguments"),TEXT("Component class must be a concrete native ActorComponent."));
        FString ReplicationMode, ComponentError;
        if (!ForgeGameplayAbilities::ValidateComponentDefinition(Definition,ComponentClass,ReplicationMode,ComponentError))
            return Fail(TEXT("invalid_arguments"),ComponentError);
        MemberNames.Add(FName(*Name));
    }
    TSet<FString> ValidGASAbilitySystemNames;
    if (BP->SimpleConstructionScript)
    {
        for (USCS_Node* Existing : BP->SimpleConstructionScript->GetAllNodes())
        {
            if (!Existing || !Existing->ComponentClass || !Existing->ComponentClass->IsChildOf(UAbilitySystemComponent::StaticClass())) continue;
            const UAbilitySystemComponent* Template=Cast<UAbilitySystemComponent>(Existing->ComponentTemplate);
            if (Template && Template->GetIsReplicated() &&
                ForgeGameplayAbilities::ReplicationModeName(Template->ReplicationMode)!=TEXT("unknown"))
                ValidGASAbilitySystemNames.Add(Existing->GetVariableName().ToString().ToLower());
        }
    }
    TArray<JObject> GASSetupDefinitions;
    for (const auto& V : Components)
    {
        JObject Definition=V->AsObject().ToSharedRef();
        UClass* Class=LoadObject<UClass>(nullptr,*Text(Definition,TEXT("class_path")));
        if (Class && Class->IsChildOf(UAbilitySystemComponent::StaticClass()))
            ValidGASAbilitySystemNames.Add(Text(Definition,TEXT("name")).ToLower());
        const TSharedPtr<FJsonValue>* SetupValue=Definition->Values.Find(TEXT("gas_setup"));
        if (SetupValue && SetupValue->IsValid() && (*SetupValue)->Type==EJson::Object)
            GASSetupDefinitions.Add((*SetupValue)->AsObject().ToSharedRef());
    }
    for (const JObject& Setup : GASSetupDefinitions)
    {
        const FString ASCName=Text(Setup,TEXT("ability_system_component"),TEXT("AbilitySystemComponent")).ToLower();
        if (!ValidGASAbilitySystemNames.Contains(ASCName))
            return Fail(TEXT("invalid_arguments"),TEXT("GAS startup settings must reference a replicated AbilitySystemComponent in the Blueprint."));
    }
    for (const auto& V : Nodes)
    {
        if (V->Type!=EJson::Object) return Fail(TEXT("invalid_arguments"),TEXT("New graph nodes must be objects."));
        JObject Definition=V->AsObject().ToSharedRef(); FString Alias=Text(Definition,TEXT("id")), Kind=Text(Definition,TEXT("kind")), Name=Text(Definition,TEXT("name"));
        const TSet<FString> NodeFields{TEXT("id"),TEXT("kind"),TEXT("name"),TEXT("owner_class"),TEXT("graph"),TEXT("x"),TEXT("y"),TEXT("execution_outputs"),TEXT("defaults")};
        for (const auto& Pair : Definition->Values)
            if (!NodeFields.Contains(Pair.Key) || ((Pair.Key==TEXT("id") || Pair.Key==TEXT("kind") || Pair.Key==TEXT("name") || Pair.Key==TEXT("owner_class") || Pair.Key==TEXT("graph")) && Pair.Value->Type!=EJson::String) || ((Pair.Key==TEXT("x") || Pair.Key==TEXT("y") || Pair.Key==TEXT("execution_outputs")) && Pair.Value->Type!=EJson::Number) || (Pair.Key==TEXT("defaults") && Pair.Value->Type!=EJson::Object)) return Fail(TEXT("invalid_arguments"),TEXT("New node contains an unknown field or incorrect field type."));
        if (Alias.IsEmpty() || Alias.Len()>64 || Definitions.Contains(Alias) || !GraphNames.Contains(Text(Definition,TEXT("graph"),TEXT("EventGraph"))) || Name.IsEmpty() || Name.Len()>64 || (Kind!=TEXT("branch") && Kind!=TEXT("sequence") && Kind!=TEXT("self") && Kind!=TEXT("reroute") && Kind!=TEXT("custom_event") && Kind!=TEXT("event") && Kind!=TEXT("call_function") && Kind!=TEXT("variable_get") && Kind!=TEXT("variable_set")))
            return Fail(TEXT("invalid_arguments"),TEXT("New node needs a unique id, existing graph, name and approved kind."));
        double X=0,Y=0,Count=2; Definition->TryGetNumberField(TEXT("x"),X); Definition->TryGetNumberField(TEXT("y"),Y); Definition->TryGetNumberField(TEXT("execution_outputs"),Count);
        if (!FMath::IsFinite(X) || !FMath::IsFinite(Y) || FMath::Abs(X)>100000 || FMath::Abs(Y)>100000 || FMath::FloorToDouble(X)!=X || FMath::FloorToDouble(Y)!=Y || !FMath::IsFinite(Count) || FMath::FloorToDouble(Count)!=Count || Count<2 || Count>16 || (Kind!=TEXT("sequence") && Count!=2))
            return Fail(TEXT("invalid_arguments"),TEXT("New-node position or Sequence output count is invalid."));
        if (Kind==TEXT("event")) { UFunction* Event=BP->ParentClass->FindFunctionByName(*Name); if (Text(Definition,TEXT("graph"),TEXT("EventGraph"))!=TEXT("EventGraph") || !Event || !Event->HasAnyFunctionFlags(FUNC_BlueprintEvent)) return Fail(TEXT("invalid_arguments"),TEXT("Event must override a native parent event in EventGraph.")); }
        if (Kind==TEXT("variable_get") || Kind==TEXT("variable_set")) { bool Found=RequestedVariables.Contains(FName(*Name)); for (const auto& Variable : BP->NewVariables) if (Variable.VarName==FName(*Name)) Found=true; if (!Found) return Fail(TEXT("invalid_arguments"),TEXT("Variable node must reference an existing or recipe-created Blueprint variable.")); }
        Definitions.Add(Alias,Definition);
    }
    TSet<FString> AllAliases; for (const auto& Pair : Definitions) AllAliases.Add(Pair.Key);
    auto RefExists=[&](const FString& Reference,const FString& GraphName){ if (AllAliases.Contains(Reference)) return true; return FindNode(BP,GraphName,Reference)!=nullptr; };
    for (const auto& V : Connections)
    {
        if (V->Type!=EJson::Object) return Fail(TEXT("invalid_arguments"),TEXT("New-node connections must be objects."));
        JObject C=V->AsObject().ToSharedRef(); FString GraphName=Text(C,TEXT("graph"),TEXT("EventGraph"));
        const TSet<FString> ConnectionFields{TEXT("graph"),TEXT("from_node"),TEXT("from_pin"),TEXT("to_node"),TEXT("to_pin")};
        for (const auto& Pair : C->Values) if (!ConnectionFields.Contains(Pair.Key) || Pair.Value->Type!=EJson::String) return Fail(TEXT("invalid_arguments"),TEXT("Connection has an unknown field or incorrect type."));
        const auto SourceDefinition=Definitions.Find(Text(C,TEXT("from_node"))), TargetDefinition=Definitions.Find(Text(C,TEXT("to_node")));
        if (!GraphNames.Contains(GraphName) || (SourceDefinition && Text(*SourceDefinition,TEXT("graph"),TEXT("EventGraph"))!=GraphName) || (TargetDefinition && Text(*TargetDefinition,TEXT("graph"),TEXT("EventGraph"))!=GraphName) || !RefExists(Text(C,TEXT("from_node")),GraphName) || !RefExists(Text(C,TEXT("to_node")),GraphName) || Text(C,TEXT("from_pin")).IsEmpty() || Text(C,TEXT("from_pin")).Len()>128 || Text(C,TEXT("to_pin")).IsEmpty() || Text(C,TEXT("to_pin")).Len()>128)
            return Fail(TEXT("invalid_arguments"),TEXT("Connection must reference existing or recipe-created nodes in an existing graph."));
    }
    for (const auto& V : *Ops)
    {
        if (V->Type!=EJson::Object) return Fail(TEXT("invalid_arguments"),TEXT("Expected edit objects."));
        auto Op=V->AsObject().ToSharedRef();
        for (const auto& Pair : Op->Values)
            if (!Fields.Contains(Pair.Key) || Pair.Value->Type!=((Pair.Key==TEXT("x") || Pair.Key==TEXT("y")) ? EJson::Number : EJson::String))
                return Fail(TEXT("invalid_arguments"),TEXT("Unknown field or incorrect JSON type."));
        const FString Kind=Text(Op,TEXT("op"));
        UEdGraphNode* Node=FindNode(BP,Text(Op,TEXT("graph")),Text(Op,TEXT("node_id")));
        if (!Node || !EditableNode(Node)) return Fail(TEXT("node_not_supported"),TEXT("Resolve an inspected node in the approved native node set."));
        if (Kind==TEXT("move"))
        {
            double X,Y;
            if (!Op->TryGetNumberField(TEXT("x"),X) || !Op->TryGetNumberField(TEXT("y"),Y) || !FMath::IsFinite(X) || !FMath::IsFinite(Y) || FMath::Abs(X)>100000 || FMath::Abs(Y)>100000 || FMath::FloorToDouble(X)!=X || FMath::FloorToDouble(Y)!=Y)
                return Fail(TEXT("invalid_arguments"),TEXT("Move requires bounded integer x/y."));
        }
        else if (Kind==TEXT("default"))
        {
            UEdGraphPin* Pin=Node->FindPin(*Text(Op,TEXT("pin")),EGPD_Input);
            const FString Value=Text(Op,TEXT("value"));
            if (!Pin || !Op->HasField(TEXT("value")) || Value.Len()>512 || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Exec || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Object || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Class)
                return Fail(TEXT("invalid_arguments"),TEXT("Expected an editable primitive input default."));
            if (Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Boolean && !Value.Equals(TEXT("true"),ESearchCase::IgnoreCase) && !Value.Equals(TEXT("false"),ESearchCase::IgnoreCase) && Value!=TEXT("0") && Value!=TEXT("1"))
                return Fail(TEXT("invalid_arguments"),TEXT("Invalid boolean default."));
            if (!Node->GetGraph()->GetSchema()->IsPinDefaultValid(Pin,Value,Pin->DefaultObject,Pin->DefaultTextValue).IsEmpty())
                return Fail(TEXT("invalid_arguments"),TEXT("Default failed native schema validation."));
        }
        else if (Kind==TEXT("connect") || Kind==TEXT("disconnect"))
        {
            UEdGraphNode* Target=FindNode(BP,Text(Op,TEXT("graph")),Text(Op,TEXT("to_node")));
            if (!Target || !EditableNode(Target) || !Node->FindPin(*Text(Op,TEXT("pin")),EGPD_Output) || !Target->FindPin(*Text(Op,TEXT("to_pin")),EGPD_Input))
                return Fail(TEXT("invalid_arguments"),TEXT("Expected approved nodes and exact output/input pins in one graph."));
        }
        else return Fail(TEXT("command_not_allowed"),TEXT("Edit operation is not allowlisted."));
    }
    if (Command==TEXT("blueprint_edit_preview"))
    {
        for (auto It=Previews.CreateIterator();It;++It) if (It.Value().Expires<=FPlatformTime::Seconds()) It.RemoveCurrent();
        if (Previews.Num()>=32) return Fail(TEXT("preview_limit"),TEXT("Too many previews."));
        FString Id=FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(Id,{Recipe,Fingerprint,FPlatformTime::Seconds()+600});
        Data->SetStringField(TEXT("preview_id"),Id); Data->SetObjectField(TEXT("changes"),Recipe.ToSharedRef());
        Data->SetBoolField(TEXT("saves_asset"),false); Data->SetStringField(TEXT("recovery"),TEXT("Blueprint-state JSON journal and in-memory rollback; not a full binary asset backup."));
        return true;
    }
    if (Plan.Fingerprint!=Fingerprint) return Fail(TEXT("stale_preview"),TEXT("Blueprint identity or state changed."));
    const FString Directory=FPaths::ProjectSavedDir()/TEXT("MajesticForge/Recovery");
    IFileManager::Get().MakeDirectory(*Directory,true);
    const FString Journal=Directory/(FGuid::NewGuid().ToString(EGuidFormats::Digits)+TEXT(".json"));
    if (!FFileHelper::SaveStringToFile(Serialize(Before),*Journal,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
        return Fail(TEXT("backup_failed"),TEXT("Graph recovery journal could not be written; no edits made."));
    FScopedTransaction Transaction(NSLOCTEXT("MajesticForge","EditBlueprint","ForgeMCP Blueprint edits"));
    BP->Modify(); bool Success=true; TArray<FString> AddedVariables, AddedComponents;
    for (const auto& V : Variables)
    {
        JObject Definition=V->AsObject().ToSharedRef(); const FString Name=Text(Definition,TEXT("name"));
        if (!FBlueprintEditorUtils::AddMemberVariable(BP,*Name,VariablePinType(Text(Definition,TEXT("type"))),Text(Definition,TEXT("default")))) { Success=false; break; }
        AddedVariables.Add(Name);
    }
    if (Success && Components.Num())
    {
        if (!BP->SimpleConstructionScript) Success=false;
        else
        {
            BP->SimpleConstructionScript->Modify();
            for (const auto& V : Components)
            {
                JObject Definition=V->AsObject().ToSharedRef(); UClass* ComponentClass=LoadObject<UClass>(nullptr,*Text(Definition,TEXT("class_path")));
                FString ReplicationMode, ComponentError;
                if (!ForgeGameplayAbilities::ValidateComponentDefinition(Definition,ComponentClass,ReplicationMode,ComponentError)) { Success=false; break; }
                USCS_Node* Component=ComponentClass ? BP->SimpleConstructionScript->CreateNode(ComponentClass,*Text(Definition,TEXT("name"))) : nullptr;
                if (!Component || !ForgeGameplayAbilities::ConfigureComponent(Component->ComponentTemplate,Definition,ComponentError)) { Success=false; if (!ComponentError.IsEmpty()) Message=ComponentError; break; }
                BP->SimpleConstructionScript->AddNode(Component); AddedComponents.Add(Component->VariableGuid.ToString());
            }
        }
    }
    TMap<FString,UEdGraphNode*> AddedNodes; TMap<FString,FString> AddedNodeGuids, AddedNodeGraphs, AddedNodeClasses;
    for (const auto& V : Nodes)
    {
        JObject Definition=V->AsObject().ToSharedRef(); const FString GraphName=Text(Definition,TEXT("graph"),TEXT("EventGraph"));
        UEdGraph* Graph=nullptr; for (UEdGraph* ExistingGraph : ExistingGraphs) if (ExistingGraph->GetName()==GraphName) Graph=ExistingGraph;
        if (Graph) Graph->Modify();
        UEdGraphNode* Node=Graph ? CreateNode(BP,Graph,Definition) : nullptr;
        if (!Node) { Success=false; break; }
        const FString Alias=Text(Definition,TEXT("id")); AddedNodes.Add(Alias,Node); AddedNodeGuids.Add(Alias,Node->NodeGuid.ToString()); AddedNodeGraphs.Add(Alias,GraphName); AddedNodeClasses.Add(Alias,Node->GetClass()->GetPathName());
        const TSharedPtr<FJsonObject>* Defaults=nullptr;
        if (Definition->TryGetObjectField(TEXT("defaults"),Defaults)) for (const auto& Pair : (*Defaults)->Values)
        {
            if (Pair.Value->Type!=EJson::String || Pair.Value->AsString().Len()>512) { Success=false; break; }
            UEdGraphPin* Pin=Node->FindPin(*Pair.Key,EGPD_Input);
            if (!Pin || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Exec || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Object || Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Class || (Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Boolean && !Pair.Value->AsString().Equals(TEXT("true"),ESearchCase::IgnoreCase) && !Pair.Value->AsString().Equals(TEXT("false"),ESearchCase::IgnoreCase) && Pair.Value->AsString()!=TEXT("0") && Pair.Value->AsString()!=TEXT("1")) || !Graph->GetSchema()->IsPinDefaultValid(Pin,Pair.Value->AsString(),Pin->DefaultObject,Pin->DefaultTextValue).IsEmpty()) { Success=false; break; }
            Graph->GetSchema()->TrySetDefaultValue(*Pin,Pair.Value->AsString());
        }
        if (!Success) break;
    }
    auto Resolve=[&](const FString& GraphName,const FString& Id)->UEdGraphNode* { if (UEdGraphNode** Found=AddedNodes.Find(Id)) return (*Found)->GetGraph()->GetName()==GraphName ? *Found : nullptr; return FindNode(BP,GraphName,Id); };
    if (Success) for (const auto& V : Connections)
    {
        JObject C=V->AsObject().ToSharedRef(); FString GraphName=Text(C,TEXT("graph"),TEXT("EventGraph")); UEdGraphNode* FromNode=Resolve(GraphName,Text(C,TEXT("from_node"))); UEdGraphNode* ToNode=Resolve(GraphName,Text(C,TEXT("to_node")));
        UEdGraphPin* From=FromNode ? FromNode->FindPin(*Text(C,TEXT("from_pin")),EGPD_Output) : nullptr; UEdGraphPin* To=ToNode ? ToNode->FindPin(*Text(C,TEXT("to_pin")),EGPD_Input) : nullptr;
        if (!From || !To || !FromNode->GetGraph()->GetSchema()->TryCreateConnection(From,To)) { Success=false; break; }
    }
    for (const auto& V : *Ops)
    {
        if (!Success) break;
        auto Op=V->AsObject().ToSharedRef(); auto* Node=FindNode(BP,Text(Op,TEXT("graph")),Text(Op,TEXT("node_id")));
        Node->Modify(); Node->GetGraph()->Modify(); const FString Kind=Text(Op,TEXT("op"));
        if (Kind==TEXT("move")) { Node->NodePosX=Op->GetIntegerField(TEXT("x")); Node->NodePosY=Op->GetIntegerField(TEXT("y")); }
        else if (Kind==TEXT("default")) Node->GetGraph()->GetSchema()->TrySetDefaultValue(*Node->FindPin(*Text(Op,TEXT("pin")),EGPD_Input),Text(Op,TEXT("value")));
        else
        {
            auto* Target=FindNode(BP,Text(Op,TEXT("graph")),Text(Op,TEXT("to_node"))); Target->Modify();
            auto* From=Node->FindPin(*Text(Op,TEXT("pin")),EGPD_Output); auto* To=Target->FindPin(*Text(Op,TEXT("to_pin")),EGPD_Input);
            if (Kind==TEXT("connect")) Success=Node->GetGraph()->GetSchema()->TryCreateConnection(From,To);
            else From->BreakLinkTo(To);
        }
        if (!Success) break;
    }
    FCompilerResultsLog Compiler;
    if (Success) { if (Nodes.Num() || Variables.Num() || Components.Num()) FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP); else FBlueprintEditorUtils::MarkBlueprintAsModified(BP); FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::None,&Compiler); Success=Compiler.NumErrors==0 && BP->Status!=BS_Error; }
    Data->SetNumberField(TEXT("compiler_errors"),Compiler.NumErrors); Data->SetNumberField(TEXT("compiler_warnings"),Compiler.NumWarnings);
    TArray<TSharedPtr<FJsonValue>> Diagnostics; for (const auto& M : Compiler.Messages) if (Diagnostics.Num()<100) Diagnostics.Add(MakeShared<FJsonValueString>(M->ToText().ToString()));
    Data->SetArrayField(TEXT("diagnostics"),Diagnostics);
    bool Recovered=true;
    if (!Success)
    {
        Recovered=Restore(BP,Before);
        if (Recovered) { FCompilerResultsLog Recovery; FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::None,&Recovery); Recovered=Recovery.NumErrors==0; }
        if (Recovered) BP->GetOutermost()->SetDirtyFlag(Before->GetBoolField(TEXT("dirty")));
        Transaction.Cancel();
    }
    else BP->MarkPackageDirty();
    Data->SetStringField(TEXT("state"),Success ? TEXT("completed") : Recovered ? TEXT("rolled_back") : TEXT("partial"));
    TArray<TSharedPtr<FJsonValue>> Added;
    if (Success) for (const auto& Pair : AddedNodeGuids) { auto Entry=MakeShared<FJsonObject>(); Entry->SetStringField(TEXT("id"),Pair.Key); Entry->SetStringField(TEXT("node_id"),Pair.Value); Entry->SetStringField(TEXT("graph"),AddedNodeGraphs[Pair.Key]); Entry->SetStringField(TEXT("class"),AddedNodeClasses[Pair.Key]); Added.Add(MakeShared<FJsonValueObject>(Entry)); }
    Data->SetArrayField(TEXT("created_nodes"),Added);
    TArray<TSharedPtr<FJsonValue>> VariableResults; if (Success) for (const FString& Name : AddedVariables) VariableResults.Add(MakeShared<FJsonValueString>(Name));
    TArray<TSharedPtr<FJsonValue>> ComponentResults; if (Success) for (const FString& Guid : AddedComponents) ComponentResults.Add(MakeShared<FJsonValueString>(Guid));
    Data->SetArrayField(TEXT("created_variables"),VariableResults); Data->SetArrayField(TEXT("created_components"),ComponentResults);
    Data->SetStringField(TEXT("asset_path"),Path); Data->SetStringField(TEXT("recovery_journal"),FPaths::ConvertRelativePathToFull(Journal));
    Data->SetBoolField(TEXT("saved"),false); return true;
}
