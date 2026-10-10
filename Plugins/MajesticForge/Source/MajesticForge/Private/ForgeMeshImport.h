#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// New static-mesh assets only, using reviewed project-local staged FBX artifacts.
class FForgeMeshImport
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Recipe;
        FString World;
        double Expires;
    };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Reset() { Previews.Empty(); }
};
