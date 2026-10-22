#if WITH_DEV_AUTOMATION_TESTS
#include "ForgeBlueprintNodeRemoval.h"
#include "ForgeReadoutFunctions.h"
#include "ForgeMeshExport.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Engine/StaticMesh.h"
#include "UObject/Package.h"
#include "Misc/AutomationTest.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet/KismetTextLibrary.h"
#include "Kismet/KismetSystemLibrary.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeNodeRemovalTest, "ForgeMCP.Readout.RemovalRecovery",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeNodeRemovalTest::RunTest(const FString& Parameters)
{
    UBlueprint* Blueprint = FKismetEditorUtilities::CreateBlueprint(UObject::StaticClass(),
        GetTransientPackage(), MakeUniqueObjectName(GetTransientPackage(), UBlueprint::StaticClass(), TEXT("ForgeRemovalTest")),
        BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass(), TEXT("ForgeNativeValidation"));
    if (!TestNotNull(TEXT("Native test Blueprint created"), Blueprint)) return false;
    UEdGraph* Graph = NewObject<UEdGraph>(Blueprint);
    Graph->Schema = UEdGraphSchema_K2::StaticClass();
    Blueprint->UbergraphPages.Add(Graph);
    UK2Node_CallFunction* Node = NewObject<UK2Node_CallFunction>(Graph);
    Node->SetFromFunction(UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("Round64")));
    Graph->AddNode(Node, false, false); Node->CreateNewGuid(); Node->AllocateDefaultPins();
    const FGuid Guid = Node->NodeGuid;
    TestTrue(TEXT("Math node can be removed"), ForgeBlueprintNodeRemoval::Allowed(Node));
    TestFalse(TEXT("Entry cannot be removed"), ForgeBlueprintNodeRemoval::Allowed(NewObject<UK2Node_FunctionEntry>(Graph)));
    ForgeBlueprintNodeRemoval::FRemovedNode Held(Node);
    Graph->RemoveNode(Node);
    TestFalse(TEXT("Removed from graph"), Graph->Nodes.Contains(Node));
    Held.Restore(); Held.Restore();
    TestEqual(TEXT("Recovery inserts once"), Graph->Nodes.Num(), 1);
    TestTrue(TEXT("GUID and pins survive"), Node->NodeGuid == Guid && Node->FindPin(TEXT("A")) != nullptr);
    TestTrue(TEXT("Native formatter allowlisted"), ForgeReadoutFunctions::Allowed(
        UKismetTextLibrary::StaticClass()->FindFunctionByName(TEXT("Conv_DoubleToText"))));
    TestFalse(TEXT("Console execution rejected"), ForgeReadoutFunctions::Allowed(
        UKismetSystemLibrary::StaticClass()->FindFunctionByName(TEXT("ExecuteConsoleCommand"))));
    TestEqual(TEXT("Two fraction digits"), UKismetTextLibrary::Conv_DoubleToText(
        1680092.834, ERoundingMode::HalfToEven, false, false, 1, 324, 0, 2).ToString(), FString(TEXT("1680092.83")));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeEngineMeshExportTest, "ForgeMCP.Transfer.EngineSource",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeEngineMeshExportTest::RunTest(const FString& Parameters)
{
    const FString AssetPath = TEXT("/Engine/BasicShapes/Sphere.Sphere");
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *AssetPath);
    if (!TestNotNull(TEXT("Engine sphere loaded in disposable test"), Mesh)) return false;
    const bool bDirtyBefore = Mesh->GetPackage()->IsDirty();
    const FString PackageFile = FPackageName::LongPackageNameToFilename(
        TEXT("/Engine/BasicShapes/Sphere"), FPackageName::GetAssetPackageExtension());
    TArray<uint8> Before, After;
    if (!TestTrue(TEXT("Read original engine package"), FFileHelper::LoadFileToArray(Before, *PackageFile))) return false;
    FForgeMeshExport Exporter;
    for (const FString Format : {FString(TEXT("fbx")), FString(TEXT("obj"))})
    {
        auto Args = MakeShared<FJsonObject>();
        Args->SetStringField(TEXT("asset_path"), AssetPath);
        Args->SetStringField(TEXT("format"), Format);
        auto Data = MakeShared<FJsonObject>();
        FString Code, Message;
        if (!TestTrue(TEXT("Engine export preview: ") + Format,
            Exporter.Handle(TEXT("mesh_export_preview"), Args, Data, Code, Message)))
        { AddError(Code + TEXT(": ") + Message); return false; }
        const FString Snapshot = Data->GetStringField(TEXT("source_snapshot_sha256"));
        const FString Id = Data->GetStringField(TEXT("preview_id"));
        auto Approval = MakeShared<FJsonObject>();
        Approval->SetStringField(TEXT("preview_id"), Id);
        Approval->SetStringField(TEXT("confirmation"), Id);
        Data = MakeShared<FJsonObject>();
        if (!TestTrue(TEXT("Engine export apply: ") + Format,
            Exporter.Handle(TEXT("mesh_export_apply"), Approval, Data, Code, Message)))
        { AddError(Code + TEXT(": ") + Message); return false; }
        TestEqual(TEXT("Source snapshot unchanged"), Data->GetStringField(TEXT("source_snapshot_sha256")), Snapshot);
        TestFalse(TEXT("Export does not modify source"), Data->GetBoolField(TEXT("source_modified")));
        TestTrue(TEXT("Export file exists"), FPaths::FileExists(FPaths::ProjectSavedDir() /
            TEXT("ForgeExports") / Id / (TEXT("mesh.") + Format)));
    }
    TestEqual(TEXT("Engine package dirty flag preserved"), Mesh->GetPackage()->IsDirty(), bDirtyBefore);
    TestTrue(TEXT("Read engine package after export"), FFileHelper::LoadFileToArray(After, *PackageFile));
    TestTrue(TEXT("Engine package bytes preserved"), Before == After);
    return true;
}
#endif
