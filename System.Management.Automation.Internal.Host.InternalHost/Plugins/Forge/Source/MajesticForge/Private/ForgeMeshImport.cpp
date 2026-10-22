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
#include "Factories/ReimportFbxStaticMeshFactory.h"
#include "EditorReimportHandler.h"
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
#include "Serialization/MemoryWriter.h"
#include "StaticMeshAttributes.h"
#include "UObject/Package.h"
#include "UObject/MetaData.h"
#include "UObject/SavePackage.h"
#include "EditorFramework/AssetImportData.h"
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

struct FPackagePart
{
    FString Source;
    FString RelativeName;
    FString Sha256;
    int64 Bytes = 0;
};

bool HashFile(const FString& Filename, FString& Digest, int64& Bytes)
{
#if PLATFORM_WINDOWS
    HANDLE File = CreateFileW(*Filename, GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN, nullptr);
    if (File == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER Size = {};
    BCRYPT_ALG_HANDLE Algorithm = nullptr;
    BCRYPT_HASH_HANDLE HashHandle = nullptr;
    DWORD ObjectLength = 0, Copied = 0;
    TArray<uint8> Object;
    uint8 Output[32] = {};
    bool Success = false;
    if (GetFileSizeEx(File, &Size) && Size.QuadPart >= 0 &&
        (GetFileAttributesW(*Filename) & FILE_ATTRIBUTE_REPARSE_POINT) == 0 &&
        BCryptOpenAlgorithmProvider(&Algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0 &&
        BCryptGetProperty(Algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&ObjectLength),
            sizeof(ObjectLength), &Copied, 0) >= 0)
    {
        Object.SetNumUninitialized(ObjectLength);
        if (BCryptCreateHash(Algorithm, &HashHandle, Object.GetData(), ObjectLength, nullptr, 0, 0) >= 0)
        {
            uint8 Buffer[1024 * 1024];
            int64 Total = 0;
            bool ReadSuccess = true;
            while (Total < Size.QuadPart)
            {
                DWORD Read = 0;
                const DWORD Wanted = static_cast<DWORD>(FMath::Min<int64>(sizeof(Buffer), Size.QuadPart - Total));
                if (!ReadFile(File, Buffer, Wanted, &Read, nullptr) || Read != Wanted ||
                    BCryptHashData(HashHandle, Buffer, Read, 0) < 0)
                { ReadSuccess = false; break; }
                Total += Read;
            }
            if (ReadSuccess && Total == Size.QuadPart && BCryptFinishHash(HashHandle, Output, sizeof(Output), 0) >= 0)
            {
                Bytes = Total;
                Digest = BytesToHex(Output, sizeof(Output)).ToLower();
                Success = true;
            }
        }
    }
    if (HashHandle) BCryptDestroyHash(HashHandle);
    if (Algorithm) BCryptCloseAlgorithmProvider(Algorithm, 0);
    CloseHandle(File);
    return Success;
#else
    return false;
#endif
}

bool PackageParts(const FString& PackagePath, TArray<FPackagePart>& Parts, FString& Fingerprint)
{
    FString AssetFilename;
    if (!FPackageName::TryConvertLongPackageNameToFilename(PackagePath, AssetFilename,
        FPackageName::GetAssetPackageExtension())) return false;
    const FString Stem = FPaths::Combine(FPaths::GetPath(AssetFilename), FPaths::GetBaseFilename(AssetFilename));
    const TArray<FString> Extensions = {TEXT("uasset"), TEXT("uexp"), TEXT("ubulk"), TEXT("uptnl")};
    TArray<uint8> Identity;
    int64 TotalBytes = 0;
    for (const FString& Extension : Extensions)
    {
        const FString Source = Stem + TEXT(".") + Extension;
        if (!IFileManager::Get().FileExists(*Source)) continue;
        if (!SafeFile(Source)) return false;
        FPackagePart Part;
        Part.Source = Source;
        Part.RelativeName = FPaths::GetCleanFilename(Source);
        if (!HashFile(Source, Part.Sha256, Part.Bytes) || Part.Bytes <= 0 ||
            Part.Bytes > 2LL * 1024 * 1024 * 1024 || TotalBytes > 2LL * 1024 * 1024 * 1024 - Part.Bytes)
            return false;
        TotalBytes += Part.Bytes;
        const FString Piece = Part.RelativeName + TEXT(":") + FString::Printf(TEXT("%lld:"), Part.Bytes) + Part.Sha256 + TEXT("\n");
        FTCHARToUTF8 Utf8(*Piece);
        Identity.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
        Parts.Add(MoveTemp(Part));
    }
    return !Parts.IsEmpty() && Hash(Identity, Fingerprint);
}

FString PartsFingerprint(const TArray<FPackagePart>& Parts)
{
    TArray<uint8> Identity;
    for (const FPackagePart& Part : Parts)
    {
        const FString Piece = Part.RelativeName + TEXT(":") + FString::Printf(TEXT("%lld:"), Part.Bytes) + Part.Sha256 + TEXT("\n");
        FTCHARToUTF8 Utf8(*Piece);
        Identity.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    }
    FString Result;
    return Hash(Identity, Result) ? Result : FString();
}

bool BackupPackage(const TArray<FPackagePart>& Parts, const FString& Directory,
    TArray<FPackagePart>& BackedUp)
{
    if (Parts.IsEmpty() || IFileManager::Get().DirectoryExists(*Directory) ||
        !SafeFile(FPaths::ProjectSavedDir()) || !IFileManager::Get().MakeDirectory(*Directory, true) || !SafeFile(Directory))
        return false;
    for (const FPackagePart& Part : Parts)
    {
        FPackagePart Copy = Part;
        Copy.Source = FPaths::Combine(Directory, Part.RelativeName);
        if (IFileManager::Get().Copy(*Copy.Source, *Part.Source, false, false) != COPY_OK || !SafeFile(Copy.Source))
            return false;
        FString Digest;
        int64 Bytes = 0;
        if (!HashFile(Copy.Source, Digest, Bytes) || Digest != Part.Sha256 || Bytes != Part.Bytes)
            return false;
        BackedUp.Add(MoveTemp(Copy));
    }
    return BackedUp.Num() == Parts.Num();
}

bool RestorePackage(const TArray<FPackagePart>& Originals, const TArray<FPackagePart>& Backups,
    const FString& PackagePath)
{
    bool Success = Originals.Num() == Backups.Num() && !Originals.IsEmpty();
    for (int32 Index = 0; Index < Backups.Num(); ++Index)
    {
        FString Digest;
        int64 Bytes = 0;
        if (!HashFile(Backups[Index].Source, Digest, Bytes) || Digest != Originals[Index].Sha256 || Bytes != Originals[Index].Bytes ||
            IFileManager::Get().Copy(*Originals[Index].Source, *Backups[Index].Source, true, true) != COPY_OK ||
            !HashFile(Originals[Index].Source, Digest, Bytes) || Digest != Originals[Index].Sha256 || Bytes != Originals[Index].Bytes)
            Success = false;
    }
    TArray<FPackagePart> Current;
    FString CurrentFingerprint;
    if (!PackageParts(PackagePath, Current, CurrentFingerprint)) return false;
    for (const FPackagePart& Part : Current)
    {
        const bool WasPresent = Originals.ContainsByPredicate([&](const FPackagePart& Original)
            { return Original.RelativeName == Part.RelativeName; });
        if (!WasPresent && !IFileManager::Get().Delete(*Part.Source, false, true, true)) Success = false;
    }
    TArray<FPackagePart> Restored;
    FString RestoredFingerprint;
    return Success && PackageParts(PackagePath, Restored, RestoredFingerprint) &&
        RestoredFingerprint == PartsFingerprint(Originals);
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

bool SlotNamesMatch(UStaticMesh* Mesh, const TSharedRef<FJsonObject>& Recipe)
{
    const TArray<TSharedPtr<FJsonValue>>* Names = nullptr;
    if (!Recipe->TryGetArrayField(TEXT("material_slot_names"), Names) || Names->Num() != Mesh->GetStaticMaterials().Num() || Names->Num() > 32)
        return false;
    TSet<FString> Unique;
    for (int32 Index = 0; Index < Names->Num(); ++Index)
    {
        FString Name;
        if (!(*Names)[Index].IsValid() || !(*Names)[Index]->TryGetString(Name) || Name.IsEmpty() || Name.Len() > 128 ||
            Unique.Contains(Name) || Mesh->GetStaticMaterials()[Index].ImportedMaterialSlotName.ToString() != Name)
            return false;
        Unique.Add(Name);
    }
    return true;
}

bool MeshRevision(UStaticMesh* Mesh, FString& Out);

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

bool Validate(const TSharedRef<FJsonObject>& Recipe, FString& Message, bool bReplacement = false)
{
    const TSet<FString> Strings = {TEXT("transfer_id"), TEXT("binding_id"), TEXT("source_snapshot_sha256"), TEXT("artifact_sha256"),
        TEXT("asset_path"), TEXT("target_project_file"), TEXT("target_session_id")};
    for (const auto& Pair : Recipe->Values)
    {
        const EJson Type = Strings.Contains(Pair.Key) ? EJson::String :
            Pair.Key == TEXT("artifact_bytes") ? EJson::Number : Pair.Key == TEXT("save") ? EJson::Boolean :
            Pair.Key == TEXT("material_definitions") ? EJson::Array :
            Pair.Key == TEXT("material_slot_names") ? EJson::Array :
            Pair.Key == TEXT("replace_existing") ? EJson::Boolean :
            (Pair.Key == TEXT("expected_target_revision_sha256") || Pair.Key == TEXT("expected_source_baseline_sha256")) ? EJson::String : EJson::None;
        if (Type == EJson::None || !Pair.Value.IsValid() || Pair.Value->Type != Type)
        { Message = TEXT("Import recipe contains unknown fields or incorrect JSON types."); return false; }
    }
    for (const FString& Field : Strings) if (!Recipe->HasField(Field))
    { Message = TEXT("Import recipe is missing required identity fields."); return false; }
    if (!Hex(Text(Recipe, TEXT("transfer_id")), 32) || !Hex(Text(Recipe, TEXT("binding_id")), 32) ||
        !Hex(Text(Recipe, TEXT("source_snapshot_sha256")), 64) || !Hex(Text(Recipe, TEXT("artifact_sha256")), 64))
    { Message = TEXT("Transfer and binding IDs and SHA256 values must use bounded lowercase hexadecimal."); return false; }
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
    const FString ObjectPath = Path + TEXT(".") + FPackageName::GetLongPackageAssetName(Path);
    UStaticMesh* Existing = FindObject<UStaticMesh>(nullptr, *ObjectPath);
    if (!bReplacement && (FindPackage(nullptr, *Path) || FPackageName::DoesPackageExist(Path)))
    { Message = TEXT("Import destination already exists; new-asset imports do not overwrite."); return false; }
    if (bReplacement)
    {
        FString Revision;
        bool ReplaceFlag = false;
        if (!Recipe->TryGetBoolField(TEXT("replace_existing"), ReplaceFlag) || !ReplaceFlag ||
            !Recipe->HasField(TEXT("expected_target_revision_sha256")) ||
            !Hex(Text(Recipe, TEXT("expected_target_revision_sha256")), 64) || !IsValid(Existing) ||
            !FPackageName::DoesPackageExist(Path) || Existing->GetOutermost()->IsDirty() ||
            !MeshRevision(Existing, Revision) || Revision != Text(Recipe, TEXT("expected_target_revision_sha256")))
        { Message = TEXT("Replacement target is unloaded, dirty, unsaved or changed since review."); return false; }
        const FString* ExistingBinding = Existing->GetPackage()->GetMetaData().FindValue(Existing, TEXT("ForgeMCP.BindingId"));
        if (!ExistingBinding || *ExistingBinding != Text(Recipe, TEXT("binding_id")))
        { Message = TEXT("Replacement requires the exact existing mesh binding ID."); return false; }
        const FString* ExistingSource = Existing->GetPackage()->GetMetaData().FindValue(Existing, TEXT("ForgeMCP.SourceSnapshot"));
        const FString* ExistingTarget = Existing->GetPackage()->GetMetaData().FindValue(Existing, TEXT("ForgeMCP.TargetSnapshot"));
        if (!Recipe->HasField(TEXT("expected_source_baseline_sha256")) ||
            !Hex(Text(Recipe, TEXT("expected_source_baseline_sha256")), 64) || !ExistingSource ||
            *ExistingSource != Text(Recipe, TEXT("expected_source_baseline_sha256")) ||
            Text(Recipe, TEXT("source_snapshot_sha256")) == *ExistingSource || !ExistingTarget || *ExistingTarget != Revision)
        { Message = TEXT("Replacement requires a new Blender revision for an existing bound mesh."); return false; }
        const TArray<TSharedPtr<FJsonValue>> Definitions = MaterialDefinitions(Recipe);
        if (!Definitions.IsEmpty() || !SlotNamesMatch(Existing, Recipe))
        { Message = TEXT("Replacement material slot identities must exactly match the existing mesh."); return false; }
    }
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

bool MeshRevision(UStaticMesh* Mesh, FString& Out)
{
    const FMeshDescription* Description = Mesh ? Mesh->GetMeshDescription(0) : nullptr;
    if (!Description || Mesh->GetStaticMaterials().Num() > 32) return false;
    FMeshDescription Copy(*Description);
    TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes);
    Copy.Serialize(Writer);
    FString Identity = FString::Printf(TEXT("%s:%s"), *Mesh->GetPathName(), *Mesh->GetLightingGuid().ToString());
    for (const FStaticMaterial& Material : Mesh->GetStaticMaterials())
        Identity += Material.MaterialSlotName.ToString() + GetPathNameSafe(Material.MaterialInterface.Get());
    FTCHARToUTF8 Utf8(*Identity);
    Bytes.Append(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    return Hash(Bytes, Out);
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
    if (Command == TEXT("mesh_replace_preview"))
    {
        FString AssetPath, BindingId, SourceSnapshot, SourceBaseline, ExpectedTargetRevision, TransferId;
        const TSet<FString> Expected = {TEXT("asset_path"), TEXT("binding_id"), TEXT("source_snapshot_sha256"),
            TEXT("source_baseline_sha256"), TEXT("target_revision_sha256"), TEXT("transfer_id"), TEXT("material_slot_names")};
        if (Args->Values.Num() != Expected.Num()) return Fail(TEXT("invalid_arguments"), TEXT("Replacement preview requires exact binding and revision identity fields."));
        for (const auto& Pair : Args->Values) if (!Expected.Contains(Pair.Key) || !Pair.Value.IsValid() ||
            (Pair.Key == TEXT("material_slot_names") ? Pair.Value->Type != EJson::Array : Pair.Value->Type != EJson::String))
            return Fail(TEXT("invalid_arguments"), TEXT("Replacement preview contains unsupported fields."));
        Args->TryGetStringField(TEXT("asset_path"), AssetPath);
        Args->TryGetStringField(TEXT("binding_id"), BindingId);
        Args->TryGetStringField(TEXT("source_snapshot_sha256"), SourceSnapshot);
        Args->TryGetStringField(TEXT("source_baseline_sha256"), SourceBaseline);
        Args->TryGetStringField(TEXT("target_revision_sha256"), ExpectedTargetRevision);
        Args->TryGetStringField(TEXT("transfer_id"), TransferId);
        const FString PackagePath = FPackageName::ObjectPathToPackageName(AssetPath);
        if (!Hex(BindingId, 32) || !Hex(SourceSnapshot, 64) || !Hex(SourceBaseline, 64) ||
            !Hex(ExpectedTargetRevision, 64) || !Hex(TransferId, 32) || !PackagePath.StartsWith(TEXT("/Game/")) ||
            !FPackageName::IsValidLongPackageName(PackagePath) || AssetPath != PackagePath + TEXT(".") + FPackageName::GetLongPackageAssetName(PackagePath))
            return Fail(TEXT("invalid_arguments"), TEXT("Replacement preview identity or exact /Game asset path is invalid."));
        UStaticMesh* Mesh = FindObject<UStaticMesh>(nullptr, *AssetPath);
        FString CurrentRevision, PackageHash;
        TArray<FPackagePart> Parts;
        const FString* StoredBinding = IsValid(Mesh) ? Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.BindingId")) : nullptr;
        const FString* StoredSource = IsValid(Mesh) ? Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.SourceSnapshot")) : nullptr;
        const FString* StoredTarget = IsValid(Mesh) ? Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.TargetSnapshot")) : nullptr;
        auto SlotRecipe = MakeShared<FJsonObject>();
        SlotRecipe->SetArrayField(TEXT("material_slot_names"), Args->GetArrayField(TEXT("material_slot_names")));
        if (!IsValid(Mesh) || Mesh->GetOutermost()->IsDirty() || !StoredBinding || *StoredBinding != BindingId ||
            !StoredSource || *StoredSource != SourceBaseline || SourceSnapshot == SourceBaseline ||
            !MeshRevision(Mesh, CurrentRevision) || CurrentRevision != ExpectedTargetRevision ||
            !StoredTarget || *StoredTarget != ExpectedTargetRevision || !PackageParts(PackagePath, Parts, PackageHash) ||
            !SlotNamesMatch(Mesh, SlotRecipe))
        {
            return Fail(TEXT("stale_replacement"), TEXT("Replacement requires an unchanged, saved target and a Blender-only change on the exact bound mesh."));
        }
        const double Now = FPlatformTime::Seconds();
        for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= Now) It.RemoveCurrent();
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending mesh previews."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        FPreview Plan;
        Plan.World = World->GetPathName(); Plan.AssetPath = AssetPath; Plan.TransferId = TransferId;
        Plan.BindingId = BindingId; Plan.SourceSnapshot = SourceSnapshot; Plan.SourceBaseline = SourceBaseline;
        Plan.TargetRevision = CurrentRevision; Plan.PackageFingerprint = PackageHash; Plan.Target = Mesh;
        Plan.bReplacement = true; Plan.Expires = Now + 300;
        Previews.Add(Id, MoveTemp(Plan));
        Data->SetStringField(TEXT("preview_id"), Id);
        Data->SetStringField(TEXT("asset_path"), AssetPath);
        Data->SetStringField(TEXT("binding_id"), BindingId);
        Data->SetStringField(TEXT("source_snapshot_sha256"), SourceSnapshot);
        Data->SetStringField(TEXT("target_revision_sha256"), CurrentRevision);
        Data->SetStringField(TEXT("package_fingerprint"), PackageHash);
        Data->SetStringField(TEXT("backup_directory"), FPaths::ConvertRelativePathToFull(FPaths::Combine(
            FPaths::ProjectSavedDir(), TEXT("ForgeMCP/Backups/MeshReplacement"), TransferId)));
        Data->SetBoolField(TEXT("backup_required"), true);
        Data->SetBoolField(TEXT("preserves_material_assignments"), true);
        TArray<TSharedPtr<FJsonValue>> MaterialAssignments;
        for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
        {
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("slot_name"), Slot.ImportedMaterialSlotName.ToString());
            Item->SetStringField(TEXT("material_path"), GetPathNameSafe(Slot.MaterialInterface.Get()));
            MaterialAssignments.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetArrayField(TEXT("material_assignments"), MaterialAssignments);
        Data->SetBoolField(TEXT("mutated"), false);
        Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        return true;
    }
    if (Command == TEXT("mesh_import_preview"))
    {
        const TSharedPtr<FJsonObject>* Recipe = nullptr;
        if (Args->Values.Num() != 1 || !Args->TryGetObjectField(TEXT("recipe"), Recipe))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected only a typed import recipe."));
        if (!Validate(Recipe->ToSharedRef(), Message, false)) return Fail(TEXT("import_rejected"), Message);
        const double Now = FPlatformTime::Seconds();
        for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= Now) It.RemoveCurrent();
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending import previews."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        FPreview Plan; Plan.Recipe = *Recipe; Plan.World = World->GetPathName(); Plan.Expires = Now + 300;
        Previews.Add(Id, MoveTemp(Plan));
        Data->SetStringField(TEXT("preview_id"), Id);
        Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        Data->SetObjectField(TEXT("changes"), *Recipe);
        Data->SetBoolField(TEXT("imports_material_assets"), !MaterialDefinitions(Recipe->ToSharedRef()).IsEmpty());
        Data->SetBoolField(TEXT("places_actor"), false);
        return true;
    }
    const bool bReplacementApply = Command == TEXT("mesh_replace_apply");
    FString Id, Confirmation;
    const TSharedPtr<FJsonObject>* ReplacementRecipe = nullptr;
    if ((Command != TEXT("mesh_import_apply") && !bReplacementApply) ||
        Args->Values.Num() != (bReplacementApply ? 3 : 2) ||
        !Args->TryGetStringField(TEXT("preview_id"), Id) || !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Confirmation != Id ||
        (bReplacementApply && !Args->TryGetObjectField(TEXT("recipe"), ReplacementRecipe)))
        return Fail(TEXT("confirmation_required"), TEXT("Expected a matching preview confirmation and the required typed recipe."));
    FPreview Plan;
    if (!Previews.RemoveAndCopyValue(Id, Plan) || Plan.Expires <= FPlatformTime::Seconds())
        return Fail(TEXT("preview_not_found"), TEXT("Import preview expired or was consumed."));
    if (Plan.bReplacement != bReplacementApply)
        return Fail(TEXT("preview_operation_mismatch"), TEXT("The preview was created for a different import operation."));
    auto Recipe = bReplacementApply ? ReplacementRecipe->ToSharedRef() : Plan.Recipe.ToSharedRef();
    if (World->GetPathName() != Plan.World || !Validate(Recipe, Message, bReplacementApply))
        return Fail(TEXT("stale_preview"), Message.IsEmpty() ? TEXT("Editor world changed.") : Message);
    if (bReplacementApply &&
        (Plan.TransferId != Text(Recipe, TEXT("transfer_id")) || Plan.BindingId != Text(Recipe, TEXT("binding_id")) ||
         Plan.SourceSnapshot != Text(Recipe, TEXT("source_snapshot_sha256")) || Plan.SourceBaseline != Text(Recipe, TEXT("expected_source_baseline_sha256")) ||
         FPackageName::ObjectPathToPackageName(Plan.AssetPath) != Text(Recipe, TEXT("asset_path")) ||
         Plan.TargetRevision != Text(Recipe, TEXT("expected_target_revision_sha256"))))
        return Fail(TEXT("stale_preview"), TEXT("Replacement recipe identity differs from the reviewed binding and revisions."));
    FArtifactLease Lease(Artifact(Recipe));
    if (!Lease.IsValid() || !Validate(Recipe, Message, bReplacementApply))
        return Fail(TEXT("artifact_unavailable"), TEXT("Could not lock and revalidate the staged artifact for native import."));
    if (bReplacementApply)
    {
        UStaticMesh* Mesh = Cast<UStaticMesh>(Plan.Target.Get());
        FString CurrentRevision, CurrentPackageFingerprint;
        TArray<FPackagePart> OriginalParts;
        const FString PackagePath = Text(Recipe, TEXT("asset_path"));
        if (!IsValid(Mesh) || Mesh->GetPathName() != Plan.AssetPath ||
            !MeshRevision(Mesh, CurrentRevision) || CurrentRevision != Plan.TargetRevision ||
            !PackageParts(PackagePath, OriginalParts, CurrentPackageFingerprint) || CurrentPackageFingerprint != Plan.PackageFingerprint)
            return Fail(TEXT("stale_preview"), TEXT("Target mesh or saved package changed after replacement review."));

        const FString BackupDirectory = FPaths::ConvertRelativePathToFull(FPaths::Combine(
            FPaths::ProjectSavedDir(), TEXT("ForgeMCP/Backups/MeshReplacement"), Plan.TransferId));
        Data->SetStringField(TEXT("transfer_id"), Plan.TransferId);
        Data->SetStringField(TEXT("asset_path"), Mesh->GetPathName());
        Data->SetStringField(TEXT("backup_directory"), BackupDirectory);
        Data->SetStringField(TEXT("state"), TEXT("replacement_started"));
        Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("materials_preserved"), false);
        Data->SetBoolField(TEXT("placed"), false);
        if (!Record(Recipe, Data)) return Fail(TEXT("report_failed"), TEXT("Replacement did not start because its recovery record could not be written."));

        TArray<FPackagePart> Backups;
        if (!BackupPackage(OriginalParts, BackupDirectory, Backups))
        {
            Data->SetStringField(TEXT("state"), TEXT("backup_failed"));
            Data->SetBoolField(TEXT("target_mutated"), false);
            Data->SetStringField(TEXT("diagnostic"), TEXT("Original package parts could not be copied and verified; no reimport was attempted."));
            Record(Recipe, Data);
            return Fail(TEXT("backup_failed"), TEXT("Original package backup could not be verified; no replacement was attempted."));
        }
        TArray<TSharedPtr<FJsonValue>> BackupParts;
        for (const FPackagePart& Part : Backups)
        {
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("file"), Part.RelativeName);
            Item->SetStringField(TEXT("sha256"), Part.Sha256);
            Item->SetNumberField(TEXT("bytes"), Part.Bytes);
            BackupParts.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetArrayField(TEXT("verified_backup_parts"), BackupParts);
        Data->SetBoolField(TEXT("backup_verified"), true);
        if (!Record(Recipe, Data))
            return Fail(TEXT("report_failed"), TEXT("A verified backup exists, but the replacement intent could not be advanced; inspect it before retrying."));

        TArray<FName> SlotNames, ImportedSlotNames;
        TArray<TObjectPtr<UMaterialInterface>> ExistingMaterials;
        for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
        {
            SlotNames.Add(Slot.MaterialSlotName);
            ImportedSlotNames.Add(Slot.ImportedMaterialSlotName);
            ExistingMaterials.Add(Slot.MaterialInterface);
        }
        FScopedTransaction Transaction(FText::FromString(TEXT("ForgeMCP: reviewed static mesh replacement")));
        TStrongObjectPtr<UReimportFbxStaticMeshFactory> FactoryOwner(NewObject<UReimportFbxStaticMeshFactory>());
        TStrongObjectPtr<UAssetImportTask> TaskOwner(NewObject<UAssetImportTask>());
        UReimportFbxStaticMeshFactory* Factory = FactoryOwner.Get();
        UAssetImportTask* Task = TaskOwner.Get();
        UFbxImportUI* Options = NewObject<UFbxImportUI>(Factory);
        Options->MeshTypeToImport = FBXIT_StaticMesh;
        Options->bAutomatedImportShouldDetectType = false;
        Options->bImportAsSkeletal = false;
        Options->bImportMesh = true;
        Options->bImportMaterials = false;
        Options->bImportTextures = false;
        Task->bAutomated = true;
        Task->bReplaceExisting = true;
        Task->bReplaceExistingSettings = false;
        Task->Options = Options;
        Factory->SetAssetImportTask(Task);
        Factory->SetAutomatedReimport(true);
        Factory->SetReimportPaths(Mesh, {Artifact(Recipe)});
        FImportDiagnostics Diagnostics;
        const EReimportResult::Type ReimportResult = Factory->Reimport(Mesh);
        Factory->CleanUp();
        Diagnostics.AppendTo(Data);

        bool MaterialsPreserved = IsValid(Mesh) && Mesh->GetStaticMaterials().Num() == ExistingMaterials.Num();
        if (MaterialsPreserved)
        {
            for (int32 Index = 0; Index < ExistingMaterials.Num(); ++Index)
            {
                FStaticMaterial& Slot = Mesh->GetStaticMaterials()[Index];
                if (Slot.MaterialSlotName != SlotNames[Index] || Slot.ImportedMaterialSlotName != ImportedSlotNames[Index])
                { MaterialsPreserved = false; break; }
                Slot.MaterialInterface = ExistingMaterials[Index];
            }
        }
        FString NewRevision;
        const bool Reimported = ReimportResult == EReimportResult::Succeeded && IsValid(Mesh) &&
            MaterialsPreserved && Describe(Mesh, Data) && MeshRevision(Mesh, NewRevision);
        if (Reimported)
        {
            Mesh->PostEditChange();
            Mesh->GetPackage()->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.BindingId"), *Plan.BindingId);
            Mesh->GetPackage()->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.SourceSnapshot"), *Plan.SourceSnapshot);
            Mesh->GetPackage()->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.TargetSnapshot"), *NewRevision);
            Mesh->MarkPackageDirty();
        }
        bool Saved = false;
        if (Reimported)
        {
            FString Filename;
            if (FPackageName::TryConvertLongPackageNameToFilename(PackagePath, Filename, FPackageName::GetAssetPackageExtension()))
            {
                FSavePackageArgs SaveArgs;
                SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
                SaveArgs.SaveFlags = SAVE_NoError;
                Saved = UPackage::SavePackage(Mesh->GetOutermost(), Mesh, *Filename, SaveArgs);
            }
        }
        TArray<FPackagePart> SavedParts;
        FString SavedFingerprint;
        Saved = Saved && PackageParts(PackagePath, SavedParts, SavedFingerprint);
        Data->SetBoolField(TEXT("saved"), Saved);
        Data->SetBoolField(TEXT("materials_preserved"), MaterialsPreserved);
        Data->SetStringField(TEXT("backup_directory"), BackupDirectory);
        Data->SetBoolField(TEXT("backup_retained"), true);
        Data->SetBoolField(TEXT("target_mutated"), true);
        if (Saved)
        {
            TArray<TSharedPtr<FJsonValue>> MaterialAssignments;
            for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
            {
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("slot_name"), Slot.ImportedMaterialSlotName.ToString());
                Item->SetStringField(TEXT("material_path"), GetPathNameSafe(Slot.MaterialInterface.Get()));
                MaterialAssignments.Add(MakeShared<FJsonValueObject>(Item));
            }
            Data->SetArrayField(TEXT("material_assignments"), MaterialAssignments);
            Data->SetStringField(TEXT("state"), TEXT("replaced"));
            Data->SetStringField(TEXT("binding_id"), Plan.BindingId);
            Data->SetStringField(TEXT("source_snapshot_sha256"), Plan.SourceSnapshot);
            Data->SetStringField(TEXT("target_revision_sha256"), NewRevision);
            Data->SetStringField(TEXT("package_fingerprint"), SavedFingerprint);
            Data->SetBoolField(TEXT("memory_state_verified"), true);
            Data->SetBoolField(TEXT("disk_state_verified"), true);
            GEditor->BroadcastObjectReimported(Mesh);
        }
        else
        {
            const bool DiskRestored = RestorePackage(OriginalParts, Backups, PackagePath);
            Data->SetStringField(TEXT("state"), DiskRestored ? TEXT("partial_disk_restored_memory_unverified") : TEXT("partial_backup_retained"));
            Data->SetBoolField(TEXT("disk_restored"), DiskRestored);
            Data->SetBoolField(TEXT("memory_state_requires_editor_restart"), true);
            Data->SetStringField(TEXT("diagnostic"), TEXT("Replacement did not verify and save. The exact original package backup was retained; the loaded object may contain partial changes."));
        }
        if (!Record(Recipe, Data))
        {
            Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
            Data->SetStringField(TEXT("diagnostic"), TEXT("Replacement report update failed; inspect the retained package backup and target before retrying."));
        }
        return true;
    }
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
        Package->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.BindingId"), *Text(Recipe, TEXT("binding_id")));
        Package->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.SourceSnapshot"), *Text(Recipe, TEXT("source_snapshot_sha256")));
        Data->SetStringField(TEXT("binding_id"), Text(Recipe, TEXT("binding_id")));
        Data->SetStringField(TEXT("source_snapshot_sha256"), Text(Recipe, TEXT("source_snapshot_sha256")));
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
        FString TargetRevision;
        if (MeshRevision(Mesh, TargetRevision))
        {
            Package->GetMetaData().SetValue(Mesh, TEXT("ForgeMCP.TargetSnapshot"), *TargetRevision);
            Data->SetStringField(TEXT("target_revision_sha256"), TargetRevision);
            Data->SetBoolField(TEXT("revision_tracking_available"), true);
        }
        else Data->SetBoolField(TEXT("revision_tracking_available"), false);
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
