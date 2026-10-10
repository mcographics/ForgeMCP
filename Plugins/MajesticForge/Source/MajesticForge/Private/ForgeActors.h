#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class FForgeActors
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Recipe;
        FString Fingerprint;
        double Expires;
    };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { Previews.Empty(); }
};
