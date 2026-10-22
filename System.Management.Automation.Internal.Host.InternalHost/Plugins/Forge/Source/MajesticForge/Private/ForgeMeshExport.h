#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

class UStaticMesh;

// Export only reviewed loaded static meshes into private generated staging.
class FForgeMeshExport
{
    struct FPreview { FString Path, Snapshot, Format; TWeakObjectPtr<UStaticMesh> Target; double Expires = 0; };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject>& Data, FString& Code, FString& Message);
    void Reset() { Previews.Empty(); }
};
