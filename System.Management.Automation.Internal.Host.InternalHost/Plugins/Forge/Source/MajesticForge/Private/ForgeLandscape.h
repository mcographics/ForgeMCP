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
        FTransform Transform = FTransform::Identity;
        FGuid Layer;
        FIntRect Bounds, EditBounds;
        TArray<uint16> Before, After;
        double Expires = 0;
    };
    struct FJob
    {
        FPlan Plan;
        FString Id, State = TEXT("running"), Error, Backup, ValidatedAfterHash;
        int32 NextRow = 0;
        double NextTime = 0, MaxStageMs = 0;
        double ExpectedCollisionWorldZ = 0, ActualCollisionWorldZ = 0, CollisionValidationStarted = 0, CollisionValidationMs = 0;
        FVector CollisionSampleWorld = FVector::ZeroVector;
        int32 CollisionValidationRetries = 0;
        bool bAwaitingCollisionValidation = false, bHeightReadbackValidated = false, bEditorCollisionHeightValidated = false;
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
    TWeakObjectPtr<UWorld> LastWorld;
    bool bWorldTransitionInProgress = false;
public:
    bool PrepareForWorldTransition(UWorld* OutgoingWorld, FString& OutError);
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Tick();
    void Reset();
};
