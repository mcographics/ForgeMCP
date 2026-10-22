#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

// New static-mesh assets only, using reviewed project-local staged FBX artifacts.
class FForgeMeshImport
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Recipe;
        TWeakObjectPtr<UObject> Target;
        FString World;
        FString AssetPath;
        FString TransferId;
        FString BindingId;
        FString SourceSnapshot;
        FString SourceBaseline;
        FString TargetRevision;
        FString PackageFingerprint;
        bool bReplacement = false;
        double Expires;
    };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Reset() { Previews.Empty(); }
};
