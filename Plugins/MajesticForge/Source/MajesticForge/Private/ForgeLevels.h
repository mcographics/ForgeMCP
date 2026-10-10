#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class FForgeLevels
{
    struct FPreview { FString Path; FString Fingerprint; double Expires; };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Reset() { Previews.Empty(); }
};
