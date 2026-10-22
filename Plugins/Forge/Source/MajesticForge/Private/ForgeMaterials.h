// SPDX-License-Identifier: MIT
#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "MaterialShared.h"
#include "UObject/WeakObjectPtr.h"

class UMaterial;

// Editor-only, authenticated dispatch. No graph deletion or replacement.
class FForgeMaterials
{
    struct FPreview
    {
        TSharedPtr<FJsonObject> Recipe;
        FString Fingerprint;
        bool bCreate;
        double Expires;
    };
    TMap<FString, FPreview> Previews;
    // Saving is limited to fresh assets created by this bridge session.
    TMap<FString, TWeakObjectPtr<UMaterial>> Created;
    TMap<FString, FString> Validated;
    // Positive engine-result evidence is pinned to the exact map, never a stale hash.
    TMap<FString, TRefCountPtr<FMaterialShaderMap>> CompletionProof;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Reset() { Previews.Empty(); Created.Empty(); Validated.Empty(); CompletionProof.Empty(); }
};
