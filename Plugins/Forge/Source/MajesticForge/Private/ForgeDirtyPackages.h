#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

class UWorld;

namespace ForgeDirtyPackages
{
	struct FPackagePolicyFacts
	{
		FString PackagePath;
		FString PackageCategory;
		uint32 PackageFlags = 0;
		int32 AssociatedActorCount = 0;
		int32 ExternalActorCount = 0;
		bool bDirty = false;
		bool bClassificationComplete = false;
		bool bOwnershipScanComplete = false;
		bool bEngineScriptProvenanceVerified = false;
		bool bIsTransientPackage = false;
		bool bCurrentWorldPackage = false;
		bool bAssociatedWithCurrentWorld = false;
		bool bAssociationWithCurrentWorldDetermined = false;
	};

	struct FPackagePolicyDecision
	{
		bool bBlocksApply = true;
		bool bDisposableEngineScriptException = false;
		FString Reason;
	};

	/** Evaluate one dirty row. Unknown or incomplete evidence always blocks. */
	FPackagePolicyDecision EvaluateLandscapeApplyPolicy(
		const FPackagePolicyFacts& Facts, bool bDisposableProject);
	bool IsLandscapeApplyPreflightBlocking(bool bInventoryComplete, int32 BlockingDirtyPackageCount);

	/** Read-only loaded-package scan used by Landscape preview and Apply gates. */
	bool InspectLandscapeApplyPreflight(UWorld* CurrentWorld, bool bDisposableProject,
		const TSharedRef<FJsonObject>& OutPolicy);

	/** Read-only inspection of loaded UPackage dirty flags; game-thread only. */
	bool Handle(const TSharedRef<FJsonObject>& Args, const TSharedRef<FJsonObject>& OutData,
		FString& OutErrorCode, FString& OutErrorMessage);
}
