#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

class UBlueprint;
class UEdGraph;
class UEdGraphNode;
class UEdGraphPin;

// Read-only, graph-scoped Blueprint inspection. Cursors are short-lived indexes
// over one revision; NodeGuid and PinId remain the identities returned to callers.
class FForgeBlueprintInspection
{
    struct FNodeCursor
    {
        TWeakObjectPtr<UBlueprint> Blueprint;
        TWeakObjectPtr<UEdGraph> Graph;
        FString AssetPath;
        FString GraphName;
        FString Fingerprint;
        FString Query;
        TArray<TWeakObjectPtr<UEdGraphNode>> Nodes;
        int32 PageSize = 0;
        double Expires = 0;
    };

    struct FPinCursor
    {
        TWeakObjectPtr<UBlueprint> Blueprint;
        TWeakObjectPtr<UEdGraph> Graph;
        TWeakObjectPtr<UEdGraphNode> Node;
        FString AssetPath;
        FString GraphName;
        FString NodeGuid;
        FString Fingerprint;
        // Ephemeral offsets are used only after graph revision and object identity
        // checks. Returned pin identities remain PinId, never these offsets.
        TArray<int32> PinIndexes;
        int32 PageSize = 0;
        double Expires = 0;
    };

    TMap<FString, FNodeCursor> NodeCursors;
    TMap<FString, FPinCursor> PinCursors;

public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { NodeCursors.Empty(); PinCursors.Empty(); }
};
