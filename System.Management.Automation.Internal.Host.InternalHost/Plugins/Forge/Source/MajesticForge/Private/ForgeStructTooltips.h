#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Reviewed, one-use edits to User Defined Struct member tooltips.
class FForgeStructTooltips
{
    struct FPreview
    {
        FString StructPath;
        FString SchemaFingerprint;
        TMap<FString, FString> Tooltips;
        double Expires = 0;
    };

    TMap<FString, FPreview> Previews;

public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { Previews.Empty(); }
};
