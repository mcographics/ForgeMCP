// Included after the adoption identity/checkpoint primitives. All calls are game-thread only.
bool SessionLayerHashes(ALandscape* L,FGuid Target,FString& TargetHash,TMap<FGuid,FString>& Protected)
{
    if (!L || L->GetLayersConst().Num()<2) return false;
    TargetHash.Empty(); Protected.Empty();
    for (const FLandscapeLayer& Layer:L->GetLayersConst())
    {
        if (!Layer.EditLayer) return false;
        FIntRect B; TArray<uint16> H;
        if (!Read(L,Layer.EditLayer->GetGuid(),B,H)) return false;
        const FString Digest=Hash(H);
        if (Layer.EditLayer->GetGuid()==Target) TargetHash=Digest;
        else Protected.Add(Layer.EditLayer->GetGuid(),Digest);
    }
    return !TargetHash.IsEmpty() && !Protected.IsEmpty();
}

FString EditingSessionLayerState(ALandscape* L)
{
    FString State;
    if (L) for (const FLandscapeLayer& Layer:L->GetLayersConst())
        if (Layer.EditLayer) State+=Layer.EditLayer->GetGuid().ToString()+TEXT(":")+
            Layer.EditLayer->GetName().ToString()+FString::FromInt(Layer.EditLayer->IsVisible())+
            FString::FromInt(Layer.EditLayer->IsLocked())+TEXT(";");
    return State;
}

bool InitializeEditingSession(FAdoptedLandscapeGrant& G)
{
    G.LayerState=EditingSessionLayerState(G.Actor.Get());
    return SessionLayerHashes(G.Actor.Get(),G.EditLayerGuid,G.ExpectedTargetHash,G.ProtectedLayerHashes);
}

bool SessionProtectedLayersMatch(const FAdoptedLandscapeGrant& G)
{
    FString Target; TMap<FGuid,FString> Protected;
    return EditingSessionLayerState(G.Actor.Get())==G.LayerState && SessionLayerHashes(G.Actor.Get(),G.EditLayerGuid,Target,Protected) &&
        Protected.OrderIndependentCompareEqual(G.ProtectedLayerHashes);
}

bool SessionWorldSafe(const FAdoptedLandscapeGrant& G)
{
    if (!G.bEditSession) return AdoptionClean(G.World.Get(),G.Actor.Get());
    if (!G.ActiveOperation.IsEmpty() || EditingSessionLayerState(G.Actor.Get())!=G.LayerState) return false;
    FString Target; TMap<FGuid,FString> Protected;
    if (!SessionLayerHashes(G.Actor.Get(),G.EditLayerGuid,Target,Protected) || Target!=G.ExpectedTargetHash ||
        !Protected.OrderIndependentCompareEqual(G.ProtectedLayerHashes)) return false;
    for (TObjectIterator<UPackage> It;It;++It)
        if (It->IsDirty() && It->GetName().StartsWith(TEXT("/Game/")) && !G.OwnedDirtyPackages.Contains(It->GetName())) return false;
    // An out-of-band save/disk edit requires a newly reviewed checkpoint, never silent rebasing.
    return AdoptionBackupsValid(G) && AdoptionCheckpointScopeMatches(G,G.World.Get());
}

bool SessionExpectedFullAfter(ALandscape* L,FGuid Layer,const FIntRect& Patch,const TArray<uint16>& After,FString& Digest)
{
    FIntRect Full; TArray<uint16> H;
    if (!Read(L,Layer,Full,H) || After.Num()!=Patch.Width()*Patch.Height() || !AdoptionRegionContains(Full,Patch)) return false;
    for(int32 Y=Patch.Min.Y;Y<Patch.Max.Y;++Y) for(int32 X=Patch.Min.X;X<Patch.Max.X;++X)
        H[(Y-Full.Min.Y)*Full.Width()+X-Full.Min.X]=After[(Y-Patch.Min.Y)*Patch.Width()+X-Patch.Min.X];
    Digest=Hash(H); return true;
}

bool SaveSessionJson(const TSharedRef<FJsonObject>& Data,const FString& File)
{
    if (IFileManager::Get().FileExists(*File)) return false;
    FString Json; auto Writer=TJsonWriterFactory<>::Create(&Json); FJsonSerializer::Serialize(Data,Writer);
    if (!FFileHelper::SaveStringToFile(Json,*File)) return false;
    FString Verify; return FFileHelper::LoadFileToString(Verify,*File) && Verify==Json;
}

// Complete in-memory layer snapshots supplement the immutable approval disk checkpoint.
// They preserve prior UNSAVED operations as well as the pre-operation target region backup.
bool BackupEditingSessionOperation(FAdoptedLandscapeGrant& G,ALandscape* L,const FString& Id,
    const FString& OperationRoot,const TSharedRef<FJsonObject>& Request,FString& Manifest)
{
    if (!SessionWorldSafe(G) || G.Operations.Num()>=64) return false;
    auto Meta=MakeShared<FJsonObject>();
    Meta->SetStringField(TEXT("edit_session_id"),G.Id); Meta->SetStringField(TEXT("operation_id"),Id);
    Meta->SetStringField(TEXT("project_file"),G.ProjectFile); Meta->SetStringField(TEXT("world"),G.WorldPackage);
    Meta->SetStringField(TEXT("actor"),G.ActorPath); Meta->SetStringField(TEXT("landscape_guid"),G.LandscapeGuid.ToString(EGuidFormats::Digits));
    Meta->SetStringField(TEXT("target_layer_guid"),G.EditLayerGuid.ToString(EGuidFormats::Digits));
    Meta->SetStringField(TEXT("transform"),L->GetTransform().ToString());
    Meta->SetObjectField(TEXT("request"),Request); Meta->SetNumberField(TEXT("created_at_unix"),FDateTime::UtcNow().ToUnixTimestamp());
    TArray<TSharedPtr<FJsonValue>> Files;
    for (const FLandscapeLayer& Layer:L->GetLayersConst())
    {
        FIntRect B; TArray<uint16> H;
        if (!Layer.EditLayer || !Read(L,Layer.EditLayer->GetGuid(),B,H)) return false;
        const FString File=OperationRoot/TEXT("layer_")+Layer.EditLayer->GetGuid().ToString(EGuidFormats::Digits)+TEXT(".r16");
        if (IFileManager::Get().FileExists(*File) || !FFileHelper::SaveArrayToFile(
            TArrayView<const uint8>(reinterpret_cast<const uint8*>(H.GetData()),H.Num()*sizeof(uint16)),*File)) return false;
        TArray<uint8> Verify;
        if (!FFileHelper::LoadFileToArray(Verify,*File) || Verify.Num()!=H.Num()*int32(sizeof(uint16)) ||
            FMemory::Memcmp(Verify.GetData(),H.GetData(),Verify.Num())!=0) return false;
        auto Item=MakeShared<FJsonObject>(); Item->SetStringField(TEXT("file"),FPaths::GetCleanFilename(File));
        Item->SetStringField(TEXT("md5"),LexToString(FMD5Hash::HashFile(*File)));
        Item->SetNumberField(TEXT("width"),B.Width()); Item->SetNumberField(TEXT("height"),B.Height());
        Item->SetNumberField(TEXT("min_x"),B.Min.X); Item->SetNumberField(TEXT("min_y"),B.Min.Y);
        Files.Add(MakeShared<FJsonValueObject>(Item));
    }
    Meta->SetArrayField(TEXT("layer_files"),Files);
    const FString File=OperationRoot/TEXT("edit_session_checkpoint.json");
    if (!SaveSessionJson(Meta,File)) return false;
    Manifest=LexToString(FMD5Hash::HashFile(*File));
    G.ActiveOperation=Id; G.Operations.Add(Id); return true;
}

bool EditingSessionRecoveryValid(const FString& Root,const FString& ManifestHash)
{
    const FString File=Root/TEXT("edit_session_checkpoint.json");
    if (ManifestHash.IsEmpty() || LexToString(FMD5Hash::HashFile(*File))!=ManifestHash) return false;
    FString Text; TSharedPtr<FJsonObject> Meta;
    if (!FFileHelper::LoadFileToString(Text,*File) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Meta) || !Meta) return false;
    const TArray<TSharedPtr<FJsonValue>>* Files=nullptr;
    if(!Meta->TryGetArrayField(TEXT("layer_files"),Files) || Files->Num()<2) return false;
    for(const auto& Value:*Files)
    {
        auto Item=Value->AsObject(); FString Name,Digest;
        if (!Item || !Item->TryGetStringField(TEXT("file"),Name) || Name!=FPaths::GetCleanFilename(Name) ||
            !Item->TryGetStringField(TEXT("md5"),Digest) || LexToString(FMD5Hash::HashFile(*(Root/Name)))!=Digest) return false;
    }
    return true;
}

bool HandleEditingSessionControl(const FString& Command,const TSharedRef<FJsonObject>& Args,UWorld* W,
    TSharedRef<FJsonObject> Data,FString& Code,FString& Message)
{
    FString Id;
    if (Args->Values.Num()!=1 || !Args->TryGetStringField(TEXT("edit_session_id"),Id))
    { Code=TEXT("invalid_arguments"); Message=TEXT("Expected only edit_session_id."); return false; }
    FAdoptedLandscapeGrant* G=AdoptionGrants.Find(Id.ToUpper());
    if (!G || !G->bEditSession || !AdoptionIdentity(*G,W,G->Actor.Get()))
    { Code=TEXT("edit_session_not_found"); Message=TEXT("Exact process/project/world/Landscape/layer session required."); return false; }
    if (Command==TEXT("landscape_edit_session_revoke")) G->bRevoked=true;
    Data->SetStringField(TEXT("authorization_origin"),TEXT("landscape_edit_session"));
    Data->SetStringField(TEXT("edit_session_id"),G->Id); Data->SetBoolField(TEXT("approved"),G->bApproved);
    Data->SetBoolField(TEXT("revoked"),G->bRevoked); Data->SetNumberField(TEXT("expires_at_unix"),G->Expires);
    Data->SetBoolField(TEXT("expired"),G->bApproved && G->Expires<=FDateTime::UtcNow().ToUnixTimestamp());
    Data->SetStringField(TEXT("layer_guid"),G->EditLayerGuid.ToString(EGuidFormats::Digits));
    Data->SetStringField(TEXT("active_operation"),G->ActiveOperation);
    Data->SetStringField(TEXT("backup_root"),G->BackupRoot);
    Data->SetBoolField(TEXT("whole_landscape_explicit"),G->bEntireLandscape);
    TArray<TSharedPtr<FJsonValue>> Ops,Region,Actions;
    for(const FString& Op:G->Operations)
    {
        auto Item=MakeShared<FJsonObject>(); Item->SetStringField(TEXT("operation_id"),Op);
        const FString Root=CanonicalPath(FPaths::ProjectSavedDir()/TEXT("ForgeLandscape")/Op);
        Item->SetStringField(TEXT("recovery_root"),Root);
        FString Text; TSharedPtr<FJsonObject> Result;
        if(FFileHelper::LoadFileToString(Text,*(Root/TEXT("edit_session_result.json"))) &&
            FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Result) && Result)
            Item->SetObjectField(TEXT("result"),Result.ToSharedRef());
        Ops.Add(MakeShared<FJsonValueObject>(Item));
    }
    for(const FString& Action:G->Actions) Actions.Add(MakeShared<FJsonValueString>(Action));
    for(int32 V:{G->Region.Min.X,G->Region.Min.Y,G->Region.Max.X-1,G->Region.Max.Y-1}) Region.Add(MakeShared<FJsonValueNumber>(V));
    Data->SetArrayField(TEXT("operations"),Ops); Data->SetArrayField(TEXT("region"),Region); Data->SetArrayField(TEXT("actions"),Actions);
    Data->SetBoolField(TEXT("read_only"),Command==TEXT("landscape_edit_session_status")); return true;
}
