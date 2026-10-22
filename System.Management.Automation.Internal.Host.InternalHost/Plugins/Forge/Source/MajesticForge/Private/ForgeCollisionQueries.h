#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Bounded, read-only editor-world collision queries. The caller dispatches this
// handler from the authenticated editor ticker on the game thread.
class FForgeCollisionQueries
{
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message) const;
};
