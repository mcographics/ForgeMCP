#include "ForgeGameplayAbilitySetupComponent.h"

#include "AbilitySystemComponent.h"
#include "AttributeSet.h"
#include "GameplayAbilitySpec.h"
#include "GameplayEffect.h"
#include "GameFramework/Actor.h"
#include "Logging/LogMacros.h"
#include "UObject/UObjectGlobals.h"

UForgeGameplayAbilitySetupComponent::UForgeGameplayAbilitySetupComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
}

void UForgeGameplayAbilitySetupComponent::ApplyReplicationMode(UAbilitySystemComponent* AbilitySystem) const
{
    if (!bConfigureReplicationMode || !AbilitySystem)
    {
        return;
    }

    switch (ReplicationMode)
    {
    case EForgeGameplayEffectReplicationMode::Minimal:
        AbilitySystem->SetReplicationMode(EGameplayEffectReplicationMode::Minimal);
        break;
    case EForgeGameplayEffectReplicationMode::Mixed:
        AbilitySystem->SetReplicationMode(EGameplayEffectReplicationMode::Mixed);
        break;
    case EForgeGameplayEffectReplicationMode::Full:
        AbilitySystem->SetReplicationMode(EGameplayEffectReplicationMode::Full);
        break;
    }
}

void UForgeGameplayAbilitySetupComponent::OnRegister()
{
    Super::OnRegister();
    if (!bConfigureReplicationMode || !GetOwner())
    {
        return;
    }

    TArray<UAbilitySystemComponent*> AbilitySystemComponents;
    GetOwner()->GetComponents<UAbilitySystemComponent>(AbilitySystemComponents);
    for (UAbilitySystemComponent* Candidate : AbilitySystemComponents)
    {
        if (Candidate && Candidate->GetFName() == AbilitySystemComponentName)
        {
            ApplyReplicationMode(Candidate);
            return;
        }
    }
}

void UForgeGameplayAbilitySetupComponent::BeginPlay()
{
    Super::BeginPlay();
    if (GetOwner() && GetOwner()->HasAuthority())
    {
        ApplyStartupConfiguration();
    }
}

bool UForgeGameplayAbilitySetupComponent::ApplyStartupConfiguration()
{
    if (!IsInGameThread() || bStartupConfigurationApplied)
    {
        return bStartupConfigurationApplied;
    }

    AActor* Owner = GetOwner();
    if (!Owner || !Owner->HasAuthority())
    {
        return false;
    }

    TArray<UAbilitySystemComponent*> AbilitySystemComponents;
    Owner->GetComponents<UAbilitySystemComponent>(AbilitySystemComponents);
    UAbilitySystemComponent* AbilitySystem = nullptr;
    for (UAbilitySystemComponent* Candidate : AbilitySystemComponents)
    {
        if (Candidate && Candidate->GetFName() == AbilitySystemComponentName)
        {
            AbilitySystem = Candidate;
            break;
        }
    }
    if (!AbilitySystem)
    {
        UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup could not find ASC '%s' on '%s'."),
            *AbilitySystemComponentName.ToString(), *Owner->GetPathName());
        return false;
    }

    ApplyReplicationMode(AbilitySystem);

    if (bInitializeOwnerAsAvatar)
    {
        AbilitySystem->InitAbilityActorInfo(Owner, Owner);
    }
    else if (!AbilitySystem->GetOwnerActor() || !AbilitySystem->GetAvatarActor())
    {
        UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup requires initialized ASC actor info when owner initialization is disabled."));
        return false;
    }

    for (const TSubclassOf<UAttributeSet>& AttributeSetClass : AttributeSets)
    {
        if (!AttributeSetClass || !AttributeSetClass->IsChildOf(UAttributeSet::StaticClass()))
        {
            UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup contains an invalid AttributeSet class."));
            return false;
        }
        if (!AbilitySystem->GetAttributeSet(AttributeSetClass))
        {
            UAttributeSet* AttributeSet = NewObject<UAttributeSet>(Owner, AttributeSetClass);
            if (!AttributeSet)
            {
                return false;
            }
            AbilitySystem->AddSpawnedAttribute(AttributeSet);
        }
    }

    for (const FForgeGASAbilityGrant& Grant : StartupAbilities)
    {
        if (!Grant.AbilityClass || Grant.Level < 1 || Grant.Level > 100 || Grant.InputId < INDEX_NONE || Grant.InputId > 255)
        {
            UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup contains an invalid ability grant."));
            return false;
        }
        if (!AbilitySystem->FindAbilitySpecFromClass(Grant.AbilityClass))
        {
            const FGameplayAbilitySpec Spec(Grant.AbilityClass, Grant.Level, Grant.InputId, this);
            if (!AbilitySystem->GiveAbility(Spec).IsValid())
            {
                UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup could not grant an ability on the authoritative actor."));
                return false;
            }
        }
    }

    for (const FForgeGASStartupEffect& StartupEffect : StartupEffects)
    {
        if (!StartupEffect.EffectClass || !FMath::IsFinite(StartupEffect.Level) ||
            StartupEffect.Level <= 0.0f || StartupEffect.Level > 100.0f)
        {
            UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup contains an invalid startup GameplayEffect."));
            return false;
        }
        if (AppliedStartupEffects.Contains(StartupEffect.EffectClass))
        {
            continue;
        }

        FGameplayEffectContextHandle Context = AbilitySystem->MakeEffectContext();
        Context.AddSourceObject(this);
        const FGameplayEffectSpecHandle Spec = AbilitySystem->MakeOutgoingSpec(
            StartupEffect.EffectClass, StartupEffect.Level, Context);
        if (!Spec.IsValid())
        {
            UE_LOG(LogTemp, Warning, TEXT("ForgeMCP GAS setup could not create a startup GameplayEffect spec."));
            return false;
        }
        AbilitySystem->ApplyGameplayEffectSpecToSelf(*Spec.Data.Get());
        AppliedStartupEffects.Add(StartupEffect.EffectClass);
    }

    bStartupConfigurationApplied = true;
    return true;
}
