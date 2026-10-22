#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"
class UBlueprint;
namespace ForgeWidgets
{
TSharedRef<FJsonObject> Inspect(UBlueprint* Blueprint);
bool Snapshot(UBlueprint* Blueprint, TSharedRef<FJsonObject> State);
bool Restore(UBlueprint* Blueprint, TSharedRef<FJsonObject> State);
bool ValidateHide(UBlueprint* Blueprint, const FString& Name, FString& Error);
bool HideText(UBlueprint* Blueprint, const FString& Name);
}
