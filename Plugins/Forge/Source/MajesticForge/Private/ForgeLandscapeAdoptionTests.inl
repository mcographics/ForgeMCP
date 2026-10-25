// Pure policy automation: no active world, assets, connection or process is mutated.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeAdoptionPolicyTest,"Forge.Landscape.Adoption.Authorization",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeAdoptionPolicyTest::RunTest(const FString& Parameters)
{
    FAdoptedLandscapeGrant G;
    G.SessionId=TEXT("unreal-123"); G.ProjectFile=TEXT("G:/Project/Game.uproject");
    G.WorldPackage=TEXT("/Game/World"); G.ActorPath=TEXT("/Game/World.World:PersistentLevel.Landscape");
    G.LandscapeGuid=FGuid(1,2,3,4); G.bWorldPartition=true;
    G.Actions.Add(TEXT("raise")); G.Expires=200;
    auto Identity=[&](const FString& Session,const FString& Project,const FString& World,
        const FString& Actor,const FGuid& Guid,bool WP)
    { return AdoptionIdentityValues(G,Session,Project,World,Actor,Guid,WP); };
    TestTrue(TEXT("exact adopted identity"),Identity(G.SessionId,G.ProjectFile,G.WorldPackage,G.ActorPath,G.LandscapeGuid,true));
    TestFalse(TEXT("wrong session/process"),Identity(TEXT("unreal-124"),G.ProjectFile,G.WorldPackage,G.ActorPath,G.LandscapeGuid,true));
    TestFalse(TEXT("wrong project"),Identity(G.SessionId,TEXT("G:/Other/Game.uproject"),G.WorldPackage,G.ActorPath,G.LandscapeGuid,true));
    TestFalse(TEXT("wrong world"),Identity(G.SessionId,G.ProjectFile,TEXT("/Game/Other"),G.ActorPath,G.LandscapeGuid,true));
    TestFalse(TEXT("wrong actor"),Identity(G.SessionId,G.ProjectFile,G.WorldPackage,TEXT("OtherActor"),G.LandscapeGuid,true));
    TestFalse(TEXT("wrong GUID"),Identity(G.SessionId,G.ProjectFile,G.WorldPackage,G.ActorPath,FGuid(5,6,7,8),true));
    TestFalse(TEXT("wrong partition state"),Identity(G.SessionId,G.ProjectFile,G.WorldPackage,G.ActorPath,G.LandscapeGuid,false));
    TestFalse(TEXT("request cannot approve itself"),AdoptionGrantActive(G,TEXT("raise"),100,false));
    G.bApproved=true;
    TestTrue(TEXT("approved operation"),AdoptionGrantActive(G,TEXT("raise"),100,false));
    TestFalse(TEXT("unapproved operation"),AdoptionGrantActive(G,TEXT("flatten"),100,false));
    TestFalse(TEXT("expiry boundary"),AdoptionGrantActive(G,TEXT("raise"),200,false));
    G.bRevoked=true;
    TestFalse(TEXT("revoked running job"),AdoptionGrantActive(G,TEXT("raise"),100,true));
    G.bRevoked=false; G.bUsed=true;
    TestFalse(TEXT("single use apply"),AdoptionGrantActive(G,TEXT("raise"),100,false));
    TestTrue(TEXT("continuation of consumed grant job"),AdoptionGrantActive(G,TEXT("raise"),100,true));
    const FIntRect Region(0,0,50,50);
    TestTrue(TEXT("localized region including halo"),AdoptionRegionContains(Region,FIntRect(10,10,40,40)));
    TestFalse(TEXT("outside region"),AdoptionRegionContains(Region,FIntRect(10,10,51,40)));
    TestFalse(TEXT("empty region"),AdoptionRegionContains(Region,FIntRect(10,10,10,40)));
    TestFalse(TEXT("missing checkpoint"),AdoptionBackupsValid(G));
    TestFalse(TEXT("missing manifest"),AdoptionBackupFilesPresent(G));
    TestTrue(TEXT("all proxies accessible"),AdoptionComponentsAccessible(16,16,0,true));
    TestFalse(TEXT("unloaded region"),AdoptionComponentsAccessible(16,15,1,true));
    TestFalse(TEXT("mismatched descriptor counts"),AdoptionComponentsAccessible(16,15,0,true));
    TestFalse(TEXT("unregistered components"),AdoptionComponentsAccessible(16,16,0,false));
    TestTrue(TEXT("dedicated visible unlocked layer"),AdoptionTargetLayerReady(true,true,false,true));
    TestFalse(TEXT("missing layer"),AdoptionTargetLayerReady(false,false,false,true));
    TestFalse(TEXT("locked layer"),AdoptionTargetLayerReady(true,true,true,true));
    TestFalse(TEXT("invisible layer"),AdoptionTargetLayerReady(true,true,false,false));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeAdoptionBackupTest,"Forge.Landscape.Adoption.BackupIntegrity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeAdoptionBackupTest::RunTest(const FString& Parameters)
{
    FAdoptedLandscapeGrant G;
    // Source must stay under ProjectDir even when -UserDir redirects generated Saved.
    const FString Root=CanonicalPath(FPaths::ProjectDir()/TEXT("Saved/ForgeAdoptionAutomation")/FGuid::NewGuid().ToString(EGuidFormats::Digits));
    const FString Source=Root/TEXT("source.data"); G.BackupRoot=Root/TEXT("checkpoint");
    IFileManager::Get().MakeDirectory(*Root,true);
    TestTrue(TEXT("temporary fixture source"),FFileHelper::SaveStringToFile(TEXT("original"),*Source));
    FString Relative=Source; FPaths::MakePathRelativeTo(Relative,*FPaths::ProjectDir());
    const FString Backup=G.BackupRoot/TEXT("before")/Relative;
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Backup),true);
    TestEqual(TEXT("fixture checkpoint copy"),IFileManager::Get().Copy(*Backup,*Source,false),uint32(COPY_OK));
    G.Backup.FileHashes.Add(Source.ToLower(),LexToString(FMD5Hash::HashFile(*Source)));
    TestTrue(TEXT("verified recoverable bytes"),AdoptionBackupsValid(G));
    FFileHelper::SaveStringToFile(TEXT("tampered"),*Backup);
    TestFalse(TEXT("tampered checkpoint rejected"),AdoptionBackupsValid(G));
    IFileManager::Get().Delete(*Backup);
    TestFalse(TEXT("missing checkpoint rejected"),AdoptionBackupsValid(G));
    // Test artifacts live in one generated Saved directory, never a content package.
    IFileManager::Get().DeleteDirectory(*Root,false,true);
    return true;
}
