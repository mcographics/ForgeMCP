#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Session-local previews are lost on bridge restart; no arbitrary execution endpoint.
class FForgeBlueprints
{
    struct FPreview { TSharedPtr<FJsonObject> Recipe; FString World; double Expires; };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { Previews.Empty(); }
};
