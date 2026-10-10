#include "ForgeActors.h"
#include "Editor.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "MeshDescription.h"
#include "StaticMeshAttributes.h"
#include "Misc/SecureHash.h"
#include "Engine/PointLight.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SpotLight.h"
#include "Camera/CameraActor.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "AbilitySystemComponent.h"
#include "AttributeSet.h"
#include "GameplayAbilitySpec.h"
#include "GameplayEffect.h"
#include "GameplayEffectTypes.h"
#include "GameplayTagContainer.h"
#include "ForgeGameplayAbilities.h"
#include "ForgeGameplayAbilitySetupComponent.h"
#include "ScopedTransaction.h"
#include "Misc/Guid.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;
UClass* SpawnClass(const FString& Name)
{
    if (Name == TEXT("/Script/Engine.StaticMeshActor")) return AStaticMeshActor::StaticClass();
    if (Name == TEXT("/Script/Engine.PointLight")) return APointLight::StaticClass();
    if (Name == TEXT("/Script/Engine.SpotLight")) return ASpotLight::StaticClass();
    if (Name == TEXT("/Script/Engine.DirectionalLight")) return ADirectionalLight::StaticClass();
    if (Name == TEXT("/Script/Engine.CameraActor")) return ACameraActor::StaticClass();
    return nullptr;
}
AActor* Resolve(UWorld* World, const FString& Path)
{
    for (TActorIterator<AActor> It(World); It; ++It)
        if (IsValid(*It) && It->GetPathName() == Path) return *It;
    return nullptr;
}
UStaticMesh* ResolveMesh(const FString& Path)
{
    // Preview never loads caller-selected objects or invokes constructors.
    if (Path.Len() > 240 || !Path.StartsWith(TEXT("/Game/")) || Path.Contains(TEXT(":"))) return nullptr;
    for (TCHAR C : Path) if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || (C >= '0' && C <= '9') || C == '_' || C == '/' || C == '.')) return nullptr;
    UStaticMesh* Mesh = FindObject<UStaticMesh>(nullptr, *Path);
    if (!IsValid(Mesh) || Mesh->GetPathName() != Path) return nullptr;
    if (Mesh->GetStaticMaterials().Num() > 32) return nullptr;
    const FMeshDescription* Description = Mesh->GetMeshDescription(0);
    if (!Description || Description->Vertices().Num() < 3 || Description->Vertices().Num() > 100000 ||
        Description->Triangles().Num() < 1 || Description->Triangles().Num() > 200000) return nullptr;
    return Mesh;
}
JObject MeshState(UStaticMesh* Mesh)
{
    auto State = MakeShared<FJsonObject>();
    State->SetStringField(TEXT("path"), Mesh->GetPathName());
    State->SetStringField(TEXT("instance"), FString::Printf(TEXT("%p"), Mesh));
    State->SetStringField(TEXT("lighting_guid"), Mesh->GetLightingGuid().ToString());
    const FMeshDescription* Description = Mesh->GetMeshDescription(0);
    FStaticMeshConstAttributes Attributes(*Description);
    const auto Positions = Attributes.GetVertexPositions();
    FSHA1 Hash;
    for (FVertexID Id : Description->Vertices().GetElementIDs())
    {
        const int32 Index = Id.GetValue();
        const FVector3f Position = Positions[Id];
        Hash.Update(reinterpret_cast<const uint8*>(&Index), sizeof(Index));
        Hash.Update(reinterpret_cast<const uint8*>(&Position), sizeof(Position));
    }
    for (FTriangleID Id : Description->Triangles().GetElementIDs())
        for (FVertexID Vertex : Description->GetTriangleVertices(Id))
        {
            const int32 Index = Vertex.GetValue();
            Hash.Update(reinterpret_cast<const uint8*>(&Index), sizeof(Index));
        }
    Hash.Final();
    uint8 Digest[20];
    Hash.GetHash(Digest);
    State->SetStringField(TEXT("geometry_fingerprint"), BytesToHex(Digest, sizeof(Digest)));
    State->SetNumberField(TEXT("vertex_count"), Description->Vertices().Num());
    State->SetNumberField(TEXT("triangle_count"), Description->Triangles().Num());
    TArray<TSharedPtr<FJsonValue>> Materials;
    for (const FStaticMaterial& Slot : Mesh->GetStaticMaterials())
    {
        auto Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("slot"), Slot.MaterialSlotName.ToString());
        Item->SetStringField(TEXT("material"), Slot.MaterialInterface ? Slot.MaterialInterface->GetPathName() : TEXT(""));
        Materials.Add(MakeShared<FJsonValueObject>(Item));
    }
    State->SetArrayField(TEXT("materials"), Materials);
    return State;
}
TSharedRef<FJsonObject> Describe(AActor* Actor)
{
    auto Result = MakeShared<FJsonObject>();
    Result->SetStringField(TEXT("path"), Actor->GetPathName());
    Result->SetStringField(TEXT("class_path"), Actor->GetClass()->GetPathName());
    Result->SetStringField(TEXT("label"), Actor->GetActorLabel());
    Result->SetStringField(TEXT("guid"), Actor->GetActorGuid().ToString());
    auto AddVector = [&](const TCHAR* Name, const FVector& Value)
    {
        Result->SetArrayField(Name, {MakeShared<FJsonValueNumber>(Value.X), MakeShared<FJsonValueNumber>(Value.Y), MakeShared<FJsonValueNumber>(Value.Z)});
    };
    AddVector(TEXT("location"), Actor->GetActorLocation());
    const FRotator Rotation = Actor->GetActorRotation();
    AddVector(TEXT("rotation"), FVector(Rotation.Pitch, Rotation.Yaw, Rotation.Roll));
    AddVector(TEXT("scale"), Actor->GetActorScale3D());
    Result->SetBoolField(TEXT("hidden"), Actor->IsHidden());
    if (AStaticMeshActor* MeshActor = Cast<AStaticMeshActor>(Actor))
    {
        UStaticMeshComponent* Component = MeshActor->GetStaticMeshComponent();
        UStaticMesh* Mesh = Component ? Component->GetStaticMesh() : nullptr;
        Result->SetStringField(TEXT("static_mesh"), Mesh ? Mesh->GetPathName() : TEXT(""));
        FVector Origin, Extent;
        Actor->GetActorBounds(false, Origin, Extent);
        AddVector(TEXT("bounds_origin"), Origin);
        AddVector(TEXT("bounds_extent"), Extent);
        TArray<TSharedPtr<FJsonValue>> Materials;
        for (int32 Index = 0; Component && Index < FMath::Min(Component->GetNumMaterials(), 32); ++Index)
        {
            UMaterialInterface* Material = Component->GetMaterial(Index);
            Materials.Add(MakeShared<FJsonValueString>(Material ? Material->GetPathName() : TEXT("")));
        }
        Result->SetArrayField(TEXT("material_assets"), Materials);
        Result->SetBoolField(TEXT("material_assets_truncated"), Component && Component->GetNumMaterials() > 32);
    }
    return Result;
}
bool ReadVector(const JObject& Op, const TCHAR* Field, FVector& Value)
{
    if (!Op->HasField(Field)) return true;
    const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
    if (!Op->TryGetArrayField(Field, Array) || Array->Num() != 3) return false;
    double Values[3];
    for (int32 Index = 0; Index < 3; ++Index)
    {
        if ((*Array)[Index]->Type != EJson::Number || !(*Array)[Index]->TryGetNumber(Values[Index]) ||
            !FMath::IsFinite(Values[Index]) || FMath::Abs(Values[Index]) > 1e8) return false;
    }
    Value = FVector(Values[0], Values[1], Values[2]);
    if (FString(Field) == TEXT("scale") && (FMath::Abs(Value.X) < 1e-8 || FMath::Abs(Value.Y) < 1e-8 || FMath::Abs(Value.Z) < 1e-8)) return false;
    return true;
}
FString Fingerprint(UWorld* World, const TArray<TSharedPtr<FJsonValue>>& Operations)
{
    auto State = MakeShared<FJsonObject>();
    State->SetStringField(TEXT("world"), World->GetPathName());
    State->SetStringField(TEXT("world_instance"), FString::Printf(TEXT("%p"), World));
    State->SetStringField(TEXT("level_instance"), FString::Printf(TEXT("%p"), World->GetCurrentLevel()));
    TArray<TSharedPtr<FJsonValue>> Targets;
    for (const auto& Value : Operations)
    {
        FString Path;
        Value->AsObject()->TryGetStringField(TEXT("actor_path"), Path);
        if (AActor* Actor = Resolve(World, Path))
        {
            auto Item = Describe(Actor);
            Item->SetStringField(TEXT("instance"), FString::Printf(TEXT("%p"), Actor));
            Item->SetStringField(TEXT("parent"), Actor->GetAttachParentActor() ? Actor->GetAttachParentActor()->GetPathName() : TEXT(""));
            Targets.Add(MakeShared<FJsonValueObject>(Item));
        }
        FString MeshPath;
        Value->AsObject()->TryGetStringField(TEXT("mesh_path"), MeshPath);
        if (UStaticMesh* Mesh = ResolveMesh(MeshPath))
            Targets.Add(MakeShared<FJsonValueObject>(MeshState(Mesh)));
    }
    State->SetArrayField(TEXT("targets"), Targets);
    FString Serialized;
    FJsonSerializer::Serialize(State, TJsonWriterFactory<>::Create(&Serialized));
    return Serialized;
}
}

bool FForgeActors::Handle(const FString& Command, const JObject& Args, JObject Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* Error, const TCHAR* Detail) { Code = Error; Message = Detail; return false; };
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!IsInGameThread() || !World || GEditor->PlayWorld)
        return Fail(TEXT("invalid_context"), TEXT("Actor operations require an idle editor world."));
    if (Command == TEXT("actor_info"))
    {
        FString Path;
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("actor_path"), Path) || Path.Len() > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected an exact bounded actor_path."));
        AActor* Actor = Resolve(World, Path);
        if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current editor world."));
        Data->SetObjectField(TEXT("actor"), Describe(Actor));
        return true;
    }
    if (Command == TEXT("gas_info"))
    {
        FString Path;
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("actor_path"), Path) ||
            Path.IsEmpty() || Path.Len() > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact bounded actor_path."));

        AActor* Actor = Resolve(World, Path);
        if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current editor world."));

        constexpr int32 MaxComponents = 16;
        constexpr int32 MaxAbilities = 64;
        constexpr int32 MaxEffects = 64;
        constexpr int32 MaxAttributes = 128;
        constexpr int32 MaxTags = 128;
        TArray<UAbilitySystemComponent*> AbilitySystems;
        Actor->GetComponents<UAbilitySystemComponent>(AbilitySystems);

        TArray<TSharedPtr<FJsonValue>> ComponentResults;
        const int32 ComponentCount = AbilitySystems.Num();
        const int32 ComponentLimit = FMath::Min(ComponentCount, MaxComponents);
        for (int32 ComponentIndex = 0; ComponentIndex < ComponentLimit; ++ComponentIndex)
        {
            UAbilitySystemComponent* AbilitySystem = AbilitySystems[ComponentIndex];
            if (!IsValid(AbilitySystem)) continue;

            auto Component = MakeShared<FJsonObject>();
            Component->SetStringField(TEXT("name"), AbilitySystem->GetName());
            Component->SetStringField(TEXT("path"), AbilitySystem->GetPathName());
            Component->SetStringField(TEXT("class_path"), AbilitySystem->GetClass()->GetPathName());
            Component->SetBoolField(TEXT("replicated"), AbilitySystem->GetIsReplicated());
            Component->SetStringField(TEXT("replication_mode"),
                ForgeGameplayAbilities::ReplicationModeName(AbilitySystem->ReplicationMode));
            AActor* OwnerActor = AbilitySystem->GetOwnerActor();
            AActor* AvatarActor = AbilitySystem->GetAvatarActor();
            Component->SetStringField(TEXT("owner_actor"), OwnerActor ? OwnerActor->GetPathName() : TEXT(""));
            Component->SetStringField(TEXT("avatar_actor"), AvatarActor ? AvatarActor->GetPathName() : TEXT(""));
            Component->SetBoolField(TEXT("actor_info_initialized"), OwnerActor != nullptr && AvatarActor != nullptr);

            TArray<FGameplayAttribute> AllAttributes;
            AbilitySystem->GetAllAttributes(AllAttributes);
            TArray<TSharedPtr<FJsonValue>> Attributes;
            int32 NonFiniteAttributeCount = 0;
            for (int32 AttributeIndex = 0; AttributeIndex < FMath::Min(AllAttributes.Num(), MaxAttributes); ++AttributeIndex)
            {
                const FGameplayAttribute& Attribute = AllAttributes[AttributeIndex];
                FProperty* Property = Attribute.GetUProperty();
                UClass* AttributeSetClass = Attribute.IsValid() ? Attribute.GetAttributeSetClass() : nullptr;
                if (!Property || !AttributeSetClass) continue;

                bool bFound = false;
                const float CurrentValue = AbilitySystem->GetGameplayAttributeValue(Attribute, bFound);
                const float BaseValue = AbilitySystem->GetNumericAttributeBase(Attribute);
                if (!bFound) continue;
                if (!FMath::IsFinite(CurrentValue) || !FMath::IsFinite(BaseValue))
                {
                    ++NonFiniteAttributeCount;
                    continue;
                }

                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("name"), Property->GetName());
                Item->SetStringField(TEXT("attribute_set_class"), AttributeSetClass->GetPathName());
                Item->SetNumberField(TEXT("base_value"), BaseValue);
                Item->SetNumberField(TEXT("current_value"), CurrentValue);
                Attributes.Add(MakeShared<FJsonValueObject>(Item));
            }
            Component->SetArrayField(TEXT("attributes"), Attributes);
            Component->SetNumberField(TEXT("attribute_count"), AllAttributes.Num());
            Component->SetNumberField(TEXT("non_finite_attribute_count"), NonFiniteAttributeCount);
            Component->SetBoolField(TEXT("attributes_truncated"), AllAttributes.Num() > MaxAttributes);

            FGameplayTagContainer OwnedTags;
            AbilitySystem->GetOwnedGameplayTags(OwnedTags);
            const TArray<FGameplayTag>& AllTags = OwnedTags.GetGameplayTagArray();
            TArray<TSharedPtr<FJsonValue>> Tags;
            for (int32 TagIndex = 0; TagIndex < FMath::Min(AllTags.Num(), MaxTags); ++TagIndex)
            {
                Tags.Add(MakeShared<FJsonValueString>(AllTags[TagIndex].ToString()));
            }
            Component->SetArrayField(TEXT("owned_tags"), Tags);
            Component->SetNumberField(TEXT("owned_tag_count"), AllTags.Num());
            Component->SetBoolField(TEXT("owned_tags_truncated"), AllTags.Num() > MaxTags);

            const TArray<FGameplayAbilitySpec>& AbilitySpecs = AbilitySystem->GetActivatableAbilities();
            TArray<TSharedPtr<FJsonValue>> Abilities;
            for (int32 AbilityIndex = 0; AbilityIndex < FMath::Min(AbilitySpecs.Num(), MaxAbilities); ++AbilityIndex)
            {
                const FGameplayAbilitySpec& Spec = AbilitySpecs[AbilityIndex];
                if (!IsValid(Spec.Ability)) continue;
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("class_path"), Spec.Ability->GetClass()->GetPathName());
                Item->SetNumberField(TEXT("level"), Spec.Level);
                Item->SetNumberField(TEXT("input_id"), Spec.InputID);
                Item->SetBoolField(TEXT("active"), Spec.IsActive());
                Abilities.Add(MakeShared<FJsonValueObject>(Item));
            }
            Component->SetArrayField(TEXT("abilities"), Abilities);
            Component->SetNumberField(TEXT("ability_count"), AbilitySpecs.Num());
            Component->SetBoolField(TEXT("abilities_truncated"), AbilitySpecs.Num() > MaxAbilities);

            const TArray<FActiveGameplayEffectHandle> EffectHandles =
                AbilitySystem->GetActiveEffects(FGameplayEffectQuery());
            TArray<TSharedPtr<FJsonValue>> Effects;
            for (int32 EffectIndex = 0; EffectIndex < FMath::Min(EffectHandles.Num(), MaxEffects); ++EffectIndex)
            {
                const FActiveGameplayEffectHandle& Handle = EffectHandles[EffectIndex];
                const FActiveGameplayEffect* ActiveEffect = AbilitySystem->GetActiveGameplayEffect(Handle);
                const UGameplayEffect* EffectClass = AbilitySystem->GetGameplayEffectCDO(Handle);
                if (!ActiveEffect || !IsValid(EffectClass)) continue;
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("class_path"), EffectClass->GetPathName());
                Item->SetNumberField(TEXT("level"), ActiveEffect->Spec.GetLevel());
                Item->SetNumberField(TEXT("stack_count"), AbilitySystem->GetCurrentStackCount(Handle));
                const float Duration = ActiveEffect->GetDuration();
                const float Remaining = ActiveEffect->GetTimeRemaining(World->GetTimeSeconds());
                if (FMath::IsFinite(Duration)) Item->SetNumberField(TEXT("duration_seconds"), Duration);
                if (FMath::IsFinite(Remaining)) Item->SetNumberField(TEXT("remaining_seconds"), Remaining);
                Effects.Add(MakeShared<FJsonValueObject>(Item));
            }
            Component->SetArrayField(TEXT("active_effects"), Effects);
            Component->SetNumberField(TEXT("active_effect_count"), EffectHandles.Num());
            Component->SetBoolField(TEXT("active_effects_truncated"), EffectHandles.Num() > MaxEffects);
            ComponentResults.Add(MakeShared<FJsonValueObject>(Component));
        }

        Data->SetStringField(TEXT("actor_path"), Actor->GetPathName());
        Data->SetArrayField(TEXT("ability_system_components"), ComponentResults);
        Data->SetNumberField(TEXT("ability_system_component_count"), ComponentCount);
        Data->SetBoolField(TEXT("ability_system_components_truncated"), ComponentCount > MaxComponents);
        return true;
    }
    TSharedPtr<FJsonObject> Recipe;
    FPreview Plan;
    if (Command == TEXT("actor_apply"))
    {
        FString Id, Confirmation;
        if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), Id) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
        if (!Previews.RemoveAndCopyValue(Id, Plan) || Plan.Expires <= FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"), TEXT("Preview is expired, consumed or belongs to another session."));
        Recipe = Plan.Recipe;
    }
    else
    {
        const TSharedPtr<FJsonObject>* Value;
        if (Args->Values.Num() != 1 || !Args->TryGetObjectField(TEXT("recipe"), Value))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected an actor recipe."));
        Recipe = *Value;
    }
    const TArray<TSharedPtr<FJsonValue>>* Operations;
    if (Recipe->Values.Num() != 1 || !Recipe->TryGetArrayField(TEXT("operations"), Operations) || Operations->Num() < 1 || Operations->Num() > 32)
        return Fail(TEXT("invalid_arguments"), TEXT("Use 1 to 32 actor operations."));
    const TSet<FString> Allowed{TEXT("op"),TEXT("actor_path"),TEXT("class_path"),TEXT("label"),TEXT("location"),TEXT("rotation"),TEXT("scale"),TEXT("hidden"),TEXT("mesh_path")};
    for (const auto& Value : *Operations)
    {
        if (Value->Type != EJson::Object) return Fail(TEXT("invalid_arguments"), TEXT("Operations must be objects."));
        const auto Op = Value->AsObject().ToSharedRef();
        for (const auto& Pair : Op->Values)
        {
            if (!Allowed.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown actor operation field."));
            const EJson Type = Pair.Key == TEXT("hidden") ? EJson::Boolean
                : (Pair.Key == TEXT("location") || Pair.Key == TEXT("rotation") || Pair.Key == TEXT("scale")) ? EJson::Array : EJson::String;
            if (Pair.Value->Type != Type) return Fail(TEXT("invalid_arguments"), TEXT("Actor fields must have exact JSON types."));
        }
        FString Kind, Path, Class, Label;
        Op->TryGetStringField(TEXT("op"), Kind); Op->TryGetStringField(TEXT("actor_path"), Path);
        Op->TryGetStringField(TEXT("class_path"), Class); Op->TryGetStringField(TEXT("label"), Label);
        FString MeshPath;
        Op->TryGetStringField(TEXT("mesh_path"), MeshPath);
        if (!MeshPath.IsEmpty() && (Kind != TEXT("spawn") || Class != TEXT("/Script/Engine.StaticMeshActor")))
            return Fail(TEXT("invalid_arguments"), TEXT("mesh_path is supported only for new native StaticMeshActor placement."));
        if (!MeshPath.IsEmpty() && !ResolveMesh(MeshPath))
            return Fail(TEXT("asset_not_found"), TEXT("mesh_path must identify an exact loaded /Game/ static mesh within geometry limits."));
        if (Path.Len() > 512 || Class.Len() > 240 || Label.Len() > 64)
            return Fail(TEXT("invalid_arguments"), TEXT("Actor names and paths exceed their bounds."));
        FVector Location(0), Rotation(0), Scale(1);
        if (!ReadVector(Op, TEXT("location"), Location) || !ReadVector(Op, TEXT("rotation"), Rotation) || !ReadVector(Op, TEXT("scale"), Scale))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected bounded vectors and nonzero scale."));
        if (Kind == TEXT("spawn"))
        {
            if (!Path.IsEmpty() || !SpawnClass(Class)) return Fail(TEXT("command_not_allowed"), TEXT("Only allowlisted native actor classes can be spawned."));
        }
        else if (Kind == TEXT("transform") || Kind == TEXT("visibility"))
        {
            AActor* Actor = Resolve(World, Path);
            if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current world."));
            if (!Class.IsEmpty() || !Label.IsEmpty() || Actor->GetAttachParentActor() || !Actor->GetRootComponent())
                return Fail(TEXT("invalid_context"), TEXT("Existing actor edits require an unattached actor with a root component."));
            if (Kind == TEXT("visibility") && !Op->HasField(TEXT("hidden")))
                return Fail(TEXT("invalid_arguments"), TEXT("Visibility requires hidden."));
            if (Kind == TEXT("visibility") && (Op->HasField(TEXT("location")) || Op->HasField(TEXT("rotation")) || Op->HasField(TEXT("scale"))))
                return Fail(TEXT("invalid_arguments"), TEXT("Visibility cannot contain transform fields."));
            if (Kind == TEXT("transform") && Op->HasField(TEXT("hidden")))
                return Fail(TEXT("invalid_arguments"), TEXT("Use a visibility operation for hidden state."));
            if (Kind == TEXT("transform") && !Op->HasField(TEXT("location")) && !Op->HasField(TEXT("rotation")) && !Op->HasField(TEXT("scale")))
                return Fail(TEXT("invalid_arguments"), TEXT("Transform requires at least one transform field."));
        }
        else return Fail(TEXT("command_not_allowed"), TEXT("Actor operation is not allowlisted."));
    }
    const FString Current = Fingerprint(World, *Operations);
    if (Command == TEXT("actor_preview"))
    {
        for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending previews."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(Id, {Recipe, Current, FPlatformTime::Seconds() + 600});
        Data->SetStringField(TEXT("preview_id"), Id); Data->SetNumberField(TEXT("expires_in_seconds"), 600);
        Data->SetArrayField(TEXT("changes"), *Operations); Data->SetBoolField(TEXT("saves_level"), false);
        Data->SetStringField(TEXT("world"), World->GetPathName()); return true;
    }
    if (Plan.Fingerprint != Current) return Fail(TEXT("stale_preview"), TEXT("Actor/world state changed after preview."));
    struct FSnapshot { AActor* Actor; FTransform Transform; bool Hidden; };
    TArray<FSnapshot> Snapshots; TArray<AActor*> Created;
    TArray<TSharedPtr<FJsonValue>> Results;
    FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "ActorRecipe", "ForgeMCP actor recipe"));
    bool Success = true;
    for (const auto& Value : *Operations)
    {
        const auto Op = Value->AsObject().ToSharedRef(); FString Kind, Path, Class, Label;
        Op->TryGetStringField(TEXT("op"), Kind); Op->TryGetStringField(TEXT("actor_path"), Path);
        Op->TryGetStringField(TEXT("class_path"), Class); Op->TryGetStringField(TEXT("label"), Label);
        AActor* Actor = Kind == TEXT("spawn") ? nullptr : Resolve(World, Path);
        FVector Location = Actor ? Actor->GetActorLocation() : FVector::ZeroVector;
        const FRotator Existing = Actor ? Actor->GetActorRotation() : FRotator::ZeroRotator;
        FVector Rotation(Existing.Pitch, Existing.Yaw, Existing.Roll), Scale = Actor ? Actor->GetActorScale3D() : FVector::OneVector;
        ReadVector(Op, TEXT("location"), Location); ReadVector(Op, TEXT("rotation"), Rotation); ReadVector(Op, TEXT("scale"), Scale);
        if (!Actor)
        {
            FActorSpawnParameters Params; Params.ObjectFlags |= RF_Transactional;
            Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Actor = World->SpawnActor<AActor>(SpawnClass(Class), FTransform(FRotator(Rotation.X,Rotation.Y,Rotation.Z),Location,Scale), Params);
            if (!Actor) { Success = false; break; }
            Created.Add(Actor); if (!Label.IsEmpty()) Actor->SetActorLabel(Label);
            FString MeshPath;
            Op->TryGetStringField(TEXT("mesh_path"), MeshPath);
            if (!MeshPath.IsEmpty())
            {
                AStaticMeshActor* MeshActor = Cast<AStaticMeshActor>(Actor);
                UStaticMeshComponent* Component = MeshActor ? MeshActor->GetStaticMeshComponent() : nullptr;
                if (Component) Component->Modify();
                if (!Component || !Component->SetStaticMesh(ResolveMesh(MeshPath))) { Success = false; break; }
            }
        }
        else
        {
            if (!Snapshots.ContainsByPredicate([&](const FSnapshot& S){ return S.Actor == Actor; }))
                Snapshots.Add({Actor, Actor->GetActorTransform(), Actor->IsHidden()});
            Actor->Modify(); Actor->GetRootComponent()->Modify();
            if (Kind == TEXT("transform") && !Actor->SetActorTransform(FTransform(FRotator(Rotation.X,Rotation.Y,Rotation.Z),Location,Scale), false, nullptr, ETeleportType::TeleportPhysics))
                { Success = false; break; }
        }
        if (Op->HasField(TEXT("hidden"))) Actor->SetActorHiddenInGame(Op->GetBoolField(TEXT("hidden")));
        Actor->PostEditMove(true); Results.Add(MakeShared<FJsonValueObject>(Describe(Actor)));
    }
    bool Restored = true;
    if (!Success)
    {
        for (const FSnapshot& S : Snapshots)
        {
            Restored &= S.Actor->SetActorTransform(S.Transform, false, nullptr, ETeleportType::TeleportPhysics);
            S.Actor->SetActorHiddenInGame(S.Hidden);
        }
        for (AActor* Actor : Created) Restored &= World->DestroyActor(Actor);
        Transaction.Cancel();
    }
    Data->SetStringField(TEXT("state"), Success ? TEXT("completed") : Restored ? TEXT("rolled_back") : TEXT("partial"));
    Data->SetArrayField(TEXT("actors"), Success ? Results : TArray<TSharedPtr<FJsonValue>>());
    Data->SetBoolField(TEXT("saved"), false); return true;
}
