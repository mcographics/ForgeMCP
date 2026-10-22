#include "ForgeLandscape.h"
#include "ForgeDirtyPackages.h"
#include "Editor.h"
#include "Editor/Transactor.h"
#include "EditorModeManager.h"
#include "EditorModes.h"
#include "LevelEditorViewport.h"
#include "LevelEditorSubsystem.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Engine/Brush.h"
#include "GameFramework/WorldSettings.h"
#include "EngineUtils.h"
#include "Landscape.h"
#include "LandscapeInfo.h"
#include "LandscapeEditLayer.h"
#include "LandscapeEdit.h"
#include "LandscapeDataAccess.h"
#include "LandscapeComponent.h"
#include "LandscapeHeightfieldCollisionComponent.h"
#include "LandscapeStreamingProxy.h"
#include "LandscapeSubsystem.h"
#include "Materials/MaterialInterface.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionSubsystem.h"
#include "WorldPartition/HLOD/HLODLayer.h"
#include "WorldPartition/ActorDescContainerInstance.h"
#include "WorldPartition/WorldPartitionActorDescInstance.h"
#include "WorldPartition/WorldPartitionEditorSpatialHash.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"
#include "WorldPartition/WorldPartitionEditorLoaderAdapter.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"
#include "WorldPartition/IWorldPartitionEditorModule.h"
#include "UObject/ReferenceChainSearch.h"
#include "FileHelpers.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/Crc.h"
#include "Misc/SecureHash.h"
#include "Templates/UnrealTemplate.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "ScopedTransaction.h"
#include "UObject/Package.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
// Landscape import/readback and edit chunks have separate bounds. Each edit
// request retains bounded before/after data; pending plans reserve at most
// 15 MiB so the final MiB remains available for a single stage's scratch rows.
constexpr int64 MaxSamples = 4LL * 1024 * 1024;
constexpr int64 MaxEditSamples = 1LL * 1024 * 1024;
constexpr int64 MaxHeightmapChunkSamples = 32LL * 1024;
constexpr int64 MaxPendingPlanBytes = 15LL * 1024 * 1024;
constexpr int64 WorkingBufferBudgetBytes = 16LL * 1024 * 1024;
constexpr int32 MaxComponents = 1024;
constexpr int32 MaxAxisVertices = 8192;
const FString TestRoot = TEXT("/Game/ForgeMCPTests/Landscape/");
const FString InPlaceLandscapeWorld = TEXT("/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017");
const FString DisposableMarkerRelativePath = TEXT("Saved/ForgeMCPDisposableProject.json");
bool TestMap(const FString& Name);

FString CanonicalPath(FString Path)
{
    Path = FPaths::ConvertRelativePathToFull(Path);
    FPaths::NormalizeFilename(Path);
    FPaths::CollapseRelativeDirectories(Path);
    while (Path.Len() > 3 && Path.EndsWith(TEXT("/"))) Path.LeftChopInline(1);
    return Path;
}

bool IsUnderDirectory(const FString& CandidatePath, const FString& DirectoryPath)
{
    FString Candidate = CanonicalPath(CandidatePath);
    FString Directory = CanonicalPath(DirectoryPath);
    if (!Directory.EndsWith(TEXT("/"))) Directory.AppendChar(TEXT('/'));
    return Candidate.StartsWith(Directory, ESearchCase::IgnoreCase);
}

bool SamePath(const FString& LeftPath, const FString& RightPath)
{
    return CanonicalPath(LeftPath).Equals(CanonicalPath(RightPath), ESearchCase::IgnoreCase);
}

bool IsAuthorizedDisposableProject(FString& OutReason)
{
    const FString ExpectedRoot = FPlatformMisc::GetEnvironmentVariable(TEXT("FORGE_LANDSCAPE_DISPOSABLE_PROJECT_ROOT"));
    if (ExpectedRoot.IsEmpty())
    {
        OutReason = TEXT("FORGE_LANDSCAPE_DISPOSABLE_PROJECT_ROOT is not configured.");
        return false;
    }
    if (!SamePath(ExpectedRoot, FPaths::ProjectDir()))
    {
        OutReason = TEXT("The configured disposable project root does not match the active Unreal project.");
        return false;
    }

    const FString MarkerFilename = FPaths::ProjectDir() / DisposableMarkerRelativePath;
    FString MarkerText;
    if (!FFileHelper::LoadFileToString(MarkerText, *MarkerFilename))
    {
        OutReason = TEXT("The disposable-project marker is missing or unreadable.");
        return false;
    }
    TSharedPtr<FJsonObject> Marker;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(MarkerText);
    if (!FJsonSerializer::Deserialize(Reader, Marker) || !Marker.IsValid())
    {
        OutReason = TEXT("The disposable-project marker is not valid JSON.");
        return false;
    }
    FString Purpose, ProjectRoot, ProjectFile, TestId;
    if (!Marker->TryGetStringField(TEXT("purpose"), Purpose) ||
        !Marker->TryGetStringField(TEXT("project_root"), ProjectRoot) ||
        !Marker->TryGetStringField(TEXT("project_file"), ProjectFile) ||
        !Marker->TryGetStringField(TEXT("test_id"), TestId) ||
        Purpose != TEXT("forge_landscape_disposable_test") || TestId.Len() != 32 ||
        !SamePath(ProjectRoot, FPaths::ProjectDir()) || !SamePath(ProjectFile, FPaths::GetProjectFilePath()))
    {
        OutReason = TEXT("The disposable-project marker does not identify this exact test project.");
        return false;
    }
    return true;
}

bool BuildCreateWriteScope(const FString& MapPackage, FString& OutMapFilename,
    FString& OutActorRoot, FString& OutObjectRoot, TArray<FString>& OutHLODPackageNames,
    FString& OutWorldStateFilename, FString& OutError, bool bWorldPartition)
{
    if (!MapPackage.StartsWith(TEXT("/Game/"), ESearchCase::CaseSensitive) || !TestMap(MapPackage))
    {
        OutError = TEXT("The map package must remain under /Game/ForgeMCPTests/Landscape/.");
        return false;
    }
    FString RelativeMap = MapPackage.Mid(6);
    if (RelativeMap.IsEmpty() || RelativeMap.Contains(TEXT("..")) || RelativeMap.Contains(TEXT(":")) ||
        RelativeMap.Contains(TEXT("\\")) || RelativeMap.Contains(TEXT("//")))
    {
        OutError = TEXT("The target map path contains an invalid package segment.");
        return false;
    }

    const FString ContentRoot = FPaths::ProjectContentDir();
    OutMapFilename = FPackageName::LongPackageNameToFilename(MapPackage, FPackageName::GetMapPackageExtension());
    OutActorRoot = FPaths::Combine(ContentRoot, TEXT("__ExternalActors__"), RelativeMap);
    OutObjectRoot = FPaths::Combine(ContentRoot, TEXT("__ExternalObjects__"), RelativeMap);
    OutWorldStateFilename = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Config"), TEXT("WorldState"),
        FString::Printf(TEXT("%u.json"), FCrc::MemCrc32(*MapPackage, sizeof(TCHAR) * MapPackage.Len())));
    OutHLODPackageNames.Reset();
    if (bWorldPartition)
    {
        UHLODLayer* Layer = UHLODLayer::GetEngineDefaultHLODLayersSetup();
        if (!Layer)
        {
            OutError = TEXT("The Engine default World Partition HLOD layer setup could not be resolved before Apply.");
            return false;
        }
        TSet<FString> VisitedLayerPaths;
        TSet<FString> PredictedPackageNames;
        constexpr int32 MaxDefaultHLODLayers = 16;
        for (int32 LayerIndex = 0; Layer; ++LayerIndex)
        {
            if (LayerIndex >= MaxDefaultHLODLayers || VisitedLayerPaths.Contains(Layer->GetPathName()))
            {
                OutError = TEXT("The Engine default HLOD layer chain is cyclic or exceeds the 16-layer preview bound.");
                return false;
            }
            VisitedLayerPaths.Add(Layer->GetPathName());
            const FString PackageName = MapPackage + TEXT("_") + Layer->GetName();
            if (!FPackageName::IsValidLongPackageName(PackageName) || PredictedPackageNames.Contains(PackageName))
            {
                OutError = TEXT("The Engine default HLOD setup produced an invalid or duplicate target package name.");
                return false;
            }
            PredictedPackageNames.Add(PackageName);
            OutHLODPackageNames.Add(PackageName);
            Layer = Layer->GetParentLayer();
        }
    }
    if (!IsUnderDirectory(OutMapFilename, ContentRoot) ||
        !IsUnderDirectory(OutActorRoot, ContentRoot) ||
        !IsUnderDirectory(OutObjectRoot, ContentRoot) ||
        !IsUnderDirectory(OutWorldStateFilename, FPaths::ProjectSavedDir()))
    {
        OutError = TEXT("A resolved package or auxiliary destination escaped the active project's Content/Saved roots.");
        return false;
    }
    for (const FString& PackageName : OutHLODPackageNames)
    {
        const FString PackageFilename = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
        if (!IsUnderDirectory(PackageFilename, ContentRoot))
        {
            OutError = TEXT("A predicted HLOD package destination escaped the active project's Content root.");
            return false;
        }
    }
    return true;
}

bool HasMapPackageOrSidecars(const FString& MapFilename)
{
    if (IFileManager::Get().FileExists(*MapFilename)) return true;
    const FString Directory = FPaths::GetPath(MapFilename);
    const FString BaseName = FPaths::GetBaseFilename(MapFilename);
    TArray<FString> Matches;
    IFileManager::Get().FindFiles(Matches, *(Directory / (BaseName + TEXT(".*"))), true, false);
    return Matches.Num() > 0;
}

bool CheckCreateDestinationsAbsent(const FString& MapPackage, FString& OutMapFilename,
    FString& OutActorRoot, FString& OutObjectRoot, TArray<FString>& OutHLODPackageNames,
    FString& OutWorldStateFilename, FString& OutError, bool bWorldPartition)
{
    if (!BuildCreateWriteScope(MapPackage, OutMapFilename, OutActorRoot, OutObjectRoot,
        OutHLODPackageNames, OutWorldStateFilename, OutError, bWorldPartition)) return false;
    if (FPackageName::DoesPackageExist(MapPackage) || FindPackage(nullptr, *MapPackage) ||
        HasMapPackageOrSidecars(OutMapFilename) ||
        IFileManager::Get().DirectoryExists(*OutActorRoot) ||
        IFileManager::Get().DirectoryExists(*OutObjectRoot) ||
        IFileManager::Get().FileExists(*OutWorldStateFilename))
    {
        OutError = TEXT("The target map, sidecar, generated external-package namespace, or map-specific WorldState file already exists.");
        return false;
    }
    for (const FString& PackageName : OutHLODPackageNames)
    {
        const FString PackageFilename = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
        if (FPackageName::DoesPackageExist(PackageName) || FindPackage(nullptr, *PackageName) ||
            HasMapPackageOrSidecars(PackageFilename))
        {
            OutError = FString::Printf(TEXT("The predicted World Partition HLOD package or sidecar already exists: %s"), *PackageName);
            return false;
        }
    }
    return true;
}

TSharedRef<FJsonObject> MakeCreateWriteScope(const FString& MapPackage, const FString& MapFilename,
    const FString& ActorRoot, const FString& ObjectRoot, const TArray<FString>& HLODPackageNames,
    const FString& WorldStateFilename, bool bWorldPartition,
    bool bMapAbsent, bool bActorRootAbsent, bool bObjectRootAbsent)
{
    TSharedRef<FJsonObject> Scope = MakeShared<FJsonObject>();
    TArray<TSharedPtr<FJsonValue>> ExactDestinations;
    TSharedRef<FJsonObject> Map = MakeShared<FJsonObject>();
    Map->SetStringField(TEXT("package_name"), MapPackage);
    Map->SetStringField(TEXT("filename"), CanonicalPath(MapFilename));
    Map->SetStringField(TEXT("filename_status"), TEXT("deterministic_known_destination"));
    ExactDestinations.Add(MakeShared<FJsonValueObject>(Map));
    for (const FString& HLODPackageName : HLODPackageNames)
    {
        TSharedRef<FJsonObject> HLOD = MakeShared<FJsonObject>();
        HLOD->SetStringField(TEXT("package_name"), HLODPackageName);
        HLOD->SetStringField(TEXT("filename"), CanonicalPath(FPackageName::LongPackageNameToFilename(
            HLODPackageName, FPackageName::GetAssetPackageExtension())));
        HLOD->SetStringField(TEXT("filename_status"), TEXT("deterministic_from_engine_default_hlod_layer_chain"));
        ExactDestinations.Add(MakeShared<FJsonValueObject>(HLOD));
    }
    Scope->SetArrayField(TEXT("exact_known_package_destinations"), ExactDestinations);

    TArray<TSharedPtr<FJsonValue>> Namespaces;
    TSharedRef<FJsonObject> Actors = MakeShared<FJsonObject>();
    Actors->SetStringField(TEXT("kind"), TEXT("World Partition external actor packages"));
    Actors->SetStringField(TEXT("package_namespace"), TEXT("/Game/__ExternalActors__/") + MapPackage.Mid(6) + TEXT("/**"));
    Actors->SetStringField(TEXT("project_directory"), CanonicalPath(ActorRoot));
    Actors->SetStringField(TEXT("filename_status"), TEXT("Unreal-generated package names; namespace only"));
    Namespaces.Add(MakeShared<FJsonValueObject>(Actors));
    TSharedRef<FJsonObject> Objects = MakeShared<FJsonObject>();
    Objects->SetStringField(TEXT("kind"), TEXT("World Partition external object packages"));
    Objects->SetStringField(TEXT("package_namespace"), TEXT("/Game/__ExternalObjects__/") + MapPackage.Mid(6) + TEXT("/**"));
    Objects->SetStringField(TEXT("project_directory"), CanonicalPath(ObjectRoot));
    Objects->SetStringField(TEXT("filename_status"), TEXT("Unreal-generated package names; namespace only"));
    Namespaces.Add(MakeShared<FJsonValueObject>(Objects));
    Scope->SetArrayField(TEXT("allowed_generated_package_namespaces"), Namespaces);

    TArray<TSharedPtr<FJsonValue>> AuxiliaryDestinations;
    TSharedRef<FJsonObject> WorldState = MakeShared<FJsonObject>();
    WorldState->SetStringField(TEXT("filename"), CanonicalPath(WorldStateFilename));
    WorldState->SetStringField(TEXT("category"), TEXT("Editor WorldFolders state for the exact target map"));
    WorldState->SetStringField(TEXT("filename_status"), TEXT("deterministic_from_engine_FCrc_MemCrc32_package_path"));
    AuxiliaryDestinations.Add(MakeShared<FJsonValueObject>(WorldState));
    Scope->SetArrayField(TEXT("exact_known_auxiliary_file_destinations"), AuxiliaryDestinations);

    TArray<TSharedPtr<FJsonValue>> Auxiliary;
    for (const TCHAR* Category : {
        TEXT("Unreal package sidecars (.uexp, .ubulk, .uptnl) adjacent to approved packages"),
        TEXT("Saved/Autosaves and PackageRestoreData.json recovery bookkeeping"),
        TEXT("Saved/SourceControl uncontrolled-changelist bookkeeping"),
        TEXT("Saved/Logs and editor diagnostic output"),
        TEXT("Saved/Config/WindowsEditor per-project editor preferences"),
        TEXT("Saved/Config/WorldState/<exact target-map CRC>.json WorldFolders state"),
        TEXT("Saved/ForgeLandscape/<preview-or-job-id> explicit height/map backup payloads for later save/edit actions") })
    {
        Auxiliary.Add(MakeShared<FJsonValueString>(Category));
    }
    Scope->SetArrayField(TEXT("expected_auxiliary_file_categories"), Auxiliary);

    TSharedRef<FJsonObject> Checks = MakeShared<FJsonObject>();
    Checks->SetBoolField(TEXT("target_map_package_and_sidecars_absent_at_preview"), bMapAbsent);
    Checks->SetBoolField(TEXT("external_actor_namespace_absent_at_preview"), bActorRootAbsent);
    Checks->SetBoolField(TEXT("external_object_namespace_absent_at_preview"), bObjectRootAbsent);
    Checks->SetBoolField(TEXT("all_destinations_rechecked_before_apply"), true);
    Checks->SetBoolField(TEXT("existing_asset_overwrites_rejected"), true);
    Checks->SetBoolField(TEXT("predicted_hlod_packages_and_sidecars_absent_at_preview_and_apply"), true);
    Checks->SetBoolField(TEXT("target_map_worldstate_file_absent_at_preview_and_apply"), true);
    Scope->SetObjectField(TEXT("existing_package_overwrite_checks"), Checks);

    TArray<TSharedPtr<FJsonValue>> SideEffects;
    SideEffects.Add(MakeShared<FJsonValueString>(TEXT("CreateNewMapForEditing can replace the active disposable editor world before package serialization.")));
    SideEffects.Add(MakeShared<FJsonValueString>(TEXT("World Partition initialization and Landscape serialization may create actor/object packages with Unreal-generated filenames.")));
    SideEffects.Add(MakeShared<FJsonValueString>(TEXT("The Engine default HLOD layer chain is duplicated to deterministic target-map package names during temporary-world rename.")));
    SideEffects.Add(MakeShared<FJsonValueString>(TEXT("WorldFolders may persist target-map UI folder state to its deterministic Saved/Config/WorldState CRC filename.")));
    SideEffects.Add(MakeShared<FJsonValueString>(TEXT("SaveLevel and Editor subsystems may update autosave, recovery, source-control, log, Asset Registry, and user-settings data.")));
    Scope->SetArrayField(TEXT("potential_editor_generated_side_effects"), SideEffects);

    TArray<TSharedPtr<FJsonValue>> Unknowns;
    Unknowns.Add(MakeShared<FJsonValueString>(TEXT("The complete filesystem write set cannot be proven or fenced by the Unreal SaveLevel API before execution.")));
    Unknowns.Add(MakeShared<FJsonValueString>(TEXT("SaveLevel and Editor subsystems can emit additional engine/plugin/version-specific files; the API provides no complete pre-write filesystem fence.")));
    Scope->SetArrayField(TEXT("explicit_unknown_or_unbounded_effects"), Unknowns);
    Scope->SetStringField(TEXT("prevention_boundary"), TEXT("Apply is refused outside a marked, isolated disposable project; post-operation filesystem audit is detection, not prevention."));
    Scope->SetStringField(TEXT("rollback_limitations"), TEXT("No guaranteed transaction rollback across map transition, SaveLevel, or generated World Partition files. On failure, preserve evidence and discard the disposable project as a whole; never repair the live project from this operation."));
    Scope->SetStringField(TEXT("preservation_limitations"), TEXT("This is not an atomic snapshot and does not preserve unrelated or unobserved in-memory Editor state."));
    Scope->SetBoolField(TEXT("world_partition_requested"), bWorldPartition);
    return Scope;
}

void AppendGeneratedPackageObservations(const FString& MapPackage, TArray<TSharedPtr<FJsonValue>>& OutPackages)
{
    const FString ActorPrefix = TEXT("/Game/__ExternalActors__/") + MapPackage.Mid(6) + TEXT("/");
    const FString ObjectPrefix = TEXT("/Game/__ExternalObjects__/") + MapPackage.Mid(6) + TEXT("/");
    for (TObjectIterator<UPackage> It; It; ++It)
    {
        UPackage* Package = *It;
        if (!Package) continue;
        const FString PackageName = Package->GetName();
        if (PackageName == MapPackage || PackageName.StartsWith(ActorPrefix, ESearchCase::IgnoreCase) ||
            PackageName.StartsWith(ObjectPrefix, ESearchCase::IgnoreCase))
        {
            TSharedRef<FJsonObject> Row = MakeShared<FJsonObject>();
            Row->SetStringField(TEXT("package_name"), PackageName.Left(1024));
            Row->SetBoolField(TEXT("is_dirty"), Package->IsDirty());
            OutPackages.Add(MakeShared<FJsonValueObject>(Row));
        }
    }
}
FString Hash(const TArray<uint16>& Values)
{
    return FMD5::HashBytes(reinterpret_cast<const uint8*>(Values.GetData()), Values.Num() * sizeof(uint16));
}
bool Number(const TSharedRef<FJsonObject>& R, const TCHAR* Key, double& Value, double Min, double Max, bool Integer = false)
{
    return R->TryGetNumberField(Key, Value) && FMath::IsFinite(Value) && Value >= Min && Value <= Max && (!Integer || Value == FMath::FloorToDouble(Value));
}
ALandscape* Resolve(UWorld* W, const FString& Path)
{
    for (TActorIterator<ALandscape> It(W); It; ++It) if (It->GetPathName() == Path) return *It;
    return nullptr;
}
void CountLandscapeStreamingProxies(UWorld* W,int32& Total,int32& ActiveWorldLoaded,int32& NotInActiveWorld,
    const FBox* FilterBounds=nullptr,int32* SpatiallyLoaded=nullptr,int32* NonSpatiallyLoaded=nullptr,
    int32* DescriptorLoaded=nullptr,int32* DescriptorUnloaded=nullptr)
{
    Total=ActiveWorldLoaded=NotInActiveWorld=0;
    if(SpatiallyLoaded) *SpatiallyLoaded=0;
    if(NonSpatiallyLoaded) *NonSpatiallyLoaded=0;
    if(DescriptorLoaded) *DescriptorLoaded=0;
    if(DescriptorUnloaded) *DescriptorUnloaded=0;
    UWorldPartition* Partition=W?W->GetWorldPartition():nullptr;
    UActorDescContainerInstance* Root=Partition?Partition->GetActorDescContainerInstance():nullptr;
    if(!Root) return;

    // Descriptor resolution is not proof of ownership by W. Build this map only
    // from actors enumerated in the explicit active world; never call GetActor()
    // on a descriptor because that API flushes async loading.
    TMap<FGuid,ALandscapeStreamingProxy*> ActiveWorldProxies;
    for(TActorIterator<ALandscapeStreamingProxy> It(W);It;++It)
    {
        ALandscapeStreamingProxy* Proxy=*It;
        if(!Proxy || Proxy->GetWorld()!=W) continue;
        const FGuid ActorGuid=Proxy->GetActorGuid();
        if(ActorGuid.IsValid()) ActiveWorldProxies.Add(ActorGuid,Proxy);
    }

    TFunction<void(UActorDescContainerInstance*)> Visit=[&](UActorDescContainerInstance* Container)
    {
        if(!Container) return;
        for(UActorDescContainerInstance::TConstIterator<ALandscapeStreamingProxy> It(Container);It;++It)
        {
            const FWorldPartitionActorDescInstance* Instance=*It;
            if(!Instance) continue;
            const FWorldPartitionActorDesc* Desc=Instance->GetActorDesc();
            if(FilterBounds && (!Desc || !FilterBounds->Intersect(Desc->GetEditorBounds()))) continue;
            ++Total;

            const bool bDescriptorLoaded=Instance->IsLoaded();
            if(DescriptorLoaded && bDescriptorLoaded) ++*DescriptorLoaded;
            if(DescriptorUnloaded && !bDescriptorLoaded) ++*DescriptorUnloaded;

            const FGuid ActorGuid=Instance->GetGuid();
            ALandscapeStreamingProxy* const* FoundProxy=ActiveWorldProxies.Find(ActorGuid);
            const bool bActorInActiveWorld=FoundProxy && IsValid(*FoundProxy) &&
                (*FoundProxy)->GetWorld()==W && (*FoundProxy)->GetActorGuid()==ActorGuid;
            if(bActorInActiveWorld) ++ActiveWorldLoaded; else ++NotInActiveWorld;

            if(Desc && Desc->GetIsSpatiallyLoadedRaw()) { if(SpatiallyLoaded) ++*SpatiallyLoaded; }
            else if(NonSpatiallyLoaded) ++*NonSpatiallyLoaded;
        }
        for(const auto& Child:Container->GetChildContainerInstances())
            if(Child.Value) Visit(Child.Value.Get());
    };
    Visit(Root);
}
bool IsEditorStreamingAvailable(UWorld* W)
{
    UWorldPartition* Partition=W?W->GetWorldPartition():nullptr;
    return Partition && Partition->IsStreamingEnabled() && Partition->IsStreamingEnabledInEditor() &&
        IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor();
}
int32 GetRegisteredEditorLoaderCount(UWorld* W)
{
    UWorldPartition* Partition=W?W->GetWorldPartition():nullptr;
    return Partition?Partition->GetRegisteredEditorLoaderAdapters().Num():0;
}
TArray<TSharedPtr<FJsonValue>> VectorJson(const FVector& Value)
{
    return {MakeShared<FJsonValueNumber>(Value.X),MakeShared<FJsonValueNumber>(Value.Y),MakeShared<FJsonValueNumber>(Value.Z)};
}
void AddStreamingDiagnostics(TSharedRef<FJsonObject> Data,UWorld* W,const FBox* RegionBounds=nullptr,
    const FGuid* RootLandscapeGuid=nullptr)
{
    UWorldPartition* Partition=W?W->GetWorldPartition():nullptr;
    int32 Total=0,Loaded=0,Unloaded=0,Spatial=0,NonSpatial=0,DescriptorLoaded=0,DescriptorUnloaded=0;
    CountLandscapeStreamingProxies(W,Total,Loaded,Unloaded,nullptr,&Spatial,&NonSpatial,&DescriptorLoaded,&DescriptorUnloaded);
    Data->SetNumberField(TEXT("landscape_proxy_descriptor_count"),Total);
    // Preserve legacy count semantics while exposing active-world ownership separately.
    Data->SetNumberField(TEXT("loaded_landscape_proxy_count"),DescriptorLoaded);
    Data->SetNumberField(TEXT("unloaded_landscape_proxy_count"),DescriptorUnloaded);
    Data->SetNumberField(TEXT("descriptor_loaded_landscape_proxy_count"),DescriptorLoaded);
    Data->SetNumberField(TEXT("descriptor_unloaded_landscape_proxy_count"),DescriptorUnloaded);
    Data->SetNumberField(TEXT("active_world_landscape_proxy_count"),Loaded);
    Data->SetNumberField(TEXT("not_in_active_world_landscape_proxy_count"),Unloaded);
    Data->SetNumberField(TEXT("spatial_landscape_proxy_count"),Spatial);
    Data->SetNumberField(TEXT("non_spatial_landscape_proxy_count"),NonSpatial);
    Data->SetNumberField(TEXT("registered_editor_loader_adapter_count"),GetRegisteredEditorLoaderCount(W));
    Data->SetBoolField(TEXT("world_partition_streaming_enabled_in_editor"),W && W->GetWorldPartition() && W->GetWorldPartition()->IsStreamingEnabledInEditor());
    Data->SetBoolField(TEXT("world_partition_editor_loading_enabled"),IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor());
    TArray<TSharedPtr<FJsonValue>> LoaderValues;
    int32 LoaderIndex=0;
    if(Partition)
    {
        for(UWorldPartitionEditorLoaderAdapter* Adapter:Partition->GetRegisteredEditorLoaderAdapters())
        {
            if(!Adapter || !Adapter->GetLoaderAdapter()) continue;
            IWorldPartitionActorLoaderInterface::ILoaderAdapter* Loader=Adapter->GetLoaderAdapter();
            if(LoaderIndex++>=64) continue;
            auto Item=MakeShared<FJsonObject>();
            Item->SetBoolField(TEXT("loaded"),Loader->IsLoaded());
            Item->SetBoolField(TEXT("user_created"),Loader->GetUserCreated());
            if(const TOptional<FString> Label=Loader->GetLabel();Label.IsSet()) Item->SetStringField(TEXT("label"),Label.GetValue());
            if(const TOptional<FBox> Bounds=Loader->GetBoundingBox();Bounds.IsSet())
            {
                Item->SetArrayField(TEXT("bounds_min"),VectorJson(Bounds.GetValue().Min));
                Item->SetArrayField(TEXT("bounds_max"),VectorJson(Bounds.GetValue().Max));
                if(RegionBounds) Item->SetBoolField(TEXT("intersects_query_region"),Bounds.GetValue().Intersect(*RegionBounds));
            }
            LoaderValues.Add(MakeShared<FJsonValueObject>(Item));
        }
    }
    Data->SetArrayField(TEXT("registered_editor_loader_adapters"),LoaderValues);
    Data->SetBoolField(TEXT("registered_editor_loader_adapters_truncated"),LoaderIndex>64);
    TArray<TSharedPtr<FJsonValue>> SourceValues;
    int32 SourceIndex=0;
    if(Partition)
    {
        for(const FWorldPartitionStreamingSource& Source:Partition->GetStreamingSources())
        {
            if(SourceIndex++>=64) continue;
            auto Item=MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"),Source.Name.ToString());
            Item->SetArrayField(TEXT("location_cm"),VectorJson(Source.Location));
            Item->SetNumberField(TEXT("target_state"),static_cast<int32>(Source.TargetState));
            Item->SetNumberField(TEXT("priority"),static_cast<int32>(Source.Priority));
            Item->SetBoolField(TEXT("remote"),Source.bRemote);
            Item->SetBoolField(TEXT("blocks_on_slow_loading"),Source.bBlockOnSlowLoading);
            if(RegionBounds) Item->SetBoolField(TEXT("location_inside_query_region"),RegionBounds->IsInsideOrOn(Source.Location));
            SourceValues.Add(MakeShared<FJsonValueObject>(Item));
        }
    }
    Data->SetArrayField(TEXT("world_partition_streaming_sources"),SourceValues);
    Data->SetBoolField(TEXT("world_partition_streaming_sources_truncated"),SourceIndex>64);

    TArray<TSharedPtr<FJsonValue>> LandscapeProxyDescriptors;
    int32 LandscapeProxyDescriptorCount=0;
    TMap<FGuid,ALandscapeStreamingProxy*> ActiveWorldProxies;
    if(W)
    {
        for(TActorIterator<ALandscapeStreamingProxy> It(W);It;++It)
        {
            ALandscapeStreamingProxy* Proxy=*It;
            if(Proxy && Proxy->GetWorld()==W && Proxy->GetActorGuid().IsValid())
                ActiveWorldProxies.Add(Proxy->GetActorGuid(),Proxy);
        }
    }
    UActorDescContainerInstance* Root=Partition?Partition->GetActorDescContainerInstance():nullptr;
    UWorldPartitionEditorSpatialHash* EditorHash=Partition?Cast<UWorldPartitionEditorSpatialHash>(Partition->EditorHash):nullptr;
    TFunction<void(UActorDescContainerInstance*)> VisitLandscapeDescriptors=[&](UActorDescContainerInstance* Container)
    {
        if(!Container) return;
        for(UActorDescContainerInstance::TConstIterator<ALandscapeStreamingProxy> It(Container);It;++It)
        {
            const FWorldPartitionActorDescInstance* Instance=*It;
            if(!Instance) continue;
            ++LandscapeProxyDescriptorCount;
            if(LandscapeProxyDescriptors.Num()>=64) continue;
            const FWorldPartitionActorDesc* Desc=Instance->GetActorDesc();
            if(!Desc) continue;

            const FGuid ActorGuid=Instance->GetGuid();
            const bool bDescriptorLoaded=Instance->IsLoaded();
            ALandscapeStreamingProxy* const* FoundProxy=ActiveWorldProxies.Find(ActorGuid);
            ALandscapeStreamingProxy* ActiveProxy=FoundProxy && IsValid(*FoundProxy) ? *FoundProxy : nullptr;
            const bool bActorInActiveWorld=ActiveProxy && ActiveProxy->GetWorld()==W &&
                ActiveProxy->GetActorGuid()==ActorGuid;
            if(!bActorInActiveWorld) ActiveProxy=nullptr;

            const FBox Bounds=Instance->GetEditorBounds();
            auto Item=MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("actor_guid"),ActorGuid.ToString());
            Item->SetStringField(TEXT("actor_name"),Instance->GetActorNameString());
            Item->SetStringField(TEXT("actor_label"),Instance->GetActorLabelString());
            Item->SetStringField(TEXT("actor_package"),Instance->GetActorPackage().ToString());
            Item->SetStringField(TEXT("actor_soft_path"),Instance->GetActorSoftPath().ToString());
            Item->SetStringField(TEXT("runtime_grid"),Instance->GetRuntimeGrid().ToString());
            Item->SetBoolField(TEXT("spatially_loaded"),Instance->GetIsSpatiallyLoaded());
            Item->SetBoolField(TEXT("spatially_loaded_raw"),Desc->GetIsSpatiallyLoadedRaw());
            Item->SetBoolField(TEXT("descriptor_loaded"),bDescriptorLoaded);
            Item->SetBoolField(TEXT("loaded"),bDescriptorLoaded);
            Item->SetStringField(TEXT("loaded_semantics"),TEXT("legacy alias for descriptor_loaded; does not prove actor ownership by the active UWorld"));
            Item->SetBoolField(TEXT("active_world_actor_resolved"),ActiveProxy!=nullptr);
            Item->SetBoolField(TEXT("actor_in_active_world"),bActorInActiveWorld);
            Item->SetBoolField(TEXT("actor_guid_matches_descriptor"),ActiveProxy && ActiveProxy->GetActorGuid()==ActorGuid);
            Item->SetStringField(TEXT("active_world_actor_path"),ActiveProxy?ActiveProxy->GetPathName():FString());
            Item->SetStringField(TEXT("active_world_actor_guid"),ActiveProxy?ActiveProxy->GetActorGuid().ToString():FString());
            Item->SetStringField(TEXT("active_world_actor_world"),ActiveProxy?ActiveProxy->GetWorld()->GetPathName():FString());
            Item->SetBoolField(TEXT("landscape_guid_available"),ActiveProxy!=nullptr);
            Item->SetStringField(TEXT("landscape_guid"),ActiveProxy?ActiveProxy->GetLandscapeGuid().ToString():FString());
            if(RootLandscapeGuid)
            {
                Item->SetStringField(TEXT("root_landscape_guid"),RootLandscapeGuid->ToString());
                Item->SetBoolField(TEXT("landscape_guid_matches_root"),ActiveProxy && ActiveProxy->GetLandscapeGuid()==*RootLandscapeGuid);
                Item->SetStringField(TEXT("landscape_guid_relationship"),!ActiveProxy?TEXT("unresolved_without_active_world_actor"):(ActiveProxy->GetLandscapeGuid()==*RootLandscapeGuid?TEXT("matches_root_landscape"):TEXT("different_landscape")));
            }
            int32 ProxyComponentCount=0,RegisteredProxyComponentCount=0,ProxyCollisionCount=0,RegisteredProxyCollisionCount=0;
            if(ActiveProxy)
            {
                for(ULandscapeComponent* Component:ActiveProxy->LandscapeComponents)
                {
                    if(!Component) continue;
                    ++ProxyComponentCount;
                    if(Component->IsRegistered()) ++RegisteredProxyComponentCount;
                }
                for(ULandscapeHeightfieldCollisionComponent* Collision:ActiveProxy->CollisionComponents)
                {
                    if(!Collision) continue;
                    ++ProxyCollisionCount;
                    if(Collision->IsRegistered()) ++RegisteredProxyCollisionCount;
                }
            }
            Item->SetNumberField(TEXT("landscape_component_count"),ProxyComponentCount);
            Item->SetNumberField(TEXT("registered_landscape_component_count"),RegisteredProxyComponentCount);
            Item->SetNumberField(TEXT("collision_component_count"),ProxyCollisionCount);
            Item->SetNumberField(TEXT("registered_collision_component_count"),RegisteredProxyCollisionCount);
            UPackage* ExternalActorPackage=ActiveProxy?ActiveProxy->GetExternalPackage():nullptr;
            Item->SetBoolField(TEXT("external_actor_package_resolved"),ExternalActorPackage!=nullptr);
            Item->SetStringField(TEXT("external_actor_package"),ExternalActorPackage?ExternalActorPackage->GetName():FString());
            if(Bounds.IsValid)
            {
                Item->SetArrayField(TEXT("editor_bounds_min"),VectorJson(Bounds.Min));
                Item->SetArrayField(TEXT("editor_bounds_max"),VectorJson(Bounds.Max));
            }
            Item->SetStringField(TEXT("cell_association_kind"),TEXT("editor_spatial_hash_intersections"));
            TArray<TSharedPtr<FJsonValue>> CellValues;
            if(EditorHash && Bounds.IsValid)
            {
                const int32 CellLevel=EditorHash->GetLevelForBox(Bounds);
                Item->SetNumberField(TEXT("editor_hash_level"),CellLevel);
                EditorHash->ForEachIntersectingCells(Bounds,CellLevel,[&](const UWorldPartitionEditorSpatialHash::FCellCoord& CellCoord)
                {
                    if(CellValues.Num()>=64) return;
                    const FBox CellBounds=EditorHash->GetCellBounds(CellCoord);
                    auto Cell=MakeShared<FJsonObject>();
                    Cell->SetNumberField(TEXT("level"),CellCoord.Level);
                    Cell->SetNumberField(TEXT("x"),double(CellCoord.X));
                    Cell->SetNumberField(TEXT("y"),double(CellCoord.Y));
                    Cell->SetNumberField(TEXT("z"),double(CellCoord.Z));
                    Cell->SetArrayField(TEXT("bounds_min"),VectorJson(CellBounds.Min));
                    Cell->SetArrayField(TEXT("bounds_max"),VectorJson(CellBounds.Max));
                    CellValues.Add(MakeShared<FJsonValueObject>(Cell));
                });
            }
            Item->SetArrayField(TEXT("editor_hash_cells"),CellValues);
            LandscapeProxyDescriptors.Add(MakeShared<FJsonValueObject>(Item));
        }
        for(const auto& Child:Container->GetChildContainerInstances())
            if(Child.Value) VisitLandscapeDescriptors(Child.Value.Get());
    };
    VisitLandscapeDescriptors(Root);
    Data->SetArrayField(TEXT("landscape_proxy_descriptors"),LandscapeProxyDescriptors);
    Data->SetNumberField(TEXT("landscape_proxy_descriptor_diagnostics_count"),LandscapeProxyDescriptorCount);
    Data->SetBoolField(TEXT("landscape_proxy_descriptor_diagnostics_truncated"),LandscapeProxyDescriptorCount>LandscapeProxyDescriptors.Num());
    Data->SetBoolField(TEXT("landscape_editor_hash_available"),EditorHash!=nullptr);

    if(RegionBounds)
    {
        int32 RegionTotal=0,RegionLoaded=0,RegionUnloaded=0,RegionSpatial=0,RegionNonSpatial=0,RegionDescriptorLoaded=0,RegionDescriptorUnloaded=0;
        CountLandscapeStreamingProxies(W,RegionTotal,RegionLoaded,RegionUnloaded,RegionBounds,&RegionSpatial,&RegionNonSpatial,&RegionDescriptorLoaded,&RegionDescriptorUnloaded);
        Data->SetNumberField(TEXT("region_proxy_descriptor_count"),RegionTotal);
        Data->SetNumberField(TEXT("region_loaded_proxy_count"),RegionDescriptorLoaded);
        Data->SetNumberField(TEXT("region_unloaded_proxy_count"),RegionDescriptorUnloaded);
        Data->SetNumberField(TEXT("region_descriptor_loaded_proxy_count"),RegionDescriptorLoaded);
        Data->SetNumberField(TEXT("region_descriptor_unloaded_proxy_count"),RegionDescriptorUnloaded);
        Data->SetNumberField(TEXT("region_active_world_proxy_count"),RegionLoaded);
        Data->SetNumberField(TEXT("region_not_in_active_world_proxy_count"),RegionUnloaded);
        Data->SetNumberField(TEXT("region_spatial_proxy_count"),RegionSpatial);
        Data->SetNumberField(TEXT("region_non_spatial_proxy_count"),RegionNonSpatial);
    }
}
bool ReadRegion(ALandscape* L, const FGuid& Layer, const FIntRect& Requested, FIntRect& B, TArray<uint16>& Heights)
{
    ULandscapeInfo* Info = L ? L->GetLandscapeInfo() : nullptr;
    int32 X1, Y1, X2, Y2;
    TArray<ULandscapeComponent*> Components;
    if (Info) Info->ForAllLandscapeComponents([&Components](ULandscapeComponent* C) { Components.Add(C); });
    int32 ProxyTotal=0,ProxyLoaded=0,ProxyUnloaded=0;
    CountLandscapeStreamingProxies(L?L->GetWorld():nullptr,ProxyTotal,ProxyLoaded,ProxyUnloaded);
    if (ProxyTotal!=ProxyLoaded+ProxyUnloaded || !Info || !Info->GetLandscapeExtent(X1, Y1, X2, Y2) || X2 < X1 || Y2 < Y1 ||
        int64(X2-X1+1) * int64(Y2-Y1+1) > MaxSamples || Components.Num() > MaxComponents) return false;
    const FIntRect FullBounds(X1, Y1, X2+1, Y2+1);
    B = Requested;
    if (B.Min.X < FullBounds.Min.X || B.Min.Y < FullBounds.Min.Y ||
        B.Max.X > FullBounds.Max.X || B.Max.Y > FullBounds.Max.Y ||
        B.Width() < 1 || B.Height() < 1 || int64(B.Width()) * B.Height() > MaxSamples) return false;
    Heights.Init(32768, B.Width()*B.Height());
    TBitArray<> Covered(false,Heights.Num());
    // The editing interface's read helper calls Texture->Modify() and takes a
    // writable source lock. Inspection must instead copy source mip data.
    for(ULandscapeComponent* C:Components)
    {
        if(!C || C->ComponentSizeQuads<1 || C->ComponentSizeQuads>510) return false;
        UTexture2D* Texture=C->GetHeightmap(Layer);
        if(!Texture || Texture->Source.GetFormat()!=TSF_BGRA8 || Texture->Source.GetSizeX()>1024 || Texture->Source.GetSizeY()>1024) return false;
        TArray64<uint8> Bytes;
        if(!Texture->Source.GetMipData(Bytes,0)) return false;
        const int32 U=Texture->Source.GetSizeX(), V=Texture->Source.GetSizeY();
        if(U<1 || V<1 || Bytes.Num()!=int64(U)*V*sizeof(FColor)) return false;
        const FColor* Pixels=reinterpret_cast<const FColor*>(Bytes.GetData());
        FLandscapeComponentDataInterfaceBase Mapping(C,0,false);
        FIntPoint Base=C->GetSectionBase();
        const int32 OX=int32(C->HeightmapScaleBias.Z*U), OY=int32(C->HeightmapScaleBias.W*V);
        const int32 LocalX1=FMath::Max(0,B.Min.X-Base.X), LocalY1=FMath::Max(0,B.Min.Y-Base.Y);
        const int32 LocalX2=FMath::Min(C->ComponentSizeQuads,B.Max.X-1-Base.X);
        const int32 LocalY2=FMath::Min(C->ComponentSizeQuads,B.Max.Y-1-Base.Y);
        if(LocalX2<LocalX1 || LocalY2<LocalY1) continue;
        for(int32 Y=LocalY1;Y<=LocalY2;++Y) for(int32 X=LocalX1;X<=LocalX2;++X)
        {
            int32 TX,TY; Mapping.VertexXYToTexelXY(X,Y,TX,TY); TX+=OX; TY+=OY;
            int32 GX=Base.X+X-B.Min.X, GY=Base.Y+Y-B.Min.Y;
            if(TX<0 || TY<0 || TX>=U || TY>=V || GX<0 || GY<0 || GX>=B.Width() || GY>=B.Height()) return false;
            const FColor& Pixel=Pixels[TY*U+TX]; uint16 Height=(uint16(Pixel.R)<<8)|Pixel.G;
            int32 Index=GY*B.Width()+GX;
            if(Covered[Index] && Heights[Index]!=Height) return false;
            Heights[Index]=Height; Covered[Index]=true;
        }
    }
    for(bool Value:Covered) if(!Value) return false;
    return true;
}
bool ParseInclusiveRegion(const TSharedRef<FJsonObject>& R,const TCHAR* Field,FIntRect& Bounds)
{
    const TArray<TSharedPtr<FJsonValue>>* Region=nullptr;
    if(!R->TryGetArrayField(Field,Region) || Region->Num()!=4) return false;
    double V[4];
    for(int32 I=0;I<4;++I)
        if(!(*Region)[I]->TryGetNumber(V[I]) || !FMath::IsFinite(V[I]) || V[I]!=FMath::FloorToDouble(V[I]) || V[I]<0 || V[I]>=MaxAxisVertices) return false;
    const int32 X1=int32(V[0]),Y1=int32(V[1]),X2=int32(V[2]),Y2=int32(V[3]);
    if(X2<X1 || Y2<Y1) return false;
    Bounds=FIntRect(X1,Y1,X2+1,Y2+1);
    return int64(Bounds.Width())*Bounds.Height()<=MaxSamples;
}
bool ParseRegion(const TSharedRef<FJsonObject>& R,FIntRect& Bounds)
{
    return ParseInclusiveRegion(R,TEXT("region"),Bounds);
}
bool IsDefaultEditorWorldActor(const AActor* A)
{
    if(!A) return false;
    const FString ClassPath=A->GetClass()->GetPathName();
    return ClassPath==TEXT("/Script/Engine.WorldPartitionMiniMap") ||
        ClassPath==TEXT("/Script/Engine.WorldDataLayers") ||
        ClassPath==TEXT("/Script/GameplayDebugger.GameplayDebuggerPlayerManager") ||
        ClassPath==TEXT("/Script/NavigationSystem.AbstractNavData") ||
        (ClassPath==TEXT("/Script/Engine.Actor") && A->GetName()==TEXT("ChaosDebugDrawActor"));
}
bool Read(ALandscape* L, const FGuid& Layer, FIntRect& B, TArray<uint16>& Heights)
{
    ULandscapeInfo* Info=L?L->GetLandscapeInfo():nullptr;
    int32 X1,Y1,X2,Y2;
    return Info && Info->GetLandscapeExtent(X1,Y1,X2,Y2) && X2>=X1 && Y2>=Y1 &&
        ReadRegion(L,Layer,FIntRect(X1,Y1,X2+1,Y2+1),B,Heights);
}
FString Fingerprint(UWorld* W, ALandscape* L, const FIntRect& Bounds, const TArray<uint16>& H)
{
    FString S = W->GetPathName() + FString::FromInt(W->GetOutermost()->IsDirty());
    if (L)
    {
        S += L->GetPathName() + L->GetTransform().ToString() + L->GetLandscapeGuid().ToString();
        S += FString::Printf(TEXT("%d,%d,%d,%d:"),Bounds.Min.X,Bounds.Min.Y,Bounds.Max.X,Bounds.Max.Y);
        if(H.Num()) S += Hash(H);
        for (const FLandscapeLayer& Layer : L->GetLayersConst()) S += Layer.EditLayer ? Layer.EditLayer->GetGuid().ToString() + Layer.EditLayer->GetName().ToString() + FString::FromInt(Layer.EditLayer->IsLocked()) + FString::FromInt(Layer.EditLayer->IsVisible()) : TEXT("invalid-layer");
    }
    return FMD5::HashAnsiString(*S);
}
bool HasOnlyDefaultEditorActors(UWorld* W)
{
    if(!W) return false;
    for(TActorIterator<AActor> It(W);It;++It)
    {
        AActor* A=*It;
        if(IsValid(A) && !A->HasAnyFlags(RF_Transient) && A!=W->GetWorldSettings() && A!=W->GetDefaultBrush() &&
            A->GetClass()->GetPathName()!=TEXT("/Script/Engine.DefaultPhysicsVolume") && !IsDefaultEditorWorldActor(A)) return false;
    }
    return true;
}
bool EmptyTestWorld(UWorld* W)
{
    if(!W || !W->GetOutermost()->GetName().StartsWith(TEXT("/Temp/Untitled")) || W->GetStreamingLevels().Num()!=0) return false;
    return HasOnlyDefaultEditorActors(W);
}
bool TestMap(const FString& Name)
{
    if (!Name.StartsWith(TestRoot)) return false;
    const FString Leaf = Name.Mid(TestRoot.Len());
    if (Leaf.IsEmpty() || Leaf.Len() > 64 || !FChar::IsAlpha(Leaf[0])) return false;
    for (TCHAR C : Leaf) if (!FChar::IsAlnum(C) && C != '_') return false;
    return true;
}
bool HasNoLandscapeActorsOrProxies(UWorld* W)
{
    if(!W) return false;
    for(TActorIterator<ALandscapeProxy> It(W);It;++It) return false;
    int32 Total=0,Loaded=0,Unloaded=0;
    CountLandscapeStreamingProxies(W,Total,Loaded,Unloaded);
    return Total==0;
}
bool ApprovedInPlaceLandscapeWorld(UWorld* W)
{
    if(!W || W->GetOutermost()->GetName()!=InPlaceLandscapeWorld || W->GetOutermost()->IsDirty() ||
        W->GetStreamingLevels().Num()!=0 || !W->PersistentLevel->IsUsingExternalActors()) return false;
    UWorldPartition* Partition=W->GetWorldPartition();
    return Partition && Partition->IsStreamingEnabled() && Partition->GetActorDescContainerInstance() &&
        IsEditorStreamingAvailable(W) && W->GetSubsystem<UWorldPartitionSubsystem>() &&
        W->GetSubsystem<ULandscapeSubsystem>();
}
bool BackupExternalLandscapePackages(ALandscape* Landscape,const FString& BackupRoot,TArray<FString>& Manifest)
{
    ULandscapeInfo* Info=Landscape?Landscape->GetLandscapeInfo():nullptr;
    if(!Info) return false;
    TSet<FString> Packages;
    Info->ForEachLandscapeProxy([&Packages](ALandscapeProxy* Proxy)
    {
        if(Proxy)
            if(UPackage* Package=Proxy->GetExternalPackage()) Packages.Add(Package->GetName());
        return true;
    });
    for(const FString& PackageName:Packages)
    {
        const FString Source=FPackageName::LongPackageNameToFilename(PackageName,FPackageName::GetAssetPackageExtension());
        if(!IFileManager::Get().FileExists(*Source)) continue;
        FString Relative=PackageName; Relative.ReplaceInline(TEXT("/"),TEXT("\\")); Relative.RemoveFromStart(TEXT("\\"));
        const FString Destination=FPaths::Combine(BackupRoot,TEXT("external"),Relative+FPackageName::GetAssetPackageExtension());
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(Destination),true);
        if(IFileManager::Get().Copy(*Destination,*Source,false)!=COPY_OK || IFileManager::Get().FileSize(*Destination)!=IFileManager::Get().FileSize(*Source)) return false;
        const FMD5Hash SourceHash=FMD5Hash::HashFile(*Source), BackupHash=FMD5Hash::HashFile(*Destination);
        if(!SourceHash.IsValid() || SourceHash!=BackupHash) return false;
        Manifest.Add(PackageName+TEXT("|")+LexToString(SourceHash));
    }
    return true;
}
bool ExternalLandscapePackagesClean(ALandscape* Landscape)
{
    ULandscapeInfo* Info=Landscape?Landscape->GetLandscapeInfo():nullptr;
    if(!Info) return false;
    bool bClean=true;
    Info->ForEachLandscapeProxy([&bClean](ALandscapeProxy* Proxy)
    {
        if(Proxy)
            if(UPackage* Package=Proxy->GetExternalPackage())
            {
                const FString Filename=FPackageName::LongPackageNameToFilename(Package->GetName(),FPackageName::GetAssetPackageExtension());
                bClean &= !Package->IsDirty() && IFileManager::Get().FileExists(*Filename);
            }
        return true;
    });
    return bClean;
}
bool SafeCreateSourceWorld(UWorld* W)
{
    if(!W) return false;
    if(EmptyTestWorld(W)) return true;
    if(W->GetOutermost()->GetName()==TEXT("/Engine/Maps/Entry") && !W->GetOutermost()->IsDirty() &&
        W->GetStreamingLevels().Num()==0 && !W->PersistentLevel->IsUsingExternalActors()) return true;
    return TestMap(W->GetOutermost()->GetName()) && !W->GetOutermost()->IsDirty() && W->GetStreamingLevels().Num()==0;
}
void Frame(ALandscape* L, const FIntRect& B)
{
    FVector Scale=L->GetActorScale3D();
    FVector Center=L->GetActorLocation()+FVector((B.Min.X+B.Max.X-1)*.5*Scale.X,(B.Min.Y+B.Max.Y-1)*.5*Scale.Y,0);
    double Span=FMath::Max(B.Width()*FMath::Abs(Scale.X),B.Height()*FMath::Abs(Scale.Y));
    FVector Eye=Center+FVector(.85*Span,-.85*Span,.9*Span);
    for(FLevelEditorViewportClient* Client:GEditor->GetLevelViewportClients()) if(Client && Client->IsPerspective())
    {
        Client->SetViewLocation(Eye); Client->SetViewRotation((Center-Eye).Rotation());
        Client->SetViewMode(VMI_Lit); Client->Invalidate();
    }
    GEditor->RedrawLevelEditingViewports();
}
TSharedRef<FJsonObject> Inspect(ALandscape* L, UWorld* W)
{
    auto D = MakeShared<FJsonObject>();
    D->SetStringField(TEXT("actor_path"), L->GetPathName());
    D->SetStringField(TEXT("guid"), L->GetLandscapeGuid().ToString());
    D->SetStringField(TEXT("landscape_guid"),L->GetLandscapeGuid().ToString());
    D->SetStringField(TEXT("active_world_path"),W?W->GetPathName():FString());
    D->SetStringField(TEXT("actor_world_path"),L->GetWorld()?L->GetWorld()->GetPathName():FString());
    D->SetBoolField(TEXT("actor_in_active_world"),W && L->GetWorld()==W);
    ULandscapeInfo* Info=L->GetLandscapeInfo();
    int32 ComponentCount=0, RegisteredComponentCount=0, CollisionCount=0, RegisteredCollisionCount=0;
    int32 ProxyCount=0, StreamingProxyCount=0, ExternalProxyCount=0;
    int32 DescriptorProxyCount=0, ActiveWorldProxyCount=0, NotInActiveWorldProxyCount=0;
    CountLandscapeStreamingProxies(W,DescriptorProxyCount,ActiveWorldProxyCount,NotInActiveWorldProxyCount);
    if(Info)
    {
        Info->ForAllLandscapeComponents([&](ULandscapeComponent* Component)
        {
            ++ComponentCount;
            if(Component->IsRegistered()) ++RegisteredComponentCount;
            if(ULandscapeHeightfieldCollisionComponent* Collision=Component->GetCollisionComponent())
            { ++CollisionCount; if(Collision->IsRegistered()) ++RegisteredCollisionCount; }
        });
        Info->ForEachLandscapeProxy([&ProxyCount,&StreamingProxyCount,&ExternalProxyCount](ALandscapeProxy* Proxy)
        {
            ++ProxyCount;
            StreamingProxyCount+=Proxy->IsA<ALandscapeStreamingProxy>()?1:0;
            ExternalProxyCount+=Proxy->GetExternalPackage()!=nullptr?1:0;
            return true;
        });
        int32 X1,Y1,X2,Y2;
        if(Info->GetLandscapeExtent(X1,Y1,X2,Y2))
        {
            D->SetNumberField(TEXT("vertices_x"),X2-X1+1);
            D->SetNumberField(TEXT("vertices_y"),Y2-Y1+1);
        }
    }
    D->SetNumberField(TEXT("component_count"), ComponentCount);
    D->SetNumberField(TEXT("registered_component_count"),RegisteredComponentCount);
    D->SetNumberField(TEXT("collision_component_count"),CollisionCount);
    D->SetNumberField(TEXT("registered_collision_component_count"),RegisteredCollisionCount);
    D->SetNumberField(TEXT("landscape_proxy_count"),ProxyCount);
    D->SetNumberField(TEXT("streaming_proxy_count"),StreamingProxyCount);
    const FGuid RootLandscapeGuid=L->GetLandscapeGuid();
    AddStreamingDiagnostics(D,W,nullptr,&RootLandscapeGuid);
    D->SetNumberField(TEXT("external_proxy_package_count"),ExternalProxyCount);
    D->SetBoolField(TEXT("edit_layers"), L->HasLayersContent());
    D->SetBoolField(TEXT("world_partition"), W->GetWorldPartition() != nullptr);
    D->SetBoolField(TEXT("world_partition_streaming"), W->GetWorldPartition() && W->GetWorldPartition()->IsStreamingEnabled());
    D->SetBoolField(TEXT("dirty"), W->GetOutermost()->IsDirty());
    D->SetBoolField(TEXT("layers_up_to_date"),L->IsUpToDate());
    TArray<TSharedPtr<FJsonValue>> Layers;
    for (const FLandscapeLayer& Layer : L->GetLayersConst())
    {
        if (!Layer.EditLayer) continue;
        auto O = MakeShared<FJsonObject>(); O->SetStringField(TEXT("name"), Layer.EditLayer->GetName().ToString());
        O->SetStringField(TEXT("guid"), Layer.EditLayer->GetGuid().ToString());
        FIntRect B; TArray<uint16> H;
        O->SetBoolField(TEXT("height_read_supported"),false);
        if (Read(L, Layer.EditLayer->GetGuid(), B, H))
        {
            O->SetBoolField(TEXT("height_read_supported"),true);
            O->SetStringField(TEXT("height_sha_md5"), Hash(H));
            uint16 Min = 65535, Max = 0; for (uint16 V : H) { Min = FMath::Min(Min,V); Max = FMath::Max(Max,V); }
            O->SetNumberField(TEXT("min_local_cm"), (int32(Min)-32768)*L->GetActorScale3D().Z/128.0);
            O->SetNumberField(TEXT("max_local_cm"), (int32(Max)-32768)*L->GetActorScale3D().Z/128.0);
            O->SetNumberField(TEXT("vertices_x"), B.Width()); O->SetNumberField(TEXT("vertices_y"), B.Height());
        }
        Layers.Add(MakeShared<FJsonValueObject>(O));
    }
    D->SetArrayField(TEXT("layers"), Layers);
    D->SetBoolField(TEXT("mutation_supported"), TestMap(W->GetOutermost()->GetName()) &&
        (W->GetWorldPartition()!=nullptr || (!W->PersistentLevel->IsUsingExternalActors() && !L->GetExternalPackage())) &&
        ComponentCount<=MaxComponents && DescriptorProxyCount==ActiveWorldProxyCount+NotInActiveWorldProxyCount);
    return D;
}

void AddWorldTransitionDiagnostics(UWorld* World,TSharedRef<FJsonObject> Data)
{
    TSharedRef<FJsonObject> Diagnostics=MakeShared<FJsonObject>();
    Diagnostics->SetStringField(TEXT("outgoing_world"),World?World->GetPathName():FString());
    Diagnostics->SetNumberField(TEXT("transaction_queue_length"),GEditor&&GEditor->Trans?GEditor->Trans->GetQueueLength():0);
    Diagnostics->SetNumberField(TEXT("transaction_undo_count"),GEditor&&GEditor->Trans?GEditor->Trans->GetUndoCount():0);
    bool bLandscapeModeActive=false;
    if(GEditor)
    {
        if(ULevelEditorSubsystem* LevelEditorSubsystem=GEditor->GetEditorSubsystem<ULevelEditorSubsystem>())
        {
            if(FEditorModeTools* ModeManager=LevelEditorSubsystem->GetLevelEditorModeManager())
                bLandscapeModeActive=ModeManager->GetActiveMode(FBuiltinEditorModes::EM_Landscape)!=nullptr;
        }
    }
    Diagnostics->SetBoolField(TEXT("landscape_editor_mode_active"),bLandscapeModeActive);

    FString HeightmapPath,HeightmapReferenceChain,WorldReferenceChain,PackageReferenceChain;
    bool bHeightmapInTransactionBuffer=false;
    if(World)
    {
        FReferenceChainSearch WorldSearch(World,EReferenceChainSearchMode::Shortest);
        WorldReferenceChain=WorldSearch.GetRootPath(World);
        if(UPackage* WorldPackage=World->GetOutermost())
        {
            FReferenceChainSearch PackageSearch(WorldPackage,EReferenceChainSearchMode::Shortest);
            PackageReferenceChain=PackageSearch.GetRootPath(WorldPackage);
        }
        for(TActorIterator<ALandscape> LandscapeIt(World);LandscapeIt && HeightmapPath.IsEmpty();++LandscapeIt)
        {
            ALandscape* Landscape=*LandscapeIt;
            for(const FLandscapeLayer& Layer:Landscape->GetLayersConst())
            {
                if(!Layer.EditLayer) continue;
                for(ULandscapeComponent* Component:Landscape->LandscapeComponents)
                {
                    UTexture2D* Heightmap=Component?Component->GetHeightmap(Layer.EditLayer->GetGuid()):nullptr;
                    if(!Heightmap) continue;
                    HeightmapPath=Heightmap->GetPathName();
                    bHeightmapInTransactionBuffer=GEditor&&GEditor->Trans&&GEditor->Trans->IsObjectInTransactionBuffer(Heightmap);
                    FReferenceChainSearch Search(Heightmap,EReferenceChainSearchMode::Shortest);
                    HeightmapReferenceChain=Search.GetRootPath(Heightmap);
                    break;
                }
                if(!HeightmapPath.IsEmpty()) break;
            }
        }
    }
    Diagnostics->SetStringField(TEXT("heightmap_object"),HeightmapPath);
    Diagnostics->SetStringField(TEXT("heightmap_reference_chain_before_transition"),HeightmapReferenceChain);
    Diagnostics->SetStringField(TEXT("outgoing_world_reference_chain_before_transition"),WorldReferenceChain);
    Diagnostics->SetStringField(TEXT("outgoing_package_reference_chain_before_transition"),PackageReferenceChain);
    Diagnostics->SetBoolField(TEXT("heightmap_in_editor_transaction_buffer"),bHeightmapInTransactionBuffer);
    Data->SetObjectField(TEXT("world_transition_diagnostics"),Diagnostics);
    UE_LOG(LogTemp,Display,TEXT("Forge Landscape transition diagnostics: outgoing=%s landscape_mode=%s heightmap=%s transaction_ref=%s heightmap_chain=%s world_chain=%s package_chain=%s"),
        World?*World->GetPathName():TEXT("<none>"),bLandscapeModeActive?TEXT("true"):TEXT("false"),*HeightmapPath,
        bHeightmapInTransactionBuffer?TEXT("true"):TEXT("false"),*HeightmapReferenceChain,*WorldReferenceChain,*PackageReferenceChain);
}
}

bool FForgeLandscape::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* C, const TCHAR* M) { Code=C; Message=M; return false; };
    if (!IsInGameThread()) return Fail(TEXT("wrong_thread"), TEXT("Landscape requires the editor game thread."));
    if (bWorldTransitionInProgress) return Fail(TEXT("world_transition_in_progress"), TEXT("A ForgeMCP map transition is already in progress; retry after the current editor tick."));
    UWorld* W = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!W || GEditor->PlayWorld || GEditor->bIsSimulatingInEditor) return Fail(TEXT("editor_not_idle"), TEXT("Stop PIE/simulation before Landscape operations."));
    if (Command == TEXT("landscape_job_status") || Command == TEXT("landscape_job_cancel"))
    {
        FString Id; Args->TryGetStringField(TEXT("job_id"), Id); FJob* J = Jobs.Find(Id);
        if (Command == TEXT("landscape_job_cancel"))
        {
            FString Confirm; Args->TryGetStringField(TEXT("confirmation"), Confirm);
            if (Confirm != Id) return Fail(TEXT("confirmation_required"), TEXT("Confirmation must equal job_id."));
            if(FLoader* Loader=Loaders.Find(Id))
            {
                UWorld* LoaderWorld=Loader->World.Get();
                UWorldPartition* Partition=LoaderWorld?LoaderWorld->GetWorldPartition():nullptr;
                UWorldPartitionEditorLoaderAdapter* Adapter=Loader->Adapter.Get();
                if(Loader->State!=TEXT("unloaded") && Loader->State!=TEXT("transition_failed") && Partition && Adapter && Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
                {
                    if(Adapter->GetLoaderAdapter()) Adapter->GetLoaderAdapter()->Unload();
                    Loader->bTargetLoaded=false; Loader->State=TEXT("unloading"); Loader->Deadline=FPlatformTime::Seconds()+30.0;
                }
                Data->SetStringField(TEXT("job_id"),Id); Data->SetStringField(TEXT("state"),Loader->State);
                Data->SetStringField(TEXT("error"),Loader->Error); Data->SetBoolField(TEXT("saved"),false);
                AddStreamingDiagnostics(Data,LoaderWorld,&Loader->WorldBounds);
                int32 Total=0,Loaded=0,Unloaded=0; CountLandscapeStreamingProxies(LoaderWorld,Total,Loaded,Unloaded,&Loader->WorldBounds);
                Data->SetNumberField(TEXT("progress"),Total?double(Total-Loaded)/Total:1.0);
                return true;
            }
            if(!J) return Fail(TEXT("job_not_found"), TEXT("Unknown session-local Landscape job or loader."));
            if (J->State == TEXT("running"))
            {
                J->State = J->NextRow ? TEXT("cancelled_partial") : TEXT("cancelled");
                J->Plan.Before.Empty(); J->Plan.After.Empty();
            }
        }
        else if(FLoader* Loader=Loaders.Find(Id))
        {
            UWorld* LoaderWorld=Loader->World.Get();
            int32 Total=0,Loaded=0,Unloaded=0; CountLandscapeStreamingProxies(LoaderWorld,Total,Loaded,Unloaded,&Loader->WorldBounds);
            Data->SetStringField(TEXT("job_id"),Id); Data->SetStringField(TEXT("state"),Loader->State);
            Data->SetStringField(TEXT("loader_id"),Id); Data->SetStringField(TEXT("error"),Loader->Error);
            Data->SetBoolField(TEXT("target_loaded"),Loader->bTargetLoaded);
            Data->SetNumberField(TEXT("progress"),Total?(Loader->bTargetLoaded?double(Loaded)/Total:double(Total-Loaded)/Total):0.0);
            AddStreamingDiagnostics(Data,LoaderWorld,&Loader->WorldBounds);
            Data->SetBoolField(TEXT("saved"),false); Data->SetBoolField(TEXT("height_readback_validated"),false);
            return true;
        }
        else if(!J) return Fail(TEXT("job_not_found"), TEXT("Unknown session-local Landscape job or loader."));
        Data->SetStringField(TEXT("job_id"),Id); Data->SetStringField(TEXT("state"),J->State);
        Data->SetStringField(TEXT("error"),J->Error); Data->SetStringField(TEXT("backup"),J->Backup);
        const auto& R = J->Plan.Request->GetArrayField(TEXT("region"));
        int32 Rows = int32(R[3]->AsNumber()-R[1]->AsNumber()+1);
        Data->SetNumberField(TEXT("rows_applied"), J->NextRow); Data->SetNumberField(TEXT("total_rows"), Rows);
        Data->SetNumberField(TEXT("progress"), double(J->NextRow)/Rows);
        Data->SetNumberField(TEXT("max_stage_ms"),J->MaxStageMs);
        Data->SetBoolField(TEXT("height_readback_validated"),J->bHeightReadbackValidated);
        Data->SetBoolField(TEXT("collision_height_validated"),false);
        Data->SetBoolField(TEXT("collision_validation_deferred_until_save_reload"),true);
        Data->SetStringField(TEXT("collision_height_source"),TEXT("deferred_until_save_reload"));
        if(J->bHeightReadbackValidated) Data->SetStringField(TEXT("validated_after_height_md5"),J->ValidatedAfterHash);
        Data->SetBoolField(TEXT("saved"),false);
        return true;
    }
    if (Command == TEXT("landscape_info"))
    {
        FString Path; Args->TryGetStringField(TEXT("actor_path"),Path);
        TArray<TSharedPtr<FJsonValue>> List; int32 Total=0;
        for (TActorIterator<ALandscape> It(W); It; ++It)
        {
            if (Path.IsEmpty() || Path == It->GetPathName())
            { ++Total; if(List.Num()<64) List.Add(MakeShared<FJsonValueObject>(Inspect(*It,W))); }
        }
        Data->SetNumberField(TEXT("total_count"),Total); Data->SetBoolField(TEXT("truncated"),Total>List.Num());
        Data->SetArrayField(TEXT("landscapes"),List); Data->SetBoolField(TEXT("world_partition"),W->GetWorldPartition()!=nullptr);
        Data->SetNumberField(TEXT("streaming_level_count"),W->GetStreamingLevels().Num());
        Data->SetBoolField(TEXT("persistent_level_uses_external_actors"),W->PersistentLevel->IsUsingExternalActors());
        Data->SetBoolField(TEXT("empty_untitled_world"),EmptyTestWorld(W));
        Data->SetBoolField(TEXT("safe_create_source"),SafeCreateSourceWorld(W));
        Data->SetStringField(TEXT("world"), W->GetPathName());
        return true;
    }
    for (const auto& Entry : Jobs) if (Entry.Value.State == TEXT("running")) return Fail(TEXT("landscape_busy"),TEXT("Wait for or cancel the active terrain job."));
    const bool bPartitionedTestWorld=W->GetWorldPartition()!=nullptr && TestMap(W->GetOutermost()->GetName());
    const bool bSafeIsolatedSource=SafeCreateSourceWorld(W);
    const bool bApprovedInPlaceLandscapeWorld=ApprovedInPlaceLandscapeWorld(W);
    if(W->GetStreamingLevels().Num() || ((W->GetWorldPartition() && !bPartitionedTestWorld) && !bSafeIsolatedSource && !bApprovedInPlaceLandscapeWorld) ||
        (!W->GetWorldPartition() && W->PersistentLevel->IsUsingExternalActors() && !bSafeIsolatedSource))
        return Fail(TEXT("unsupported_world"),TEXT("Streaming sublevels and non-test World Partition maps are read-only; Landscape writes require an isolated test map."));
    if (Command == TEXT("landscape_preview"))
    {
        const double PreviewStarted=FPlatformTime::Seconds();
        const TSharedPtr<FJsonObject>* Obj=nullptr;
        if (!Args->TryGetObjectField(TEXT("request"),Obj)) return Fail(TEXT("invalid_request"),TEXT("Expected a typed Landscape request."));
        auto R=(*Obj).ToSharedRef(); FString Action;
        if (!R->TryGetStringField(TEXT("action"),Action)) return Fail(TEXT("invalid_action"),TEXT("Missing action."));
        const TSet<FString> Actions={TEXT("create"),TEXT("create_in_place"),TEXT("raise"),TEXT("lower"),TEXT("flatten"),TEXT("smooth"),TEXT("generate"),TEXT("apply_heightmap"),TEXT("coastline"),TEXT("frame"),TEXT("save"),TEXT("reload"),TEXT("load_region"),TEXT("unload_region")};
        if (!Actions.Contains(Action)) return Fail(TEXT("invalid_action"),TEXT("Unsupported Landscape action."));
        FPlan P; P.World=W; P.Request=R; P.Expires=FPlatformTime::Seconds()+300;
        if (Action == TEXT("create") || Action == TEXT("create_in_place"))
        {
            const bool bInPlace=Action==TEXT("create_in_place");
            FString Path; R->TryGetStringField(TEXT("map_path"),Path);
            if(bInPlace)
            {
                bool bWorldPartition=false; R->TryGetBoolField(TEXT("world_partition"),bWorldPartition);
                if(!bWorldPartition || !Path.IsEmpty() || !ApprovedInPlaceLandscapeWorld(W))
                    return Fail(TEXT("in_place_world_not_approved"),TEXT("create_in_place requires the exact saved Phase6C Empty Open World map with World Partition streaming and editor-region loading already enabled."));
                if(!HasNoLandscapeActorsOrProxies(W)) return Fail(TEXT("landscape_exists"),TEXT("The approved in-place test world already contains a loaded or unloaded Landscape actor or streaming proxy."));
                for(const auto& Entry:Loaders) if(Entry.Value.World.Get()==W) return Fail(TEXT("landscape_loader_active"),TEXT("Release active Landscape region loaders before creating in this World Partition map."));
                Data->SetStringField(TEXT("existing_world"),W->GetPathName());
                Data->SetBoolField(TEXT("existing_world_partition_enabled"),true);
                Data->SetBoolField(TEXT("existing_world_partition_subsystem_available"),true);
                Data->SetBoolField(TEXT("existing_landscape_subsystem_available"),true);
            }
            else
            {
                if (!TestMap(Path) || FPackageName::DoesPackageExist(Path) || FindPackage(nullptr,*Path)) return Fail(TEXT("invalid_destination"),TEXT("Creation requires an absent disposable test-map path."));
                if (!SafeCreateSourceWorld(W)) return Fail(TEXT("isolated_world_required"),TEXT("Create requires the clean Engine Entry map, an empty untitled world, or a clean saved ForgeMCP Landscape test map."));
                if(EmptyTestWorld(W)) for (TActorIterator<ALandscapeProxy> It(W); It; ++It) return Fail(TEXT("landscape_exists"),TEXT("The disposable world already contains a Landscape."));
            }
            bool bUseEngineBasicMaterial=false;
            if(R->HasField(TEXT("use_engine_basic_landscape_material")) &&
                !R->TryGetBoolField(TEXT("use_engine_basic_landscape_material"),bUseEngineBasicMaterial))
                return Fail(TEXT("invalid_material_option"),TEXT("use_engine_basic_landscape_material must be boolean."));
            if(bUseEngineBasicMaterial && !LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial")))
                return Fail(TEXT("visual_material_unavailable"),TEXT("The engine BasicShapeMaterial is unavailable for this isolated visual test."));
            double CX,CY,Q,Sections,XY,Z,Grid=2; bool bWorldPartition=false;
            R->TryGetBoolField(TEXT("world_partition"),bWorldPartition);
            R->TryGetNumberField(TEXT("partition_grid_size_components"),Grid);
            if (!Number(R,TEXT("components_x"),CX,1,256,true) || !Number(R,TEXT("components_y"),CY,1,256,true) ||
                !Number(R,TEXT("quads_per_section"),Q,7,255,true) || !(Q==7 || Q==15 || Q==31 || Q==63 || Q==127 || Q==255) ||
                !Number(R,TEXT("sections_per_component"),Sections,1,2,true) || !(Sections==1 || Sections==2) ||
                !Number(R,TEXT("xy_scale_cm"),XY,1,1000) || !Number(R,TEXT("z_scale"),Z,1,1000)) return Fail(TEXT("invalid_dimensions"),TEXT("Invalid Landscape topology or scale."));
            const int64 Width=int64(CX)*int64(Q)*int64(Sections)+1, Height=int64(CY)*int64(Q)*int64(Sections)+1;
            if(CX*CY>MaxComponents || Width>MaxAxisVertices || Height>MaxAxisVertices || Width*Height>MaxSamples)
                return Fail(TEXT("resource_limit"),TEXT("Landscape exceeds the 1,024-component, 8192-vertex-axis or 4,194,304-sample resource limit."));
            if(bWorldPartition && (!Number(R,TEXT("partition_grid_size_components"),Grid,1,256,true) || Grid<1))
                return Fail(TEXT("invalid_partition_grid"),TEXT("World Partition requires an integer component grid size from 1 through 256."));
            if (!bInPlace)
            {
                FString MapFilename, ActorRoot, ObjectRoot, WorldStateFilename, ScopeError;
                TArray<FString> HLODPackageNames;
                const FString TargetMapPackage = R->GetStringField(TEXT("map_path"));
                if (!CheckCreateDestinationsAbsent(TargetMapPackage, MapFilename, ActorRoot, ObjectRoot,
                    HLODPackageNames, WorldStateFilename, ScopeError, bWorldPartition))
                    return Fail(TEXT("write_scope_rejected"), *ScopeError);
                P.TargetMapPackage = TargetMapPackage;
                P.TargetMapFilename = CanonicalPath(MapFilename);
                P.TargetExternalActorsRoot = CanonicalPath(ActorRoot);
                P.TargetExternalObjectsRoot = CanonicalPath(ObjectRoot);

                FString DisposableBlockReason;
                const bool bDisposableProject = IsAuthorizedDisposableProject(DisposableBlockReason);
                TSharedRef<FJsonObject> DirtyPolicy = MakeShared<FJsonObject>();
                const bool bDirtyInventoryComplete = ForgeDirtyPackages::InspectLandscapeApplyPreflight(
                    W, bDisposableProject, DirtyPolicy);
                double BlockingDirtyCountValue = 0.0;
                DirtyPolicy->TryGetNumberField(TEXT("blocking_dirty_loaded_packages"), BlockingDirtyCountValue);
                const int32 BlockingDirtyCount = static_cast<int32>(BlockingDirtyCountValue);

                const bool bWorldPartitionEditorLoaded = FModuleManager::Get().IsModuleLoaded(TEXT("WorldPartitionEditor"));
                const bool bWorldPartitionEditorReady = bWorldPartitionEditorLoaded &&
                    IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor();
                const bool bPreflightReady = !bWorldPartition || bWorldPartitionEditorReady;
                const bool bDirtyPolicyBlocks = ForgeDirtyPackages::IsLandscapeApplyPreflightBlocking(
                    bDirtyInventoryComplete, BlockingDirtyCount);
                P.bApplyAllowed = bDisposableProject && !bDirtyPolicyBlocks && bPreflightReady;
                if (!bDisposableProject) P.ApplyBlockReason = DisposableBlockReason;
                if (bDirtyPolicyBlocks)
                {
                    if (!P.ApplyBlockReason.IsEmpty()) P.ApplyBlockReason += TEXT("; ");
                    P.ApplyBlockReason += TEXT("The loaded dirty-package preflight is incomplete or found blocking dirty packages; unresolved packages block Apply.");
                }
                if (!bPreflightReady)
                {
                    if (!P.ApplyBlockReason.IsEmpty()) P.ApplyBlockReason += TEXT("; ");
                    P.ApplyBlockReason += TEXT("World Partition Editor support or editor-region loading is unavailable before map transition.");
                }
                TSharedRef<FJsonObject> WriteScope = MakeCreateWriteScope(TargetMapPackage, MapFilename,
                    ActorRoot, ObjectRoot, HLODPackageNames, WorldStateFilename, bWorldPartition, true, true, true);
                Data->SetObjectField(TEXT("write_scope"), WriteScope);
                Data->SetObjectField(TEXT("dirty_package_preflight"), DirtyPolicy);
                Data->SetBoolField(TEXT("disposable_project_verified"), bDisposableProject);
                Data->SetBoolField(TEXT("world_partition_preflight_ready"), bPreflightReady);
                Data->SetBoolField(TEXT("apply_allowed"), P.bApplyAllowed);
                Data->SetStringField(TEXT("apply_block_reason"), P.ApplyBlockReason);
            }
            else
            {
                P.bApplyAllowed = false;
                P.ApplyBlockReason = TEXT("In-place Landscape creation is not enabled by the disposable-project write-scope policy.");
                Data->SetBoolField(TEXT("apply_allowed"), false);
                Data->SetStringField(TEXT("apply_block_reason"), P.ApplyBlockReason);
            }
        }
        else
        {
            const bool bApprovedExistingWorldPartitionOperation=(Action==TEXT("load_region") || Action==TEXT("unload_region")) && ApprovedInPlaceLandscapeWorld(W);
            if (!TestMap(W->GetOutermost()->GetName()) && !bApprovedExistingWorldPartitionOperation)
                return Fail(TEXT("protected_world"),TEXT("Terrain mutation is limited to disposable Landscape test maps; the approved Phase6C Open World map permits only its bounded load_region and unload_region operations."));
            const bool bPartitionOperation=Action==TEXT("load_region") || Action==TEXT("unload_region");
            if(bPartitionOperation && !W->GetWorldPartition()) return Fail(TEXT("world_partition_required"),TEXT("Region loading requires an isolated World Partition test map."));
            if(bPartitionOperation && !IsEditorStreamingAvailable(W))
                return Fail(TEXT("editor_streaming_disabled"),TEXT("Real region transitions require World Partition streaming enabled for this map and dynamic loading enabled in the Editor."));
            FString Path; R->TryGetStringField(TEXT("actor_path"),Path);
            ALandscape* L=Resolve(W,Path);
            if(Action==TEXT("unload_region"))
            {
                FString LoaderId; R->TryGetStringField(TEXT("partition_loader_id"),LoaderId);
                FLoader* Existing=Loaders.Find(LoaderId);
                if(!Existing || Existing->World.Get()!=W || !Existing->Adapter.IsValid() || !Existing->Adapter->GetLoaderAdapter() || !Existing->Adapter->GetLoaderAdapter()->GetUserCreated()) return Fail(TEXT("loader_not_found"),TEXT("unload_region requires a live user-created Forge loader for this World Partition test map."));
                if(L && Existing->Actor.IsValid() && L!=Existing->Actor.Get()) return Fail(TEXT("loader_actor_mismatch"),TEXT("The loader belongs to a different Landscape actor."));
                P.Actor=Existing->Actor.Get(); P.Layer=Existing->LandscapeGuid; P.Bounds=Existing->Bounds;
                if(P.Actor.IsValid()) P.Transform=P.Actor->GetActorTransform();
            }
            else
            {
                P.Actor=L;
                int32 LoadedComponentCount=0;
                if(L && L->GetLandscapeInfo()) L->GetLandscapeInfo()->ForAllLandscapeComponents([&LoadedComponentCount](ULandscapeComponent*) { ++LoadedComponentCount; });
                if (!L || (!W->GetWorldPartition() && L->GetExternalPackage()) || !L->HasLayersContent() || L->GetLayersConst().Num()!=1 || LoadedComponentCount>MaxComponents || L->GetLevel()!=W->PersistentLevel ||
                    !L->GetActorRotation().IsNearlyZero() || L->GetActorScale3D().Z <= 0) return Fail(TEXT("unsupported_landscape"),TEXT("Requires an isolated Landscape with one ForgeTerrain Edit Layer, positive scale and zero rotation."));
                const FLandscapeLayer* Layer=L->GetLayerConst(FName(TEXT("ForgeTerrain")));
                if (!Layer || !Layer->EditLayer || Layer->EditLayer->IsLocked() || !Layer->EditLayer->IsVisible()) return Fail(TEXT("unsupported_layer"),TEXT("ForgeTerrain must exist, be unlocked and visible."));
                P.Transform=L->GetActorTransform(); P.Layer=Layer->EditLayer->GetGuid();
                if(bPartitionOperation)
                {
        if(!ParseRegion(R,P.Bounds) || int64(P.Bounds.Width())*P.Bounds.Height()>1048576) return Fail(TEXT("invalid_region"),TEXT("World Partition loader bounds must be valid and no larger than 1,048,576 sample cells."));
                }
                else if(Action==TEXT("frame"))
                {
                    int32 X1,Y1,X2,Y2;
                    if(!L->GetLandscapeInfo()->GetLandscapeExtent(X1,Y1,X2,Y2) || X2<X1 || Y2<Y1) return Fail(TEXT("extent_unavailable"),TEXT("Landscape extent is unavailable."));
                    const FIntRect FullBounds(X1,Y1,X2+1,Y2+1);
                    FIntRect Requested;
                    if(!ParseRegion(R,Requested)) return Fail(TEXT("invalid_region"),TEXT("Frame region must use ordered inclusive Landscape vertex coordinates."));
                    const bool bDefaultFrameRegion=Requested.Min==FIntPoint(0,0) && Requested.Max==FIntPoint(64,64);
                    P.Bounds=bDefaultFrameRegion?FullBounds:Requested;
                    if(P.Bounds.Min.X<FullBounds.Min.X || P.Bounds.Min.Y<FullBounds.Min.Y ||
                        P.Bounds.Max.X>FullBounds.Max.X || P.Bounds.Max.Y>FullBounds.Max.Y)
                        return Fail(TEXT("region_unavailable"),TEXT("Frame region lies outside the loaded Landscape extent."));
                }
                else if(Action==TEXT("save") || Action==TEXT("reload"))
                {
                    if(!Read(L,P.Layer,P.Bounds,P.Before)) return Fail(TEXT("read_failed"),TEXT("Unable to read all Landscape heights; one or more World Partition proxies may be unloaded."));
                    if(Action==TEXT("reload") && W->GetOutermost()->IsDirty()) return Fail(TEXT("unsaved_changes"),TEXT("Save the terrain before reload."));
                }
                else
                {
                    FIntRect Requested;
                    if(!ParseRegion(R,Requested)) return Fail(TEXT("invalid_region"),TEXT("Expected ordered inclusive vertex coordinates within the 8,192-vertex axis and sample limits."));
                    const int64 RequestedSamples=int64(Requested.Width())*Requested.Height();
                    if(Action==TEXT("apply_heightmap") ? RequestedSamples>MaxHeightmapChunkSamples : RequestedSamples>MaxEditSamples)
                        return Fail(TEXT("edit_chunk_limit"),Action==TEXT("apply_heightmap")?TEXT("A heightmap input chunk is limited to 32,768 samples."):TEXT("A terrain edit chunk is limited to 1,048,576 samples."));
                    int32 FullX1,FullY1,FullX2,FullY2;
                    if(!L->GetLandscapeInfo()->GetLandscapeExtent(FullX1,FullY1,FullX2,FullY2) || FullX2<FullX1 || FullY2<FullY1) return Fail(TEXT("extent_unavailable"),TEXT("Landscape extent is unavailable."));
                    const FIntRect FullBounds(FullX1,FullY1,FullX2+1,FullY2+1);
                    if(Requested.Min.X<FullBounds.Min.X || Requested.Min.Y<FullBounds.Min.Y || Requested.Max.X>FullBounds.Max.X || Requested.Max.Y>FullBounds.Max.Y)
                        return Fail(TEXT("region_unavailable"),TEXT("The requested edit lies outside the currently loaded Landscape extent."));
                    FIntRect OperationBounds=Requested;
                    if(R->HasField(TEXT("operation_region")) && !R->HasTypedField<EJson::Null>(TEXT("operation_region")))
                    {
                        if(Action!=TEXT("raise") && Action!=TEXT("lower") && Action!=TEXT("coastline"))
                            return Fail(TEXT("invalid_operation_region"),TEXT("operation_region is only supported for chunked raise, lower or coastline edits."));
                        if(!R->HasTypedField<EJson::Array>(TEXT("operation_region")))
                            return Fail(TEXT("invalid_operation_region"),TEXT("operation_region must be a four-integer array."));
                        if(!ParseInclusiveRegion(R,TEXT("operation_region"),OperationBounds) ||
                            OperationBounds.Min.X>Requested.Min.X || OperationBounds.Min.Y>Requested.Min.Y ||
                            OperationBounds.Max.X<Requested.Max.X || OperationBounds.Max.Y<Requested.Max.Y)
                            return Fail(TEXT("invalid_operation_region"),TEXT("operation_region must be ordered and contain the requested edit chunk."));
                    }
                    const FIntRect Snapshot(FMath::Max(FullBounds.Min.X,Requested.Min.X-1),FMath::Max(FullBounds.Min.Y,Requested.Min.Y-1),
                        FMath::Min(FullBounds.Max.X,Requested.Max.X+1),FMath::Min(FullBounds.Max.Y,Requested.Max.Y+1));
                    if(!ReadRegion(L,P.Layer,Snapshot,P.Bounds,P.Before)) return Fail(TEXT("region_unavailable"),TEXT("The requested edit and one-vertex normal halo must be loaded across all touched components."));
                    P.EditBounds=Requested;
                    double H,S,Wave,Rows,Interval;
                    if (!Number(R,TEXT("height_cm"),H,-100000,100000) || !Number(R,TEXT("strength"),S,0,1) || !Number(R,TEXT("wavelength_vertices"),Wave,2,8192) || !Number(R,TEXT("rows_per_stage"),Rows,1,8,true) || !Number(R,TEXT("stage_interval_seconds"),Interval,.1,2)) return Fail(TEXT("invalid_parameters"),TEXT("Invalid finite terrain parameters."));
                    const int32 X1=Requested.Min.X,Y1=Requested.Min.Y,X2=Requested.Max.X-1,Y2=Requested.Max.Y-1;
                    const TArray<TSharedPtr<FJsonValue>>* Samples=nullptr;
                    if (Action==TEXT("apply_heightmap") && (!R->TryGetArrayField(TEXT("samples_cm"),Samples) || Samples->Num()!=Requested.Width()*Requested.Height() || Samples->Num()>MaxHeightmapChunkSamples)) return Fail(TEXT("invalid_heightmap"),TEXT("Heightmap chunk must match the region with at most 32,768 finite samples."));
                    P.After=P.Before;
                    for (int32 Y=Y1;Y<=Y2;++Y) for(int32 X=X1;X<=X2;++X)
                    {
                        int32 Index=(Y-P.Bounds.Min.Y)*P.Bounds.Width()+X-P.Bounds.Min.X;
                        double Old=(int32(P.Before[Index])-32768)*L->GetActorScale3D().Z/128.0, New=Old;
                        const int32 OperationX1=OperationBounds.Min.X,OperationY1=OperationBounds.Min.Y;
                        const int32 OperationX2=OperationBounds.Max.X-1,OperationY2=OperationBounds.Max.Y-1;
                        double DX=(X-(OperationX1+OperationX2)*.5)/FMath::Max(1.,(OperationX2-OperationX1)*.5), DY=(Y-(OperationY1+OperationY2)*.5)/FMath::Max(1.,(OperationY2-OperationY1)*.5);
                        double Falloff=.5+.5*FMath::Cos(PI*FMath::Min(1.,FMath::Sqrt(DX*DX+DY*DY)));
                        if(Action==TEXT("raise") || Action==TEXT("lower")) New=Old+(Action==TEXT("lower")?-1:1)*FMath::Abs(H)*Falloff;
                        else if(Action==TEXT("flatten")) New=FMath::Lerp(Old,H,S);
                        else if(Action==TEXT("generate")) New=H*FMath::Sin(2*PI*X/Wave)*FMath::Sin(2*PI*Y/Wave);
                        else if(Action==TEXT("coastline")) New=H*((X-OperationX1)/FMath::Max(1.,double(OperationX2-OperationX1))*2-1);
                        else if(Action==TEXT("apply_heightmap")) { if(!(*Samples)[(Y-Y1)*(X2-X1+1)+X-X1]->TryGetNumber(New) || !FMath::IsFinite(New)) return Fail(TEXT("invalid_heightmap"),TEXT("Non-finite height sample.")); }
                        else if(Action==TEXT("smooth"))
                        {
                            double Sum=0; int Count=0;
                            for(int YY=FMath::Max(P.Bounds.Min.Y,Y-1);YY<=FMath::Min(P.Bounds.Max.Y-1,Y+1);++YY)
                                for(int XX=FMath::Max(P.Bounds.Min.X,X-1);XX<=FMath::Min(P.Bounds.Max.X-1,X+1);++XX) { Sum+=P.Before[(YY-P.Bounds.Min.Y)*P.Bounds.Width()+XX-P.Bounds.Min.X];++Count; }
                            New=FMath::Lerp(Old,(Sum/Count-32768)*L->GetActorScale3D().Z/128.,S);
                        }
                        double Encoded=New*128./L->GetActorScale3D().Z+32768.;
                        if(!FMath::IsFinite(Encoded) || Encoded<0 || Encoded>65535) return Fail(TEXT("height_out_of_range"),TEXT("Requested height exceeds uint16 Landscape range at this Z scale; no clipping is performed."));
                        P.After[Index]=uint16(FMath::RoundToInt(Encoded));
                    }
                }
            }
        }
        P.Fingerprint=Fingerprint(W,P.Actor.Get(),P.Bounds,P.Before);
        for(auto It=Previews.CreateIterator();It;++It) if(It.Value().Expires<FPlatformTime::Seconds()) It.RemoveCurrent();
        int64 ReservedPreviewBytes=0;
        for(const auto& Entry:Previews) ReservedPreviewBytes+=(Entry.Value.Before.Num()+Entry.Value.After.Num())*sizeof(uint16);
        const int64 PlanBytes=(P.Before.Num()+P.After.Num())*sizeof(uint16);
        if(ReservedPreviewBytes+PlanBytes>MaxPendingPlanBytes)
            return Fail(TEXT("preview_memory_limit"),TEXT("Outstanding preview plans exceed the 15 MiB reservation, leaving 1 MiB for bounded stage arrays."));
        if(Previews.Num()>=32) return Fail(TEXT("preview_limit"),TEXT("Too many outstanding terrain previews."));
        FString Id=FGuid::NewGuid().ToString(EGuidFormats::Digits);
        const FString BeforeHash=Hash(P.Before),AfterHash=Hash(P.After); const int32 PreviewSamples=P.Before.Num();
        const int64 EditWidth=FMath::Max(0,P.EditBounds.Width());
        Previews.Add(Id,MoveTemp(P));
        Data->SetStringField(TEXT("preview_id"),Id); Data->SetObjectField(TEXT("request"),R);
        Data->SetNumberField(TEXT("expires_in_seconds"),300); Data->SetStringField(TEXT("before_height_md5"),BeforeHash); Data->SetStringField(TEXT("after_height_md5"),AfterHash);
        Data->SetNumberField(TEXT("samples"),PreviewSamples);
        Data->SetNumberField(TEXT("height_buffer_bytes"),PlanBytes);
        const int32 BatchRows=FMath::Clamp(R->GetIntegerField(TEXT("rows_per_stage")),1,8);
        const int64 StageWidth=FMath::Min<int64>(EditWidth+2,MaxAxisVertices+2);
        const int64 StageHeight=BatchRows+2;
        const int64 StageBytes=2*StageWidth*StageHeight*sizeof(uint16)+FMath::Min<int64>(EditWidth,MaxAxisVertices)*BatchRows*sizeof(uint16);
        Data->SetNumberField(TEXT("estimated_stage_buffer_bytes"),StageBytes);
        Data->SetNumberField(TEXT("working_buffer_budget_bytes"),WorkingBufferBudgetBytes);
        Data->SetNumberField(TEXT("estimated_plan_plus_stage_buffer_bytes"),PlanBytes+StageBytes);
        Data->SetNumberField(TEXT("native_preview_processing_ms"),(FPlatformTime::Seconds()-PreviewStarted)*1000.0);
        Data->SetStringField(TEXT("scope"),TEXT("Isolated test maps only; creation/readback is limited to 4,194,304 samples, edit requests are chunks up to 1,048,576 samples, heightmap input chunks are limited to 32,768 samples, pending height plans are capped at 15 MiB, and each height job writes at most eight rows per editor tick. The estimated Forge-owned plan and stage height arrays stay within 16 MiB; Unreal texture source, collision, and derived-data memory are measured separately. Cancellation retains already applied rows. Heights are Edit Layer values, not merged heights."));
        return true;
    }
    if(Command != TEXT("landscape_apply")) return Fail(TEXT("command_not_allowed"),TEXT("Unknown Landscape command."));
    FString Id,Confirm; Args->TryGetStringField(TEXT("preview_id"),Id); Args->TryGetStringField(TEXT("confirmation"),Confirm);
    if(Id.IsEmpty() || Confirm!=Id) return Fail(TEXT("confirmation_required"),TEXT("Confirmation must equal preview_id."));
    FPlan P; if(!Previews.RemoveAndCopyValue(Id,P)) return Fail(TEXT("preview_not_found"),TEXT("Preview is unknown or already consumed."));
    auto R=P.Request.ToSharedRef(); FString Action=R->GetStringField(TEXT("action"));
    const bool bPartitionOperation=Action==TEXT("load_region") || Action==TEXT("unload_region");
    if(bPartitionOperation && !TestMap(W->GetOutermost()->GetName()) && !ApprovedInPlaceLandscapeWorld(W))
        return Fail(TEXT("protected_world"),TEXT("The approved Phase6C World Partition operation can only apply in its exact isolated test map."));
    FIntRect B; TArray<uint16> Current;
    if(!bPartitionOperation && Action!=TEXT("frame") && P.Actor.IsValid() &&
        !ReadRegion(P.Actor.Get(),P.Layer,P.Bounds,B,Current)) return Fail(TEXT("read_failed"),TEXT("The preview region is no longer readable; a World Partition cell may have unloaded."));
    if(P.Expires<FPlatformTime::Seconds() || P.World.Get()!=W || Fingerprint(W,P.Actor.Get(),P.Bounds,Current)!=P.Fingerprint) return Fail(TEXT("stale_preview"),TEXT("World, transform, layer or preview-region heights changed; preview again."));
    if(Action==TEXT("create") || Action==TEXT("create_in_place"))
    {
        const bool bInPlace=Action==TEXT("create_in_place");
        if (bInPlace)
            return Fail(TEXT("in_place_creation_disabled"), TEXT("In-place Landscape creation is disabled by the disposable-project write-scope policy."));
        if(!bInPlace)
        {
            if (!P.bApplyAllowed)
                return Fail(TEXT("landscape_safety_gate_blocked"), *P.ApplyBlockReason);
            FString DisposableBlockReason;
            if (!IsAuthorizedDisposableProject(DisposableBlockReason))
                return Fail(TEXT("disposable_project_required"), *DisposableBlockReason);
            TSharedRef<FJsonObject> DirtyPolicy = MakeShared<FJsonObject>();
            const bool bDirtyInventoryComplete = ForgeDirtyPackages::InspectLandscapeApplyPreflight(
                W, true, DirtyPolicy);
            double BlockingDirtyCountValue = 0.0;
            DirtyPolicy->TryGetNumberField(TEXT("blocking_dirty_loaded_packages"), BlockingDirtyCountValue);
            const int32 BlockingDirtyCount = static_cast<int32>(BlockingDirtyCountValue);
            if (ForgeDirtyPackages::IsLandscapeApplyPreflightBlocking(
                    bDirtyInventoryComplete, BlockingDirtyCount))
            {
                Data->SetObjectField(TEXT("dirty_package_preflight"), DirtyPolicy);
                return Fail(TEXT("dirty_packages_block_apply"), TEXT("The loaded dirty-package inventory is incomplete or contains blocking dirty packages; unresolved engine or content packages block Apply, and no world transition was started."));
            }
            FString MapFilename, ActorRoot, ObjectRoot, WorldStateFilename, ScopeError;
            TArray<FString> HLODPackageNames;
            bool bWorldPartition=false; R->TryGetBoolField(TEXT("world_partition"),bWorldPartition);
            if (!CheckCreateDestinationsAbsent(P.TargetMapPackage, MapFilename, ActorRoot, ObjectRoot,
                HLODPackageNames, WorldStateFilename, ScopeError, bWorldPartition))
                return Fail(TEXT("write_scope_rejected"), *ScopeError);
            const bool bWorldPartitionEditorLoaded = FModuleManager::Get().IsModuleLoaded(TEXT("WorldPartitionEditor"));
            const bool bWorldPartitionEditorReady = bWorldPartitionEditorLoaded &&
                IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor();
            if (bWorldPartition && !bWorldPartitionEditorReady)
                return Fail(TEXT("world_partition_preflight_failed"), TEXT("World Partition Editor support or editor-region loading is unavailable before map transition."));
            FString TransitionError;
            if(!PrepareForWorldTransition(W,TransitionError)) { Code=TEXT("world_transition_blocked"); Message=TransitionError; return false; }
        }
        TGuardValue<bool> TransitionGuard(bWorldTransitionInProgress,!bInPlace);
        FString Path;
        bool bWorldPartition=false; R->TryGetBoolField(TEXT("world_partition"),bWorldPartition);
        if(bInPlace)
        {
            if(!bWorldPartition || !ApprovedInPlaceLandscapeWorld(W) || !HasNoLandscapeActorsOrProxies(W))
                return Fail(TEXT("in_place_world_changed"),TEXT("The approved World Partition map changed or is no longer eligible for in-place Landscape creation."));
            for(const auto& Entry:Loaders) if(Entry.Value.World.Get()==W) return Fail(TEXT("landscape_loader_active"),TEXT("Release active Landscape region loaders before creating in this World Partition map."));
            Path=W->GetOutermost()->GetName();
            UWorldPartition* ExistingPartition=W->GetWorldPartition();
            UWorldPartitionSubsystem* ExistingPartitionSubsystem=W->GetSubsystem<UWorldPartitionSubsystem>();
            ULandscapeSubsystem* ExistingLandscapeSubsystem=W->GetSubsystem<ULandscapeSubsystem>();
            const bool bEditorModuleLoaded=FModuleManager::Get().IsModuleLoaded(TEXT("WorldPartitionEditor"));
            const bool bEditorRegionLoadingEnabled=bEditorModuleLoaded && IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor();
            Data->SetStringField(TEXT("existing_world"),W->GetPathName());
            Data->SetBoolField(TEXT("world_partition_enabled_before_landscape"),ExistingPartition && ExistingPartition->IsStreamingEnabled());
            Data->SetBoolField(TEXT("world_partition_subsystem_available_before_landscape"),ExistingPartitionSubsystem!=nullptr);
            Data->SetBoolField(TEXT("landscape_subsystem_available_before_landscape"),ExistingLandscapeSubsystem!=nullptr);
            Data->SetBoolField(TEXT("world_partition_editor_module_available_before_landscape"),bEditorModuleLoaded);
            Data->SetBoolField(TEXT("world_partition_editor_region_loading_enabled_before_landscape"),bEditorRegionLoadingEnabled);
            Data->SetBoolField(TEXT("world_transition_performed"),false);
            Data->SetStringField(TEXT("requested_map_package_path"),W->GetOutermost()->GetName());
            Data->SetStringField(TEXT("world_package_before_landscape"),W->GetOutermost()->GetName());
            Data->SetBoolField(TEXT("existing_world_saved_before_landscape"),!W->GetOutermost()->IsDirty());
            if(!ExistingPartition || !ExistingPartition->IsStreamingEnabled() || !ExistingPartitionSubsystem ||
                !ExistingLandscapeSubsystem || !bEditorRegionLoadingEnabled)
                return Fail(TEXT("world_partition_initialization_failed"),TEXT("The existing map lost World Partition streaming, subsystem, or editor region-loading support; no Landscape was created."));
        }
        else
        {
            Path=R->GetStringField(TEXT("map_path"));
            if(!SafeCreateSourceWorld(W)) return Fail(TEXT("isolated_world_required"),TEXT("The source world changed or is not a clean disposable Landscape test source."));
            if(FPackageName::DoesPackageExist(Path) || FindPackage(nullptr,*Path)) return Fail(TEXT("destination_exists"),TEXT("Destination appeared since preview."));
            TWeakObjectPtr<UWorld> OutgoingWorld(W);
            TWeakObjectPtr<UPackage> OutgoingPackage(W->GetOutermost());
            const FString OutgoingWorldPath=W->GetPathName();
            AddWorldTransitionDiagnostics(W,Data);
            GEditor->CreateNewMapForEditing(false,bWorldPartition);
            W=GEditor->GetEditorWorldContext().World();
            if(!W || W->GetPathName()==OutgoingWorldPath) return Fail(TEXT("test_world_create_failed"),TEXT("Unreal's standard new-map workflow did not replace the outgoing editor world."));
            if(OutgoingWorld.IsValid() || OutgoingPackage.IsValid()) return Fail(TEXT("world_transition_cleanup_failed"),TEXT("Unreal returned from map creation while the outgoing world or package remained valid."));
            if(bool(W->GetWorldPartition())!=bWorldPartition) return Fail(TEXT("test_world_create_failed"),TEXT("The editor did not initialize the requested disposable world type."));
            Data->SetStringField(TEXT("map_creation_api"),TEXT("UEditorEngine::CreateNewMapForEditing"));
            Data->SetStringField(TEXT("outgoing_world_path"),OutgoingWorldPath);
            Data->SetBoolField(TEXT("outgoing_world_released"),!OutgoingWorld.IsValid());
            Data->SetBoolField(TEXT("outgoing_package_released"),!OutgoingPackage.IsValid());
            Data->SetBoolField(TEXT("world_transition_performed"),true);
            LastWorld=W;
            P.World=W;
            if(!EmptyTestWorld(W)) return Fail(TEXT("test_world_not_empty"),TEXT("New isolated test world contains unexpected actors."));
        if(bWorldPartition)
        {
            UWorldPartition* NewPartition=W->GetWorldPartition();
            if(!NewPartition) return Fail(TEXT("world_partition_initialization_failed"),TEXT("World Partition was not initialized before Landscape creation."));
            if(!NewPartition->IsStreamingEnabled()) NewPartition->SetEnableStreaming(true);
            UWorldPartitionSubsystem* PartitionSubsystem=W->GetSubsystem<UWorldPartitionSubsystem>();
            const bool bEditorModuleLoaded=FModuleManager::Get().IsModuleLoaded(TEXT("WorldPartitionEditor"));
            const bool bEditorRegionLoadingEnabled=bEditorModuleLoaded && IWorldPartitionEditorModule::Get().GetEnableLoadingInEditor();
            Data->SetBoolField(TEXT("world_partition_enabled_before_landscape"),NewPartition->IsStreamingEnabled());
            Data->SetBoolField(TEXT("world_partition_subsystem_available_before_landscape"),PartitionSubsystem!=nullptr);
            Data->SetBoolField(TEXT("world_partition_editor_module_available_before_landscape"),bEditorModuleLoaded);
            Data->SetBoolField(TEXT("world_partition_editor_region_loading_enabled_before_landscape"),bEditorRegionLoadingEnabled);
            if(!NewPartition->IsStreamingEnabled() || !PartitionSubsystem || !bEditorRegionLoadingEnabled)
                return Fail(TEXT("world_partition_initialization_failed"),TEXT("World Partition streaming, subsystem, or editor region loading is unavailable; no Landscape was created."));
        }
        const FString Filename=FPackageName::LongPackageNameToFilename(Path,FPackageName::GetMapPackageExtension());
        IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename),true);
        const bool bInitializedWorldSaved=FEditorFileUtils::SaveLevel(W->PersistentLevel,Filename);
        Data->SetStringField(TEXT("requested_map_package_path"),Path);
        Data->SetStringField(TEXT("map_template_equivalent"),bWorldPartition?TEXT("UEditorEngine::CreateNewMapForEditing(false, true)"):TEXT("UEditorEngine::CreateNewMapForEditing(false, false)"));
        Data->SetStringField(TEXT("world_package_after_initialization_save"),W->GetOutermost()->GetName());
        Data->SetBoolField(TEXT("initialized_world_saved_before_landscape"),bInitializedWorldSaved);
        if(!bInitializedWorldSaved)
            return Fail(TEXT("world_initialization_save_failed"),TEXT("The newly initialized test world could not be saved before Landscape creation."));
        }
        const FString Filename=FPackageName::LongPackageNameToFilename(Path,FPackageName::GetMapPackageExtension());
        FScopedTransaction Transaction(NSLOCTEXT("Forge","CreateTerrain","Create disposable Landscape"));
        ALandscape* L=W->SpawnActor<ALandscape>();
        if(!L) return Fail(TEXT("spawn_failed"),TEXT("Landscape spawn failed."));
        L->SetActorLabel(TEXT("ForgeTerrain")); L->bCanHaveLayersContent=true;
        L->SetActorScale3D(FVector(R->GetNumberField(TEXT("xy_scale_cm")),R->GetNumberField(TEXT("xy_scale_cm")),R->GetNumberField(TEXT("z_scale"))));
        int32 Q=R->GetIntegerField(TEXT("quads_per_section")), Sections=R->GetIntegerField(TEXT("sections_per_component"));
        int32 NX=Q*Sections*R->GetIntegerField(TEXT("components_x"))+1, NY=Q*Sections*R->GetIntegerField(TEXT("components_y"))+1;
        TMap<FGuid,TArray<uint16>> Heights; Heights.Add(FGuid()).Init(32768,NX*NY);
        TMap<FGuid,TArray<FLandscapeImportLayerInfo>> Materials; Materials.Add(FGuid());
        L->Import(FGuid::NewGuid(),0,0,NX-1,NY-1,Sections,Q,Heights,TEXT(""),Materials,ELandscapeImportAlphamapType::Additive,TArrayView<const FLandscapeLayer>());
        if(L->GetLayersConst().Num()!=1 || L->LandscapeComponents.Num()!=R->GetIntegerField(TEXT("components_x"))*R->GetIntegerField(TEXT("components_y")))
        { W->DestroyActor(L); return Fail(TEXT("import_failed"),TEXT("Unexpected native Landscape topology; spawned actor removed.")); }
        bool bUseEngineBasicMaterial=false; R->TryGetBoolField(TEXT("use_engine_basic_landscape_material"),bUseEngineBasicMaterial);
        if(bUseEngineBasicMaterial)
        {
            UMaterialInterface* VisualMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
            if(!VisualMaterial) { W->DestroyActor(L); return Fail(TEXT("visual_material_unavailable"),TEXT("The engine BasicShapeMaterial could not be loaded; Landscape creation was rolled back.")); }
            FProperty* MaterialProperty=FindFProperty<FProperty>(L->GetClass(),TEXT("LandscapeMaterial"));
            if(!MaterialProperty) { W->DestroyActor(L); return Fail(TEXT("visual_material_unavailable"),TEXT("LandscapeMaterial is not reflected on the created actor.")); }
            L->LandscapeMaterial=VisualMaterial;
            FPropertyChangedEvent MaterialChanged(MaterialProperty);
            L->PostEditChangeProperty(MaterialChanged);
        }
        L->GetLayersConst()[0].EditLayer->SetName(TEXT("ForgeTerrain"),true); L->RequestLayersContentUpdate(ELandscapeLayerUpdateMode::Update_All);
        if(bWorldPartition)
        {
            L->bAreNewLandscapeActorsSpatiallyLoaded=true;
            ULandscapeSubsystem* LandscapeSubsystem=W->GetSubsystem<ULandscapeSubsystem>();
            if(!LandscapeSubsystem || !LandscapeSubsystem->IsGridBased())
            { W->DestroyActor(L); return Fail(TEXT("partition_subsystem_unavailable"),TEXT("World Partition Landscape subsystem is unavailable.")); }
            const int32 Grid=R->GetIntegerField(TEXT("partition_grid_size_components"));
            LandscapeSubsystem->ChangeGridSize(L->GetLandscapeInfo(),Grid);
            if(L->GetLandscapeInfo()) L->GetLandscapeInfo()->ForceLayersFullUpdate();
        }
        bool Saved=FEditorFileUtils::SaveLevel(W->PersistentLevel,Filename);
        FIntRect CreatedBounds; TArray<uint16> CreatedHeights; bool HeightReadback=Read(L,L->GetLayersConst()[0].EditLayer->GetGuid(),CreatedBounds,CreatedHeights);
        Data->SetStringField(TEXT("state"),Saved&&HeightReadback?TEXT("completed"):TEXT("partial")); Data->SetBoolField(TEXT("saved"),Saved);
        Data->SetBoolField(TEXT("height_readback_validated"),HeightReadback);
        Data->SetBoolField(TEXT("world_partition_created"),W->GetWorldPartition()!=nullptr);
        Data->SetBoolField(TEXT("world_partition_streaming_enabled"),W->GetWorldPartition()&&W->GetWorldPartition()->IsStreamingEnabled());
        Data->SetBoolField(TEXT("created_in_existing_world"),bInPlace);
        Data->SetBoolField(TEXT("engine_basic_landscape_material_applied"),bUseEngineBasicMaterial);
        TArray<TSharedPtr<FJsonValue>> GeneratedPackageObservations;
        AppendGeneratedPackageObservations(Path, GeneratedPackageObservations);
        Data->SetArrayField(TEXT("generated_packages_observed_after_apply"), GeneratedPackageObservations);
        Data->SetBoolField(TEXT("generated_package_observations_are_complete"), false);
        Data->SetStringField(TEXT("generated_package_observation_limit"), TEXT("Loaded UPackage objects matching the target map and generated external namespaces only; the filesystem audit remains authoritative for actual writes."));
        Data->SetObjectField(TEXT("landscape"),Inspect(L,W)); if(HeightReadback) Frame(L,CreatedBounds); return true;
    }
    if(Action==TEXT("load_region"))
    {
        ALandscape* L=P.Actor.Get(); UWorldPartition* Partition=W->GetWorldPartition();
        const bool bApprovedExistingWorldPartitionOperation=ApprovedInPlaceLandscapeWorld(W);
        if(!L || !Partition || (!TestMap(W->GetOutermost()->GetName()) && !bApprovedExistingWorldPartitionOperation) || !L->GetActorTransform().Equals(P.Transform))
            return Fail(TEXT("stale_preview"),TEXT("The isolated World Partition Landscape changed after preview."));
        if(Loaders.Num()>=64) return Fail(TEXT("loader_limit"),TEXT("The session-local World Partition loader history is full; restart the isolated validation Editor."));
        const FVector Location=L->GetActorLocation(),Scale=L->GetActorScale3D();
        if(Scale.X<=0 || Scale.Y<=0) return Fail(TEXT("unsupported_transform"),TEXT("World Partition region loading requires positive Landscape XY scale."));
        const double MinX=Location.X+P.Bounds.Min.X*Scale.X, MinY=Location.Y+P.Bounds.Min.Y*Scale.Y;
        const double MaxX=Location.X+P.Bounds.Max.X*Scale.X, MaxY=Location.Y+P.Bounds.Max.Y*Scale.Y;
        const FBox WorldBounds(FVector(MinX,MinY,-HALF_WORLD_MAX),FVector(MaxX,MaxY,HALF_WORLD_MAX));
        const FString LoaderId=FGuid::NewGuid().ToString(EGuidFormats::Digits);
        UWorldPartitionEditorLoaderAdapter* Adapter=Partition->CreateEditorLoaderAdapter<FLoaderAdapterShape>(W,WorldBounds,TEXT("Forge Landscape Region ")+LoaderId);
        if(!Adapter || !Adapter->GetLoaderAdapter()) return Fail(TEXT("loader_create_failed"),TEXT("World Partition editor region loader could not be created."));
        Adapter->GetLoaderAdapter()->SetUserCreated(true);
        Adapter->GetLoaderAdapter()->Load();
        FLoader Entry; Entry.World=W; Entry.Actor=L; Entry.Adapter=Adapter; Entry.LandscapeGuid=L->GetLandscapeGuid(); Entry.Bounds=P.Bounds; Entry.WorldBounds=WorldBounds; Entry.Deadline=FPlatformTime::Seconds()+30.0;
        int32 RegionTotal=0,RegionLoaded=0,RegionUnloaded=0; CountLandscapeStreamingProxies(W,RegionTotal,RegionLoaded,RegionUnloaded,&WorldBounds);
        Entry.State=RegionTotal>0 && RegionLoaded==RegionTotal?TEXT("loaded"):TEXT("loading");
        Loaders.Add(LoaderId,Entry);
        Data->SetStringField(TEXT("loader_id"),LoaderId); Data->SetStringField(TEXT("job_id"),LoaderId);
        Data->SetStringField(TEXT("state"),Entry.State); Data->SetNumberField(TEXT("progress"),RegionTotal?double(RegionLoaded)/RegionTotal:0.0);
        AddStreamingDiagnostics(Data,W,&WorldBounds);
        Data->SetBoolField(TEXT("saved"),false); Data->SetBoolField(TEXT("height_readback_validated"),false);
        return true;
    }
    if(Action==TEXT("unload_region"))
    {
        FString LoaderId; R->TryGetStringField(TEXT("partition_loader_id"),LoaderId);
        FLoader* Entry=Loaders.Find(LoaderId); UWorldPartition* Partition=W->GetWorldPartition();
        UWorldPartitionEditorLoaderAdapter* Adapter=Entry?Entry->Adapter.Get():nullptr;
        if(!Entry || Entry->World.Get()!=W || !Partition)
            return Fail(TEXT("loader_not_found"),TEXT("The previewed Forge World Partition loader is no longer active."));
        if(Entry->State!=TEXT("unloaded") && Entry->State!=TEXT("unloading"))
        {
            if(!Adapter || !Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
                return Fail(TEXT("loader_not_found"),TEXT("The previewed Forge World Partition loader is no longer registered."));
            if(Adapter->GetLoaderAdapter()) Adapter->GetLoaderAdapter()->Unload();
            // Match the UE 5.6 editor's UnloadSelectedRegions path: unload and
            // release the editor loader immediately so it cannot retain cells
            // while we asynchronously observe their descriptor transitions.
            Partition->ReleaseEditorLoaderAdapter(Adapter);
            Entry->Adapter.Reset();
            Entry->bTargetLoaded=false; Entry->State=TEXT("unloading"); Entry->Deadline=FPlatformTime::Seconds()+30.0;
        }
        int32 Total=0,Loaded=0,Unloaded=0; CountLandscapeStreamingProxies(W,Total,Loaded,Unloaded,&Entry->WorldBounds);
        if(Total>0 && Loaded==0)
        {
            Entry->State=TEXT("unloaded");
        }
        Data->SetStringField(TEXT("loader_id"),LoaderId); Data->SetStringField(TEXT("job_id"),LoaderId); Data->SetStringField(TEXT("state"),Entry->State);
        Data->SetNumberField(TEXT("progress"),Total?double(Total-Loaded)/Total:0.0); AddStreamingDiagnostics(Data,W,&Entry->WorldBounds);
        Data->SetBoolField(TEXT("saved"),false); return true;
    }
    ALandscape* L=P.Actor.Get();
    if(Action==TEXT("frame")) { Frame(L,P.Bounds); Data->SetStringField(TEXT("state"),TEXT("completed")); return true; }
    if(Action==TEXT("save") || Action==TEXT("reload"))
    {
        FString Filename=FPackageName::LongPackageNameToFilename(W->GetOutermost()->GetName(),FPackageName::GetMapPackageExtension());
        if(Action==TEXT("save"))
        {
            if(!L->IsUpToDate()) return Fail(TEXT("terrain_pending"),TEXT("Wait for native layer recomposition before save."));
            FString BackupRoot=FPaths::ProjectSavedDir()/TEXT("ForgeLandscape")/Id;
            FString Backup=BackupRoot/TEXT("before.umap"); IFileManager::Get().MakeDirectory(*BackupRoot,true);
            if(IFileManager::Get().Copy(*Backup,*Filename,false)!=COPY_OK) return Fail(TEXT("backup_failed"),TEXT("Map backup failed; save refused."));
            TArray<FString> ExternalManifest;
            if(W->GetWorldPartition() && !BackupExternalLandscapePackages(L,BackupRoot,ExternalManifest)) return Fail(TEXT("external_backup_failed"),TEXT("A loaded Landscape external actor package could not be backed up and verified; save refused."));
            // Do not schedule another full regeneration immediately before saving.
            // Pending GPU layer readbacks can dirty a just-saved map on later ticks.
            L->ForceUpdateLayersContent();
            bool Saved=FEditorFileUtils::SaveLevel(W->PersistentLevel,Filename);
            Saved=Saved && !W->GetOutermost()->IsDirty() && ExternalLandscapePackagesClean(L);
            TArray<TSharedPtr<FJsonValue>> ExternalValues;
            for(const FString& Package:ExternalManifest) ExternalValues.Add(MakeShared<FJsonValueString>(Package));
            Data->SetBoolField(TEXT("saved"),Saved); Data->SetStringField(TEXT("backup"),Backup); Data->SetStringField(TEXT("external_backup_root"),BackupRoot);
            Data->SetNumberField(TEXT("external_package_backup_count"),ExternalManifest.Num()); Data->SetArrayField(TEXT("external_package_backup_manifest"),ExternalValues);
            Data->SetStringField(TEXT("state"),Saved?TEXT("completed"):TEXT("partial"));
            Data->SetStringField(TEXT("height_md5"),Hash(Current)); return true;
        }
        FString Guid=L->GetLandscapeGuid().ToString();
        if(!UEditorLoadingAndSavingUtils::LoadMap(Filename)) return Fail(TEXT("reload_failed"),TEXT("Native test-map reload failed."));
        UWorld* Reloaded=GEditor->GetEditorWorldContext().World(); ALandscape* Found=nullptr;
        for(TActorIterator<ALandscape> It(Reloaded);It;++It) if(It->GetLandscapeGuid().ToString()==Guid) Found=*It;
        TArray<uint16> Readback; FIntRect RB;
        bool Match=Found && Read(Found,P.Layer,RB,Readback) && RB==P.Bounds && Readback==P.Before;
        bool ComplexCollisionMatch=false;
        if(Match && Found && !Readback.IsEmpty())
        {
            const int32 SampleX=P.Bounds.Min.X+P.Bounds.Width()/2;
            const int32 SampleY=P.Bounds.Min.Y+P.Bounds.Height()/2;
            const int32 SampleIndex=(SampleY-P.Bounds.Min.Y)*P.Bounds.Width()+SampleX-P.Bounds.Min.X;
            const FTransform LandscapeTransform=Found->LandscapeActorToWorld();
            const FVector SampleWorld=LandscapeTransform.TransformPosition(FVector(SampleX,SampleY,0));
            const double ExpectedWorldZ=LandscapeTransform.GetLocation().Z+
                (int32(Readback[SampleIndex])-32768)*LandscapeTransform.GetScale3D().Z/128.0;
            const TOptional<float> ActualWorldZ=Found->GetHeightAtLocation(SampleWorld,EHeightfieldSource::Complex);
            ComplexCollisionMatch=ActualWorldZ.IsSet() && FMath::Abs(ActualWorldZ.GetValue()-ExpectedWorldZ)<=8.0;
            Data->SetNumberField(TEXT("complex_collision_expected_world_z_cm"),ExpectedWorldZ);
            if(ActualWorldZ.IsSet()) Data->SetNumberField(TEXT("complex_collision_actual_world_z_cm"),ActualWorldZ.GetValue());
        }
        Data->SetBoolField(TEXT("complex_collision_validated_after_reload"),ComplexCollisionMatch);
        if(Found && !ComplexCollisionMatch)
            Data->SetStringField(TEXT("complex_collision_validation_note"),TEXT("Saved layer readback and cooked Complex collision are reported separately; a collision mismatch does not rewrite package data."));
        Data->SetStringField(TEXT("state"),Match?TEXT("completed"):TEXT("validation_failed")); Data->SetBoolField(TEXT("persistence_validated"),Match);
        if(Found) Data->SetObjectField(TEXT("landscape"),Inspect(Found,Reloaded)); return true;
    }
    int64 ActiveJobSamples=0;
    for(const auto& Entry:Jobs) if(Entry.Value.State==TEXT("running")) ActiveJobSamples+=Entry.Value.Plan.Before.Num()+Entry.Value.Plan.After.Num();
    if(ActiveJobSamples+P.Before.Num()+P.After.Num()>MaxSamples*2) return Fail(TEXT("job_memory_limit"),TEXT("Active job before/after buffers exceed the 8,388,608-uint16-sample (16 MiB) processing budget."));
    if(Jobs.Num()>=64) return Fail(TEXT("job_limit"),TEXT("Session job history is full; restart the isolated validation host."));
    FJob J; J.Plan=MoveTemp(P); J.Id=Id; J.ValidatedAfterHash=Hash(J.Plan.After); J.NextTime=FPlatformTime::Seconds()+R->GetNumberField(TEXT("stage_interval_seconds"));
    J.Backup=FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/TEXT("ForgeLandscape")/Id/TEXT("before.r16"));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(J.Backup),true);
    if(!FFileHelper::SaveArrayToFile(TArrayView<const uint8>(reinterpret_cast<const uint8*>(J.Plan.Before.GetData()),J.Plan.Before.Num()*sizeof(uint16)),*J.Backup)) return Fail(TEXT("backup_failed"),TEXT("Height backup failed; no edit started."));
    TArray<uint8> BackupBytes;
    if(!FFileHelper::LoadFileToArray(BackupBytes,*J.Backup) || BackupBytes.Num()!=J.Plan.Before.Num()*int32(sizeof(uint16)) || FMemory::Memcmp(BackupBytes.GetData(),J.Plan.Before.GetData(),BackupBytes.Num())!=0) return Fail(TEXT("backup_failed"),TEXT("Height backup readback failed; no edit started."));
    auto Meta=MakeShared<FJsonObject>(); Meta->SetObjectField(TEXT("request"),R);
    Meta->SetStringField(TEXT("layer_guid"),J.Plan.Layer.ToString()); Meta->SetStringField(TEXT("before_md5"),Hash(J.Plan.Before));
    Meta->SetNumberField(TEXT("width"),J.Plan.Bounds.Width()); Meta->SetNumberField(TEXT("height"),J.Plan.Bounds.Height());
    Meta->SetNumberField(TEXT("min_x"),J.Plan.Bounds.Min.X); Meta->SetNumberField(TEXT("min_y"),J.Plan.Bounds.Min.Y);
    Meta->SetStringField(TEXT("transform"),L->GetTransform().ToString());
    FString Metadata; auto Writer=TJsonWriterFactory<>::Create(&Metadata); FJsonSerializer::Serialize(Meta,Writer);
    if(!FFileHelper::SaveStringToFile(Metadata,*(J.Backup+TEXT(".json")))) return Fail(TEXT("backup_failed"),TEXT("Backup metadata failed; no edit started."));
    const FString BackupPath=J.Backup; Jobs.Add(Id,MoveTemp(J)); Data->SetStringField(TEXT("job_id"),Id); Data->SetStringField(TEXT("state"),TEXT("running")); Data->SetStringField(TEXT("backup"),BackupPath); return true;
}

void FForgeLandscape::Tick()
{
    if(!IsInGameThread()) return;
    UWorld* CurrentWorld=GEditor?GEditor->GetEditorWorldContext().World():nullptr;
    if(LastWorld.Get()!=CurrentWorld)
    {
        Reset();
        LastWorld=CurrentWorld;
    }
    for(auto& Entry:Loaders)
    {
        FLoader& Loader=Entry.Value;
        if(Loader.State!=TEXT("loading") && Loader.State!=TEXT("unloading")) continue;
        UWorld* LoaderWorld=Loader.World.Get();
        UWorldPartition* Partition=LoaderWorld?LoaderWorld->GetWorldPartition():nullptr;
        if(!Partition) { Loader.State=TEXT("transition_failed"); Loader.Error=TEXT("World Partition ended before the region transition completed."); continue; }
        int32 Total=0,Loaded=0,Unloaded=0,Spatial=0,NonSpatial=0;
        CountLandscapeStreamingProxies(LoaderWorld,Total,Loaded,Unloaded,&Loader.WorldBounds,&Spatial,&NonSpatial);
        UWorldPartitionEditorLoaderAdapter* Adapter=Loader.Adapter.Get();
        if(Total==0)
        {
            Loader.State=TEXT("no_region_proxies");
        }
        else if(Loader.bTargetLoaded && Loaded==Total)
        {
            Loader.State=TEXT("loaded");
        }
        else if(!Loader.bTargetLoaded && Loaded==0)
        {
            Loader.State=TEXT("unloaded");
        }
        else if(FPlatformTime::Seconds()>=Loader.Deadline)
        {
            Loader.State=TEXT("transition_failed");
            Loader.Error=FString::Printf(TEXT("Region proxy state did not reach target: loaded=%d total=%d spatial=%d non_spatial=%d editor_loaders=%d."),
                Loaded,Total,Spatial,NonSpatial,Partition->GetRegisteredEditorLoaderAdapters().Num());
        }
        else continue;

        if((Loader.State==TEXT("unloaded") || Loader.State==TEXT("no_region_proxies") || Loader.State==TEXT("transition_failed")) &&
            Adapter && Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
        {
            if(Loader.State==TEXT("transition_failed") && Adapter->GetLoaderAdapter()) Adapter->GetLoaderAdapter()->Unload();
            Partition->ReleaseEditorLoaderAdapter(Adapter);
            Loader.Adapter.Reset();
        }
    }
    for(auto& Entry:Jobs)
    {
        FJob& J=Entry.Value; if(J.State!=TEXT("running") || FPlatformTime::Seconds()<J.NextTime) continue;
        ALandscape* L=J.Plan.Actor.Get(); UWorld* W=GEditor?GEditor->GetEditorWorldContext().World():nullptr;
        FIntRect B; TArray<uint16> Current;
        const FLandscapeLayer* CurrentLayer=L?L->GetLayerConst(FName(TEXT("ForgeTerrain"))):nullptr;
        if(!GEditor || GEditor->PlayWorld || GEditor->bIsSimulatingInEditor || W!=J.Plan.World.Get() || !TestMap(W->GetOutermost()->GetName()) || !L ||
            !CurrentLayer || !CurrentLayer->EditLayer || CurrentLayer->EditLayer->GetGuid()!=J.Plan.Layer || CurrentLayer->EditLayer->IsLocked() ||
            !CurrentLayer->EditLayer->IsVisible() || !L->GetActorTransform().Equals(J.Plan.Transform) || L->GetLandscapeInfo()==nullptr)
        { J.State=TEXT("interrupted_partial"); J.Error=TEXT("World/PIE/landscape changed between stages; no further writes."); J.Plan.Before.Empty(); J.Plan.After.Empty(); continue; }
        double Started=FPlatformTime::Seconds(); auto R=J.Plan.Request.ToSharedRef();
        const int32 X1=J.Plan.EditBounds.Min.X,Y1=J.Plan.EditBounds.Min.Y;
        const int32 X2=J.Plan.EditBounds.Max.X-1,Y2=J.Plan.EditBounds.Max.Y-1;
        int32 First=Y1+J.NextRow, Last=FMath::Min(Y2,First+R->GetIntegerField(TEXT("rows_per_stage"))-1);
        const int32 WriteX1=FMath::Max(J.Plan.Bounds.Min.X,X1-1), WriteY1=FMath::Max(J.Plan.Bounds.Min.Y,First-1);
        const int32 WriteX2=FMath::Min(J.Plan.Bounds.Max.X-1,X2+1), WriteY2=FMath::Min(J.Plan.Bounds.Max.Y-1,Last+1);
        if(First>Y2 || !ReadRegion(L,J.Plan.Layer,FIntRect(WriteX1,WriteY1,WriteX2+1,WriteY2+1),B,Current) || B!=FIntRect(WriteX1,WriteY1,WriteX2+1,WriteY2+1))
        { J.State=TEXT("interrupted_partial"); J.Error=TEXT("Next terrain batch could not be read across loaded Landscape components."); J.Plan.Before.Empty(); J.Plan.After.Empty(); continue; }
        bool bStale=false;
        for(int32 Y=WriteY1;Y<=WriteY2 && !bStale;++Y) for(int32 X=WriteX1;X<=WriteX2;++X)
        {
            int32 ExpectedIndex=(Y-J.Plan.Bounds.Min.Y)*J.Plan.Bounds.Width()+X-J.Plan.Bounds.Min.X;
            int32 PatchIndex=(Y-WriteY1)*B.Width()+X-WriteX1;
            if(Current[PatchIndex]!=J.Plan.Before[ExpectedIndex]) { bStale=true; break; }
        }
        if(bStale)
        { J.State=TEXT("interrupted_partial"); J.Error=TEXT("Terrain changed in the next batch after preview; no further writes."); J.Plan.Before.Empty(); J.Plan.After.Empty(); continue; }
        TArray<uint16> Patch=Current;
        for(int32 Y=First;Y<=Last;++Y) for(int32 X=X1;X<=X2;++X)
            Patch[(Y-WriteY1)*B.Width()+X-WriteX1]=J.Plan.After[(Y-J.Plan.Bounds.Min.Y)*J.Plan.Bounds.Width()+X-J.Plan.Bounds.Min.X];
        {
            FScopedTransaction Transaction(NSLOCTEXT("Forge","TerrainStage","Forge Landscape stage")); L->Modify();
            L->GetLandscapeInfo()->ForAllLandscapeComponents([WriteX1,WriteX2,WriteY1,WriteY2](ULandscapeComponent* C)
            {
                const FIntPoint Base=C->GetSectionBase(); const int32 Size=C->ComponentSizeQuads;
                if(Base.X<=WriteX2 && Base.X+Size>=WriteX1 && Base.Y<=WriteY2 && Base.Y+Size>=WriteY1)
                { C->Modify(); if(ALandscapeProxy* Proxy=C->GetLandscapeProxy()) Proxy->Modify(); }
            });
            FLandscapeEditDataInterface Edit(L->GetLandscapeInfo(),J.Plan.Layer);
            Edit.SetHeightData(WriteX1,WriteY1,WriteX2,WriteY2,Patch.GetData(),B.Width(),true); Edit.Flush();
        }
        L->RequestLayersContentUpdate(ELandscapeLayerUpdateMode::Update_Heightmap_Editing);
        GEditor->RedrawLevelEditingViewports();
        J.NextRow+=Last-First+1;
        for(int32 Y=First;Y<=Last;++Y) for(int32 X=X1;X<=X2;++X)
        { int32 I=(Y-J.Plan.Bounds.Min.Y)*J.Plan.Bounds.Width()+X-J.Plan.Bounds.Min.X; J.Plan.Before[I]=J.Plan.After[I]; }
        TArray<uint16> Readback; FIntRect RB;
        bool bReadbackMatches=ReadRegion(L,J.Plan.Layer,FIntRect(X1,First,X2+1,Last+1),RB,Readback) && RB==FIntRect(X1,First,X2+1,Last+1);
        for(int32 Y=First;Y<=Last && bReadbackMatches;++Y) for(int32 X=X1;X<=X2;++X)
            if(Readback[(Y-First)*RB.Width()+X-X1]!=J.Plan.After[(Y-J.Plan.Bounds.Min.Y)*J.Plan.Bounds.Width()+X-J.Plan.Bounds.Min.X]) { bReadbackMatches=false; break; }
        if(!bReadbackMatches)
        { J.State=TEXT("validation_failed_partial"); J.Error=TEXT("Native height readback differs from planned stage."); J.Plan.Before.Empty(); J.Plan.After.Empty(); }
        else if(Last==Y2)
        {
            J.bHeightReadbackValidated=true;
            J.State=TEXT("completed");
            J.Plan.Before.Empty(); J.Plan.After.Empty();
        }
        J.MaxStageMs=FMath::Max(J.MaxStageMs,(FPlatformTime::Seconds()-Started)*1000);
        J.NextTime=FPlatformTime::Seconds()+R->GetNumberField(TEXT("stage_interval_seconds"));
    }
}

void FForgeLandscape::Reset()
{
    for(auto& Entry:Loaders)
    {
        UWorld* W=Entry.Value.World.Get(); UWorldPartition* Partition=W?W->GetWorldPartition():nullptr;
        UWorldPartitionEditorLoaderAdapter* Adapter=Entry.Value.Adapter.Get();
        if(Partition && Adapter && Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
        {
            if(Adapter->GetLoaderAdapter()) Adapter->GetLoaderAdapter()->Unload();
            Partition->ReleaseEditorLoaderAdapter(Adapter);
        }
    }
    Loaders.Empty(); Previews.Empty(); Jobs.Empty();
    bWorldTransitionInProgress=false;
}

bool FForgeLandscape::PrepareForWorldTransition(UWorld* OutgoingWorld,FString& OutError)
{
    if(!IsInGameThread() || !GEditor || !OutgoingWorld || GEditor->GetEditorWorldContext().World()!=OutgoingWorld)
    {
        OutError=TEXT("Map transition preflight could not verify the outgoing editor world on the game thread.");
        return false;
    }

    for(const auto& Entry:Jobs)
    {
        const FJob& Job=Entry.Value;
        if(Job.Plan.World.Get()==OutgoingWorld && Job.State==TEXT("running"))
        {
            OutError=FString::Printf(TEXT("Landscape job %s is still active (%s, %d rows applied); wait for completion or cancel it explicitly before changing maps."),*Job.Id,*Job.State,Job.NextRow);
            return false;
        }
    }

    for(auto& Entry:Loaders)
    {
        FLoader& Loader=Entry.Value;
        if(Loader.World.Get()!=OutgoingWorld) continue;
        UWorldPartition* Partition=OutgoingWorld->GetWorldPartition();
        UWorldPartitionEditorLoaderAdapter* Adapter=Loader.Adapter.Get();
        if(Loader.State==TEXT("loading") || Loader.State==TEXT("unloading"))
        {
            OutError=FString::Printf(TEXT("World Partition loader %s is still %s; wait for the native proxy transition before changing maps."),*Entry.Key,*Loader.State);
            return false;
        }
        if(Loader.State==TEXT("loaded"))
        {
            if(Partition && Adapter && Adapter->GetLoaderAdapter() && Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
            {
                Adapter->GetLoaderAdapter()->Unload();
                Loader.bTargetLoaded=false;
                Loader.State=TEXT("unloading");
                Loader.Deadline=FPlatformTime::Seconds()+30.0;
            }
            OutError=FString::Printf(TEXT("World Partition loader %s was asked to unload; retry map creation after its proxies report unloaded."),*Entry.Key);
            return false;
        }
        if(Partition && Adapter && Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
        {
            if(Adapter->GetLoaderAdapter()) Adapter->GetLoaderAdapter()->Unload();
            Partition->ReleaseEditorLoaderAdapter(Adapter);
            if(Partition->GetRegisteredEditorLoaderAdapters().Contains(Adapter))
            {
                OutError=FString::Printf(TEXT("ForgeMCP could not unregister World Partition loader %s; map transition refused."),*Entry.Key);
                return false;
            }
            Loader.Adapter.Reset();
        }
    }

    for(auto& Entry:Jobs)
    {
        FJob& Job=Entry.Value;
        if(Job.Plan.World.Get()==OutgoingWorld)
        {
            Job.Plan.Before.Empty();
            Job.Plan.After.Empty();
        }
    }
    Previews.Empty();
    Loaders.Empty();
    return true;
}
