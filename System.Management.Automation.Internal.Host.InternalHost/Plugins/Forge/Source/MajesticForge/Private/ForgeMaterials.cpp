// SPDX-License-Identifier: MIT
#include "ForgeMaterials.h"
#include "ForgeMaterialValidationState.h"
#include "ForgeMaterialDevelopmentPolicy.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "Editor.h"
#include "Engine/BlendableInterface.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "MaterialEditingLibrary.h"
#include "MaterialDomain.h"
#include "MaterialShared.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionAdd.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Materials/MaterialExpressionConstant3Vector.h"
#include "Materials/MaterialExpressionComment.h"
#include "Materials/MaterialExpressionMultiply.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionSceneTexture.h"
#include "Materials/MaterialExpressionSubtract.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "Misc/App.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "ShaderCompiler.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"
#include "UnrealEngine.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;
using JArray = TArray<TSharedPtr<FJsonValue>>;

FString Text(const JObject& O, const TCHAR* Key)
{
    FString V; O->TryGetStringField(Key, V); return V;
}

FString Json(const JObject& O)
{
    FString V;
    FJsonSerializer::Serialize(O, TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&V));
    return V;
}

bool Fields(const JObject& O, std::initializer_list<const TCHAR*> Allowed)
{
    for (const auto& Field : O->Values)
    {
        bool Found = false;
        for (const TCHAR* Key : Allowed) if (Field.Key == Key) Found = true;
        if (!Found || !Field.Value.IsValid()) return false;
    }
    return true;
}

bool Identifier(const FString& V, bool bDigitStart = false)
{
    if (V.IsEmpty() || V.Len() > 64) return false;
    for (int32 I = 0; I < V.Len(); ++I)
    {
        const TCHAR C = V[I];
        if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
            ((I > 0 || bDigitStart) && C >= '0' && C <= '9'))) return false;
    }
    return true;
}

bool Path(const FString& V)
{
    if (V.Len() > 240 || !(V.StartsWith(TEXT("/Game/")) || V.StartsWith(TEXT("/JasperPrism/"))) ||
        !FPackageName::IsValidLongPackageName(V)) return false;
    TArray<FString> Parts; V.ParseIntoArray(Parts, TEXT("/"), false);
    for (int32 I = 1; I < Parts.Num(); ++I) if (!Identifier(Parts[I])) return false;
    FString Filename;
    return FPackageName::TryConvertLongPackageNameToFilename(V, Filename, FPackageName::GetAssetPackageExtension());
}

FString ObjectPath(const FString& V) { return V + TEXT(".") + FPackageName::GetLongPackageAssetName(V); }

UClass* ExpressionClass(const FString& Type)
{
    if (Type == TEXT("SceneTexture")) return UMaterialExpressionSceneTexture::StaticClass();
    if (Type == TEXT("Subtract")) return UMaterialExpressionSubtract::StaticClass();
    if (Type == TEXT("Multiply")) return UMaterialExpressionMultiply::StaticClass();
    if (Type == TEXT("Add")) return UMaterialExpressionAdd::StaticClass();
    if (Type == TEXT("Constant")) return UMaterialExpressionConstant::StaticClass();
    if (Type == TEXT("Constant3Vector")) return UMaterialExpressionConstant3Vector::StaticClass();
    if (Type == TEXT("ScalarParameter")) return UMaterialExpressionScalarParameter::StaticClass();
    if (Type == TEXT("VectorParameter")) return UMaterialExpressionVectorParameter::StaticClass();
    return nullptr;
}

bool Parameters(const JObject& P, UClass* Class)
{
    if (!Class || P->Values.Num() > 2) return false;
    for (const auto& Pair : P->Values)
    {
        const FString& K = Pair.Key;
        const auto& V = Pair.Value;
        if (!V.IsValid()) return false;
        if (Class == UMaterialExpressionSceneTexture::StaticClass())
        {
            if (K == TEXT("scene_texture_id") && V->Type == EJson::String && V->AsString() == TEXT("PostProcessInput0")) continue;
            if (K == TEXT("filtered") && V->Type == EJson::Boolean) continue;
            return false;
        }
        if (Class == UMaterialExpressionScalarParameter::StaticClass() || Class == UMaterialExpressionVectorParameter::StaticClass())
        {
            if (K == TEXT("parameter_name") && V->Type == EJson::String && Identifier(V->AsString())) continue;
            if (K != TEXT("default_value")) return false;
        }
        else if (Class == UMaterialExpressionConstant::StaticClass() || Class == UMaterialExpressionConstant3Vector::StaticClass())
        { if (K != TEXT("value")) return false; }
        else if (K != TEXT("const_a") && K != TEXT("const_b")) return false;
        if (Class == UMaterialExpressionConstant3Vector::StaticClass() || Class == UMaterialExpressionVectorParameter::StaticClass())
        {
            if (V->Type != EJson::Array || V->AsArray().Num() != (Class == UMaterialExpressionConstant3Vector::StaticClass() ? 3 : 4)) return false;
            for (const auto& C : V->AsArray())
            {
                double N;
                if (!C.IsValid() || C->Type != EJson::Number || !C->TryGetNumber(N) || !FMath::IsFinite(N) || FMath::Abs(N) > 1000000) return false;
            }
        }
        else
        {
            double N;
            if (V->Type != EJson::Number || !V->TryGetNumber(N) || !FMath::IsFinite(N) || FMath::Abs(N) > 1000000) return false;
        }
    }
    return true;
}

void SetParameters(UMaterialExpression* E, const JObject& P)
{
    if (auto* N = Cast<UMaterialExpressionSceneTexture>(E))
    {
        N->SceneTextureId = PPI_PostProcessInput0;
        if (P->HasField(TEXT("filtered"))) N->bFiltered = P->GetBoolField(TEXT("filtered"));
    }
    for (const auto& Pair : P->Values)
    {
        const FString& K = Pair.Key;
        if (K == TEXT("scene_texture_id") || K == TEXT("filtered")) continue;
        if (K == TEXT("parameter_name"))
        {
            if (auto* N = Cast<UMaterialExpressionScalarParameter>(E)) N->ParameterName = *Pair.Value->AsString();
            if (auto* N = Cast<UMaterialExpressionVectorParameter>(E)) N->ParameterName = *Pair.Value->AsString();
        }
        else if (Pair.Value->Type == EJson::Array)
        {
            const auto& C = Pair.Value->AsArray();
            FLinearColor Color(C[0]->AsNumber(), C[1]->AsNumber(), C[2]->AsNumber(), C.Num() == 4 ? C[3]->AsNumber() : 1);
            if (auto* N = Cast<UMaterialExpressionConstant3Vector>(E)) N->Constant = Color;
            if (auto* N = Cast<UMaterialExpressionVectorParameter>(E)) N->DefaultValue = Color;
        }
        else
        {
            const float Value = Pair.Value->AsNumber();
            if (auto* N = Cast<UMaterialExpressionConstant>(E)) N->R = Value;
            if (auto* N = Cast<UMaterialExpressionScalarParameter>(E)) N->DefaultValue = Value;
            if (auto* N = Cast<UMaterialExpressionSubtract>(E)) { if (K == TEXT("const_a")) N->ConstA = Value; else N->ConstB = Value; }
            if (auto* N = Cast<UMaterialExpressionMultiply>(E)) { if (K == TEXT("const_a")) N->ConstA = Value; else N->ConstB = Value; }
            if (auto* N = Cast<UMaterialExpressionAdd>(E)) { if (K == TEXT("const_a")) N->ConstA = Value; else N->ConstB = Value; }
        }
    }
}

JObject GetParameters(UMaterialExpression* E)
{
    auto P = MakeShared<FJsonObject>();
    if (auto* N = Cast<UMaterialExpressionSceneTexture>(E))
    {
        P->SetStringField(TEXT("scene_texture_id"), N->SceneTextureId == PPI_PostProcessInput0 ? TEXT("PostProcessInput0") : TEXT("Unsupported"));
        P->SetNumberField(TEXT("scene_texture_id_native"), N->SceneTextureId);
        P->SetBoolField(TEXT("filtered"), N->bFiltered);
    }
    if (auto* N = Cast<UMaterialExpressionConstant>(E)) P->SetNumberField(TEXT("value"), N->R);
    if (auto* N = Cast<UMaterialExpressionSubtract>(E)) { P->SetNumberField(TEXT("const_a"), N->ConstA); P->SetNumberField(TEXT("const_b"), N->ConstB); }
    if (auto* N = Cast<UMaterialExpressionMultiply>(E)) { P->SetNumberField(TEXT("const_a"), N->ConstA); P->SetNumberField(TEXT("const_b"), N->ConstB); }
    if (auto* N = Cast<UMaterialExpressionAdd>(E)) { P->SetNumberField(TEXT("const_a"), N->ConstA); P->SetNumberField(TEXT("const_b"), N->ConstB); }
    if (auto* N = Cast<UMaterialExpressionScalarParameter>(E))
    { P->SetStringField(TEXT("parameter_name"), N->ParameterName.ToString()); P->SetNumberField(TEXT("default_value"), N->DefaultValue); }
    auto Color = [&](const TCHAR* Key, const FLinearColor& C, bool Alpha)
    {
        JArray A = {MakeShared<FJsonValueNumber>(C.R), MakeShared<FJsonValueNumber>(C.G), MakeShared<FJsonValueNumber>(C.B)};
        if (Alpha) A.Add(MakeShared<FJsonValueNumber>(C.A));
        P->SetArrayField(Key, A);
    };
    if (auto* N = Cast<UMaterialExpressionConstant3Vector>(E)) Color(TEXT("value"), N->Constant, false);
    if (auto* N = Cast<UMaterialExpressionVectorParameter>(E))
    { P->SetStringField(TEXT("parameter_name"), N->ParameterName.ToString()); Color(TEXT("default_value"), N->DefaultValue, true); }
    return P;
}

FString Id(UMaterialExpression* E) { return E ? E->MaterialExpressionGuid.ToString(EGuidFormats::Digits) : FString(); }

int32 Output(UMaterialExpression* E, const FString& Name)
{
    auto& Outputs = E->GetOutputs();
    if (Name.IsEmpty()) return Outputs.Num() ? 0 : INDEX_NONE;
    // SceneTexture output zero is unnamed in native 5.6; expose an explicit Color alias.
    if (E->GetClass() == UMaterialExpressionSceneTexture::StaticClass() && Name == TEXT("Color")) return 0;
    for (int32 I = 0; I < Outputs.Num(); ++I)
    {
        const auto& P = Outputs[I];
        if (!P.OutputName.IsNone() && P.OutputName.ToString() == Name) return I;
        if (P.OutputName.IsNone())
        {
            if (Name == TEXT("R") && P.MaskR && !P.MaskG && !P.MaskB && !P.MaskA) return I;
            if (Name == TEXT("G") && !P.MaskR && P.MaskG && !P.MaskB && !P.MaskA) return I;
            if (Name == TEXT("B") && !P.MaskR && !P.MaskG && P.MaskB && !P.MaskA) return I;
            if (Name == TEXT("A") && !P.MaskR && !P.MaskG && !P.MaskB && P.MaskA) return I;
            if (Name == TEXT("RGB") && P.MaskR && P.MaskG && P.MaskB && !P.MaskA) return I;
        }
    }
    return INDEX_NONE;
}

FString NativeOutput(UMaterialExpression* E, const FString& Name)
{
    return E->GetClass() == UMaterialExpressionSceneTexture::StaticClass() && Name == TEXT("Color") ? FString() : Name;
}

FExpressionInput* Input(UMaterialExpression* E, const FString& Name)
{
    for (int32 I = 0; FExpressionInput* Pin = E->GetInput(I); ++I)
        if (E->GetInputName(I).ToString() == Name) return Pin;
    return nullptr;
}

JObject Connection(const FExpressionInput* Pin)
{
    auto O = MakeShared<FJsonObject>();
    O->SetBoolField(TEXT("connected"), Pin && Pin->Expression != nullptr);
    if (Pin && Pin->Expression)
    {
        O->SetStringField(TEXT("from_node"), Id(Pin->Expression));
        O->SetNumberField(TEXT("output_index"), Pin->OutputIndex);
        auto& Outputs = Pin->Expression->GetOutputs();
        O->SetStringField(TEXT("output_name"), Outputs.IsValidIndex(Pin->OutputIndex) ? Outputs[Pin->OutputIndex].OutputName.ToString() : TEXT("Invalid"));
        O->SetNumberField(TEXT("mask"), Pin->Mask);
        O->SetNumberField(TEXT("mask_r"), Pin->MaskR); O->SetNumberField(TEXT("mask_g"), Pin->MaskG);
        O->SetNumberField(TEXT("mask_b"), Pin->MaskB); O->SetNumberField(TEXT("mask_a"), Pin->MaskA);
    }
    return O;
}

// Export editable values for all expression classes, but never import arbitrary properties.
// This makes stale-preview detection cover values on unsupported nodes as well.
JObject EditableValues(UObject* E)
{
    auto O = MakeShared<FJsonObject>();
    for (TFieldIterator<FProperty> It(E->GetClass()); It; ++It)
    {
        if (!It->HasAnyPropertyFlags(CPF_Edit) || It->HasAnyPropertyFlags(CPF_Transient)) continue;
        FString Value;
        It->ExportText_InContainer(0, Value, E, E, E, PPF_None);
        O->SetStringField(It->GetName(), Value);
    }
    return O;
}

JObject Inspect(UMaterial* M)
{
    auto O = MakeShared<FJsonObject>();
    O->SetStringField(TEXT("asset_path"), M->GetOutermost()->GetName());
    O->SetStringField(TEXT("object_path"), M->GetPathName());
    O->SetStringField(TEXT("state_id"), M->StateId.ToString());
    O->SetBoolField(TEXT("dirty"), M->GetOutermost()->IsDirty());
    O->SetStringField(TEXT("domain"), M->MaterialDomain == MD_PostProcess ? TEXT("PostProcess") : TEXT("Other"));
    O->SetStringField(TEXT("blendable_location"), M->BlendableLocation == BL_SceneColorAfterTonemapping ? TEXT("SceneColorAfterTonemapping") : TEXT("Other"));
    O->SetObjectField(TEXT("material_settings"), EditableValues(M));
    JArray Nodes;
    for (UMaterialExpression* E : M->GetExpressions())
    {
        if (!E) continue;
        auto N = MakeShared<FJsonObject>();
        N->SetStringField(TEXT("node_id"), Id(E)); N->SetStringField(TEXT("class_path"), E->GetClass()->GetPathName());
        N->SetStringField(TEXT("object_path"), E->GetPathName());
        N->SetNumberField(TEXT("x"), E->MaterialExpressionEditorX); N->SetNumberField(TEXT("y"), E->MaterialExpressionEditorY);
        N->SetObjectField(TEXT("parameters"), GetParameters(E));
        N->SetObjectField(TEXT("editable_values"), EditableValues(E));
        JArray Inputs, Outputs;
        for (int32 I = 0; FExpressionInput* Pin = E->GetInput(I); ++I)
        {
            auto P = Connection(Pin);
            P->SetStringField(TEXT("name"), E->GetInputName(I).ToString());
            P->SetNumberField(TEXT("index"), I); Inputs.Add(MakeShared<FJsonValueObject>(P));
        }
        auto& Pins = E->GetOutputs();
        for (int32 I = 0; I < Pins.Num(); ++I)
        {
            auto P = MakeShared<FJsonObject>(); P->SetNumberField(TEXT("index"), I);
            P->SetStringField(TEXT("name"), Pins[I].OutputName.ToString());
            if (I == 0 && E->GetClass() == UMaterialExpressionSceneTexture::StaticClass()) P->SetStringField(TEXT("alias"), TEXT("Color"));
            P->SetNumberField(TEXT("mask"), Pins[I].Mask);
            P->SetNumberField(TEXT("mask_r"), Pins[I].MaskR); P->SetNumberField(TEXT("mask_g"), Pins[I].MaskG);
            P->SetNumberField(TEXT("mask_b"), Pins[I].MaskB); P->SetNumberField(TEXT("mask_a"), Pins[I].MaskA);
            Outputs.Add(MakeShared<FJsonValueObject>(P));
        }
        N->SetArrayField(TEXT("inputs"), Inputs); N->SetArrayField(TEXT("outputs"), Outputs);
        Nodes.Add(MakeShared<FJsonValueObject>(N));
    }
    O->SetArrayField(TEXT("nodes"), Nodes);
    JArray Comments;
    for (UMaterialExpressionComment* E : M->GetEditorComments())
    {
        if (!E) continue;
        auto C = MakeShared<FJsonObject>(); C->SetStringField(TEXT("object_path"), E->GetPathName());
        C->SetNumberField(TEXT("x"), E->MaterialExpressionEditorX); C->SetNumberField(TEXT("y"), E->MaterialExpressionEditorY);
        C->SetObjectField(TEXT("editable_values"), EditableValues(E));
        Comments.Add(MakeShared<FJsonValueObject>(C));
    }
    O->SetArrayField(TEXT("comments"), Comments);
    JArray Props;
    const UEnum* Enum = StaticEnum<EMaterialProperty>();
    for (int32 I = 0; I < MP_MAX; ++I)
    {
        auto* Pin = M->GetExpressionInputForProperty(static_cast<EMaterialProperty>(I));
        if (!Pin) continue;
        auto P = Connection(Pin); P->SetStringField(TEXT("property"), Enum->GetNameStringByValue(I));
        Props.Add(MakeShared<FJsonValueObject>(P));
    }
    O->SetArrayField(TEXT("property_inputs"), Props);
    O->SetBoolField(TEXT("truncated"), false);
    return O;
}

FString Fingerprint(UMaterial* M)
{
    auto O = Inspect(M);
    return Json(O);
}

bool Arrays(const JObject& O, const TCHAR* Key, int32 Max, JArray& Out)
{
    const JArray* A = nullptr;
    if (!O->TryGetArrayField(Key, A) || A->Num() > Max) return false;
    for (const auto& V : *A) if (!V.IsValid() || V->Type != EJson::Object) return false;
    Out = *A; return true;
}

ForgeMaterialValidation::EState ShaderState(UMaterial* M, EMaterialQualityLevel::Type Quality,
    const JObject& Data, bool DeadlineReached = false, bool SubmitDeferredJobs = false,
    const FMaterialShaderMap* CompletedMap = nullptr)
{
    using namespace ForgeMaterialValidation;
    FSnapshot S;
    const bool GameThread = IsInGameThread();
    const bool CanRender = FApp::CanEverRender();
    const bool HasCompiler = GShaderCompilingManager != nullptr;
    const bool Skipped = HasCompiler && GShaderCompilingManager->IsShaderCompilationSkipped();
    S.Available = GameThread && CanRender && HasCompiler && !Skipped;
    auto* Resource = GameThread ? M->GetMaterialResource(GMaxRHIFeatureLevel, Quality) : nullptr;
    S.HasResource = Resource != nullptr;
    // This poll completes an async DDC lookup only after it is ready. It is not
    // proof of success and does not itself submit deferred material shader jobs.
    bool WorkFinished = S.Available && Resource && Resource->IsCompilationFinished();
    if (SubmitDeferredJobs && S.Available && Resource)
    {
        // The public submission API safely handles a missing/previously submitted
        // compiling map internally. The resource's compiling ID is protected.
        Resource->SubmitCompileJobs_GameThread(EShaderCompileJobPriority::High);
        Data->SetBoolField(TEXT("deferred_submission_attempted"), true);
        // Preserve a pending DDC observation for this iteration; a ready lookup
        // is completed and its deferred work submitted on the following poll.
        if (WorkFinished) WorkFinished = Resource->IsCompilationFinished();
    }
    auto* Map = Resource ? Resource->GetGameThreadShaderMap() : nullptr;
    const uint32 MapId = Map ? Map->GetCompilingId() : 0;
    const bool JobsPending = HasCompiler && MapId && GShaderCompilingManager->IsCompilingShaderMap(MapId);
    S.Pending = Resource && (!WorkFinished || JobsPending);
    JArray Errors;
    if (Resource) for (const FString& E : Resource->GetCompileErrors()) Errors.Add(MakeShared<FJsonValueString>(E));
    S.HasErrors = !Errors.IsEmpty();
    S.HasMap = Map != nullptr;
    S.Finalized = Map && Map->IsCompilationFinalized();
    S.Successful = Map && Map->CompiledSuccessfully();
    S.Complete = Resource && Resource->IsGameThreadShaderMapComplete();
    S.HasShaders = Map && Map->GetShaderNum() > 0;
    const bool MaterialMapDDC = IsMaterialMapDDCEnabled();
    const bool RequiredComplete = Resource && Resource->IsRequiredComplete();
    S.LazyShaderJobMode = !MaterialMapDDC && !RequiredComplete;
    if (Resource && Map)
    {
        FMaterialShaderMapId ExpectedId;
        const EShaderPlatform Platform = GShaderPlatformForFeatureLevel[GMaxRHIFeatureLevel];
        Resource->GetShaderMapId(Platform, nullptr, ExpectedId);
        S.MapIdentityMatches = Map->GetShaderPlatform() == Platform && Map->GetShaderMapId() == ExpectedId;
    }
    S.CompletionObserved = Map && Map == CompletedMap;
    const EState State = Classify(S, DeadlineReached);
    FString Reason;
    if (S.HasErrors) Reason = TEXT("compiler_errors");
    else if (!GameThread) Reason = TEXT("game_thread_required");
    else if (!CanRender) Reason = TEXT("rendering_unavailable");
    else if (!HasCompiler) Reason = TEXT("shader_compiler_unavailable");
    else if (Skipped) Reason = TEXT("shader_compilation_skipped");
    else if (!Resource) Reason = TEXT("material_resource_missing");
    else if (State == EState::TimedOut) Reason = TEXT("shader_validation_deadline");
    else if (State == EState::Pending) Reason = S.Pending ? TEXT("shader_cache_or_jobs_pending") : TEXT("shader_map_finalization_evidence_pending");
    else if (!Map) Reason = TEXT("shader_map_missing");
    else if (!S.MapIdentityMatches) Reason = TEXT("shader_map_identity_mismatch");
    else if (State == EState::Failed) Reason = TEXT("shader_map_compilation_failed");
    else if (State == EState::Succeeded && !S.Finalized) Reason = TEXT("validated_lazy_shader_job_result");
    else if (!S.Finalized) Reason = TEXT("shader_map_not_finalized_without_pending_work");
    else if (!S.Complete || !S.HasShaders) Reason = TEXT("shader_map_incomplete_without_pending_work");
    else Reason = TEXT("complete_shader_map");
    Data->SetArrayField(TEXT("compiler_errors"), Errors);
    Data->SetBoolField(TEXT("compiled"), State == EState::Succeeded);
    Data->SetStringField(TEXT("compile_scope"), TEXT("Active editor RHI feature level and material quality; not all cooking platforms."));
    Data->SetStringField(TEXT("compile_state"), UTF8_TO_TCHAR(Name(State)));
    Data->SetStringField(TEXT("compile_reason"), Reason);
    auto Diagnostics = MakeShared<FJsonObject>();
    Diagnostics->SetBoolField(TEXT("game_thread"), GameThread);
    Diagnostics->SetBoolField(TEXT("can_render"), CanRender);
    Diagnostics->SetBoolField(TEXT("compiler_available"), HasCompiler);
    Diagnostics->SetBoolField(TEXT("compilation_skipped"), Skipped);
    Diagnostics->SetNumberField(TEXT("feature_level"), static_cast<int32>(GMaxRHIFeatureLevel));
    Diagnostics->SetNumberField(TEXT("requested_quality_level"), static_cast<int32>(Quality));
    if (Resource) Diagnostics->SetNumberField(TEXT("resource_quality_level"), static_cast<int32>(Resource->GetQualityLevel()));
    Diagnostics->SetBoolField(TEXT("resource_present"), S.HasResource);
    Diagnostics->SetBoolField(TEXT("cache_and_jobs_finished"), WorkFinished);
    Diagnostics->SetNumberField(TEXT("shader_map_compiling_id"), MapId);
    Diagnostics->SetBoolField(TEXT("manager_jobs_pending"), JobsPending);
    Diagnostics->SetBoolField(TEXT("shader_map_present"), S.HasMap);
    Diagnostics->SetBoolField(TEXT("shader_map_finalized"), S.Finalized);
    Diagnostics->SetBoolField(TEXT("shader_map_successful"), S.Successful);
    Diagnostics->SetBoolField(TEXT("shader_map_complete"), S.Complete);
    Diagnostics->SetNumberField(TEXT("shader_count"), Map ? Map->GetShaderNum() : 0);
    Diagnostics->SetBoolField(TEXT("material_map_ddc_enabled"), MaterialMapDDC);
    Diagnostics->SetBoolField(TEXT("resource_requires_complete_map"), RequiredComplete);
    Diagnostics->SetBoolField(TEXT("lazy_shader_job_mode"), S.LazyShaderJobMode);
    Diagnostics->SetBoolField(TEXT("shader_map_identity_matches"), S.MapIdentityMatches);
    Diagnostics->SetBoolField(TEXT("completion_event_observed_for_map"), S.CompletionObserved);
    Data->SetObjectField(TEXT("compile_diagnostics"), Diagnostics);
    return State;
}

bool Compile(UMaterial* M, const JObject& Data, double WaitBudgetSeconds = 45.0,
    TRefCountPtr<FMaterialShaderMap>* SuccessfulMapEvidence = nullptr)
{
    using namespace ForgeMaterialValidation;
    const double Started = FPlatformTime::Seconds();
    const auto Quality = static_cast<EMaterialQualityLevel::Type>(GetCachedScalabilityCVars().MaterialQualityLevel);
    TRefCountPtr<FMaterialShaderMap> CompletedMap;
    // Subscribe before recompile so even synchronous engine result propagation is
    // observed. Failure notifications have null/error maps and never establish proof.
    const FDelegateHandle CompletionHandle = UMaterial::OnMaterialCompilationFinished().AddLambda(
        [M, Quality, &CompletedMap](UMaterialInterface* Finished)
        {
            if (Finished != M || !IsInGameThread() || !GShaderCompilingManager) return;
            auto* Resource = M->GetMaterialResource(GMaxRHIFeatureLevel, Quality);
            if (Resource && Resource->IsCompilationFinished() && Resource->GetCompileErrors().IsEmpty() &&
                Resource->IsGameThreadShaderMapComplete())
            {
                CompletedMap = Resource->GetGameThreadShaderMap();
            }
        });
    if (IsInGameThread()) UMaterialEditingLibrary::RecompileMaterial(M);
    JArray States;
    EState State;
    FString Previous;
    Data->SetBoolField(TEXT("deferred_submission_attempted"), false);
    do
    {
        // PostEditChange uses PrecompileMode::None in UE 5.6.1. FinishCompilation
        // cannot wait for jobs that were never submitted. Poll DDC readiness first,
        // then explicitly submit this resource's deferred jobs at editor priority.
        if (IsInGameThread() && GShaderCompilingManager && !GShaderCompilingManager->IsShaderCompilationSkipped())
        {
            GShaderCompilingManager->ProcessAsyncResults(0.002f, false);
        }
        State = ShaderState(M, Quality, Data, FPlatformTime::Seconds() - Started >= WaitBudgetSeconds, true, CompletedMap.GetReference());
        const FString Current = UTF8_TO_TCHAR(Name(State));
        if (Current != Previous) { States.Add(MakeShared<FJsonValueString>(Current)); Previous = Current; }
        if (State == EState::Pending) FPlatformProcess::Sleep(0.01f);
    } while (State == EState::Pending);
    Data->SetArrayField(TEXT("compile_states_observed"), States);
    Data->SetNumberField(TEXT("compile_elapsed_seconds"), FPlatformTime::Seconds() - Started);
    Data->SetNumberField(TEXT("compile_wait_budget_seconds"), WaitBudgetSeconds);
    UMaterial::OnMaterialCompilationFinished().Remove(CompletionHandle);
    if (SuccessfulMapEvidence && State == EState::Succeeded) *SuccessfulMapEvidence = CompletedMap;
    return State == EState::Succeeded;
}

bool JasperContrastGraph(UMaterial* M, bool Completed, FString& MultiplyId)
{
    if (!M || M->GetExpressions().Num() != (Completed ? 4 : 3)) return false;
    UMaterialExpressionSceneTexture* Scene = nullptr;
    UMaterialExpressionSubtract* Subtract = nullptr;
    UMaterialExpressionMultiply* Multiply = nullptr;
    UMaterialExpressionAdd* Add = nullptr;
    for (UMaterialExpression* E : M->GetExpressions())
    {
        if (!E) return false;
        if (E->GetClass() == UMaterialExpressionSceneTexture::StaticClass())
        { if (Scene) return false; Scene = CastChecked<UMaterialExpressionSceneTexture>(E); }
        else if (E->GetClass() == UMaterialExpressionSubtract::StaticClass())
        { if (Subtract) return false; Subtract = CastChecked<UMaterialExpressionSubtract>(E); }
        else if (E->GetClass() == UMaterialExpressionMultiply::StaticClass())
        { if (Multiply) return false; Multiply = CastChecked<UMaterialExpressionMultiply>(E); }
        else if (E->GetClass() == UMaterialExpressionAdd::StaticClass())
        { if (Add) return false; Add = CastChecked<UMaterialExpressionAdd>(E); }
        else return false;
    }
    if (!Scene || !Subtract || !Multiply || Scene->SceneTextureId != PPI_PostProcessInput0 ||
        Scene->Coordinates.Expression || Subtract->ConstB != 0.5f || Multiply->ConstB != 1.08f ||
        Subtract->A.Expression != Scene || Subtract->A.OutputIndex != 0 || Subtract->B.Expression ||
        Multiply->A.Expression != Subtract || Multiply->A.OutputIndex != 0 || Multiply->B.Expression) return false;
    auto* Emissive = M->GetExpressionInputForProperty(MP_EmissiveColor);
    if (!Emissive) return false;
    if (Completed)
    {
        if (!Add || Add->ConstB != 0.5f || Add->A.Expression != Multiply || Add->A.OutputIndex != 0 ||
            Add->B.Expression || Emissive->Expression != Add || Emissive->OutputIndex != 0) return false;
    }
    else if (Add || Emissive->Expression || M->GetOutermost()->IsDirty()) return false;
    auto Info = Inspect(M);
    for (const auto& V : Info->GetArrayField(TEXT("property_inputs")))
    {
        auto P = V->AsObject();
        if (Text(P.ToSharedRef(), TEXT("property")) != TEXT("MP_EmissiveColor") && P->GetBoolField(TEXT("connected"))) return false;
    }
    MultiplyId = Id(Multiply);
    return true;
}

bool JasperRecipe(const JArray& Nodes, const JArray& Links, const JArray& Props, const JArray& Updates, const FString& MultiplyId)
{
    if (Nodes.Num() != 1 || Links.Num() != 1 || Props.Num() != 1 || Updates.Num()) return false;
    auto N = Nodes[0]->AsObject().ToSharedRef();
    auto L = Links[0]->AsObject().ToSharedRef();
    auto P = Props[0]->AsObject().ToSharedRef();
    const TSharedPtr<FJsonObject>* ParametersObject = nullptr;
    double Constant = 0;
    return Text(N, TEXT("id")) == TEXT("contrast_add") && Text(N, TEXT("type")) == TEXT("Add") &&
        N->TryGetObjectField(TEXT("parameters"), ParametersObject) && (*ParametersObject)->Values.Num() == 1 &&
        (*ParametersObject)->TryGetNumberField(TEXT("const_b"), Constant) && Constant == 0.5 &&
        Text(L, TEXT("from_node")) == MultiplyId && Text(L, TEXT("from_output")).IsEmpty() &&
        Text(L, TEXT("to_node")) == TEXT("contrast_add") && Text(L, TEXT("to_input")) == TEXT("A") &&
        Text(P, TEXT("from_node")) == TEXT("contrast_add") && Text(P, TEXT("from_output")).IsEmpty() &&
        Text(P, TEXT("property")) == TEXT("EmissiveColor");
}

bool HasCycle(const TMap<FString, TArray<FString>>& Edges)
{
    TSet<FString> Active, Done;
    TFunction<bool(const FString&)> Visit = [&](const FString& N)
    {
        if (Active.Contains(N)) return true;
        if (Done.Contains(N)) return false;
        Active.Add(N);
        if (const auto* Targets = Edges.Find(N)) for (const FString& T : *Targets) if (Visit(T)) return true;
        Active.Remove(N); Done.Add(N); return false;
    };
    for (const auto& Pair : Edges) if (Visit(Pair.Key)) return true;
    return false;
}
}

bool FForgeMaterials::Handle(const FString& Command, const JObject& Args, JObject Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* C, const TCHAR* M) { Code = C; Message = M; return false; };
    if (!IsInGameThread()) return Fail(TEXT("wrong_thread"), TEXT("Material operations require the game thread."));
    if (!GEditor || GEditor->PlayWorld) return Fail(TEXT("editor_not_ready"), TEXT("Material operations require an idle editor, outside PIE."));
    const bool bInspect = Command == TEXT("material_graph_info");
    const bool bPreview = Command == TEXT("material_preview") || Command == TEXT("material_edit_preview");
    const bool bApply = Command == TEXT("material_apply") || Command == TEXT("material_edit_apply");
    if (!bInspect && !bPreview && !bApply) return Fail(TEXT("command_not_allowed"), TEXT("Material command is not allowlisted."));
    for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
    TSharedPtr<FJsonObject> Recipe;
    FPreview Plan;
    bool bCreate = Command == TEXT("material_preview");
    if (bInspect)
    {
        if (!Fields(Args, {TEXT("asset_path")})) return Fail(TEXT("invalid_arguments"), TEXT("Inspection requires one package path."));
        const FString AssetPath = Text(Args, TEXT("asset_path"));
        if (!Path(AssetPath)) return Fail(TEXT("invalid_arguments"), TEXT("Use a valid /Game/ or /JasperPrism/ package path."));
        UMaterial* M = LoadObject<UMaterial>(nullptr, *ObjectPath(AssetPath));
        if (!M) return Fail(TEXT("asset_not_found"), TEXT("Material asset was not found."));
        if (M->GetExpressions().Num() + M->GetEditorComments().Num() > 256) return Fail(TEXT("graph_limit"), TEXT("Material exceeds the 256-node inspection bound; no partial graph is returned."));
        auto Info = Inspect(M);
        if (Json(Info).Len() > 400000) return Fail(TEXT("graph_limit"), TEXT("Graph metadata exceeds the response bound; no partial graph is returned."));
        Data->Values = Info->Values; Data->SetBoolField(TEXT("saved"), false); return true;
    }
    if (bPreview)
    {
        const TSharedPtr<FJsonObject>* R = nullptr;
        if (!Fields(Args, {TEXT("recipe")}) || !Args->TryGetObjectField(TEXT("recipe"), R))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected a typed material recipe."));
        Recipe = *R;
    }
    else
    {
        if (!Fields(Args, {TEXT("preview_id"), TEXT("confirmation"), TEXT("expected_action")})) return Fail(TEXT("invalid_arguments"), TEXT("Apply requires preview_id, confirmation and optional expected_action only."));
        const FString PreviewId = Text(Args, TEXT("preview_id"));
        if (PreviewId.IsEmpty() || PreviewId != Text(Args, TEXT("confirmation"))) return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
        auto* Found = Previews.Find(PreviewId);
        if (!Found) return Fail(TEXT("preview_not_found"), TEXT("Preview is missing, expired or consumed."));
        if (Found->bCreate != (Command == TEXT("material_apply"))) return Fail(TEXT("preview_kind_mismatch"), TEXT("Use the apply operation matching the reviewed preview."));
        if (Args->HasField(TEXT("expected_action")) && Text(Args, TEXT("expected_action")) != Text(Found->Recipe.ToSharedRef(), TEXT("action")))
            return Fail(TEXT("preview_kind_mismatch"), TEXT("The preview action does not match this compile/save operation."));
        Plan = *Found; Previews.Remove(PreviewId); Recipe = Plan.Recipe; bCreate = Plan.bCreate;
    }
    auto R = Recipe.ToSharedRef();
    if (!Fields(R, {TEXT("asset_path"), TEXT("domain"), TEXT("blendable_location"), TEXT("nodes"), TEXT("connections"), TEXT("properties"), TEXT("updates"), TEXT("action"), TEXT("development_authorization"), TEXT("creation_authorization")}))
        return Fail(TEXT("invalid_arguments"), TEXT("Recipe contains unsupported fields."));
    const FString AssetPath = Text(R, TEXT("asset_path"));
    if (!Path(AssetPath)) return Fail(TEXT("invalid_arguments"), TEXT("Destination must be a mounted /Game/ or /JasperPrism/ package path."));
    const bool Protected = AssetPath.Equals(UTF8_TO_TCHAR(ForgeMaterialDevelopment::Target), ESearchCase::IgnoreCase);
    const bool ForgeTestTarget = AssetPath.Equals(UTF8_TO_TCHAR(ForgeMaterialDevelopment::CreationTarget), ESearchCase::IgnoreCase);
    const TSharedPtr<FJsonObject>* Authorization = nullptr;
    const bool HasAuthorization = R->TryGetObjectField(TEXT("development_authorization"), Authorization);
    const TSharedPtr<FJsonObject>* CreationAuthorization = nullptr;
    const bool HasCreationAuthorization = R->TryGetObjectField(TEXT("creation_authorization"), CreationAuthorization);
    if (HasAuthorization && HasCreationAuthorization)
        return Fail(TEXT("development_not_authorized"), TEXT("Existing-material and test-material creation authorizations cannot be combined."));
    if (Protected && !HasAuthorization)
        return Fail(TEXT("asset_protected"), TEXT("The original JasperPrism material is protected from mutations."));
    if (HasAuthorization && (!Protected || bCreate))
        return Fail(TEXT("development_not_authorized"), TEXT("Development authorization cannot create, replace or target unrelated materials."));
    if (ForgeTestTarget && AssetPath != UTF8_TO_TCHAR(ForgeMaterialDevelopment::CreationTarget))
        return Fail(TEXT("development_not_authorized"), TEXT("Use the exact canonical ForgeMCP test-material path."));
    if (HasCreationAuthorization && !bCreate)
        return Fail(TEXT("development_not_authorized"), TEXT("Test-material creation authorization cannot modify an existing material."));
    const bool DestinationAbsent = !FindPackage(nullptr, *AssetPath) && !FPackageName::DoesPackageExist(AssetPath);
    if (bCreate && !DestinationAbsent)
        return Fail(TEXT("asset_exists"), TEXT("Destination exists; material overwrite is forbidden."));
    if (Text(R, TEXT("domain")) != TEXT("PostProcess") || Text(R, TEXT("blendable_location")) != TEXT("SceneColorAfterTonemapping"))
        return Fail(TEXT("unsupported_material_settings"), TEXT("This version supports PostProcess at SceneColorAfterTonemapping only."));
    const FString Action = Text(R, TEXT("action"));
    if (Action != TEXT("edit") && Action != TEXT("compile") && Action != TEXT("save"))
        return Fail(TEXT("invalid_arguments"), TEXT("Unknown material action."));
    if (ForgeTestTarget && bCreate && !HasCreationAuthorization)
        return Fail(TEXT("creation_authorization_required"), TEXT("The ForgeMCP test-material path requires explicit creation authorization."));
    if (HasCreationAuthorization)
    {
        auto A = CreationAuthorization->ToSharedRef();
        if (!Fields(A, {TEXT("asset_path"), TEXT("permission"), TEXT("expected_state")}) ||
            !ForgeMaterialDevelopment::AllowedCreation(TCHAR_TO_UTF8(*AssetPath),
                TCHAR_TO_UTF8(*Text(A, TEXT("asset_path"))), TCHAR_TO_UTF8(*Text(A, TEXT("permission"))),
                TCHAR_TO_UTF8(*Text(A, TEXT("expected_state"))), DestinationAbsent, bCreate, Action == TEXT("edit")))
            return Fail(TEXT("development_not_authorized"), TEXT("Creation authorization permits only a new material at the exact test path while its destination is absent."));
    }
    JArray Nodes, Links, Props, Updates;
    if (!Arrays(R, TEXT("nodes"), 32, Nodes) || !Arrays(R, TEXT("connections"), 64, Links) || !Arrays(R, TEXT("properties"), 1, Props) || !Arrays(R, TEXT("updates"), 32, Updates))
        return Fail(TEXT("invalid_arguments"), TEXT("Expected bounded typed node, connection, property and update arrays."));
    if ((Action != TEXT("edit") && (bCreate || Nodes.Num() || Links.Num() || Props.Num() || Updates.Num())) || (bCreate && Updates.Num()))
        return Fail(TEXT("invalid_arguments"), TEXT("Creation cannot contain updates; compile/save cannot contain graph edits."));
    UMaterial* M = bCreate ? nullptr : LoadObject<UMaterial>(nullptr, *ObjectPath(AssetPath));
    if (!bCreate && !M) return Fail(TEXT("asset_not_found"), TEXT("Material asset was not found."));
    if (M && M->GetPathName() != ObjectPath(AssetPath)) return Fail(TEXT("asset_identity_mismatch"), TEXT("Redirected or aliased material destinations are forbidden."));
    if (M && (M->MaterialDomain != MD_PostProcess || M->BlendableLocation != BL_SceneColorAfterTonemapping))
        return Fail(TEXT("unsupported_material_settings"), TEXT("Edits preserve domain/location and require a matching post-process material."));
    if (M && (M->GetExpressions().Num() + M->GetEditorComments().Num() > 256 || Json(Inspect(M)).Len() > 400000))
        return Fail(TEXT("graph_limit"), TEXT("Material exceeds complete graph inspection bounds."));
    if (HasAuthorization)
    {
        auto A = Authorization->ToSharedRef();
        FString MultiplyId;
        const bool ShapeMatches = JasperContrastGraph(M, Action == TEXT("compile"), MultiplyId) &&
            (Action != TEXT("edit") || JasperRecipe(Nodes, Links, Props, Updates, MultiplyId));
        if (!Fields(A, {TEXT("asset_path"), TEXT("permission"), TEXT("expected_state_id")}) ||
            !ForgeMaterialDevelopment::Allowed(TCHAR_TO_UTF8(*AssetPath), TCHAR_TO_UTF8(*Text(A, TEXT("asset_path"))),
                TCHAR_TO_UTF8(*Text(A, TEXT("permission"))),
                M && Text(A, TEXT("expected_state_id")) == Text(Inspect(M), TEXT("state_id")), bCreate,
                Action == TEXT("edit") || Action == TEXT("compile"), ShapeMatches))
            return Fail(TEXT("development_not_authorized"), TEXT("Explicit exact-path/state consent permits only the missing contrast Add/connections or compilation of the completed graph; no existing-material save."));
    }
    if (M && M->GetExpressions().Num() + M->GetEditorComments().Num() + Nodes.Num() > 256)
        return Fail(TEXT("graph_limit"), TEXT("Result would exceed the 256-node graph bound."));
    const FString BeforeFingerprint = M ? Fingerprint(M) : AssetPath;
    if (bApply && BeforeFingerprint != Plan.Fingerprint) return Fail(TEXT("stale_preview"), TEXT("Material state changed; inspect and preview again."));
    if (Action == TEXT("save"))
    {
        auto* Owned = Created.Find(AssetPath);
        if (!Owned || Owned->Get() != M || FPackageName::DoesPackageExist(AssetPath))
            return Fail(TEXT("save_not_authorized"), TEXT("Saving supports only new unsaved materials created by this bridge session; no existing asset file overwrite."));
        if (Validated.FindRef(AssetPath) != BeforeFingerprint)
            return Fail(TEXT("compile_required"), TEXT("Compile the current graph successfully before previewing save."));
    }
    TMap<FString, UMaterialExpression*> Existing;
    TMap<FString, UClass*> Classes;
    TMap<FString, TArray<FString>> Edges;
    TSet<FString> Occupied, ParameterNames;
    if (M) for (UMaterialExpression* E : M->GetExpressions())
    {
        if (!E) continue;
        const FString NodeId = Id(E);
        if (!E->MaterialExpressionGuid.IsValid() || Existing.Contains(NodeId)) return Fail(TEXT("ambiguous_node_id"), TEXT("Existing expression GUIDs must be valid and unique."));
        Existing.Add(NodeId, E); Classes.Add(NodeId, E->GetClass());
        if (auto* N = Cast<UMaterialExpressionScalarParameter>(E)) ParameterNames.Add(N->ParameterName.ToString().ToLower());
        if (auto* N = Cast<UMaterialExpressionVectorParameter>(E)) ParameterNames.Add(N->ParameterName.ToString().ToLower());
        for (int32 I = 0; FExpressionInput* Pin = E->GetInput(I); ++I) if (Pin->Expression)
        {
            Occupied.Add(NodeId + TEXT("|") + E->GetInputName(I).ToString());
            Edges.FindOrAdd(Id(Pin->Expression)).Add(NodeId);
        }
    }
    for (const auto& V : Nodes)
    {
        auto N = V->AsObject().ToSharedRef();
        const FString Alias = Text(N, TEXT("id")); UClass* Class = ExpressionClass(Text(N, TEXT("type")));
        const TSharedPtr<FJsonObject>* P = nullptr;
        double X = 0, Y = 0;
        if (!Fields(N, {TEXT("id"), TEXT("type"), TEXT("x"), TEXT("y"), TEXT("parameters")}) || !Identifier(Alias, true) || Classes.Contains(Alias) ||
            !Class || !N->TryGetObjectField(TEXT("parameters"), P) || !Parameters(P->ToSharedRef(), Class) ||
            !N->TryGetNumberField(TEXT("x"), X) || !N->TryGetNumberField(TEXT("y"), Y) || !FMath::IsFinite(X) || !FMath::IsFinite(Y) ||
            X != FMath::FloorToDouble(X) || Y != FMath::FloorToDouble(Y) || FMath::Abs(X) > 16000 || FMath::Abs(Y) > 16000)
            return Fail(TEXT("invalid_arguments"), TEXT("Invalid expression type, alias, position or parameters."));
        if (Class == UMaterialExpressionScalarParameter::StaticClass() || Class == UMaterialExpressionVectorParameter::StaticClass())
        {
            const FString Name = Text(P->ToSharedRef(), TEXT("parameter_name")).ToLower();
            if (Name.IsEmpty() || ParameterNames.Contains(Name)) return Fail(TEXT("parameter_name_conflict"), TEXT("New scalar/vector parameters require unique explicit names."));
            ParameterNames.Add(Name);
        }
        Classes.Add(Alias, Class);
    }
    TSet<FString> Updated;
    for (const auto& V : Updates)
    {
        auto U = V->AsObject().ToSharedRef(); const FString NodeId = Text(U, TEXT("node_id"));
        auto* E = Existing.FindRef(NodeId); UClass* Class = ExpressionClass(Text(U, TEXT("type")));
        const TSharedPtr<FJsonObject>* P = nullptr;
        if (!Fields(U, {TEXT("node_id"), TEXT("type"), TEXT("parameters")}) || !E || E->GetClass() != Class || Updated.Contains(NodeId) ||
            !U->TryGetObjectField(TEXT("parameters"), P) || (*P)->Values.IsEmpty() || !Parameters(P->ToSharedRef(), Class))
            return Fail(TEXT("invalid_arguments"), TEXT("Update requires an exact inspected expression GUID, matching allowlisted type and valid parameters."));
        // Renaming existing parameters can affect instances and is excluded from this first version.
        if ((*P)->HasField(TEXT("parameter_name"))) return Fail(TEXT("unsupported_operation"), TEXT("Existing parameter renaming is not supported."));
        if (Class == UMaterialExpressionSceneTexture::StaticClass() && CastChecked<UMaterialExpressionSceneTexture>(E)->SceneTextureId != PPI_PostProcessInput0)
            return Fail(TEXT("unsupported_operation"), TEXT("Only existing PostProcessInput0 SceneTexture nodes can be updated."));
        Updated.Add(NodeId);
    }
    auto ResolvePreview = [&](const FString& NodeId) -> UMaterialExpression*
    {
        if (auto* E = Existing.FindRef(NodeId)) return E;
        UClass* Class = Classes.FindRef(NodeId);
        return Class ? Class->GetDefaultObject<UMaterialExpression>() : nullptr;
    };
    for (const auto& V : Links)
    {
        auto L = V->AsObject().ToSharedRef(); const FString From = Text(L, TEXT("from_node")), To = Text(L, TEXT("to_node"));
        auto* F = ResolvePreview(From); auto* T = ResolvePreview(To);
        FString Out; const FString In = Text(L, TEXT("to_input"));
        const FString Target = To + TEXT("|") + In;
        if (!Fields(L, {TEXT("from_node"), TEXT("from_output"), TEXT("to_node"), TEXT("to_input")}) || !F || !T ||
            !L->TryGetStringField(TEXT("from_output"), Out) || Output(F, Out) == INDEX_NONE || !Input(T, In) || Occupied.Contains(Target))
            return Fail(TEXT("invalid_connection"), TEXT("Connection requires valid native pins and an unoccupied destination input."));
        Occupied.Add(Target); Edges.FindOrAdd(From).Add(To);
    }
    if (HasCycle(Edges)) return Fail(TEXT("graph_cycle"), TEXT("Graph cycles are unsupported."));
    for (const auto& V : Props)
    {
        auto P = V->AsObject().ToSharedRef(); auto* E = ResolvePreview(Text(P, TEXT("from_node"))); FString Out;
        if (!Fields(P, {TEXT("from_node"), TEXT("from_output"), TEXT("property")}) || Text(P, TEXT("property")) != TEXT("EmissiveColor") ||
            !P->TryGetStringField(TEXT("from_output"), Out) || !E || Output(E, Out) == INDEX_NONE ||
            (M && M->GetExpressionInputForProperty(MP_EmissiveColor)->Expression))
            return Fail(TEXT("invalid_connection"), TEXT("Only an unoccupied EmissiveColor property can be connected."));
    }
    if (bPreview)
    {
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired previews are supported."));
        const FString PreviewId = FGuid::NewGuid().ToString(EGuidFormats::Digits);
        Previews.Add(PreviewId, {Recipe, BeforeFingerprint, bCreate, FPlatformTime::Seconds() + 600});
        Data->SetStringField(TEXT("preview_id"), PreviewId); Data->SetObjectField(TEXT("changes"), R);
        Data->SetStringField(TEXT("action"), Action); Data->SetBoolField(TEXT("creates_asset"), bCreate);
        Data->SetBoolField(TEXT("saves_asset"), Action == TEXT("save")); Data->SetNumberField(TEXT("expires_in_seconds"), 600);
        Data->SetStringField(TEXT("compile_scope"), TEXT("Active editor RHI feature level and material quality only."));
        return true;
    }
    Data->SetStringField(TEXT("asset_path"), AssetPath); Data->SetBoolField(TEXT("saved"), false);
    if (Action == TEXT("save"))
    {
        FString Filename;
        if (!FPackageName::TryConvertLongPackageNameToFilename(AssetPath, Filename, FPackageName::GetAssetPackageExtension()) ||
            IFileManager::Get().FileExists(*Filename)) return Fail(TEXT("asset_exists"), TEXT("Asset save destination already exists."));
        // Revalidate shader state immediately before save; graph fingerprint already matches.
        const auto Quality = static_cast<EMaterialQualityLevel::Type>(GetCachedScalabilityCVars().MaterialQualityLevel);
        const auto* Proof = CompletionProof.Find(AssetPath);
        if (ShaderState(M, Quality, Data, false, false, Proof ? Proof->GetReference() : nullptr) != ForgeMaterialValidation::EState::Succeeded)
            return Fail(TEXT("compile_required"), TEXT("Shader validation is no longer successful; asset was not saved."));
        FSavePackageArgs SaveArgs; SaveArgs.TopLevelFlags = RF_Public | RF_Standalone; SaveArgs.SaveFlags = SAVE_NoError;
        const bool Saved = UPackage::SavePackage(M->GetOutermost(), M, *Filename, SaveArgs);
        Data->SetBoolField(TEXT("saved"), Saved);
        Data->SetStringField(TEXT("state"), Saved ? TEXT("saved") : TEXT("save_failed"));
        Data->SetStringField(TEXT("filename"), FPaths::ConvertRelativePathToFull(Filename));
        if (Saved) { Created.Remove(AssetPath); Validated.Remove(AssetPath); CompletionProof.Remove(AssetPath); }
        return true;
    }
    const FString Directory = FPaths::ProjectSavedDir() / TEXT("MajesticForge/MaterialRecovery");
    IFileManager::Get().MakeDirectory(*Directory, true);
    const FString Journal = Directory / (FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".json"));
    if (HasAuthorization)
    {
        FString OriginalFilename;
        const FString BinaryBackup = FPaths::ChangeExtension(Journal, TEXT("uasset"));
        if (!FPackageName::TryConvertLongPackageNameToFilename(AssetPath, OriginalFilename, FPackageName::GetAssetPackageExtension()) ||
            !IFileManager::Get().FileExists(*OriginalFilename) ||
            IFileManager::Get().FileExists(*(FPaths::ChangeExtension(OriginalFilename, TEXT("uexp")))) ||
            IFileManager::Get().FileExists(*(FPaths::ChangeExtension(OriginalFilename, TEXT("ubulk")))) ||
            IFileManager::Get().Copy(*BinaryBackup, *OriginalFilename, false, false) != COPY_OK)
            return Fail(TEXT("backup_failed"), TEXT("Exact original material backup could not be created; split packages are unsupported; no mutations made."));
        TArray<uint8> OriginalBytes, BackupBytes;
        if (!FFileHelper::LoadFileToArray(OriginalBytes, *OriginalFilename) ||
            !FFileHelper::LoadFileToArray(BackupBytes, *BinaryBackup) || OriginalBytes != BackupBytes)
            return Fail(TEXT("backup_failed"), TEXT("Original material backup verification failed; no mutations made."));
        Data->SetStringField(TEXT("asset_backup"), FPaths::ConvertRelativePathToFull(BinaryBackup));
    }
    auto Before = M ? Inspect(M) : MakeShared<FJsonObject>();
    if (!FFileHelper::SaveStringToFile(Json(Before), *Journal, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
        return Fail(TEXT("backup_failed"), TEXT("Graph-state recovery journal could not be written; no mutations made."));
    Data->SetStringField(TEXT("recovery_journal"), FPaths::ConvertRelativePathToFull(Journal));
    Validated.Remove(AssetPath); CompletionProof.Remove(AssetPath);
    FScopedTransaction Transaction(NSLOCTEXT("MajesticForge", "MaterialEdit", "ForgeMCP material graph"));
    const bool WasDirty = M && M->GetOutermost()->IsDirty();
    if (bCreate)
    {
        UPackage* Package = CreatePackage(*AssetPath);
        M = NewObject<UMaterial>(Package, *FPackageName::GetLongPackageAssetName(AssetPath), RF_Public | RF_Standalone | RF_Transactional);
        if (!M) { Transaction.Cancel(); return Fail(TEXT("creation_failed"), TEXT("Native material creation failed.")); }
        M->MaterialDomain = MD_PostProcess; M->BlendableLocation = BL_SceneColorAfterTonemapping;
        FAssetRegistryModule::AssetCreated(M); Created.Add(AssetPath, M);
    }
    M->Modify();
    // Retain exact native pin state and typed values for recovery without touching other graphs.
    TArray<TPair<FExpressionInput*, FExpressionInput>> PinBackup;
    TMap<UMaterialExpression*, TSharedRef<FJsonObject>> ValueBackup;
    for (const auto& Pair : Existing)
    {
        auto* E = Pair.Value;
        for (int32 I = 0; FExpressionInput* Pin = E->GetInput(I); ++I) PinBackup.Emplace(Pin, *Pin);
    }
    auto* Emissive = M->GetExpressionInputForProperty(MP_EmissiveColor);
    PinBackup.Emplace(Emissive, *Emissive);
    TArray<UMaterialExpression*> Added;
    TMap<FString, UMaterialExpression*> Resolved = Existing;
    JArray AddedInfo;
    bool Success = true;
    for (const auto& V : Nodes)
    {
        auto N = V->AsObject().ToSharedRef();
        auto* E = UMaterialEditingLibrary::CreateMaterialExpression(M, ExpressionClass(Text(N, TEXT("type"))), N->GetIntegerField(TEXT("x")), N->GetIntegerField(TEXT("y")));
        if (!E) { Success = false; break; }
        E->SetFlags(RF_Transactional); E->Modify(); Added.Add(E);
        SetParameters(E, N->GetObjectField(TEXT("parameters")).ToSharedRef());
        Resolved.Add(Text(N, TEXT("id")), E);
        auto Entry = MakeShared<FJsonObject>(); Entry->SetStringField(TEXT("id"), Text(N, TEXT("id"))); Entry->SetStringField(TEXT("node_id"), Id(E));
        AddedInfo.Add(MakeShared<FJsonValueObject>(Entry));
    }
    if (Success) for (const auto& V : Updates)
    {
        auto U = V->AsObject().ToSharedRef(); auto* E = Resolved.FindRef(Text(U, TEXT("node_id")));
        auto P = GetParameters(E); P->RemoveField(TEXT("scene_texture_id_native"));
        ValueBackup.Add(E, P); E->Modify(); SetParameters(E, U->GetObjectField(TEXT("parameters")).ToSharedRef());
    }
    if (Success) for (const auto& V : Links)
    {
        auto L = V->AsObject().ToSharedRef(); auto* F = Resolved.FindRef(Text(L, TEXT("from_node"))); auto* T = Resolved.FindRef(Text(L, TEXT("to_node")));
        if (!F || !T) { Success = false; break; }
        T->Modify();
        if (!UMaterialEditingLibrary::ConnectMaterialExpressions(F, NativeOutput(F, Text(L, TEXT("from_output"))), T, Text(L, TEXT("to_input")))) { Success = false; break; }
        auto* Pin = Input(T, Text(L, TEXT("to_input")));
        if (!Pin || Pin->Expression != F || Pin->OutputIndex != Output(F, Text(L, TEXT("from_output")))) { Success = false; break; }
    }
    if (Success) for (const auto& V : Props)
    {
        auto P = V->AsObject().ToSharedRef(); auto* F = Resolved.FindRef(Text(P, TEXT("from_node")));
        if (!F || !UMaterialEditingLibrary::ConnectMaterialProperty(F, NativeOutput(F, Text(P, TEXT("from_output"))), MP_EmissiveColor) ||
            Emissive->Expression != F || Emissive->OutputIndex != Output(F, Text(P, TEXT("from_output")))) { Success = false; break; }
    }
    if (Success && HasAuthorization)
    {
        FString MultiplyId;
        Success = JasperContrastGraph(M, true, MultiplyId);
    }
    TRefCountPtr<FMaterialShaderMap> SuccessfulMapEvidence;
    if (Success) Success = Compile(M, Data, 45.0, &SuccessfulMapEvidence);
    Validated.Remove(AssetPath);
    if (!Success)
    {
        for (const auto& Pair : PinBackup) *Pair.Key = Pair.Value;
        for (const auto& Pair : ValueBackup) SetParameters(Pair.Key, Pair.Value);
        for (UMaterialExpression* E : Added) UMaterialEditingLibrary::DeleteMaterialExpression(M, E);
        bool Recovered = true;
        if (bCreate)
        {
            FAssetRegistryModule::AssetDeleted(M); Created.Remove(AssetPath);
            M->ClearFlags(RF_Public | RF_Standalone); M->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
            // The fresh empty package is no longer a material asset and must not be saved.
            if (UPackage* Package = FindPackage(nullptr, *AssetPath)) Package->SetDirtyFlag(false);
        }
        else
        {
            auto RecoveryData = MakeShared<FJsonObject>(); Compile(M, RecoveryData, 5.0);
            Data->SetObjectField(TEXT("rollback_shader_validation"), RecoveryData);
            M->GetOutermost()->SetDirtyFlag(WasDirty);
            auto Restored = Inspect(M); Restored->SetStringField(TEXT("state_id"), Before->GetStringField(TEXT("state_id")));
            Recovered = Json(Restored) == Json(Before);
        }
        Transaction.Cancel();
        Data->SetStringField(TEXT("state"), Recovered ? TEXT("rolled_back") : TEXT("partial"));
        Data->SetStringField(TEXT("diagnostic_code"), TEXT("material_validation_failed"));
        Data->SetArrayField(TEXT("created_nodes"), {}); return true;
    }
    M->MarkPackageDirty(); Validated.Add(AssetPath, Fingerprint(M));
    if (SuccessfulMapEvidence) CompletionProof.Add(AssetPath, SuccessfulMapEvidence);
    Data->SetStringField(TEXT("state"), TEXT("completed")); Data->SetArrayField(TEXT("created_nodes"), AddedInfo);
    Data->SetObjectField(TEXT("graph"), Inspect(M)); return true;
}
