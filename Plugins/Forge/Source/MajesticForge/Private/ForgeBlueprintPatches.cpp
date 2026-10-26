#include "ForgeBlueprintPatches.h"

#include "Editor.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "Engine/SCS_Node.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/World.h"
#include "Components/ActorComponent.h"
#include "HAL/FileManager.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/CompilerResultsLog.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Logging/TokenizedMessage.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/PackagePath.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "ScopedTransaction.h"
#include "Serialization/Archive.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
#include <bcrypt.h>
#include <sddl.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

namespace ForgeBlueprintPatches
{
using JObject = TSharedRef<FJsonObject>;
constexpr int32 MaxOperations = 32;
constexpr int32 MaxScopePins = 128;
constexpr int32 MaxScopeLinks = 4096;

FString Text(const JObject& Object, const TCHAR* Key)
{ FString Value; Object->TryGetStringField(Key, Value); return Value; }
FString Json(const JObject& Object)
{
    FString Value;
    FJsonSerializer::Serialize(Object, TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Value));
    return Value;
}
int32 Utf8Size(const FString& Value) { FTCHARToUTF8 Encoded(*Value, Value.Len()); return Encoded.Length(); }
bool Fields(const JObject& Object, const TSet<FString>& Allowed)
{ for (const auto& Pair : Object->Values) if (!Allowed.Contains(Pair.Key)) return false; return true; }
bool Guid(const FString& Value, FGuid& Out)
{ return Value.Len() <= 36 && FGuid::Parse(Value, Out) && Out.IsValid(); }
FString Id(const FGuid& Value) { return Value.ToString(EGuidFormats::Digits); }
FString PinKey(const UEdGraphPin* Pin)
{ return Pin && Pin->GetOwningNode() ? Id(Pin->GetOwningNode()->NodeGuid) + TEXT(":") + Id(Pin->PinId) : FString(); }
FString TypeText(const FEdGraphPinType& Type)
{
    FString Value;
    FEdGraphPinType::StaticStruct()->ExportText(Value, &Type, nullptr, nullptr, PPF_None, nullptr);
    return Value;
}
FString TextIdentity(const FText& Value)
{ FString Out; FTextStringHelper::WriteToBuffer(Out, Value); return Out; }

// Streaming SHA-256 is used for package backups and semantic comparisons. Do
// not call GenericPlatformMisc's unimplemented SHA-256 fallback on other OSes.
class FHash
{
#if PLATFORM_WINDOWS
    BCRYPT_ALG_HANDLE Algorithm = nullptr;
    BCRYPT_HASH_HANDLE Hash = nullptr;
#endif
    bool bValid = false;
public:
    FHash()
    {
#if PLATFORM_WINDOWS
        bValid = BCryptOpenAlgorithmProvider(&Algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0 &&
            BCryptCreateHash(Algorithm, &Hash, nullptr, 0, nullptr, 0, 0) >= 0;
#endif
    }
    ~FHash()
    {
#if PLATFORM_WINDOWS
        if (Hash) BCryptDestroyHash(Hash);
        if (Algorithm) BCryptCloseAlgorithmProvider(Algorithm, 0);
#endif
    }
    bool Valid() const { return bValid; }
    void Bytes(const void* Data, uint32 Count)
    {
#if PLATFORM_WINDOWS
        if (bValid && Count) bValid = BCryptHashData(Hash, const_cast<PUCHAR>(static_cast<const UCHAR*>(Data)), Count, 0) >= 0;
#endif
    }
    void Add(const FString& Value)
    {
        FTCHARToUTF8 Encoded(*Value, Value.Len());
        const uint64 Count = Encoded.Length();
        Bytes(&Count, sizeof(Count));
        Bytes(Encoded.Get(), Encoded.Length());
    }
    FString Finish()
    {
#if PLATFORM_WINDOWS
        uint8 Digest[32];
        if (bValid && BCryptFinishHash(Hash, Digest, sizeof(Digest), 0) >= 0)
        { bValid = false; return BytesToHex(Digest, sizeof(Digest)).ToLower(); }
#endif
        bValid = false;
        return FString();
    }
};
FString Digest(const FString& Value) { FHash Hash; Hash.Add(Value); return Hash.Finish(); }
bool FileHash(const FString& Filename, FString& Out)
{
    TUniquePtr<FArchive> Reader(IFileManager::Get().CreateFileReader(*Filename));
    FHash Hash;
    if (!Reader || !Hash.Valid() || Reader->TotalSize() < 0) return false;
    TArray<uint8> Buffer; Buffer.SetNumUninitialized(64 * 1024);
    int64 Remaining = Reader->TotalSize();
    while (Remaining > 0)
    {
        const int32 Count = static_cast<int32>(FMath::Min<int64>(Remaining, Buffer.Num()));
        Reader->Serialize(Buffer.GetData(), Count);
        if (Reader->IsError()) return false;
        Hash.Bytes(Buffer.GetData(), Count);
        Remaining -= Count;
    }
    Out = Hash.Finish();
    return !Out.IsEmpty();
}
bool SafePath(const FString& InPath)
{
#if PLATFORM_WINDOWS
    FString Path = FPaths::ConvertRelativePathToFull(InPath);
    FPaths::CollapseRelativeDirectories(Path);
    FPaths::MakePlatformFilename(Path);
    while (!Path.IsEmpty())
    {
        const DWORD Attributes = GetFileAttributesW(*Path);
        if (Attributes != INVALID_FILE_ATTRIBUTES && (Attributes & FILE_ATTRIBUTE_REPARSE_POINT)) return false;
        const FString Parent = FPaths::GetPath(Path);
        if (Parent == Path) break;
        Path = Parent;
    }
    return true;
#else
    return false;
#endif
}
bool PrivateDirectory(const FString& Path)
{
#if PLATFORM_WINDOWS
    if (!SafePath(Path) || !IFileManager::Get().MakeDirectory(*Path, true)) return false;
    PSECURITY_DESCRIPTOR Descriptor = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)",
        SDDL_REVISION_1, &Descriptor, nullptr)) return false;
    const bool bOk = SetFileSecurityW(*Path, DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION, Descriptor) != 0;
    LocalFree(Descriptor);
    return bOk;
#else
    return false;
#endif
}

struct FDiskFile { FString Path, RelativePath, Sha256; };
struct FNodeScope
{
    TWeakObjectPtr<UEdGraphNode> Node;
    FGuid Guid;
    FString ClassPath, Identity;
    bool bMove = false;
    int32 BeforeX = 0, BeforeY = 0, AfterX = 0, AfterY = 0;
};
struct FPinScope
{
    FString NodeKey;
    FGuid Guid;
    FName Name;
    EEdGraphPinDirection Direction = EGPD_Input;
    bool bDefaultIgnored = false;
    bool bDefault = false, bLinks = false;
    FEdGraphPinType BeforeType, AfterType;
    FString BeforeValue, AfterValue, ObjectPath, TextValue;
    TSet<FString> BeforeLinks, AfterLinks;
};
struct FOperation { FString Kind, NodeKey, Pin, OtherPin; int32 X = 0, Y = 0; FString Value; };
struct FPlan
{
    TWeakObjectPtr<UBlueprint> Blueprint;
    TWeakObjectPtr<UEdGraph> Graph;
    FString AssetPath, GraphName, GraphPath, WorldPath, ProjectFile, PreviewId, BeforeState;
    TMap<FString, FNodeScope> Nodes;
    TMap<FString, FPinScope> Pins;
    TArray<FOperation> Operations;
    TArray<FString> PrefixDigests;
    TArray<FDiskFile> Files;
    TSharedPtr<FJsonObject> Request;
    double Expires = 0;
};

UEdGraphNode* FindNode(UEdGraph* Graph, const FGuid& Guid)
{
    UEdGraphNode* Found = nullptr;
    for (UEdGraphNode* Node : Graph->Nodes) if (Node && Node->NodeGuid == Guid)
    { if (Found) return nullptr; Found = Node; }
    return Found;
}
FString NodeIdentity(const UEdGraphNode* Node)
{
    auto Identity = MakeShared<FJsonObject>();
    for (const TCHAR* Name : {TEXT("FunctionReference"), TEXT("VariableReference"), TEXT("EventReference"), TEXT("CustomFunctionName")})
        if (const FProperty* Property = Node->GetClass()->FindPropertyByName(Name))
        {
            FString Value;
            Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Node), nullptr,
                const_cast<UEdGraphNode*>(Node), PPF_None);
            Identity->SetStringField(Name, Value);
        }
    if (const auto* Call = Cast<UK2Node_CallFunction>(Node))
        if (const UFunction* Function = Call->GetTargetFunction())
        {
            FString Signature = Function->GetPathName() + TEXT(":") + LexToString(static_cast<uint32>(Function->FunctionFlags));
            for (TFieldIterator<FProperty> It(Function); It; ++It) if (It->HasAnyPropertyFlags(CPF_Parm))
                Signature += TEXT("|") + It->GetName() + TEXT(":") + It->GetCPPType() + TEXT(":") + LexToString(static_cast<uint64>(It->GetPropertyFlags()));
            Identity->SetStringField(TEXT("resolved_function_signature"), Signature);
        }
    return Json(Identity);
}
UEdGraphPin* ResolvePin(const FPlan& Plan, const FString& Key)
{
    const FPinScope* Pin = Plan.Pins.Find(Key);
    const FNodeScope* Node = Pin ? Plan.Nodes.Find(Pin->NodeKey) : nullptr;
    if (!Node || !Node->Node.IsValid() || !Plan.Graph.IsValid() ||
        Node->Node->GetGraph() != Plan.Graph.Get() || FindNode(Plan.Graph.Get(), Node->Guid) != Node->Node.Get()) return nullptr;
    UEdGraphPin* Found = Node->Node->FindPinById(Pin->Guid);
    int32 Matches = 0;
    for (UEdGraphPin* Candidate : Node->Node->Pins) if (Candidate && Candidate->PinId == Pin->Guid) ++Matches;
    return Matches == 1 ? Found : nullptr;
}
bool LinkSet(UEdGraphPin* Pin, TSet<FString>& Out)
{
    Out.Empty();
    if (!Pin || !Pin->PinId.IsValid() || Pin->LinkedTo.Num() > MaxScopeLinks) return false;
    for (UEdGraphPin* Link : Pin->LinkedTo)
    {
        if (!Link || !Link->PinId.IsValid() || !Link->GetOwningNode() || !Link->GetOwningNode()->NodeGuid.IsValid() ||
            Link->GetOwningNode()->GetGraph() != Pin->GetOwningNode()->GetGraph() ||
            !Link->LinkedTo.Contains(Pin) || Link->Direction == Pin->Direction) return false;
        Out.Add(PinKey(Link));
    }
    return Out.Num() == Pin->LinkedTo.Num();
}
JObject ScopeState(const FPlan& Plan, bool bCurrent, bool bAfter, bool& bValid)
{
    auto State = MakeShared<FJsonObject>();
    TArray<FString> Keys; Plan.Nodes.GetKeys(Keys); Keys.Sort();
    TArray<TSharedPtr<FJsonValue>> Nodes, Pins;
    bValid = Plan.Blueprint.IsValid() && Plan.Graph.IsValid();
    for (const FString& Key : Keys)
    {
        const FNodeScope& Scope = Plan.Nodes[Key];
        UEdGraphNode* Node = Scope.Node.Get();
        if (!Node || !bValid || Node->GetGraph() != Plan.Graph.Get() ||
            FindNode(Plan.Graph.Get(), Scope.Guid) != Node || Node->GetClass()->GetPathName() != Scope.ClassPath)
        { bValid = false; return State; }
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("node_guid"), Key);
        Row->SetStringField(TEXT("class_path"), Scope.ClassPath);
        Row->SetStringField(TEXT("member_identity"), bCurrent ? NodeIdentity(Node) : Scope.Identity);
        if (Scope.bMove)
        {
            Row->SetNumberField(TEXT("x"), bCurrent ? Node->NodePosX : bAfter ? Scope.AfterX : Scope.BeforeX);
            Row->SetNumberField(TEXT("y"), bCurrent ? Node->NodePosY : bAfter ? Scope.AfterY : Scope.BeforeY);
        }
        Nodes.Add(MakeShared<FJsonValueObject>(Row));
    }
    Plan.Pins.GetKeys(Keys); Keys.Sort();
    for (const FString& Key : Keys)
    {
        const FPinScope& Scope = Plan.Pins[Key];
        UEdGraphPin* Pin = bCurrent ? ResolvePin(Plan, Key) : nullptr;
        if (bCurrent && !Pin) { bValid = false; return State; }
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("pin_key"), Key);
        Row->SetStringField(TEXT("pin_name"), bCurrent ? Pin->PinName.ToString() : Scope.Name.ToString());
        Row->SetNumberField(TEXT("direction"), bCurrent ? static_cast<int32>(Pin->Direction) : static_cast<int32>(Scope.Direction));
        Row->SetBoolField(TEXT("orphaned"), bCurrent && Pin->bOrphanedPin);
        Row->SetBoolField(TEXT("default_ignored"), bCurrent ? Pin->bDefaultValueIsIgnored : Scope.bDefaultIgnored);
        Row->SetStringField(TEXT("type"), TypeText(bCurrent ? Pin->PinType : bAfter ? Scope.AfterType : Scope.BeforeType));
        if (Scope.bDefault)
        {
            Row->SetStringField(TEXT("value"), bCurrent ? Pin->DefaultValue : bAfter ? Scope.AfterValue : Scope.BeforeValue);
            Row->SetStringField(TEXT("object"), bCurrent ? GetPathNameSafe(Pin->DefaultObject) : Scope.ObjectPath);
            Row->SetStringField(TEXT("text"), bCurrent ? TextIdentity(Pin->DefaultTextValue) : Scope.TextValue);
        }
        if (Scope.bLinks)
        {
            TSet<FString> Links = bAfter ? Scope.AfterLinks : Scope.BeforeLinks;
            if (bCurrent && !LinkSet(Pin, Links)) { bValid = false; return State; }
            TArray<FString> Sorted = Links.Array(); Sorted.Sort();
            TArray<TSharedPtr<FJsonValue>> Values;
            for (const FString& Link : Sorted) Values.Add(MakeShared<FJsonValueString>(Link));
            Row->SetArrayField(TEXT("links"), Values);
        }
        Pins.Add(MakeShared<FJsonValueObject>(Row));
    }
    State->SetArrayField(TEXT("nodes"), Nodes);
    State->SetArrayField(TEXT("pins"), Pins);
    return State;
}

void HashEditableDefaults(FHash& Hash, const UObject* Object)
{
    Hash.Add(Object ? Object->GetClass()->GetPathName() : FString());
    if (!Object) return;
    TArray<FProperty*> Properties;
    for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
        if (It->HasAnyPropertyFlags(CPF_Edit | CPF_BlueprintVisible) &&
            !It->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient | CPF_NonPIEDuplicateTransient | CPF_Deprecated | CPF_SkipSerialization))
            Properties.Add(*It);
    Properties.Sort([](const FProperty& A, const FProperty& B) { return A.GetName() < B.GetName(); });
    for (const FProperty* Property : Properties)
    {
        FString Value;
        Property->ExportTextItem_Direct(Value, Property->ContainerPtrToValuePtr<void>(Object), nullptr,
            const_cast<UObject*>(Object), PPF_None);
        Hash.Add(Property->GetName()); Hash.Add(Value);
    }
}
FString DefaultsFingerprint(const UBlueprint* Blueprint)
{
    FHash Hash;
    for (const FBPVariableDescription& Variable : Blueprint->NewVariables)
    {
        Hash.Add(Variable.VarName.ToString()); Hash.Add(Id(Variable.VarGuid)); Hash.Add(TypeText(Variable.VarType));
        Hash.Add(Variable.DefaultValue); Hash.Add(LexToString(Variable.PropertyFlags));
        Hash.Add(Variable.RepNotifyFunc.ToString()); Hash.Add(TextIdentity(Variable.Category));
        Hash.Add(FString::FromInt(Variable.ReplicationCondition.GetValue()));
        for (const auto& Metadata : Variable.MetaDataArray)
        { Hash.Add(Metadata.DataKey.ToString()); Hash.Add(Metadata.DataValue); }
    }
    HashEditableDefaults(Hash, Blueprint->GeneratedClass ? Blueprint->GeneratedClass->GetDefaultObject(false) : nullptr);
    TArray<USCS_Node*> Components;
    if (Blueprint->SimpleConstructionScript)
    {
        Hash.Add(FString::FromInt(Blueprint->SimpleConstructionScript->GetAllNodes().Num()));
        for (USCS_Node* Component : Blueprint->SimpleConstructionScript->GetAllNodes()) if (Component) Components.Add(Component);
    }
    Components.Sort([](const USCS_Node& A, const USCS_Node& B) { return Id(A.VariableGuid) < Id(B.VariableGuid); });
    for (const USCS_Node* Component : Components) if (Component)
    {
        Hash.Add(Id(Component->VariableGuid)); Hash.Add(Component->GetVariableName().ToString());
        Hash.Add(GetPathNameSafe(Component->ComponentClass));
        const USCS_Node* Parent = Blueprint->SimpleConstructionScript->FindParentNode(const_cast<USCS_Node*>(Component));
        Hash.Add(Parent ? Id(Parent->VariableGuid) : FString());
        HashEditableDefaults(Hash, Component->ComponentTemplate);
    }
    return Hash.Finish();
}

// Hash every untouched node identity, pin default, and link topology. Only the
// exact planned fields are excluded, including other fields on targeted nodes.
TMap<FString, FString> Preservation(const UBlueprint* Blueprint, const FPlan& Plan)
{
    TMap<FString, FString> Result;
    TArray<UEdGraph*> Graphs; Blueprint->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs)
    {
        FHash Hash; Hash.Add(Graph->GetClass()->GetPathName()); Hash.Add(Graph->GetPathName());
        Hash.Add(Graph->GetSchema() ? Graph->GetSchema()->GetClass()->GetPathName() : FString());
        TArray<UEdGraphNode*> Nodes;
        for (UEdGraphNode* Node : Graph->Nodes) if (Node) Nodes.Add(Node);
        Nodes.Sort([](const UEdGraphNode& A, const UEdGraphNode& B) { return Id(A.NodeGuid) + A.GetPathName() < Id(B.NodeGuid) + B.GetPathName(); });
        Hash.Add(FString::FromInt(Graph->Nodes.Num()));
        for (UEdGraphNode* Node : Nodes)
        {
            Hash.Add(Id(Node->NodeGuid)); Hash.Add(Node->GetClass()->GetPathName()); Hash.Add(NodeIdentity(Node)); Hash.Add(Node->NodeComment);
            const FNodeScope* NodeScope = Graph == Plan.Graph.Get() ? Plan.Nodes.Find(Id(Node->NodeGuid)) : nullptr;
            if (!NodeScope || !NodeScope->bMove)
            { Hash.Add(FString::FromInt(Node->NodePosX)); Hash.Add(FString::FromInt(Node->NodePosY)); }
            Hash.Add(FString::FromInt(Node->Pins.Num()));
            for (UEdGraphPin* Pin : Node->Pins)
            {
                if (!Pin) { Hash.Add(TEXT("null-pin")); continue; }
                const FPinScope* PinScope = Graph == Plan.Graph.Get() ? Plan.Pins.Find(PinKey(Pin)) : nullptr;
                Hash.Add(Id(Pin->PinId)); Hash.Add(Pin->PinName.ToString()); Hash.Add(FString::FromInt(Pin->Direction));
                if (!PinScope || !PinScope->bDefault)
                {
                    Hash.Add(TypeText(Pin->PinType)); Hash.Add(Pin->DefaultValue);
                    Hash.Add(GetPathNameSafe(Pin->DefaultObject)); Hash.Add(TextIdentity(Pin->DefaultTextValue));
                }
                if (!PinScope || !PinScope->bLinks)
                {
                    TArray<FString> Links;
                    for (UEdGraphPin* Link : Pin->LinkedTo) Links.Add(Link ? PinKey(Link) : TEXT("null-link"));
                    Links.Sort(); Hash.Add(FString::FromInt(Links.Num()));
                    for (const FString& Link : Links) Hash.Add(Link);
                }
            }
        }
        Result.Add(Graph->GetPathName(), Hash.Finish());
    }
    Result.Add(TEXT("$blueprint_variables_cdo_and_own_scs_defaults"), DefaultsFingerprint(Blueprint));
    return Result;
}
bool SameDigests(const TMap<FString, FString>& A, const TMap<FString, FString>& B)
{
    if (A.Num() != B.Num()) return false;
    for (const auto& Pair : A) if (Pair.Value.IsEmpty() || !B.Contains(Pair.Key) || B[Pair.Key] != Pair.Value) return false;
    return true;
}

bool DiskFiles(const FString& AssetPath, TArray<FDiskFile>& Out)
{
    Out.Empty();
    FString Main = FPaths::ConvertRelativePathToFull(FPackageName::LongPackageNameToFilename(AssetPath, FPackageName::GetAssetPackageExtension()));
    const FString Base = FPaths::GetPath(Main) / FPaths::GetBaseFilename(Main);
    if (!IFileManager::Get().FileExists(*Main)) return false;
    TArray<FString> Candidates{Main};
    for (EPackageExtension Extension : {EPackageExtension::Exports, EPackageExtension::BulkDataDefault,
        EPackageExtension::BulkDataOptional, EPackageExtension::BulkDataMemoryMapped, EPackageExtension::PayloadSidecar})
        Candidates.Add(Base + LexToString(Extension));
    for (const FString& Path : Candidates)
    {
        if (!IFileManager::Get().FileExists(*Path)) continue;
        FDiskFile File; File.Path = Path; File.RelativePath = Path;
        if (!FPaths::IsUnderDirectory(Path, FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir())) ||
            !SafePath(Path) || !FPaths::MakePathRelativeTo(File.RelativePath, *FPaths::ConvertRelativePathToFull(FPaths::ProjectDir())) ||
            File.RelativePath.Contains(TEXT("..")) || !FileHash(Path, File.Sha256)) return false;
        Out.Add(File);
    }
    return !Out.IsEmpty();
}
JObject FilesJson(const TArray<FDiskFile>& Files)
{
    auto Result = MakeShared<FJsonObject>();
    for (const FDiskFile& File : Files) Result->SetStringField(File.RelativePath, File.Sha256);
    return Result;
}
FString JournalRoot(const FPlan& Plan)
{ return FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("MajesticForge/BlueprintJournals") / Plan.PreviewId); }
bool Backup(const FPlan& Plan)
{
    const FString Root = JournalRoot(Plan);
    if (IFileManager::Get().DirectoryExists(*Root) || !PrivateDirectory(Root)) return false;
    for (const FDiskFile& File : Plan.Files)
    {
        const FString Destination = Root / TEXT("OriginalPackage") / File.RelativePath;
        if (!FPaths::IsUnderDirectory(Destination, Root) || !SafePath(Destination) ||
            !IFileManager::Get().MakeDirectory(*FPaths::GetPath(Destination), true) ||
            IFileManager::Get().Copy(*Destination, *File.Path, false, false) != COPY_OK) return false;
        FString SourceHash, BackupHash;
        if (!FileHash(File.Path, SourceHash) || !FileHash(Destination, BackupHash) ||
            SourceHash != File.Sha256 || BackupHash != File.Sha256) return false;
    }
    return true;
}
bool Compile(UBlueprint* Blueprint, FCompilerResultsLog& Log)
{
    FKismetEditorUtilities::CompileBlueprint(Blueprint, EBlueprintCompileOptions::SkipSave, &Log);
    return Log.NumErrors == 0 && Blueprint->Status != BS_Error;
}

bool FixedPinAdapter(const UEdGraphNode* Node)
{
    static const TSet<FString> Classes{
        TEXT("/Script/BlueprintGraph.K2Node_IfThenElse"), TEXT("/Script/BlueprintGraph.K2Node_ExecutionSequence"),
        TEXT("/Script/BlueprintGraph.K2Node_Event"), TEXT("/Script/BlueprintGraph.K2Node_CustomEvent"),
        TEXT("/Script/BlueprintGraph.K2Node_VariableGet"), TEXT("/Script/BlueprintGraph.K2Node_VariableSet"),
        TEXT("/Script/BlueprintGraph.K2Node_FunctionEntry"), TEXT("/Script/BlueprintGraph.K2Node_FunctionResult"),
        TEXT("/Script/BlueprintGraph.K2Node_Tunnel")};
    if (Classes.Contains(Node->GetClass()->GetPathName())) return true;
    const auto* Call = Cast<UK2Node_CallFunction>(Node);
    const UFunction* Function = Call ? Call->GetTargetFunction() : nullptr;
    return Node->GetClass() == UK2Node_CallFunction::StaticClass() && Function &&
        !Function->HasMetaData(TEXT("CustomThunk")) && !Function->HasMetaData(TEXT("DeterminesOutputType")) &&
        !Function->HasMetaData(TEXT("ArrayParm")) && !Function->HasMetaData(TEXT("CustomStructureParam"));
}
bool PrimitiveDefault(const UEdGraphPin* Pin)
{
    const FName Category = Pin->PinType.PinCategory;
    return Pin->Direction == EGPD_Input && !Pin->bOrphanedPin && !Pin->bDefaultValueIsIgnored &&
        Pin->PinType.ContainerType == EPinContainerType::None && !Pin->PinType.bIsReference &&
        (Category == UEdGraphSchema_K2::PC_Boolean || Category == UEdGraphSchema_K2::PC_Int ||
         Category == UEdGraphSchema_K2::PC_Int64 || Category == UEdGraphSchema_K2::PC_Real ||
         Category == UEdGraphSchema_K2::PC_String || Category == UEdGraphSchema_K2::PC_Name);
}
void Simulate(FPlan& Plan, const FOperation& Op)
{
    if (Op.Kind == TEXT("move_node"))
    { auto& Node = Plan.Nodes[Op.NodeKey]; Node.AfterX = Op.X; Node.AfterY = Op.Y; }
    else if (Op.Kind == TEXT("set_pin_default"))
    {
        auto& Pin = Plan.Pins[Op.Pin]; Pin.AfterValue = Op.Value;
        if (Pin.AfterType.PinCategory == UEdGraphSchema_K2::PC_Real) Pin.AfterType.bSerializeAsSinglePrecisionFloat = false;
    }
    else if (Op.Kind == TEXT("connect_pins"))
    { Plan.Pins[Op.Pin].AfterLinks.Add(Op.OtherPin); Plan.Pins[Op.OtherPin].AfterLinks.Add(Op.Pin); }
    else
    { Plan.Pins[Op.Pin].AfterLinks.Remove(Op.OtherPin); Plan.Pins[Op.OtherPin].AfterLinks.Remove(Op.Pin); }
}
bool ApplyOperation(FPlan& Plan, const FOperation& Op, bool bUndo)
{
    const UEdGraphSchema* Schema = Plan.Graph->GetSchema();
    if (Op.Kind == TEXT("move_node"))
    {
        auto& Scope = Plan.Nodes[Op.NodeKey]; UEdGraphNode* Node = Scope.Node.Get();
        if (!Node) return false;
        Node->NodePosX = bUndo ? Scope.BeforeX : Op.X; Node->NodePosY = bUndo ? Scope.BeforeY : Op.Y;
        return true;
    }
    UEdGraphPin* Pin = ResolvePin(Plan, Op.Pin);
    if (!Pin) return false;
    if (Op.Kind == TEXT("set_pin_default"))
    {
        const auto& Scope = Plan.Pins[Op.Pin];
        Schema->TrySetDefaultValue(*Pin, bUndo ? Scope.BeforeValue : Op.Value, true);
        Pin = ResolvePin(Plan, Op.Pin);
        if (bUndo && Pin) Pin->PinType.bSerializeAsSinglePrecisionFloat = Scope.BeforeType.bSerializeAsSinglePrecisionFloat;
        return Pin != nullptr;
    }
    UEdGraphPin* Other = ResolvePin(Plan, Op.OtherPin);
    if (!Other) return false;
    const bool bConnect = (Op.Kind == TEXT("connect_pins")) != bUndo;
    if (bConnect)
    {
        if (Pin->LinkedTo.Contains(Other) || Schema->CanCreateConnection(Pin, Other).Response != CONNECT_RESPONSE_MAKE) return false;
        return Schema->TryCreateConnection(Pin, Other) && Pin->LinkedTo.Contains(Other) && Other->LinkedTo.Contains(Pin);
    }
    if (!Pin->LinkedTo.Contains(Other) || !Other->LinkedTo.Contains(Pin)) return false;
    Schema->BreakSinglePinLink(Pin, Other);
    return !Pin->LinkedTo.Contains(Other) && !Other->LinkedTo.Contains(Pin);
}
void Stages(const JObject& Data, bool bApplied, bool bCompiled, bool bCompileSuccess)
{
    auto State = MakeShared<FJsonObject>();
    State->SetBoolField(TEXT("preview_generated"), true);
    State->SetBoolField(TEXT("apply_completed_in_memory"), bApplied);
    State->SetBoolField(TEXT("compilation_completed"), bCompiled);
    State->SetBoolField(TEXT("compilation_success"), bCompileSuccess);
    State->SetBoolField(TEXT("saved_to_disk"), false);
    State->SetBoolField(TEXT("independent_reload_verified"), false);
    State->SetBoolField(TEXT("runtime_behavior_verified"), false);
    Data->SetObjectField(TEXT("stages"), State);
}
}

bool FForgeBlueprintPatches::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message)
{
    using namespace ForgeBlueprintPatches;
    auto Fail = [&Code, &Message](const TCHAR* ErrorCode, const TCHAR* ErrorMessage)
    { Code = ErrorCode; Message = ErrorMessage; return false; };
    if (!IsInGameThread() || !GEditor || !GEditor->GetEditorWorldContext().World() || GEditor->PlayWorld)
        return Fail(TEXT("invalid_context"), TEXT("An idle Unreal Editor game thread is required."));
    if (!FHash().Valid()) return Fail(TEXT("unsupported_platform"), TEXT("Verified SHA-256 backup support is unavailable on this platform."));
    const double Now = FPlatformTime::Seconds();
    for (auto It = Plans.CreateIterator(); It; ++It) if (It.Value()->Expires <= Now || !It.Value()->Blueprint.IsValid()) It.RemoveCurrent();

    if (Command == TEXT("blueprint_patch_preview"))
    {
        const TSharedPtr<FJsonObject>* RequestPtr = nullptr;
        if (Args->Values.Num() != 1 || !Args->TryGetObjectField(TEXT("request"), RequestPtr))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected one typed graph patch request."));
        const JObject Request = (*RequestPtr).ToSharedRef();
        const TArray<TSharedPtr<FJsonValue>>* Operations = nullptr;
        const FString AssetPath = Text(Request, TEXT("asset_path")), GraphName = Text(Request, TEXT("graph_name"));
        if (!Fields(Request, {TEXT("asset_path"), TEXT("graph_name"), TEXT("operations")}) ||
            AssetPath.Len() > 240 || !AssetPath.StartsWith(TEXT("/Game/")) || AssetPath.Contains(TEXT(".")) ||
            !FPackageName::IsValidLongPackageName(AssetPath) || GraphName.IsEmpty() || GraphName.Len() > 128 ||
            !Request->TryGetArrayField(TEXT("operations"), Operations) || Operations->IsEmpty() || Operations->Num() > MaxOperations)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected an exact /Game package, graph name and 1-32 typed operations."));
        UBlueprint* Blueprint = LoadObject<UBlueprint>(nullptr, *(AssetPath + TEXT(".") + FPackageName::GetLongPackageAssetName(AssetPath)));
        if (!Blueprint || Blueprint->GetOutermost()->GetName() != AssetPath)
            return Fail(TEXT("asset_not_found"), TEXT("The exact Blueprint package was not found."));
        if (Blueprint->BlueprintType != BPTYPE_Normal ||
            (Blueprint->Status != BS_UpToDate && Blueprint->Status != BS_UpToDateWithWarnings))
            return Fail(TEXT("unsupported_blueprint"), TEXT("This adapter requires a normal Blueprint with a compiled baseline."));
        if (Blueprint->GetOutermost()->IsDirty())
            return Fail(TEXT("dirty_blueprint"), TEXT("The target package is dirty. Stop for the owner's save/preservation decision."));
        TArray<UEdGraph*> Graphs; Blueprint->GetAllGraphs(Graphs);
        UEdGraph* Graph = nullptr;
        for (UEdGraph* Candidate : Graphs) if (Candidate && Candidate->GetName() == GraphName)
        { if (Graph) return Fail(TEXT("ambiguous_graph"), TEXT("The graph name is not unique.")); Graph = Candidate; }
        if (!Graph) return Fail(TEXT("graph_not_found"), TEXT("The exact graph was not found."));
        if (Graph->GetClass() != UEdGraph::StaticClass() || !Graph->GetSchema() || Graph->GetSchema()->GetClass() != UEdGraphSchema_K2::StaticClass())
            return Fail(TEXT("unsupported_graph_adapter"), TEXT("This adapter supports the ordinary K2 schema only."));
        const auto* Schema = CastChecked<UEdGraphSchema_K2>(Graph->GetSchema());
        auto Plan = MakeShared<FPlan>();
        Plan->Blueprint = Blueprint; Plan->Graph = Graph; Plan->AssetPath = AssetPath;
        Plan->GraphName = GraphName; Plan->GraphPath = Graph->GetPathName();
        Plan->WorldPath = GEditor->GetEditorWorldContext().World()->GetPathName();
        Plan->ProjectFile = FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath());
        Plan->PreviewId = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        Plan->Expires = Now + 600; Plan->Request = Request;
        if (!DiskFiles(AssetPath, Plan->Files))
            return Fail(TEXT("package_backup_unavailable"), TEXT("A complete existing /Game package and SHA-256 file inventory are required before editing."));

        auto CaptureNode = [&](const FString& GuidText) -> FString
        {
            FGuid NodeGuid;
            if (!Guid(GuidText, NodeGuid)) return FString();
            const FString Key = Id(NodeGuid);
            if (Plan->Nodes.Contains(Key)) return Key;
            UEdGraphNode* Node = FindNode(Graph, NodeGuid);
            if (!Node) return FString();
            FNodeScope Scope; Scope.Node = Node; Scope.Guid = NodeGuid; Scope.ClassPath = Node->GetClass()->GetPathName();
            Scope.Identity = NodeIdentity(Node);
            Scope.BeforeX = Scope.AfterX = Node->NodePosX; Scope.BeforeY = Scope.AfterY = Node->NodePosY;
            Plan->Nodes.Add(Key, MoveTemp(Scope)); return Key;
        };
        auto CapturePin = [&](const FString& NodeGuidText, const FString& PinGuidText) -> FString
        {
            const FString NodeKey = CaptureNode(NodeGuidText);
            FGuid PinGuid;
            if (NodeKey.IsEmpty() || !Guid(PinGuidText, PinGuid)) return FString();
            const FString Key = NodeKey + TEXT(":") + Id(PinGuid);
            if (Plan->Pins.Contains(Key)) return Key;
            if (Plan->Pins.Num() >= MaxScopePins) return FString();
            UEdGraphNode* Node = Plan->Nodes[NodeKey].Node.Get();
            UEdGraphPin* Pin = Node->FindPinById(PinGuid);
            int32 Count = 0; for (UEdGraphPin* Candidate : Node->Pins) if (Candidate && Candidate->PinId == PinGuid) ++Count;
            if (!Pin || Count != 1 || Pin->bOrphanedPin || !FixedPinAdapter(Node)) return FString();
            FPinScope Scope; Scope.NodeKey = NodeKey; Scope.Guid = PinGuid;
            Scope.Name = Pin->PinName; Scope.Direction = Pin->Direction; Scope.bDefaultIgnored = Pin->bDefaultValueIsIgnored;
            Scope.BeforeType = Scope.AfterType = Pin->PinType;
            Scope.BeforeValue = Scope.AfterValue = Pin->DefaultValue;
            Scope.ObjectPath = GetPathNameSafe(Pin->DefaultObject); Scope.TextValue = TextIdentity(Pin->DefaultTextValue);
            if (!LinkSet(Pin, Scope.BeforeLinks)) return FString();
            Scope.AfterLinks = Scope.BeforeLinks;
            Plan->Pins.Add(Key, MoveTemp(Scope)); return Key;
        };

        for (const auto& Value : *Operations)
        {
            if (!Value || Value->Type != EJson::Object) return Fail(TEXT("invalid_arguments"), TEXT("Every operation must be a typed object."));
            const JObject Op = Value->AsObject().ToSharedRef();
            FOperation Native; Native.Kind = Text(Op, TEXT("op"));
            if (Native.Kind == TEXT("move_node"))
            {
                double X = 0, Y = 0;
                Native.NodeKey = CaptureNode(Text(Op, TEXT("node_guid")));
                if (!Fields(Op, {TEXT("op"), TEXT("node_guid"), TEXT("x"), TEXT("y")}) || Op->Values.Num() != 4 ||
                    Native.NodeKey.IsEmpty() || !Op->TryGetNumberField(TEXT("x"), X) || !Op->TryGetNumberField(TEXT("y"), Y) ||
                    !FMath::IsFinite(X) || !FMath::IsFinite(Y) || FMath::Abs(X) > 100000 || FMath::Abs(Y) > 100000 ||
                    FMath::FloorToDouble(X) != X || FMath::FloorToDouble(Y) != Y || Plan->Nodes[Native.NodeKey].bMove)
                    return Fail(TEXT("invalid_move"), TEXT("Move needs a unique NodeGuid and one bounded integer position change."));
                Plan->Nodes[Native.NodeKey].bMove = true; Native.X = static_cast<int32>(X); Native.Y = static_cast<int32>(Y);
                UEdGraphNode* Node = Plan->Nodes[Native.NodeKey].Node.Get();
                const FString Class = Node->GetClass()->GetPathName();
                if (!FixedPinAdapter(Node) && Class != TEXT("/Script/BlueprintGraph.K2Node_Knot") &&
                    Class != TEXT("/Script/BlueprintGraph.K2Node_Self") && Class != TEXT("/Script/UnrealEd.EdGraphNode_Comment"))
                    return Fail(TEXT("unsupported_node_adapter"), TEXT("Moving this node class requires a dedicated scoped adapter."));
                if (Native.X == Plan->Nodes[Native.NodeKey].BeforeX && Native.Y == Plan->Nodes[Native.NodeKey].BeforeY)
                    return Fail(TEXT("no_change"), TEXT("The requested node position already matches."));
            }
            else if (Native.Kind == TEXT("set_pin_default"))
            {
                if (!Fields(Op, {TEXT("op"), TEXT("node_guid"), TEXT("pin_id"), TEXT("value")}) || Op->Values.Num() != 4 ||
                    !Op->TryGetStringField(TEXT("value"), Native.Value) || Native.Value.Len() > 4096)
                    return Fail(TEXT("invalid_arguments"), TEXT("Pin default needs exact node/pin GUIDs and a bounded string value."));
                for (TCHAR Character : Native.Value)
                    if (Character < 32 && Character != TEXT('\n') && Character != TEXT('\r') && Character != TEXT('\t'))
                        return Fail(TEXT("invalid_pin_default"), TEXT("Control characters other than whitespace are not accepted in pin defaults."));
                Native.Pin = CapturePin(Text(Op, TEXT("node_guid")), Text(Op, TEXT("pin_id")));
                UEdGraphPin* Pin = Native.Pin.IsEmpty() ? nullptr : ResolvePin(*Plan, Native.Pin);
                if (!Pin || !PrimitiveDefault(Pin) || Plan->Pins[Native.Pin].bDefault ||
                    !Plan->Pins[Native.Pin].AfterLinks.IsEmpty() || Pin->DefaultObject ||
                    TextIdentity(Pin->DefaultTextValue) != TextIdentity(FText::GetEmpty()))
                    return Fail(TEXT("unsupported_pin_default"), TEXT("This adapter supports one unlinked primitive input default with stable IDs and no object/text state."));
                TObjectPtr<UObject> Object = nullptr; FText TextValue; FString Normalized;
                Schema->GetPinDefaultValuesFromString(Pin->PinType, Pin->GetOwningNode(), Native.Value, Normalized, Object, TextValue, false);
                if (Object || !TextValue.IsEmpty() || !Schema->IsPinDefaultValid(Pin, Normalized, Object, TextValue).IsEmpty())
                    return Fail(TEXT("invalid_pin_default"), TEXT("The proposed default failed native K2 schema validation."));
                if (Normalized == Pin->DefaultValue) return Fail(TEXT("no_change"), TEXT("The requested pin default already matches."));
                Native.Value = Normalized; Plan->Pins[Native.Pin].bDefault = true; Plan->Pins[Native.Pin].bLinks = true;
            }
            else if (Native.Kind == TEXT("connect_pins") || Native.Kind == TEXT("disconnect_pins"))
            {
                if (!Fields(Op, {TEXT("op"), TEXT("from_node_guid"), TEXT("from_pin_id"), TEXT("to_node_guid"), TEXT("to_pin_id")}) || Op->Values.Num() != 5)
                    return Fail(TEXT("invalid_arguments"), TEXT("A link operation requires exact node and pin GUIDs."));
                Native.Pin = CapturePin(Text(Op, TEXT("from_node_guid")), Text(Op, TEXT("from_pin_id")));
                Native.OtherPin = CapturePin(Text(Op, TEXT("to_node_guid")), Text(Op, TEXT("to_pin_id")));
                UEdGraphPin* From = Native.Pin.IsEmpty() ? nullptr : ResolvePin(*Plan, Native.Pin);
                UEdGraphPin* To = Native.OtherPin.IsEmpty() ? nullptr : ResolvePin(*Plan, Native.OtherPin);
                if (!From || !To || From->Direction != EGPD_Output || To->Direction != EGPD_Input || From == To ||
                    From->PinType.PinCategory == UEdGraphSchema_K2::PC_Wildcard || To->PinType.PinCategory == UEdGraphSchema_K2::PC_Wildcard)
                    return Fail(TEXT("unsupported_pin_link"), TEXT("Resolve fixed-type pins in a supported native K2 node adapter."));
                auto& FromScope = Plan->Pins[Native.Pin]; auto& ToScope = Plan->Pins[Native.OtherPin];
                FromScope.bLinks = ToScope.bLinks = true;
                const bool bLinked = FromScope.AfterLinks.Contains(Native.OtherPin) && ToScope.AfterLinks.Contains(Native.Pin);
                if (Native.Kind == TEXT("disconnect_pins"))
                { if (!bLinked) return Fail(TEXT("link_not_found"), TEXT("The exact link is absent from the proposed operation sequence.")); }
                else
                {
                    if (bLinked) return Fail(TEXT("link_already_exists"), TEXT("The exact link already exists."));
                    if ((From->PinType.PinCategory == UEdGraphSchema_K2::PC_Exec && !FromScope.AfterLinks.IsEmpty()) ||
                        (To->PinType.PinCategory != UEdGraphSchema_K2::PC_Exec && !ToScope.AfterLinks.IsEmpty()))
                        return Fail(TEXT("explicit_disconnect_required"), TEXT("Existing links must be explicitly disconnected earlier in the patch; replacement is never implicit."));
                    const auto Response = Schema->CanCreateConnection(From, To).Response;
                    if (Response != CONNECT_RESPONSE_MAKE && Response != CONNECT_RESPONSE_BREAK_OTHERS_A &&
                        Response != CONNECT_RESPONSE_BREAK_OTHERS_B && Response != CONNECT_RESPONSE_BREAK_OTHERS_AB)
                        return Fail(TEXT("incompatible_pins"), TEXT("Native schema rejected the connection or requires an unsupported conversion/promotion node."));
                }
            }
            else return Fail(TEXT("unsupported_patch_operation"), TEXT("This scoped adapter currently supports move/default/connect/disconnect only."));
            Simulate(*Plan, Native); Plan->Operations.Add(MoveTemp(Native));
        }
        bool bValid = false;
        Plan->BeforeState = Json(ScopeState(*Plan, false, false, bValid));
        if (!bValid || Utf8Size(Plan->BeforeState) > 128 * 1024 ||
            Utf8Size(Json(ScopeState(*Plan, false, true, bValid))) > 128 * 1024)
            return Fail(TEXT("target_scope_too_large"), TEXT("The targeted before-state exceeds its explicit bound; unrelated graph size is not limited."));
        FPlan Simulation = *Plan;
        for (auto& Pair : Simulation.Nodes) { Pair.Value.AfterX = Pair.Value.BeforeX; Pair.Value.AfterY = Pair.Value.BeforeY; }
        for (auto& Pair : Simulation.Pins)
        { Pair.Value.AfterType = Pair.Value.BeforeType; Pair.Value.AfterValue = Pair.Value.BeforeValue; Pair.Value.AfterLinks = Pair.Value.BeforeLinks; }
        for (const auto& Op : Simulation.Operations)
        {
            Simulate(Simulation, Op); Plan->PrefixDigests.Add(Digest(Json(ScopeState(Simulation, false, true, bValid))));
            if (!bValid || Plan->PrefixDigests.Last().IsEmpty())
                return Fail(TEXT("semantic_hash_failed"), TEXT("The proposed scope revisions could not be hashed."));
        }
        if (!bValid || Digest(Json(ScopeState(*Plan, true, false, bValid))) != Digest(Plan->BeforeState))
            return Fail(TEXT("unstable_scope"), TEXT("The live target state could not be verified without mutation."));
        if (Plans.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending graph patch previews."));
        Plans.Add(Plan->PreviewId, Plan);
        Data->SetStringField(TEXT("preview_id"), Plan->PreviewId);
        Data->SetStringField(TEXT("asset_path"), AssetPath); Data->SetStringField(TEXT("graph_path"), Plan->GraphPath);
        Data->SetObjectField(TEXT("request"), Request);
        Data->SetObjectField(TEXT("before"), ScopeState(*Plan, false, false, bValid));
        Data->SetObjectField(TEXT("expected_after"), ScopeState(*Plan, false, true, bValid));
        Data->SetStringField(TEXT("relevant_preconditions_sha256"), Digest(Plan->BeforeState));
        Data->SetObjectField(TEXT("original_package_files_sha256"), FilesJson(Plan->Files));
        Data->SetStringField(TEXT("backup_location"), JournalRoot(*Plan) / TEXT("OriginalPackage"));
        Data->SetStringField(TEXT("adapter"), TEXT("normal_k2_existing_graph_primitives"));
        Data->SetBoolField(TEXT("package_dirty_before"), false);
        Data->SetNumberField(TEXT("target_node_count"), Plan->Nodes.Num()); Data->SetNumberField(TEXT("target_pin_count"), Plan->Pins.Num());
        Data->SetNumberField(TEXT("expires_in_seconds"), 600);
        Data->SetArrayField(TEXT("new_objects"), {}); Data->SetArrayField(TEXT("removed_objects"), {});
        Data->SetStringField(TEXT("compile_risk"), TEXT("Compilation may reinstance dependent classes/actors. Untouched graph identities, defaults and topology are checked after apply and after any safe rollback."));
        Data->SetStringField(TEXT("authorization"), TEXT("Apply requires the user's authorization for this exact reviewed asset and change set; the confirmation token is not evidence of that authorization."));
        Stages(Data, false, false, false);
        if (Utf8Size(Json(Data)) > 768 * 1024)
        { Plans.Remove(Plan->PreviewId); return Fail(TEXT("preview_response_too_large"), TEXT("The exact target preview exceeds its byte budget; reduce the targeted operation scope.")); }
        return true;
    }

    if (Command != TEXT("blueprint_patch_apply")) return Fail(TEXT("command_not_allowed"), TEXT("Unsupported graph patch command."));
    const FString PreviewId = Text(Args, TEXT("preview_id"));
    if (Args->Values.Num() != 2 || PreviewId.Len() != 32 || Text(Args, TEXT("confirmation")) != PreviewId)
        return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
    TSharedPtr<FPlan> Plan;
    if (!Plans.RemoveAndCopyValue(PreviewId, Plan) || !Plan || Plan->Expires <= Now || !Plan->Blueprint.IsValid() || !Plan->Graph.IsValid())
        return Fail(TEXT("preview_not_found"), TEXT("Preview expired, was consumed, or its target object no longer exists."));
    UBlueprint* Blueprint = Plan->Blueprint.Get();
    bool bValid = false;
    const FString Current = Json(ScopeState(*Plan, true, false, bValid));
    TArray<FDiskFile> CurrentFiles;
    if (!bValid || Current != Plan->BeforeState || Blueprint->GetOutermost()->IsDirty() ||
        Blueprint->BlueprintType != BPTYPE_Normal ||
        (Blueprint->Status != BS_UpToDate && Blueprint->Status != BS_UpToDateWithWarnings) ||
        Plan->Graph->GetClass() != UEdGraph::StaticClass() || !Plan->Graph->GetSchema() ||
        Plan->Graph->GetSchema()->GetClass() != UEdGraphSchema_K2::StaticClass() ||
        Plan->Graph->GetPathName() != Plan->GraphPath || Plan->WorldPath != GEditor->GetEditorWorldContext().World()->GetPathName() ||
        Plan->ProjectFile != FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()) ||
        !DiskFiles(Plan->AssetPath, CurrentFiles) || Json(FilesJson(CurrentFiles)) != Json(FilesJson(Plan->Files)))
        return Fail(TEXT("stale_preview"), TEXT("Target before-values, object identity, dirty state, context or original disk package changed."));
    const auto BeforePreservation = Preservation(Blueprint, *Plan);
    for (const auto& Pair : BeforePreservation) if (Pair.Value.IsEmpty())
        return Fail(TEXT("semantic_hash_failed"), TEXT("Untouched graph semantic hashes could not be recorded."));
    if (!Backup(*Plan)) return Fail(TEXT("package_backup_failed"), TEXT("Original package backup could not be created and SHA-256 verified; no graph edits performed."));
    auto Journal = MakeShared<FJsonObject>();
    Journal->SetStringField(TEXT("state"), TEXT("prepared")); Journal->SetStringField(TEXT("asset_path"), Plan->AssetPath);
    Journal->SetStringField(TEXT("graph_path"), Plan->GraphPath); Journal->SetObjectField(TEXT("request"), Plan->Request.ToSharedRef());
    Journal->SetObjectField(TEXT("before"), ScopeState(*Plan, false, false, bValid));
    Journal->SetObjectField(TEXT("expected_after"), ScopeState(*Plan, false, true, bValid));
    Journal->SetObjectField(TEXT("original_package_files_sha256"), FilesJson(Plan->Files));
    auto BeforeHashes = MakeShared<FJsonObject>();
    for (const auto& Pair : BeforePreservation) BeforeHashes->SetStringField(Pair.Key, Pair.Value);
    Journal->SetObjectField(TEXT("untouched_graph_before_sha256"), BeforeHashes);
    const FString Root = JournalRoot(*Plan);
    if (!FFileHelper::SaveStringToFile(Json(Journal), *(Root / TEXT("journal.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
        return Fail(TEXT("journal_write_failed"), TEXT("The explicit scoped before-state could not be written; no graph edits performed."));
    FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "ScopedBlueprintPatch", "ForgeMCP scoped Blueprint graph patch"));
    Blueprint->Modify(); Plan->Graph->Modify();
    for (auto& Pair : Plan->Nodes) Pair.Value.Node->Modify();
    int32 Completed = 0; bool bOperationsOk = true, bKnownScope = true;
    FString PriorDigest = Digest(Plan->BeforeState);
    for (int32 Index = 0; Index < Plan->Operations.Num(); ++Index)
    {
        const bool bOperationOk = ApplyOperation(*Plan, Plan->Operations[Index], false);
        const FString AfterDigest = Digest(Json(ScopeState(*Plan, true, false, bValid)));
        const bool bReachedExpected = bValid && AfterDigest == Plan->PrefixDigests[Index];
        if (bReachedExpected) { ++Completed; PriorDigest = AfterDigest; }
        if (!bOperationOk || !bReachedExpected)
        { bKnownScope = bValid && (bReachedExpected || AfterDigest == PriorDigest); bOperationsOk = false; break; }
    }
    FCompilerResultsLog Compiler;
    bool bCompileAttempted = false, bCompileSuccess = false;
    if (bOperationsOk)
    {
        FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint); bCompileAttempted = true;
#if WITH_DEV_AUTOMATION_TESTS
        bCompileSuccess = TestCompiler ? TestCompiler(Blueprint, Compiler) : Compile(Blueprint, Compiler);
#else
        bCompileSuccess = Compile(Blueprint, Compiler);
#endif
    }
    auto AfterPreservation = Preservation(Blueprint, *Plan);
    const FString FinalScope = Json(ScopeState(*Plan, true, false, bValid));
    const bool bPreserved = SameDigests(BeforePreservation, AfterPreservation);
    const bool bSucceeded = bOperationsOk && bCompileSuccess && bValid && bPreserved &&
        Digest(FinalScope) == Plan->PrefixDigests.Last();
    bool bRollbackAttempted = false, bRollbackVerified = false;
    if (!bSucceeded && bKnownScope && bValid && bPreserved && Digest(FinalScope) == PriorDigest)
    {
        bRollbackAttempted = true; bRollbackVerified = true;
        for (int32 Index = Completed - 1; Index >= 0 && bRollbackVerified; --Index)
            bRollbackVerified = ApplyOperation(*Plan, Plan->Operations[Index], true);
        if (bRollbackVerified)
        {
            FCompilerResultsLog RecoveryCompiler;
            bRollbackVerified = Compile(Blueprint, RecoveryCompiler) &&
                Json(ScopeState(*Plan, true, false, bValid)) == Plan->BeforeState && bValid &&
                SameDigests(BeforePreservation, Preservation(Blueprint, *Plan));
        }
        if (bRollbackVerified) { Blueprint->GetOutermost()->SetDirtyFlag(false); Transaction.Cancel(); }
    }
    if (bSucceeded) Blueprint->MarkPackageDirty();
    Plan->Graph->NotifyGraphChanged();
    Data->SetStringField(TEXT("state"), bSucceeded ? TEXT("applied_in_memory") : bRollbackVerified ? TEXT("rolled_back") : TEXT("partial_scope_requires_owner"));
    Data->SetStringField(TEXT("asset_path"), Plan->AssetPath); Data->SetStringField(TEXT("graph_path"), Plan->GraphPath);
    Data->SetBoolField(TEXT("changes_retained_in_memory"), bSucceeded);
    Data->SetBoolField(TEXT("owner_decision_required"), !bSucceeded && !bRollbackVerified);
    Data->SetBoolField(TEXT("backup_verified"), true); Data->SetStringField(TEXT("backup_location"), Root / TEXT("OriginalPackage"));
    Data->SetStringField(TEXT("journal_path"), Root / TEXT("journal.json"));
    Data->SetBoolField(TEXT("rollback_attempted"), bRollbackAttempted); Data->SetBoolField(TEXT("rollback_verified"), bRollbackVerified);
    Data->SetBoolField(TEXT("untouched_semantics_preserved"), bPreserved);
    Data->SetNumberField(TEXT("compiler_errors"), Compiler.NumErrors); Data->SetNumberField(TEXT("compiler_warnings"), Compiler.NumWarnings);
    TArray<TSharedPtr<FJsonValue>> Diagnostics;
    for (const auto& Entry : Compiler.Messages) if (Diagnostics.Num() < 100) Diagnostics.Add(MakeShared<FJsonValueString>(Entry->ToText().ToString()));
    Data->SetArrayField(TEXT("compiler_diagnostics"), Diagnostics);
    auto Comparisons = MakeShared<FJsonObject>();
    auto ReturnedComparisons = MakeShared<FJsonObject>();
    TArray<FString> GraphKeys; BeforePreservation.GetKeys(GraphKeys); GraphKeys.Sort();
    for (const FString& GraphKey : GraphKeys)
    {
        auto Row = MakeShared<FJsonObject>(); Row->SetStringField(TEXT("before_sha256"), BeforePreservation[GraphKey]);
        Row->SetStringField(TEXT("after_sha256"), AfterPreservation.FindRef(GraphKey));
        Row->SetBoolField(TEXT("equal"), AfterPreservation.FindRef(GraphKey) == BeforePreservation[GraphKey]);
        Comparisons->SetObjectField(GraphKey, Row);
        if (ReturnedComparisons->Values.Num() < 64) ReturnedComparisons->SetObjectField(GraphKey, Row);
    }
    const FString ComparisonPath = Root / TEXT("semantic-comparisons.json");
    const bool bComparisonsSaved = FFileHelper::SaveStringToFile(Json(Comparisons), *ComparisonPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    Data->SetObjectField(TEXT("untouched_semantics"), ReturnedComparisons);
    Data->SetNumberField(TEXT("semantic_scope_count"), Comparisons->Values.Num());
    Data->SetBoolField(TEXT("semantic_summary_truncated"), Comparisons->Values.Num() > ReturnedComparisons->Values.Num());
    Data->SetStringField(TEXT("semantic_comparison_report"), ComparisonPath);
    Data->SetBoolField(TEXT("semantic_comparison_report_saved"), bComparisonsSaved);
    Stages(Data, bOperationsOk, bCompileAttempted, bCompileSuccess);
    const bool bResultSaved = FFileHelper::SaveStringToFile(Json(Data), *(Root / TEXT("result.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    Data->SetBoolField(TEXT("result_report_saved"), bResultSaved);
    Data->SetBoolField(TEXT("saved"), false);
    return true;
}
