#pragma once
#include "UObject/Class.h"

namespace ForgeReadoutFunctions
{
inline bool Allowed(UFunction* Function)
{
    if (!Function || !Function->HasAnyFunctionFlags(FUNC_BlueprintPure)) return false;
    const FString Owner = Function->GetOuterUClass()->GetPathName();
    const FString Name = Function->GetName();
    return (Owner == TEXT("/Script/Engine.ActorComponent") && Name == TEXT("GetOwner")) ||
        (Owner == TEXT("/Script/Engine.KismetSystemLibrary") && Name == TEXT("GetObjectName")) ||
        (Owner == TEXT("/Script/Engine.GameplayStatics") &&
            (Name == TEXT("GetPlayerController") || Name == TEXT("GetPlayerPawn") || Name == TEXT("GetPlayerCameraManager"))) ||
        (Owner == TEXT("/Script/Engine.PlayerCameraManager") && Name == TEXT("GetCameraLocation")) ||
        (Owner == TEXT("/Script/Engine.KismetTextLibrary") &&
            (Name == TEXT("Conv_DoubleToText") || Name == TEXT("Conv_TextToString")));
}
}
