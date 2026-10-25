#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"
class ALandscape;
class UWorld;
class UWorldPartitionEditorLoaderAdapter;

// All entry points and batches run exclusively on the editor game thread.
class FForgeLandscape
{
    struct FPlan
    {
        TWeakObjectPtr<UWorld> World;
        TWeakObjectPtr<ALandscape> Actor;
        TSharedPtr<FJsonObject> Request;
        FString Fingerprint;
        FString AdoptionId;
        FString SessionExpectedAfter;
        FTransform Transform = FTransform::Identity;
        FGuid Layer;
        FIntRect Bounds, EditBounds;
        TArray<uint16> Before, After;
        bool bApplyAllowed = true;
        FString ApplyBlockReason;
        FString TargetMapPackage;
        FString TargetMapFilename;
        FString TargetExternalActorsRoot;
        FString TargetExternalObjectsRoot;
        FString ExistingWorldAuthorizationId;
        FString ExistingWorldAuthorizationSessionId;
        FString ExistingWorldAuthorizationProjectFile;
        FString ExistingWorldAuthorizationPackage;
        FString ExistingWorldPackageFingerprint;
        TSet<FString> ExistingWorldAuthorizationActions;
        int64 ExistingWorldAuthorizationExpiresAtUnix = 0;
        bool bHasExistingWorldAuthorization = false;
        double Expires = 0;
    };
    struct FJob
    {
        FPlan Plan;
        FString Id, State = TEXT("running"), Error, Backup, ValidatedAfterHash;
        int32 NextRow = 0;
        double NextTime = 0, MaxStageMs = 0;
        bool bHeightReadbackValidated = false;
        bool bSessionResultLogged = false;
        FString SessionRecoveryManifest;
    };
    struct FLoader
    {
        TWeakObjectPtr<UWorld> World;
        TWeakObjectPtr<ALandscape> Actor;
        TWeakObjectPtr<UWorldPartitionEditorLoaderAdapter> Adapter;
        FGuid LandscapeGuid;
        FIntRect Bounds;
        FBox WorldBounds = FBox(ForceInit);
        FString State = TEXT("loading"), Error;
        double Deadline = 0;
        bool bTargetLoaded = true;
    };
    TMap<FString, FPlan> Previews;
    TMap<FString, FJob> Jobs;
    TMap<FString, FLoader> Loaders;
    TMap<FString, FGuid> AuthorizedExistingWorldLandscapes;
    TWeakObjectPtr<UWorld> LastWorld;
    bool bWorldTransitionInProgress = false;
    void FinishEditSessionJob(FJob& Job);
public:
    bool PrepareForWorldTransition(UWorld* OutgoingWorld, FString& OutError);
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Tick();
    void Reset();
};
