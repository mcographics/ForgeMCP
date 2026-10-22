#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

// Bounded registry queries and reviewed, typed asset property operations.
class FForgeAssets
{
    struct FDataAssetCreatePreview
    {
        TWeakObjectPtr<UClass> AssetClass;
        FString ClassPath;
        FString PackagePath;
        FString AssetName;
        TArray<TPair<FString, FString>> Properties;
        bool bSave = false;
        double Expires = 0;
    };
    TMap<FString, FDataAssetCreatePreview> DataAssetCreatePreviews;
    struct FDataAssetEditValue
    {
        FString Name;
        FString Type;
        FString BeforeValue;
        FString ProposedValue;
    };
    struct FDataAssetEditPreview
    {
        TWeakObjectPtr<UObject> Target;
        FString AssetPath;
        FString ClassPath;
        FString PackagePath;
        FString Filename;
        FString DiskFingerprint;
        FString BackupPath;
        TArray<FDataAssetEditValue> Properties;
        bool bSave = false;
        double Expires = 0;
    };
    TMap<FString, FDataAssetEditPreview> DataAssetEditPreviews;
    struct FPropertyEditPreview
    {
        TWeakObjectPtr<UObject> Target;
        FString AssetPath;
        FString ClassPath;
        FString PropertyName;
        FString BeforeValue;
        FString ProposedValue;
        double Expires = 0;
    };
    TMap<FString, FPropertyEditPreview> PropertyEditPreviews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage);
    void Reset() { PropertyEditPreviews.Empty(); DataAssetEditPreviews.Empty(); DataAssetCreatePreviews.Empty(); }
};
