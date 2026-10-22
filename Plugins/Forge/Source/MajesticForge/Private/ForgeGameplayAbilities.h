#pragma once

#include "AbilitySystemComponent.h"
#include "AttributeSet.h"
#include "Components/ActorComponent.h"
#include "Dom/JsonObject.h"
#include "ForgeGameplayAbilitySetupComponent.h"
#include "GameplayEffect.h"
#include "Abilities/GameplayAbility.h"

namespace ForgeGameplayAbilities
{
inline FString Text(const TSharedRef<FJsonObject>& Object, const TCHAR* Key, const FString& Default = FString())
{
    FString Value;
    return Object->TryGetStringField(Key, Value) ? Value : Default;
}

inline bool IsSafeClassPath(const FString& Path)
{
    return Path.Len() <= 240 && !Path.Contains(TEXT("..")) &&
        (Path.StartsWith(TEXT("/Script/")) || Path.StartsWith(TEXT("/Game/")));
}

inline UClass* LoadConfiguredClass(const FString& Path, UClass* BaseClass, FString& Error)
{
    if (!IsSafeClassPath(Path))
    {
        Error = TEXT("GAS class paths must be bounded /Script or /Game class references.");
        return nullptr;
    }
    UClass* Class = StaticLoadClass(BaseClass, nullptr, *Path);
    if (!Class || !Class->IsChildOf(BaseClass) || Class->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated))
    {
        Error = TEXT("GAS class reference was not found as a concrete class of the required type.");
        return nullptr;
    }
    return Class;
}

inline bool TryInteger(const TSharedRef<FJsonObject>& Object, const TCHAR* Key, int32 Min, int32 Max, int32& Out)
{
    double Number = 0;
    if (!Object->TryGetNumberField(Key, Number) || !FMath::IsFinite(Number) ||
        FMath::FloorToDouble(Number) != Number || Number < Min || Number > Max)
    {
        return false;
    }
    Out = static_cast<int32>(Number);
    return true;
}

inline bool ValidateGASSetup(const TSharedRef<FJsonObject>& Setup, FString& Error)
{
    Error.Reset();
    const TSet<FString> Fields{
        TEXT("ability_system_component"), TEXT("replication_mode"),
        TEXT("initialize_owner_as_avatar"),
        TEXT("attribute_sets"), TEXT("startup_abilities"), TEXT("startup_effects")
    };
    for (const auto& Pair : Setup->Values)
    {
        if (!Fields.Contains(Pair.Key))
        {
            Error = TEXT("GAS setup contains an unsupported field.");
            return false;
        }
    }

    FString AbilitySystemName = TEXT("AbilitySystemComponent");
    if (Setup->HasField(TEXT("ability_system_component")) &&
        !Setup->TryGetStringField(TEXT("ability_system_component"), AbilitySystemName))
    {
        Error = TEXT("ability_system_component must be a component identifier.");
        return false;
    }
    if (AbilitySystemName.IsEmpty() || AbilitySystemName.Len() > 64 ||
        (!FChar::IsAlpha(AbilitySystemName[0]) && AbilitySystemName[0] != '_'))
    {
        Error = TEXT("ability_system_component must be a component identifier.");
        return false;
    }
    for (TCHAR Character : AbilitySystemName)
    {
        if (!FChar::IsAlnum(Character) && Character != '_')
        {
            Error = TEXT("ability_system_component must be a component identifier.");
            return false;
        }
    }
    const TSharedPtr<FJsonValue>* ModeValue = Setup->Values.Find(TEXT("replication_mode"));
    if (ModeValue && ModeValue->IsValid() && (*ModeValue)->Type != EJson::Null)
    {
        FString ReplicationMode;
        if ((*ModeValue)->Type != EJson::String ||
            !Setup->TryGetStringField(TEXT("replication_mode"), ReplicationMode) ||
            (ReplicationMode != TEXT("minimal") && ReplicationMode != TEXT("mixed") &&
                ReplicationMode != TEXT("full")))
        {
            Error = TEXT("GAS setup replication_mode must be minimal, mixed, or full.");
            return false;
        }
    }
    if (Setup->HasField(TEXT("initialize_owner_as_avatar")))
    {
        bool InitializeOwnerAsAvatar = false;
        if (!Setup->TryGetBoolField(TEXT("initialize_owner_as_avatar"), InitializeOwnerAsAvatar))
        {
            Error = TEXT("initialize_owner_as_avatar must be a boolean.");
            return false;
        }
    }

    const TArray<TSharedPtr<FJsonValue>>* AttributeSets = nullptr;
    if (Setup->TryGetArrayField(TEXT("attribute_sets"), AttributeSets))
    {
        if (AttributeSets->Num() > 16)
        {
            Error = TEXT("GAS setup supports at most 16 AttributeSet classes.");
            return false;
        }
        TSet<FString> Paths;
        for (const TSharedPtr<FJsonValue>& Value : *AttributeSets)
        {
            if (!Value.IsValid() || Value->Type != EJson::String)
            {
                Error = TEXT("attribute_sets must contain class-path strings.");
                return false;
            }
            const FString Path = Value->AsString();
            if (Paths.Contains(Path.ToLower()) ||
                !LoadConfiguredClass(Path, UAttributeSet::StaticClass(), Error))
            {
                if (Error.IsEmpty()) Error = TEXT("GAS AttributeSet classes must be unique.");
                return false;
            }
            Paths.Add(Path.ToLower());
        }
    }

    const TArray<TSharedPtr<FJsonValue>>* Abilities = nullptr;
    if (Setup->TryGetArrayField(TEXT("startup_abilities"), Abilities))
    {
        if (Abilities->Num() > 32)
        {
            Error = TEXT("GAS setup supports at most 32 starting abilities.");
            return false;
        }
        TSet<FString> Paths;
        for (const TSharedPtr<FJsonValue>& Value : *Abilities)
        {
            if (!Value.IsValid() || Value->Type != EJson::Object)
            {
                Error = TEXT("Each startup ability must be an object.");
                return false;
            }
            const TSharedRef<FJsonObject> Ability = Value->AsObject().ToSharedRef();
            for (const auto& Pair : Ability->Values)
            {
                if (Pair.Key != TEXT("class_path") && Pair.Key != TEXT("level") && Pair.Key != TEXT("input_id"))
                {
                    Error = TEXT("Startup ability contains an unsupported field.");
                    return false;
                }
            }
            const FString Path = Text(Ability, TEXT("class_path"));
            int32 Level = 1;
            int32 InputId = INDEX_NONE;
            if (Paths.Contains(Path.ToLower()) ||
                !LoadConfiguredClass(Path, UGameplayAbility::StaticClass(), Error) ||
                (Ability->HasField(TEXT("level")) && !TryInteger(Ability, TEXT("level"), 1, 100, Level)) ||
                (Ability->HasField(TEXT("input_id")) && !TryInteger(Ability, TEXT("input_id"), INDEX_NONE, 255, InputId)))
            {
                if (Error.IsEmpty()) Error = TEXT("Startup ability path, level, or input_id is invalid.");
                return false;
            }
            Paths.Add(Path.ToLower());
        }
    }

    const TArray<TSharedPtr<FJsonValue>>* Effects = nullptr;
    if (Setup->TryGetArrayField(TEXT("startup_effects"), Effects))
    {
        if (Effects->Num() > 32)
        {
            Error = TEXT("GAS setup supports at most 32 starting GameplayEffects.");
            return false;
        }
        TSet<FString> Paths;
        for (const TSharedPtr<FJsonValue>& Value : *Effects)
        {
            if (!Value.IsValid() || Value->Type != EJson::Object)
            {
                Error = TEXT("Each startup effect must be an object.");
                return false;
            }
            const TSharedRef<FJsonObject> Effect = Value->AsObject().ToSharedRef();
            for (const auto& Pair : Effect->Values)
            {
                if (Pair.Key != TEXT("class_path") && Pair.Key != TEXT("level"))
                {
                    Error = TEXT("Startup effect contains an unsupported field.");
                    return false;
                }
            }
            const FString Path = Text(Effect, TEXT("class_path"));
            double Level = 1.0;
            if (Paths.Contains(Path.ToLower()) ||
                !LoadConfiguredClass(Path, UGameplayEffect::StaticClass(), Error) ||
                (Effect->HasField(TEXT("level")) &&
                    (!Effect->TryGetNumberField(TEXT("level"), Level) || !FMath::IsFinite(Level) || Level <= 0 || Level > 100)))
            {
                if (Error.IsEmpty()) Error = TEXT("Startup GameplayEffect path or level is invalid.");
                return false;
            }
            Paths.Add(Path.ToLower());
        }
    }
    return true;
}

inline bool ValidateComponentDefinition(
    const TSharedRef<FJsonObject>& Definition,
    UClass* ComponentClass,
    FString& OutReplicationMode,
    FString& Error)
{
    Error.Reset();
    if (!ComponentClass || !ComponentClass->IsChildOf(UActorComponent::StaticClass()) ||
        ComponentClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated))
    {
        Error = TEXT("Component class must be a concrete native ActorComponent class.");
        return false;
    }
    for (const auto& Pair : Definition->Values)
    {
        if (Pair.Key != TEXT("name") && Pair.Key != TEXT("class_path") &&
            Pair.Key != TEXT("replication_mode") && Pair.Key != TEXT("gas_setup"))
        {
            Error = TEXT("Component definition has an unsupported field.");
            return false;
        }
    }

    const TSharedPtr<FJsonValue>* ModeValue = Definition->Values.Find(TEXT("replication_mode"));
    if (ModeValue && ModeValue->IsValid() && (*ModeValue)->Type != EJson::Null)
    {
        if ((*ModeValue)->Type != EJson::String ||
            !Definition->TryGetStringField(TEXT("replication_mode"), OutReplicationMode))
        {
            Error = TEXT("replication_mode must be minimal, mixed, full, or null.");
            return false;
        }
    }

    const bool bAbilitySystem = ComponentClass &&
        ComponentClass->IsChildOf(UAbilitySystemComponent::StaticClass());
    const bool bGASSetupComponent = ComponentClass &&
        ComponentClass->IsChildOf(UForgeGameplayAbilitySetupComponent::StaticClass());
    if (bAbilitySystem && OutReplicationMode.IsEmpty())
    {
        Error = TEXT("AbilitySystemComponent requires an explicit replication_mode.");
        return false;
    }
    if (!bAbilitySystem && !OutReplicationMode.IsEmpty())
    {
        Error = TEXT("replication_mode is supported only on AbilitySystemComponent.");
        return false;
    }
    if (!OutReplicationMode.IsEmpty() && OutReplicationMode != TEXT("minimal") &&
        OutReplicationMode != TEXT("mixed") && OutReplicationMode != TEXT("full"))
    {
        Error = TEXT("Use replication_mode minimal, mixed, or full.");
        return false;
    }

    const TSharedPtr<FJsonValue>* SetupValue = Definition->Values.Find(TEXT("gas_setup"));
    const bool bHasSetup = SetupValue && SetupValue->IsValid() && (*SetupValue)->Type != EJson::Null;
    if (bGASSetupComponent != bHasSetup)
    {
        Error = TEXT("ForgeGameplayAbilitySetupComponent requires gas_setup settings, and those settings are not valid on other components.");
        return false;
    }
    if (bHasSetup)
    {
        if ((*SetupValue)->Type != EJson::Object || !ValidateGASSetup((*SetupValue)->AsObject().ToSharedRef(), Error))
        {
            if (Error.IsEmpty()) Error = TEXT("gas_setup must be an object.");
            return false;
        }
    }
    return true;
}

inline bool ConfigureComponent(
    UActorComponent* Component,
    const TSharedRef<FJsonObject>& Definition,
    FString& Error)
{
    Error.Reset();
    if (!Component)
    {
        Error = TEXT("Blueprint component template could not be created.");
        return false;
    }
    if (UAbilitySystemComponent* AbilitySystem = Cast<UAbilitySystemComponent>(Component))
    {
        AbilitySystem->SetIsReplicated(true);
    }

    UForgeGameplayAbilitySetupComponent* GASSetup = Cast<UForgeGameplayAbilitySetupComponent>(Component);
    if (!GASSetup)
    {
        const TSharedPtr<FJsonValue>* SetupValue = Definition->Values.Find(TEXT("gas_setup"));
        if (SetupValue && SetupValue->IsValid() && (*SetupValue)->Type != EJson::Null)
        {
            Error = TEXT("GAS startup settings require a ForgeGameplayAbilitySetupComponent.");
            return false;
        }
        return true;
    }

    const TSharedPtr<FJsonObject>* SetupValue = nullptr;
    if (!Definition->TryGetObjectField(TEXT("gas_setup"), SetupValue) || !SetupValue || !SetupValue->IsValid())
    {
        Error = TEXT("GAS startup settings were not provided.");
        return false;
    }
    const TSharedRef<FJsonObject> Setup = (*SetupValue).ToSharedRef();
    GASSetup->AbilitySystemComponentName = FName(*Text(Setup, TEXT("ability_system_component"), TEXT("AbilitySystemComponent")));
    FString ConfiguredReplicationMode;
    GASSetup->bConfigureReplicationMode = Setup->TryGetStringField(TEXT("replication_mode"), ConfiguredReplicationMode);
    GASSetup->ReplicationMode = EForgeGameplayEffectReplicationMode::Full;
    if (ConfiguredReplicationMode == TEXT("minimal"))
        GASSetup->ReplicationMode = EForgeGameplayEffectReplicationMode::Minimal;
    else if (ConfiguredReplicationMode == TEXT("mixed"))
        GASSetup->ReplicationMode = EForgeGameplayEffectReplicationMode::Mixed;
    GASSetup->bInitializeOwnerAsAvatar = true;
    Setup->TryGetBoolField(TEXT("initialize_owner_as_avatar"), GASSetup->bInitializeOwnerAsAvatar);
    GASSetup->AttributeSets.Reset();
    GASSetup->StartupAbilities.Reset();
    GASSetup->StartupEffects.Reset();

    const TArray<TSharedPtr<FJsonValue>>* AttributeSets = nullptr;
    if (Setup->TryGetArrayField(TEXT("attribute_sets"), AttributeSets))
    {
        for (const TSharedPtr<FJsonValue>& Value : *AttributeSets)
        {
            UClass* Class = LoadConfiguredClass(Value->AsString(), UAttributeSet::StaticClass(), Error);
            if (!Class) return false;
            GASSetup->AttributeSets.Add(Class);
        }
    }
    const TArray<TSharedPtr<FJsonValue>>* Abilities = nullptr;
    if (Setup->TryGetArrayField(TEXT("startup_abilities"), Abilities))
    {
        for (const TSharedPtr<FJsonValue>& Value : *Abilities)
        {
            const TSharedRef<FJsonObject> Ability = Value->AsObject().ToSharedRef();
            FForgeGASAbilityGrant Grant;
            Grant.AbilityClass = LoadConfiguredClass(Text(Ability, TEXT("class_path")), UGameplayAbility::StaticClass(), Error);
            if (!Grant.AbilityClass) return false;
            TryInteger(Ability, TEXT("level"), 1, 100, Grant.Level);
            TryInteger(Ability, TEXT("input_id"), INDEX_NONE, 255, Grant.InputId);
            GASSetup->StartupAbilities.Add(Grant);
        }
    }
    const TArray<TSharedPtr<FJsonValue>>* Effects = nullptr;
    if (Setup->TryGetArrayField(TEXT("startup_effects"), Effects))
    {
        for (const TSharedPtr<FJsonValue>& Value : *Effects)
        {
            const TSharedRef<FJsonObject> Effect = Value->AsObject().ToSharedRef();
            FForgeGASStartupEffect Grant;
            Grant.EffectClass = LoadConfiguredClass(Text(Effect, TEXT("class_path")), UGameplayEffect::StaticClass(), Error);
            double Level = 1.0;
            if (!Grant.EffectClass) return false;
            Effect->TryGetNumberField(TEXT("level"), Level);
            Grant.Level = static_cast<float>(Level);
            GASSetup->StartupEffects.Add(Grant);
        }
    }
    return true;
}

inline FString ReplicationModeName(EGameplayEffectReplicationMode Mode)
{
    switch (Mode)
    {
    case EGameplayEffectReplicationMode::Minimal: return TEXT("minimal");
    case EGameplayEffectReplicationMode::Mixed: return TEXT("mixed");
    case EGameplayEffectReplicationMode::Full: return TEXT("full");
    default: return TEXT("unknown");
    }
}

inline FString ReplicationModeName(EForgeGameplayEffectReplicationMode Mode)
{
    switch (Mode)
    {
    case EForgeGameplayEffectReplicationMode::Minimal: return TEXT("minimal");
    case EForgeGameplayEffectReplicationMode::Mixed: return TEXT("mixed");
    case EForgeGameplayEffectReplicationMode::Full: return TEXT("full");
    default: return TEXT("unknown");
    }
}
}
