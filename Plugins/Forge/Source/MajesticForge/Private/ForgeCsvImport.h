#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// Previewed, project-local CSV to User Defined Struct and DataTable creation.
class FForgeCsvImport
{
    struct FPreview
    {
        FString CsvPath;
        FString FileHash;
        FString StructPath;
        FString TablePath;
        FString KeyColumn;
        FString StructSchemaFingerprint;
        bool bStructExisted = false;
        TSharedPtr<FJsonObject> Overrides;
        double Expires = 0;
        int32 RowCount = 0;
    };
    TMap<FString, FPreview> Previews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { Previews.Empty(); }
};
