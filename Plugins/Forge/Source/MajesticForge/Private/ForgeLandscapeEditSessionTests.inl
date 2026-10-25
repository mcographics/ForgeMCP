// Pure authorization and generated Saved-fixture tests; never mutate an open scene.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeEditingSessionPolicyTest,"Forge.Landscape.EditSession.Authorization",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeEditingSessionPolicyTest::RunTest(const FString& Parameters)
{
    FAdoptedLandscapeGrant G; G.bEditSession=true; G.bApproved=true; G.Expires=7300;
    G.SessionId=TEXT("unreal-42"); G.ProjectFile=TEXT("G:/Fixture/Test.uproject");
    G.WorldPackage=TEXT("/Game/Fixture"); G.ActorPath=TEXT("/Game/Fixture.Fixture:PersistentLevel.Landscape");
    G.LandscapeGuid=FGuid(1,2,3,4); G.EditLayerGuid=FGuid(5,6,7,8); G.Actions.Add(TEXT("apply_heightmap"));
    TestTrue(TEXT("first operation"),AdoptionGrantActive(G,TEXT("apply_heightmap"),100,false));
    G.bUsed=true; G.Operations.Add(TEXT("first"));
    TestTrue(TEXT("second operation same approval"),AdoptionGrantActive(G,TEXT("apply_heightmap"),101,false));
    G.Operations.Add(TEXT("second"));
    TestTrue(TEXT("subsequent operation same approval"),AdoptionGrantActive(G,TEXT("apply_heightmap"),102,false));
    TestFalse(TEXT("setup not implicitly authorized"),AdoptionGrantActive(G,TEXT("setup_layer"),102,false));
    TestFalse(TEXT("expiry is exclusive"),AdoptionGrantActive(G,TEXT("apply_heightmap"),7300,false));
    G.bRevoked=true;
    TestFalse(TEXT("revoke blocks queued operations"),AdoptionGrantActive(G,TEXT("apply_heightmap"),102,false));
    TestFalse(TEXT("revoke blocks running batches"),AdoptionGrantActive(G,TEXT("apply_heightmap"),102,true));
    G.bRevoked=false; G.bEditSession=false;
    TestFalse(TEXT("legacy single-use remains consumed"),AdoptionGrantActive(G,TEXT("apply_heightmap"),102,false));
    TestTrue(TEXT("legacy in-flight continuation"),AdoptionGrantActive(G,TEXT("apply_heightmap"),102,true));
    TestFalse(TEXT("wrong project"),AdoptionIdentityValues(G,G.SessionId,TEXT("G:/Wrong/Test.uproject"),G.WorldPackage,G.ActorPath,G.LandscapeGuid,false));
    TestFalse(TEXT("wrong Landscape"),AdoptionIdentityValues(G,G.SessionId,G.ProjectFile,G.WorldPackage,G.ActorPath,FGuid(),false));
    TestFalse(TEXT("wrong Editor"),AdoptionIdentityValues(G,TEXT("unreal-43"),G.ProjectFile,G.WorldPackage,G.ActorPath,G.LandscapeGuid,false));
    TestFalse(TEXT("unauthorized halo"),AdoptionRegionContains(FIntRect(0,0,8,8),FIntRect(-1,0,5,5)));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeEditingSessionRecoveryTest,"Forge.Landscape.EditSession.RecoveryIntegrity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeEditingSessionRecoveryTest::RunTest(const FString& Parameters)
{
    const FString Root=CanonicalPath(FPaths::ProjectSavedDir()/TEXT("ForgeEditSessionAutomation")/FGuid::NewGuid().ToString(EGuidFormats::Digits));
    IFileManager::Get().MakeDirectory(*Root,true);
    TArray<TSharedPtr<FJsonValue>> Files;
    for (const TCHAR* Name:{TEXT("original.r16"),TEXT("target.r16")})
    {
        const FString Path=Root/Name; FFileHelper::SaveStringToFile(TEXT("fixture-height-bytes"),*Path);
        auto Item=MakeShared<FJsonObject>(); Item->SetStringField(TEXT("file"),Name);
        Item->SetStringField(TEXT("md5"),LexToString(FMD5Hash::HashFile(*Path))); Files.Add(MakeShared<FJsonValueObject>(Item));
    }
    auto Meta=MakeShared<FJsonObject>(); Meta->SetArrayField(TEXT("layer_files"),Files);
    const FString Manifest=Root/TEXT("edit_session_checkpoint.json");
    TestTrue(TEXT("write exclusive recovery manifest"),SaveSessionJson(Meta,Manifest));
    TestFalse(TEXT("never overwrite recovery"),SaveSessionJson(Meta,Manifest));
    const FString Hash=LexToString(FMD5Hash::HashFile(*Manifest));
    TestTrue(TEXT("readable independent fixture"),EditingSessionRecoveryValid(Root,Hash));
    FFileHelper::SaveStringToFile(TEXT("corrupt"),*(Root/TEXT("target.r16")));
    TestFalse(TEXT("tampering halts operation"),EditingSessionRecoveryValid(Root,Hash));
    TestTrue(TEXT("failed recovery retains manifest"),IFileManager::Get().FileExists(*Manifest));
    // Delete only this generated Saved fixture after assertions, never project Content.
    IFileManager::Get().DeleteDirectory(*Root,false,true);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeEditingSessionNativeSequenceTest,"Forge.Landscape.EditSession.IsolatedNativeSequence",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeEditingSessionNativeSequenceTest::RunTest(const FString& Parameters)
{
    // This mutating fixture may ONLY run in our newly generated disposable host.
    // Running the normal regression suite in production must not change its world.
    if (!CanonicalPath(FPaths::ProjectDir()).Contains(TEXT("/LandscapeEditSession_Dev_")) ||
        !IFileManager::Get().FileExists(*(FPaths::ProjectDir()/TEXT(".forgemcp-edit-session-tests"))))
    { AddInfo(TEXT("Isolated native sequence skipped: disposable host marker required.")); return true; }
    const FString Map=TEXT("/Game/ForgeMCPTests/Landscape/EditSession_")+FGuid::NewGuid().ToString(EGuidFormats::Digits);
    if (!GEditor || GEditor->PlayWorld || !GEditor->GetEditorSubsystem<ULevelEditorSubsystem>()->NewLevel(Map,false))
    { AddError(TEXT("Cannot create the disposable native fixture map.")); return false; }
    UWorld* W=GEditor->GetEditorWorldContext().World();
    ALandscape* L=W->SpawnActor<ALandscape>();
    if(!L) return false;
    L->bCanHaveLayersContent=true; L->SetActorScale3D(FVector(100));
    TMap<FGuid,TArray<uint16>> Heights; Heights.Add(FGuid()).Init(32768,64);
    TMap<FGuid,TArray<FLandscapeImportLayerInfo>> Materials; Materials.Add(FGuid());
    L->Import(FGuid::NewGuid(),0,0,7,7,1,7,Heights,TEXT(""),Materials,ELandscapeImportAlphamapType::Additive,TArrayView<const FLandscapeLayer>());
    if(L->GetLayersConst().Num()!=1) return false;
    L->GetLayersConst()[0].EditLayer->SetName(TEXT("Original"),true);
    const int32 Index=L->CreateLayer(FName(TEXT("ForgeTerrain")));
    if(Index==INDEX_NONE) return false;
    const FGuid Layer=L->GetLayersConst()[Index].EditLayer->GetGuid();
    TArray<uint16> Neutral; Neutral.Init(32768,64);
    { FLandscapeEditDataInterface Edit(L->GetLandscapeInfo(),Layer); Edit.SetHeightData(0,0,7,7,Neutral.GetData(),8,true); Edit.Flush(); }
    L->RequestLayersContentUpdate(ELandscapeLayerUpdateMode::Update_All); L->GetLandscapeInfo()->ForceLayersFullUpdate();
    if(!UEditorLoadingAndSavingUtils::SaveMap(W,Map)) return false;
    FForgeLandscape Automation; Automation.Tick();
    auto SessionRequest=MakeShared<FJsonObject>();
    SessionRequest->SetStringField(TEXT("actor_path"),L->GetPathName());
    SessionRequest->SetStringField(TEXT("project_file"),CanonicalPath(FPaths::GetProjectFilePath()));
    SessionRequest->SetStringField(TEXT("world_path"),W->GetOutermost()->GetName());
    SessionRequest->SetStringField(TEXT("landscape_guid"),L->GetLandscapeGuid().ToString(EGuidFormats::Digits));
    SessionRequest->SetStringField(TEXT("layer_guid"),Layer.ToString(EGuidFormats::Digits));
    SessionRequest->SetStringField(TEXT("layer_name"),TEXT("ForgeTerrain"));
    SessionRequest->SetStringField(TEXT("region_scope"),TEXT("entire_landscape"));
    SessionRequest->SetNumberField(TEXT("editor_pid"),FPlatformProcess::GetCurrentProcessId());
    SessionRequest->SetNumberField(TEXT("lifetime_seconds"),7200); SessionRequest->SetBoolField(TEXT("world_partition"),false);
    TArray<TSharedPtr<FJsonValue>> SessionBounds,SessionActions;
    for(int32 V:{0,0,7,7}) SessionBounds.Add(MakeShared<FJsonValueNumber>(V));
    SessionActions.Add(MakeShared<FJsonValueString>(TEXT("apply_heightmap")));
    SessionRequest->SetArrayField(TEXT("region"),SessionBounds); SessionRequest->SetArrayField(TEXT("actions"),SessionActions);
    auto SessionArgs=MakeShared<FJsonObject>(); SessionArgs->SetObjectField(TEXT("request"),SessionRequest);
    auto Preflight=MakeShared<FJsonObject>(); auto Pending=MakeShared<FJsonObject>(); FString SessionCode,SessionMessage;
    if(!Automation.Handle(TEXT("landscape_edit_session_preflight"),SessionArgs,Preflight,SessionCode,SessionMessage) ||
       !Automation.Handle(TEXT("landscape_edit_session_request"),SessionArgs,Pending,SessionCode,SessionMessage))
    { AddError(SessionCode+TEXT(": ")+SessionMessage); return false; }
    TestEqual(TEXT("native two-hour request"),Preflight->GetNumberField(TEXT("requested_lifetime_seconds")),7200.0);
    TestEqual(TEXT("explicit whole fixture extent"),Preflight->GetStringField(TEXT("region_scope")),FString(TEXT("entire_landscape")));
    const FString PendingId=Pending->GetStringField(TEXT("edit_session_id"));
    TestFalse(TEXT("MCP request cannot approve itself"),AdoptionGrants.FindChecked(PendingId).bApproved);
    TestTrue(TEXT("local-only editing approval command"),Pending->GetStringField(TEXT("local_editor_command")).StartsWith(TEXT("Forge.Landscape.ApproveEditSession ")));
    // Fixture models the owner-accepted state. It never auto-accepts a production dialog.
    FAdoptedLandscapeGrant Grant=AdoptionGrants.FindChecked(PendingId); AdoptionGrants.Remove(PendingId);
    Grant.bApproved=true;
    Grant.ProjectFile=CanonicalPath(FPaths::GetProjectFilePath()); Grant.SessionId=FString::Printf(TEXT("unreal-%u"),FPlatformProcess::GetCurrentProcessId());
    Grant.WorldPackage=W->GetOutermost()->GetName(); Grant.ActorPath=L->GetPathName(); Grant.LandscapeGuid=L->GetLandscapeGuid();
    Grant.EditLayerGuid=Layer; Grant.SessionTransform=L->GetActorTransform(); Grant.Region=FIntRect(0,0,8,8);
    Grant.Actions.Add(TEXT("apply_heightmap")); Grant.Expires=FDateTime::UtcNow().ToUnixTimestamp()+7200;
    Grant.BackupRoot=CanonicalPath(FPaths::ProjectSavedDir()/TEXT("EditSessionNativeFixture")/Grant.Id);
    FString Error;
    if(!BackupExistingWorldWriteScope(W,L,Grant.BackupRoot,Grant.Backup,Error) || !InitializeEditingSession(Grant)) return false;
    auto Checkpoint=MakeShared<FJsonObject>(); Checkpoint->SetStringField(TEXT("fixture"),TEXT("test-owner-approved-state"));
    if(!SaveSessionJson(Checkpoint,Grant.BackupRoot/TEXT("manifest.json"))) return false;
    Grant.ManifestHash=LexToString(FMD5Hash::HashFile(*(Grant.BackupRoot/TEXT("manifest.json"))));
    const FString SessionId=Grant.Id; AdoptionGrants.Add(SessionId,Grant);
    auto Request=[&](int32 X1,int32 Y1,int32 X2,int32 Y2,double Height)
    {
        auto R=MakeShared<FJsonObject>(); R->SetStringField(TEXT("action"),TEXT("apply_heightmap"));
        R->SetStringField(TEXT("actor_path"),L->GetPathName()); R->SetStringField(TEXT("edit_session_id"),SessionId);
        TArray<TSharedPtr<FJsonValue>> Region,Samples;
        for(int32 V:{X1,Y1,X2,Y2}) Region.Add(MakeShared<FJsonValueNumber>(V));
        for(int32 I=0;I<(X2-X1+1)*(Y2-Y1+1);++I) Samples.Add(MakeShared<FJsonValueNumber>(Height));
        R->SetArrayField(TEXT("region"),Region); R->SetArrayField(TEXT("samples_cm"),Samples);
        R->SetNumberField(TEXT("height_cm"),0); R->SetNumberField(TEXT("strength"),1); R->SetNumberField(TEXT("wavelength_vertices"),32);
        R->SetNumberField(TEXT("rows_per_stage"),8); R->SetNumberField(TEXT("stage_interval_seconds"),0.1);
        auto Args=MakeShared<FJsonObject>(); Args->SetObjectField(TEXT("request"),R); return Args;
    };
    auto Run=[&](const TSharedRef<FJsonObject>& Args,bool bRevoke)
    {
        auto Preview=MakeShared<FJsonObject>(); FString Code,Message;
        if(!Automation.Handle(TEXT("landscape_preview"),Args,Preview,Code,Message))
        { AddError(Code+TEXT(": ")+Message); return false; }
        const FString Id=Preview->GetStringField(TEXT("preview_id")); auto Apply=MakeShared<FJsonObject>();
        Apply->SetStringField(TEXT("preview_id"),Id); Apply->SetStringField(TEXT("confirmation"),Id);
        auto Result=MakeShared<FJsonObject>();
        if(!Automation.Handle(TEXT("landscape_apply"),Apply,Result,Code,Message))
        { AddError(Code+TEXT(": ")+Message); return false; }
        if(bRevoke) AdoptionGrants.FindChecked(SessionId).bRevoked=true;
        FPlatformProcess::Sleep(.12f); Automation.Tick(); Automation.Tick();
        auto Status=MakeShared<FJsonObject>(); auto Query=MakeShared<FJsonObject>(); Query->SetStringField(TEXT("job_id"),Id);
        if(!Automation.Handle(TEXT("landscape_job_status"),Query,Status,Code,Message)) return false;
        const FString State=Status->GetStringField(TEXT("state"));
        TestEqual(TEXT("native terminal state"),State,bRevoke?FString(TEXT("interrupted_partial")):FString(TEXT("completed")));
        if(bRevoke) TestEqual(TEXT("revocation before first batch writes zero rows"),Status->GetNumberField(TEXT("rows_applied")),0.0);
        TestTrue(TEXT("operation evidence retained"),IFileManager::Get().FileExists(*(FPaths::ProjectSavedDir()/TEXT("ForgeLandscape")/Id/TEXT("edit_session_checkpoint.json"))));
        L->GetLandscapeInfo()->ForceLayersFullUpdate(); return State==(bRevoke?TEXT("interrupted_partial"):TEXT("completed"));
    };
    TestTrue(TEXT("first native sculpt using fixture owner approval"),Run(Request(1,1,3,3,10),false));
    TestTrue(TEXT("second native sculpt without another approval or save"),Run(Request(4,4,6,6,-20),false));
    auto& Active=AdoptionGrants.FindChecked(SessionId);
    FString Target; TMap<FGuid,FString> Protected;
    TestTrue(TEXT("layer readback"),SessionLayerHashes(L,Layer,Target,Protected));
    TestTrue(TEXT("Original heights unchanged"),Protected.OrderIndependentCompareEqual(Grant.ProtectedLayerHashes));
    TestNotEqual(TEXT("target heights changed"),Target,Grant.ExpectedTargetHash);
    TestEqual(TEXT("two operation checkpoints"),Active.Operations.Num(),2);
    auto HeightArgs=MakeShared<FJsonObject>(); auto HeightRequest=MakeShared<FJsonObject>();
    HeightRequest->SetStringField(TEXT("actor_path"),L->GetPathName());
    HeightRequest->SetStringField(TEXT("layer_guid"),Layer.ToString(EGuidFormats::Digits));
    TArray<TSharedPtr<FJsonValue>> ReadRegionValues;
    for(int32 V:{1,1,1,1}) ReadRegionValues.Add(MakeShared<FJsonValueNumber>(V));
    HeightRequest->SetArrayField(TEXT("region"),ReadRegionValues); HeightArgs->SetObjectField(TEXT("request"),HeightRequest);
    auto HeightResult=MakeShared<FJsonObject>(); FString ReadCode,ReadMessage;
    TestTrue(TEXT("bounded native height read tool"),Automation.Handle(TEXT("landscape_read_region"),HeightArgs,HeightResult,ReadCode,ReadMessage));
    if(HeightResult->HasField(TEXT("samples_cm")))
        TestEqual(TEXT("quantized first edit remains after second edit"),HeightResult->GetArrayField(TEXT("samples_cm"))[0]->AsNumber(),10.15625);
    TArray<uint8> Prior;
    const FString SecondCheckpoint=FPaths::ProjectSavedDir()/TEXT("ForgeLandscape")/Active.Operations[1]/
        (TEXT("layer_")+Layer.ToString(EGuidFormats::Digits)+TEXT(".r16"));
    TestTrue(TEXT("pre-second-edit complete layer snapshot readable"),FFileHelper::LoadFileToArray(Prior,*SecondCheckpoint));
    if(Prior.Num()==128)
    {
        const uint16* Values=reinterpret_cast<const uint16*>(Prior.GetData());
        TestEqual(TEXT("prior unsaved first edit protected"),Values[9],uint16(32781));
        TestEqual(TEXT("second region was neutral before second edit"),Values[36],uint16(32768));
    }
    auto Rejected=MakeShared<FJsonObject>(); FString Code,Message;
    const FString SavedProject=Active.ProjectFile; Active.ProjectFile=TEXT("G:/Wrong/Test.uproject");
    TestFalse(TEXT("wrong project rejected natively"),Automation.Handle(TEXT("landscape_preview"),Request(1,1,3,3,10),Rejected,Code,Message)); Active.ProjectFile=SavedProject;
    const FGuid SavedGuid=Active.LandscapeGuid; Active.LandscapeGuid=FGuid::NewGuid();
    TestFalse(TEXT("wrong Landscape rejected natively"),Automation.Handle(TEXT("landscape_preview"),Request(1,1,3,3,10),Rejected,Code,Message)); Active.LandscapeGuid=SavedGuid;
    Active.EditLayerGuid=FGuid::NewGuid();
    TestFalse(TEXT("wrong edit layer rejected natively"),Automation.Handle(TEXT("landscape_preview"),Request(1,1,3,3,10),Rejected,Code,Message)); Active.EditLayerGuid=Layer;
    Active.Region=FIntRect(0,0,7,8);
    TestFalse(TEXT("outside authorized region rejected natively"),Automation.Handle(TEXT("landscape_preview"),Request(7,7,7,7,10),Rejected,Code,Message)); Active.Region=Grant.Region;
    const int64 Expiry=Active.Expires; Active.Expires=FDateTime::UtcNow().ToUnixTimestamp();
    TestFalse(TEXT("expired session rejected natively"),Automation.Handle(TEXT("landscape_preview"),Request(1,1,3,3,10),Rejected,Code,Message)); Active.Expires=Expiry;
    TestTrue(TEXT("revocation stops a third operation before its first batch"),Run(Request(1,1,3,3,30),true));
    TestTrue(TEXT("revoked future operation rejected"),!Automation.Handle(TEXT("landscape_preview"),Request(1,1,3,3,40),Rejected,Code,Message));
    Automation.Reset(); return !HasAnyErrors();
}
