#if WITH_DEV_AUTOMATION_TESTS

#include "ForgeBlueprintPatches.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/SceneComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectIterator.h"

namespace
{
FString FixtureSignature(const UBlueprint* Blueprint)
{
    FString Value;
    TArray<UEdGraph*> Graphs; Blueprint->GetAllGraphs(Graphs);
    Graphs.Sort([](const UEdGraph& A, const UEdGraph& B) { return A.GetPathName() < B.GetPathName(); });
    for (const UEdGraph* Graph : Graphs)
    {
        Value += Graph->GetPathName() + TEXT("|");
        for (const UEdGraphNode* Node : Graph->Nodes)
        {
            Value += Node->NodeGuid.ToString() + Node->GetClass()->GetPathName() + Node->NodeComment +
                FString::Printf(TEXT(":%d:%d:"), Node->NodePosX, Node->NodePosY);
            for (const UEdGraphPin* Pin : Node->Pins)
            {
                FString Type;
                FEdGraphPinType::StaticStruct()->ExportText(Type, &Pin->PinType, nullptr, nullptr, PPF_None, nullptr);
                Value += Pin->PinId.ToString() + Pin->PinName.ToString() + Type + Pin->DefaultValue +
                    GetPathNameSafe(Pin->DefaultObject) + Pin->DefaultTextValue.ToString();
                TArray<FString> Links;
                for (const UEdGraphPin* Link : Pin->LinkedTo)
                    Links.Add(Link->GetOwningNode()->NodeGuid.ToString() + Link->PinId.ToString());
                Links.Sort(); for (const auto& Link : Links) Value += Link + TEXT(";");
            }
        }
    }
    for (const auto& Variable : Blueprint->NewVariables)
        Value += Variable.VarName.ToString() + Variable.VarGuid.ToString() + Variable.DefaultValue;
    if (Blueprint->SimpleConstructionScript) for (const auto* Node : Blueprint->SimpleConstructionScript->GetAllNodes())
        if (const auto* Scene = Cast<USceneComponent>(Node->ComponentTemplate))
            Value += Node->VariableGuid.ToString() + Node->GetVariableName().ToString() + FString::FromInt(Scene->Mobility);
    return Value;
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeScopedBlueprintPatchTest,
    "ForgeMCP.BlueprintPatches.ScopedPrimitiveJournal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForgeScopedBlueprintPatchTest::RunTest(const FString& Parameters)
{
    for (TObjectIterator<UPackage> It; It; ++It)
        if (It->IsDirty() && !It->HasAnyFlags(RF_Transient) && It->GetName().StartsWith(TEXT("/Game/")))
        { AddError(TEXT("Dirty project package blocks disposable fixture creation: ") + It->GetName()); return false; }
    const FString Name = TEXT("BP_Scoped_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
    const FString Path = TEXT("/Game/ForgeMCPTests/BlueprintPatches/") + Name;
    const FString Filename = FPackageName::LongPackageNameToFilename(Path, FPackageName::GetAssetPackageExtension());
    if (!TestTrue(TEXT("Fixture destination is a normal directory inside this project's Content"),
        FPaths::IsUnderDirectory(FPaths::ConvertRelativePathToFull(Filename), FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir())) &&
        ForgeBlueprintPatches::SafePath(Filename))) return false;
    if (!TestFalse(TEXT("Unique fixture never overwrites a package"), IFileManager::Get().FileExists(*Filename))) return false;
    UPackage* Package = CreatePackage(*Path);
    TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), Package,
        FName(*Name), BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass(), TEXT("ForgeScopedPatchValidation")));
    if (!TestNotNull(TEXT("Disposable fixture Blueprint created"), Blueprint.Get())) return false;
    FEdGraphPinType Integer; Integer.PinCategory = UEdGraphSchema_K2::PC_Int;
    if (!TestTrue(TEXT("Fixture variable created"), FBlueprintEditorUtils::AddMemberVariable(Blueprint.Get(), TEXT("Counter"), Integer, TEXT("42")))) return false;
    FEdGraphPinType Vectors; Vectors.PinCategory = UEdGraphSchema_K2::PC_Struct;
    Vectors.PinSubCategoryObject = TBaseStructure<FVector>::Get(); Vectors.ContainerType = EPinContainerType::Array;
    if (!TestTrue(TEXT("Fixed vector-array fixture variable created"), FBlueprintEditorUtils::AddMemberVariable(Blueprint.Get(), TEXT("Vectors"), Vectors))) return false;
    auto* Component = Blueprint->SimpleConstructionScript->CreateNode(USceneComponent::StaticClass(), TEXT("JournalComponent"));
    Blueprint->SimpleConstructionScript->AddNode(Component);
    CastChecked<USceneComponent>(Component->ComponentTemplate)->SetMobility(EComponentMobility::Movable);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint.Get());
    FCompilerResultsLog MemberCompile;
    FKismetEditorUtilities::CompileBlueprint(Blueprint.Get(), EBlueprintCompileOptions::SkipSave, &MemberCompile);
    if (!TestEqual(TEXT("Fixture member declarations compile before node construction"), MemberCompile.NumErrors, 0)) return false;
    UEdGraph* Graph = NewObject<UEdGraph>(Blueprint.Get(), TEXT("JournalEventGraph"));
    Graph->Schema = UEdGraphSchema_K2::StaticClass(); Blueprint->UbergraphPages.Add(Graph);
    auto AddNode = [](UEdGraph* Target, UEdGraphNode* Node)
    { Target->AddNode(Node, false, false); Node->CreateNewGuid(); Node->PostPlacedNewNode(); Node->AllocateDefaultPins(); };
    TArray<UK2Node_IfThenElse*> Branches;
    for (int32 Index = 0; Index < 1000; ++Index)
    {
        auto* Node = NewObject<UK2Node_IfThenElse>(Graph); AddNode(Graph, Node);
        Node->NodePosX = Index * 16; Node->NodeComment = FString::Printf(TEXT("untouched_%d"), Index); Branches.Add(Node);
    }
    auto* Event = NewObject<UK2Node_CustomEvent>(Graph); Event->CustomFunctionName = TEXT("InputFixture"); AddNode(Graph, Event);
    auto* Variable = NewObject<UK2Node_VariableGet>(Graph); Variable->VariableReference.SetSelfMember(TEXT("Counter")); AddNode(Graph, Variable);
    UFunction* Function = UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("Greater_IntInt"));
    if (!TestNotNull(TEXT("Representative reflected function resolved"), Function)) return false;
    auto* Compare = NewObject<UK2Node_CallFunction>(Graph); Compare->SetFromFunction(Function); AddNode(Graph, Compare);
    auto* VectorVariable = NewObject<UK2Node_VariableGet>(Graph); VectorVariable->VariableReference.SetSelfMember(TEXT("Vectors")); AddNode(Graph, VectorVariable);
    UFunction* AverageFunction = UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("GetVectorArrayAverage"));
    UFunction* LocationFunction = AActor::StaticClass()->FindFunctionByName(TEXT("K2_SetActorLocation"));
    if (!TestNotNull(TEXT("Fixed-array function resolved"), AverageFunction) || !TestNotNull(TEXT("Actor function resolved"), LocationFunction)) return false;
    auto* Average = NewObject<UK2Node_CallFunction>(Graph); Average->SetFromFunction(AverageFunction); AddNode(Graph, Average);
    auto* SetLocation = NewObject<UK2Node_CallFunction>(Graph); SetLocation->SetFromFunction(LocationFunction); AddNode(Graph, SetLocation);
    UEdGraph* Untouched = NewObject<UEdGraph>(Blueprint.Get(), TEXT("UntouchedEventGraph"));
    Untouched->Schema = UEdGraphSchema_K2::StaticClass(); Blueprint->UbergraphPages.Add(Untouched);
    AddNode(Untouched, NewObject<UK2Node_IfThenElse>(Untouched));
    const UEdGraphSchema* Schema = Graph->GetSchema();
    UEdGraphPin* Source = Branches[0]->FindPin(UEdGraphSchema_K2::PN_Then);
    UEdGraphPin* OriginalTarget = Branches[1]->FindPin(UEdGraphSchema_K2::PN_Execute);
    UEdGraphPin* NewTarget = Branches[2]->FindPin(UEdGraphSchema_K2::PN_Execute);
    if (!TestTrue(TEXT("Fixture input links through native schema"), Schema->TryCreateConnection(Event->FindPin(UEdGraphSchema_K2::PN_Then), Branches[0]->FindPin(UEdGraphSchema_K2::PN_Execute)))) return false;
    if (!TestTrue(TEXT("Original execution link exists"), Schema->TryCreateConnection(Source, OriginalTarget))) return false;
    if (!TestTrue(TEXT("Fixture control chain reaches actor function"), Schema->TryCreateConnection(Branches[1]->FindPin(UEdGraphSchema_K2::PN_Then), SetLocation->FindPin(UEdGraphSchema_K2::PN_Execute)))) return false;
    if (!TestTrue(TEXT("Required array input is initially wired"), Schema->TryCreateConnection(VectorVariable->FindPin(TEXT("Vectors")), Average->FindPin(TEXT("Vectors"))))) return false;
    if (!TestTrue(TEXT("Average result is consumed in executable chain"), Schema->TryCreateConnection(Average->FindPin(UEdGraphSchema_K2::PN_ReturnValue), SetLocation->FindPin(TEXT("NewLocation"))))) return false;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(Blueprint.Get());
    FCompilerResultsLog BaselineCompile;
    FKismetEditorUtilities::CompileBlueprint(Blueprint.Get(), EBlueprintCompileOptions::SkipSave, &BaselineCompile);
    if (!TestEqual(TEXT("Fixture baseline compiles"), BaselineCompile.NumErrors, 0)) return false;
    // Re-resolve pins after compilation before recording stable identities.
    Source = Branches[0]->FindPin(UEdGraphSchema_K2::PN_Then); OriginalTarget = Branches[1]->FindPin(UEdGraphSchema_K2::PN_Execute);
    NewTarget = Branches[2]->FindPin(UEdGraphSchema_K2::PN_Execute);
    UEdGraphPin* Condition = Branches[0]->FindPin(TEXT("Condition"));
    UEdGraphPin* VariablePin = Variable->FindPin(TEXT("Counter")); UEdGraphPin* CompareInput = Compare->FindPin(TEXT("A"));
    if (!TestNotNull(TEXT("Variable output resolved"), VariablePin) || !TestNotNull(TEXT("Function input resolved"), CompareInput)) return false;
    if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true)) return false;
    FSavePackageArgs Save; Save.TopLevelFlags = RF_Public | RF_Standalone;
    if (!TestTrue(TEXT("Explicit disposable baseline save succeeded"), UPackage::SavePackage(Package, Blueprint.Get(), *Filename, Save))) return false;
    FAssetRegistryModule::AssetCreated(Blueprint.Get());
    TArray<uint8> OriginalFile; if (!FFileHelper::LoadFileToArray(OriginalFile, *Filename)) return false;
    const FString OriginalSignature = FixtureSignature(Blueprint.Get());
    const int32 OriginalX = Branches[2]->NodePosX, OriginalY = Branches[2]->NodePosY;
    const FString OriginalDefault = Condition->DefaultValue;
    AddInfo(TEXT("Persistent disposable journal fixture: ") + Path);
    AddInfo(TEXT("The required-array disconnection exercises a real UE compiler error. Separate injected failures test controlled rollback/refusal branches."));

    auto Move = MakeShared<FJsonObject>(); Move->SetStringField(TEXT("op"), TEXT("move_node"));
    Move->SetStringField(TEXT("node_guid"), Branches[2]->NodeGuid.ToString()); Move->SetNumberField(TEXT("x"), 77); Move->SetNumberField(TEXT("y"), 88);
    auto Default = MakeShared<FJsonObject>(); Default->SetStringField(TEXT("op"), TEXT("set_pin_default"));
    Default->SetStringField(TEXT("node_guid"), Branches[0]->NodeGuid.ToString()); Default->SetStringField(TEXT("pin_id"), Condition->PinId.ToString());
    Default->SetStringField(TEXT("value"), OriginalDefault == TEXT("true") ? TEXT("false") : TEXT("true"));
    auto Link = [](const TCHAR* Kind, UEdGraphPin* From, UEdGraphPin* To)
    {
        auto Op = MakeShared<FJsonObject>(); Op->SetStringField(TEXT("op"), Kind);
        Op->SetStringField(TEXT("from_node_guid"), From->GetOwningNode()->NodeGuid.ToString()); Op->SetStringField(TEXT("from_pin_id"), From->PinId.ToString());
        Op->SetStringField(TEXT("to_node_guid"), To->GetOwningNode()->NodeGuid.ToString()); Op->SetStringField(TEXT("to_pin_id"), To->PinId.ToString()); return Op;
    };
    FForgeBlueprintPatches Patches;
    auto Preview = [&](const TArray<TSharedPtr<FJsonValue>>& Ops, TSharedRef<FJsonObject> Out, FString& Code, FString& Message)
    {
        auto Request = MakeShared<FJsonObject>(); Request->SetStringField(TEXT("asset_path"), Path);
        Request->SetStringField(TEXT("graph_name"), Graph->GetName()); Request->SetArrayField(TEXT("operations"), Ops);
        auto Args = MakeShared<FJsonObject>(); Args->SetObjectField(TEXT("request"), Request);
        return Patches.Handle(TEXT("blueprint_patch_preview"), Args, Out, Code, Message);
    };
    auto Apply = [&](const TSharedRef<FJsonObject>& Plan, TSharedRef<FJsonObject> Out, FString& Code, FString& Message)
    {
        auto Args = MakeShared<FJsonObject>(); const FString Id = Plan->GetStringField(TEXT("preview_id"));
        Args->SetStringField(TEXT("preview_id"), Id); Args->SetStringField(TEXT("confirmation"), Id);
        return Patches.Handle(TEXT("blueprint_patch_apply"), Args, Out, Code, Message);
    };
    auto RestoreFixture = [&]()
    {
        Source = Branches[0]->FindPin(UEdGraphSchema_K2::PN_Then); OriginalTarget = Branches[1]->FindPin(UEdGraphSchema_K2::PN_Execute);
        NewTarget = Branches[2]->FindPin(UEdGraphSchema_K2::PN_Execute);
        if (Source->LinkedTo.Contains(NewTarget)) Schema->BreakSinglePinLink(Source, NewTarget);
        if (!Source->LinkedTo.Contains(OriginalTarget) && !Schema->TryCreateConnection(Source, OriginalTarget)) return false;
        VariablePin = Variable->FindPin(TEXT("Counter")); CompareInput = Compare->FindPin(TEXT("A"));
        if (VariablePin->LinkedTo.Contains(CompareInput)) Schema->BreakSinglePinLink(VariablePin, CompareInput);
        Branches[2]->NodePosX = OriginalX; Branches[2]->NodePosY = OriginalY; Branches[999]->NodePosY = 0;
        Condition = Branches[0]->FindPin(TEXT("Condition")); Schema->TrySetDefaultValue(*Condition, OriginalDefault, true);
        FCompilerResultsLog Log; FKismetEditorUtilities::CompileBlueprint(Blueprint.Get(), EBlueprintCompileOptions::SkipSave, &Log);
        TArray<uint8> Disk; const bool bSame = Log.NumErrors == 0 && FixtureSignature(Blueprint.Get()) == OriginalSignature &&
            FFileHelper::LoadFileToArray(Disk, *Filename) && Disk == OriginalFile;
        if (bSame) Package->SetDirtyFlag(false); // Only this verified disposable fixture is reset.
        return bSame;
    };
    FString Code, Message;
    auto Plan = MakeShared<FJsonObject>();
    TestFalse(TEXT("Implicit execution replacement is rejected"), Preview({MakeShared<FJsonValueObject>(Link(TEXT("connect_pins"), Source, NewTarget))}, Plan, Code, Message));
    TestEqual(TEXT("Replacement rejection is explicit"), Code, FString(TEXT("explicit_disconnect_required")));
    if (!TestTrue(TEXT("Large-fixture scoped preview succeeds: ") + Message, Preview({
        MakeShared<FJsonValueObject>(Move), MakeShared<FJsonValueObject>(Default),
        MakeShared<FJsonValueObject>(Link(TEXT("disconnect_pins"), Source, OriginalTarget)),
        MakeShared<FJsonValueObject>(Link(TEXT("connect_pins"), Source, NewTarget)),
        MakeShared<FJsonValueObject>(Link(TEXT("connect_pins"), VariablePin, CompareInput))}, Plan, Code, Message))) return false;
    auto Result = MakeShared<FJsonObject>();
    if (!TestTrue(TEXT("Scoped apply completes"), Apply(Plan, Result, Code, Message))) return false;
    if (!TestEqual(TEXT("Apply remains in memory"), Result->GetStringField(TEXT("state")), FString(TEXT("applied_in_memory")))) return false;
    TestTrue(TEXT("Binary package backup is verified"), Result->GetBoolField(TEXT("backup_verified")));
    TestTrue(TEXT("Unrelated graph/default semantics are preserved"), Result->GetBoolField(TEXT("untouched_semantics_preserved")));
    TestFalse(TEXT("Apply did not save"), Result->GetBoolField(TEXT("saved")));
    Source = Branches[0]->FindPin(UEdGraphSchema_K2::PN_Then); OriginalTarget = Branches[1]->FindPin(UEdGraphSchema_K2::PN_Execute);
    NewTarget = Branches[2]->FindPin(UEdGraphSchema_K2::PN_Execute);
    VariablePin = Variable->FindPin(TEXT("Counter")); CompareInput = Compare->FindPin(TEXT("A"));
    TestTrue(TEXT("Execution path reconnected exactly"), Source->LinkedTo.Contains(NewTarget) && !Source->LinkedTo.Contains(OriginalTarget));
    TestTrue(TEXT("Typed data link exists"), VariablePin->LinkedTo.Contains(CompareInput));
    if (!TestTrue(TEXT("Fixture restores with complete semantic and disk comparison"), RestoreFixture())) return false;

    Plan = MakeShared<FJsonObject>();
    if (!Preview({MakeShared<FJsonValueObject>(Move)}, Plan, Code, Message)) return false;
    Branches[2]->NodePosX += 1;
    TestFalse(TEXT("Stale targeted position rejects apply"), Apply(Plan, Result, Code, Message));
    TestEqual(TEXT("Stale preview is explicit"), Code, FString(TEXT("stale_preview")));
    if (!TestTrue(TEXT("Stale test restores only its fixture"), RestoreFixture())) return false;

    // K2's required array-input validation is an actual compiler failure. The
    // function output is consumed on an execution path, so this is not dead code.
    UEdGraphPin* VectorOutput = VectorVariable->FindPin(TEXT("Vectors"));
    UEdGraphPin* RequiredArray = Average->FindPin(TEXT("Vectors"));
    Plan = MakeShared<FJsonObject>();
    if (!Preview({MakeShared<FJsonValueObject>(Link(TEXT("disconnect_pins"), VectorOutput, RequiredArray))}, Plan, Code, Message)) return false;
    AddExpectedErrorPlain(TEXT("Array inputs"), EAutomationExpectedErrorFlags::Contains, -1);
    if (!Apply(Plan, Result, Code, Message)) return false;
    TestTrue(TEXT("Actual UE compile failure is reported"), Result->GetNumberField(TEXT("compiler_errors")) > 0);
    if (!TestEqual(TEXT("Actual compile failure restores only verified scope"), Result->GetStringField(TEXT("state")), FString(TEXT("rolled_back")))) return false;
    TestTrue(TEXT("Real compile failure rollback verifies complete fixture semantics"), FixtureSignature(Blueprint.Get()) == OriginalSignature);

    Patches.SetCompilerForTesting([](UBlueprint*, FCompilerResultsLog& Log) { Log.NumErrors = 1; return false; });
    Plan = MakeShared<FJsonObject>();
    if (!Preview({MakeShared<FJsonValueObject>(Default)}, Plan, Code, Message) || !Apply(Plan, Result, Code, Message)) return false;
    if (!TestEqual(TEXT("Injected compile failure is rolled back"), Result->GetStringField(TEXT("state")), FString(TEXT("rolled_back")))) return false;
    TestTrue(TEXT("Scoped rollback is independently verified"), Result->GetBoolField(TEXT("rollback_verified")));
    TestTrue(TEXT("Every fixture graph identity/default/link matches baseline"), FixtureSignature(Blueprint.Get()) == OriginalSignature);

    Patches.SetCompilerForTesting([&](UBlueprint*, FCompilerResultsLog& Log) { Branches[999]->NodePosY = 1; Log.NumErrors = 1; return false; });
    Plan = MakeShared<FJsonObject>();
    if (!Preview({MakeShared<FJsonValueObject>(Default)}, Plan, Code, Message) || !Apply(Plan, Result, Code, Message)) return false;
    TestEqual(TEXT("Unexpected outside-scope change stops for owner"), Result->GetStringField(TEXT("state")), FString(TEXT("partial_scope_requires_owner")));
    TestFalse(TEXT("Unsafe restoration is not attempted"), Result->GetBoolField(TEXT("rollback_attempted")));
    Patches.SetCompilerForTesting({});
    TestTrue(TEXT("Only the disposable test harness restores the injected condition"), RestoreFixture());
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
