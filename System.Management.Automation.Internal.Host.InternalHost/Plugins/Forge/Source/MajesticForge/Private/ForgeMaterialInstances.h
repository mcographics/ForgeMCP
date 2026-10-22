// SPDX-License-Identifier: MIT
#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

class UMaterialInstanceConstant;
class UMaterialInterface;

// Native material-instance operations are typed, session-scoped and game-thread only.
class FForgeMaterialInstances
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Request;
        TWeakObjectPtr<UMaterialInterface> Target;
        TWeakObjectPtr<UMaterialInterface> Parent;
        FString Fingerprint;
        bool bCreate = false;
        bool bSave = false;
        bool bSaveExisting = false;
        FString DiskFingerprint;
        FString BackupPath;
        double Expires = 0;
    };

    struct FTrackedInstance
    {
        TWeakObjectPtr<UMaterialInstanceConstant> Instance;
        bool bCreated = false;
        FString Fingerprint;
    };

    TMap<FString, FPreview> Previews;
    TMap<FString, FTrackedInstance> TrackedInstances;

public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);

    void Reset() { Previews.Empty(); TrackedInstances.Empty(); }
};
