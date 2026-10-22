#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Bounded read-only inspection of project DataTable assets and row structs.
class FForgeDataTables
{
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
};
