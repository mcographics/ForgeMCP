#include "ForgeStructTooltips.h"

#include "Engine/UserDefinedStruct.h"
#include "EdGraphSchema_K2.h"
#include "HAL/FileManager.h"
#include "Kismet2/StructureEditorUtils.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "UObject/SavePackage.h"

namespace
{
constexpr int32 MaxTooltips = 256;
constexpr int32 MaxTooltipChars = 1024;

FString Fingerprint(const UUserDefinedStruct* Struct)
{
    FString State;
    for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
    {
        const FEdGraphPinType Type = Variable.ToPinType();
        State += Variable.VarGuid.ToString(EGuidFormats::Digits);
        State += TEXT("|");
        State += Variable.FriendlyName;
        State += TEXT("|");
        State += Type.PinCategory.ToString();
        State += TEXT("|");
        State += Type.PinSubCategory.ToString();
        State += TEXT("|");
        State += LexToString(static_cast<uint8>(Type.ContainerType));
        State += TEXT("|");
        State += FStructureEditorUtils::GetVariableTooltip(Struct, Variable.VarGuid);
        State += TEXT("\n");
    }
    FTCHARToUTF8 Utf8(*State);
    FMD5 Md5;
    Md5.Update(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    uint8 Digest[16];
    Md5.Final(Digest);
    return BytesToHex(Digest, UE_ARRAY_COUNT(Digest));
}

bool SaveStruct(UUserDefinedStruct* Struct, FString& OutFilename)
{
    if (!Struct || !Struct->GetOutermost()) return false;
    OutFilename = FPackageName::LongPackageNameToFilename(
        Struct->GetOutermost()->GetName(), FPackageName::GetAssetPackageExtension());
    FSavePackageArgs SaveArgs;
    SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
    SaveArgs.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Struct->GetOutermost(), Struct, *OutFilename, SaveArgs);
}
}

bool FForgeStructTooltips::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    { ErrorCode = Code; ErrorMessage = Message; return false; };
    if (!IsInGameThread()) return Fail(TEXT("invalid_context"), TEXT("Struct tooltip edits require the Editor game thread."));
    const bool bPreview = Command == TEXT("struct_tooltips_preview");
    const bool bApply = Command == TEXT("struct_tooltips_apply");
    if (!bPreview && !bApply) return Fail(TEXT("unknown_command"), TEXT("Unsupported struct tooltip command."));

    for (auto It = Previews.CreateIterator(); It; ++It)
        if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();

    FString PreviewId, Confirmation;
    if (bPreview)
    {
        static const TSet<FString> Allowed = { TEXT("struct_path"), TEXT("tooltips") };
        for (const auto& Pair : Args->Values)
            if (!Allowed.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown struct tooltip preview field."));

        FString StructPath;
        const TSharedPtr<FJsonObject>* TooltipObject = nullptr;
        if (!Args->TryGetStringField(TEXT("struct_path"), StructPath) ||
            !Args->TryGetObjectField(TEXT("tooltips"), TooltipObject) || !TooltipObject->IsValid())
            return Fail(TEXT("invalid_arguments"), TEXT("struct_path and a tooltips object are required."));
        if (StructPath.Len() > 240 || !FPackageName::IsValidLongPackageName(StructPath) || !StructPath.StartsWith(TEXT("/Game/")))
            return Fail(TEXT("unsupported_asset_path"), TEXT("Struct path must be an existing /Game package."));
        if ((*TooltipObject)->Values.Num() == 0 || (*TooltipObject)->Values.Num() > MaxTooltips)
            return Fail(TEXT("tooltip_count_limit"), TEXT("Provide between 1 and 256 member tooltips."));

        const FString ObjectPath = StructPath + TEXT(".") + FPackageName::GetLongPackageAssetName(StructPath);
        UUserDefinedStruct* Struct = LoadObject<UUserDefinedStruct>(nullptr, *ObjectPath);
        if (!Struct || FStructureEditorUtils::IsStructureValid(Struct) != FStructureEditorUtils::Ok)
            return Fail(TEXT("invalid_user_defined_struct"), TEXT("Target must be a valid loaded User Defined Struct."));
        if (Struct->GetOutermost()->IsDirty())
            return Fail(TEXT("package_dirty"), TEXT("Save or revert existing struct edits before previewing tooltip changes."));

        FPreview Preview;
        Preview.StructPath = StructPath;
        Preview.Expires = FPlatformTime::Seconds() + 300;
        Preview.SchemaFingerprint = Fingerprint(Struct);

        TArray<TSharedPtr<FJsonValue>> Changes;
        for (const auto& Pair : (*TooltipObject)->Values)
        {
            FString Tooltip;
            if (!Pair.Value.IsValid() || !Pair.Value->TryGetString(Tooltip) || Tooltip.TrimStartAndEnd().IsEmpty() || Tooltip.Len() > MaxTooltipChars)
                return Fail(TEXT("invalid_tooltip"), TEXT("Every tooltip must be nonempty text up to 1024 characters."));
            const FStructVariableDescription* Match = nullptr;
            for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
                if (!Variable.bInvalidMember && Variable.FriendlyName == Pair.Key) { Match = &Variable; break; }
            if (!Match)
                return Fail(TEXT("unknown_struct_member"), TEXT("A tooltip key does not exactly match a valid struct member name."));

            Preview.Tooltips.Add(Pair.Key, Tooltip);
            auto Change = MakeShared<FJsonObject>();
            Change->SetStringField(TEXT("member"), Pair.Key);
            Change->SetStringField(TEXT("previous_tooltip"), FStructureEditorUtils::GetVariableTooltip(Struct, Match->VarGuid));
            Change->SetStringField(TEXT("new_tooltip"), Tooltip);
            Changes.Add(MakeShared<FJsonValueObject>(Change));
        }
        if (Previews.Num() >= 16) return Fail(TEXT("preview_limit"), TEXT("Too many pending struct tooltip previews."));

        PreviewId = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        Previews.Add(PreviewId, MoveTemp(Preview));
        Data->SetStringField(TEXT("preview_id"), PreviewId);
        Data->SetStringField(TEXT("struct_path"), StructPath);
        Data->SetNumberField(TEXT("member_count"), Changes.Num());
        Data->SetArrayField(TEXT("changes"), Changes);
        Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        return true;
    }

    FString StructPath;
    static const TSet<FString> ApplyFields = { TEXT("preview_id"), TEXT("confirmation") };
    for (const auto& Pair : Args->Values)
        if (!ApplyFields.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown struct tooltip apply field."));
    if (!Args->TryGetStringField(TEXT("preview_id"), PreviewId) ||
        !Args->TryGetStringField(TEXT("confirmation"), Confirmation) ||
        PreviewId.IsEmpty() || PreviewId != Confirmation)
        return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));

    FPreview Preview;
    if (!Previews.RemoveAndCopyValue(PreviewId, Preview) || Preview.Expires <= FPlatformTime::Seconds())
        return Fail(TEXT("preview_not_found"), TEXT("Struct tooltip preview is missing, expired, or already used."));
    const FString ObjectPath = Preview.StructPath + TEXT(".") + FPackageName::GetLongPackageAssetName(Preview.StructPath);
    UUserDefinedStruct* Struct = LoadObject<UUserDefinedStruct>(nullptr, *ObjectPath);
    if (!Struct || Fingerprint(Struct) != Preview.SchemaFingerprint)
        return Fail(TEXT("stale_struct_preview"), TEXT("Struct members or tooltips changed after preview; inspect and preview again."));
    if (Struct->GetOutermost()->IsDirty())
        return Fail(TEXT("package_dirty"), TEXT("The struct package became dirty after preview; save or revert it and preview again."));

    const FString Filename = FPackageName::LongPackageNameToFilename(Preview.StructPath, FPackageName::GetAssetPackageExtension());
    TArray<uint8> Backup;
    if (!FFileHelper::LoadFileToArray(Backup, *Filename))
        return Fail(TEXT("backup_failed"), TEXT("Could not read a rollback copy of the existing struct package."));

    TMap<FGuid, FString> Previous;
    for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
    {
        if (const FString* Tooltip = Preview.Tooltips.Find(Variable.FriendlyName))
        {
            Previous.Add(Variable.VarGuid, FStructureEditorUtils::GetVariableTooltip(Struct, Variable.VarGuid));
            if (!FStructureEditorUtils::ChangeVariableTooltip(Struct, Variable.VarGuid, *Tooltip))
            {
                for (const auto& Restore : Previous) FStructureEditorUtils::ChangeVariableTooltip(Struct, Restore.Key, Restore.Value);
                return Fail(TEXT("tooltip_edit_failed"), TEXT("Unreal rejected a member tooltip edit; no package was saved."));
            }
        }
    }
    FString SavedFilename;
    if (!SaveStruct(Struct, SavedFilename))
    {
        for (const auto& Restore : Previous) FStructureEditorUtils::ChangeVariableTooltip(Struct, Restore.Key, Restore.Value);
        if (!FFileHelper::SaveArrayToFile(Backup, *Filename))
            return Fail(TEXT("rollback_failed"), TEXT("Struct save failed and restoring its original package bytes also failed; inspect the asset before continuing."));
        Struct->GetOutermost()->SetDirtyFlag(false);
        return Fail(TEXT("asset_save_failed"), TEXT("Could not save the struct; original package bytes were restored."));
    }
    Struct->GetOutermost()->SetDirtyFlag(false);

    TArray<TSharedPtr<FJsonValue>> Updated;
    for (const auto& Pair : Preview.Tooltips) Updated.Add(MakeShared<FJsonValueString>(Pair.Key));
    Data->SetStringField(TEXT("struct_path"), Struct->GetPathName());
    Data->SetNumberField(TEXT("updated_tooltip_count"), Updated.Num());
    Data->SetArrayField(TEXT("updated_members"), Updated);
    Data->SetBoolField(TEXT("saved"), true);
    return true;
}
