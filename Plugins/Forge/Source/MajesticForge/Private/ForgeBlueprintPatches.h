#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UBlueprint;
class FCompilerResultsLog;
namespace ForgeBlueprintPatches { struct FPlan; bool SafePath(const FString& InPath); }

// Existing K2 graph primitives. The legacy recipe API remains separate. Plans
// retain only targeted before-values and revision checks, never a Blueprint snapshot.
class FForgeBlueprintPatches
{
    TMap<FString, TSharedPtr<ForgeBlueprintPatches::FPlan>> Plans;
#if WITH_DEV_AUTOMATION_TESTS
    TFunction<bool(UBlueprint*, FCompilerResultsLog&)> TestCompiler;
#endif

public:
    bool Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
        TSharedRef<FJsonObject> Data, FString& Code, FString& Message);
    void Reset() { Plans.Empty(); }
#if WITH_DEV_AUTOMATION_TESTS
    void SetCompilerForTesting(TFunction<bool(UBlueprint*, FCompilerResultsLog&)> InCompiler)
    { TestCompiler = MoveTemp(InCompiler); }
#endif
};
