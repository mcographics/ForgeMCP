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
#include "Components/PrimitiveComponent.h"
#include "Components/ActorComponent.h"
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
#include "UObject/UnrealType.h"
#include "UObject/TextProperty.h"
#include "Misc/OutputDeviceNull.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;
UClass* SpawnClass(const FString& Name)
{
    // The isolated Phase 6C visual acceptance project stages this licensed
    // content pack separately. Keep this exact Blueprint path allowlisted;
    // never generalize actor spawning to arbitrary project classes.
    if (Name == TEXT("/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Sky.Ultra_Dynamic_Sky_C"))
    {
        UClass* SkyClass = LoadClass<AActor>(nullptr, *Name);
        return SkyClass && SkyClass->IsChildOf(AActor::StaticClass()) ? SkyClass : nullptr;
    }
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
UActorComponent* ResolveComponent(UWorld* World, const FString& Path)
{
    if (Path.IsEmpty() || Path.Len() > 512) return nullptr;
    for (TActorIterator<AActor> It(World); It; ++It)
    {
        if (!IsValid(*It)) continue;
        TArray<UActorComponent*> Components;
        (*It)->GetComponents<UActorComponent>(Components);
        for (UActorComponent* Component : Components)
            if (IsValid(Component) && Component->GetPathName() == Path) return Component;
    }
    return nullptr;
}
bool IsInspectableActorProperty(const FProperty* Property)
{
    if (!Property || Property->ArrayDim != 1 || Property->HasAnyPropertyFlags(
        CPF_Transient | CPF_Deprecated | CPF_SkipSerialization)) return false;
    if (Property->IsA<FBoolProperty>() || Property->IsA<FEnumProperty>() ||
        Property->IsA<FByteProperty>() || Property->IsA<FNumericProperty>() ||
        Property->IsA<FNameProperty>() || Property->IsA<FStrProperty>() || Property->IsA<FTextProperty>()) return true;
    const FStructProperty* Struct = CastField<FStructProperty>(Property);
    return Struct && (Struct->Struct == TBaseStructure<FVector>::Get() ||
        Struct->Struct == TBaseStructure<FRotator>::Get() ||
        Struct->Struct == TBaseStructure<FLinearColor>::Get() ||
        Struct->Struct == TBaseStructure<FColor>::Get());
}
bool IsEditableActorProperty(AActor* Actor, FProperty* Property)
{
    return Actor && IsInspectableActorProperty(Property) && Property->HasAnyPropertyFlags(CPF_Edit) &&
        !Property->HasAnyPropertyFlags(CPF_EditConst | CPF_DisableEditOnInstance | CPF_Config) &&
        Actor->CanEditChange(Property);
}
bool IsEditableComponentProperty(UActorComponent* Component, FProperty* Property)
{
    return Component && IsInspectableActorProperty(Property) && Property->HasAnyPropertyFlags(CPF_Edit) &&
        !Property->HasAnyPropertyFlags(CPF_EditConst | CPF_DisableEditOnInstance | CPF_Config) &&
        Component->CanEditChange(Property);
}
bool ExportActorProperty(UObject* Actor, FProperty* Property, FString& Value)
{
    if (!Actor || !Property) return false;
    if (const FBoolProperty* BoolProperty = CastField<FBoolProperty>(Property))
    {
        Value = BoolProperty->GetPropertyValue_InContainer(Actor) ? TEXT("true") : TEXT("false");
        return true;
    }
    const bool ExportResult = Property->ExportText_Direct(Value,
        Property->ContainerPtrToValuePtr<void>(Actor), nullptr, Actor, PPF_None, nullptr);
    return ExportResult && Value.Len() <= 512;
}
bool ParseBooleanText(const FString& Text, bool& Value)
{
    FString NormalizedInput = Text;
    NormalizedInput.TrimStartAndEndInline();
    if (NormalizedInput.Equals(TEXT("true"), ESearchCase::IgnoreCase) || NormalizedInput == TEXT("1"))
    {
        Value = true;
        return true;
    }
    if (NormalizedInput.Equals(TEXT("false"), ESearchCase::IgnoreCase) || NormalizedInput == TEXT("0"))
    {
        Value = false;
        return true;
    }
    return false;
}
bool ImportNativePropertyText(UObject* Owner, FProperty* Property, const FString& Text,
    void* Destination, FOutputDeviceNull& ErrorOutput, bool DestinationIsContainer = false)
{
    if (!Owner || !Property || !Destination || Text.Len() > 512) return false;
    void* PropertyValue = DestinationIsContainer
        ? Property->ContainerPtrToValuePtr<void>(Destination) : Destination;
    if (!PropertyValue) return false;
    if (FBoolProperty* BoolProperty = CastField<FBoolProperty>(Property))
    {
        bool Value = false;
        if (!ParseBooleanText(Text, Value)) return false;
        BoolProperty->SetPropertyValue(PropertyValue, Value);
        return true;
    }
    const TCHAR* End = Property->ImportText_Direct(*Text, PropertyValue, Owner, PPF_None, &ErrorOutput);
    return End && *End == TEXT('\0');
}
bool ParseActorProperty(UObject* Actor, FProperty* Property, const FString& Text, FString& Normalized)
{
    if (!Actor || !Property || Text.Len() > 512 || (Text.IsEmpty() && !Property->IsA<FStrProperty>())) return false;
    void* Value = FMemory::Malloc(Property->GetSize(), Property->GetMinAlignment());
    if (!Value) return false;
    Property->InitializeValue(Value);
    Property->CopyCompleteValue(Value, Property->ContainerPtrToValuePtr<void>(Actor));
    if (FBoolProperty* BoolProperty = CastField<FBoolProperty>(Property))
    {
        bool BooleanValue = false;
        const bool ParsedBoolean = ParseBooleanText(Text, BooleanValue);
        if (ParsedBoolean)
        {
            BoolProperty->SetPropertyValue(Value, BooleanValue);
            Normalized = BooleanValue ? TEXT("true") : TEXT("false");
        }
        Property->DestroyValue(Value);
        FMemory::Free(Value);
        return ParsedBoolean;
    }
    FOutputDeviceNull ErrorOutput;
    const bool Imported = ImportNativePropertyText(Actor, Property, Text, Value, ErrorOutput);
    bool Finite = true;
    if (const FNumericProperty* Numeric = CastField<FNumericProperty>(Property))
        Finite = Numeric->IsInteger() || FMath::IsFinite(Numeric->GetFloatingPointPropertyValue(Value));
    else if (const FStructProperty* Struct = CastField<FStructProperty>(Property))
    {
        if (Struct->Struct == TBaseStructure<FVector>::Get())
        {
            const FVector& V = *static_cast<const FVector*>(Value);
            Finite = FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z);
        }
        else if (Struct->Struct == TBaseStructure<FRotator>::Get())
        {
            const FRotator& V = *static_cast<const FRotator*>(Value);
            Finite = FMath::IsFinite(V.Roll) && FMath::IsFinite(V.Pitch) && FMath::IsFinite(V.Yaw);
        }
        else if (Struct->Struct == TBaseStructure<FLinearColor>::Get())
        {
            const FLinearColor& V = *static_cast<const FLinearColor*>(Value);
            Finite = FMath::IsFinite(V.R) && FMath::IsFinite(V.G) && FMath::IsFinite(V.B) && FMath::IsFinite(V.A);
        }
    }
    const bool Parsed = Imported && Finite && Property->ExportText_Direct(
        Normalized, Value, nullptr, Actor, PPF_None, nullptr) && Normalized.Len() <= 512;
    Property->DestroyValue(Value);
    FMemory::Free(Value);
    return Parsed;
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
    TArray<TSharedPtr<FJsonValue>> ActorTags;
    for (int32 Index = 0; Index < FMath::Min(Actor->Tags.Num(), 64); ++Index)
        ActorTags.Add(MakeShared<FJsonValueString>(Actor->Tags[Index].ToString()));
    Result->SetArrayField(TEXT("tags"), ActorTags);
    Result->SetBoolField(TEXT("tags_truncated"), Actor->Tags.Num() > ActorTags.Num());
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
bool ReadActorTags(const JObject& Op, TArray<FName>& OutTags)
{
    OutTags.Reset();
    if (!Op->HasField(TEXT("tags"))) return true;
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Op->TryGetArrayField(TEXT("tags"), Values) || Values->Num() > 16) return false;
    TSet<FName> Unique;
    for (const TSharedPtr<FJsonValue>& Value : *Values)
    {
        FString Tag;
        if (!Value.IsValid() || Value->Type != EJson::String || !Value->TryGetString(Tag) ||
            Tag.IsEmpty() || Tag.Len() > 128 || Tag.TrimStartAndEnd() != Tag) return false;
        const FName Name(*Tag);
        if (Unique.Contains(Name)) return false;
        Unique.Add(Name);
        OutTags.Add(Name);
    }
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
    if (Command == TEXT("actor_delete_preview") || Command == TEXT("actor_delete_apply"))
    {
        auto IsDeletable = [&](AActor* Actor)
        {
            if (!IsValid(Actor) || Actor == World->GetWorldSettings() || Actor->GetWorld() != World ||
                Actor->GetLevel() != World->GetCurrentLevel() || Actor->GetAttachParentActor()) return false;
            const FString ClassPath = Actor->GetClass()->GetPathName();
            if (ClassPath == TEXT("/Script/Engine.WorldDataLayers") ||
                ClassPath == TEXT("/Script/Engine.WorldPartitionMiniMap") ||
                ClassPath == TEXT("/Script/Engine.LevelScriptActor")) return false;
            TArray<AActor*> Attached;
            Actor->GetAttachedActors(Attached, true, true);
            return Attached.IsEmpty();
        };
        auto DeleteFingerprint = [&](AActor* Actor)
        {
            auto Operation = MakeShared<FJsonObject>();
            Operation->SetStringField(TEXT("op"), TEXT("delete"));
            Operation->SetStringField(TEXT("actor_path"), Actor->GetPathName());
            TArray<TSharedPtr<FJsonValue>> Operations;
            Operations.Add(MakeShared<FJsonValueObject>(Operation));
            return Fingerprint(World, Operations);
        };

        if (Command == TEXT("actor_delete_preview"))
        {
            FString ActorPath;
            if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("actor_path"), ActorPath) ||
                ActorPath.IsEmpty() || ActorPath.Len() > 512)
                return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact actor_path from the current editor world."));
            AActor* Actor = Resolve(World, ActorPath);
            if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("The exact actor is not loaded in the current editor world."));
            if (!IsDeletable(Actor))
                return Fail(TEXT("actor_protected"), TEXT("This operation cannot delete world infrastructure, attached actors, actors with attached children, or actors outside the current level."));
            for (auto It = DeletePreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (DeletePreviews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("At most 32 actor deletion previews may be pending."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FDeletePreview Preview;
            Preview.Actor = Actor;
            Preview.World = World;
            Preview.ActorPath = ActorPath;
            Preview.ClassPath = Actor->GetClass()->GetPathName();
            Preview.WorldPath = World->GetPathName();
            Preview.Fingerprint = DeleteFingerprint(Actor);
            Preview.Expires = FPlatformTime::Seconds() + 300;
            if (Preview.Fingerprint.IsEmpty()) return Fail(TEXT("preview_failed"), TEXT("The actor state could not be fingerprinted."));
            DeletePreviews.Add(Id, MoveTemp(Preview));
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("world"), World->GetPathName());
            Data->SetObjectField(TEXT("actor"), Describe(Actor));
            Data->SetBoolField(TEXT("deletes_exactly_one_actor"), true);
            Data->SetBoolField(TEXT("saves_level"), false);
            Data->SetStringField(TEXT("undo"), TEXT("An editor transaction is recorded; save current level separately to persist the deletion."));
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            return true;
        }

        FString PreviewId, Confirmation;
        if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), PreviewId) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || PreviewId != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
        FDeletePreview Plan;
        if (!DeletePreviews.RemoveAndCopyValue(PreviewId, Plan) || Plan.Expires <= FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"), TEXT("Deletion preview is expired, consumed or belongs to another editor session."));
        AActor* Actor = Plan.Actor.Get();
        if (Plan.World.Get() != World || Plan.WorldPath != World->GetPathName() ||
            !IsValid(Actor) || Resolve(World, Plan.ActorPath) != Actor ||
            Actor->GetClass()->GetPathName() != Plan.ClassPath || !IsDeletable(Actor) ||
            DeleteFingerprint(Actor) != Plan.Fingerprint)
            return Fail(TEXT("stale_preview"), TEXT("The world or exact actor changed after preview; nothing was deleted."));

        FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "DeleteActor", "ForgeMCP delete actor"));
        World->Modify();
        Actor->Modify();
        const FString DeletedPath = Actor->GetPathName();
        const FString DeletedClass = Actor->GetClass()->GetPathName();
        const FString DeletedLabel = Actor->GetActorLabel();
        const bool bDeleted = World->EditorDestroyActor(Actor, true);
        Data->SetStringField(TEXT("actor_path"), DeletedPath);
        Data->SetStringField(TEXT("class_path"), DeletedClass);
        Data->SetStringField(TEXT("label"), DeletedLabel);
        Data->SetBoolField(TEXT("deleted"), bDeleted);
        Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("undo_available"), bDeleted);
        Data->SetStringField(TEXT("state"), bDeleted ? TEXT("deleted_unsaved") : TEXT("failed"));
        Data->SetStringField(TEXT("world"), World->GetPathName());
        return true;
    }
    if (Command == TEXT("actor_property_info"))
    {
        FString Path; double Limit = 100;
        if (Args->Values.Num() < 1 || Args->Values.Num() > 2 ||
            !Args->TryGetStringField(TEXT("actor_path"), Path) || Path.IsEmpty() || Path.Len() > 512 ||
            (Args->HasField(TEXT("limit")) && !Args->TryGetNumberField(TEXT("limit"), Limit)) ||
            Limit < 1 || Limit > 200 || FMath::FloorToDouble(Limit) != Limit ||
            (Args->HasField(TEXT("limit")) && Args->Values[TEXT("limit")]->Type != EJson::Number))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected actor_path and optional integer limit from 1 to 200."));
        for (const auto& Pair : Args->Values)
            if (Pair.Key != TEXT("actor_path") && Pair.Key != TEXT("limit"))
                return Fail(TEXT("invalid_arguments"), TEXT("Actor property inspection contains an unsupported field."));
        AActor* Actor = Resolve(World, Path);
        if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current editor world."));
        TArray<TSharedPtr<FJsonValue>> Properties;
        int32 Supported = 0, Omitted = 0;
        for (TFieldIterator<FProperty> It(Actor->GetClass(), EFieldIteratorFlags::IncludeSuper); It; ++It)
        {
            FProperty* Property = *It;
            if (!IsInspectableActorProperty(Property)) { ++Omitted; continue; }
            FString Value;
            if (!ExportActorProperty(Actor, Property, Value)) { ++Omitted; continue; }
            ++Supported;
            if (Properties.Num() >= static_cast<int32>(Limit)) continue;
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Property->GetName().Left(128));
            Item->SetStringField(TEXT("type"), Property->GetCPPType().Left(128));
            Item->SetStringField(TEXT("reflection_class"), Property->GetClass()->GetName());
            Item->SetStringField(TEXT("value"), Value);
            Item->SetBoolField(TEXT("editable_in_editor"), IsEditableActorProperty(Actor, Property));
            Properties.Add(MakeShared<FJsonValueObject>(Item));
        }
        if (!Supported) return Fail(TEXT("properties_unavailable"), TEXT("No supported simple reflected actor properties were found."));
        Data->SetStringField(TEXT("actor_path"), Actor->GetPathName());
        Data->SetStringField(TEXT("class_path"), Actor->GetClass()->GetPathName());
        Data->SetArrayField(TEXT("properties"), Properties);
        Data->SetNumberField(TEXT("supported_property_count"), Supported);
        Data->SetNumberField(TEXT("returned_property_count"), Properties.Num());
        Data->SetNumberField(TEXT("omitted_complex_or_transient_property_count"), Omitted);
        Data->SetBoolField(TEXT("truncated"), Supported > Properties.Num());
        Data->SetBoolField(TEXT("level_dirty"), Actor->GetLevel() && Actor->GetLevel()->GetOutermost()->IsDirty());
        Data->SetStringField(TEXT("scope"), TEXT("Loaded actor instance; bounded simple reflected properties only. Nested objects, arrays and component properties are omitted; no save or reference traversal."));
        return true;
    }
    if (Command == TEXT("component_property_info"))
    {
        FString Path;
        double Limit = 100;
        if (Args->Values.Num() < 1 || Args->Values.Num() > 2 ||
            !Args->TryGetStringField(TEXT("component_path"), Path) || Path.IsEmpty() || Path.Len() > 512 ||
            (Args->HasField(TEXT("limit")) && !Args->TryGetNumberField(TEXT("limit"), Limit)) ||
            Limit < 1 || Limit > 200 || FMath::FloorToDouble(Limit) != Limit ||
            (Args->HasField(TEXT("limit")) && Args->Values[TEXT("limit")]->Type != EJson::Number))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected component_path and optional integer limit from 1 to 200."));
        for (const auto& Pair : Args->Values)
            if (Pair.Key != TEXT("component_path") && Pair.Key != TEXT("limit"))
                return Fail(TEXT("invalid_arguments"), TEXT("Component property inspection contains an unsupported field."));
        UActorComponent* Component = ResolveComponent(World, Path);
        if (!Component) return Fail(TEXT("component_not_found"), TEXT("Component is not owned by an actor in the current editor world."));
        TArray<TSharedPtr<FJsonValue>> Properties;
        int32 Supported = 0, Omitted = 0;
        for (TFieldIterator<FProperty> It(Component->GetClass(), EFieldIteratorFlags::IncludeSuper); It; ++It)
        {
            FProperty* Property = *It;
            if (!IsInspectableActorProperty(Property)) { ++Omitted; continue; }
            FString Value;
            if (!ExportActorProperty(Component, Property, Value)) { ++Omitted; continue; }
            ++Supported;
            if (Properties.Num() >= static_cast<int32>(Limit)) continue;
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Property->GetName().Left(128));
            Item->SetStringField(TEXT("type"), Property->GetCPPType().Left(128));
            Item->SetStringField(TEXT("reflection_class"), Property->GetClass()->GetName());
            Item->SetStringField(TEXT("value"), Value);
            Item->SetBoolField(TEXT("editable_in_editor"), Property->HasAnyPropertyFlags(CPF_Edit) &&
                !Property->HasAnyPropertyFlags(CPF_EditConst | CPF_DisableEditOnInstance | CPF_Config) &&
                Component->CanEditChange(Property));
            Properties.Add(MakeShared<FJsonValueObject>(Item));
        }
        if (!Supported) return Fail(TEXT("properties_unavailable"), TEXT("No supported simple reflected component properties were found."));
        Data->SetStringField(TEXT("component_path"), Component->GetPathName());
        Data->SetStringField(TEXT("class_path"), Component->GetClass()->GetPathName());
        Data->SetStringField(TEXT("owner_actor"), Component->GetOwner() ? Component->GetOwner()->GetPathName() : TEXT(""));
        Data->SetArrayField(TEXT("properties"), Properties);
        Data->SetNumberField(TEXT("supported_property_count"), Supported);
        Data->SetNumberField(TEXT("returned_property_count"), Properties.Num());
        Data->SetNumberField(TEXT("omitted_complex_or_transient_property_count"), Omitted);
        Data->SetBoolField(TEXT("truncated"), Supported > Properties.Num());
        Data->SetBoolField(TEXT("saved"), false);
        Data->SetStringField(TEXT("scope"), TEXT("Loaded actor component; bounded simple reflected properties only. Nested objects and containers are omitted; read-only operation."));
        return true;
    }
    if (Command == TEXT("component_property_edit_preview"))
    {
        FString Path, PropertyName, Proposed;
        if (Args->Values.Num() != 3 || !Args->TryGetStringField(TEXT("component_path"), Path) ||
            Path.IsEmpty() || Path.Len() > 512 || !Args->TryGetStringField(TEXT("property_name"), PropertyName) ||
            PropertyName.IsEmpty() || PropertyName.Len() > 128 ||
            !Args->TryGetStringField(TEXT("property_value"), Proposed) || Proposed.Len() > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected exact component_path, property_name and bounded property_value strings."));
        for (const auto& Pair : Args->Values)
            if ((Pair.Key != TEXT("component_path") && Pair.Key != TEXT("property_name") && Pair.Key != TEXT("property_value")) ||
                !Pair.Value.IsValid() || Pair.Value->Type != EJson::String)
                return Fail(TEXT("invalid_arguments"), TEXT("Component property edit fields must be exact strings."));
        for (int32 Index = 0; Index < PropertyName.Len(); ++Index)
        {
            const TCHAR C = PropertyName[Index];
            if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
                (Index > 0 && C >= '0' && C <= '9')))
                return Fail(TEXT("invalid_arguments"), TEXT("Property names must be exact reflected identifiers."));
        }
        UActorComponent* Component = ResolveComponent(World, Path);
        if (!Component) return Fail(TEXT("component_not_found"), TEXT("Component is not owned by an actor in the current editor world."));
        FProperty* Property = FindFProperty<FProperty>(Component->GetClass(), FName(*PropertyName));
        if (!IsEditableComponentProperty(Component, Property))
            return Fail(TEXT("property_not_editable"), TEXT("The exact component property is not editor-editable or is outside the supported type set."));
        FString Before, Normalized;
        if (!ExportActorProperty(Component, Property, Before) ||
            !ParseActorProperty(Component, Property, Proposed, Normalized))
            return Fail(TEXT("invalid_property_value"), TEXT("The value does not match the reflected component property or is non-finite."));
        if (Before == Normalized) return Fail(TEXT("no_change"), TEXT("The proposed value already matches the current component property."));
        for (auto It = ComponentPropertyEditPreviews.CreateIterator(); It; ++It)
            if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
        if (ComponentPropertyEditPreviews.Num() >= 32)
            return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired component-property previews are allowed."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        FComponentPropertyEditPreview Plan;
        Plan.Target = Component; Plan.World = World; Plan.ComponentPath = Component->GetPathName();
        Plan.OwnerActorPath = Component->GetOwner() ? Component->GetOwner()->GetPathName() : TEXT("");
        Plan.ClassPath = Component->GetClass()->GetPathName(); Plan.PropertyName = PropertyName;
        Plan.BeforeValue = Before; Plan.ProposedValue = Normalized; Plan.Expires = FPlatformTime::Seconds() + 300.0;
        ComponentPropertyEditPreviews.Add(Id, MoveTemp(Plan));
        Data->SetStringField(TEXT("preview_id"), Id); Data->SetStringField(TEXT("component_path"), Component->GetPathName());
        Data->SetStringField(TEXT("owner_actor"), Component->GetOwner() ? Component->GetOwner()->GetPathName() : TEXT(""));
        Data->SetStringField(TEXT("class_path"), Component->GetClass()->GetPathName());
        Data->SetStringField(TEXT("property_name"), PropertyName); Data->SetStringField(TEXT("property_type"), Property->GetCPPType());
        Data->SetStringField(TEXT("current_value"), Before); Data->SetStringField(TEXT("proposed_value"), Normalized);
        Data->SetBoolField(TEXT("saves_level"), false); Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        return true;
    }
    if (Command == TEXT("component_property_edit_apply"))
    {
        FString Id, Confirmation;
        if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), Id) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id.Len() != 32 || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must exactly match the reviewed component-property preview ID."));
        FComponentPropertyEditPreview* Stored = ComponentPropertyEditPreviews.Find(Id);
        if (!Stored) return Fail(TEXT("preview_not_found"), TEXT("Component-property preview is absent, expired or already used."));
        const FComponentPropertyEditPreview Plan = *Stored; ComponentPropertyEditPreviews.Remove(Id);
        UActorComponent* Component = Plan.Target.Get();
        if (Plan.Expires <= FPlatformTime::Seconds() || Plan.World.Get() != World || !IsValid(Component) ||
            ResolveComponent(World, Plan.ComponentPath) != Component || Component->GetPathName() != Plan.ComponentPath ||
            !Component->GetOwner() || Component->GetOwner()->GetPathName() != Plan.OwnerActorPath ||
            Component->GetClass()->GetPathName() != Plan.ClassPath)
            return Fail(TEXT("stale_preview"), TEXT("Component identity, owner or editor world changed; preview the edit again."));
        FProperty* Property = FindFProperty<FProperty>(Component->GetClass(), FName(*Plan.PropertyName));
        FString Current, Normalized;
        if (!IsEditableComponentProperty(Component, Property) || !ExportActorProperty(Component, Property, Current) ||
            Current != Plan.BeforeValue || !ParseActorProperty(Component, Property, Plan.ProposedValue, Normalized) ||
            Normalized != Plan.ProposedValue)
            return Fail(TEXT("stale_preview"), TEXT("Component property changed or is no longer editable."));
        FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "EditComponentProperty", "ForgeMCP Edit Component Property"));
        const bool AddedTransactional = !Component->HasAnyFlags(RF_Transactional);
        if (AddedTransactional) Component->SetFlags(RF_Transactional);
        if (!Component->Modify())
        {
            Transaction.Cancel(); if (AddedTransactional) Component->ClearFlags(RF_Transactional);
            return Fail(TEXT("transaction_unavailable"), TEXT("Unreal could not record the component in an Editor transaction."));
        }
        Component->PreEditChange(Property); FOutputDeviceNull ErrorOutput;
        if (!ImportNativePropertyText(Component, Property, Plan.ProposedValue, Component, ErrorOutput, true))
        {
            ImportNativePropertyText(Component, Property, Plan.BeforeValue, Component, ErrorOutput, true);
            FPropertyChangedEvent Event(Property, EPropertyChangeType::ValueSet); Component->PostEditChangeProperty(Event);
            Transaction.Cancel(); if (AddedTransactional) Component->ClearFlags(RF_Transactional);
            return Fail(TEXT("property_edit_failed"), TEXT("Native component property application failed; original value restored."));
        }
        FPropertyChangedEvent Event(Property, EPropertyChangeType::ValueSet); Component->PostEditChangeProperty(Event);
        FString Applied;
        const bool Exported = ExportActorProperty(Component, Property, Applied);
        if (!Exported || Applied != Plan.ProposedValue)
        {
            const bool IsBitfieldBool = CastField<FBoolProperty>(Property) != nullptr;
            const bool BitfieldValue = IsBitfieldBool
                ? CastFieldChecked<FBoolProperty>(Property)->GetPropertyValue_InContainer(Component) : false;
            Component->PreEditChange(Property);
            ImportNativePropertyText(Component, Property, Plan.BeforeValue, Component, ErrorOutput, true);
            FPropertyChangedEvent Rollback(Property, EPropertyChangeType::ValueSet); Component->PostEditChangeProperty(Rollback);
            Transaction.Cancel(); if (AddedTransactional) Component->ClearFlags(RF_Transactional);
            Code = TEXT("property_verification_failed");
            Message = FString::Printf(TEXT("Component property read-back mismatch for %s (class=%s, exported=%s, expected=%s, observed=%s, bitfield=%s). Original value restored."),
                *Plan.PropertyName, *Property->GetClass()->GetName(), Exported ? TEXT("true") : TEXT("false"),
                *Plan.ProposedValue, *Applied, IsBitfieldBool ? (BitfieldValue ? TEXT("true") : TEXT("false")) : TEXT("n/a"));
            return false;
        }
        Data->SetStringField(TEXT("component_path"), Component->GetPathName());
        Data->SetStringField(TEXT("owner_actor"), Plan.OwnerActorPath); Data->SetStringField(TEXT("property_name"), Plan.PropertyName);
        Data->SetStringField(TEXT("property_type"), Property->GetCPPType()); Data->SetStringField(TEXT("previous_value"), Plan.BeforeValue);
        Data->SetStringField(TEXT("applied_value"), Applied); Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("level_dirty"), Component->GetOwner() && Component->GetOwner()->GetLevel() &&
            Component->GetOwner()->GetLevel()->GetOutermost()->IsDirty());
        Data->SetBoolField(TEXT("undo_transaction_recorded"), true); Data->SetBoolField(TEXT("transactional_flag_added"), AddedTransactional);
        return true;
    }
    if (Command == TEXT("actor_property_edit_preview"))
    {
        FString Path, PropertyName, Proposed;
        if (Args->Values.Num() != 3 || !Args->TryGetStringField(TEXT("actor_path"), Path) || Path.IsEmpty() || Path.Len() > 512 ||
            !Args->TryGetStringField(TEXT("property_name"), PropertyName) || PropertyName.Len() > 128 ||
            !Args->TryGetStringField(TEXT("property_value"), Proposed) || Proposed.Len() > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected exact actor_path, reflected property_name and bounded property_value."));
        for (const auto& Pair : Args->Values)
            if ((Pair.Key != TEXT("actor_path") && Pair.Key != TEXT("property_name") && Pair.Key != TEXT("property_value")) ||
                !Pair.Value.IsValid() || Pair.Value->Type != EJson::String)
                return Fail(TEXT("invalid_arguments"), TEXT("Actor property preview fields must be exact strings."));
        for (int32 Index = 0; Index < PropertyName.Len(); ++Index)
        {
            const TCHAR C = PropertyName[Index];
            if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' || (Index > 0 && C >= '0' && C <= '9')))
                return Fail(TEXT("invalid_arguments"), TEXT("Property names must be exact reflected identifiers."));
        }
        AActor* Actor = Resolve(World, Path);
        if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current editor world."));
        FProperty* Property = FindFProperty<FProperty>(Actor->GetClass(), FName(*PropertyName));
        if (!IsEditableActorProperty(Actor, Property))
            return Fail(TEXT("property_not_editable"), TEXT("The exact actor property is not editor-editable or is outside the supported type set."));
        FString Before, Normalized;
        if (!ExportActorProperty(Actor, Property, Before) || !ParseActorProperty(Actor, Property, Proposed, Normalized))
            return Fail(TEXT("invalid_property_value"), TEXT("The proposed value does not match the reflected property type or contains a non-finite number."));
        if (Before == Normalized) return Fail(TEXT("no_change"), TEXT("The proposed value already matches the current property value."));
        for (auto It = PropertyEditPreviews.CreateIterator(); It; ++It)
            if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
        if (PropertyEditPreviews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired actor-property previews are allowed."));
        const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        FPropertyEditPreview Plan; Plan.Target = Actor; Plan.World = World; Plan.ActorPath = Actor->GetPathName();
        Plan.ClassPath = Actor->GetClass()->GetPathName(); Plan.PropertyName = PropertyName;
        Plan.BeforeValue = Before; Plan.ProposedValue = Normalized; Plan.Expires = FPlatformTime::Seconds() + 300.0;
        PropertyEditPreviews.Add(Id, MoveTemp(Plan));
        Data->SetStringField(TEXT("preview_id"), Id); Data->SetStringField(TEXT("actor_path"), Actor->GetPathName());
        Data->SetStringField(TEXT("class_path"), Actor->GetClass()->GetPathName());
        Data->SetStringField(TEXT("property_name"), PropertyName); Data->SetStringField(TEXT("property_type"), Property->GetCPPType());
        Data->SetStringField(TEXT("current_value"), Before); Data->SetStringField(TEXT("proposed_value"), Normalized);
        Data->SetBoolField(TEXT("saves_level"), false); Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        return true;
    }
    if (Command == TEXT("actor_property_edit_apply"))
    {
        FString Id, Confirmation;
        if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), Id) ||
            !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || Id.Len() != 32 || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must exactly match the reviewed actor-property preview ID."));
        FPropertyEditPreview* Stored = PropertyEditPreviews.Find(Id);
        if (!Stored) return Fail(TEXT("preview_not_found"), TEXT("Actor-property preview is absent, expired or already used."));
        const FPropertyEditPreview Plan = *Stored; PropertyEditPreviews.Remove(Id);
        AActor* Actor = Plan.Target.Get();
        if (Plan.Expires <= FPlatformTime::Seconds() || Plan.World.Get() != World || !IsValid(Actor) ||
            Actor->GetPathName() != Plan.ActorPath || Actor->GetClass()->GetPathName() != Plan.ClassPath)
            return Fail(TEXT("stale_preview"), TEXT("Actor identity or editor world changed; preview the edit again."));
        FProperty* Property = FindFProperty<FProperty>(Actor->GetClass(), FName(*Plan.PropertyName));
        FString Current, Normalized;
        if (!IsEditableActorProperty(Actor, Property) || !ExportActorProperty(Actor, Property, Current) ||
            Current != Plan.BeforeValue || !ParseActorProperty(Actor, Property, Plan.ProposedValue, Normalized) || Normalized != Plan.ProposedValue)
            return Fail(TEXT("stale_preview"), TEXT("Actor property changed or is no longer editable."));
        FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "EditActorProperty", "ForgeMCP Edit Actor Property"));
        const bool AddedTransactional = !Actor->HasAnyFlags(RF_Transactional);
        if (AddedTransactional) Actor->SetFlags(RF_Transactional);
        if (!Actor->Modify())
        {
            Transaction.Cancel(); if (AddedTransactional) Actor->ClearFlags(RF_Transactional);
            return Fail(TEXT("transaction_unavailable"), TEXT("Unreal could not record the actor in an Editor transaction."));
        }
        Actor->PreEditChange(Property); FOutputDeviceNull ErrorOutput;
        if (!ImportNativePropertyText(Actor, Property, Plan.ProposedValue, Actor, ErrorOutput, true))
        {
            ImportNativePropertyText(Actor, Property, Plan.BeforeValue, Actor, ErrorOutput, true);
            FPropertyChangedEvent Event(Property, EPropertyChangeType::ValueSet); Actor->PostEditChangeProperty(Event);
            Transaction.Cancel(); if (AddedTransactional) Actor->ClearFlags(RF_Transactional);
            return Fail(TEXT("property_edit_failed"), TEXT("Native property application failed; the original value was restored."));
        }
        FPropertyChangedEvent Event(Property, EPropertyChangeType::ValueSet); Actor->PostEditChangeProperty(Event);
        FString Applied;
        if (!ExportActorProperty(Actor, Property, Applied) || Applied != Plan.ProposedValue)
        {
            Actor->PreEditChange(Property);
            ImportNativePropertyText(Actor, Property, Plan.BeforeValue, Actor, ErrorOutput, true);
            FPropertyChangedEvent Rollback(Property, EPropertyChangeType::ValueSet); Actor->PostEditChangeProperty(Rollback);
            Transaction.Cancel(); if (AddedTransactional) Actor->ClearFlags(RF_Transactional);
            return Fail(TEXT("property_verification_failed"), TEXT("Applied value failed native verification; original value was restored."));
        }
        Data->SetStringField(TEXT("actor_path"), Actor->GetPathName()); Data->SetStringField(TEXT("property_name"), Plan.PropertyName);
        Data->SetStringField(TEXT("property_type"), Property->GetCPPType()); Data->SetStringField(TEXT("previous_value"), Plan.BeforeValue);
        Data->SetStringField(TEXT("applied_value"), Applied); Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("level_dirty"), Actor->GetLevel() && Actor->GetLevel()->GetOutermost()->IsDirty());
        Data->SetBoolField(TEXT("undo_transaction_recorded"), true); Data->SetBoolField(TEXT("transactional_flag_added"), AddedTransactional);
        return true;
    }
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
    if (Command == TEXT("actor_components_info"))
    {
        FString Path;
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("actor_path"), Path) ||
            Path.IsEmpty() || Path.Len() > 512)
            return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact bounded actor_path."));
        AActor* Actor = Resolve(World, Path);
        if (!Actor) return Fail(TEXT("actor_not_found"), TEXT("Actor is not loaded in the current editor world."));

        TArray<UActorComponent*> Components;
        Actor->GetComponents<UActorComponent>(Components);
        constexpr int32 MaxComponents = 128;
        TArray<TSharedPtr<FJsonValue>> Results;
        const int32 Count = FMath::Min(Components.Num(), MaxComponents);
        auto AddVector = [](const TSharedRef<FJsonObject>& Object, const TCHAR* Field, const FVector& Value)
        {
            Object->SetArrayField(Field, {MakeShared<FJsonValueNumber>(Value.X),
                MakeShared<FJsonValueNumber>(Value.Y), MakeShared<FJsonValueNumber>(Value.Z)});
        };
        for (int32 Index = 0; Index < Count; ++Index)
        {
            UActorComponent* Component = Components[Index];
            if (!IsValid(Component)) continue;
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Component->GetName());
            Item->SetStringField(TEXT("path"), Component->GetPathName());
            Item->SetStringField(TEXT("class_path"), Component->GetClass()->GetPathName());
            Item->SetBoolField(TEXT("registered"), Component->IsRegistered());
            Item->SetBoolField(TEXT("active"), Component->IsActive());
            if (USceneComponent* SceneComponent = Cast<USceneComponent>(Component))
            {
                Item->SetStringField(TEXT("attach_parent"), SceneComponent->GetAttachParent()
                    ? SceneComponent->GetAttachParent()->GetPathName() : TEXT(""));
                Item->SetBoolField(TEXT("visible"), SceneComponent->IsVisible());
                AddVector(Item, TEXT("relative_location"), SceneComponent->GetRelativeLocation());
                const FRotator RelativeRotation = SceneComponent->GetRelativeRotation();
                AddVector(Item, TEXT("relative_rotation"), FVector(RelativeRotation.Pitch,
                    RelativeRotation.Yaw, RelativeRotation.Roll));
                AddVector(Item, TEXT("relative_scale"), SceneComponent->GetRelativeScale3D());
                AddVector(Item, TEXT("world_location"), SceneComponent->GetComponentLocation());
            }
            if (UPrimitiveComponent* Primitive = Cast<UPrimitiveComponent>(Component))
            {
                const TCHAR* Mobility = Primitive->Mobility == EComponentMobility::Static ? TEXT("static") :
                    Primitive->Mobility == EComponentMobility::Stationary ? TEXT("stationary") : TEXT("movable");
                Item->SetStringField(TEXT("mobility"), Mobility);
            }
            if (UStaticMeshComponent* MeshComponent = Cast<UStaticMeshComponent>(Component))
            {
                UStaticMesh* Mesh = MeshComponent->GetStaticMesh();
                Item->SetStringField(TEXT("static_mesh"), Mesh ? Mesh->GetPathName() : TEXT(""));
            }
            Results.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetStringField(TEXT("actor_path"), Actor->GetPathName());
        Data->SetStringField(TEXT("world"), World->GetPathName());
        Data->SetNumberField(TEXT("component_count"), Components.Num());
        Data->SetBoolField(TEXT("truncated"), Components.Num() > MaxComponents);
        Data->SetArrayField(TEXT("components"), Results);
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
    const TSet<FString> Allowed{TEXT("op"),TEXT("actor_path"),TEXT("class_path"),TEXT("label"),TEXT("tags"),TEXT("location"),TEXT("rotation"),TEXT("scale"),TEXT("hidden"),TEXT("mesh_path")};
    for (const auto& Value : *Operations)
    {
        if (Value->Type != EJson::Object) return Fail(TEXT("invalid_arguments"), TEXT("Operations must be objects."));
        const auto Op = Value->AsObject().ToSharedRef();
        for (const auto& Pair : Op->Values)
        {
            if (!Allowed.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown actor operation field."));
            const EJson Type = Pair.Key == TEXT("hidden") ? EJson::Boolean
                : (Pair.Key == TEXT("location") || Pair.Key == TEXT("rotation") || Pair.Key == TEXT("scale") || Pair.Key == TEXT("tags")) ? EJson::Array : EJson::String;
            if (Pair.Value->Type != Type) return Fail(TEXT("invalid_arguments"), TEXT("Actor fields must have exact JSON types."));
        }
        FString Kind, Path, Class, Label;
        Op->TryGetStringField(TEXT("op"), Kind); Op->TryGetStringField(TEXT("actor_path"), Path);
        Op->TryGetStringField(TEXT("class_path"), Class); Op->TryGetStringField(TEXT("label"), Label);
        TArray<FName> ActorTags;
        if (!ReadActorTags(Op, ActorTags) || (Op->HasField(TEXT("tags")) && Kind != TEXT("spawn")))
            return Fail(TEXT("invalid_arguments"), TEXT("tags must be up to 16 unique nonempty strings and may only be set when spawning."));
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
        TArray<FName> ActorTags;
        if (!ReadActorTags(Op, ActorTags)) { Success = false; break; }
        ReadVector(Op, TEXT("location"), Location); ReadVector(Op, TEXT("rotation"), Rotation); ReadVector(Op, TEXT("scale"), Scale);
        if (!Actor)
        {
            FActorSpawnParameters Params; Params.ObjectFlags |= RF_Transactional;
            Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Actor = World->SpawnActor<AActor>(SpawnClass(Class), FTransform(FRotator(Rotation.X,Rotation.Y,Rotation.Z),Location,Scale), Params);
            if (!Actor) { Success = false; break; }
            Created.Add(Actor); if (!Label.IsEmpty()) Actor->SetActorLabel(Label);
            if (Op->HasField(TEXT("tags"))) Actor->Tags = ActorTags;
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
