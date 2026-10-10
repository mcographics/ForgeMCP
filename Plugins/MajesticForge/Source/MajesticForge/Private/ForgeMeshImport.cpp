#include "ForgeMeshImport.h"
#include "AssetImportTask.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionConstant3Vector.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Factories/FbxFactory.h"
#include "Factories/FbxImportUI.h"
#include "Factories/FbxStaticMeshImportData.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "MeshDescription.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/OutputDevice.h"
#include "Misc/OutputDeviceRedirector.h"
#include "Misc/ScopeLock.h"
#include "ScopedTransaction.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "StaticMeshAttributes.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/StrongObjectPtr.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

namespace
{
// Hold a read-only Windows handle while the FBX SDK reopens the artifact.
// Deny writers and deletion so the checksum remains tied to the imported bytes.
class FArtifactLease
{
#if PLATFORM_WINDOWS
    HANDLE Handle = INVALID_HANDLE_VALUE;
#endif
public:
    explicit FArtifactLease(const FString& Path)
    {
#if PLATFORM_WINDOWS
        Handle = CreateFileW(*Path, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
#endif
    }
    bool IsValid() const
    {
#if PLATFORM_WINDOWS
        return Handle != INVALID_HANDLE_VALUE;
#else
        return false;
#endif
    }
    ~FArtifactLease()
    {
#if PLATFORM_WINDOWS
        if (IsValid()) CloseHandle(Handle);
#endif
    }
};

class FImportDiagnostics : public FOutputDevice
{
    FCriticalSection Mutex;
    TArray<TSharedPtr<FJsonValue>> Entries;
public:
    FImportDiagnostics()
    {
        if (GLog)
        {
            GLog->FlushThreadedLogs();
            GLog->AddOutputDevice(this);
        }
    }
    ~FImportDiagnostics() { if (GLog) GLog->RemoveOutputDevice(this); }
    virtual bool CanBeUsedOnAnyThread() const override { return true; }
    virtual void Serialize(const TCHAR* Message, ELogVerbosity::Type Verbosity, const FName& Category) override
    {
        if (Verbosity != ELogVerbosity::Warning && Verbosity != ELogVerbosity::Error && Verbosity != ELogVerbosity::Fatal) return;
        const FString Name = Category.ToString();
        if (Name != TEXT("FBXImport") && Name != TEXT("LogFbx") && Name != TEXT("LogStaticMesh") && Name != TEXT("LogFactory")) return;
        FScopeLock Lock(&Mutex);
        if (Entries.Num() >= 32) return;
        auto Entry = MakeShared<FJsonObject>();
        Entry->SetStringField(TEXT("category"), Name);
        Entry->SetStringField(TEXT("severity"), Verbosity == ELogVerbosity::Warning ? TEXT("warning") : TEXT("error"));
        Entry->SetStringField(TEXT("message"), FString(Message).Left(1024));
        Entries.Add(MakeShared<FJsonValueObject>(Entry));
    }
    void AppendTo(const TSharedRef<FJsonObject>& Data)
    {
        // Unreal's dedicated logging thread may still hold this import's messages.
        // Flush before taking our mutex so delivery can finish without deadlock.
        if (GLog) GLog->FlushThreadedLogs();
        FScopeLock Lock(&Mutex);
        Data->SetArrayField(TEXT("native_diagnostics"), Entries);
        Data->SetBoolField(TEXT("native_diagnostics_limit_reached"), Entries.Num() >= 32);
    }
};

FString Text(const TSharedRef<FJsonObject>& Object, const TCHAR* Key)
{
    FString Value;
    Object->TryGetStringField(Key, Value);
    return Value;
}

bool Hex(const FString& Value, int32 Length)
{
    if (Value.Len() != Length) return false;
    for (TCHAR C : Value) if (!((C >= '0' && C <= '9') || (C >= 'a' && C <= 'f'))) return false;
    return true;
}

bool Hash(const TArray<uint8>& Bytes, FString& Digest)
{
#if PLATFORM_WINDOWS
    BCRYPT_ALG_HANDLE Algorithm = nullptr;
    BCRYPT_HASH_HANDLE Handle = nullptr;
    DWORD Length = 0, Copied = 0;
    TArray<uint8> Object;
    uint8 Output[32] = {};
    bool Success = false;
    if (BCryptOpenAlgorithmProvider(&Algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return false;
    if (BCryptGetProperty(Algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&Length),
        sizeof(Length), &Copied, 0) >= 0)
    {
        Object.SetNumUninitialized(Length);
        if (BCryptCreateHash(Algorithm, &Handle, Object.GetData(), Length, nullptr, 0, 0) >= 0 &&
            BCryptHashData(Handle, const_cast<PUCHAR>(Bytes.GetData()), Bytes.Num(), 0) >= 0 &&
            BCryptFinishHash(Handle, Output, sizeof(Output), 0) >= 0)
        {
            Digest = BytesToHex(Output, sizeof(Output)).ToLower();
            Success = true;
        }
    }
    if (Handle) BCryptDestroyHash(Handle);
    BCryptCloseAlgorithmProvider(Algorithm, 0);
    return Success;
#else
    return false;
#endif
}

bool SafeFile(const FString& File)
{
#if PLATFORM_WINDOWS
    FString Current = FPaths::ConvertRelativePathToFull(File);
    while (!Current.IsEmpty())
    {
        const DWORD Attributes = GetFileAttributesW(*Current);
        if (Attributes == INVALID_FILE_ATTRIBUTES || (Attributes & FILE_ATTRIBUTE_REPARSE_POINT)) return false;
        if (Current.Len() <= 3) break;
        const FString Parent = FPaths::GetPath(Current);
        if (Parent == Current) break;
        Current = Parent.Len() == 2 && Parent[1] == ':' ? Parent + TEXT("/") : Parent;
    }
    return true;
#else
    return false;
#endif
}

FString Artifact(const TSharedRef<FJsonObject>& Recipe)
{
    return FPaths::ConvertRelativePathToFull(FPaths::Combine(
        FPaths::ProjectSavedDir(), TEXT("ForgeTransfers"), Text(Recipe, TEXT("transfer_id")), TEXT("mesh.fbx")));
}

TArray<TSharedPtr<FJsonValue>> MaterialDefinitions(const TSharedRef<FJsonObject>& Recipe)
{
    const TArray<TSharedPtr<FJsonValue>>* Definitions = nullptr;
    return Recipe->TryGetArrayField(TEXT("material_definitions"), Definitions) ? *Definitions : TArray<TSharedPtr<FJsonValue>>();
}

bool ValidateMaterials(const TSharedRef<FJsonObject>& Recipe, FString& Message)
{
    auto Definitions = MaterialDefinitions(Recipe);
    if (Definitions.Num() > 32) { Message = TEXT("Use at most 32 material definitions."); return false; }
    TSet<FString> Names;
    for (int32 Index = 0; Index < Definitions.Num(); ++Index)
    {
        if (!Definitions[Index].IsValid() || Definitions[Index]->Type != EJson::Object)
        { Message = TEXT("Material definitions must be typed objects."); return false; }
        auto Definition = Definitions[Index]->AsObject().ToSharedRef();
        if (Definition->Values.Num() != 8)
        { Message = TEXT("Material definitions require exactly eight fields."); return false; }
        for (const auto& Field : Definition->Values)
        {
            const EJson Type = Field.Key == TEXT("two_sided") ? EJson::Boolean : Field.Key == TEXT("base_color") ? EJson::Array :
                (Field.Key == TEXT("index") || Field.Key == TEXT("roughness") || Field.Key == TEXT("metallic")) ? EJson::Number :
                (Field.Key == TEXT("source_name") || Field.Key == TEXT("asset_path") || Field.Key == TEXT("color_space")) ? EJson::String : EJson::None;
            if (Type == EJson::None || !Field.Value.IsValid() || Field.Value->Type != Type)
            { Message = TEXT("Material definition has unknown fields or incorrect JSON types."); return false; }
        }
        const FString Name = Text(Definition, TEXT("source_name"));
        const FString Expected = FString::Printf(TEXT("%s/M_%s_%d"),
            *FPaths::GetPath(Text(Recipe, TEXT("asset_path"))), *Text(Recipe, TEXT("transfer_id")), Index);
        double Number = 0, Roughness = 0, Metallic = 0;
        const TArray<TSharedPtr<FJsonValue>>* Color = nullptr;
        if (!Definition->TryGetNumberField(TEXT("index"), Number) || Number != Index || Name.IsEmpty() || Name.Len() > 128 ||
            Names.Contains(Name) || Text(Definition, TEXT("asset_path")) != Expected || Expected.Len() > 240 ||
            Text(Definition, TEXT("color_space")) != TEXT("scene_linear") ||
            !Definition->TryGetNumberField(TEXT("roughness"), Roughness) || !FMath::IsFinite(Roughness) || Roughness < 0 || Roughness > 1 ||
            !Definition->TryGetNumberField(TEXT("metallic"), Metallic) || !FMath::IsFinite(Metallic) || Metallic < 0 || Metallic > 1 ||
            !Definition->TryGetArrayField(TEXT("base_color"), Color) || Color->Num() != 3)
        { Message = TEXT("Material constants, slot identity or generated destination are invalid."); return false; }
        for (const auto& Component : *Color)
        {
            double Value = 0;
            if (!Component.IsValid() || Component->Type != EJson::Number || !Component->TryGetNumber(Value) || !FMath::IsFinite(Value) || Value < 0 || Value > 1)
            { Message = TEXT("Material color must contain three finite scene-linear values in 0..1."); return false; }
        }
        if (FindPackage(nullptr, *Expected) || FPackageName::DoesPackageExist(Expected))
        { Message = TEXT("A generated material destination already exists; overwrites are not supported."); return false; }
        Names.Add(Name);
    }
    return true;
}

bool SlotsMatch(UStaticMesh* Mesh, const TArray<TSharedPtr<FJsonValue>>& Definitions)
{
    if (Definitions.IsEmpty()) return true;
    if (Mesh->GetStaticMaterials().Num() != Definitions.Num()) return false;
    for (int32 Index = 0; Index < Definitions.Num(); ++Index)
        if (Mesh->GetStaticMaterials()[Index].ImportedMaterialSlotName.ToString() != Text(Definitions[Index]->AsObject().ToSharedRef(), TEXT("source_name"))) return false;
    return true;
}

UMaterial* CreateMaterial(const TSharedRef<FJsonObject>& Definition)
{
    const FString Path = Text(Definition, TEXT("asset_path"));
    UPackage* Package = CreatePackage(*Path);
    UMaterial* Material = NewObject<UMaterial>(Package, *FPackageName::GetLongPackageAssetName(Path), RF_Public | RF_Standalone | RF_Transactional);
    Material->SetShadingModel(MSM_DefaultLit);
    Material->BlendMode = BLEND_Opaque;
    Material->TwoSided = Definition->GetBoolField(TEXT("two_sided"));
    auto Color = NewObject<UMaterialExpressionConstant3Vector>(Material);
    const auto Values = Definition->GetArrayField(TEXT("base_color"));
    Color->Constant = FLinearColor(Values[0]->AsNumber(), Values[1]->AsNumber(), Values[2]->AsNumber(), 1);
    auto Roughness = NewObject<UMaterialExpressionConstant>(Material);
    Roughness->R = Definition->GetNumberField(TEXT("roughness"));
    auto Metallic = NewObject<UMaterialExpressionConstant>(Material);
    Metallic->R = Definition->GetNumberField(TEXT("metallic"));
    Material->GetExpressionCollection().AddExpression(Color);
    Material->GetExpressionCollection().AddExpression(Roughness);
    Material->GetExpressionCollection().AddExpression(Metallic);
    Material->GetEditorOnlyData()->BaseColor.Connect(0, Color);
    Material->GetEditorOnlyData()->Roughness.Connect(0, Roughness);
    Material->GetEditorOnlyData()->Metallic.Connect(0, Metallic);
    Material->PostEditChange();
    Material->MarkPackageDirty();
    return Material;
}

TSharedRef<FJsonObject> DescribeMaterial(UMaterial* Material)
{
    auto Result = MakeShared<FJsonObject>();
    const auto* Data = Material->GetEditorOnlyData();
    auto Color = Cast<UMaterialExpressionConstant3Vector>(Data->BaseColor.Expression);
    auto Roughness = Cast<UMaterialExpressionConstant>(Data->Roughness.Expression);
    auto Metallic = Cast<UMaterialExpressionConstant>(Data->Metallic.Expression);
    Result->SetStringField(TEXT("asset_path"), Material->GetPathName());
    Result->SetStringField(TEXT("model"), TEXT("pbr_constants"));
    Result->SetStringField(TEXT("color_space"), TEXT("scene_linear"));
    Result->SetBoolField(TEXT("two_sided"), Material->TwoSided);
    Result->SetBoolField(TEXT("native_graph_verified"), Color && Roughness && Metallic &&
        Material->BlendMode == BLEND_Opaque && Material->GetShadingModels().HasShadingModel(MSM_DefaultLit));
    Result->SetBoolField(TEXT("shader_compile_verified"), false);
    if (Color && Roughness && Metallic)
    {
        Result->SetArrayField(TEXT("base_color"), {MakeShared<FJsonValueNumber>(Color->Constant.R),
            MakeShared<FJsonValueNumber>(Color->Constant.G), MakeShared<FJsonValueNumber>(Color->Constant.B)});
        Result->SetNumberField(TEXT("roughness"), Roughness->R);
        Result->SetNumberField(TEXT("metallic"), Metallic->R);
    }
    return Result;
}

bool Validate(const TSharedRef<FJsonObject>& Recipe, FString& Message)
{
    const TSet<FString> Strings = {TEXT("transfer_id"), TEXT("artifact_sha256"),
        TEXT("asset_path"), TEXT("target_project_file"), TEXT("target_session_id")};
    for (const auto& Pair : Recipe->Values)
    {
        const EJson Type = Strings.Contains(Pair.Key) ? EJson::String :
            Pair.Key == TEXT("artifact_bytes") ? EJson::Number : Pair.Key == TEXT("save") ? EJson::Boolean :
            Pair.Key == TEXT("material_definitions") ? EJson::Array : EJson::None;
        if (Type == EJson::None || !Pair.Value.IsValid() || Pair.Value->Type != Type)
        { Message = TEXT("Import recipe contains unknown fields or incorrect JSON types."); return false; }
    }
    for (const FString& Field : Strings) if (!Recipe->HasField(Field))
    { Message = TEXT("Import recipe is missing required identity fields."); return false; }
    if (!Hex(Text(Recipe, TEXT("transfer_id")), 32) || !Hex(Text(Recipe, TEXT("artifact_sha256")), 64))
    { Message = TEXT("Transfer ID and SHA256 must use bounded lowercase hexadecimal."); return false; }
    double Size = 0;
    if (!Recipe->TryGetNumberField(TEXT("artifact_bytes"), Size) || Size < 23 || Size > 64 * 1024 * 1024 ||
        FMath::FloorToDouble(Size) != Size)
    { Message = TEXT("FBX size must be an integer from 23 bytes to 64 MiB."); return false; }
    const FString Project = FPaths::ConvertRelativePathToFull(Text(Recipe, TEXT("target_project_file")));
    if (!Project.Equals(FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath()), ESearchCase::IgnoreCase) ||
        Text(Recipe, TEXT("target_session_id")) != FString::Printf(TEXT("unreal-%u"), FPlatformProcess::GetCurrentProcessId()))
    { Message = TEXT("Import target does not match this project and editor session."); return false; }
    const FString Path = Text(Recipe, TEXT("asset_path"));
    if (Path.Len() > 240 || !Path.StartsWith(TEXT("/Game/")) || !FPackageName::IsValidLongPackageName(Path))
    { Message = TEXT("Import destination must be a valid /Game/ package path."); return false; }
    for (TCHAR C : Path) if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || (C >= '0' && C <= '9') || C == '_' || C == '/'))
    { Message = TEXT("Import destination contains unsupported characters."); return false; }
    if (FindPackage(nullptr, *Path) || FPackageName::DoesPackageExist(Path))
    { Message = TEXT("Import destination already exists; overwrites are not supported."); return false; }
    if (!ValidateMaterials(Recipe, Message)) return false;
    const FString File = Artifact(Recipe);
    if (IFileManager::Get().FileExists(*(FPaths::GetPath(File) / TEXT("import-report.json"))))
    { Message = TEXT("This transfer already has an import recovery record; inspect its outcome and stage a new transfer before retrying."); return false; }
    TArray<uint8> Bytes;
    FString Digest;
    static const uint8 Header[] = {'K','a','y','d','a','r','a',' ','F','B','X',' ','B','i','n','a','r','y',' ',' ',0,0x1a,0};
    if (!SafeFile(File) || IFileManager::Get().FileSize(*File) != static_cast<int64>(Size) ||
        !FFileHelper::LoadFileToArray(Bytes, *File) || Bytes.Num() != Size ||
        FMemory::Memcmp(Bytes.GetData(), Header, sizeof(Header)) != 0 || !Hash(Bytes, Digest) ||
        Digest != Text(Recipe, TEXT("artifact_sha256")) || !SafeFile(File))
    { Message = TEXT("Project-local staged FBX failed path, header, size or checksum validation."); return false; }
    return true;
}

bool Record(const TSharedRef<FJsonObject>& Recipe, const TSharedRef<FJsonObject>& Result)
{
    FString Json;
    auto Writer = TJsonWriterFactory<>::Create(&Json);
    if (!FJsonSerializer::Serialize(Result, Writer)) return false;
    const FString Directory = FPaths::GetPath(Artifact(Recipe));
    const FString Temporary = Directory / (TEXT("import-report-") + FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".tmp"));
    return FFileHelper::SaveStringToFile(Json, *Temporary, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM) &&
        IFileManager::Get().Move(*(Directory / TEXT("import-report.json")), *Temporary, true, true);
}

bool Describe(UStaticMesh* Mesh, TSharedRef<FJsonObject> Data)
{
    FMeshDescription* Description = Mesh->GetMeshDescription(0);
    if (!Description || Description->Vertices().Num() < 3 || Description->Triangles().Num() < 1) return false;
    if (Description->Vertices().Num() > 100000 || Description->Triangles().Num() > 200000) return false;
    FStaticMeshConstAttributes Attributes(*Description);
    auto Positions = Attributes.GetVertexPositions();
    FBox Bounds(ForceInit);
    TArray<TSharedPtr<FJsonValue>> Samples;
    for (FVertexID Id : Description->Vertices().GetElementIDs())
    {
        const FVector Point(Positions[Id]);
        if (Point.ContainsNaN()) return false;
        Bounds += Point;
        if (Samples.Num() < 256)
            Samples.Add(MakeShared<FJsonValueArray>(TArray<TSharedPtr<FJsonValue>>{
                MakeShared<FJsonValueNumber>(Point.X), MakeShared<FJsonValueNumber>(Point.Y), MakeShared<FJsonValueNumber>(Point.Z)}));
    }
    auto VectorJson = [](const FVector& V) { return TArray<TSharedPtr<FJsonValue>>{
        MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z)}; };
    Data->SetStringField(TEXT("asset_path"), Mesh->GetPathName());
    Data->SetStringField(TEXT("class_path"), Mesh->GetClass()->GetPathName());
    Data->SetNumberField(TEXT("vertex_count"), Description->Vertices().Num());
    Data->SetNumberField(TEXT("triangle_count"), Description->Triangles().Num());
    Data->SetArrayField(TEXT("bounds_min_cm"), VectorJson(Bounds.Min));
    Data->SetArrayField(TEXT("bounds_max_cm"), VectorJson(Bounds.Max));
    Data->SetArrayField(TEXT("vertex_positions_cm"), Samples);
    Data->SetBoolField(TEXT("vertices_truncated"), Description->Vertices().Num() > Samples.Num());
    TArray<TSharedPtr<FJsonValue>> Materials;
    for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
    {
        auto Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("slot_name"), Slot.MaterialSlotName.ToString());
        Item->SetStringField(TEXT("imported_slot_name"), Slot.ImportedMaterialSlotName.ToString());
        Materials.Add(MakeShared<FJsonValueObject>(Item));
    }
    Data->SetArrayField(TEXT("material_slots"), Materials);
    Data->SetBoolField(TEXT("material_assets_imported"), false);
    return true;
}
}

bool FForgeMeshImport::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* Error, const FString& Detail) { Code = Error; Message = Detail; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld) return Fail(TEXT("invalid_context"), TEXT("Mesh import requires the editor game thread outside PIE."));
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!World) return Fail(TEXT("invalid_context"), TEXT("No editor world is available."));
    if (Command == TEXT("mesh_info"))
    {
        FString Path;
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("asset_path"), Path) || Path.Len() > 240)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected only an exact loaded /Game/ mesh object path."));
        const FString Package = FPackageName::ObjectPathToPackageName(Path);
        if (!Package.StartsWith(TEXT("/Game/")) || !FPackageName::IsValidLongPackageName(Package) ||
            Path != Package + TEXT(".") + FPackageName::GetLongPackageAssetName(Package))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected an exact /Game/ mesh object path."));
        UStaticMesh* Mesh = FindObject<UStaticMesh>(nullptr, *Path);
        if (!Mesh) return Fail(TEXT("mesh_not_loaded"), TEXT("Mesh is not loaded; inspection never loads or reimports assets."));
        if (Mesh->GetStaticMaterials().Num() > 32 || !Describe(Mesh, Data))
            return Fail(TEXT("inspection_limit"), TEXT("Mesh exceeds bounded native inspection limits."));
        Data->SetBoolField(TEXT("loads_assets"), false);
        Data->SetBoolField(TEXT("package_dirty"), Mesh->GetPackage()->IsDirty());
        Data->SetBoolField(TEXT("disk_package_present"), FPackageName::DoesPackageExist(Package));
        TArray<TSharedPtr<FJsonValue>> Materials;
        for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
        {
            auto Item = MakeShared<FJsonObject>();
            UMaterial* Material = Cast<UMaterial>(Slot.MaterialInterface);
            if (Material) Item = DescribeMaterial(Material);
            if (Slot.MaterialInterface)
            {
                Item->SetStringField(TEXT("asset_path"), Slot.MaterialInterface->GetPathName());
                Item->SetStringField(TEXT("class_path"), Slot.MaterialInterface->GetClass()->GetPathName());
                Item->SetBoolField(TEXT("package_dirty"), Slot.MaterialInterface->GetPackage()->IsDirty());
                Item->SetBoolField(TEXT("disk_package_present"), FPackageName::DoesPackageExist(Slot.MaterialInterface->GetPackage()->GetName()));
            }
            Materials.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetArrayField(TEXT("materials"), Materials);
        Data->SetBoolField(TEXT("runtime_state_verified"), true);
        Data->SetStringField(TEXT("save_evidence_scope"), TEXT("Current dirty flag and disk package existence; not disk contents or completed save verification."));
        return true;
    }
    if (Command == TEXT("mesh_import_preview"))
    {
        const TSharedPtr<FJsonObject>* Recipe = nullptr;
        if (Args->Values.Num() != 1 || !Args->TryGetObjectField(TEXT("recipe"), Recipe))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected only a typed import recipe."));
        if (!Validate(Recipe->ToSharedRef(), Message)) return Fail(TEXT("import_rejected"), Message);
        const double Now = FPlatformTime::Seconds();
        for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= Now) It.RemoveCurrent();
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending import previews."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(Id, {*Recipe, World->GetPathName(), Now + 300});
        Data->SetStringField(TEXT("preview_id"), Id);
        Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        Data->SetObjectField(TEXT("changes"), *Recipe);
        Data->SetBoolField(TEXT("imports_material_assets"), !MaterialDefinitions(Recipe->ToSharedRef()).IsEmpty());
        Data->SetBoolField(TEXT("places_actor"), false);
        return true;
    }
    FString Id, Confirmation;
    if (Command != TEXT("mesh_import_apply") || Args->Values.Num() != 2 ||
        !Args->TryGetStringField(TEXT("preview_id"), Id) || !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Confirmation != Id)
        return Fail(TEXT("confirmation_required"), TEXT("Expected preview_id and equal confirmation."));
    FPreview Plan;
    if (!Previews.RemoveAndCopyValue(Id, Plan) || Plan.Expires <= FPlatformTime::Seconds())
        return Fail(TEXT("preview_not_found"), TEXT("Import preview expired or was consumed."));
    if (World->GetPathName() != Plan.World || !Validate(Plan.Recipe.ToSharedRef(), Message))
        return Fail(TEXT("stale_preview"), Message.IsEmpty() ? TEXT("Editor world changed.") : Message);
    auto Recipe = Plan.Recipe.ToSharedRef();
    FArtifactLease Lease(Artifact(Recipe));
    if (!Lease.IsValid() || !Validate(Recipe, Message))
        return Fail(TEXT("artifact_unavailable"), TEXT("Could not lock and revalidate the staged artifact for native import."));
    const FString PackagePath = Text(Recipe, TEXT("asset_path"));
    Data->SetStringField(TEXT("transfer_id"), Text(Recipe, TEXT("transfer_id")));
    Data->SetStringField(TEXT("target_project_file"), FPaths::GetProjectFilePath());
    Data->SetStringField(TEXT("state"), TEXT("import_started"));
    Data->SetStringField(TEXT("planned_asset_package"), PackagePath);
    TArray<TSharedPtr<FJsonValue>> PlannedMaterials;
    for (const auto& Value : MaterialDefinitions(Recipe))
        PlannedMaterials.Add(MakeShared<FJsonValueString>(Text(Value->AsObject().ToSharedRef(), TEXT("asset_path"))));
    Data->SetArrayField(TEXT("planned_material_packages"), PlannedMaterials);
    Data->SetBoolField(TEXT("saved"), false);
    Data->SetBoolField(TEXT("placed"), false);
    if (!Record(Recipe, Data)) return Fail(TEXT("report_failed"), TEXT("Import did not start because its recovery record could not be written."));
    UPackage* Package = CreatePackage(*PackagePath);
    FScopedTransaction Transaction(FText::FromString(TEXT("ForgeMCP: import new static mesh")));
    TStrongObjectPtr<UFbxFactory> FactoryOwner(NewObject<UFbxFactory>());
    TStrongObjectPtr<UAssetImportTask> TaskOwner(NewObject<UAssetImportTask>());
    UFbxFactory* Factory = FactoryOwner.Get();
    UAssetImportTask* Task = TaskOwner.Get();
    Task->bAutomated = true;
    Task->bReplaceExisting = false;
    Task->bReplaceExistingSettings = false;
    Factory->SetAssetImportTask(Task);
    Factory->SetDetectImportTypeOnImport(false);
    Factory->ImportUI->MeshTypeToImport = FBXIT_StaticMesh;
    Factory->ImportUI->bAutomatedImportShouldDetectType = false;
    Factory->ImportUI->bImportAsSkeletal = false;
    Factory->ImportUI->bImportMesh = true;
    Factory->ImportUI->bImportMaterials = false;
    Factory->ImportUI->bImportTextures = false;
    Factory->ImportUI->bOverrideFullName = true;
    Factory->ImportUI->StaticMeshImportData->bCombineMeshes = true;
    Factory->ImportUI->StaticMeshImportData->bConvertScene = true;
    Factory->ImportUI->StaticMeshImportData->bConvertSceneUnit = true;
    Factory->ImportUI->StaticMeshImportData->bForceFrontXAxis = true;
    Factory->ImportUI->StaticMeshImportData->bTransformVertexToAbsolute = true;
    bool Canceled = false;
    FImportDiagnostics Diagnostics;
    UObject* Imported = Factory->ImportObject(UStaticMesh::StaticClass(), Package,
        *FPackageName::GetLongPackageAssetName(PackagePath), RF_Public | RF_Standalone,
        Artifact(Recipe), nullptr, Canceled);
    Factory->CleanUp();
    Diagnostics.AppendTo(Data);
    UStaticMesh* Mesh = Cast<UStaticMesh>(Imported);
    const auto Definitions = MaterialDefinitions(Recipe);
    if (Canceled || !Mesh || !Describe(Mesh, Data) || !SlotsMatch(Mesh, Definitions))
    {
        Transaction.Cancel();
        if (Imported)
        {
            FAssetRegistryModule::AssetDeleted(Imported);
            Imported->ClearFlags(RF_Public | RF_Standalone);
            Imported->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
        }
        Package->SetDirtyFlag(false);
        Package->SetFlags(RF_Transient);
        Package->Rename(*(TEXT("/Temp/ForgeImportDiscard_") + FGuid::NewGuid().ToString(EGuidFormats::Digits)),
            nullptr, REN_DontCreateRedirectors | REN_NonTransactional);
        Data->SetStringField(TEXT("state"), TEXT("rolled_back"));
        Data->SetStringField(TEXT("diagnostic"), TEXT("Native import failed or produced unsupported geometry/material slots."));
    }
    else
    {
        bool Save = false;
        Recipe->TryGetBoolField(TEXT("save"), Save);
        bool Saved = false;
        bool MaterialsSaved = true;
        TArray<TSharedPtr<FJsonValue>> Materials, SavedAssets;
        for (int32 Index = 0; Index < Definitions.Num(); ++Index)
        {
            UMaterial* Material = CreateMaterial(Definitions[Index]->AsObject().ToSharedRef());
            Mesh->SetMaterial(Index, Material);
            FAssetRegistryModule::AssetCreated(Material);
            auto Description = DescribeMaterial(Material);
            Description->SetNumberField(TEXT("index"), Index);
            bool MaterialSaved = false;
            if (Save)
            {
                FSavePackageArgs Arguments;
                Arguments.TopLevelFlags = RF_Public | RF_Standalone;
                Arguments.SaveFlags = SAVE_NoError;
                const FString Filename = FPackageName::LongPackageNameToFilename(Material->GetPackage()->GetName(), FPackageName::GetAssetPackageExtension());
                MaterialSaved = UPackage::SavePackage(Material->GetPackage(), Material, *Filename, Arguments);
                MaterialsSaved &= MaterialSaved;
            }
            if (MaterialSaved) SavedAssets.Add(MakeShared<FJsonValueString>(Material->GetPathName()));
            Description->SetBoolField(TEXT("saved"), MaterialSaved);
            Materials.Add(MakeShared<FJsonValueObject>(Description));
        }
        Data->SetArrayField(TEXT("materials"), Materials);
        Data->SetBoolField(TEXT("material_assets_imported"), !Definitions.IsEmpty());
        Data->SetBoolField(TEXT("material_assets_saved"), Save && MaterialsSaved);
        if (Save && MaterialsSaved)
        {
            FSavePackageArgs SaveArgs;
            SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
            SaveArgs.SaveFlags = SAVE_NoError;
            const FString Filename = FPackageName::LongPackageNameToFilename(PackagePath, FPackageName::GetAssetPackageExtension());
            Saved = UPackage::SavePackage(Package, Mesh, *Filename, SaveArgs);
        }
        if (Saved) SavedAssets.Add(MakeShared<FJsonValueString>(Mesh->GetPathName()));
        Data->SetArrayField(TEXT("saved_assets"), SavedAssets);
        FAssetRegistryModule::AssetCreated(Mesh);
        if (!Saved) Mesh->MarkPackageDirty();
        Data->SetBoolField(TEXT("saved"), Saved);
        Data->SetStringField(TEXT("state"), Save && !Saved ? TEXT("partial") : TEXT("imported"));
        Data->SetBoolField(TEXT("cross_application_verified"), false);
        if (Save && !Saved) Data->SetStringField(TEXT("diagnostic"), MaterialsSaved ?
            TEXT("Mesh exists in memory but package save failed; inspect saved_assets before retrying.") :
            TEXT("A material save failed; mesh was not saved. Inspect saved_assets and in-memory objects before retrying."));
    }
    if (!Record(Recipe, Data))
    {
        Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
        Data->SetStringField(TEXT("diagnostic"), TEXT("Import recovery record update failed; inspect retained staging and destination before retrying."));
    }
    return true;
}
