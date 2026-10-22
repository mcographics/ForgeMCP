#include "ForgeCollisionQueries.h"

#include "CollisionQueryParams.h"
#include "Engine/CollisionProfile.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Editor.h"
#include "Components/PrimitiveComponent.h"
#include "CollisionShape.h"
#include "UObject/UObjectGlobals.h"

namespace
{
    constexpr int32 MaxBatchQueries = 32;
    constexpr int32 MaxIgnoredActors = 16;
    constexpr double MaxQueryDistanceCm = 100000.0;
    constexpr double MaxCoordinateCm = 10000000.0;
    constexpr double MaxRadiusCm = 5000.0;
    constexpr double MaxCapsuleHalfHeightCm = 10000.0;

    enum class EForgeQueryShape : uint8
    {
        Line,
        Sphere,
        Capsule
    };

    struct FForgeCollisionQuery
    {
        EForgeQueryShape Shape = EForgeQueryShape::Line;
        FVector Start = FVector::ZeroVector;
        FVector End = FVector::ZeroVector;
        ECollisionChannel Channel = ECC_Visibility;
        FName ChannelName = NAME_None;
        double RadiusCm = 0.0;
        double HalfHeightCm = 0.0;
        bool bTraceComplex = true;
        TArray<AActor*> IgnoredActors;
    };

    bool Reject(FString& OutCode, FString& OutMessage, const TCHAR* InCode, const FString& InMessage)
    {
        OutCode = InCode;
        OutMessage = InMessage;
        return false;
    }

    bool HasOnlyFields(const TSharedRef<FJsonObject>& Object, std::initializer_list<const TCHAR*> Allowed)
    {
        TSet<FString> AllowedFields;
        for (const TCHAR* Field : Allowed) AllowedFields.Add(Field);
        for (const auto& Pair : Object->Values)
            if (!AllowedFields.Contains(Pair.Key)) return false;
        return true;
    }

    bool ReadVector(const TSharedRef<FJsonObject>& Object, const TCHAR* Field, FVector& OutVector)
    {
        const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
        if (!Object->TryGetArrayField(Field, Values) || !Values || Values->Num() != 3) return false;
        double Components[3] = {0.0, 0.0, 0.0};
        for (int32 Index = 0; Index < 3; ++Index)
        {
            const TSharedPtr<FJsonValue>& Value = (*Values)[Index];
            if (!Value.IsValid() || Value->Type != EJson::Number || !Value->TryGetNumber(Components[Index]) ||
                !FMath::IsFinite(Components[Index]) || FMath::Abs(Components[Index]) > MaxCoordinateCm)
                return false;
        }
        OutVector = FVector(Components[0], Components[1], Components[2]);
        return true;
    }

    bool ReadOptionalNumber(const TSharedRef<FJsonObject>& Object, const TCHAR* Field,
        bool& bOutPresent, double& OutNumber)
    {
        const TSharedPtr<FJsonValue>* Value = Object->Values.Find(Field);
        bOutPresent = Value != nullptr;
        if (!bOutPresent) return true;
        return Value->IsValid() && (*Value)->Type == EJson::Number && (*Value)->TryGetNumber(OutNumber) &&
            FMath::IsFinite(OutNumber);
    }

    FString ResponseName(ECollisionResponse Response)
    {
        switch (Response)
        {
        case ECR_Ignore: return TEXT("Ignore");
        case ECR_Overlap: return TEXT("Overlap");
        case ECR_Block: return TEXT("Block");
        default: return TEXT("Unknown");
        }
    }

    FString CollisionEnabledName(ECollisionEnabled::Type Enabled)
    {
        switch (Enabled)
        {
        case ECollisionEnabled::NoCollision: return TEXT("NoCollision");
        case ECollisionEnabled::QueryOnly: return TEXT("QueryOnly");
        case ECollisionEnabled::PhysicsOnly: return TEXT("PhysicsOnly");
        case ECollisionEnabled::QueryAndPhysics: return TEXT("QueryAndPhysics");
        case ECollisionEnabled::ProbeOnly: return TEXT("ProbeOnly");
        case ECollisionEnabled::QueryAndProbe: return TEXT("QueryAndProbe");
        default: return TEXT("Unknown");
        }
    }

    bool ResolveTraceChannel(const FString& RequestedName, UCollisionProfile* Profile,
        ECollisionChannel& OutChannel, FName& OutName)
    {
        if (!Profile || RequestedName.IsEmpty() || RequestedName.Len() > 64) return false;
        const FName RequestedChannelName(*RequestedName);
        for (int32 ChannelIndex = 0; ChannelIndex < ECC_MAX; ++ChannelIndex)
        {
            const FName ConfiguredName = Profile->ReturnChannelNameFromContainerIndex(ChannelIndex);
            if (ConfiguredName.IsNone() || ConfiguredName != RequestedChannelName) continue;
            const ECollisionChannel Channel = static_cast<ECollisionChannel>(ChannelIndex);
            if (Profile->ConvertToTraceType(Channel) == TraceTypeQuery_MAX) return false;
            OutChannel = Channel;
            OutName = ConfiguredName;
            return true;
        }
        return false;
    }

    void AddAvailableTraceChannels(TArray<TSharedPtr<FJsonValue>>& OutValues, UCollisionProfile* Profile)
    {
        if (!Profile) return;
        for (int32 Index = 0; Index < ECC_MAX; ++Index)
        {
            const ECollisionChannel Channel = static_cast<ECollisionChannel>(Index);
            if (Profile->ConvertToTraceType(Channel) == TraceTypeQuery_MAX) continue;
            const FName Name = Profile->ReturnChannelNameFromContainerIndex(Index);
            if (!Name.IsNone()) OutValues.Add(MakeShared<FJsonValueString>(Name.ToString()));
        }
    }

    TSharedRef<FJsonObject> MakeHitResult(const FForgeCollisionQuery& Query, UWorld* World,
        const FHitResult& Hit, bool bBlockingHit, double QueryLengthCm, UCollisionProfile* Profile)
    {
        auto Result = MakeShared<FJsonObject>();
        Result->SetBoolField(TEXT("query_success"), true);
        Result->SetBoolField(TEXT("blocking_hit"), bBlockingHit);
        Result->SetBoolField(TEXT("hit_details_available"), bBlockingHit);
        Result->SetStringField(TEXT("shape"), Query.Shape == EForgeQueryShape::Line ? TEXT("line") :
            (Query.Shape == EForgeQueryShape::Sphere ? TEXT("sphere") : TEXT("capsule")));
        Result->SetStringField(TEXT("channel_name"), Query.ChannelName.ToString());
        Result->SetStringField(TEXT("world_path"), World ? World->GetPathName() : FString());
        Result->SetBoolField(TEXT("trace_complex"), Query.bTraceComplex);
        Result->SetNumberField(TEXT("query_length_cm"), QueryLengthCm);

        if (!bBlockingHit) return Result;

        Result->SetStringField(TEXT("hit_actor_path"), Hit.GetActor() ? Hit.GetActor()->GetPathName() : FString());
        Result->SetStringField(TEXT("hit_actor_name"), Hit.GetActor() ? Hit.GetActor()->GetName() : FString());
        Result->SetStringField(TEXT("hit_actor_label"), Hit.GetActor() ? Hit.GetActor()->GetActorLabel() : FString());
        Result->SetStringField(TEXT("hit_actor_class"), Hit.GetActor() ? Hit.GetActor()->GetClass()->GetPathName() : FString());
        Result->SetStringField(TEXT("hit_component_path"), Hit.GetComponent() ? Hit.GetComponent()->GetPathName() : FString());
        Result->SetStringField(TEXT("hit_component_name"), Hit.GetComponent() ? Hit.GetComponent()->GetName() : FString());
        Result->SetStringField(TEXT("hit_component_class"), Hit.GetComponent() ? Hit.GetComponent()->GetClass()->GetPathName() : FString());
        Result->SetNumberField(TEXT("hit_distance_cm"), Hit.Distance);
        Result->SetNumberField(TEXT("impact_location_x_cm"), Hit.ImpactPoint.X);
        Result->SetNumberField(TEXT("impact_location_y_cm"), Hit.ImpactPoint.Y);
        Result->SetNumberField(TEXT("impact_location_z_cm"), Hit.ImpactPoint.Z);
        Result->SetNumberField(TEXT("impact_normal_x"), Hit.ImpactNormal.X);
        Result->SetNumberField(TEXT("impact_normal_y"), Hit.ImpactNormal.Y);
        Result->SetNumberField(TEXT("impact_normal_z"), Hit.ImpactNormal.Z);

        const UPrimitiveComponent* Component = Hit.GetComponent();
        if (!IsValid(Component)) return Result;

        Result->SetStringField(TEXT("collision_enabled"), CollisionEnabledName(Component->GetCollisionEnabled()));
        Result->SetStringField(TEXT("collision_profile"), Component->GetCollisionProfileName().ToString());
        const ECollisionChannel ObjectType = Component->GetCollisionObjectType();
        const FName ObjectTypeName = Profile ? Profile->ReturnChannelNameFromContainerIndex(static_cast<int32>(ObjectType)) : NAME_None;
        Result->SetStringField(TEXT("collision_object_type"), ObjectTypeName.ToString());
        Result->SetStringField(TEXT("query_channel_response"),
            ResponseName(Component->GetCollisionResponseToChannel(Query.Channel)));

        auto Responses = MakeShared<FJsonObject>();
        const FCollisionResponseContainer& ResponseContainer = Component->GetCollisionResponseToChannels();
        if (Profile)
        {
            for (int32 Index = 0; Index < ECC_MAX; ++Index)
            {
                const FName ChannelName = Profile->ReturnChannelNameFromContainerIndex(Index);
                if (ChannelName.IsNone()) continue;
                Responses->SetStringField(ChannelName.ToString(),
                    ResponseName(ResponseContainer.GetResponse(static_cast<ECollisionChannel>(Index))));
            }
        }
        Result->SetObjectField(TEXT("collision_responses"), Responses);
        return Result;
    }
}

bool FForgeCollisionQueries::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message) const
{
    if (Command != TEXT("collision_query"))
        return Reject(Code, Message, TEXT("unsupported_command"), TEXT("Unsupported collision query command."));
    if (!IsInGameThread())
        return Reject(Code, Message, TEXT("wrong_thread"), TEXT("Collision queries must run on the editor game thread."));
    if (!GEditor)
        return Reject(Code, Message, TEXT("no_editor"), TEXT("The Unreal Editor context is unavailable."));
    if (GEditor->PlayWorld || GEditor->bIsSimulatingInEditor)
        return Reject(Code, Message, TEXT("pie_not_allowed"), TEXT("Collision queries are disabled during PIE and Simulate."));

    UWorld* World = GEditor->GetEditorWorldContext().World();
    if (!IsValid(World) || (World->WorldType != EWorldType::Editor && World->WorldType != EWorldType::EditorPreview))
        return Reject(Code, Message, TEXT("no_editor_world"), TEXT("No active editor world is available for collision queries."));

    if (!HasOnlyFields(Args, { TEXT("request") }))
        return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("collision_query accepts only a request object."));
    const TSharedPtr<FJsonObject>* RequestField = nullptr;
    if (!Args->TryGetObjectField(TEXT("request"), RequestField) || !RequestField || !RequestField->IsValid())
        return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("request must be an object."));
    const TSharedRef<FJsonObject> Request = RequestField->ToSharedRef();
    if (!HasOnlyFields(Request, { TEXT("queries"), TEXT("max_query_distance_cm") }))
        return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("request contains unsupported fields."));

    double MaxDistanceCm = 0.0;
    if (!Request->TryGetNumberField(TEXT("max_query_distance_cm"), MaxDistanceCm) ||
        !FMath::IsFinite(MaxDistanceCm) || MaxDistanceCm <= 0.0 || MaxDistanceCm > MaxQueryDistanceCm)
        return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("max_query_distance_cm must be greater than 0 and no more than 100000 cm."));

    const TArray<TSharedPtr<FJsonValue>>* QueryValues = nullptr;
    if (!Request->TryGetArrayField(TEXT("queries"), QueryValues) || !QueryValues ||
        QueryValues->Num() < 1 || QueryValues->Num() > MaxBatchQueries)
        return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("queries must contain from 1 to 32 entries."));

    UCollisionProfile* CollisionProfile = UCollisionProfile::Get();
    if (!CollisionProfile)
        return Reject(Code, Message, TEXT("collision_profile_unavailable"), TEXT("Unreal collision channel configuration is unavailable."));

    TArray<FForgeCollisionQuery> Queries;
    Queries.Reserve(QueryValues->Num());
    for (int32 QueryIndex = 0; QueryIndex < QueryValues->Num(); ++QueryIndex)
    {
        const TSharedPtr<FJsonValue>& QueryValue = (*QueryValues)[QueryIndex];
        if (!QueryValue.IsValid() || QueryValue->Type != EJson::Object)
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Each query must be an object."));
        const TSharedRef<FJsonObject> QueryObject = QueryValue->AsObject().ToSharedRef();
        if (!HasOnlyFields(QueryObject, { TEXT("shape"), TEXT("start_cm"), TEXT("end_cm"), TEXT("channel_name"),
                TEXT("radius_cm"), TEXT("half_height_cm"), TEXT("trace_complex"), TEXT("ignored_actor_paths") }))
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("A query contains unsupported fields."));

        FForgeCollisionQuery Query;
        FString ShapeName, ChannelNameString;
        if (!QueryObject->TryGetStringField(TEXT("shape"), ShapeName) ||
            !QueryObject->TryGetStringField(TEXT("channel_name"), ChannelNameString) ||
            !ReadVector(QueryObject, TEXT("start_cm"), Query.Start) || !ReadVector(QueryObject, TEXT("end_cm"), Query.End))
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Each query requires a supported shape, finite 3D start_cm/end_cm coordinates, and channel_name."));

        if (ShapeName == TEXT("line")) Query.Shape = EForgeQueryShape::Line;
        else if (ShapeName == TEXT("sphere")) Query.Shape = EForgeQueryShape::Sphere;
        else if (ShapeName == TEXT("capsule")) Query.Shape = EForgeQueryShape::Capsule;
        else return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("shape must be line, sphere, or capsule."));

        if (!ResolveTraceChannel(ChannelNameString, CollisionProfile, Query.Channel, Query.ChannelName))
            return Reject(Code, Message, TEXT("invalid_channel"), FString::Printf(
                TEXT("channel_name '%s' is not an active Unreal trace channel."), *ChannelNameString));

        bool bHasRadius = false, bHasHalfHeight = false;
        if (!ReadOptionalNumber(QueryObject, TEXT("radius_cm"), bHasRadius, Query.RadiusCm) ||
            !ReadOptionalNumber(QueryObject, TEXT("half_height_cm"), bHasHalfHeight, Query.HalfHeightCm))
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Sweep dimensions must be finite numbers."));

        if ((Query.Shape == EForgeQueryShape::Line && (bHasRadius || bHasHalfHeight)) ||
            (Query.Shape == EForgeQueryShape::Sphere && (!bHasRadius || bHasHalfHeight)) ||
            (Query.Shape == EForgeQueryShape::Capsule && (!bHasRadius || !bHasHalfHeight)))
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Sweep dimensions do not match the requested shape."));
        if ((bHasRadius && (Query.RadiusCm <= 0.0 || Query.RadiusCm > MaxRadiusCm)) ||
            (bHasHalfHeight && (Query.HalfHeightCm <= 0.0 || Query.HalfHeightCm > MaxCapsuleHalfHeightCm)) ||
            (Query.Shape == EForgeQueryShape::Capsule && Query.HalfHeightCm < Query.RadiusCm))
            return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Sweep dimensions exceed their positive bounded ranges."));

        const TSharedPtr<FJsonValue>* TraceComplexValue = QueryObject->Values.Find(TEXT("trace_complex"));
        if (TraceComplexValue)
        {
            if (!TraceComplexValue->IsValid() || (*TraceComplexValue)->Type != EJson::Boolean ||
                !(*TraceComplexValue)->TryGetBool(Query.bTraceComplex))
                return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("trace_complex must be a boolean."));
        }

        const double QueryLengthCm = FVector::Distance(Query.Start, Query.End);
        if (!FMath::IsFinite(QueryLengthCm) || QueryLengthCm > MaxDistanceCm)
            return Reject(Code, Message, TEXT("query_too_long"), TEXT("A query segment exceeds max_query_distance_cm."));

        const TSharedPtr<FJsonValue>* IgnoredValue = QueryObject->Values.Find(TEXT("ignored_actor_paths"));
        if (IgnoredValue)
        {
            if (!IgnoredValue->IsValid() || (*IgnoredValue)->Type != EJson::Array)
                return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("ignored_actor_paths must be an array of loaded actor paths."));
            const TArray<TSharedPtr<FJsonValue>>& Paths = (*IgnoredValue)->AsArray();
            if (Paths.Num() > MaxIgnoredActors)
                return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("ignored_actor_paths is limited to 16 loaded actors."));
            TSet<FString> SeenPaths;
            for (const TSharedPtr<FJsonValue>& PathValue : Paths)
            {
                FString ActorPath;
                if (!PathValue.IsValid() || PathValue->Type != EJson::String || !PathValue->TryGetString(ActorPath) ||
                    ActorPath.IsEmpty() || ActorPath.Len() > 512 || SeenPaths.Contains(ActorPath))
                    return Reject(Code, Message, TEXT("invalid_arguments"), TEXT("Ignored actor paths must be unique, nonempty exact paths up to 512 characters."));
                SeenPaths.Add(ActorPath);
                AActor* FoundActor = FindObject<AActor>(nullptr, *ActorPath);
                if (!IsValid(FoundActor) || FoundActor->GetWorld() != World)
                    return Reject(Code, Message, TEXT("actor_not_loaded"), FString::Printf(
                        TEXT("Ignored actor '%s' is not loaded in the active editor world."), *ActorPath));
                Query.IgnoredActors.Add(FoundActor);
            }
        }
        Queries.Add(MoveTemp(Query));
    }

    TArray<TSharedPtr<FJsonValue>> Results;
    Results.Reserve(Queries.Num());
    for (const FForgeCollisionQuery& Query : Queries)
    {
        FCollisionQueryParams Params(FName(TEXT("ForgeMCPReadOnlyCollisionQuery")), Query.bTraceComplex);
        for (AActor* IgnoredActor : Query.IgnoredActors) Params.AddIgnoredActor(IgnoredActor);

        FHitResult Hit;
        bool bBlockingHit = false;
        if (Query.Shape == EForgeQueryShape::Line)
        {
            bBlockingHit = World->LineTraceSingleByChannel(Hit, Query.Start, Query.End, Query.Channel, Params);
        }
        else
        {
            const FCollisionShape Shape = Query.Shape == EForgeQueryShape::Sphere
                ? FCollisionShape::MakeSphere(Query.RadiusCm)
                : FCollisionShape::MakeCapsule(Query.RadiusCm, Query.HalfHeightCm);
            bBlockingHit = World->SweepSingleByChannel(Hit, Query.Start, Query.End, FQuat::Identity,
                Query.Channel, Shape, Params);
        }
        bBlockingHit = bBlockingHit && Hit.bBlockingHit;
        Results.Add(MakeShared<FJsonValueObject>(MakeHitResult(Query, World, Hit, bBlockingHit,
            FVector::Distance(Query.Start, Query.End), CollisionProfile)));
    }

    TArray<TSharedPtr<FJsonValue>> AvailableChannels;
    AddAvailableTraceChannels(AvailableChannels, CollisionProfile);
    Data->SetBoolField(TEXT("query_success"), true);
    Data->SetNumberField(TEXT("query_count"), Results.Num());
    Data->SetStringField(TEXT("world_path"), World->GetPathName());
    Data->SetNumberField(TEXT("max_query_distance_cm"), MaxDistanceCm);
    Data->SetArrayField(TEXT("available_trace_channels"), AvailableChannels);
    Data->SetArrayField(TEXT("results"), Results);
    return true;
}
