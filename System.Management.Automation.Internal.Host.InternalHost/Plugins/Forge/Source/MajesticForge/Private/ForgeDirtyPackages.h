#pragma once

#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

namespace ForgeDirtyPackages
{
	/** Read-only inspection of loaded UPackage dirty flags. Must run on the Editor game thread. */
	bool Handle(const TSharedRef<FJsonObject>& Args, const TSharedRef<FJsonObject>& OutData,
		FString& OutErrorCode, FString& OutErrorMessage);
}
