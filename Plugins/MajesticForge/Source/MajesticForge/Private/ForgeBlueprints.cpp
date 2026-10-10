#include "ForgeBlueprints.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "GameFramework/Actor.h"
#include "Components/ActorComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_Event.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_FunctionResult.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "K2Node_CallFunction.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_Self.h"
#include "K2Node_Knot.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Logging/TokenizedMessage.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Misc/PackageName.h"
#include "Misc/Guid.h"
#include "ScopedTransaction.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"
#include "ForgeGameplayAbilities.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;
TArray<TSharedPtr<FJsonValue>> Items(const JObject& Object, const TCHAR* Key)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    return Object->TryGetArrayField(Key, Values) ? *Values : TArray<TSharedPtr<FJsonValue>>();
}
FString Text(const JObject& Object, const TCHAR* Key, const FString& Default = FString())
{
    FString Value;
    return Object->TryGetStringField(Key, Value) ? Value : Default;
}
bool Identifier(const FString& Value)
{
    if (Value.IsEmpty() || Value.Len() > 64 || (!FChar::IsAlpha(Value[0]) && Value[0] != '_')) return false;
    for (TCHAR C : Value) if (!FChar::IsAlnum(C) && C != '_') return false;
    return true;
}
bool AssetPath(const FString& Value)
{
    return Value.StartsWith(TEXT("/Game/")) && Value.Len() <= 240 && !Value.Contains(TEXT("..")) && FPackageName::IsValidLongPackageName(Value);
}
UClass* NativeClass(const FString& Path)
{
    return Path.StartsWith(TEXT("/Script/")) && Path.Len() <= 240 ? LoadObject<UClass>(nullptr, *Path) : nullptr;
}
bool NodeFunctionAllowed(UFunction* Function)
{
    if (!Function || !Function->HasAnyFunctionFlags(FUNC_BlueprintCallable | FUNC_BlueprintPure)) return false;
    const FString Owner=Function->GetOuterUClass()->GetPathName(), Name=Function->GetName();
    if ((Owner==TEXT("/Script/Engine.KismetMathLibrary") || Owner==TEXT("/Script/Engine.KismetStringLibrary")) && Function->HasAnyFunctionFlags(FUNC_BlueprintPure)) return true;
    if (Owner==TEXT("/Script/Engine.KismetSystemLibrary")) return Name==TEXT("PrintString") || Name==TEXT("PrintText") || Name==TEXT("IsValid");
    if (Owner==TEXT("/Script/Engine.Actor")) return Name==TEXT("K2_GetActorLocation") || Name==TEXT("K2_GetActorRotation") || Name==TEXT("GetActorScale3D") || Name==TEXT("K2_SetActorLocation") || Name==TEXT("K2_SetActorRotation") || Name==TEXT("SetActorScale3D") || Name==TEXT("SetActorHiddenInGame");
    return false;
}
FEdGraphPinType PinType(const FString& Type)
{
    FEdGraphPinType Pin;
    if (Type == TEXT("bool")) Pin.PinCategory = UEdGraphSchema_K2::PC_Boolean;
    else if (Type == TEXT("int")) Pin.PinCategory = UEdGraphSchema_K2::PC_Int;
    else if (Type == TEXT("float")) { Pin.PinCategory = UEdGraphSchema_K2::PC_Real; Pin.PinSubCategory = UEdGraphSchema_K2::PC_Double; }
    else if (Type == TEXT("string")) Pin.PinCategory = UEdGraphSchema_K2::PC_String;
    else if (Type == TEXT("name")) Pin.PinCategory = UEdGraphSchema_K2::PC_Name;
    else if (Type == TEXT("vector") || Type == TEXT("rotator"))
    {
        Pin.PinCategory = UEdGraphSchema_K2::PC_Struct;
        Pin.PinSubCategoryObject = Type == TEXT("vector") ? TBaseStructure<FVector>::Get() : TBaseStructure<FRotator>::Get();
    }
    return Pin;
}
struct FFunctionPinSpec
{
    FString Name;
    FString Type;
};
struct FFunctionSpec
{
    FString Name;
    bool bPure = false;
    TArray<FFunctionPinSpec> Inputs;
    TArray<FFunctionPinSpec> Outputs;
};
bool ReadFunctionPinList(const JObject& Function, const TCHAR* Key,
    TArray<FFunctionPinSpec>& Pins, FString& Error)
{
    if (!Function->HasField(Key)) return true;
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Function->TryGetArrayField(Key, Values) || !Values || Values->Num() > 16)
    { Error = TEXT("Function inputs/outputs must be arrays containing at most 16 pins."); return false; }
    TSet<FString> Names;
    for (const auto& Value : *Values)
    {
        if (!Value.IsValid() || Value->Type != EJson::Object)
        { Error = TEXT("Function pins must be objects with a name and supported type."); return false; }
        auto Pin = Value->AsObject().ToSharedRef();
        for (const auto& Pair : Pin->Values)
            if (Pair.Key != TEXT("name") && Pair.Key != TEXT("type"))
            { Error = TEXT("Function pin has an unsupported field."); return false; }
        FFunctionPinSpec Spec;
        if (!Pin->TryGetStringField(TEXT("name"), Spec.Name) ||
            !Pin->TryGetStringField(TEXT("type"), Spec.Type) ||
            !Identifier(Spec.Name) || PinType(Spec.Type).PinCategory.IsNone() ||
            Names.Contains(Spec.Name.ToLower()))
        { Error = TEXT("Function pin name/type is invalid or duplicated."); return false; }
        Names.Add(Spec.Name.ToLower());
        Pins.Add(MoveTemp(Spec));
    }
    return true;
}
bool ParseFunctionSpec(const TSharedPtr<FJsonValue>& Value, FFunctionSpec& Function, FString& Error)
{
    if (!Value.IsValid()) { Error = TEXT("Function definition is missing."); return false; }
    if (Value->Type == EJson::String)
    {
        Function.Name = Value->AsString();
        return true;
    }
    if (Value->Type != EJson::Object)
    { Error = TEXT("Function definitions must be names or signature objects."); return false; }
    auto Object = Value->AsObject().ToSharedRef();
    for (const auto& Pair : Object->Values)
        if (Pair.Key != TEXT("name") && Pair.Key != TEXT("inputs") &&
            Pair.Key != TEXT("outputs") && Pair.Key != TEXT("pure"))
        { Error = TEXT("Function definition has an unsupported field."); return false; }
    if (!Object->TryGetStringField(TEXT("name"), Function.Name))
    { Error = TEXT("Function definition requires a name."); return false; }
    if (Object->HasField(TEXT("pure")) && !Object->TryGetBoolField(TEXT("pure"), Function.bPure))
    { Error = TEXT("Function pure must be a boolean."); return false; }
    if (!ReadFunctionPinList(Object, TEXT("inputs"), Function.Inputs, Error) ||
        !ReadFunctionPinList(Object, TEXT("outputs"), Function.Outputs, Error)) return false;
    if (Function.bPure && Function.Outputs.IsEmpty())
    { Error = TEXT("Pure functions must declare at least one output."); return false; }
    return true;
}
bool Validate(const JObject& Recipe, FString& Error)
{
    FString Path = Text(Recipe, TEXT("asset_path"));
    if (!AssetPath(Path)) { Error = TEXT("Use a new /Game package path."); return false; }
    if (FPackageName::DoesPackageExist(Path) || FindPackage(nullptr, *Path)) { Error = TEXT("Asset/package already exists; overwrites are not supported."); return false; }
    UClass* Parent = NativeClass(Text(Recipe, TEXT("parent_class"), TEXT("/Script/Engine.Actor")));
    if (!Parent || !Parent->IsChildOf(AActor::StaticClass()) || Parent->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NotPlaceable)) { Error = TEXT("Parent must be a concrete native actor class."); return false; }
    TSet<FString> NameKeys, FunctionNameKeys, Variables, Graphs{TEXT("EventGraph")}, Nodes;
    for (const auto& Pair : Recipe->Values)
        if ((Pair.Key == TEXT("variables") || Pair.Key == TEXT("components") || Pair.Key == TEXT("functions") || Pair.Key == TEXT("nodes") || Pair.Key == TEXT("connections")) && Pair.Value->Type != EJson::Array) { Error = TEXT("Expected recipe arrays."); return false; }
    if (Items(Recipe,TEXT("variables")).Num()>32 || Items(Recipe,TEXT("components")).Num()>32 || Items(Recipe,TEXT("functions")).Num()>16 || Items(Recipe,TEXT("nodes")).Num()>64 || Items(Recipe,TEXT("connections")).Num()>128) { Error = TEXT("Recipe exceeds operation limits."); return false; }
    for (const auto& V : Items(Recipe, TEXT("variables")))
    {
        if (V->Type != EJson::Object) { Error = TEXT("Variable must be an object."); return false; }
        auto Var = V->AsObject().ToSharedRef(); FString Name = Text(Var,TEXT("name"));
        if (!Identifier(Name) || NameKeys.Contains(Name.ToLower()) || FindFProperty<FProperty>(Parent, *Name) || PinType(Text(Var,TEXT("type"))).PinCategory.IsNone() || Text(Var,TEXT("default")).Len()>512) { Error = TEXT("Invalid variable name/type/default or duplicate member."); return false; }
        NameKeys.Add(Name.ToLower()); Variables.Add(Name);
    }
    TSet<FString> AbilitySystemComponentNames;
    TMap<FString, FString> AbilitySystemReplicationModes;
    TArray<TSharedRef<FJsonObject>> GASSetupDefinitions;
    for (const auto& V : Items(Recipe, TEXT("components")))
    {
        if (V->Type != EJson::Object) { Error = TEXT("Component must be an object."); return false; }
        auto Component = V->AsObject().ToSharedRef(); FString Name = Text(Component,TEXT("name"));
        UClass* Class = NativeClass(Text(Component,TEXT("class_path")));
        FString ReplicationMode;
        if (!ForgeGameplayAbilities::ValidateComponentDefinition(Component,Class,ReplicationMode,Error)) return false;
        if (!Identifier(Name) || NameKeys.Contains(Name.ToLower()) || FindFProperty<FProperty>(Parent, *Name) || !Class || !Class->IsChildOf(UActorComponent::StaticClass()) || Class->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated)) { Error = TEXT("Invalid component class/name or duplicate member."); return false; }
        if (Class->IsChildOf(UAbilitySystemComponent::StaticClass()))
        {
            AbilitySystemComponentNames.Add(Name.ToLower());
            FString ConfiguredMode;
            Component->TryGetStringField(TEXT("replication_mode"), ConfiguredMode);
            AbilitySystemReplicationModes.Add(Name.ToLower(), ConfiguredMode);
        }
        const TSharedPtr<FJsonValue>* SetupValue = Component->Values.Find(TEXT("gas_setup"));
        if (SetupValue && SetupValue->IsValid() && (*SetupValue)->Type == EJson::Object)
            GASSetupDefinitions.Add((*SetupValue)->AsObject().ToSharedRef());
        NameKeys.Add(Name.ToLower());
    }
    for (const TSharedRef<FJsonObject>& GASSetup : GASSetupDefinitions)
    {
        const FString ASCName = Text(GASSetup,TEXT("ability_system_component"),TEXT("AbilitySystemComponent")).ToLower();
        const FString* ASCMode = AbilitySystemReplicationModes.Find(ASCName);
        if (!AbilitySystemComponentNames.Contains(ASCName) || !ASCMode)
        {
            Error = TEXT("GAS startup settings must reference a Blueprint AbilitySystemComponent.");
            return false;
        }
        const FString SetupMode = Text(GASSetup, TEXT("replication_mode"));
        if (!SetupMode.IsEmpty() && SetupMode != *ASCMode)
        {
            Error = TEXT("GAS setup replication_mode must match its AbilitySystemComponent.");
            return false;
        }
    }
    for (const auto& Pair : AbilitySystemReplicationModes)
    {
        if (Pair.Value != TEXT("minimal") && Pair.Value != TEXT("mixed"))
        {
            continue;
        }
        const bool bHasMatchingSetup = GASSetupDefinitions.ContainsByPredicate(
            [&Pair](const TSharedRef<FJsonObject>& GASSetup)
            {
                return Text(GASSetup, TEXT("ability_system_component"), TEXT("AbilitySystemComponent"))
                    .Equals(Pair.Key, ESearchCase::IgnoreCase) &&
                    Text(GASSetup, TEXT("replication_mode")) == Pair.Value;
            });
        if (!bHasMatchingSetup)
        {
            Error = TEXT("minimal/mixed replication_mode requires a matching ForgeGameplayAbilitySetupComponent.");
            return false;
        }
    }
    for (const auto& V : Items(Recipe, TEXT("functions")))
    {
        FFunctionSpec Function;
        if (!ParseFunctionSpec(V, Function, Error)) return false;
        const FString FunctionKey = Function.Name.ToLower();
        if (!Identifier(Function.Name))
        { Error = TEXT("Function name is invalid."); return false; }
        if (Function.Name.Equals(TEXT("EventGraph"), ESearchCase::IgnoreCase))
        { Error = TEXT("Function name conflicts with the EventGraph name."); return false; }
        if (FunctionNameKeys.Contains(FunctionKey))
        { Error = TEXT("Function name is duplicated in the recipe."); return false; }
        if (NameKeys.Contains(FunctionKey))
        { Error = TEXT("Function name conflicts with a Blueprint variable or component."); return false; }
        if (Parent->FindFunctionByName(*Function.Name))
        { Error = TEXT("Function name conflicts with an inherited native function."); return false; }
        TSet<FString> ParameterNames;
        for (const FFunctionPinSpec& Pin : Function.Inputs)
        {
            const FString Key = Pin.Name.ToLower();
            if (ParameterNames.Contains(Key)) { Error = TEXT("Function input/output parameter names must be unique."); return false; }
            ParameterNames.Add(Key);
        }
        for (const FFunctionPinSpec& Pin : Function.Outputs)
        {
            const FString Key = Pin.Name.ToLower();
            if (ParameterNames.Contains(Key)) { Error = TEXT("Function input/output parameter names must be unique."); return false; }
            ParameterNames.Add(Key);
        }
        FunctionNameKeys.Add(FunctionKey); NameKeys.Add(FunctionKey); Graphs.Add(Function.Name);
    }
    TSet<FString> FunctionEntryReferences, FunctionResultReferences;
    for (const auto& V : Items(Recipe,TEXT("nodes")))
    {
        if (V->Type != EJson::Object) { Error = TEXT("Node must be an object."); return false; }
        auto N=V->AsObject().ToSharedRef(); FString Id=Text(N,TEXT("id")), Kind=Text(N,TEXT("kind")), Name=Text(N,TEXT("name")), Graph=Text(N,TEXT("graph"),TEXT("EventGraph"));
        if (!Identifier(Id) || Nodes.Contains(Id) || !Identifier(Name) || !Graphs.Contains(Graph)) { Error=TEXT("Invalid node id, name, or graph."); return false; }
        Nodes.Add(Id);
        double ExecutionOutputs = 2;
        if (N->HasField(TEXT("execution_outputs")) &&
            (N->Values[TEXT("execution_outputs")]->Type != EJson::Number || !N->TryGetNumberField(TEXT("execution_outputs"), ExecutionOutputs)))
            { Error=TEXT("execution_outputs must be an integer."); return false; }
        if (ExecutionOutputs < 2 || ExecutionOutputs > 16 || FMath::FloorToDouble(ExecutionOutputs) != ExecutionOutputs ||
            (Kind != TEXT("sequence") && ExecutionOutputs != 2))
            { Error=TEXT("Use 2 to 16 execution outputs on sequence nodes only."); return false; }
        for (const TCHAR* Coordinate : {TEXT("x"),TEXT("y")}) { double Number; if (N->HasField(Coordinate) && (!N->TryGetNumberField(Coordinate,Number) || !FMath::IsFinite(Number) || FMath::Abs(Number)>100000)) { Error=TEXT("Invalid node coordinates."); return false; } }
        const TSharedPtr<FJsonObject>* Defaults=nullptr;
        if (N->HasField(TEXT("defaults")) && !N->TryGetObjectField(TEXT("defaults"),Defaults)) { Error=TEXT("Pin defaults must be an object."); return false; }
        if (Kind==TEXT("function_entry") || Kind==TEXT("function_result"))
        {
            const FString ExpectedName = Kind==TEXT("function_entry") ? TEXT("Entry") : TEXT("Return");
            TSet<FString>& References = Kind==TEXT("function_entry") ? FunctionEntryReferences : FunctionResultReferences;
            const FString GraphKey = Graph.ToLower();
            if (Graph==TEXT("EventGraph") || Name!=ExpectedName || References.Contains(GraphKey))
            { Error=TEXT("Function entry/return references must uniquely target a declared function graph using the Entry or Return name."); return false; }
            References.Add(GraphKey);
        }
        else if (Kind==TEXT("event"))
        {
            UFunction* Event=Parent->FindFunctionByName(*Name);
            if (Graph!=TEXT("EventGraph") || !Event || !Event->HasAnyFunctionFlags(FUNC_BlueprintEvent) || NameKeys.Contains(Name.ToLower())) { Error=TEXT("Event must override a parent Blueprint event in EventGraph."); return false; }
            NameKeys.Add(Name.ToLower());
        }
        else if (Kind==TEXT("custom_event"))
        {
            if (Graph!=TEXT("EventGraph") || NameKeys.Contains(Name.ToLower()) || Parent->FindFunctionByName(*Name)) { Error=TEXT("Custom event name conflicts or is in a function graph."); return false; }
            NameKeys.Add(Name.ToLower());
        }
        else if (Kind==TEXT("variable_get") || Kind==TEXT("variable_set"))
        { if (!Variables.Contains(Name)) { Error=TEXT("Variable node references an undeclared recipe variable."); return false; } }
        else if (Kind==TEXT("call_function"))
        {
            UClass* Owner=NativeClass(Text(N,TEXT("owner_class"),TEXT("/Script/Engine.Actor")));
            UFunction* Function=Owner ? Owner->FindFunctionByName(*Name) : nullptr;
            if (!NodeFunctionAllowed(Function)) { Error=TEXT("Function is not in the recipe's approved native function set. Script/console execution nodes are prohibited."); return false; }
        }
        else if (Kind!=TEXT("branch") && Kind!=TEXT("sequence") && Kind!=TEXT("self") && Kind!=TEXT("reroute"))
            { Error=TEXT("Unsupported graph node kind."); return false; }
    }
    for (const auto& V : Items(Recipe,TEXT("connections")))
    {
        if (V->Type!=EJson::Object) { Error=TEXT("Connection must be an object."); return false; }
        auto C=V->AsObject().ToSharedRef();
        if (!Nodes.Contains(Text(C,TEXT("from_node"))) || !Nodes.Contains(Text(C,TEXT("to_node"))) || Text(C,TEXT("from_pin")).IsEmpty() || Text(C,TEXT("to_pin")).IsEmpty()) { Error=TEXT("Connection references missing nodes/pins."); return false; }
    }
    const auto Location=Items(Recipe,TEXT("location"));
    if (Recipe->HasField(TEXT("location")) && Location.Num()!=3) { Error=TEXT("location requires three finite numbers."); return false; }
    for (const auto& V : Location) { double Number; if (!V->TryGetNumber(Number) || !FMath::IsFinite(Number) || FMath::Abs(Number)>1e8) { Error=TEXT("Invalid location."); return false; } }
    for (const TCHAR* Key : {TEXT("save"),TEXT("place")}) { bool Value; if (Recipe->HasField(Key) && !Recipe->TryGetBoolField(Key,Value)) { Error=TEXT("save/place must be booleans."); return false; } }
    return true;
}
void Inspect(UBlueprint* BP, JObject Data)
{
    Data->SetStringField(TEXT("asset_path"),BP->GetPathName());
    Data->SetStringField(TEXT("parent_class"),BP->ParentClass->GetPathName());
    Data->SetNumberField(TEXT("compile_status"),static_cast<int32>(BP->Status));
    TArray<TSharedPtr<FJsonValue>> Variables, Components, Graphs;
    UObject* Defaults=BP->GeneratedClass ? BP->GeneratedClass->GetDefaultObject() : nullptr;
    TMap<FName, FString> ConfiguredReplicationModes;
    if (BP->SimpleConstructionScript)
    {
        for (USCS_Node* Node : BP->SimpleConstructionScript->GetAllNodes())
        {
            const UForgeGameplayAbilitySetupComponent* GASSetup =
                Node ? Cast<UForgeGameplayAbilitySetupComponent>(Node->ComponentTemplate) : nullptr;
            if (GASSetup && GASSetup->bConfigureReplicationMode)
            {
                ConfiguredReplicationModes.Add(
                    GASSetup->AbilitySystemComponentName,
                    ForgeGameplayAbilities::ReplicationModeName(GASSetup->ReplicationMode));
            }
        }
    }
    for (const auto& V : BP->NewVariables)
    {
        auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("name"),V.VarName.ToString()); J->SetStringField(TEXT("type"),V.VarType.PinCategory.ToString());
        FString DefaultValue=V.DefaultValue;
        if (Defaults) if (FProperty* Property=BP->GeneratedClass->FindPropertyByName(V.VarName)) Property->ExportTextItem_Direct(DefaultValue,Property->ContainerPtrToValuePtr<void>(Defaults),nullptr,Defaults,PPF_None);
        J->SetStringField(TEXT("default"),DefaultValue); Variables.Add(MakeShared<FJsonValueObject>(J));
    }
    if (BP->SimpleConstructionScript) for (auto* Node : BP->SimpleConstructionScript->GetAllNodes())
    {
        auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("name"),Node->GetVariableName().ToString()); J->SetStringField(TEXT("class"),Node->ComponentClass->GetPathName());
        if (const UAbilitySystemComponent* AbilitySystem=Cast<UAbilitySystemComponent>(Node->ComponentTemplate))
        {
            J->SetBoolField(TEXT("replicated"),AbilitySystem->GetIsReplicated());
            const FString TemplateMode = ForgeGameplayAbilities::ReplicationModeName(AbilitySystem->ReplicationMode);
            const FString* ConfiguredMode = ConfiguredReplicationModes.Find(Node->GetVariableName());
            J->SetStringField(TEXT("replication_mode"), ConfiguredMode ? *ConfiguredMode : TemplateMode);
            J->SetBoolField(TEXT("replication_mode_configured"), ConfiguredMode != nullptr);
            J->SetStringField(TEXT("component_template_replication_mode"), TemplateMode);
        }
        if (const UForgeGameplayAbilitySetupComponent* GASSetup=Cast<UForgeGameplayAbilitySetupComponent>(Node->ComponentTemplate))
        {
            J->SetStringField(TEXT("gas_ability_system_component"),GASSetup->AbilitySystemComponentName.ToString());
            J->SetBoolField(TEXT("gas_configures_replication_mode"),GASSetup->bConfigureReplicationMode);
            J->SetStringField(TEXT("gas_replication_mode"),ForgeGameplayAbilities::ReplicationModeName(GASSetup->ReplicationMode));
            J->SetBoolField(TEXT("gas_initialize_owner_as_avatar"),GASSetup->bInitializeOwnerAsAvatar);
            TArray<TSharedPtr<FJsonValue>> AttributeSets, Abilities, Effects;
            for (const TSubclassOf<UAttributeSet>& AttributeSet : GASSetup->AttributeSets)
                if (AttributeSet) AttributeSets.Add(MakeShared<FJsonValueString>(AttributeSet->GetPathName()));
            for (const FForgeGASAbilityGrant& Grant : GASSetup->StartupAbilities)
            {
                auto Entry=MakeShared<FJsonObject>();
                if (Grant.AbilityClass) Entry->SetStringField(TEXT("class_path"),Grant.AbilityClass->GetPathName());
                Entry->SetNumberField(TEXT("level"),Grant.Level); Entry->SetNumberField(TEXT("input_id"),Grant.InputId);
                Abilities.Add(MakeShared<FJsonValueObject>(Entry));
            }
            for (const FForgeGASStartupEffect& Grant : GASSetup->StartupEffects)
            {
                auto Entry=MakeShared<FJsonObject>();
                if (Grant.EffectClass) Entry->SetStringField(TEXT("class_path"),Grant.EffectClass->GetPathName());
                Entry->SetNumberField(TEXT("level"),Grant.Level); Effects.Add(MakeShared<FJsonValueObject>(Entry));
            }
            J->SetArrayField(TEXT("gas_attribute_sets"),AttributeSets);
            J->SetArrayField(TEXT("gas_startup_abilities"),Abilities);
            J->SetArrayField(TEXT("gas_startup_effects"),Effects);
        }
        Components.Add(MakeShared<FJsonValueObject>(J));
    }
    TArray<UEdGraph*> AllGraphs; BP->GetAllGraphs(AllGraphs);
    for (auto* Graph : AllGraphs)
    {
        if (Graphs.Num()>=64) break;
        auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("name"),Graph->GetName()); TArray<TSharedPtr<FJsonValue>> Nodes;
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Nodes.Num()>=128) break;
            auto N=MakeShared<FJsonObject>(); N->SetStringField(TEXT("id"),Node->NodeGuid.ToString()); N->SetStringField(TEXT("class"),Node->GetClass()->GetPathName()); N->SetStringField(TEXT("title"),Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
            N->SetNumberField(TEXT("x"),Node->NodePosX); N->SetNumberField(TEXT("y"),Node->NodePosY);
            TArray<TSharedPtr<FJsonValue>> Pins;
            for (auto* Pin : Node->Pins) { auto P=MakeShared<FJsonObject>(); P->SetStringField(TEXT("name"),Pin->PinName.ToString()); P->SetStringField(TEXT("type"),Pin->PinType.PinCategory.ToString()); P->SetStringField(TEXT("direction"),Pin->Direction==EGPD_Input?TEXT("input"):TEXT("output")); P->SetStringField(TEXT("default"),Pin->DefaultValue); TArray<TSharedPtr<FJsonValue>> Links; for (auto* Link : Pin->LinkedTo) Links.Add(MakeShared<FJsonValueString>(Link->GetOwningNode()->NodeGuid.ToString()+TEXT(":")+Link->PinName.ToString())); P->SetArrayField(TEXT("links"),Links); Pins.Add(MakeShared<FJsonValueObject>(P)); }
            N->SetArrayField(TEXT("pins"),Pins); Nodes.Add(MakeShared<FJsonValueObject>(N));
        }
        J->SetArrayField(TEXT("nodes"),Nodes); J->SetNumberField(TEXT("total_nodes"),Graph->Nodes.Num()); J->SetBoolField(TEXT("truncated"),Graph->Nodes.Num()>Nodes.Num()); Graphs.Add(MakeShared<FJsonValueObject>(J));
    }
    Data->SetArrayField(TEXT("variables"),Variables); Data->SetArrayField(TEXT("components"),Components); Data->SetArrayField(TEXT("graphs"),Graphs); Data->SetBoolField(TEXT("graphs_truncated"),AllGraphs.Num()>Graphs.Num());
}
}

bool FForgeBlueprints::Handle(const FString& Command, const JObject& Args, JObject Data, FString& Code, FString& Message)
{
    check(IsInGameThread());
    auto Fail=[&](const TCHAR* ErrorCode,const FString& Error) { Code=ErrorCode; Message=Error; return false; };
    if (Command==TEXT("class_info"))
    {
        UClass* Class=NativeClass(Text(Args,TEXT("class_path")));
        if (!Class) return Fail(TEXT("class_not_found"),TEXT("Native class was not found."));
        Data->SetStringField(TEXT("class_path"),Class->GetPathName()); TArray<TSharedPtr<FJsonValue>> Properties, Functions; int32 PropertyCount=0,FunctionCount=0;
        for (TFieldIterator<FProperty> It(Class);It;++It) { ++PropertyCount; if (Properties.Num()>=200) continue; auto P=MakeShared<FJsonObject>(); P->SetStringField(TEXT("name"),It->GetName()); P->SetStringField(TEXT("cpp_type"),It->GetCPPType()); P->SetBoolField(TEXT("editable"),It->HasAnyPropertyFlags(CPF_Edit)); Properties.Add(MakeShared<FJsonValueObject>(P)); }
        for (TFieldIterator<UFunction> It(Class);It;++It)
        {
            if (!It->HasAnyFunctionFlags(FUNC_BlueprintCallable|FUNC_BlueprintPure)) continue;
            ++FunctionCount; if (Functions.Num()>=200) continue;
            auto F=MakeShared<FJsonObject>(); F->SetStringField(TEXT("name"),It->GetName()); F->SetBoolField(TEXT("recipe_supported"),NodeFunctionAllowed(*It)); F->SetBoolField(TEXT("static"),It->HasAnyFunctionFlags(FUNC_Static)); F->SetBoolField(TEXT("pure"),It->HasAnyFunctionFlags(FUNC_BlueprintPure)); TArray<TSharedPtr<FJsonValue>> Parameters;
            for (TFieldIterator<FProperty> P(*It);P && P->HasAnyPropertyFlags(CPF_Parm);++P) { auto V=MakeShared<FJsonObject>(); V->SetStringField(TEXT("name"),P->GetName()); V->SetStringField(TEXT("cpp_type"),P->GetCPPType()); V->SetBoolField(TEXT("output"),P->HasAnyPropertyFlags(CPF_OutParm|CPF_ReturnParm)); Parameters.Add(MakeShared<FJsonValueObject>(V)); }
            F->SetArrayField(TEXT("parameters"),Parameters); Functions.Add(MakeShared<FJsonValueObject>(F));
        }
        Data->SetArrayField(TEXT("properties"),Properties); Data->SetArrayField(TEXT("functions"),Functions); Data->SetNumberField(TEXT("total_properties"),PropertyCount); Data->SetNumberField(TEXT("total_functions"),FunctionCount); Data->SetBoolField(TEXT("truncated"),PropertyCount>Properties.Num() || FunctionCount>Functions.Num()); return true;
    }
    if (Command==TEXT("blueprint_info"))
    {
        FString Path=Text(Args,TEXT("asset_path"));
        if (!AssetPath(Path)) return Fail(TEXT("invalid_arguments"),TEXT("Expected a /Game package path."));
        UBlueprint* BP=LoadObject<UBlueprint>(nullptr,*(Path+TEXT(".")+FPackageName::GetLongPackageAssetName(Path)));
        if (!BP) return Fail(TEXT("asset_not_found"),TEXT("Blueprint was not found.")); Inspect(BP,Data); return true;
    }
    UWorld* World=GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!World || GEditor->PlayWorld) return Fail(TEXT("invalid_context"),TEXT("An editor world outside PIE is required."));
    if (Command==TEXT("blueprint_preview"))
    {
        const TSharedPtr<FJsonObject>* Recipe=nullptr;
        if (!Args->TryGetObjectField(TEXT("recipe"),Recipe) || !Validate(Recipe->ToSharedRef(),Message)) return Fail(TEXT("invalid_recipe"),Message.IsEmpty()?TEXT("Expected recipe object."):Message);
        const double Now=FPlatformTime::Seconds();
        for (auto It=Previews.CreateIterator();It;++It) if (It.Value().Expires<=Now) It.RemoveCurrent();
        if (Previews.Num()>=32) return Fail(TEXT("preview_limit"),TEXT("Too many pending previews."));
        FString Id=FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(Id,{*Recipe,World->GetPathName(),Now+600}); Data->SetStringField(TEXT("preview_id"),Id); Data->SetNumberField(TEXT("expires_in_seconds"),600); Data->SetObjectField(TEXT("changes"),*Recipe); Data->SetStringField(TEXT("world"),World->GetPathName()); Data->SetStringField(TEXT("recovery"),TEXT("New assets only; failed graph/compile changes are discarded before saving. Actor placement uses an editor transaction.")); return true;
    }
    if (Command!=TEXT("blueprint_apply")) return Fail(TEXT("command_not_allowed"),TEXT("Unsupported Blueprint command."));
    FString Id=Text(Args,TEXT("preview_id"));
    if (Id.IsEmpty() || Text(Args,TEXT("confirmation"))!=Id) return Fail(TEXT("confirmation_required"),TEXT("confirmation must equal the reviewed preview_id."));
    FPreview Preview;
    if (!Previews.RemoveAndCopyValue(Id,Preview) || Preview.Expires<=FPlatformTime::Seconds()) return Fail(TEXT("preview_not_found"),TEXT("Preview expired, consumed, or belongs to another session."));
    if (Preview.World!=World->GetPathName()) return Fail(TEXT("stale_preview"),TEXT("Editor world changed; inspect and preview again."));
    if (!Validate(Preview.Recipe.ToSharedRef(),Message)) return Fail(TEXT("stale_preview"),Message);
    JObject Recipe=Preview.Recipe.ToSharedRef(); FString Path=Text(Recipe,TEXT("asset_path"));
    UClass* Parent=NativeClass(Text(Recipe,TEXT("parent_class"),TEXT("/Script/Engine.Actor")));
    UPackage* Package=CreatePackage(*Path);
    FScopedTransaction Transaction(FText::FromString(TEXT("ForgeMCP: create Blueprint")));
    UBlueprint* BP=FKismetEditorUtilities::CreateBlueprint(Parent,Package,*FPackageName::GetLongPackageAssetName(Path),BPTYPE_Normal,UBlueprint::StaticClass(),UBlueprintGeneratedClass::StaticClass(),TEXT("MajesticForge"));
    auto Discard=[&](const FString& Error)
    {
        Transaction.Cancel();
        if (BP) { BP->ClearFlags(RF_Public|RF_Standalone); BP->Rename(nullptr,GetTransientPackage(),REN_DontCreateRedirectors|REN_NonTransactional); }
        Package->SetDirtyFlag(false); Package->SetFlags(RF_Transient); Package->Rename(*(TEXT("/Temp/ForgeDiscard_")+FGuid::NewGuid().ToString(EGuidFormats::Digits)),nullptr,REN_DontCreateRedirectors|REN_NonTransactional);
        Data->SetStringField(TEXT("state"),TEXT("rolled_back")); Data->SetStringField(TEXT("message"),Error); Data->SetBoolField(TEXT("saved"),false); Data->SetBoolField(TEXT("placed"),false); return true;
    };
    if (!BP) return Discard(TEXT("Blueprint creation failed."));
    BP->Modify();
    for (const auto& V : Items(Recipe,TEXT("variables"))) { auto Var=V->AsObject().ToSharedRef(); if (!FBlueprintEditorUtils::AddMemberVariable(BP,*Text(Var,TEXT("name")),PinType(Text(Var,TEXT("type"))),Text(Var,TEXT("default")))) return Discard(TEXT("Variable creation failed.")); }
    for (const auto& V : Items(Recipe,TEXT("components")))
    {
        auto C=V->AsObject().ToSharedRef(); UClass* Class=NativeClass(Text(C,TEXT("class_path")));
        FString ReplicationMode;
        if (!ForgeGameplayAbilities::ValidateComponentDefinition(C,Class,ReplicationMode,Message)) return Discard(Message);
        auto* Node=BP->SimpleConstructionScript->CreateNode(Class,*Text(C,TEXT("name")));
        if (!Node) return Discard(TEXT("Blueprint component node could not be created."));
        if (!ForgeGameplayAbilities::ConfigureComponent(Node->ComponentTemplate,C,Message))
            return Discard(Message.IsEmpty()?TEXT("Blueprint component configuration failed."):Message);
        BP->SimpleConstructionScript->AddNode(Node);
    }
    TMap<FString,UEdGraph*> Graphs;
    UEdGraph* EventGraph=FBlueprintEditorUtils::FindEventGraph(BP);
    if (!EventGraph) { EventGraph=FBlueprintEditorUtils::CreateNewGraph(BP,TEXT("EventGraph"),UEdGraph::StaticClass(),UEdGraphSchema_K2::StaticClass()); FBlueprintEditorUtils::AddUbergraphPage(BP,EventGraph); }
    Graphs.Add(TEXT("EventGraph"),EventGraph);
    for (const auto& V : Items(Recipe,TEXT("functions")))
    {
        FFunctionSpec Function;
        if (!ParseFunctionSpec(V, Function, Message)) return Discard(Message);
        UEdGraph* FunctionGraph=FBlueprintEditorUtils::CreateNewGraph(BP,*Function.Name,UEdGraph::StaticClass(),UEdGraphSchema_K2::StaticClass());
        FBlueprintEditorUtils::AddFunctionGraph<UFunction>(BP,FunctionGraph,true,nullptr);
        TArray<UK2Node_FunctionEntry*> Entries; FunctionGraph->GetNodesOfClass<UK2Node_FunctionEntry>(Entries);
        if (Entries.Num()!=1) return Discard(TEXT("Function graph did not create exactly one entry node."));
        UK2Node_FunctionEntry* Entry=Entries[0]; Entry->Modify();
        for (const FFunctionPinSpec& Pin : Function.Inputs)
        {
            const FEdGraphPinType Type=PinType(Pin.Type); FText PinError;
            if (!Entry->CanCreateUserDefinedPin(Type,EGPD_Output,PinError) ||
                !Entry->CreateUserDefinedPin(FName(*Pin.Name),Type,EGPD_Output,false))
                return Discard(TEXT("Function input pin could not be created."));
        }
        UK2Node_FunctionResult* Result=nullptr;
        if (Function.Outputs.Num())
        {
            Result=FBlueprintEditorUtils::FindOrCreateFunctionResultNode(Entry);
            if (!Result) return Discard(TEXT("Function return node could not be created."));
            Result->Modify();
            for (const FFunctionPinSpec& Pin : Function.Outputs)
            {
                const FEdGraphPinType Type=PinType(Pin.Type); FText PinError;
                if (!Result->CanCreateUserDefinedPin(Type,EGPD_Input,PinError) ||
                    !Result->CreateUserDefinedPin(FName(*Pin.Name),Type,EGPD_Input,false))
                    return Discard(TEXT("Function output pin could not be created."));
            }
        }
        if (Function.bPure)
        {
            Entry->AddExtraFlags(FUNC_BlueprintPure);
            Entry->ReconstructNode();
            if (Result) Result->ReconstructNode();
        }
        Graphs.Add(Function.Name,FunctionGraph);
    }
    TMap<FString,UEdGraphNode*> Nodes;
    for (const auto& V : Items(Recipe,TEXT("nodes")))
    {
        auto N=V->AsObject().ToSharedRef(); FString Kind=Text(N,TEXT("kind")), Name=Text(N,TEXT("name")); auto* Graph=Graphs[Text(N,TEXT("graph"),TEXT("EventGraph"))]; UEdGraphNode* Node=nullptr;
        if (Kind==TEXT("event"))
        {
            for (UEdGraphNode* Existing : Graph->Nodes) { auto* Event=Cast<UK2Node_Event>(Existing); if (Event && Event->bOverrideFunction && Event->EventReference.GetMemberName()==FName(*Name)) { Node=Event; break; } }
            if (!Node) { auto* Event=NewObject<UK2Node_Event>(Graph); Event->EventReference.SetExternalMember(*Name,Parent); Event->bOverrideFunction=true; Node=Event; }
        }
        else if (Kind==TEXT("custom_event")) { auto* Event=NewObject<UK2Node_CustomEvent>(Graph); Event->CustomFunctionName=*Name; Node=Event; }
        else if (Kind==TEXT("variable_get")) { auto* Get=NewObject<UK2Node_VariableGet>(Graph); Get->VariableReference.SetSelfMember(*Name); Node=Get; }
        else if (Kind==TEXT("variable_set")) { auto* Set=NewObject<UK2Node_VariableSet>(Graph); Set->VariableReference.SetSelfMember(*Name); Node=Set; }
        else if (Kind==TEXT("function_entry")) { TArray<UK2Node_FunctionEntry*> Entries; Graph->GetNodesOfClass<UK2Node_FunctionEntry>(Entries); if (Entries.Num()!=1) return Discard(TEXT("Function graph entry reference is ambiguous.")); Node=Entries[0]; }
        else if (Kind==TEXT("function_result")) { TArray<UK2Node_FunctionEntry*> Entries; Graph->GetNodesOfClass<UK2Node_FunctionEntry>(Entries); if (Entries.Num()!=1) return Discard(TEXT("Function graph return reference has no unique entry.")); Node=FBlueprintEditorUtils::FindOrCreateFunctionResultNode(Entries[0]); }
        else if (Kind==TEXT("branch")) Node=NewObject<UK2Node_IfThenElse>(Graph);
        else if (Kind==TEXT("sequence")) Node=NewObject<UK2Node_ExecutionSequence>(Graph);
        else if (Kind==TEXT("self")) Node=NewObject<UK2Node_Self>(Graph);
        else if (Kind==TEXT("reroute")) Node=NewObject<UK2Node_Knot>(Graph);
        else { auto* Call=NewObject<UK2Node_CallFunction>(Graph); Call->SetFromFunction(NativeClass(Text(N,TEXT("owner_class"),TEXT("/Script/Engine.Actor")))->FindFunctionByName(*Name)); Node=Call; }
        if (!Node) return Discard(TEXT("Blueprint graph node could not be created."));
        if (!Graph->Nodes.Contains(Node)) { Node->SetFlags(RF_Transactional); Graph->AddNode(Node,false,false); Node->CreateNewGuid(); Node->PostPlacedNewNode(); Node->AllocateDefaultPins(); }
        if (auto* Sequence=Cast<UK2Node_ExecutionSequence>(Node))
        {
            double Count=2; N->TryGetNumberField(TEXT("execution_outputs"),Count);
            for (int32 Index=2; Index<static_cast<int32>(Count); ++Index) Sequence->AddInputPin();
        }
        double X=0,Y=0; N->TryGetNumberField(TEXT("x"),X); N->TryGetNumberField(TEXT("y"),Y); Node->NodePosX=FMath::Clamp(X,-100000.0,100000.0); Node->NodePosY=FMath::Clamp(Y,-100000.0,100000.0); Nodes.Add(Text(N,TEXT("id")),Node);
        const TSharedPtr<FJsonObject>* Defaults=nullptr;
        if (N->TryGetObjectField(TEXT("defaults"),Defaults)) for (const auto& Pair : (*Defaults)->Values)
        {
            if (Pair.Value->Type!=EJson::String || Pair.Value->AsString().Len()>512) return Discard(TEXT("Invalid pin default."));
            UEdGraphPin* Pin=Node->FindPin(*Pair.Key,EGPD_Input);
            if (!Pin) return Discard(TEXT("Input default pin was not found."));
            const FString Default=Pair.Value->AsString();
            if (Pin->PinType.PinCategory==UEdGraphSchema_K2::PC_Boolean &&
                !Default.Equals(TEXT("true"),ESearchCase::IgnoreCase) && !Default.Equals(TEXT("false"),ESearchCase::IgnoreCase) &&
                Default!=TEXT("0") && Default!=TEXT("1"))
                return Discard(TEXT("Boolean defaults must be true, false, 0 or 1."));
            if (!Graph->GetSchema()->IsPinDefaultValid(Pin,Default,Pin->DefaultObject,Pin->DefaultTextValue).IsEmpty())
                return Discard(TEXT("Pin default failed native schema validation."));
            Graph->GetSchema()->TrySetDefaultValue(*Pin,Default);
        }
    }
    for (const auto& V : Items(Recipe,TEXT("connections"))) { auto C=V->AsObject().ToSharedRef(); auto* From=Nodes[Text(C,TEXT("from_node"))]->FindPin(*Text(C,TEXT("from_pin")),EGPD_Output); auto* To=Nodes[Text(C,TEXT("to_node"))]->FindPin(*Text(C,TEXT("to_pin")),EGPD_Input); if (!From || !To || From->GetOwningNode()->GetGraph()!=To->GetOwningNode()->GetGraph() || !From->GetOwningNode()->GetGraph()->GetSchema()->TryCreateConnection(From,To)) return Discard(TEXT("Pin connection failed schema validation.")); }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FCompilerResultsLog Compiler; FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::None,&Compiler);
    TArray<TSharedPtr<FJsonValue>> Diagnostics; for (const auto& M : Compiler.Messages) { if (Diagnostics.Num()>=100) break; Diagnostics.Add(MakeShared<FJsonValueString>(M->ToText().ToString())); }
    Data->SetNumberField(TEXT("compiler_errors"),Compiler.NumErrors); Data->SetNumberField(TEXT("compiler_warnings"),Compiler.NumWarnings); Data->SetArrayField(TEXT("diagnostics"),Diagnostics);
    if (Compiler.NumErrors || BP->Status==BS_Error || !BP->GeneratedClass) return Discard(TEXT("Blueprint compilation failed."));
    bool Save=false,Place=false; Recipe->TryGetBoolField(TEXT("save"),Save); Recipe->TryGetBoolField(TEXT("place"),Place); bool Saved=false;
    if (Save) { FSavePackageArgs SaveArgs; SaveArgs.TopLevelFlags=RF_Public|RF_Standalone; FString Filename=FPackageName::LongPackageNameToFilename(Path,FPackageName::GetAssetPackageExtension()); Saved=UPackage::SavePackage(Package,BP,*Filename,SaveArgs); }
    AActor* Actor=nullptr;
    if (Place) { FVector Location=FVector::ZeroVector; auto L=Items(Recipe,TEXT("location")); if (L.Num()==3) Location=FVector(L[0]->AsNumber(),L[1]->AsNumber(),L[2]->AsNumber()); World->GetCurrentLevel()->Modify(); Actor=GEditor->AddActor(World->GetCurrentLevel(),BP->GeneratedClass,FTransform(Location),true,RF_Transactional,false); }
    FAssetRegistryModule::AssetCreated(BP); if (!Saved) BP->MarkPackageDirty();
    Inspect(BP,Data); Data->SetBoolField(TEXT("saved"),Saved); Data->SetBoolField(TEXT("placed"),Actor!=nullptr); Data->SetBoolField(TEXT("level_saved"),false); Data->SetStringField(TEXT("actor_path"),Actor?Actor->GetPathName():FString()); Data->SetStringField(TEXT("state"),(!Save||Saved)&&(!Place||Actor)?TEXT("completed"):TEXT("partial")); return true;
}
