#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "ForgeWebBridge.generated.h"

UCLASS()
class UForgeWebBridge final : public UObject
{
	GENERATED_BODY()

public:
	using FStateProvider = TFunction<FString()>;
	using FActionHandler = TFunction<void(const FString&, const FString&)>;

	void Configure(FStateProvider InStateProvider, FActionHandler InActionHandler)
	{
		StateProvider = MoveTemp(InStateProvider);
		ActionHandler = MoveTemp(InActionHandler);
	}

	UFUNCTION()
	FString GetState() const
	{
		return StateProvider ? StateProvider() : TEXT("{}");
	}

	UFUNCTION()
	void Dispatch(const FString& Action, const FString& Payload)
	{
		if (ActionHandler) ActionHandler(Action, Payload);
	}

private:
	FStateProvider StateProvider;
	FActionHandler ActionHandler;
};
