// SPDX-License-Identifier: MIT
#include "ForgeMaterialInstances.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Editor.h"
#include "HAL/FileManager.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Engine/Texture.h"
#include "MaterialTypes.h"
#include "Misc/SecureHash.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectGlobals.h"

namespace
{
using JObject = TSharedRef<FJsonObject>;

FString Field(const JObject& Object, const TCHAR* Name)
{
    FString Value;
    Object->TryGetStringField(Name, Value);
    return Value;
}

bool ValidAssetPackage(const FString& Path)
{
    if (Path.Len() > 240 || !(Path.StartsWith(TEXT("/Game/")) || Path.StartsWith(TEXT("/JasperPrism/"))) ||
        !FPackageName::IsValidLongPackageName(Path)) return false;
    FString Filename;
    return FPackageName::TryConvertLongPackageNameToFilename(Path, Filename, FPackageName::GetAssetPackageExtension());
}

FString ObjectPath(const FString& PackagePath)
{
    return PackagePath + TEXT(".") + FPackageName::GetLongPackageAssetName(PackagePath);
}

FString ParameterKey(EMaterialParameterType Type, const FMaterialParameterInfo& Info)
{
    return FString::Printf(TEXT("%d|%s|%d|%d"), static_cast<int32>(Type), *Info.Name.ToString(),
        static_cast<int32>(Info.Association.GetValue()), Info.Index);
}

void AddParameterValues(UMaterialInterface* Material, EMaterialParameterType Type, TArray<JObject>& Out, FString& Fingerprint)
{
    TMap<FMaterialParameterInfo, FMaterialParameterMetadata> Parameters;
    Material->GetAllParametersOfType(Type, Parameters);
    TArray<FMaterialParameterInfo> Keys;
    Parameters.GenerateKeyArray(Keys);
    Keys.Sort([](const FMaterialParameterInfo& A, const FMaterialParameterInfo& B)
    {
        return A.ToString() < B.ToString();
    });

    for (const FMaterialParameterInfo& Info : Keys)
    {
        const FMaterialParameterMetadata& Meta = Parameters.FindChecked(Info);
        auto Value = MakeShared<FJsonObject>();
        const TCHAR* Kind = Type == EMaterialParameterType::Scalar ? TEXT("scalar") :
            Type == EMaterialParameterType::Vector ? TEXT("vector") : TEXT("texture");
        Value->SetStringField(TEXT("type"), Kind);
        Value->SetStringField(TEXT("name"), Info.Name.ToString());
        Value->SetStringField(TEXT("association"), Info.Association == EMaterialParameterAssociation::GlobalParameter ? TEXT("global") : TEXT("layer_or_blend"));
        Value->SetNumberField(TEXT("index"), Info.Index);
        Value->SetBoolField(TEXT("overridden"), Meta.bOverride);
        if (Type == EMaterialParameterType::Scalar)
        {
            const double Scalar = Meta.Value.AsScalar();
            Value->SetNumberField(TEXT("value"), Scalar);
            Fingerprint += FString::Printf(TEXT("%s=%.9g|%d;"), *ParameterKey(Type, Info), Scalar, Meta.bOverride);
        }
        else if (Type == EMaterialParameterType::Vector)
        {
            const FLinearColor Color = Meta.Value.AsLinearColor();
            TArray<TSharedPtr<FJsonValue>> Components = {
                MakeShared<FJsonValueNumber>(Color.R), MakeShared<FJsonValueNumber>(Color.G),
                MakeShared<FJsonValueNumber>(Color.B), MakeShared<FJsonValueNumber>(Color.A)};
            Value->SetArrayField(TEXT("value"), Components);
            Fingerprint += FString::Printf(TEXT("%s=%.9g,%.9g,%.9g,%.9g|%d;"),
                *ParameterKey(Type, Info), Color.R, Color.G, Color.B, Color.A, Meta.bOverride);
        }
        else
        {
            UObject* Texture = Meta.Value.AsTextureObject();
            const FString TexturePath = GetPathNameSafe(Texture);
            Value->SetStringField(TEXT("value"), TexturePath);
            Fingerprint += ParameterKey(Type, Info) + TEXT("=") + TexturePath + FString::Printf(TEXT("|%d;"), Meta.bOverride);
        }
        Out.Add(Value);
    }
}

FString Fingerprint(UMaterialInterface* Material)
{
    if (!IsValid(Material)) return {};
    FString State = Material->GetPathName() + TEXT("|") + Material->GetLightingGuid().ToString() + TEXT("|");
    if (const auto* Instance = Cast<UMaterialInstance>(Material))
        State += FString::Printf(TEXT("%u|"), Instance->ComputeAllStateCRC());
    TArray<JObject> Ignored;
    AddParameterValues(Material, EMaterialParameterType::Scalar, Ignored, State);
    AddParameterValues(Material, EMaterialParameterType::Vector, Ignored, State);
    AddParameterValues(Material, EMaterialParameterType::Texture, Ignored, State);
    return FMD5::HashAnsiString(*State);
}

FString FileFingerprint(const FString& Filename)
{
    const FMD5Hash Hash = FMD5Hash::HashFile(*Filename);
    return Hash.IsValid() ? BytesToHex(Hash.GetBytes(), Hash.GetSize()) : FString();
}

bool InstanceFilename(UMaterialInstanceConstant* Instance, FString& Filename)
{
    return IsValid(Instance) && FPackageName::TryConvertLongPackageNameToFilename(
        Instance->GetOutermost()->GetName(), Filename, FPackageName::GetAssetPackageExtension());
}

bool Fields(const JObject& Object, std::initializer_list<const TCHAR*> Allowed)
{
    for (const auto& Pair : Object->Values)
    {
        if (!Pair.Value.IsValid()) return false;
        bool Found = false;
        for (const TCHAR* Name : Allowed) if (Pair.Key == Name) Found = true;
        if (!Found) return false;
    }
    return true;
}

bool HasParameter(UMaterialInterface* Parent, EMaterialParameterType Type, const FName Name)
{
    TMap<FMaterialParameterInfo, FMaterialParameterMetadata> Parameters;
    Parent->GetAllParametersOfType(Type, Parameters);
    return Parameters.Contains(FMaterialParameterInfo(Name));
}

bool ValidateParameters(UMaterialInterface* Parent, const TArray<TSharedPtr<FJsonValue>>& Values,
    FString& Code, FString& Message)
{
    if (Values.Num() > 64)
    {
        Code = TEXT("limit_exceeded"); Message = TEXT("At most 64 scalar, vector and texture overrides can be changed per operation."); return false;
    }
    TSet<FString> Names;
    for (const auto& Entry : Values)
    {
        if (!Entry.IsValid() || Entry->Type != EJson::Object)
        { Code = TEXT("invalid_arguments"); Message = TEXT("Each parameter change must be a typed object."); return false; }
        const JObject Change = Entry->AsObject().ToSharedRef();
        FString Type, Name;
        if (!Fields(Change, {TEXT("type"), TEXT("name"), TEXT("value")}) ||
            !Change->HasField(TEXT("value")) ||
            !Change->TryGetStringField(TEXT("type"), Type) || !Change->TryGetStringField(TEXT("name"), Name) ||
            Name.IsEmpty() || Name.Len() > 64 || !(FChar::IsAlpha(Name[0]) || Name[0] == '_'))
        { Code = TEXT("invalid_arguments"); Message = TEXT("Parameters require only type, name and value fields, with a valid native name."); return false; }
        for (TCHAR Character : Name)
            if (!((Character >= 'a' && Character <= 'z') || (Character >= 'A' && Character <= 'Z') ||
                (Character >= '0' && Character <= '9') || Character == '_'))
            { Code = TEXT("invalid_arguments"); Message = TEXT("Parameter names are limited to ASCII-style identifiers."); return false; }
        const FString Identity = Type + TEXT("|") + Name;
        if (Names.Contains(Identity))
        { Code = TEXT("invalid_arguments"); Message = TEXT("A parameter may be changed only once per operation."); return false; }
        Names.Add(Identity);

        EMaterialParameterType NativeType = EMaterialParameterType::None;
        if (Type == TEXT("scalar")) NativeType = EMaterialParameterType::Scalar;
        else if (Type == TEXT("vector")) NativeType = EMaterialParameterType::Vector;
        else if (Type == TEXT("texture")) NativeType = EMaterialParameterType::Texture;
        else { Code = TEXT("unsupported_parameter_type"); Message = TEXT("Only scalar, vector and texture parameters are supported in this operation."); return false; }
        if (!HasParameter(Parent, NativeType, *Name))
        { Code = TEXT("parameter_not_found"); Message = TEXT("The parent material does not expose the requested global parameter of this type."); return false; }

        const TSharedPtr<FJsonValue> ParameterValue = Change->Values.FindChecked(TEXT("value"));
        if (NativeType == EMaterialParameterType::Scalar)
        {
            double Number = 0;
            if (ParameterValue->Type != EJson::Number || !ParameterValue->TryGetNumber(Number) || !FMath::IsFinite(Number) || FMath::Abs(Number) > 1000000)
            { Code = TEXT("invalid_arguments"); Message = TEXT("Scalar overrides require a finite number with absolute value at most 1,000,000."); return false; }
        }
        else if (NativeType == EMaterialParameterType::Vector)
        {
            if (ParameterValue->Type != EJson::Array || ParameterValue->AsArray().Num() != 4)
            { Code = TEXT("invalid_arguments"); Message = TEXT("Vector overrides require four finite linear RGBA components."); return false; }
            for (const auto& Component : ParameterValue->AsArray())
            {
                double Number = 0;
                if (!Component.IsValid() || Component->Type != EJson::Number || !Component->TryGetNumber(Number) || !FMath::IsFinite(Number) || FMath::Abs(Number) > 1000000)
                { Code = TEXT("invalid_arguments"); Message = TEXT("Vector components must be finite and bounded."); return false; }
            }
        }
        else if (ParameterValue->Type == EJson::String)
        {
            const FString TexturePath = ParameterValue->AsString();
            if (!(TexturePath.StartsWith(TEXT("/Game/")) || TexturePath.StartsWith(TEXT("/JasperPrism/"))) ||
                TexturePath.Len() > 280 || !TexturePath.Contains(TEXT(".")) ||
                !FindObject<UTexture>(nullptr, *TexturePath))
            { Code = TEXT("texture_not_loaded"); Message = TEXT("Texture override must reference an already loaded texture by exact object path."); return false; }
        }
        else if (ParameterValue->Type != EJson::Null)
        { Code = TEXT("invalid_arguments"); Message = TEXT("Texture overrides require a loaded exact object path or null for an explicit empty value."); return false; }
    }
    return true;
}

void ApplyParameters(UMaterialInstanceConstant* Instance, const TArray<TSharedPtr<FJsonValue>>& Values)
{
    for (const auto& Entry : Values)
    {
        const JObject Change = Entry->AsObject().ToSharedRef();
        const FString Type = Field(Change, TEXT("type"));
        const FMaterialParameterInfo Info(*Field(Change, TEXT("name")));
        const TSharedPtr<FJsonValue> Value = Change->Values.FindChecked(TEXT("value"));
        if (Type == TEXT("scalar")) Instance->SetScalarParameterValueEditorOnly(Info, static_cast<float>(Value->AsNumber()));
        else if (Type == TEXT("vector"))
        {
            const auto& C = Value->AsArray();
            Instance->SetVectorParameterValueEditorOnly(Info, FLinearColor(C[0]->AsNumber(), C[1]->AsNumber(), C[2]->AsNumber(), C[3]->AsNumber()));
        }
        else Instance->SetTextureParameterValueEditorOnly(Info, Value->Type == EJson::Null ? nullptr : FindObject<UTexture>(nullptr, *Value->AsString()));
    }
    Instance->PostEditChange();
    Instance->UpdateCachedData();
    Instance->MarkPackageDirty();
}

}

bool FForgeMaterialInstances::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* ErrorCode, const TCHAR* ErrorMessage)
    { Code = ErrorCode; Message = ErrorMessage; return false; };
    if (!IsInGameThread() || !GEditor || GEditor->PlayWorld)
        return Fail(TEXT("invalid_context"), TEXT("Material instance changes require the Unreal Editor game thread outside Play in Editor."));

    const bool bInspect = Command == TEXT("material_instance_info");
    const bool bSavePreview = Command == TEXT("material_instance_save_preview");
    const bool bSaveApply = Command == TEXT("material_instance_save_apply");
    const bool bPreview = Command == TEXT("material_instance_preview");
    const bool bApply = Command == TEXT("material_instance_apply");
    if (!bInspect && !bSavePreview && !bSaveApply && !bPreview && !bApply)
        return Fail(TEXT("command_not_allowed"), TEXT("Material instance command is not allowlisted."));

    FString AssetPath;
    if (bInspect || bSavePreview)
    {
        if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("asset_path"), AssetPath) || !ValidAssetPackage(AssetPath))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact loaded /Game or /JasperPrism material instance package path."));
    }
    else
    {
        FString PreviewId, Confirmation;
        if (bPreview)
        {
            if (Args->Values.Num() != 1)
                return Fail(TEXT("invalid_arguments"), TEXT("Expected one typed material-instance request."));
            const TSharedPtr<FJsonObject>* Request = nullptr;
            if (!Args->TryGetObjectField(TEXT("request"), Request) || !Request || !Request->IsValid())
                return Fail(TEXT("invalid_arguments"), TEXT("Expected one typed material-instance request."));
            const JObject Recipe = Request->ToSharedRef();
            FString Action;
            if (!Recipe->TryGetStringField(TEXT("action"), Action) || (Action != TEXT("create") && Action != TEXT("update")) ||
                !Recipe->TryGetStringField(TEXT("asset_path"), AssetPath) || !ValidAssetPackage(AssetPath))
                return Fail(TEXT("invalid_arguments"), TEXT("Choose create or update and an exact /Game or /JasperPrism destination."));
            const TArray<TSharedPtr<FJsonValue>>* Parameters = nullptr;
            if (!Recipe->TryGetArrayField(TEXT("parameters"), Parameters) || Parameters->Num() > 64)
                return Fail(TEXT("invalid_arguments"), TEXT("parameters must be an array containing at most 64 overrides."));
            const bool bCreate = Action == TEXT("create");
            FString ParentPath = Field(Recipe, TEXT("parent_path"));
            if (bCreate)
            {
                if (!Fields(Recipe, {TEXT("action"), TEXT("asset_path"), TEXT("parent_path"), TEXT("parameters")}) || !ValidAssetPackage(ParentPath))
                    return Fail(TEXT("invalid_arguments"), TEXT("Create requires action, destination, parent path and parameters only."));
            }
            else if (!Fields(Recipe, {TEXT("action"), TEXT("asset_path"), TEXT("parameters")}))
                return Fail(TEXT("invalid_arguments"), TEXT("Update requires action, existing instance path and parameters only."));

            UMaterialInterface* Target = nullptr;
            UMaterialInterface* Parent = nullptr;
            if (bCreate)
            {
                Parent = FindObject<UMaterialInterface>(nullptr, *ObjectPath(ParentPath));
                if (!IsValid(Parent)) return Fail(TEXT("parent_not_loaded"), TEXT("Load the exact parent material or instance in the Editor before preview."));
                FString DestinationFile;
                FPackageName::TryConvertLongPackageNameToFilename(AssetPath, DestinationFile, FPackageName::GetAssetPackageExtension());
                if (FindPackage(nullptr, *AssetPath) || FindObject<UObject>(nullptr, *ObjectPath(AssetPath)) || IFileManager::Get().FileExists(*DestinationFile))
                    return Fail(TEXT("asset_exists"), TEXT("Material-instance destinations cannot overwrite an existing asset."));
                Target = Parent;
            }
            else
            {
                Target = FindObject<UMaterialInstanceConstant>(nullptr, *ObjectPath(AssetPath));
                if (!IsValid(Target)) return Fail(TEXT("material_instance_not_loaded"), TEXT("Load the exact existing material instance in the Editor before preview."));
                const FString TargetState = Fingerprint(Target);
                const FTrackedInstance* ExistingTrack = TrackedInstances.Find(AssetPath);
                if (Target->GetOutermost()->IsDirty() &&
                    (!ExistingTrack || ExistingTrack->Instance.Get() != Target || ExistingTrack->Fingerprint != TargetState))
                    return Fail(TEXT("package_dirty"), TEXT("The existing instance package has changes not accounted for by this ForgeMCP session; save or revert them before editing."));
                Parent = Target->GetMaterial();
                if (!IsValid(Parent)) return Fail(TEXT("invalid_parent"), TEXT("The material instance has no valid parent."));
            }
            FString ValidationCode, ValidationMessage;
            if (!ValidateParameters(Parent, *Parameters, ValidationCode, ValidationMessage))
            { Code = ValidationCode; Message = ValidationMessage; return false; }
            const FString State = Fingerprint(Target);
            if (State.IsEmpty()) return Fail(TEXT("invalid_native_result"), TEXT("The target material state could not be fingerprinted."));
            for (auto It = Previews.CreateIterator(); It; ++It) if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired material-instance previews are allowed."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FPreview Plan;
            Plan.Request = Recipe;
            Plan.Target = Target;
            Plan.Parent = Parent;
            Plan.Fingerprint = State;
            Plan.bCreate = bCreate;
            Plan.Expires = FPlatformTime::Seconds() + 300;
            Previews.Add(Id, MoveTemp(Plan));
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetObjectField(TEXT("changes"), Recipe);
            Data->SetStringField(TEXT("parent_path"), Parent->GetPathName());
            Data->SetBoolField(TEXT("creates_asset"), bCreate);
            Data->SetBoolField(TEXT("overwrites_existing_asset"), false);
            Data->SetBoolField(TEXT("saves_asset"), false);
            Data->SetBoolField(TEXT("static_permutation_rebuilt"), false);
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            return true;
        }

        if (bApply || bSaveApply)
        {
            if (Args->Values.Num() != 2 || !Args->TryGetStringField(TEXT("preview_id"), PreviewId) ||
                !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || PreviewId != Confirmation)
                return Fail(TEXT("confirmation_required"), TEXT("Confirmation must match the reviewed material-instance preview."));
        }
        else if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("asset_path"), AssetPath) || !ValidAssetPackage(AssetPath))
            return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact material-instance package path."));

        if (bSavePreview || bSaveApply)
        {
            UMaterialInstanceConstant* Instance = bSavePreview ? FindObject<UMaterialInstanceConstant>(nullptr, *ObjectPath(AssetPath)) : nullptr;
            FString State;
            FString Filename;
            FTrackedInstance* Tracked = nullptr;
            if (bSavePreview)
            {
                Tracked = TrackedInstances.Find(AssetPath);
                if (!IsValid(Instance) || !Tracked || Tracked->Instance.Get() != Instance)
                    return Fail(TEXT("save_not_authorized"), TEXT("Only a material instance created or updated by ForgeMCP in this bridge session can be saved."));
                if (Tracked->Fingerprint != Fingerprint(Instance))
                    return Fail(TEXT("unreviewed_instance_change"), TEXT("The tracked instance changed outside its reviewed ForgeMCP operation; inspect and preview the current state first."));
                if (!InstanceFilename(Instance, Filename))
                    return Fail(TEXT("invalid_asset_path"), TEXT("Unreal could not resolve the exact material-instance package file."));
                if (!Instance->GetOutermost()->IsDirty())
                    return Fail(TEXT("no_unsaved_changes"), TEXT("The tracked material instance has no unsaved changes."));
                const bool bFileExists = IFileManager::Get().FileExists(*Filename);
                if (Tracked->bCreated == bFileExists)
                    return Fail(TEXT("asset_state_changed"), TEXT("The created/existing package state changed; no save was attempted."));
                if (!Tracked->bCreated && FileFingerprint(Filename).IsEmpty())
                    return Fail(TEXT("backup_unavailable"), TEXT("The existing material-instance package could not be fingerprinted."));
                State = Fingerprint(Instance);
            }
            FPreview Plan;
            if (bSavePreview)
            {
                for (auto It = Previews.CreateIterator(); It; ++It)
                    if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
                if (Previews.Num() >= 32)
                    return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired material-instance previews are allowed."));
                if (Tracked->bCreated && IFileManager::Get().FileExists(*Filename))
                    return Fail(TEXT("asset_exists"), TEXT("The new instance package already exists on disk."));
                Plan.Request = MakeShared<FJsonObject>();
                Plan.Target = Instance;
                Plan.Fingerprint = State;
                Plan.bSave = true;
                Plan.bSaveExisting = !Tracked->bCreated;
                Plan.DiskFingerprint = Plan.bSaveExisting ? FileFingerprint(Filename) : FString();
                const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
                if (Plan.bSaveExisting)
                {
                    const FString BackupDirectory = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("ForgeMCP"), TEXT("Backups"), TEXT("MaterialInstances"));
                    Plan.BackupPath = FPaths::Combine(BackupDirectory, Id + FPackageName::GetAssetPackageExtension());
                }
                Plan.Expires = FPlatformTime::Seconds() + 300;
                Previews.Add(Id, MoveTemp(Plan));
                const FPreview& StoredPlan = Previews.FindChecked(Id);
                Data->SetStringField(TEXT("preview_id"), Id);
                Data->SetStringField(TEXT("asset_path"), AssetPath);
                Data->SetStringField(TEXT("parent_path"), GetPathNameSafe(Instance->Parent));
                Data->SetBoolField(TEXT("overwrites_existing_asset"), !Tracked->bCreated);
                Data->SetBoolField(TEXT("backup_required"), !Tracked->bCreated);
                if (!Tracked->bCreated)
                {
                    Data->SetStringField(TEXT("backup_path"), StoredPlan.BackupPath);
                    Data->SetStringField(TEXT("current_package_fingerprint"), StoredPlan.DiskFingerprint);
                }
                Data->SetNumberField(TEXT("expires_in_seconds"), 300);
                return true;
            }
            FPreview* Stored = Previews.Find(PreviewId);
            if (!Stored || !Stored->bSave || Stored->Expires <= FPlatformTime::Seconds())
                return Fail(TEXT("preview_not_found"), TEXT("The save preview expired or was consumed."));
            Plan = *Stored; Previews.Remove(PreviewId);
            Instance = Cast<UMaterialInstanceConstant>(Plan.Target.Get());
            const FString PackagePath = IsValid(Instance) ? Instance->GetOutermost()->GetName() : FString();
            Tracked = TrackedInstances.Find(PackagePath);
            if (!IsValid(Instance) || !Tracked || Tracked->Instance.Get() != Instance ||
                Fingerprint(Instance) != Plan.Fingerprint || !InstanceFilename(Instance, Filename) ||
                !Instance->GetOutermost()->IsDirty() || Tracked->bCreated == IFileManager::Get().FileExists(*Filename))
                return Fail(TEXT("stale_preview"), TEXT("The tracked instance, dirty state or package state changed after save preview."));
            if (Plan.bSaveExisting)
            {
                if (Tracked->bCreated || Plan.DiskFingerprint.IsEmpty() ||
                    FileFingerprint(Filename) != Plan.DiskFingerprint || Plan.BackupPath.IsEmpty())
                    return Fail(TEXT("stale_preview"), TEXT("The existing package changed after preview; no overwrite was attempted."));
                const FString BackupDirectory = FPaths::GetPath(Plan.BackupPath);
                if (!IFileManager::Get().MakeDirectory(*BackupDirectory, true) ||
                    IFileManager::Get().Copy(*Plan.BackupPath, *Filename, false, false) != COPY_OK ||
                    FileFingerprint(Plan.BackupPath) != Plan.DiskFingerprint)
                    return Fail(TEXT("backup_failed"), TEXT("The original package could not be backed up and verified; no save was attempted."));
            }
            else if (!Tracked->bCreated || IFileManager::Get().FileExists(*Filename))
                return Fail(TEXT("asset_exists"), TEXT("A new instance cannot overwrite an existing package."));
            FSavePackageArgs SaveArgs;
            SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
            SaveArgs.SaveFlags = SAVE_NoError;
            const bool bSaveCallSucceeded = UPackage::SavePackage(Instance->GetOutermost(), Instance, *Filename, SaveArgs);
            const bool bSaved = bSaveCallSucceeded && !FileFingerprint(Filename).IsEmpty();
            const bool bBackupAvailable = Plan.bSaveExisting && FileFingerprint(Plan.BackupPath) == Plan.DiskFingerprint;
            bool bDiskRestored = false;
            if (!bSaved && bBackupAvailable)
            {
                bDiskRestored = IFileManager::Get().Copy(*Filename, *Plan.BackupPath, true, true) == COPY_OK &&
                    FileFingerprint(Filename) == Plan.DiskFingerprint;
            }
            Data->SetStringField(TEXT("asset_path"), Instance->GetPathName());
            Data->SetBoolField(TEXT("saved"), bSaved);
            const TCHAR* SaveState = bSaved ? TEXT("saved") :
                (Plan.bSaveExisting ? (bDiskRestored ? TEXT("partial_memory_dirty_disk_restored") : TEXT("partial_backup_retained")) : TEXT("save_failed"));
            Data->SetStringField(TEXT("state"), SaveState);
            Data->SetStringField(TEXT("filename"), FPaths::ConvertRelativePathToFull(Filename));
            Data->SetBoolField(TEXT("overwrote_existing_asset"), Plan.bSaveExisting);
            if (Plan.bSaveExisting) Data->SetStringField(TEXT("backup_path"), Plan.BackupPath);
            if (!bSaved)
            {
                Data->SetBoolField(TEXT("disk_restored"), bDiskRestored);
                Data->SetStringField(TEXT("diagnostic"), TEXT("Unreal could not save the material instance. The original package backup was retained; inspect disk and in-memory state before retry."));
            }
            else TrackedInstances.Remove(PackagePath);
            return true;
        }

        FPreview* Stored = Previews.Find(PreviewId);
        if (!Stored || Stored->bSave || Stored->Expires <= FPlatformTime::Seconds())
            return Fail(TEXT("preview_not_found"), TEXT("The material-instance preview expired or was consumed."));
        FPreview Plan = *Stored; Previews.Remove(PreviewId);
        UMaterialInterface* Target = Plan.Target.Get();
        UMaterialInterface* Parent = Plan.Parent.Get();
        if (!IsValid(Target) || !IsValid(Parent) || Fingerprint(Target) != Plan.Fingerprint)
            return Fail(TEXT("stale_preview"), TEXT("The target or parent changed after preview."));
        const TArray<TSharedPtr<FJsonValue>>* Parameters = nullptr;
        if (!Plan.Request->TryGetArrayField(TEXT("parameters"), Parameters))
            return Fail(TEXT("invalid_preview"), TEXT("The reviewed parameters are unavailable."));
        FString ValidationCode, ValidationMessage;
        if (!ValidateParameters(Plan.bCreate ? Parent : Target, *Parameters, ValidationCode, ValidationMessage))
        { Code = ValidationCode; Message = ValidationMessage; return false; }
        UMaterialInstanceConstant* Instance = Cast<UMaterialInstanceConstant>(Target);
        bool bCreated = false;
        const FString InstancePackagePath = Field(Plan.Request.ToSharedRef(), TEXT("asset_path"));
        const FTrackedInstance* PreviouslyTracked = TrackedInstances.Find(InstancePackagePath);
        const bool bSessionCreated = PreviouslyTracked && PreviouslyTracked->Instance.Get() == Instance && PreviouslyTracked->bCreated;
        const FScopedTransaction Transaction(NSLOCTEXT("ForgeMCP", "MaterialInstanceEdit", "ForgeMCP material instance"));
        if (Plan.bCreate)
        {
            const FString PackagePath = Field(Plan.Request.ToSharedRef(), TEXT("asset_path"));
            FString DestinationFile;
            FPackageName::TryConvertLongPackageNameToFilename(PackagePath, DestinationFile, FPackageName::GetAssetPackageExtension());
            if (FindPackage(nullptr, *PackagePath) || FindObject<UObject>(nullptr, *ObjectPath(PackagePath)) ||
                IFileManager::Get().FileExists(*DestinationFile))
                return Fail(TEXT("asset_exists"), TEXT("The reviewed destination package appeared after preview; no overwrite was attempted."));
            UPackage* Package = CreatePackage(*PackagePath);
            Instance = Package ? NewObject<UMaterialInstanceConstant>(Package, *FPackageName::GetLongPackageAssetName(PackagePath), RF_Public | RF_Standalone | RF_Transactional) : nullptr;
            if (!IsValid(Instance)) return Fail(TEXT("creation_failed"), TEXT("Unreal could not create the material-instance asset."));
            Instance->Modify();
            Instance->SetParentEditorOnly(Parent, false);
            bCreated = true;
        }
        else Instance->Modify();
        if (!Instance) return Fail(TEXT("invalid_native_result"), TEXT("No material instance was available after preview."));
        ApplyParameters(Instance, *Parameters);
        if (bCreated)
        {
            FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get().AssetCreated(Instance);
        }
        TrackedInstances.Add(Instance->GetOutermost()->GetName(), {Instance, bCreated || bSessionCreated, Fingerprint(Instance)});
        Data->SetStringField(TEXT("asset_path"), Instance->GetPathName());
        Data->SetStringField(TEXT("parent_path"), GetPathNameSafe(Instance->Parent));
        Data->SetNumberField(TEXT("override_count"), Parameters->Num());
        Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("overwrites_existing_asset"), false);
        return true;
    }

    FString Path;
    if (Args->Values.Num() != 1 || !Args->TryGetStringField(TEXT("asset_path"), Path) || !ValidAssetPackage(Path))
        return Fail(TEXT("invalid_arguments"), TEXT("Expected one exact loaded material-instance package path."));
    UMaterialInstanceConstant* Instance = FindObject<UMaterialInstanceConstant>(nullptr, *ObjectPath(Path));
    if (!IsValid(Instance)) return Fail(TEXT("material_instance_not_loaded"), TEXT("The exact UMaterialInstanceConstant must already be loaded."));
    Data->SetStringField(TEXT("asset_path"), Instance->GetPathName());
    Data->SetStringField(TEXT("parent_path"), GetPathNameSafe(Instance->Parent));
    TArray<JObject> Values;
    FString State;
    AddParameterValues(Instance, EMaterialParameterType::Scalar, Values, State);
    AddParameterValues(Instance, EMaterialParameterType::Vector, Values, State);
    AddParameterValues(Instance, EMaterialParameterType::Texture, Values, State);
    if (Values.Num() > 512) return Fail(TEXT("limit_exceeded"), TEXT("Material instance exposes more than 512 supported parameters."));
    TArray<TSharedPtr<FJsonValue>> Array;
    for (const JObject& Value : Values) Array.Add(MakeShared<FJsonValueObject>(Value));
    Data->SetArrayField(TEXT("parameters"), Array);
    Data->SetStringField(TEXT("supported_parameter_types"), TEXT("scalar, vector, texture"));
    Data->SetStringField(TEXT("unsupported_parameter_types"), TEXT("static switches, static masks, double vectors, runtime virtual textures, sparse volume textures, texture collections and font parameters"));
    return true;
}
