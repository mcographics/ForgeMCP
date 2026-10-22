#include "ForgeLevels.h"
#include "ForgeLandscape.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "EngineUtils.h"
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
#include "LandscapeProxy.h"
#include "Engine/StreamableRenderAsset.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionSubsystem.h"
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
bool EmptyOpenWorldDestination(const FString& Path, FString& Filename)
{
    return Path.StartsWith(TEXT("/Game/ForgeMCPTests/EmptyOpenWorld/"), ESearchCase::CaseSensitive) &&
        Destination(Path, Filename);
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
bool HashFile(const FString& Filename, FString& Hash, int64& Size)
{
    Hash.Reset();
    Size = 0;
    if (!IFileManager::Get().FileExists(*Filename)) return false;
    TUniquePtr<FArchive> Reader(IFileManager::Get().CreateFileReader(*Filename));
    if (!Reader || Reader->TotalSize() <= 0 || Reader->TotalSize() > 2ll * 1024 * 1024 * 1024) return false;
    Size = Reader->TotalSize();
    FSHA1 Sha;
    TArray<uint8> Buffer;
    Buffer.SetNumUninitialized(1024 * 1024);
    int64 Remaining = Size;
    while (Remaining > 0)
    {
        const int64 Chunk = FMath::Min<int64>(Remaining, Buffer.Num());
        Reader->Serialize(Buffer.GetData(), Chunk);
        if (Reader->IsError()) return false;
        Sha.Update(Buffer.GetData(), static_cast<uint32>(Chunk));
        Remaining -= Chunk;
    }
    if (Reader->Tell() != Size) return false;
    Sha.Final();
    uint8 Digest[20];
    Sha.GetHash(Digest);
    Hash = BytesToHex(Digest, UE_ARRAY_COUNT(Digest));
    return true;
}
bool HashText(const FString& State, FString& Hash)
{
    FTCHARToUTF8 Bytes(*State);
    FSHA1 Sha;
    Sha.Update(reinterpret_cast<const uint8*>(Bytes.Get()), Bytes.Length());
    Sha.Final();
    uint8 Digest[20];
    Sha.GetHash(Digest);
    Hash = BytesToHex(Digest, UE_ARRAY_COUNT(Digest));
    return true;
}
bool PackageState(UPackage* Package, FString& StateHash)
{
    if (!IsValid(Package)) return false;
    TArray<UObject*> Objects;
    GetObjectsWithPackage(Package, Objects);
    if (Objects.Num() > 20000) return false;
    Objects.Sort([](const UObject& A, const UObject& B) { return A.GetPathName() < B.GetPathName(); });
    FString State = Package->GetName() + FString::Printf(TEXT("|%p|dirty=%d|flags=%u|"), Package,
        Package->IsDirty() ? 1 : 0, static_cast<uint32>(Package->GetPackageFlags()));
    for (UObject* Object : Objects)
    {
        if (!IsValid(Object) || Object->HasAnyFlags(RF_Transient)) continue;
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
    return HashText(State, StateHash);
}
bool PackageFilename(const FString& PackageName, const bool bMapPackage, FString& Filename)
{
    const FString Extension = bMapPackage ? FPackageName::GetMapPackageExtension() : FPackageName::GetAssetPackageExtension();
    if (!PackageName.StartsWith(TEXT("/Game/")) || PackageName.Len() > 1024 ||
        !FPackageName::IsValidLongPackageName(PackageName) ||
        !FPackageName::TryConvertLongPackageNameToFilename(PackageName, Filename, Extension)) return false;
    Filename = FPaths::ConvertRelativePathToFull(Filename);
    const FString Content = FPaths::ConvertRelativePathToFull(FPaths::ProjectContentDir());
    return FPaths::IsUnderDirectory(Filename, Content) && SafeDirectoryPath(FPaths::GetPath(Filename));
}
bool GatherCurrentSavePackages(UWorld* World, ULevel* Level,
    TArray<FForgeLevels::FCurrentPackage>& OutPackages, FString& Fingerprint)
{
    if (!IsValid(World) || !IsValid(Level) || Level != World->PersistentLevel || World != GWorld) return false;
    TArray<UPackage*> Packages;
    if (UPackage* LevelPackage = Level->GetPackage()) Packages.Add(LevelPackage);
    for (UPackage* ExternalPackage : Level->GetLoadedExternalObjectPackages())
        if (IsValid(ExternalPackage) && !Packages.Contains(ExternalPackage)) Packages.Add(ExternalPackage);
    if (Packages.Num() < 1 || Packages.Num() > 1024) return false;
    Packages.Sort([](const UPackage& A, const UPackage& B) { return A.GetName() < B.GetName(); });
    FString State = World->GetPathName() + FString::Printf(TEXT("|%p|%s|"), World, *Level->GetPathName());
    OutPackages.Reset();
    for (UPackage* Package : Packages)
    {
        const bool bMap = Package == Level->GetPackage();
        FString Filename;
        FString ObjectState;
        if (!PackageFilename(Package->GetName(), bMap, Filename) || !PackageState(Package, ObjectState)) return false;
        FForgeLevels::FCurrentPackage Entry;
        Entry.Package = Package;
        Entry.PackageName = Package->GetName();
        Entry.Filename = Filename;
        Entry.bFileExisted = IFileManager::Get().FileExists(*Filename);
        // Removing a World Partition actor legitimately removes its now-empty
        // external actor package. Track that as a verified delete, not a failed save.
        Entry.bWillDelete = !bMap && Entry.PackageName.StartsWith(TEXT("/Game/__ExternalActors__/")) &&
            UPackage::IsEmptyPackage(Package);
        Entry.bWillSave = !Entry.bWillDelete && (Package->IsDirty() ||
            Package->HasAnyPackageFlags(PKG_NewlyCreated) || UPackage::IsEmptyPackage(Package));
        if (Entry.bFileExisted && !HashFile(Filename, Entry.BeforeFingerprint, Entry.BeforeBytes)) return false;
        if (!Entry.bFileExisted && !Entry.bWillSave && !Entry.bWillDelete) return false;
        Entry.BeforeFingerprint = ObjectState + TEXT("|") + Entry.BeforeFingerprint;
        State += Entry.PackageName + TEXT("|") + Entry.BeforeFingerprint + FString::Printf(TEXT("|save=%d|delete=%d|"),
            Entry.bWillSave ? 1 : 0, Entry.bWillDelete ? 1 : 0);
        OutPackages.Add(MoveTemp(Entry));
    }
    return HashText(State, Fingerprint);
}
bool SnapshotWorldPackages(UWorld* World, FString& Fingerprint, int32& DirtyCount)
{
    if (!IsValid(World) || !IsValid(World->PersistentLevel) || World != GWorld) return false;
    TArray<UPackage*> Packages;
    if (UPackage* WorldPackage = World->GetOutermost()) Packages.Add(WorldPackage);
    for (UPackage* ExternalPackage : World->PersistentLevel->GetLoadedExternalObjectPackages())
        if (IsValid(ExternalPackage) && !Packages.Contains(ExternalPackage)) Packages.Add(ExternalPackage);
    if (Packages.IsEmpty() || Packages.Num() > 1024) return false;
    Packages.Sort([](const UPackage& A, const UPackage& B) { return A.GetName() < B.GetName(); });
    FString State = World->GetPathName() + FString::Printf(TEXT("|%p|"), World);
    DirtyCount = 0;
    for (UPackage* Package : Packages)
    {
        FString PackageFingerprint;
        if (!PackageState(Package, PackageFingerprint)) return false;
        DirtyCount += Package->IsDirty() ? 1 : 0;
        State += PackageFingerprint + TEXT("\n");
    }
    return HashText(State, Fingerprint);
}
}

bool FForgeLevels::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message, FForgeLandscape* LandscapeAutomation)
{
    auto Fail = [&](const TCHAR* Error, const TCHAR* Detail) { Code = Error; Message = Detail; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld) return Fail(TEXT("invalid_context"), TEXT("Requires an editor world outside PIE."));
    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (Command == TEXT("level_create_preview") || Command == TEXT("level_create_apply"))
    {
        if (!IsValid(World) || World != GWorld || !World->PersistentLevel)
            return Fail(TEXT("invalid_context"), TEXT("Empty Open World creation requires the active editor world outside PIE."));

        if (Command == TEXT("level_create_preview"))
        {
            FString MapPath, Filename, SourceFingerprint;
            int32 DirtyPackages = 0;
            if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("map_path"), MapPath))
                return Fail(TEXT("invalid_arguments"), TEXT("Expected only map_path."));
            if (!EmptyOpenWorldDestination(MapPath, Filename))
                return Fail(TEXT("destination_unavailable"), TEXT("Use a fresh /Game/ForgeMCPTests/EmptyOpenWorld/<Map> package in a new folder."));
            if (!SnapshotWorldPackages(World, SourceFingerprint, DirtyPackages))
                return Fail(TEXT("source_world_unavailable"), TEXT("The outgoing editor world and its loaded external packages could not be safely inspected."));
            if (DirtyPackages != 0)
                return Fail(TEXT("source_world_dirty"), TEXT("Save or discard dirty outgoing world packages before creating a new level; ForgeMCP will not save them implicitly."));

            const double Now = FPlatformTime::Seconds();
            for (auto It = EmptyOpenWorldPreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= Now) It.RemoveCurrent();
            if (EmptyOpenWorldPreviews.Num() >= 16)
                return Fail(TEXT("preview_limit"), TEXT("At most 16 Empty Open World previews may be pending."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FEmptyOpenWorldPreview Plan;
            Plan.SourceWorld = World;
            Plan.SourceWorldPath = World->GetPathName();
            Plan.SourceFingerprint = SourceFingerprint;
            Plan.MapPath = MapPath;
            Plan.Expires = Now + 300.0;
            EmptyOpenWorldPreviews.Add(Id, MoveTemp(Plan));

            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("template"), TEXT("Empty Open World"));
            Data->SetStringField(TEXT("map_path"), MapPath);
            Data->SetStringField(TEXT("source_world"), World->GetPathName());
            Data->SetStringField(TEXT("creation_api"), TEXT("UEditorEngine::CreateNewMapForEditing(false, true)"));
            Data->SetBoolField(TEXT("world_partition_requested"), true);
            Data->SetBoolField(TEXT("source_world_clean"), true);
            Data->SetBoolField(TEXT("overwrites_existing"), false);
            Data->SetBoolField(TEXT("landscape_spawn_requested"), false);
            Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            return true;
        }

        FString Id, Confirmation;
        if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), Id) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal preview_id."));
        FEmptyOpenWorldPreview Plan;
        if (!EmptyOpenWorldPreviews.RemoveAndCopyValue(Id, Plan) || Plan.Expires <= FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"), TEXT("Empty Open World preview is expired, consumed or belongs to another editor session."));
        if (Plan.SourceWorld.Get() != World || Plan.SourceWorldPath != World->GetPathName())
            return Fail(TEXT("stale_preview"), TEXT("The active world changed after preview; no map transition was attempted."));

        FString CurrentFingerprint, Filename;
        int32 DirtyPackages = 0;
        if (!SnapshotWorldPackages(World, CurrentFingerprint, DirtyPackages) || DirtyPackages != 0 ||
            CurrentFingerprint != Plan.SourceFingerprint)
            return Fail(TEXT("stale_preview"), TEXT("Outgoing world package state changed after preview; no map transition was attempted."));
        if (!EmptyOpenWorldDestination(Plan.MapPath, Filename))
            return Fail(TEXT("destination_unavailable"), TEXT("The reviewed destination changed or is no longer fresh."));
        if (!LandscapeAutomation)
            return Fail(TEXT("lifecycle_gate_unavailable"), TEXT("The native Landscape world-transition safety gate is unavailable; no map transition was attempted."));

        const FString OperationFolder = FPaths::ConvertRelativePathToFull(
            FPaths::ProjectSavedDir() / TEXT("ForgeLevelSaves") / Id);
        if (!SafeDirectoryPath(OperationFolder) || !IFileManager::Get().MakeDirectory(*OperationFolder, true) ||
            !SafeDirectoryPath(OperationFolder))
            return Fail(TEXT("receipt_unavailable"), TEXT("Could not prepare the durable operation receipt; no map transition was attempted."));

        Data->SetStringField(TEXT("operation_id"), Id);
        Data->SetStringField(TEXT("template"), TEXT("Empty Open World"));
        Data->SetStringField(TEXT("map_path"), Plan.MapPath);
        Data->SetStringField(TEXT("source_world"), Plan.SourceWorldPath);
        Data->SetStringField(TEXT("creation_api"), TEXT("UEditorEngine::CreateNewMapForEditing(false, true)"));
        Data->SetStringField(TEXT("state"), TEXT("started"));
        Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
        if (!Record(Id, Data))
            return Fail(TEXT("receipt_unavailable"), TEXT("The durable intent receipt could not be written; no map transition was attempted."));

        FString TransitionError;
        if (!LandscapeAutomation->PrepareForWorldTransition(World, TransitionError))
        {
            Data->SetStringField(TEXT("state"), TEXT("blocked"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("world_transition_blocked"));
            Data->SetStringField(TEXT("detail"), TransitionError);
            Record(Id, Data);
            return Fail(TEXT("world_transition_blocked"), *TransitionError);
        }

        const FString Folder = FPaths::GetPath(Filename);
        if (!SafeDirectoryPath(Folder) || !IFileManager::Get().MakeDirectory(*Folder, true) || !SafeDirectoryPath(Folder))
        {
            Data->SetStringField(TEXT("state"), TEXT("failed"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("destination_directory_unavailable"));
            Record(Id, Data);
            return Fail(TEXT("destination_directory_unavailable"), TEXT("Could not safely prepare the new map folder; map transition was not attempted."));
        }

        GEditor->CreateNewMapForEditing(false, true);
        UWorld* NewWorld = GEditor->GetEditorWorldContext().World();
        if (!IsValid(NewWorld) || NewWorld == World || NewWorld != GWorld)
        {
            Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("new_world_not_loaded"));
            Record(Id, Data);
            return Fail(TEXT("new_world_not_loaded"), TEXT("The editor did not establish a distinct current world; the operation was not retried."));
        }

        UWorldPartition* Partition = NewWorld->GetWorldPartition();
        UWorldPartitionSubsystem* PartitionSubsystem = NewWorld->GetSubsystem<UWorldPartitionSubsystem>();
        int32 LandscapeActorCount = 0;
        for (TActorIterator<ALandscapeProxy> It(NewWorld); It; ++It) ++LandscapeActorCount;
        const bool bPartitionInitialized = Partition && Partition->IsInitialized();
        const bool bPartitionEnabled = Partition != nullptr && UWorld::IsPartitionedWorld(NewWorld);
        const bool bSubsystemAvailable = PartitionSubsystem != nullptr;
        const FString ExpectedWorldPath = Plan.MapPath + TEXT(".") + FPackageName::GetShortName(Plan.MapPath);
        if (!bPartitionEnabled || !bPartitionInitialized || !bSubsystemAvailable || LandscapeActorCount != 0)
        {
            Data->SetStringField(TEXT("state"), TEXT("partial"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("empty_open_world_validation_failed"));
            Data->SetStringField(TEXT("world"), NewWorld->GetPathName());
            Data->SetBoolField(TEXT("world_partition_enabled"), bPartitionEnabled);
            Data->SetBoolField(TEXT("partition_initialized"), bPartitionInitialized);
            Data->SetBoolField(TEXT("partition_subsystem_available"), bSubsystemAvailable);
            Data->SetBoolField(TEXT("partition_streaming_enabled"), Partition && Partition->IsStreamingEnabled());
            Data->SetNumberField(TEXT("landscape_actor_count"), LandscapeActorCount);
            Data->SetBoolField(TEXT("saved"), false);
            Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
            Record(Id, Data);
            return true;
        }

        const bool bSaved = UEditorLoadingAndSavingUtils::SaveMap(NewWorld, Plan.MapPath);
        FString MapHash;
        int64 MapBytes = 0;
        const bool bMapFileVerified = bSaved && HashFile(Filename, MapHash, MapBytes);
        UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
        const FString CurrentWorldPath = IsValid(CurrentWorld) ? CurrentWorld->GetPathName() : FString();
        const bool bWorldLoaded = CurrentWorld == NewWorld && CurrentWorldPath == ExpectedWorldPath;
        const bool bVerified = bMapFileVerified && bWorldLoaded && bPartitionEnabled &&
            bPartitionInitialized && bSubsystemAvailable && LandscapeActorCount == 0;

        Data->SetStringField(TEXT("state"), bVerified ? TEXT("saved") : TEXT("partial"));
        Data->SetStringField(TEXT("world"), CurrentWorldPath);
        Data->SetStringField(TEXT("map_path"), Plan.MapPath);
        Data->SetStringField(TEXT("map_file"), Filename);
        Data->SetStringField(TEXT("map_file_sha1"), MapHash);
        Data->SetNumberField(TEXT("map_file_bytes"), MapBytes);
        Data->SetBoolField(TEXT("saved"), bVerified);
        Data->SetBoolField(TEXT("world_loaded"), bWorldLoaded);
        Data->SetBoolField(TEXT("current_world_changed"), CurrentWorld != World);
        Data->SetBoolField(TEXT("world_partition_enabled"), bPartitionEnabled);
        Data->SetBoolField(TEXT("partition_initialized"), bPartitionInitialized);
        Data->SetBoolField(TEXT("partition_subsystem_available"), bSubsystemAvailable);
        Data->SetBoolField(TEXT("partition_streaming_enabled"), Partition->IsStreamingEnabled());
        Data->SetNumberField(TEXT("landscape_actor_count"), LandscapeActorCount);
        Data->SetBoolField(TEXT("rollback_performed"), false);
        Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
        if (!bVerified) Data->SetStringField(TEXT("diagnostic_code"), TEXT("saved_map_or_runtime_verification_failed"));
        if (!Record(Id, Data))
        {
            Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("receipt_failed"));
        }
        return true;
    }

    if (Command == TEXT("current_level_save_preview") || Command == TEXT("current_level_save_apply"))
    {
        if (!World || World != GWorld || Args->Values.Num() != (Command == TEXT("current_level_save_preview") ? 0 : 2))
            return Fail(TEXT("invalid_context"), TEXT("Current-level save requires the active non-PIE editor world and exact arguments."));
        ULevel* Level = World->GetCurrentLevel();
        // This operation targets the current persistent level and uses Unreal's
        // native SaveCurrentLevel path, which includes loaded World Partition
        // external-object packages without saving unrelated dirty content assets.
        if (!Level || Level != World->PersistentLevel)
            return Fail(TEXT("unsupported_level"), TEXT("Current-level save requires the persistent level of the active world."));

        auto PackageListJson = [](const TArray<FCurrentPackage>& Packages, const bool bAfterSave)
        {
            TArray<TSharedPtr<FJsonValue>> Items;
            for (const FCurrentPackage& Package : Packages)
            {
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("package"), Package.PackageName);
                Item->SetBoolField(TEXT("will_save"), Package.bWillSave);
                Item->SetBoolField(TEXT("will_delete"), Package.bWillDelete);
                Item->SetBoolField(TEXT("file_existed_before"), Package.bFileExisted);
                if (!bAfterSave && Package.bFileExisted)
                {
                    FString Hash = Package.BeforeFingerprint;
                    const int32 Separator = Hash.Find(TEXT("|"), ESearchCase::CaseSensitive, ESearchDir::FromEnd);
                    Hash = Separator != INDEX_NONE ? Hash.Mid(Separator + 1) : FString();
                    Item->SetStringField(TEXT("before_sha1"), Hash);
                    Item->SetNumberField(TEXT("before_bytes"), Package.BeforeBytes);
                }
                Items.Add(MakeShared<FJsonValueObject>(Item));
            }
            return Items;
        };

        if (Command == TEXT("current_level_save_preview"))
        {
            TArray<FCurrentPackage> Packages;
            FString Fingerprint;
            if (!GatherCurrentSavePackages(World, Level, Packages, Fingerprint))
                return Fail(TEXT("unsupported_level"), TEXT("The current level or its loaded external packages exceed bounded project-content save checks."));
            for (auto It = CurrentPreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (CurrentPreviews.Num() >= 16) return Fail(TEXT("preview_limit"), TEXT("At most 16 current-level save previews may be pending."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FCurrentSavePreview Plan;
            Plan.World = World;
            Plan.Level = Level;
            Plan.WorldPath = World->GetPathName();
            Plan.LevelPath = Level->GetPackage()->GetName();
            Plan.Fingerprint = Fingerprint;
            Plan.Packages = Packages;
            Plan.Expires = FPlatformTime::Seconds() + 300;
            CurrentPreviews.Add(Id, MoveTemp(Plan));
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("world"), World->GetPathName());
            Data->SetStringField(TEXT("level_package"), Level->GetPackage()->GetName());
            Data->SetArrayField(TEXT("packages"), PackageListJson(Packages, false));
            Data->SetNumberField(TEXT("package_count"), Packages.Num());
            Data->SetBoolField(TEXT("world_partition_supported"), World->GetWorldPartition() != nullptr);
            Data->SetBoolField(TEXT("overwrite_existing_level_packages"), true);
            Data->SetBoolField(TEXT("binary_backups_created_on_apply"), true);
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            return true;
        }

        FString Id, Confirmation;
        if (!Args->TryGetStringField(TEXT("preview_id"), Id) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
        FCurrentSavePreview Plan;
        if (!CurrentPreviews.RemoveAndCopyValue(Id, Plan) || Plan.Expires <= FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"), TEXT("Current-level save preview is expired, consumed or belongs to another editor session."));
        if (Plan.World.Get() != World || Plan.Level.Get() != Level || Plan.WorldPath != World->GetPathName() ||
            Plan.LevelPath != Level->GetPackage()->GetName())
            return Fail(TEXT("stale_preview"), TEXT("The active world or level changed after preview; nothing was saved."));
        TArray<FCurrentPackage> CurrentPackages;
        FString CurrentFingerprint;
        if (!GatherCurrentSavePackages(World, Level, CurrentPackages, CurrentFingerprint) ||
            CurrentFingerprint != Plan.Fingerprint || CurrentPackages.Num() != Plan.Packages.Num())
            return Fail(TEXT("stale_preview"), TEXT("Current level contents or package state changed after preview; nothing was saved."));

        const FString BackupRoot = FPaths::ConvertRelativePathToFull(
            FPaths::ProjectSavedDir() / TEXT("ForgeLevelSaves") / Id / TEXT("Backups"));
        if (!SafeDirectoryPath(BackupRoot) || !IFileManager::Get().MakeDirectory(*BackupRoot, true) || !SafeDirectoryPath(BackupRoot))
            return Fail(TEXT("backup_unavailable"), TEXT("Could not safely prepare the current-level package backup directory."));
        Data->SetStringField(TEXT("operation_id"), Id);
        Data->SetStringField(TEXT("state"), TEXT("started"));
        Data->SetStringField(TEXT("world"), Plan.WorldPath);
        Data->SetStringField(TEXT("level_package"), Plan.LevelPath);
        Data->SetStringField(TEXT("backup_root"), BackupRoot);
        Data->SetArrayField(TEXT("packages"), PackageListJson(Plan.Packages, false));
        Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
        if (!Record(Id, Data)) return Fail(TEXT("receipt_failed"), TEXT("The save did not start because its intent receipt could not be recorded."));

        struct FDiskBackup { FString Filename; FString BackupFilename; FString BeforeHash; bool bExisted = false; };
        TArray<FDiskBackup> Backups;
        Backups.Reserve(Plan.Packages.Num());
        for (const FCurrentPackage& Package : Plan.Packages)
        {
            if (!Package.bWillSave && !Package.bWillDelete) continue;
            FDiskBackup Backup;
            Backup.Filename = Package.Filename;
            Backup.bExisted = Package.bFileExisted;
            if (Package.bFileExisted)
            {
                FString Relative = Package.PackageName.Mid(6);
                const FString Extension = FPaths::GetExtension(Package.Filename, true);
                Backup.BackupFilename = FPaths::ConvertRelativePathToFull(
                    FPaths::Combine(BackupRoot, TEXT("Content"), Relative + Extension));
                if (!FPaths::IsUnderDirectory(Backup.BackupFilename, BackupRoot) ||
                    !SafeDirectoryPath(FPaths::GetPath(Backup.BackupFilename)) ||
                    !IFileManager::Get().MakeDirectory(*FPaths::GetPath(Backup.BackupFilename), true) ||
                    IFileManager::Get().Copy(*Backup.BackupFilename, *Backup.Filename, false, false) != COPY_OK)
                {
                    Data->SetStringField(TEXT("state"), TEXT("backup_failed"));
                    Data->SetStringField(TEXT("diagnostic_code"), TEXT("backup_verification_failed"));
                    Record(Id, Data);
                    return Fail(TEXT("backup_failed"), TEXT("A required current-level package backup could not be created; save was not attempted."));
                }
                int64 SourceBytes = 0;
                if (!HashFile(Backup.Filename, Backup.BeforeHash, SourceBytes) || SourceBytes != Package.BeforeBytes ||
                    Backup.BeforeHash != Package.BeforeFingerprint.Right(40))
                {
                    Data->SetStringField(TEXT("state"), TEXT("backup_failed"));
                    Data->SetStringField(TEXT("diagnostic_code"), TEXT("source_changed_before_backup"));
                    Record(Id, Data);
                    return Fail(TEXT("backup_failed"), TEXT("A current-level package changed while its backup was being created; save was not attempted."));
                }
                FString BackupHash; int64 BackupBytes = 0;
                if (!HashFile(Backup.BackupFilename, BackupHash, BackupBytes) || BackupHash != Backup.BeforeHash || BackupBytes != Package.BeforeBytes)
                {
                    Data->SetStringField(TEXT("state"), TEXT("backup_failed"));
                    Data->SetStringField(TEXT("diagnostic_code"), TEXT("backup_hash_mismatch"));
                    Record(Id, Data);
                    return Fail(TEXT("backup_failed"), TEXT("A required package backup failed exact hash verification; save was not attempted."));
                }
            }
            Backups.Add(MoveTemp(Backup));
        }

        const bool bSaveCallSucceeded = FEditorFileUtils::SaveCurrentLevel();
        TArray<TSharedPtr<FJsonValue>> SavedPackages;
        bool bVerified = bSaveCallSucceeded;
        for (const FCurrentPackage& Package : Plan.Packages)
        {
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("package"), Package.PackageName);
            Item->SetBoolField(TEXT("saved"), Package.bWillSave);
            Item->SetBoolField(TEXT("deleted"), Package.bWillDelete);
            if (Package.bWillDelete)
            {
                if (IFileManager::Get().FileExists(*Package.Filename)) bVerified = false;
            }
            else if (Package.bWillSave)
            {
                FString Hash; int64 Bytes = 0;
                if (!HashFile(Package.Filename, Hash, Bytes)) bVerified = false;
                else { Item->SetStringField(TEXT("sha1"), Hash); Item->SetNumberField(TEXT("bytes"), Bytes); }
            }
            else if (Package.bFileExisted)
            {
                FString Hash; int64 Bytes = 0;
                if (!HashFile(Package.Filename, Hash, Bytes) || Hash != Package.BeforeFingerprint.Right(40)) bVerified = false;
                else { Item->SetStringField(TEXT("sha1"), Hash); Item->SetNumberField(TEXT("bytes"), Bytes); }
            }
            SavedPackages.Add(MakeShared<FJsonValueObject>(Item));
        }
        bool bRestored = true;
        if (!bVerified)
        {
            for (const FDiskBackup& Backup : Backups)
            {
                if (Backup.bExisted)
                {
                    bRestored &= IFileManager::Get().Copy(*Backup.Filename, *Backup.BackupFilename, true, true) == COPY_OK;
                    FString RestoredHash; int64 RestoredBytes = 0;
                    bRestored &= HashFile(Backup.Filename, RestoredHash, RestoredBytes) && RestoredHash == Backup.BeforeHash;
                }
                else if (IFileManager::Get().FileExists(*Backup.Filename))
                    bRestored &= IFileManager::Get().Delete(*Backup.Filename, false, true, true);
            }
        }
        Data->SetStringField(TEXT("state"), bVerified ? TEXT("saved") : bRestored ? TEXT("partial_disk_restored") : TEXT("partial_backup_retained"));
        Data->SetBoolField(TEXT("saved"), bVerified);
        Data->SetBoolField(TEXT("native_save_returned_success"), bSaveCallSucceeded);
        Data->SetBoolField(TEXT("disk_restored"), !bVerified && bRestored);
        Data->SetBoolField(TEXT("rollback_performed"), !bVerified && bRestored);
        Data->SetArrayField(TEXT("saved_packages"), SavedPackages);
        Data->SetStringField(TEXT("backup_root"), BackupRoot);
        Data->SetBoolField(TEXT("automatic_native_replay_allowed"), false);
        if (!bVerified) Data->SetStringField(TEXT("diagnostic_code"), TEXT("save_or_disk_verification_failed"));
        if (!Record(Id, Data))
        {
            Data->SetStringField(TEXT("state"), TEXT("outcome_unknown"));
            Data->SetStringField(TEXT("diagnostic_code"), TEXT("receipt_failed"));
        }
        return true;
    }
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
