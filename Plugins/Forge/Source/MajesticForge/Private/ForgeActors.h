#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

class AActor;
class UActorComponent;
class UWorld;

class FForgeActors
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Recipe;
        FString Fingerprint;
        double Expires;
    };
    struct FPropertyEditPreview
    {
        TWeakObjectPtr<AActor> Target;
        TWeakObjectPtr<UWorld> World;
        FString ActorPath;
        FString ClassPath;
        FString PropertyName;
        FString BeforeValue;
        FString ProposedValue;
        double Expires = 0;
    };
    struct FComponentPropertyEditPreview
    {
        TWeakObjectPtr<UActorComponent> Target;
        TWeakObjectPtr<UWorld> World;
        FString ComponentPath;
        FString OwnerActorPath;
        FString ClassPath;
        FString PropertyName;
        FString BeforeValue;
        FString ProposedValue;
        double Expires = 0;
    };
    struct FDeletePreview
    {
        TWeakObjectPtr<AActor> Actor;
        TWeakObjectPtr<UWorld> World;
        FString ActorPath;
        FString ClassPath;
        FString WorldPath;
        FString Fingerprint;
        double Expires = 0;
    };
    TMap<FString, FPreview> Previews;
    TMap<FString, FPropertyEditPreview> PropertyEditPreviews;
    TMap<FString, FComponentPropertyEditPreview> ComponentPropertyEditPreviews;
    TMap<FString, FDeletePreview> DeletePreviews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { Previews.Empty(); PropertyEditPreviews.Empty(); ComponentPropertyEditPreviews.Empty(); DeletePreviews.Empty(); }
};
