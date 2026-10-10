#include "ForgeLevels.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "FileHelpers.h"
#include "HAL/FileManager.h"
#include "Misc/Guid.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/PackageName.h"
#include "Misc/SecureHash.h"
#include "UObject/Package.h"
#include "UObject/UObjectHash.h"
#include "UObject/UnrealType.h"
#include "UObject/UObjectGlobals.h"
#include "Materials/MaterialInterface.h"
#include "Engine/StreamableRenderAsset.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

namespace
{
bool Record(const FString& Id, const TSharedRef<FJsonObject>& Data)
{
    const FString Folder = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("ForgeLevelSaves") / Id);
    FString Json;
    auto Writer = TJsonWriterFactory<>::Create(&Json);
    if (!FJsonSerializer::Serialize(Data, Writer)) return false;
    const FString Temporary = Folder / (FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".tmp"));
    return FFileHelper::SaveStringToFile(Json, *Temporary, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM) &&
        IFileManager::Get().Move(*(Folder / TEXT("record.json")), *Temporary, true, true);
}
bool SafeDirectoryPath(const FString& Path)
{
#if PLATFORM_WINDOWS
    FString Current = FPaths::ConvertRelativePathToFull(Path);
    while (!Current.IsEmpty())
    {
        const DWORD Attributes = GetFileAttributesW(*Current);
        if (Attributes != INVALID_FILE_ATTRIBUTES &&
            ((Attributes & FILE_ATTRIBUTE_REPARSE_POINT) || !(Attributes & FILE_ATTRIBUTE_DIRECTORY))) return false;
        FString Parent = FPaths::GetPath(Current);
        if (Parent == Current) break;
        Current = Parent;
    }
    return true;
#else
    return false; // This development package currently targets Win64.
#endif
}
bool Destination(const FString& Path, FString& Filename)
{
    if (Path.Len() > 200 || !Path.StartsWith(TEXT("/Game/"))) return false;
    TArray<FString> Segments;
    Path.Mid(6).ParseIntoArray(Segments, TEXT("/"), false);
    if (Segments.Num() < 2) return false;
    for (const FString& Segment : Segments)
    {
        if (Segment.IsEmpty() || !FChar::IsAlpha(Segment[0])) return false;
        for (TCHAR C : Segment) if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') ||
            (C >= '0' && C <= '9') || C == '_')) return false;
        const FString Upper = Segment.ToUpper();
        if (Upper == TEXT("CON") || Upper == TEXT("PRN") || Upper == TEXT("AUX") || Upper == TEXT("NUL") ||
            (Upper.Len() == 4 && (Upper.StartsWith(TEXT("COM")) || Upper.StartsWith(TEXT("LPT"))) &&
                Upper[3] >= '0' && Upper[3] <= '9')) return false;
    }
    Filename = FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir() / Path.Mid(6) + TEXT(".umap"));
    const FString Folder = FPaths::GetPath(Filename);
    // Reserve a fresh folder for the map and any generated companion packages.
    return SafeDirectoryPath(Folder) && !IFileManager::Get().DirectoryExists(*Folder) &&
        !IFileManager::Get().FileExists(*Filename) && !FPackageName::DoesPackageExist(Path) &&
        !FindPackage(nullptr, *Path);
}
bool Snapshot(UWorld* World, FString& Fingerprint, int32& ObjectCount)
{
    if (!World || !World->PersistentLevel || World->GetLevels().Num() != 1 || World->GetWorldPartition() ||
        World->GetCurrentLevel() != World->PersistentLevel) return false;
    TArray<UObject*> Objects;
    GetObjectsWithOuter(World->GetOutermost(), Objects, true);
    if (Objects.Num() > 10000) return false;
    Objects.Sort([](const UObject& A, const UObject& B) { return A.GetPathName() < B.GetPathName(); });
    FString State = World->GetPathName() + FString::Printf(TEXT("|%p|"), World);
    for (UObject* Object : Objects)
    {
        if (!IsValid(Object)) continue;
        if (Object->IsPackageExternal()) return false;
        if (Object->HasAnyFlags(RF_Transient)) continue;
        State += Object->GetPathName() + TEXT("|") + Object->GetClass()->GetPathName() + TEXT("|");
        for (TFieldIterator<FProperty> It(Object->GetClass()); It; ++It)
        {
            if (It->HasAnyPropertyFlags(CPF_Transient | CPF_DuplicateTransient | CPF_TextExportTransient | CPF_NonPIEDuplicateTransient)) continue;
            for (int32 Index = 0; Index < It->ArrayDim; ++Index)
            {
                FString Value;
                It->ExportText_InContainer(Index, Value, Object, nullptr, Object, PPF_None);
                State += It->GetName() + FString::FromInt(Index) + TEXT("=") + Value + TEXT("\n");
                if (State.Len() > 8 * 1024 * 1024) return false;
            }
        }
    }
    ObjectCount = Objects.Num();
    FTCHARToUTF8 Bytes(*State);
    FSHA1 Hash; Hash.Update(reinterpret_cast<const uint8*>(Bytes.Get()), Bytes.Length()); Hash.Final();
    uint8 Digest[20]; Hash.GetHash(Digest); Fingerprint = BytesToHex(Digest, 20);
    return true;
}
bool Dependencies(UWorld* World, TArray<TSharedPtr<FJsonValue>>& Results, bool& Blocked, FString& State)
{
    TArray<UObject*> Queue;
    GetObjectsWithOuter(World->GetOutermost(), Queue, true);
    Queue.Add(World);
    TSet<UObject*> Seen;
    TSet<UPackage*> Packages;
    for (int32 Index = 0; Index < Queue.Num(); ++Index)
    {
        if (Queue.Num() > 20000) return false;
        UObject* Object = Queue[Index];
        if (!IsValid(Object) || Seen.Contains(Object) || Object->HasAnyFlags(RF_Transient)) continue;
        Seen.Add(Object);
        TArray<UObject*> References;
        FReferenceFinder Finder(References, nullptr, false, true, false, true);
        Finder.FindReferences(Object);
        if (References.Num() > 10000) return false;
        for (UObject* Reference : References)
        {
            if (!IsValid(Reference)) continue;
            UPackage* Package = Reference->GetOutermost();
            if (Package == World->GetOutermost() || Package->GetName().StartsWith(TEXT("/Script/"))) continue;
            if (Reference->HasAnyFlags(RF_Transient) || Package == GetTransientPackage())
            {
                // Persistent component material/mesh/texture references cannot
                // survive saving when their asset exists only in transient storage.
                if (Reference->IsA<UMaterialInterface>() || Reference->IsA<UStreamableRenderAsset>()) Packages.Add(Package);
                if (Packages.Num() > 256) return false;
                continue;
            }
            Packages.Add(Package);
            if (Packages.Num() > 256) return false;
            if (!Seen.Contains(Reference)) Queue.Add(Reference);
        }
    }
    TArray<UPackage*> Ordered = Packages.Array();
    Ordered.Sort([](const UPackage& A, const UPackage& B) { return A.GetName() < B.GetName(); });
    Blocked = false;
    for (UPackage* Package : Ordered)
    {
        const bool Present = FPackageName::DoesPackageExist(Package->GetName());
        const bool Dirty = Package->IsDirty();
        const bool Unsaved = Dirty || !Present;
        Blocked |= Unsaved;
        auto Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("package"), Package->GetName());
        Item->SetBoolField(TEXT("dirty"), Dirty); Item->SetBoolField(TEXT("disk_package_present"), Present);
        Item->SetBoolField(TEXT("requires_separate_save"), Unsaved);
        Results.Add(MakeShared<FJsonValueObject>(Item));
        State += Package->GetName() + (Dirty ? TEXT("|dirty") : TEXT("|clean")) + (Present ? TEXT("|present;") : TEXT("|missing;"));
    }
    return true;
}
}

bool FForgeLevels::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* Error, const TCHAR* Detail) { Code = Error; Message = Detail; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld) return Fail(TEXT("invalid_context"), TEXT("Requires an editor world outside PIE."));
    UWorld* World = GEditor->GetEditorWorldContext().World();
    FString Fingerprint; int32 Count = 0;
    if (!Snapshot(World, Fingerprint, Count)) return Fail(TEXT("unsupported_level"), TEXT("Requires a bounded single persistent level without external packages or world partition."));
    TArray<TSharedPtr<FJsonValue>> DependencyResults;
    bool UnsavedDependencies = false;
    FString DependencyState;
    if (!Dependencies(World, DependencyResults, UnsavedDependencies, DependencyState))
        return Fail(TEXT("dependency_limit"), TEXT("Referenced object/package graph exceeds inspection limits."));
    Fingerprint += DependencyState;
    const double Now = FPlatformTime::Seconds();
    for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= Now) It.RemoveCurrent();
    if (Command == TEXT("level_save_preview"))
    {
        FString Path, Filename;
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("asset_path"), Path))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected only asset_path."));
        if (!Destination(Path, Filename)) return Fail(TEXT("destination_unavailable"), TEXT("Use an absent /Game/ map destination in a new folder; existing and linked destinations are protected."));
        Data->SetArrayField(TEXT("dependencies"), DependencyResults);
        Data->SetStringField(TEXT("source_world"), World->GetPathName());
        Data->SetStringField(TEXT("asset_path"), Path);
        if (UnsavedDependencies)
        {
            Data->SetStringField(TEXT("state"), TEXT("blocked"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("unsaved_dependencies"));
            Data->SetBoolField(TEXT("preview_created"), false);
            return true;
        }
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending previews."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(Id, {Path, Fingerprint, Now + 300});
        Data->SetStringField(TEXT("preview_id"), Id); Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        Data->SetStringField(TEXT("source_world"), World->GetPathName());
        Data->SetStringField(TEXT("asset_path"), Path); Data->SetNumberField(TEXT("snapshot_object_count"), Count);
        Data->SetBoolField(TEXT("overwrites_existing"), false); Data->SetBoolField(TEXT("saves_other_assets"), false);
        Data->SetBoolField(TEXT("current_world_identity_may_change"), true);
        return true;
    }
    FString Id, Confirmation;
    if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), Id) ||
        !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id != Confirmation)
        return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal preview_id."));
    FPreview Plan;
    if (!Previews.RemoveAndCopyValue(Id, Plan)) return Fail(TEXT("preview_not_found"), TEXT("Preview is expired, consumed or belongs to another session."));
    if (UnsavedDependencies) return Fail(TEXT("unsaved_dependencies"), TEXT("Referenced asset packages must be saved separately before saving this map."));
    if (Fingerprint != Plan.Fingerprint) return Fail(TEXT("stale_preview"), TEXT("Persistent world state changed after preview."));
    FString Filename;
    if (!Destination(Plan.Path, Filename)) return Fail(TEXT("destination_unavailable"), TEXT("Destination changed after preview."));
    const FString Folder = FPaths::GetPath(Filename);
    if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Folder), true) || !SafeDirectoryPath(FPaths::GetPath(Folder)))
        return Fail(TEXT("save_directory_unavailable"), TEXT("Could not prepare destination parent."));
#if PLATFORM_WINDOWS
    if (!CreateDirectoryW(*Folder, nullptr)) return Fail(TEXT("destination_unavailable"), TEXT("Could not exclusively reserve a fresh map folder."));
#endif
    const FString Before = World->GetPathName();
    const FString ReportFolder = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("ForgeLevelSaves") / Id);
    if (!SafeDirectoryPath(ReportFolder) || !IFileManager::Get().MakeDirectory(*ReportFolder, true))
        return Fail(TEXT("report_failed"), TEXT("Map save did not start; could not prepare its operation record."));
    Data->SetStringField(TEXT("operation_id"), Id); Data->SetStringField(TEXT("asset_path"), Plan.Path);
    Data->SetStringField(TEXT("source_world"), Before); Data->SetStringField(TEXT("map_file"), Filename);
    Data->SetStringField(TEXT("state"), TEXT("started"));
    Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
    if (!Record(Id, Data)) return Fail(TEXT("report_failed"), TEXT("Map save did not start because its intent record could not be written."));
    const bool Saved = UEditorLoadingAndSavingUtils::SaveMap(World, Plan.Path);
    const bool FilePresent = IFileManager::Get().FileSize(*Filename) > 0;
    Data->SetStringField(TEXT("state"), Saved && FilePresent ? TEXT("saved") : TEXT("partial"));
    Data->SetBoolField(TEXT("saved"), Saved && FilePresent);
    UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
    const FString CurrentPath = CurrentWorld ? CurrentWorld->GetPathName() : TEXT("");
    Data->SetStringField(TEXT("source_world"), Before); Data->SetStringField(TEXT("world"), CurrentPath);
    Data->SetBoolField(TEXT("current_world_changed"), CurrentPath != Before);
    Data->SetStringField(TEXT("asset_path"), Plan.Path); Data->SetStringField(TEXT("map_file"), Filename);
    Data->SetStringField(TEXT("operation_id"), Id); Data->SetBoolField(TEXT("rollback_performed"), false);
    Data->SetBoolField(TEXT("reopened_verified"), false); Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
    if (!Record(Id, Data))
    {
        Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
        Data->SetStringField(TEXT("diagnostic_code"), TEXT("report_failed"));
    }
    return true;
}
