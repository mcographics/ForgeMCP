#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Registry metadata only: no asset loading, saving, or arbitrary property execution.
class FForgeAssets
{
public:
    static bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
};
