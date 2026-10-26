#include "ForgeBlueprintInspection.h"

#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_MacroInstance.h"
#include "Misc/PackageName.h"
#include "Misc/SecureHash.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"

namespace ForgeBlueprintInspection
{
using JObject = TSharedRef<FJsonObject>;
constexpr int32 MaxCursors = 24;
constexpr int32 MaxGraphPageSize = 64;
constexpr int32 MaxPinPageSize = 128;
constexpr int32 MaxProperties = 256;
constexpr int32 MaxResponseBytes = 768 * 1024;
constexpr double CursorLifetimeSeconds = 300.0;

FString Text(const JObject& Object, const TCHAR* Name, const TCHAR* Fallback = TEXT(""))
{
    FString Value;
    return Object->TryGetStringField(Name, Value) ? Value : FString(Fallback);
}

FString Serialize(const TSharedRef<FJsonObject>& Object)
{
    FString Result;
    FJsonSerializer::Serialize(Object, TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Result));
    return Result;
}

int64 Utf8Bytes(const FString& Value)
{
    FTCHARToUTF8 Encoded(*Value);
    return Encoded.Length();
}

FString PinTypeText(const UEdGraphPin* Pin)
{
    FString Type;
    if (Pin) FEdGraphPinType::StaticStruct()->ExportText(Type, &Pin->PinType, nullptr, nullptr, PPF_None, nullptr);
    return Type;
}

FString PinIdentity(const UEdGraphPin* Pin)
{
    return Pin && Pin->PinId.IsValid() ? Pin->PinId.ToString(EGuidFormats::Digits) : FString();
}

bool HasReciprocalLink(const UEdGraphPin* Pin, const UEdGraphPin* Other)
{
    return Pin && Other && Other->LinkedTo.Contains(const_cast<UEdGraphPin*>(Pin));
}

FString GraphType(const UBlueprint* Blueprint, const UEdGraph* Graph)
{
    if (!Blueprint || !Graph) return TEXT("unknown");
    if (Blueprint->UbergraphPages.Contains(Graph)) return TEXT("event");
    if (Blueprint->FunctionGraphs.Contains(Graph)) return TEXT("function");
    if (Blueprint->MacroGraphs.Contains(Graph)) return TEXT("macro");
    if (Blueprint->DelegateSignatureGraphs.Contains(Graph)) return TEXT("delegate_signature");
    return TEXT("nested_or_special");
}

FString GraphFingerprint(const UEdGraph* Graph)
{
    FMD5 Hash;
    const uint8 Separator = 0;
    auto Add = [&Hash, &Separator](const FString& Value)
    {
        FTCHARToUTF8 Encoded(*Value);
        Hash.Update(reinterpret_cast<const uint8*>(Encoded.Get()), Encoded.Length());
        Hash.Update(&Separator, 1);
    };

    if (!Graph) return TEXT("invalid");
    Add(Graph->GetPathName());
    Add(Graph->GetClass()->GetPathName());
    Add(Graph->GetSchema() ? Graph->GetSchema()->GetClass()->GetPathName() : FString());
    for (TFieldIterator<FProperty> It(Graph->GetClass()); It; ++It)
    {
        FProperty* Property = *It;
        if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient | CPF_NonPIEDuplicateTransient) ||
            Property->GetName() == TEXT("Nodes")) continue;
        FString Value;
        Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Graph), nullptr,
            const_cast<UEdGraph*>(Graph), PPF_None);
        Add(Property->GetName());
        Add(Value);
    }

    TArray<UEdGraphNode*> Nodes;
    for (UEdGraphNode* Node : Graph->Nodes) if (Node) Nodes.Add(Node);
    Nodes.Sort([](const UEdGraphNode& A, const UEdGraphNode& B)
    {
        const FString Left = A.NodeGuid.IsValid() ? A.NodeGuid.ToString(EGuidFormats::Digits) : A.GetPathName();
        const FString Right = B.NodeGuid.IsValid() ? B.NodeGuid.ToString(EGuidFormats::Digits) : B.GetPathName();
        return Left < Right;
    });
    Add(FString::FromInt(Graph->Nodes.Num()));
    Add(FString::FromInt(Nodes.Num()));
    for (const UEdGraphNode* Node : Nodes)
    {
        if (!Node) { Add(TEXT("null-node")); continue; }
        Add(Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
        Add(Node->GetClass()->GetPathName());
        Add(Node->GetPathName());
        Add(FString::FromInt(Node->NodePosX));
        Add(FString::FromInt(Node->NodePosY));
        Add(Node->NodeComment);
        for (TFieldIterator<FProperty> It(Node->GetClass()); It; ++It)
        {
            FProperty* Property = *It;
            if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient | CPF_NonPIEDuplicateTransient) ||
                Property->GetName() == TEXT("Pins")) continue;
            FString Value;
            Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Node), nullptr,
                const_cast<UEdGraphNode*>(Node), PPF_None);
            Add(Property->GetName());
            Add(Value);
        }

        TArray<UEdGraphPin*> Pins;
        for (int32 PinIndex = 0; PinIndex < Node->Pins.Num(); ++PinIndex)
        {
            const UEdGraphPin* Pin = Node->Pins[PinIndex];
            Add(FString::FromInt(PinIndex));
            Add(Pin ? PinIdentity(Pin) + TEXT(":") + Pin->PinName.ToString() : TEXT("null-pin"));
            if (Pin) Pins.Add(Node->Pins[PinIndex]);
        }
        Pins.Sort([](const UEdGraphPin& A, const UEdGraphPin& B)
        {
            const FString Left = A.PinId.IsValid()
                ? A.PinId.ToString(EGuidFormats::Digits)
                : A.PinName.ToString() + TEXT(":") + FString::FromInt(static_cast<int32>(A.Direction));
            const FString Right = B.PinId.IsValid()
                ? B.PinId.ToString(EGuidFormats::Digits)
                : B.PinName.ToString() + TEXT(":") + FString::FromInt(static_cast<int32>(B.Direction));
            return Left < Right;
        });
        Add(FString::FromInt(Pins.Num()));
        for (const UEdGraphPin* Pin : Pins)
        {
            if (!Pin) { Add(TEXT("null-pin")); continue; }
            Add(PinIdentity(Pin));
            Add(Pin->PinName.ToString());
            Add(FString::FromInt(static_cast<int32>(Pin->Direction)));
            Add(PinTypeText(Pin));
            Add(Pin->DefaultValue);
            Add(Pin->DefaultObject ? Pin->DefaultObject->GetPathName() : FString());
            Add(Pin->DefaultTextValue.ToString());
            Add(Pin->bOrphanedPin ? TEXT("orphan") : TEXT("active"));

            TArray<FString> Links;
            for (const UEdGraphPin* Link : Pin->LinkedTo)
                if (Link && Link->GetOwningNode())
                    Links.Add(Link->GetOwningNode()->NodeGuid.ToString(EGuidFormats::Digits) + TEXT(":") +
                        PinIdentity(Link) + TEXT(":") + Link->PinName.ToString());
            Links.Sort();
            for (const FString& Link : Links) Add(Link);
        }
    }

    uint8 Digest[16];
    Hash.Final(Digest);
    FString Result;
    for (const uint8 Byte : Digest) Result += FString::Printf(TEXT("%02x"), Byte);
    return Result;
}

bool LoadBlueprint(const FString& AssetPath, UBlueprint*& Blueprint, FString& ErrorCode, FString& Error)
{
    if (AssetPath.Len() > 240 || !AssetPath.StartsWith(TEXT("/Game/")) || AssetPath.Contains(TEXT("..")) ||
        AssetPath.Contains(TEXT(".")) || !FPackageName::IsValidLongPackageName(AssetPath))
    {
        ErrorCode = TEXT("invalid_asset_path");
        Error = TEXT("Expected an exact /Game package path without an object suffix.");
        return false;
    }
    const FString ObjectPath = AssetPath + TEXT(".") + FPackageName::GetLongPackageAssetName(AssetPath);
    Blueprint = LoadObject<UBlueprint>(nullptr, *ObjectPath);
    if (!Blueprint)
    {
        ErrorCode = TEXT("asset_not_found");
        Error = TEXT("Blueprint asset was not found at the exact package path.");
        return false;
    }
    return true;
}

UEdGraph* FindGraph(UBlueprint* Blueprint, const FString& Name, bool& bAmbiguous)
{
    bAmbiguous = false;
    if (!Blueprint || Name.IsEmpty() || Name.Len() > 128) return nullptr;
    TArray<UEdGraph*> Graphs;
    Blueprint->GetAllGraphs(Graphs);
    UEdGraph* Found = nullptr;
    for (UEdGraph* Graph : Graphs)
        if (Graph && Graph->GetName() == Name)
        {
            if (Found) { bAmbiguous = true; return nullptr; }
            Found = Graph;
        }
    return Found;
}

UEdGraphNode* FindNode(UEdGraph* Graph, const FString& GuidText, bool& bAmbiguous)
{
    bAmbiguous = false;
    FGuid Guid;
    if (!Graph || !FGuid::Parse(GuidText, Guid) || !Guid.IsValid()) return nullptr;
    UEdGraphNode* Found = nullptr;
    for (UEdGraphNode* Node : Graph->Nodes)
        if (Node && Node->NodeGuid == Guid)
        {
            if (Found) { bAmbiguous = true; return nullptr; }
            Found = Node;
        }
    return Found;
}

FString NodeFunctionName(const UEdGraphNode* Node)
{
    if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
        if (const UFunction* Function = Call->GetTargetFunction()) return Function->GetName();
    return FString();
}

JObject NodeReference(const UEdGraphNode* Node)
{
    auto Result = MakeShared<FJsonObject>();
    Result->SetBoolField(TEXT("resolved"), false);
    if (const UK2Node_CallFunction* Call = Cast<UK2Node_CallFunction>(Node))
    {
        if (const UFunction* Function = Call->GetTargetFunction())
        {
            Result->SetBoolField(TEXT("resolved"), true);
            Result->SetStringField(TEXT("kind"), TEXT("function"));
            Result->SetStringField(TEXT("function_path"), Function->GetPathName());
            Result->SetStringField(TEXT("function_name"), Function->GetName());
            Result->SetStringField(TEXT("owner_class_path"), Function->GetOuterUClass()->GetPathName());
            Result->SetStringField(TEXT("signature"), Function->GetName() + TEXT(" ") + Function->GetOuterUClass()->GetPathName());
        }
    }
    else if (const UK2Node_MacroInstance* Macro = Cast<UK2Node_MacroInstance>(Node))
    {
        UEdGraph* MacroGraph = Macro->GetMacroGraph();
        Result->SetBoolField(TEXT("resolved"), MacroGraph != nullptr);
        Result->SetStringField(TEXT("kind"), TEXT("macro"));
        Result->SetStringField(TEXT("graph_path"), MacroGraph ? MacroGraph->GetPathName() : FString());
        Result->SetStringField(TEXT("graph_name"), MacroGraph ? MacroGraph->GetName() : FString());
    }
    return Result;
}

JObject NodeSummary(const UBlueprint* Blueprint, const UEdGraph* Graph, const UEdGraphNode* Node)
{
    auto Result = MakeShared<FJsonObject>();
    const FString Comment = Node->NodeComment;
    const FString Title = Node->GetNodeTitle(ENodeTitleType::ListView).ToString();
    const bool bK2Graph = Graph->GetSchema() && Graph->GetSchema()->IsA(UEdGraphSchema_K2::StaticClass());
    Result->SetStringField(TEXT("asset_path"), Blueprint->GetOutermost()->GetName());
    Result->SetStringField(TEXT("graph_name"), Graph->GetName());
    Result->SetStringField(TEXT("graph_type"), GraphType(Blueprint, Graph));
    Result->SetStringField(TEXT("node_guid"), Node->NodeGuid.IsValid() ? Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens) : FString());
    Result->SetBoolField(TEXT("identity_stable"), Node->NodeGuid.IsValid());
    Result->SetStringField(TEXT("object_path"), Node->GetPathName());
    Result->SetStringField(TEXT("class_path"), Node->GetClass()->GetPathName());
    Result->SetStringField(TEXT("title"), Title.Left(4096));
    Result->SetBoolField(TEXT("title_truncated"), Title.Len() > 4096);
    Result->SetStringField(TEXT("comment"), Comment.Left(4096));
    Result->SetBoolField(TEXT("comment_truncated"), Comment.Len() > 4096);
    Result->SetNumberField(TEXT("x"), Node->NodePosX);
    Result->SetNumberField(TEXT("y"), Node->NodePosY);
    Result->SetNumberField(TEXT("pin_count"), Node->Pins.Num());
    int32 OrphanedPins = 0;
    int32 UnresolvedPins = 0;
    int32 BrokenLinks = 0;
    for (const UEdGraphPin* Pin : Node->Pins)
    {
        if (!Pin) { ++BrokenLinks; continue; }
        if (Pin->bOrphanedPin) ++OrphanedPins;
        if (Pin->PinType.PinCategory.IsNone()) ++UnresolvedPins;
        for (const UEdGraphPin* Link : Pin->LinkedTo)
            if (!Link || !Link->GetOwningNode() || Link->GetOwningNode()->GetGraph() != Graph ||
                Link->Direction == Pin->Direction || !HasReciprocalLink(Pin, Link)) ++BrokenLinks;
    }
    Result->SetNumberField(TEXT("orphaned_pin_count"), OrphanedPins);
    Result->SetNumberField(TEXT("unresolved_pin_count"), UnresolvedPins);
    Result->SetNumberField(TEXT("broken_link_count"), BrokenLinks);
    Result->SetBoolField(TEXT("has_graph_integrity_issues"), OrphanedPins > 0 || UnresolvedPins > 0 || BrokenLinks > 0);
    Result->SetBoolField(TEXT("inspection_supported"), true);
    Result->SetStringField(TEXT("inspection_adapter"), bK2Graph ? TEXT("k2_reflection") : TEXT("edgraph_reflection"));
    Result->SetStringField(TEXT("mutation_capability"), TEXT("partial; see blueprint_capabilities"));
    Result->SetObjectField(TEXT("reference"), NodeReference(Node));
    return Result;
}

JObject PinInfo(const UEdGraphPin* Pin)
{
    auto Result = MakeShared<FJsonObject>();
    const FString Default = Pin->DefaultValue;
    Result->SetStringField(TEXT("pin_id"), PinIdentity(Pin));
    Result->SetBoolField(TEXT("pin_id_stable"), Pin->PinId.IsValid());
    Result->SetStringField(TEXT("name"), Pin->PinName.ToString());
    Result->SetStringField(TEXT("direction"), Pin->Direction == EGPD_Input ? TEXT("input") : TEXT("output"));
    Result->SetStringField(TEXT("type"), PinTypeText(Pin));
    Result->SetStringField(TEXT("default_value"), Default.Left(4096));
    Result->SetBoolField(TEXT("default_value_truncated"), Default.Len() > 4096);
    Result->SetStringField(TEXT("default_object_path"), Pin->DefaultObject ? Pin->DefaultObject->GetPathName() : FString());
    const FString DefaultText = Pin->DefaultTextValue.ToString();
    Result->SetStringField(TEXT("default_text"), DefaultText.Left(4096));
    Result->SetBoolField(TEXT("default_text_truncated"), DefaultText.Len() > 4096);
    Result->SetBoolField(TEXT("orphaned"), Pin->bOrphanedPin);
    Result->SetBoolField(TEXT("unresolved"), Pin->PinType.PinCategory.IsNone());

    TArray<TSharedPtr<FJsonValue>> Links;
    int32 Broken = 0;
    for (const UEdGraphPin* Link : Pin->LinkedTo)
    {
        auto Edge = MakeShared<FJsonObject>();
        const UEdGraphNode* OtherNode = Link ? Link->GetOwningNode() : nullptr;
        Edge->SetStringField(TEXT("graph_name"), OtherNode && OtherNode->GetGraph() ? OtherNode->GetGraph()->GetName() : FString());
        Edge->SetStringField(TEXT("node_guid"), OtherNode && OtherNode->NodeGuid.IsValid() ? OtherNode->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens) : FString());
        Edge->SetStringField(TEXT("object_path"), OtherNode ? OtherNode->GetPathName() : FString());
        Edge->SetStringField(TEXT("pin_id"), PinIdentity(Link));
        Edge->SetStringField(TEXT("pin_name"), Link ? Link->PinName.ToString() : FString());
        Edge->SetStringField(TEXT("direction"), Link && Link->Direction == EGPD_Input ? TEXT("input") : TEXT("output"));
        const bool bBroken = !Link || !OtherNode || OtherNode->GetGraph() != Pin->GetOwningNode()->GetGraph() ||
            Link->Direction == Pin->Direction || !HasReciprocalLink(Pin, Link);
        Edge->SetBoolField(TEXT("broken"), bBroken);
        if (bBroken) ++Broken;
        Links.Add(MakeShared<FJsonValueObject>(Edge));
    }
    Result->SetArrayField(TEXT("linked_to"), Links);
    Result->SetNumberField(TEXT("broken_link_count"), Broken);
    Result->SetBoolField(TEXT("broken"), Broken > 0);
    return Result;
}

JObject NodeProperties(const UEdGraphNode* Node)
{
    auto Result = MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> Properties;
    int32 Total = 0;
    for (TFieldIterator<FProperty> It(Node->GetClass()); It; ++It)
    {
        FProperty* Property = *It;
        if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient | CPF_NonPIEDuplicateTransient)) continue;
        ++Total;
        if (Properties.Num() >= MaxProperties) continue;
        FString Value;
        Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Node), nullptr,
            const_cast<UEdGraphNode*>(Node), PPF_None);
        auto Entry = MakeShared<FJsonObject>();
        Entry->SetStringField(TEXT("name"), Property->GetName());
        Entry->SetStringField(TEXT("property_class"), Property->GetClass()->GetName());
        Entry->SetStringField(TEXT("value"), Value.Left(4096));
        Entry->SetBoolField(TEXT("value_truncated"), Value.Len() > 4096);
        Entry->SetBoolField(TEXT("editable"), Property->HasAnyPropertyFlags(CPF_Edit));
        Properties.Add(MakeShared<FJsonValueObject>(Entry));
    }
    Result->SetArrayField(TEXT("properties"), Properties);
    Result->SetNumberField(TEXT("property_count"), Total);
    Result->SetBoolField(TEXT("properties_truncated"), Total > Properties.Num());
    return Result;
}

FString QueryFingerprint(const FString& GraphName, int32 PageSize, const FString& NodeGuid,
    const FString& ClassPath, const FString& Title, const FString& FunctionName, const FString& Comment)
{
    auto Query = MakeShared<FJsonObject>();
    Query->SetStringField(TEXT("graph"), GraphName);
    Query->SetNumberField(TEXT("page_size"), PageSize);
    Query->SetStringField(TEXT("node_guid"), NodeGuid);
    Query->SetStringField(TEXT("class_path"), ClassPath.ToLower());
    Query->SetStringField(TEXT("title"), Title.ToLower());
    Query->SetStringField(TEXT("function"), FunctionName.ToLower());
    Query->SetStringField(TEXT("comment"), Comment.ToLower());
    return Serialize(Query);
}

bool ParseCursor(const FString& Cursor, TCHAR ExpectedPrefix, FString& Id, int32& Offset)
{
    FString Left, Right;
    if (!Cursor.Split(TEXT(":"), &Left, &Right) || Left.Len() != 33 || Left[0] != ExpectedPrefix ||
        Right.IsEmpty() || Right.Len() > 10 || Cursor.Len() > 64) return false;
    FGuid Guid;
    if (!FGuid::Parse(Left.Mid(1), Guid) || !Guid.IsValid()) return false;
    for (TCHAR Character : Right) if (!FChar::IsDigit(Character)) return false;
    const int64 ParsedOffset = FCString::Atoi64(*Right);
    if (ParsedOffset < 0 || ParsedOffset > MAX_int32) return false;
    Offset = static_cast<int32>(ParsedOffset);
    Id = Left.Mid(1);
    return true;
}

FString MakeCursor(TCHAR Prefix, const FString& Id, int32 Offset)
{
    return FString::Printf(TEXT("%c%s:%d"), Prefix, *Id, Offset);
}

void AddGraphInfo(const UBlueprint* Blueprint, const UEdGraph* Graph, TArray<TSharedPtr<FJsonValue>>& Out)
{
    auto Entry = MakeShared<FJsonObject>();
    int32 InvalidGuids = 0;
    int32 NodeCount = 0;
    for (const UEdGraphNode* Node : Graph->Nodes) if (Node)
    {
        ++NodeCount;
        if (!Node->NodeGuid.IsValid()) ++InvalidGuids;
    }
    Entry->SetStringField(TEXT("name"), Graph->GetName());
    Entry->SetStringField(TEXT("graph_path"), Graph->GetPathName());
    Entry->SetStringField(TEXT("graph_type"), GraphType(Blueprint, Graph));
    Entry->SetStringField(TEXT("graph_class_path"), Graph->GetClass()->GetPathName());
    Entry->SetStringField(TEXT("schema_class_path"), Graph->GetSchema() ? Graph->GetSchema()->GetClass()->GetPathName() : FString());
    Entry->SetNumberField(TEXT("node_count"), NodeCount);
    Entry->SetNumberField(TEXT("null_node_slots"), Graph->Nodes.Num() - NodeCount);
    Entry->SetNumberField(TEXT("nodes_without_stable_guid"), InvalidGuids);
    Entry->SetStringField(TEXT("inspection_capability"), TEXT("PARTIAL"));
    Entry->SetStringField(TEXT("verification"), TEXT("Native runtime acceptance has not been completed for this implementation."));
    Entry->SetStringField(TEXT("mutation_capability"), TEXT("PARTIAL"));
    Out.Add(MakeShared<FJsonValueObject>(Entry));
}

bool CheckArgFields(const JObject& Args, const TSet<FString>& Allowed)
{
    for (const auto& Pair : Args->Values) if (!Allowed.Contains(Pair.Key)) return false;
    return true;
}
}

bool FForgeBlueprintInspection::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    using namespace ForgeBlueprintInspection;
    auto Fail = [&ErrorCode, &ErrorMessage](const TCHAR* Code, const TCHAR* Message)
    {
        ErrorCode = Code;
        ErrorMessage = Message;
        return false;
    };
    if (!IsInGameThread()) return Fail(TEXT("wrong_thread"), TEXT("Blueprint inspection requires Unreal's game thread."));

    for (auto It = NodeCursors.CreateIterator(); It; ++It)
        if (It.Value().Expires <= FPlatformTime::Seconds() || !It.Value().Graph.IsValid()) It.RemoveCurrent();
    for (auto It = PinCursors.CreateIterator(); It; ++It)
        if (It.Value().Expires <= FPlatformTime::Seconds() || !It.Value().Graph.IsValid() || !It.Value().Node.IsValid()) It.RemoveCurrent();

    auto ReserveCursor = [this]()
    {
        while (NodeCursors.Num() + PinCursors.Num() >= MaxCursors)
        {
            FString OldestId;
            double OldestExpiry = TNumericLimits<double>::Max();
            bool bOldestIsNode = false;
            for (const auto& Pair : NodeCursors)
                if (Pair.Value.Expires < OldestExpiry) { OldestExpiry = Pair.Value.Expires; OldestId = Pair.Key; bOldestIsNode = true; }
            for (const auto& Pair : PinCursors)
                if (Pair.Value.Expires < OldestExpiry) { OldestExpiry = Pair.Value.Expires; OldestId = Pair.Key; bOldestIsNode = false; }
            if (OldestId.IsEmpty()) return false;
            if (bOldestIsNode) NodeCursors.Remove(OldestId); else PinCursors.Remove(OldestId);
        }
        return true;
    };

    if (Command == TEXT("blueprint_capabilities"))
    {
        if (!Args->Values.IsEmpty()) return Fail(TEXT("invalid_arguments"), TEXT("This capability registry takes no arguments."));
        Data->SetStringField(TEXT("registry_version"), TEXT("2"));
        Data->SetStringField(TEXT("blueprint_scope"), TEXT("Native graph inspection implementation; live acceptance is required before production mutation work."));
        TArray<TSharedPtr<FJsonValue>> Entries;
        struct FCapability { const TCHAR* Name; const TCHAR* State; const TCHAR* Details; };
        const TArray<FCapability> Capabilities{
            {TEXT("graph_list"), TEXT("PARTIAL"), TEXT("Graph metadata readback; oversized graph lists fail explicitly and do not yet have their own cursor.")},
            {TEXT("node_guid_pagination"), TEXT("PARTIAL"), TEXT("Deterministic revision-checked cursors with explicit page/byte limits; invalid or ambiguous identities are reported.")},
            {TEXT("node_pin_inspection"), TEXT("PARTIAL"), TEXT("Bounded pin pages; an oversized single pin detail fails explicitly.")},
            {TEXT("node_reflected_properties"), TEXT("PARTIAL"), TEXT("Capped at 256 properties and 4096 characters per value; truncation is explicit.")},
            {TEXT("connection_readback"), TEXT("PARTIAL"), TEXT("Stable endpoint IDs and reciprocal/direction diagnostics; this is not a complete dependency validator.")},
            {TEXT("execution_trace"), TEXT("PARTIAL"), TEXT("Execution traversal within one graph, with explicit depth and node limits.")},
            {TEXT("function_macro_reference_readback"), TEXT("PARTIAL"), TEXT("Target references are reported; cross-graph execution is not merged.")},
            {TEXT("graph_mutation"), TEXT("PARTIAL"), TEXT("Legacy bounded node allowlist and full-asset snapshot remain in use.")},
            {TEXT("scoped_change_journal"), TEXT("PARTIAL"), TEXT("Windows existing normal-K2 graph adapter: move, primitive defaults, explicit connect/disconnect; separate verified package backup. Its own runtime acceptance is required. Legacy recipes retain their old snapshot limits.")},
            {TEXT("component_template_mutation"), TEXT("PARTIAL"), TEXT("Legacy support covers SCS mobility and static-mesh material slots.")},
            {TEXT("Blueprint_component_Niagara_system_assignment"), TEXT("UNSUPPORTED"), TEXT("Not implemented.")},
            {TEXT("Blueprint_asset_save_reload"), TEXT("UNSUPPORTED"), TEXT("Existing edit apply does not save or independently reload.")},
            {TEXT("animation_blueprint_and_rig_graphs"), TEXT("UNSUPPORTED"), TEXT("No dedicated mutation adapter is registered.")},
            {TEXT("native_runtime_acceptance"), TEXT("PARTIAL"), TEXT("Validation is recorded per binary, feature and session in dated evidence. This support registry is not an automatic test-status feed.")}
        };
        for (const auto& Capability : Capabilities)
        {
            auto Entry = MakeShared<FJsonObject>();
            Entry->SetStringField(TEXT("capability"), Capability.Name);
            Entry->SetStringField(TEXT("state"), Capability.State);
            Entry->SetStringField(TEXT("details"), Capability.Details);
            Entries.Add(MakeShared<FJsonValueObject>(Entry));
        }
        Data->SetArrayField(TEXT("capabilities"), Entries);
        Data->SetBoolField(TEXT("truncated"), false);
        return true;
    }

    const TSet<FString> AssetOnly{TEXT("asset_path")};
    const TSet<FString> PageFields{TEXT("asset_path"), TEXT("graph_name"), TEXT("page_size"), TEXT("cursor"),
        TEXT("node_guid"), TEXT("class_path"), TEXT("title_contains"), TEXT("function_name"), TEXT("comment_contains")};
    const TSet<FString> NodeFields{TEXT("asset_path"), TEXT("graph_name"), TEXT("node_guid"), TEXT("pin_page_size"), TEXT("pin_cursor")};
    const TSet<FString> TraceFields{TEXT("asset_path"), TEXT("graph_name"), TEXT("start_node_guid"), TEXT("direction"), TEXT("depth"), TEXT("node_limit")};

    FString AssetPath;
    if (!Args->TryGetStringField(TEXT("asset_path"), AssetPath)) return Fail(TEXT("invalid_arguments"), TEXT("asset_path is required."));
    UBlueprint* Blueprint = nullptr;
    if (!LoadBlueprint(AssetPath, Blueprint, ErrorCode, ErrorMessage)) return false;

    if (Command == TEXT("blueprint_graph_list"))
    {
        if (!CheckArgFields(Args, AssetOnly)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown graph-list arguments."));
        TArray<UEdGraph*> Graphs;
        Blueprint->GetAllGraphs(Graphs);
        TArray<TSharedPtr<FJsonValue>> Entries;
        for (const UEdGraph* Graph : Graphs) if (Graph) AddGraphInfo(Blueprint, Graph, Entries);
        Data->SetStringField(TEXT("asset_path"), Blueprint->GetOutermost()->GetName());
        Data->SetNumberField(TEXT("total_graphs"), Graphs.Num());
        Data->SetArrayField(TEXT("graphs"), Entries);
        Data->SetBoolField(TEXT("truncated"), false);
        if (Utf8Bytes(Serialize(Data)) > MaxResponseBytes)
            return Fail(TEXT("graph_list_too_large"), TEXT("All graph metadata exceeds the bounded response budget; no graph metadata was silently omitted."));
        return true;
    }

    FString GraphName;
    if (!Args->TryGetStringField(TEXT("graph_name"), GraphName)) return Fail(TEXT("invalid_arguments"), TEXT("graph_name is required."));
    bool bAmbiguousGraph = false;
    UEdGraph* Graph = FindGraph(Blueprint, GraphName, bAmbiguousGraph);
    if (bAmbiguousGraph) return Fail(TEXT("ambiguous_graph"), TEXT("More than one graph has this name; this API cannot select it safely by name."));
    if (!Graph) return Fail(TEXT("graph_not_found"), TEXT("The exact graph name was not found on this Blueprint."));

    if (Command == TEXT("blueprint_graph_page"))
    {
        if (!CheckArgFields(Args, PageFields)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown graph page arguments."));
        int32 PageSize = 32;
        double PageSizeValue = 32;
        if (Args->HasField(TEXT("page_size")) && (!Args->TryGetNumberField(TEXT("page_size"), PageSizeValue) ||
            !FMath::IsFinite(PageSizeValue) || FMath::FloorToDouble(PageSizeValue) != PageSizeValue || PageSizeValue < 1 || PageSizeValue > MaxGraphPageSize))
            return Fail(TEXT("invalid_arguments"), TEXT("page_size must be an integer from 1 through 64."));
        PageSize = static_cast<int32>(PageSizeValue);
        FString Cursor, RequestedNodeGuid, ClassFilter, TitleFilter, FunctionFilter, CommentFilter;
        Args->TryGetStringField(TEXT("cursor"), Cursor);
        Args->TryGetStringField(TEXT("node_guid"), RequestedNodeGuid);
        Args->TryGetStringField(TEXT("class_path"), ClassFilter);
        Args->TryGetStringField(TEXT("title_contains"), TitleFilter);
        Args->TryGetStringField(TEXT("function_name"), FunctionFilter);
        Args->TryGetStringField(TEXT("comment_contains"), CommentFilter);
        if (RequestedNodeGuid.Len() > 64 || ClassFilter.Len() > 512 || TitleFilter.Len() > 256 ||
            FunctionFilter.Len() > 128 || CommentFilter.Len() > 256 || Cursor.Len() > 64)
            return Fail(TEXT("invalid_arguments"), TEXT("A graph page filter exceeds its bound."));
        if (!RequestedNodeGuid.IsEmpty())
        {
            FGuid RequestedGuid;
            if (!FGuid::Parse(RequestedNodeGuid, RequestedGuid) || !RequestedGuid.IsValid())
                return Fail(TEXT("invalid_arguments"), TEXT("node_guid must be a valid nonzero NodeGuid."));
            RequestedNodeGuid = RequestedGuid.ToString(EGuidFormats::Digits);
        }
        const FString Query = QueryFingerprint(GraphName, PageSize, RequestedNodeGuid, ClassFilter, TitleFilter, FunctionFilter, CommentFilter);

        FNodeCursor Snapshot;
        FString CursorId;
        int32 Offset = 0;
        if (!Cursor.IsEmpty())
        {
            if (!ParseCursor(Cursor, TEXT('g'), CursorId, Offset) || !NodeCursors.Contains(CursorId))
                return Fail(TEXT("invalid_cursor"), TEXT("The graph cursor is invalid, expired, or belongs to another inspection."));
            Snapshot = NodeCursors[CursorId];
            if (Snapshot.AssetPath != AssetPath || Snapshot.GraphName != GraphName || Snapshot.Query != Query || Snapshot.PageSize != PageSize)
                return Fail(TEXT("invalid_cursor"), TEXT("The graph cursor does not match the asset, graph, filters, or page size."));
            if (!Snapshot.Graph.IsValid() || Snapshot.Graph.Get() != Graph || Snapshot.Blueprint.Get() != Blueprint ||
                GraphFingerprint(Graph) != Snapshot.Fingerprint)
            {
                NodeCursors.Remove(CursorId);
                return Fail(TEXT("stale_cursor"), TEXT("The graph changed after pagination began; restart inspection at the first page."));
            }
        }
        else
        {
            Snapshot.Blueprint = Blueprint;
            Snapshot.Graph = Graph;
            Snapshot.AssetPath = AssetPath;
            Snapshot.GraphName = GraphName;
            Snapshot.Query = Query;
            Snapshot.PageSize = PageSize;
            Snapshot.Expires = FPlatformTime::Seconds() + CursorLifetimeSeconds;
            Snapshot.Fingerprint = GraphFingerprint(Graph);
            TArray<UEdGraphNode*> Candidates;
            for (UEdGraphNode* Node : Graph->Nodes) if (Node) Candidates.Add(Node);
            Candidates.Sort([](const UEdGraphNode& A, const UEdGraphNode& B)
            {
                const FString Left = A.NodeGuid.IsValid() ? A.NodeGuid.ToString(EGuidFormats::Digits) : A.GetPathName();
                const FString Right = B.NodeGuid.IsValid() ? B.NodeGuid.ToString(EGuidFormats::Digits) : B.GetPathName();
                return Left < Right;
            });
            TSet<FGuid> SeenGuids;
            for (UEdGraphNode* Node : Candidates)
            {
                if (!Node) continue;
                if (Node->NodeGuid.IsValid() && SeenGuids.Contains(Node->NodeGuid))
                    return Fail(TEXT("unstable_node_identity"), TEXT("This graph contains duplicate NodeGuid values; stable pagination cannot be guaranteed."));
                if (Node->NodeGuid.IsValid()) SeenGuids.Add(Node->NodeGuid);
                if (!RequestedNodeGuid.IsEmpty() && Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens) != RequestedNodeGuid &&
                    Node->NodeGuid.ToString(EGuidFormats::Digits) != RequestedNodeGuid) continue;
                if (!ClassFilter.IsEmpty() && !Node->GetClass()->GetPathName().Contains(ClassFilter, ESearchCase::IgnoreCase)) continue;
                if (!TitleFilter.IsEmpty() && !Node->GetNodeTitle(ENodeTitleType::ListView).ToString().Contains(TitleFilter, ESearchCase::IgnoreCase)) continue;
                if (!FunctionFilter.IsEmpty() && !NodeFunctionName(Node).Contains(FunctionFilter, ESearchCase::IgnoreCase)) continue;
                if (!CommentFilter.IsEmpty() && !Node->NodeComment.Contains(CommentFilter, ESearchCase::IgnoreCase)) continue;
                Snapshot.Nodes.Add(Node);
            }
        }

        if (Offset > Snapshot.Nodes.Num()) return Fail(TEXT("invalid_cursor"), TEXT("The graph cursor offset exceeds the inspection snapshot."));
        auto BuildPage = [&](int32 Count, TSharedRef<FJsonObject> Out)
        {
            TArray<TSharedPtr<FJsonValue>> Items;
            for (int32 Index = 0; Index < Count; ++Index)
            {
                UEdGraphNode* Node = Snapshot.Nodes[Offset + Index].Get();
                if (!Node) continue;
                Items.Add(MakeShared<FJsonValueObject>(NodeSummary(Blueprint, Graph, Node)));
            }
            Out->SetStringField(TEXT("asset_path"), AssetPath);
            Out->SetStringField(TEXT("graph_name"), GraphName);
            Out->SetStringField(TEXT("graph_fingerprint"), Snapshot.Fingerprint);
            Out->SetNumberField(TEXT("total_nodes"), Snapshot.Nodes.Num());
            Out->SetNumberField(TEXT("offset"), Offset);
            Out->SetNumberField(TEXT("returned_nodes"), Items.Num());
            Out->SetArrayField(TEXT("nodes"), Items);
            const bool bMore = Offset + Count < Snapshot.Nodes.Num();
            Out->SetBoolField(TEXT("has_more"), bMore);
            Out->SetBoolField(TEXT("truncated"), bMore);
            Out->SetStringField(TEXT("next_cursor"), bMore ? MakeCursor(TEXT('g'), CursorId, Offset + Count) : FString());
        };

        int32 Count = FMath::Min(PageSize, Snapshot.Nodes.Num() - Offset);
        if (CursorId.IsEmpty() && Count < Snapshot.Nodes.Num()) CursorId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        if (!CursorId.IsEmpty()) Snapshot.Expires = FPlatformTime::Seconds() + CursorLifetimeSeconds;
        TSharedRef<FJsonObject> Page = MakeShared<FJsonObject>();
        do
        {
            Page->Values.Empty();
            BuildPage(Count, Page);
            if (Utf8Bytes(Serialize(Page)) <= MaxResponseBytes || Count <= 1) break;
            --Count;
        } while (Count > 0);
        if (Utf8Bytes(Serialize(Page)) > MaxResponseBytes)
            return Fail(TEXT("node_summary_too_large"), TEXT("A single node summary exceeds the response budget; inspect it individually."));

        if (Page->GetBoolField(TEXT("has_more")))
        {
            if (CursorId.IsEmpty()) CursorId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
            if (!ReserveCursor()) return Fail(TEXT("cursor_capacity"), TEXT("No cursor slot is available for this page; wait for an existing cursor to expire."));
            NodeCursors.Add(CursorId, Snapshot);
            Page->SetStringField(TEXT("next_cursor"), MakeCursor(TEXT('g'), CursorId, Offset + Count));
        }
        else if (!Cursor.IsEmpty()) NodeCursors.Remove(CursorId);
        Data->Values = MoveTemp(Page->Values);
        return true;
    }

    if (Command == TEXT("blueprint_node_inspect"))
    {
        if (!CheckArgFields(Args, NodeFields)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown node inspection arguments."));
        FString GuidText, Cursor;
        if (!Args->TryGetStringField(TEXT("node_guid"), GuidText)) return Fail(TEXT("invalid_arguments"), TEXT("node_guid is required."));
        Args->TryGetStringField(TEXT("pin_cursor"), Cursor);
        double PageSizeValue = 32;
        if (Args->HasField(TEXT("pin_page_size")) && (!Args->TryGetNumberField(TEXT("pin_page_size"), PageSizeValue) || !FMath::IsFinite(PageSizeValue) ||
            FMath::FloorToDouble(PageSizeValue) != PageSizeValue || PageSizeValue < 1 || PageSizeValue > MaxPinPageSize))
            return Fail(TEXT("invalid_arguments"), TEXT("pin_page_size must be an integer from 1 through 128."));
        const int32 PageSize = static_cast<int32>(PageSizeValue);
        bool bAmbiguousNode = false;
        UEdGraphNode* Node = FindNode(Graph, GuidText, bAmbiguousNode);
        if (bAmbiguousNode) return Fail(TEXT("unstable_node_identity"), TEXT("More than one node has this NodeGuid; individual inspection is ambiguous."));
        if (!Node) return Fail(TEXT("node_not_found"), TEXT("The exact NodeGuid was not found in this graph."));
        const FString Fingerprint = GraphFingerprint(Graph);
        FPinCursor Snapshot;
        FString CursorId;
        int32 Offset = 0;
        if (!Cursor.IsEmpty())
        {
            if (!ParseCursor(Cursor, TEXT('p'), CursorId, Offset) || !PinCursors.Contains(CursorId))
                return Fail(TEXT("invalid_cursor"), TEXT("The pin cursor is invalid, expired, or belongs to another node."));
            Snapshot = PinCursors[CursorId];
            if (Snapshot.AssetPath != AssetPath || Snapshot.GraphName != GraphName || Snapshot.NodeGuid != Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens) || Snapshot.PageSize != PageSize)
                return Fail(TEXT("invalid_cursor"), TEXT("The pin cursor does not match the asset, graph, node, or page size."));
            if (!Snapshot.Graph.IsValid() || Snapshot.Graph.Get() != Graph || Snapshot.Blueprint.Get() != Blueprint ||
                Snapshot.Node.Get() != Node || Fingerprint != Snapshot.Fingerprint)
            {
                PinCursors.Remove(CursorId);
                return Fail(TEXT("stale_cursor"), TEXT("The graph changed after pin pagination began; restart node inspection."));
            }
        }
        else
        {
            Snapshot.Blueprint = Blueprint;
            Snapshot.Graph = Graph;
            Snapshot.Node = Node;
            Snapshot.AssetPath = AssetPath;
            Snapshot.GraphName = GraphName;
            Snapshot.NodeGuid = Node->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens);
            Snapshot.Fingerprint = Fingerprint;
            Snapshot.PageSize = PageSize;
            Snapshot.Expires = FPlatformTime::Seconds() + CursorLifetimeSeconds;
            for (int32 PinIndex = 0; PinIndex < Node->Pins.Num(); ++PinIndex)
                if (Node->Pins[PinIndex]) Snapshot.PinIndexes.Add(PinIndex);
            Snapshot.PinIndexes.Sort([Node](int32 LeftIndex, int32 RightIndex)
            {
                const UEdGraphPin& A = *Node->Pins[LeftIndex];
                const UEdGraphPin& B = *Node->Pins[RightIndex];
                const FString Left = A.PinId.IsValid() ? A.PinId.ToString(EGuidFormats::Digits) : A.PinName.ToString() + FString::FromInt(static_cast<int32>(A.Direction));
                const FString Right = B.PinId.IsValid() ? B.PinId.ToString(EGuidFormats::Digits) : B.PinName.ToString() + FString::FromInt(static_cast<int32>(B.Direction));
                return Left == Right ? LeftIndex < RightIndex : Left < Right;
            });
        }
        if (Offset > Snapshot.PinIndexes.Num()) return Fail(TEXT("invalid_cursor"), TEXT("The pin cursor offset exceeds the inspection snapshot."));
        int32 Count = FMath::Min(PageSize, Snapshot.PinIndexes.Num() - Offset);
        if (CursorId.IsEmpty() && Count < Snapshot.PinIndexes.Num()) CursorId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        auto BuildPage = [&](int32 ItemCount, TSharedRef<FJsonObject> Out)
        {
            TArray<TSharedPtr<FJsonValue>> Pins;
            for (int32 Index = 0; Index < ItemCount; ++Index)
                if (UEdGraphPin* Pin = Node->Pins[Snapshot.PinIndexes[Offset + Index]]) Pins.Add(MakeShared<FJsonValueObject>(PinInfo(Pin)));
            Out->SetStringField(TEXT("asset_path"), AssetPath);
            Out->SetStringField(TEXT("graph_name"), GraphName);
            Out->SetObjectField(TEXT("node"), NodeSummary(Blueprint, Graph, Node));
            Out->SetObjectField(TEXT("reflected_properties"), NodeProperties(Node));
            Out->SetNumberField(TEXT("total_pins"), Snapshot.PinIndexes.Num());
            Out->SetNumberField(TEXT("null_pin_slots"), Node->Pins.Num() - Snapshot.PinIndexes.Num());
            Out->SetNumberField(TEXT("pin_offset"), Offset);
            Out->SetNumberField(TEXT("returned_pins"), Pins.Num());
            Out->SetArrayField(TEXT("pins"), Pins);
            const bool bMore = Offset + ItemCount < Snapshot.PinIndexes.Num();
            Out->SetBoolField(TEXT("has_more_pins"), bMore);
            Out->SetBoolField(TEXT("truncated"), bMore);
            Out->SetStringField(TEXT("next_cursor"), bMore ? MakeCursor(TEXT('p'), CursorId, Offset + ItemCount) : FString());
        };
        TSharedRef<FJsonObject> Page = MakeShared<FJsonObject>();
        do
        {
            Page->Values.Empty();
            BuildPage(Count, Page);
            if (Utf8Bytes(Serialize(Page)) <= MaxResponseBytes || Count <= 1) break;
            --Count;
        } while (Count > 0);
        if (Utf8Bytes(Serialize(Page)) > MaxResponseBytes)
            return Fail(TEXT("pin_detail_too_large"), TEXT("A single pin detail exceeds the response budget; its linked endpoints or defaults are unusually large."));
        if (Page->GetBoolField(TEXT("has_more_pins")))
        {
            if (CursorId.IsEmpty()) CursorId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
            if (!ReserveCursor()) return Fail(TEXT("cursor_capacity"), TEXT("No cursor slot is available for this page; wait for an existing cursor to expire."));
            Snapshot.Expires = FPlatformTime::Seconds() + CursorLifetimeSeconds;
            PinCursors.Add(CursorId, Snapshot);
            Page->SetStringField(TEXT("next_cursor"), MakeCursor(TEXT('p'), CursorId, Offset + Count));
        }
        else if (!Cursor.IsEmpty()) PinCursors.Remove(CursorId);
        Data->Values = MoveTemp(Page->Values);
        return true;
    }

    if (Command == TEXT("blueprint_graph_trace"))
    {
        if (!CheckArgFields(Args, TraceFields)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown graph trace arguments."));
        FString StartGuid, Direction = TEXT("forward");
        Args->TryGetStringField(TEXT("start_node_guid"), StartGuid);
        Args->TryGetStringField(TEXT("direction"), Direction);
        if (StartGuid.IsEmpty() || (Direction != TEXT("forward") && Direction != TEXT("backward") && Direction != TEXT("both")))
            return Fail(TEXT("invalid_arguments"), TEXT("Trace requires a NodeGuid and direction forward, backward, or both."));
        double DepthValue = 4, LimitValue = 256;
        if (Args->HasField(TEXT("depth")) && !Args->TryGetNumberField(TEXT("depth"), DepthValue)) return Fail(TEXT("invalid_arguments"), TEXT("depth must be numeric."));
        if (Args->HasField(TEXT("node_limit")) && !Args->TryGetNumberField(TEXT("node_limit"), LimitValue)) return Fail(TEXT("invalid_arguments"), TEXT("node_limit must be numeric."));
        if (!FMath::IsFinite(DepthValue) || FMath::FloorToDouble(DepthValue) != DepthValue || DepthValue < 0 || DepthValue > 32 ||
            !FMath::IsFinite(LimitValue) || FMath::FloorToDouble(LimitValue) != LimitValue || LimitValue < 1 || LimitValue > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("depth must be 0-32 and node_limit must be 1-512."));
        bool bAmbiguousNode = false;
        UEdGraphNode* Start = FindNode(Graph, StartGuid, bAmbiguousNode);
        if (bAmbiguousNode) return Fail(TEXT("unstable_node_identity"), TEXT("More than one node has this NodeGuid; execution traversal is ambiguous."));
        if (!Start) return Fail(TEXT("node_not_found"), TEXT("The exact start NodeGuid was not found in this graph."));

        struct FQueuedNode { UEdGraphNode* Node; int32 Depth; };
        TArray<FQueuedNode> Queue;
        TMap<FGuid, int32> Visited;
        TSet<FString> SeenEdges;
        TArray<TSharedPtr<FJsonValue>> Nodes, Edges;
        Queue.Add({Start, 0});
        Visited.Add(Start->NodeGuid, 0);
        bool bDepthLimited = false;
        bool bNodeLimited = false;
        for (int32 QueueIndex = 0; QueueIndex < Queue.Num(); ++QueueIndex)
        {
            const FQueuedNode Current = Queue[QueueIndex];
            Nodes.Add(MakeShared<FJsonValueObject>(NodeSummary(Blueprint, Graph, Current.Node)));
            for (UEdGraphPin* Pin : Current.Node->Pins)
            {
                if (!Pin || Pin->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec) continue;
                const bool bForward = Direction == TEXT("forward") || Direction == TEXT("both");
                const bool bBackward = Direction == TEXT("backward") || Direction == TEXT("both");
                if ((Pin->Direction == EGPD_Output && !bForward) || (Pin->Direction == EGPD_Input && !bBackward)) continue;
                for (UEdGraphPin* Link : Pin->LinkedTo)
                {
                    UEdGraphNode* Other = Link ? Link->GetOwningNode() : nullptr;
                    if (!Other || Other->GetGraph() != Graph || !Other->NodeGuid.IsValid() || !Current.Node->NodeGuid.IsValid()) continue;
                    if (Current.Depth >= static_cast<int32>(DepthValue))
                    {
                        if (!Visited.Contains(Other->NodeGuid)) bDepthLimited = true;
                        continue;
                    }
                    auto Edge = MakeShared<FJsonObject>();
                    UEdGraphPin* Source = Pin->Direction == EGPD_Output ? Pin : Link;
                    UEdGraphPin* Target = Pin->Direction == EGPD_Output ? Link : Pin;
                    Edge->SetStringField(TEXT("source_node_guid"), Source->GetOwningNode()->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
                    Edge->SetStringField(TEXT("source_pin_id"), PinIdentity(Source));
                    Edge->SetStringField(TEXT("source_pin_name"), Source->PinName.ToString());
                    Edge->SetStringField(TEXT("destination_node_guid"), Target->GetOwningNode()->NodeGuid.ToString(EGuidFormats::DigitsWithHyphens));
                    Edge->SetStringField(TEXT("destination_pin_id"), PinIdentity(Target));
                    Edge->SetStringField(TEXT("destination_pin_name"), Target->PinName.ToString());
                    const FString EdgeKey = Source->GetOwningNode()->NodeGuid.ToString() + TEXT(":") + PinIdentity(Source) + TEXT(":") +
                        Target->GetOwningNode()->NodeGuid.ToString() + TEXT(":") + PinIdentity(Target);
                    if (!SeenEdges.Contains(EdgeKey)) { SeenEdges.Add(EdgeKey); Edges.Add(MakeShared<FJsonValueObject>(Edge)); }
                    if (!Visited.Contains(Other->NodeGuid))
                    {
                        if (Visited.Num() >= static_cast<int32>(LimitValue)) { bNodeLimited = true; continue; }
                        Visited.Add(Other->NodeGuid, Current.Depth + 1);
                        Queue.Add({Other, Current.Depth + 1});
                    }
                }
            }
        }
        Data->SetStringField(TEXT("asset_path"), AssetPath);
        Data->SetStringField(TEXT("graph_name"), GraphName);
        Data->SetStringField(TEXT("direction"), Direction);
        Data->SetNumberField(TEXT("max_depth"), DepthValue);
        Data->SetNumberField(TEXT("visited_node_count"), Visited.Num());
        Data->SetArrayField(TEXT("nodes"), Nodes);
        Data->SetArrayField(TEXT("execution_edges"), Edges);
        Data->SetBoolField(TEXT("depth_limited"), bDepthLimited);
        Data->SetBoolField(TEXT("node_limit_reached"), bNodeLimited);
        Data->SetBoolField(TEXT("truncated"), bNodeLimited || bDepthLimited);
        Data->SetBoolField(TEXT("cross_graph_references_followed"), false);
        Data->SetStringField(TEXT("reference_note"), TEXT("Function and macro targets are resolved by blueprint_node_inspect; cross-graph execution is not merged into this trace."));
        if (Utf8Bytes(Serialize(Data)) > MaxResponseBytes)
            return Fail(TEXT("trace_response_too_large"), TEXT("The requested trace exceeds the bounded response budget; reduce depth or node_limit."));
        return true;
    }

    return Fail(TEXT("command_not_allowed"), TEXT("Unsupported Blueprint inspection command."));
}
