// Included in ForgeLandscape.cpp after the bounded read/backup helpers.
// Game-thread-only approval state. Never deserialize an approval from MCP args.
struct FAdoptedLandscapeGrant
{
    FString Id, ActorPath, ProjectFile, WorldPackage, SessionId, BackupRoot, ManifestHash;
    FGuid LandscapeGuid;
    TWeakObjectPtr<UWorld> World;
    TWeakObjectPtr<ALandscape> Actor;
    FIntRect Region;
    TSet<FString> Actions;
    FExistingWorldWriteSnapshot Backup;
    bool bWorldPartition = false, bApproved = false, bRevoked = false, bUsed = false;
    int64 Expires = 0, RequestExpires = 0;
    int32 Lifetime = 0;
    // Editing sessions are distinct from the existing consumed-once adoption grants.
    bool bEditSession = false, bEntireLandscape = false;
    FGuid EditLayerGuid;
    FTransform SessionTransform = FTransform::Identity;
    FString ExpectedTargetHash, ActiveOperation, LayerState;
    TMap<FGuid,FString> ProtectedLayerHashes;
    TSet<FString> OwnedDirtyPackages;
    TArray<FString> Operations;
};
TMap<FString, FAdoptedLandscapeGrant> AdoptionGrants;
const TSet<FString> AdoptionActions={TEXT("setup_layer"),TEXT("raise"),TEXT("lower"),TEXT("flatten"),
    TEXT("smooth"),TEXT("generate"),TEXT("apply_heightmap"),TEXT("coastline")};

bool AdoptionGrantActive(const FAdoptedLandscapeGrant& G,const FString& Action,int64 Now,bool bAllowUsed)
{
    return G.bApproved && !G.bRevoked && (G.bEditSession || bAllowUsed || !G.bUsed) && G.Expires>Now && G.Actions.Contains(Action);
}

bool AdoptionRegionContains(const FIntRect& Allowed,const FIntRect& Requested)
{
    return Requested.Width()>0 && Requested.Height()>0 && Requested.Min.X>=Allowed.Min.X &&
        Requested.Min.Y>=Allowed.Min.Y && Requested.Max.X<=Allowed.Max.X && Requested.Max.Y<=Allowed.Max.Y;
}

bool AdoptionComponentsAccessible(int32 Total,int32 Loaded,int32 Unloaded,bool bRegistered)
{
    return Total>=0 && Total==Loaded && Unloaded==0 && bRegistered;
}

bool AdoptionTargetLayerReady(bool bExists,bool bHasNativeLayer,bool bLocked,bool bVisible)
{
    return bExists && bHasNativeLayer && !bLocked && bVisible;
}

bool AdoptionIdentityValues(const FAdoptedLandscapeGrant& G,const FString& Session,const FString& Project,
    const FString& World,const FString& Actor,const FGuid& Guid,bool bWorldPartition)
{
    return G.SessionId==Session && SamePath(G.ProjectFile,Project) && G.WorldPackage==World &&
        G.ActorPath==Actor && G.LandscapeGuid==Guid && G.bWorldPartition==bWorldPartition;
}

bool AdoptionIdentity(const FAdoptedLandscapeGrant& G, UWorld* W, ALandscape* L)
{
    if (G.bEditSession)
    {
        const FLandscapeLayer* Layer=L?L->GetLayerConst(FName(TEXT("ForgeTerrain"))):nullptr;
        if (!Layer || !Layer->EditLayer || Layer->EditLayer->GetGuid()!=G.EditLayerGuid ||
            !L->GetActorTransform().Equals(G.SessionTransform)) return false;
    }
    return W && L && G.World.Get()==W && G.Actor.Get()==L && L->GetWorld()==W &&
        AdoptionIdentityValues(G,FString::Printf(TEXT("unreal-%u"),FPlatformProcess::GetCurrentProcessId()),
            FPaths::GetProjectFilePath(),W->GetOutermost()->GetName(),L->GetPathName(),L->GetLandscapeGuid(),W->GetWorldPartition()!=nullptr);
}

bool AdoptionClean(UWorld* W, ALandscape* L)
{
    if (!W || W->GetOutermost()->IsDirty() || !ExternalLandscapePackagesClean(L)) return false;
    FString Relative=W->GetOutermost()->GetName().Mid(6);
    const FString ActorRoot=TEXT("/Game/__ExternalActors__/")+Relative+TEXT("/");
    const FString ObjectRoot=TEXT("/Game/__ExternalObjects__/")+Relative+TEXT("/");
    for (TObjectIterator<UPackage> It;It;++It)
        if (It->IsDirty() && (It->GetName().StartsWith(ActorRoot) || It->GetName().StartsWith(ObjectRoot))) return false;
    return true;
}

bool AdoptionReady(UWorld* W, ALandscape* L, const FIntRect& Region, FString& Error,bool bAllowPendingComposition=false)
{
    if (!W || !L || L->GetWorld()!=W || L->GetLevel()!=W->PersistentLevel ||
        GEditor->PlayWorld || GEditor->bIsSimulatingInEditor || W->GetStreamingLevels().Num()!=0 ||
        !L->HasLayersContent() || !L->GetLandscapeInfo() || !L->GetActorRotation().IsNearlyZero() ||
        L->GetActorScale3D().GetMin()<=0 || (!bAllowPendingComposition && !L->IsUpToDate()))
    { Error=TEXT("Landscape identity, layers, transform, PIE or recomposition is unsafe."); return false; }
    if (W->GetWorldPartition() && !ExistingWorldPartitionConfiguration(W))
    { Error=TEXT("World Partition editor streaming/loading support is unavailable."); return false; }
    int32 Total=0,Loaded=0,Unloaded=0;
    CountLandscapeStreamingProxies(W,Total,Loaded,Unloaded);
    if (Unloaded || Total!=Loaded)
    { Error=TEXT("All world Landscape proxies must be loaded for initial adoption."); return false; }
    bool Registered=true;
    L->GetLandscapeInfo()->ForAllLandscapeComponents([&](ULandscapeComponent* C)
    {
        ALandscapeProxy* Proxy=C?C->GetLandscapeProxy():nullptr;
        Registered &= C && C->IsRegistered() && C->GetWorld()==W && Proxy && Proxy->GetWorld()==W &&
            Proxy->GetLandscapeGuid()==L->GetLandscapeGuid() && C->GetCollisionComponent() && C->GetCollisionComponent()->IsRegistered();
    });
    L->GetLandscapeInfo()->ForEachLandscapeProxy([&](ALandscapeProxy* Proxy)
    { Registered &= Proxy && Proxy->GetWorld()==W && Proxy->GetLandscapeGuid()==L->GetLandscapeGuid(); return true; });
    if (!AdoptionComponentsAccessible(Total,Loaded,Unloaded,Registered) || L->GetLayersConst().Num()==0)
    { Error=TEXT("Required native Landscape/collision components or layers are unavailable."); return false; }
    const FLandscapeLayer& Source=L->GetLayersConst()[0];
    FIntRect ReadBounds; TArray<uint16> Heights;
    int32 X1,Y1,X2,Y2;
    if (!Source.EditLayer || !L->GetLandscapeInfo()->GetLandscapeExtent(X1,Y1,X2,Y2) ||
        Region.Min.X<X1 || Region.Min.Y<Y1 || Region.Max.X>X2+1 || Region.Max.Y>Y2+1)
    { Error=TEXT("Requested region is outside the native Landscape extent."); return false; }
    const FIntRect Halo(FMath::Max(X1,Region.Min.X-1),FMath::Max(Y1,Region.Min.Y-1),
        FMath::Min(X2+1,Region.Max.X+1),FMath::Min(Y2+1,Region.Max.Y+1));
    if (!ReadRegion(L,Source.EditLayer->GetGuid(),Halo,ReadBounds,Heights))
    { Error=TEXT("The requested region and normal halo are partially loaded or mismatched."); return false; }
    return true;
}

bool AdoptionBackupsValid(const FAdoptedLandscapeGrant& G)
{
    if (G.Backup.FileHashes.IsEmpty()) return false;
    for (const auto& Entry:G.Backup.FileHashes)
    {
        FString Relative=Entry.Key;
        if (!FPaths::MakePathRelativeTo(Relative,*FPaths::ProjectDir()) || Relative.StartsWith(TEXT(".."))) return false;
        const FString File=CanonicalPath(G.BackupRoot/TEXT("before")/Relative);
        const FMD5Hash Hash=FMD5Hash::HashFile(*File);
        if (!Hash.IsValid() || LexToString(Hash)!=Entry.Value) return false;
        // Reject a save or external disk edit since the checkpoint.
        const FMD5Hash Current=FMD5Hash::HashFile(*Entry.Key);
        if (!Current.IsValid() || LexToString(Current)!=Entry.Value) return false;
    }
    return true;
}

bool AdoptionBackupFilesPresent(const FAdoptedLandscapeGrant& G)
{
    if (G.Backup.FileHashes.IsEmpty() || !IFileManager::Get().FileExists(*(G.BackupRoot/TEXT("manifest.json")))) return false;
    const FMD5Hash Manifest=FMD5Hash::HashFile(*(G.BackupRoot/TEXT("manifest.json")));
    if (!Manifest.IsValid() || LexToString(Manifest)!=G.ManifestHash) return false;
    for (const auto& Entry:G.Backup.FileHashes)
    {
        FString Relative=Entry.Key;
        if (!FPaths::MakePathRelativeTo(Relative,*FPaths::ProjectDir()) || Relative.StartsWith(TEXT("..")) ||
            !IFileManager::Get().FileExists(*(G.BackupRoot/TEXT("before")/Relative))) return false;
    }
    return true;
}

bool AdoptionCheckpointScopeMatches(const FAdoptedLandscapeGrant& G,UWorld* W)
{
    TArray<FString> Files; FString Error;
    if (!EnumerateExistingWorldPackageFiles(W,Files,Error) || Files.Num()!=G.Backup.FileHashes.Num()) return false;
    for (const FString& File:Files) if (!G.Backup.FileHashes.Contains(CanonicalPath(File).ToLower())) return false;
    return true;
}

FAdoptedLandscapeGrant* FindAdoption(const FString& Id,UWorld* W,ALandscape* L,
    const FString& Action,const FIntRect* Region=nullptr,bool bAllowUsed=false)
{
    FAdoptedLandscapeGrant* G=AdoptionGrants.Find(Id);
    if (!G || !AdoptionGrantActive(*G,Action,FDateTime::UtcNow().ToUnixTimestamp(),bAllowUsed) || !AdoptionIdentity(*G,W,L)) return nullptr;
    if (Region && !AdoptionRegionContains(G->Region,*Region)) return nullptr;
    return G;
}

#include "ForgeLandscapeEditSession.inl"

bool HandleAdoptionRequest(const FString& Command,const TSharedRef<FJsonObject>& Args,UWorld* W,
    TSharedRef<FJsonObject> Data,FString& Code,FString& Message)
{
    auto Fail=[&](const TCHAR* C,const FString& M) { Code=C; Message=M; return false; };
    const TSharedPtr<FJsonObject>* Request=nullptr;
    if (!Args->TryGetObjectField(TEXT("request"),Request) || !Request || !Request->IsValid())
        return Fail(TEXT("invalid_request"),TEXT("A typed adoption request is required."));
    auto R=Request->ToSharedRef(); FString Path,GuidText,ProjectFile,WorldPackage;
    const bool bSession=Command.StartsWith(TEXT("landscape_edit_session_"));
    double EditorPid=0; bool bPartitioned=false;
    if (!R->TryGetStringField(TEXT("project_file"),ProjectFile) || !SamePath(ProjectFile,FPaths::GetProjectFilePath()) ||
        !R->TryGetStringField(TEXT("world_path"),WorldPackage) || WorldPackage!=W->GetOutermost()->GetName() ||
        !Number(R,TEXT("editor_pid"),EditorPid,1,MAX_int32,true) || EditorPid!=FPlatformProcess::GetCurrentProcessId() ||
        !R->TryGetBoolField(TEXT("world_partition"),bPartitioned) || bPartitioned!=(W->GetWorldPartition()!=nullptr))
        return Fail(TEXT("adoption_identity_mismatch"),TEXT("Expected Editor PID, project, world and World Partition status must match the live Editor."));
    FGuid Guid; FIntRect Region;
    if (!R->TryGetStringField(TEXT("actor_path"),Path) || !R->TryGetStringField(TEXT("landscape_guid"),GuidText) ||
        !FGuid::ParseExact(GuidText,EGuidFormats::Digits,Guid) || !ParseRegion(R,Region))
        return Fail(TEXT("invalid_scope"),TEXT("Exact actor/GUID and bounded inclusive region required."));
    ALandscape* L=Resolve(W,Path);
    if (!L || L->GetWorld()!=W || L->GetLandscapeGuid()!=Guid)
        return Fail(TEXT("landscape_identity_mismatch"),TEXT("Actor and GUID must match the current active world."));
    double Lifetime=0; const TArray<TSharedPtr<FJsonValue>>* Actions=nullptr; TSet<FString> Parsed;
    if (!Number(R,TEXT("lifetime_seconds"),Lifetime,bSession?60:30,bSession?86400:3600,true) || !R->TryGetArrayField(TEXT("actions"),Actions) ||
        Actions->Num()<1 || Actions->Num()>8) return Fail(TEXT("invalid_scope"),TEXT("Bounded actions and lifetime required."));
    for (const auto& Value:*Actions)
    {
        FString Action;
        if (!Value->TryGetString(Action) || !AdoptionActions.Contains(Action) || Parsed.Contains(Action))
            return Fail(TEXT("invalid_scope"),TEXT("Unsupported or duplicate adoption action."));
        Parsed.Add(Action);
    }
    if (Parsed.Contains(TEXT("setup_layer")) && Parsed.Num()!=1)
        return Fail(TEXT("invalid_scope"),TEXT("Layer setup needs a separate approval/checkpoint."));
    const bool bSetup=Parsed.Contains(TEXT("setup_layer"));
    FString LayerName,LayerGuidText,RegionScope; FGuid SessionLayerGuid;
    if (bSession && (bSetup || !R->TryGetStringField(TEXT("layer_name"),LayerName) || LayerName!=TEXT("ForgeTerrain") ||
        !R->TryGetStringField(TEXT("layer_guid"),LayerGuidText) || !FGuid::ParseExact(LayerGuidText,EGuidFormats::Digits,SessionLayerGuid) ||
        !R->TryGetStringField(TEXT("region_scope"),RegionScope) || (RegionScope!=TEXT("bounded") && RegionScope!=TEXT("entire_landscape"))))
        return Fail(TEXT("invalid_edit_session_scope"),TEXT("Sculpt actions, exact ForgeTerrain GUID and explicit region scope required."));
    if (bSession && RegionScope==TEXT("entire_landscape"))
    {
        int32 X1,Y1,X2,Y2;
        if (!L->GetLandscapeInfo() || !L->GetLandscapeInfo()->GetLandscapeExtent(X1,Y1,X2,Y2) ||
            Region!=FIntRect(X1,Y1,X2+1,Y2+1)) return Fail(TEXT("invalid_entire_landscape_scope"),TEXT("Explicit whole-Landscape approval must match the full extent exactly."));
    }
    if (!bSetup && int64(Region.Width())*Region.Height()>(bSession && RegionScope==TEXT("entire_landscape")?MaxSamples:MaxEditSamples))
        return Fail(TEXT("invalid_scope"),TEXT("Sculpt adoption is limited to 1,048,576 samples including halo."));
    if (bSetup)
    {
        int32 X1,Y1,X2,Y2;
        if (!L->GetLandscapeInfo() || !L->GetLandscapeInfo()->GetLandscapeExtent(X1,Y1,X2,Y2) || Region!=FIntRect(X1,Y1,X2+1,Y2+1))
            return Fail(TEXT("invalid_setup_scope"),TEXT("Layer setup is actor-wide; authorize the exact full Landscape extent explicitly."));
    }
    FString Error; const bool Ready=AdoptionReady(W,L,Region,Error);
    const bool Clean=AdoptionClean(W,L);
    TArray<FString> BackupFiles; FString BackupError;
    const bool bBackupScopeReadable=EnumerateExistingWorldPackageFiles(W,BackupFiles,BackupError);
    const FLandscapeLayer* Layer=L->GetLayerConst(FName(TEXT("ForgeTerrain")));
    if (bSession && (!Layer || !Layer->EditLayer || Layer->EditLayer->GetGuid()!=SessionLayerGuid))
        return Fail(TEXT("edit_layer_mismatch"),TEXT("Session must bind the existing ForgeTerrain layer GUID."));
    const bool LayerReady=AdoptionTargetLayerReady(Layer!=nullptr,Layer && Layer->EditLayer,
        Layer && Layer->EditLayer && Layer->EditLayer->IsLocked(),Layer && Layer->EditLayer && Layer->EditLayer->IsVisible());
    Data->SetStringField(TEXT("authorization_origin"),TEXT("adopted_existing_landscape"));
    Data->SetStringField(TEXT("session_id"),FString::Printf(TEXT("unreal-%u"),FPlatformProcess::GetCurrentProcessId()));
    Data->SetNumberField(TEXT("editor_pid"),FPlatformProcess::GetCurrentProcessId());
    Data->SetStringField(TEXT("project_file"),CanonicalPath(FPaths::GetProjectFilePath()));
    Data->SetStringField(TEXT("world_path"),W->GetOutermost()->GetName());
    Data->SetStringField(TEXT("actor_path"),Path); Data->SetStringField(TEXT("landscape_guid"),GuidText);
    Data->SetBoolField(TEXT("world_partition"),W->GetWorldPartition()!=nullptr);
    Data->SetBoolField(TEXT("potentially_adoptable"),Ready); Data->SetStringField(TEXT("readiness_blocker"),Error);
    Data->SetBoolField(TEXT("checkpoint_source_clean"),Clean);
    Data->SetBoolField(TEXT("target_layer_exists"),Layer!=nullptr); Data->SetBoolField(TEXT("target_layer_ready"),LayerReady);
    Data->SetBoolField(TEXT("target_layer_locked"),Layer && Layer->EditLayer && Layer->EditLayer->IsLocked());
    Data->SetBoolField(TEXT("target_layer_visible"),Layer && Layer->EditLayer && Layer->EditLayer->IsVisible());
    Data->SetBoolField(TEXT("requires_layer_setup"),!Layer);
    Data->SetBoolField(TEXT("local_editor_confirmation_required"),true);
    Data->SetBoolField(TEXT("backup_required"),true);
    Data->SetBoolField(TEXT("backup_scope_readable"),bBackupScopeReadable);
    Data->SetStringField(TEXT("backup_scope_blocker"),BackupError);
    Data->SetNumberField(TEXT("backup_source_file_count"),BackupFiles.Num());
    Data->SetBoolField(TEXT("setup_affects_entire_selected_landscape"),bSetup);
    Data->SetBoolField(TEXT("read_only"),true);
    if (bSession)
    {
        Data->SetStringField(TEXT("authorization_origin"),TEXT("landscape_edit_session"));
        Data->SetStringField(TEXT("layer_guid"),SessionLayerGuid.ToString(EGuidFormats::Digits));
        Data->SetStringField(TEXT("region_scope"),RegionScope);
        Data->SetNumberField(TEXT("requested_lifetime_seconds"),Lifetime);
    }
    TArray<TSharedPtr<FJsonValue>> Status;
    for (const auto& Entry:AdoptionGrants)
    {
        const auto& G=Entry.Value; if (!AdoptionIdentity(G,W,L)) continue;
        auto Item=MakeShared<FJsonObject>(); Item->SetStringField(TEXT("adoption_id"),G.Id);
        Item->SetBoolField(TEXT("approved"),G.bApproved); Item->SetBoolField(TEXT("revoked"),G.bRevoked);
        Item->SetBoolField(TEXT("used"),G.bUsed); Item->SetNumberField(TEXT("expires_at_unix"),G.Expires);
        Item->SetBoolField(TEXT("expired"),G.bApproved && G.Expires<=FDateTime::UtcNow().ToUnixTimestamp());
        Item->SetStringField(TEXT("backup_root"),G.BackupRoot);
        TArray<TSharedPtr<FJsonValue>> Permitted,Bounds;
        for (const FString& A:G.Actions) Permitted.Add(MakeShared<FJsonValueString>(A));
        for (int32 V:{G.Region.Min.X,G.Region.Min.Y,G.Region.Max.X-1,G.Region.Max.Y-1}) Bounds.Add(MakeShared<FJsonValueNumber>(V));
        Item->SetArrayField(TEXT("actions"),Permitted); Item->SetArrayField(TEXT("region"),Bounds);
        Item->SetBoolField(TEXT("checkpoint_files_present"),G.bApproved && AdoptionBackupFilesPresent(G));
        Status.Add(MakeShared<FJsonValueObject>(Item));
    }
    Data->SetArrayField(TEXT("requests"),Status);
    if (Command==TEXT("landscape_adoption_preflight")) return true;
    if (Command==TEXT("landscape_edit_session_preflight")) return true;
    if (!Ready || !Clean || !bBackupScopeReadable || (Parsed.Contains(TEXT("setup_layer")) ? Layer!=nullptr : !LayerReady))
        return Fail(TEXT("adoption_preparation_required"),TEXT("Resolve readiness, unsaved changes, or dedicated layer setup before requesting approval."));
    for (auto It=AdoptionGrants.CreateIterator();It;++It)
        if (!It.Value().bApproved && It.Value().RequestExpires<FDateTime::UtcNow().ToUnixTimestamp()) It.RemoveCurrent();
    if (AdoptionGrants.Num()>=32) return Fail(TEXT("adoption_limit"),TEXT("At most 32 pending/granted adoptions per editor world."));
    FAdoptedLandscapeGrant G;
    G.Id=FGuid::NewGuid().ToString(EGuidFormats::Digits); G.World=W; G.Actor=L;
    G.ActorPath=Path; G.LandscapeGuid=Guid; G.ProjectFile=CanonicalPath(FPaths::GetProjectFilePath());
    G.WorldPackage=W->GetOutermost()->GetName(); G.SessionId=FString::Printf(TEXT("unreal-%u"),FPlatformProcess::GetCurrentProcessId());
    G.Region=Region; G.Actions=Parsed; G.bWorldPartition=W->GetWorldPartition()!=nullptr;
    G.Lifetime=int32(Lifetime); G.RequestExpires=FDateTime::UtcNow().ToUnixTimestamp()+300;
    G.bEditSession=bSession; G.bEntireLandscape=RegionScope==TEXT("entire_landscape");
    G.EditLayerGuid=SessionLayerGuid; G.SessionTransform=L->GetActorTransform();
    Data->SetStringField(TEXT("adoption_id"),G.Id); Data->SetStringField(TEXT("state"),TEXT("pending_local_approval"));
    Data->SetStringField(TEXT("local_editor_command"),TEXT("Forge.Landscape.ApproveAdoption ")+G.Id);
    if (bSession)
    {
        Data->RemoveField(TEXT("adoption_id")); Data->SetStringField(TEXT("edit_session_id"),G.Id);
        Data->SetStringField(TEXT("authorization_origin"),TEXT("landscape_edit_session"));
        Data->SetStringField(TEXT("local_editor_command"),TEXT("Forge.Landscape.ApproveEditSession ")+G.Id);
    }
    AdoptionGrants.Add(G.Id,MoveTemp(G)); return true;
}

void ApproveLandscapeAdoption(const TArray<FString>& Args,bool bSession=false)
{
    if (!IsInGameThread() || Args.Num()!=1 || !GEditor || GEditor->PlayWorld) return;
    FAdoptedLandscapeGrant* G=AdoptionGrants.Find(Args[0]);
    UWorld* W=GEditor->GetEditorWorldContext().World();
    FString Error;
    if (!G || G->bEditSession!=bSession || G->bApproved || G->bRevoked || G->RequestExpires<=FDateTime::UtcNow().ToUnixTimestamp() ||
        !AdoptionIdentity(*G,W,G->Actor.Get()) || !AdoptionReady(W,G->Actor.Get(),G->Region,Error) || !AdoptionClean(W,G->Actor.Get()))
    { UE_LOG(LogTemp,Warning,TEXT("Landscape adoption refused: request stale or unsaved/unsafe world. %s"),*Error); return; }
    FString Actions; for (const FString& A:G->Actions) Actions+=A+TEXT(" ");
    FString Prompt=FString::Printf(TEXT("Approve one UNSAVED Landscape operation?\nSession: %s\nProject: %s\nWorld: %s\nActor: %s\nGUID: %s\nActions: %s\nRegion: %d,%d to %d,%d inclusive\nLifetime: %d seconds\nWorld Partition: %s\nSetup adds a neutral layer across the ENTIRE selected Landscape and preserves existing layers. Sculpt is region-limited.\nA verified full world/external-package checkpoint will be created. No automatic save. Revocation stops future batches; applied rows require recovery."),
        *G->SessionId,*G->ProjectFile,*G->WorldPackage,*G->ActorPath,*G->LandscapeGuid.ToString(EGuidFormats::Digits),*Actions,
        G->Region.Min.X,G->Region.Min.Y,G->Region.Max.X-1,G->Region.Max.Y-1,G->Lifetime,G->bWorldPartition?TEXT("yes"):TEXT("no"));
    if (bSession) Prompt=Prompt.Replace(TEXT("Approve one UNSAVED Landscape operation?"),TEXT("Approve MULTIPLE UNSAVED operations in ONE editing session?"))+
        FString::Printf(TEXT("\nBound layer: ForgeTerrain %s\nScope: %s\nNo per-operation confirmation; every operation still requires preview, recovery and verification. No setup, save or reload permission."),
            *G->EditLayerGuid.ToString(EGuidFormats::Digits),G->bEntireLandscape?TEXT("ENTIRE LANDSCAPE (explicit)"):TEXT("bounded region"));
    if (FMessageDialog::Open(EAppMsgType::YesNo,FText::FromString(Prompt))!=EAppReturnType::Yes) return;
    if (!AdoptionIdentity(*G,W,G->Actor.Get()) || !AdoptionClean(W,G->Actor.Get())) return;
    G->BackupRoot=CanonicalPath(FPaths::ProjectSavedDir()/TEXT("ForgeLandscapeAdoption")/G->Id);
    if (!BackupExistingWorldWriteScope(W,G->Actor.Get(),G->BackupRoot,G->Backup,Error) || !AdoptionBackupsValid(*G))
    { G->bRevoked=true; UE_LOG(LogTemp,Error,TEXT("Landscape adoption backup failed: %s"),*Error); return; }
    auto Manifest=MakeShared<FJsonObject>();
    Manifest->SetStringField(TEXT("origin"),TEXT("adopted_existing_landscape"));
    Manifest->SetStringField(TEXT("world"),G->WorldPackage); Manifest->SetStringField(TEXT("actor"),G->ActorPath);
    Manifest->SetStringField(TEXT("landscape_guid"),G->LandscapeGuid.ToString(EGuidFormats::Digits));
    for (const auto& File:G->Backup.FileHashes) Manifest->SetStringField(File.Key,File.Value);
    FString Json; auto Writer=TJsonWriterFactory<>::Create(&Json); FJsonSerializer::Serialize(Manifest,Writer);
    if (!FFileHelper::SaveStringToFile(Json,*(G->BackupRoot/TEXT("manifest.json")))) { G->bRevoked=true; return; }
    const FMD5Hash ManifestHash=FMD5Hash::HashFile(*(G->BackupRoot/TEXT("manifest.json")));
    if (!ManifestHash.IsValid()) { G->bRevoked=true; return; }
    G->ManifestHash=LexToString(ManifestHash);
    if (bSession && !InitializeEditingSession(*G)) { G->bRevoked=true; return; }
    G->Expires=FDateTime::UtcNow().ToUnixTimestamp()+G->Lifetime; G->bApproved=true;
    if (bSession) { UE_LOG(LogTemp,Display,TEXT("Landscape editing session approved: %s"),*G->Id); }
    else { UE_LOG(LogTemp,Display,TEXT("Landscape adoption approved for one operation: %s"),*G->Id); }
}

FAutoConsoleCommand ApproveLandscapeAdoptionCommand(TEXT("Forge.Landscape.ApproveAdoption"),
    TEXT("Locally confirm a pending Landscape adoption request and create its checkpoint."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args) { ApproveLandscapeAdoption(Args,false); }));
FAutoConsoleCommand ApproveLandscapeEditSessionCommand(TEXT("Forge.Landscape.ApproveEditSession"),
    TEXT("Locally approve an exact multi-operation Landscape editing session."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args) { ApproveLandscapeAdoption(Args,true); }));
FAutoConsoleCommand RevokeLandscapeEditSessionCommand(TEXT("Forge.Landscape.RevokeEditSession"),
    TEXT("Revoke session; future batches stop without restoring applied rows."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args)
    { if (IsInGameThread() && Args.Num()==1) if (auto* G=AdoptionGrants.Find(Args[0])) if(G->bEditSession) G->bRevoked=true; }));
FAutoConsoleCommand RevokeLandscapeAdoptionCommand(TEXT("Forge.Landscape.RevokeAdoption"),
    TEXT("Revoke a Landscape adoption request/grant; future terrain batches stop."),
    FConsoleCommandWithArgsDelegate::CreateLambda([](const TArray<FString>& Args)
    { if (IsInGameThread() && Args.Num()==1) if (auto* G=AdoptionGrants.Find(Args[0])) G->bRevoked=true; }));
