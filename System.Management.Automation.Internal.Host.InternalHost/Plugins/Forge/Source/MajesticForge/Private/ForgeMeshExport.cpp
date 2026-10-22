#include "ForgeMeshExport.h"
#include "AssetExportTask.h"
#include "Editor.h"
#include "Engine/StaticMesh.h"
#include "Exporters/Exporter.h"
#include "Exporters/StaticMeshExporterFBX.h"
#include "Exporters/StaticMeshExporterOBJ.h"
#include "Exporters/FbxExportOption.h"
#include "HAL/FileManager.h"
#include "MeshDescription.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshResources.h"
#include "Serialization/MemoryWriter.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/MetaData.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#include "Windows/AllowWindowsPlatformTypes.h"
#include <sddl.h>
#include <bcrypt.h>
#include "Windows/HideWindowsPlatformTypes.h"
#endif

namespace
{
bool SafeDirectory(const FString& Path)
{
#if PLATFORM_WINDOWS
    FString Current = FPaths::ConvertRelativePathToFull(Path);
    while (Current.Len() > 3)
    {
        DWORD A = GetFileAttributesW(*Current);
        if (A != INVALID_FILE_ATTRIBUTES && (A & FILE_ATTRIBUTE_REPARSE_POINT)) return false;
        Current = FPaths::GetPath(Current);
    }
    return true;
#else
    return false;
#endif
}
bool PrivateDirectory(const FString& Path)
{
#if PLATFORM_WINDOWS
    if (!SafeDirectory(Path) || !IFileManager::Get().MakeDirectory(*Path, true)) return false;
    PSECURITY_DESCRIPTOR D = nullptr;
    if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)", SDDL_REVISION_1, &D, nullptr)) return false;
    bool Ok = SetFileSecurityW(*Path, DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION, D) != 0;
    LocalFree(D); return Ok;
#else
    return false;
#endif
}
bool Digest(const TArray<uint8>& Bytes, FString& Out)
{
#if PLATFORM_WINDOWS
    BCRYPT_ALG_HANDLE A = nullptr; BCRYPT_HASH_HANDLE H = nullptr; uint8 Hash[32];
    if (BCryptOpenAlgorithmProvider(&A, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) return false;
    bool Ok = BCryptCreateHash(A, &H, nullptr, 0, nullptr, 0, 0) >= 0;
    if (Ok) Ok = BCryptHashData(H, const_cast<uint8*>(Bytes.GetData()), Bytes.Num(), 0) >= 0 && BCryptFinishHash(H, Hash, 32, 0) >= 0;
    if (H) BCryptDestroyHash(H);
    BCryptCloseAlgorithmProvider(A, 0);
    if (Ok) Out = BytesToHex(Hash, 32).ToLower();
    return Ok;
#else
    return false;
#endif
}
bool Snapshot(UStaticMesh* Mesh, FString& Out, int32& Vertices, int32& Triangles)
{
    if (Mesh && Mesh->IsHiResMeshDescriptionValid()) return false;
    const FMeshDescription* D = Mesh ? Mesh->GetMeshDescription(0) : nullptr;
    if (!D || D->Vertices().Num() < 3 || D->Vertices().Num() > 100000 || D->Triangles().Num() < 1 || D->Triangles().Num() > 200000 || Mesh->GetStaticMaterials().Num() > 32) return false;
    Vertices = D->Vertices().Num(); Triangles = D->Triangles().Num();
    // Serialize the complete source description, including topology/UVs/normals.
    FMeshDescription Copy(*D); TArray<uint8> Bytes;
    FMemoryWriter Writer(Bytes); Copy.Serialize(Writer);
    // Keep this content fingerprint stable across Editor restarts. Preview lifetime
    // and target binding are validated separately; pointer values are process-local.
    FString Identity = FString::Printf(TEXT("%s:%s"), *Mesh->GetPathName(), *Mesh->GetLightingGuid().ToString());
    for (const FStaticMaterial& M : Mesh->GetStaticMaterials()) Identity += M.MaterialSlotName.ToString() + GetPathNameSafe(M.MaterialInterface.Get());
    FTCHARToUTF8 Text(*Identity); Bytes.Append(reinterpret_cast<const uint8*>(Text.Get()), Text.Length());
    return Digest(Bytes, Out);
}
}

bool FForgeMeshExport::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject>& Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* C, const TCHAR* M) { Code=C; Message=M; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld) return Fail(TEXT("invalid_context"), TEXT("Stop Play in Editor before transferring."));
    FString Path, Id, Confirmation, Format;
    FPreview Plan;
    bool Preview = Command == TEXT("mesh_export_preview");
    bool InspectBinding = Command == TEXT("mesh_binding_info");
    if (Preview || InspectBinding)
    {
        if ((InspectBinding ? Args->Values.Num()!=1 : (Args->Values.Num()!=1 && Args->Values.Num()!=2)) ||
            !Args->TryGetStringField(TEXT("asset_path"),Path) ||
            !(Path.StartsWith(TEXT("/Game/")) || Path.StartsWith(TEXT("/JasperPrism/")) ||
                (Preview && Path.StartsWith(TEXT("/Engine/")))) ||
            Path.Len()>240 || Path.Contains(TEXT(":")) || Path.Contains(TEXT("..")))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected an exact loaded /Game or /JasperPrism static mesh object path; read-only export also accepts /Engine. Optional format is fbx or obj."));
        if (Preview && Args->HasField(TEXT("format")) && !Args->TryGetStringField(TEXT("format"), Format))
            return Fail(TEXT("invalid_arguments"), TEXT("format must be the string fbx or obj."));
        if (Args->Values.Num() == 2 && !Args->HasField(TEXT("format")))
            return Fail(TEXT("invalid_arguments"), TEXT("Only asset_path and format are accepted."));
        for (const auto& Pair : Args->Values)
            if (Pair.Key != TEXT("asset_path") && (!Preview || Pair.Key != TEXT("format")))
                return Fail(TEXT("invalid_arguments"), TEXT("Only asset_path and format are accepted."));
        if (Preview && Format.IsEmpty()) Format = TEXT("fbx");
        if (Preview && Format != TEXT("fbx") && Format != TEXT("obj"))
            return Fail(TEXT("unsupported_format"), TEXT("Choose binary FBX or OBJ."));
    }
    else
    {
        if (Args->Values.Num()!=2 || !Args->TryGetStringField(TEXT("preview_id"),Id) || !Args->TryGetStringField(TEXT("confirmation"),Confirmation) || Id!=Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must match the reviewed preview."));
        const FPreview* P = Previews.Find(Id);
        if (!P || P->Expires <= FPlatformTime::Seconds()) return Fail(TEXT("preview_not_found"), TEXT("Preview expired or was consumed."));
        Plan=*P; Previews.Remove(Id); Path=Plan.Path; Format=Plan.Format;
    }
    UStaticMesh* Mesh = FindObject<UStaticMesh>(nullptr,*Path);
    FString Hash; int32 Vertices=0, Triangles=0;
    if (!IsValid(Mesh) || !Snapshot(Mesh,Hash,Vertices,Triangles)) return Fail(TEXT("unsupported_source"), TEXT("Select a loaded static mesh with bounded LOD0 source geometry."));
    if (Format == TEXT("obj"))
    {
        const FStaticMeshLODResources& LOD = Mesh->GetLODForExport(0);
        if (LOD.GetNumTriangles() != Triangles)
            return Fail(TEXT("unsupported_obj_source"), TEXT("OBJ export requires render LOD0 triangles to match the source mesh description."));
    }
    if (!Preview && !InspectBinding && (Plan.Target.Get()!=Mesh || Hash!=Plan.Snapshot)) return Fail(TEXT("stale_preview"), TEXT("Source object or geometry changed; preview again."));
    if (Preview)
    {
        for (auto It=Previews.CreateIterator(); It; ++It) if (It.Value().Expires<=FPlatformTime::Seconds()) It.RemoveCurrent();
        if (Previews.Num()>=32) return Fail(TEXT("preview_limit"), TEXT("Too many pending previews."));
        Id=FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        Previews.Add(Id,{Path,Hash,Format,Mesh,FPlatformTime::Seconds()+300});
        Data->SetStringField(TEXT("preview_id"),Id);
    }
    Data->SetStringField(TEXT("asset_path"),Path);
    Data->SetStringField(TEXT("source_snapshot_sha256"),Hash);
    if (const FString* BindingId = Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.BindingId")))
        Data->SetStringField(TEXT("binding_id"), *BindingId);
    if (const FString* SourceRevision = Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.SourceSnapshot")))
        Data->SetStringField(TEXT("source_revision_sha256"), *SourceRevision);
    if (const FString* TargetRevision = Mesh->GetPackage()->GetMetaData().FindValue(Mesh, TEXT("ForgeMCP.TargetSnapshot")))
        Data->SetStringField(TEXT("target_revision_sha256"), *TargetRevision);
    Data->SetStringField(TEXT("format"),Format);
    Data->SetNumberField(TEXT("vertex_count"),Vertices);
    Data->SetNumberField(TEXT("triangle_count"),Triangles);
    Data->SetBoolField(TEXT("source_modified"),false);
    Data->SetBoolField(TEXT("material_shader_equivalence"),false);
    if (Preview || InspectBinding) return true;
    FString Directory=FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("ForgeExports"),Id));
    if (IFileManager::Get().DirectoryExists(*Directory) || !PrivateDirectory(Directory)) return Fail(TEXT("unsafe_staging"), TEXT("Cannot create new private export staging."));
    TStrongObjectPtr<UAssetExportTask> Task(NewObject<UAssetExportTask>());
    Task->Object=Mesh;
    if (Format == TEXT("obj"))
    {
        Task->Exporter=NewObject<UStaticMeshExporterOBJ>();
        Task->Filename=FPaths::Combine(Directory,TEXT("mesh.obj"));
    }
    else
    {
        TStrongObjectPtr<UFbxExportOption> Options(NewObject<UFbxExportOption>());
        Options->bASCII=false; Options->LevelOfDetail=false; Options->Collision=false;
        // Match the existing return importer; Blender reads this FBX front-axis metadata.
        Options->bExportSourceMesh=true; Options->bForceFrontXAxis=true;
        Options->BakeMaterialInputs=EFbxMaterialBakeMode::Disabled;
        Task->Exporter=NewObject<UStaticMeshExporterFBX>(); Task->Options=Options.Get();
        Task->Filename=FPaths::Combine(Directory,TEXT("mesh.fbx"));
    }
    Task->bAutomated=true; Task->bPrompt=false; Task->bReplaceIdentical=false;
    if (!UExporter::RunAssetExportTask(Task.Get())) return Fail(TEXT("export_failed"), TEXT("Native FBX export failed; staged files are retained."));
    TArray<uint8> Bytes; FString ArtifactHash;
    int64 Size=IFileManager::Get().FileSize(*Task->Filename);
    if (Size<23 || Size>64*1024*1024 || !FFileHelper::LoadFileToArray(Bytes,*Task->Filename) || !Digest(Bytes,ArtifactHash))
        return Fail(TEXT("export_failed"), TEXT("Export artifact is missing or exceeds limits."));
    Data->SetStringField(TEXT("transfer_id"),Id);
    Data->SetStringField(TEXT("status"),TEXT("exported"));
    Data->SetStringField(TEXT("artifact_name"),FPaths::GetCleanFilename(Task->Filename));
    Data->SetStringField(TEXT("artifact_sha256"),ArtifactHash);
    Data->SetNumberField(TEXT("artifact_bytes"),Bytes.Num());
    return true;
}
