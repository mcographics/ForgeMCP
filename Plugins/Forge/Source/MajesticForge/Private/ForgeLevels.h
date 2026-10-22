#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
#include "UObject/WeakObjectPtr.h"

class ULevel;
class UPackage;
class UWorld;
class FForgeLandscape;

class FForgeLevels
{
    struct FPreview { FString Path; FString Fingerprint; double Expires; };
public:
    struct FCurrentPackage
    {
        TWeakObjectPtr<UPackage> Package;
        FString PackageName;
        FString Filename;
        FString BeforeFingerprint;
        int64 BeforeBytes = 0;
        bool bFileExisted = false;
        bool bWillSave = false;
        bool bWillDelete = false;
    };
    struct FCurrentSavePreview
    {
        TWeakObjectPtr<UWorld> World;
        TWeakObjectPtr<ULevel> Level;
        FString WorldPath;
        FString LevelPath;
        FString Fingerprint;
        TArray<FCurrentPackage> Packages;
        double Expires = 0;
    };
private:
    struct FEmptyOpenWorldPreview
    {
        TWeakObjectPtr<UWorld> SourceWorld;
        FString SourceWorldPath;
        FString SourceFingerprint;
        FString MapPath;
        double Expires = 0;
    };
    TMap<FString, FPreview> Previews;
    TMap<FString, FCurrentSavePreview> CurrentPreviews;
    TMap<FString, FEmptyOpenWorldPreview> EmptyOpenWorldPreviews;
public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message, FForgeLandscape* LandscapeAutomation = nullptr);
    void Reset() { Previews.Empty(); CurrentPreviews.Empty(); EmptyOpenWorldPreviews.Empty(); }
};
