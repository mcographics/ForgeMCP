#pragma once

#include "CoreMinimal.h"
#include "AbilitySystemComponent.h"
#include "Components/ActorComponent.h"
#include "ForgeGameplayAbilitySetupComponent.generated.h"

class UAbilitySystemComponent;
class UAttributeSet;
class UGameplayAbility;
class UGameplayEffect;

UENUM(BlueprintType)
enum class EForgeGameplayEffectReplicationMode : uint8
{
    Minimal,
    Mixed,
    Full
};

USTRUCT(BlueprintType)
struct MAJESTICFORGERUNTIME_API FForgeGASAbilityGrant
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    TSubclassOf<UGameplayAbility> AbilityClass;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS", meta = (ClampMin = "1", ClampMax = "100"))
    int32 Level = 1;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS", meta = (ClampMin = "-1", ClampMax = "255"))
    int32 InputId = INDEX_NONE;
};

USTRUCT(BlueprintType)
struct MAJESTICFORGERUNTIME_API FForgeGASStartupEffect
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    TSubclassOf<UGameplayEffect> EffectClass;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS", meta = (ClampMin = "0.01", ClampMax = "100.0"))
    float Level = 1.0f;
};

/** Applies an explicit, bounded GAS starting configuration on the authoritative actor. */
UCLASS(ClassGroup = (ForgeMCP), meta = (BlueprintSpawnableComponent))
class MAJESTICFORGERUNTIME_API UForgeGameplayAbilitySetupComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UForgeGameplayAbilitySetupComponent();

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    bool bConfigureReplicationMode = false;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    EForgeGameplayEffectReplicationMode ReplicationMode = EForgeGameplayEffectReplicationMode::Full;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    FName AbilitySystemComponentName = TEXT("AbilitySystemComponent");

    /** Initialize a self-owned actor ASC with this actor as both owner and avatar. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    bool bInitializeOwnerAsAvatar = true;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    TArray<TSubclassOf<UAttributeSet>> AttributeSets;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    TArray<FForgeGASAbilityGrant> StartupAbilities;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "ForgeMCP|GAS")
    TArray<FForgeGASStartupEffect> StartupEffects;

    UPROPERTY(Transient, BlueprintReadOnly, Category = "ForgeMCP|GAS|Runtime")
    bool bStartupConfigurationApplied = false;

    /** May be called by Blueprint after an externally owned ASC has initialized its actor info. */
    UFUNCTION(BlueprintCallable, Category = "ForgeMCP|GAS")
    bool ApplyStartupConfiguration();

protected:
    virtual void OnRegister() override;
    virtual void BeginPlay() override;

private:
    void ApplyReplicationMode(UAbilitySystemComponent* AbilitySystem) const;

    UPROPERTY(Transient)
    TArray<TSubclassOf<UGameplayEffect>> AppliedStartupEffects;
};
