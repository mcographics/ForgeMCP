#if WITH_DEV_AUTOMATION_TESTS

#include "ForgeBlueprintInspection.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "GameFramework/Actor.h"
#include "K2Node_CustomEvent.h"
#include "K2Node_IfThenElse.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "UObject/Package.h"
#include "UObject/StrongObjectPtr.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeBlueprintLargeInspectionTest,
    "ForgeMCP.BlueprintInspection.LargeGraphPaginationAndTrace",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForgeBlueprintLargeInspectionTest::RunTest(const FString& Parameters)
{
    const FString AssetName = TEXT("BP_InspectionFixture_") + FGuid::NewGuid().ToString(EGuidFormats::Digits);
    const FString AssetPath = TEXT("/Game/ForgeMCPTests/BlueprintInspection/") + AssetName;
    UPackage* Package = CreatePackage(*AssetPath);
    Package->SetFlags(RF_Transient);
    ON_SCOPE_EXIT { Package->SetDirtyFlag(false); };
    TStrongObjectPtr<UBlueprint> Blueprint(FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(),
        Package, FName(*AssetName), BPTYPE_Normal, UBlueprint::StaticClass(),
        UBlueprintGeneratedClass::StaticClass(), TEXT("ForgeInspectionValidation")));
    if (!TestNotNull(TEXT("Disposable in-memory Blueprint created"), Blueprint.Get())) return false;
    Blueprint->SetFlags(RF_Transient);
    UEdGraph* Graph = NewObject<UEdGraph>(Blueprint.Get(), TEXT("InspectionEventGraph"));
    Graph->Schema = UEdGraphSchema_K2::StaticClass();
    Blueprint->UbergraphPages.Add(Graph);
    auto AddNode = [Graph](UEdGraphNode* Node)
    {
        Graph->AddNode(Node, false, false);
        Node->CreateNewGuid();
        Node->PostPlacedNewNode();
        Node->AllocateDefaultPins();
    };
    TArray<UK2Node_IfThenElse*> Branches;
    for (int32 Index = 0; Index < 1000; ++Index)
    {
        auto* Branch = NewObject<UK2Node_IfThenElse>(Graph);
        AddNode(Branch);
        Branch->NodePosX = Index * 16;
        Branch->NodeComment = FString::Printf(TEXT("unrelated_fixture_%d"), Index);
        Branches.Add(Branch);
    }
    auto* Input = NewObject<UK2Node_CustomEvent>(Graph);
    Input->CustomFunctionName = TEXT("InputFixture");
    AddNode(Input);
    Branches[0]->NodeComment = TEXT("acceleration_fixture");
    Branches[1]->NodeComment = TEXT("deceleration_fixture");
    const UEdGraphSchema* Schema = Graph->GetSchema();
    if (!TestTrue(TEXT("Fixture input connects through native schema"), Schema->TryCreateConnection(
        Input->FindPin(UEdGraphSchema_K2::PN_Then), Branches[0]->FindPin(UEdGraphSchema_K2::PN_Execute)))) return false;
    if (!TestTrue(TEXT("Fixture branch chain connects through native schema"), Schema->TryCreateConnection(
        Branches[0]->FindPin(UEdGraphSchema_K2::PN_Then), Branches[1]->FindPin(UEdGraphSchema_K2::PN_Execute)))) return false;

    FForgeBlueprintInspection Inspector;
    auto Args = MakeShared<FJsonObject>();
    Args->SetStringField(TEXT("asset_path"), AssetPath);
    Args->SetStringField(TEXT("graph_name"), Graph->GetName());
    Args->SetNumberField(TEXT("page_size"), 64);
    FString Code, Message;
    TSet<FString> Seen;
    int32 PageCount = 0;
    bool bMore = true;
    while (bMore && PageCount < 32)
    {
        auto Data = MakeShared<FJsonObject>();
        if (!TestTrue(TEXT("Graph page succeeds: ") + Code + TEXT(" ") + Message,
            Inspector.Handle(TEXT("blueprint_graph_page"), Args, Data, Code, Message))) return false;
        TestEqual(TEXT("Every page has exact total"), static_cast<int32>(Data->GetNumberField(TEXT("total_nodes"))), 1001);
        const auto& Rows = Data->GetArrayField(TEXT("nodes"));
        for (const auto& Row : Rows)
        {
            const FString Guid = Row->AsObject()->GetStringField(TEXT("node_guid"));
            TestFalse(TEXT("No duplicate NodeGuid across pages"), Seen.Contains(Guid));
            Seen.Add(Guid);
        }
        bMore = Data->GetBoolField(TEXT("has_more"));
        TestEqual(TEXT("Truncation explicitly matches pagination"), Data->GetBoolField(TEXT("truncated")), bMore);
        Args->SetStringField(TEXT("cursor"), Data->GetStringField(TEXT("next_cursor")));
        ++PageCount;
    }
    TestFalse(TEXT("Every page was consumed"), bMore);
    TestEqual(TEXT("Every fixture node was enumerated once"), Seen.Num(), 1001);

    for (const FString& Direction : {FString(TEXT("forward")), FString(TEXT("backward")), FString(TEXT("both"))})
    {
        auto TraceArgs = MakeShared<FJsonObject>();
        TraceArgs->SetStringField(TEXT("asset_path"), AssetPath);
        TraceArgs->SetStringField(TEXT("graph_name"), Graph->GetName());
        TraceArgs->SetStringField(TEXT("direction"), Direction);
        UEdGraphNode* Start = Direction == TEXT("forward") ? static_cast<UEdGraphNode*>(Input) :
            Direction == TEXT("backward") ? Branches[1] : Branches[0];
        TraceArgs->SetStringField(TEXT("start_node_guid"), Start->NodeGuid.ToString());
        auto Data = MakeShared<FJsonObject>();
        if (!TestTrue(TEXT("Trace succeeds: ") + Direction,
            Inspector.Handle(TEXT("blueprint_graph_trace"), TraceArgs, Data, Code, Message))) return false;
        TestEqual(TEXT("Trace includes exactly three connected nodes"), static_cast<int32>(Data->GetNumberField(TEXT("visited_node_count"))), 3);
        TestEqual(TEXT("Trace returns each execution edge once"), Data->GetArrayField(TEXT("execution_edges")).Num(), 2);
    }

    Args->RemoveField(TEXT("cursor"));
    Args->SetStringField(TEXT("comment_contains"), TEXT("acceleration_fixture"));
    auto Filtered = MakeShared<FJsonObject>();
    if (!TestTrue(TEXT("Targeted comment discovery succeeds"), Inspector.Handle(TEXT("blueprint_graph_page"), Args, Filtered, Code, Message))) return false;
    TestEqual(TEXT("Targeted discovery returns one node"), static_cast<int32>(Filtered->GetNumberField(TEXT("total_nodes"))), 1);
    Args->RemoveField(TEXT("comment_contains"));
    auto First = MakeShared<FJsonObject>();
    if (!Inspector.Handle(TEXT("blueprint_graph_page"), Args, First, Code, Message)) return false;
    Args->SetStringField(TEXT("cursor"), First->GetStringField(TEXT("next_cursor")));
    Branches[2]->NodePosX += 1;
    auto Stale = MakeShared<FJsonObject>();
    TestFalse(TEXT("Changed graph rejects stale cursor"), Inspector.Handle(TEXT("blueprint_graph_page"), Args, Stale, Code, Message));
    TestEqual(TEXT("Stale rejection is explicit"), Code, FString(TEXT("stale_cursor")));

    auto NodeArgs = MakeShared<FJsonObject>();
    NodeArgs->SetStringField(TEXT("asset_path"), AssetPath);
    NodeArgs->SetStringField(TEXT("graph_name"), Graph->GetName());
    NodeArgs->SetStringField(TEXT("node_guid"), Branches[0]->NodeGuid.ToString());
    NodeArgs->SetNumberField(TEXT("pin_page_size"), 1);
    auto NodePage = MakeShared<FJsonObject>();
    if (!TestTrue(TEXT("Individual node inspection succeeds"), Inspector.Handle(TEXT("blueprint_node_inspect"), NodeArgs, NodePage, Code, Message))) return false;
    TestTrue(TEXT("Pin pagination reports more pins"), NodePage->GetBoolField(TEXT("has_more_pins")));
    NodeArgs->SetStringField(TEXT("pin_cursor"), NodePage->GetStringField(TEXT("next_cursor")));
    UEdGraphPin* Condition = Branches[0]->FindPin(TEXT("Condition"));
    if (!TestNotNull(TEXT("Fixture has condition pin"), Condition)) return false;
    Condition->DefaultValue = Condition->DefaultValue == TEXT("true") ? TEXT("false") : TEXT("true");
    TestFalse(TEXT("Changed pin default rejects stale pin cursor"), Inspector.Handle(TEXT("blueprint_node_inspect"), NodeArgs, Stale, Code, Message));
    TestEqual(TEXT("Stale pin rejection is explicit"), Code, FString(TEXT("stale_cursor")));

    NodeArgs->RemoveField(TEXT("pin_cursor"));
    const FGuid OriginalGuid = Branches[3]->NodeGuid;
    Branches[3]->NodeGuid = Branches[0]->NodeGuid;
    TestFalse(TEXT("Individual node inspection rejects duplicate GUIDs"), Inspector.Handle(TEXT("blueprint_node_inspect"), NodeArgs, Stale, Code, Message));
    TestEqual(TEXT("Duplicate GUID rejection is explicit"), Code, FString(TEXT("unstable_node_identity")));
    Branches[3]->NodeGuid = OriginalGuid;

    auto* NestedGraph = NewObject<UEdGraph>(Graph, FName(*Graph->GetName()));
    NestedGraph->Schema = UEdGraphSchema_K2::StaticClass();
    Graph->SubGraphs.Add(NestedGraph);
    Args->RemoveField(TEXT("cursor"));
    TestFalse(TEXT("Graph selection rejects duplicate graph names"), Inspector.Handle(TEXT("blueprint_graph_page"), Args, Stale, Code, Message));
    TestEqual(TEXT("Ambiguous graph rejection is explicit"), Code, FString(TEXT("ambiguous_graph")));
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
