#include "ForgeCsvImport.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "EdGraphSchema_K2.h"
#include "Engine/DataTable.h"
#include "Engine/UserDefinedStruct.h"
#include "HAL/PlatformFileManager.h"
#include "HAL/FileManager.h"
#include "Kismet2/StructureEditorUtils.h"
#include "UserDefinedStructure/UserDefinedStructEditorData.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Serialization/Csv/CsvParser.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace
{
constexpr int64 MaxCsvBytes = 128ll * 1024 * 1024;
constexpr int32 MaxCsvRows = 200000;
constexpr int32 MaxCsvColumns = 256;

struct FCsvPlan
{
    FString AbsolutePath;
    FString Hash;
    FString Key;
    int32 RowCount = 0;
    TArray<FString> Headers;
    TArray<FString> Types;
};

bool IsIdentifier(const FString& Text)
{
    if (Text.IsEmpty() || Text.Len() > 64 || !(FChar::IsAlpha(Text[0]) || Text[0] == TEXT('_'))) return false;
    for (TCHAR C : Text) if (!(FChar::IsAlnum(C) || C == TEXT('_'))) return false;
    return true;
}

bool IsIntegerToken(const FString& Text)
{
    if (Text.IsEmpty()) return false;
    int32 Index = (Text[0] == TEXT('+') || Text[0] == TEXT('-')) ? 1 : 0;
    if (Index == Text.Len()) return false;
    for (; Index < Text.Len(); ++Index)
        if (Text[Index] < TEXT('0') || Text[Index] > TEXT('9')) return false;
    return true;
}

bool IsNumericToken(const FString& Text)
{
    if (Text.IsEmpty()) return false;
    int32 Index = (Text[0] == TEXT('+') || Text[0] == TEXT('-')) ? 1 : 0;
    int32 IntegerDigits = 0;
    while (Index < Text.Len() && Text[Index] >= TEXT('0') && Text[Index] <= TEXT('9'))
    { ++IntegerDigits; ++Index; }
    int32 FractionDigits = 0;
    if (Index < Text.Len() && Text[Index] == TEXT('.'))
    {
        ++Index;
        while (Index < Text.Len() && Text[Index] >= TEXT('0') && Text[Index] <= TEXT('9'))
        { ++FractionDigits; ++Index; }
    }
    if (IntegerDigits + FractionDigits == 0) return false;
    if (Index < Text.Len() && (Text[Index] == TEXT('e') || Text[Index] == TEXT('E')))
    {
        ++Index;
        if (Index < Text.Len() && (Text[Index] == TEXT('+') || Text[Index] == TEXT('-'))) ++Index;
        const int32 ExponentStart = Index;
        while (Index < Text.Len() && Text[Index] >= TEXT('0') && Text[Index] <= TEXT('9')) ++Index;
        if (Index == ExponentStart) return false;
    }
    return Index == Text.Len();
}

bool IsUnderProject(const FString& Candidate, FString& Absolute)
{
    Absolute = FPaths::ConvertRelativePathToFull(Candidate);
    FPaths::NormalizeFilename(Absolute);
    FString Root = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
    FPaths::NormalizeDirectoryName(Root);
    FString Relative = Absolute;
    if (!FPaths::MakePathRelativeTo(Relative, *Root)) return false;
    FPaths::NormalizeFilename(Relative);
    return !Relative.StartsWith(TEXT("../")) && Relative != TEXT("..") && !Relative.StartsWith(TEXT("/"));
}

bool ReadCsv(const FString& InputPath, const TSharedRef<FJsonObject>& Overrides,
    const FString& KeyColumn, FCsvPlan& Out, FString& Code, FString& Message)
{
    auto Fail = [&](const TCHAR* InCode, const TCHAR* InMessage)
    { Code = InCode; Message = InMessage; return false; };
    if (!IsUnderProject(InputPath, Out.AbsolutePath) || FPaths::GetExtension(Out.AbsolutePath).ToLower() != TEXT("csv"))
        return Fail(TEXT("unsupported_csv_path"), TEXT("CSV access is limited to .csv files inside the connected project."));
    const int64 FileSize = IFileManager::Get().FileSize(*Out.AbsolutePath);
    if (FileSize <= 0 || FileSize > MaxCsvBytes)
        return Fail(TEXT("csv_size_limit"), TEXT("CSV must be nonempty and no larger than 128 MiB."));
    FString Csv;
    if (!FFileHelper::LoadFileToString(Csv, *Out.AbsolutePath))
        return Fail(TEXT("csv_read_failed"), TEXT("The selected project CSV could not be read."));
    const FMD5Hash FileHash = FMD5Hash::HashFile(*Out.AbsolutePath);
    if (!FileHash.IsValid()) return Fail(TEXT("csv_hash_failed"), TEXT("Could not fingerprint the CSV for a stable preview."));
    Out.Hash = BytesToHex(FileHash.GetBytes(), FileHash.GetSize());
    FCsvParser Parser(MoveTemp(Csv));
    const FCsvParser::FRows& Rows = Parser.GetRows();
    if (Rows.Num() < 2 || Rows.Num() > MaxCsvRows + 1 || Rows[0].Num() < 2 || Rows[0].Num() > MaxCsvColumns)
        return Fail(TEXT("csv_shape_limit"), TEXT("CSV must contain a header, at least one row, no more than 200000 rows and at most 256 columns."));

    TSet<FString> UniqueHeaders;
    for (const TCHAR* Header : Rows[0])
    {
        const FString Name(Header ? Header : TEXT(""));
        if (!IsIdentifier(Name) || UniqueHeaders.Contains(Name.ToLower()))
            return Fail(TEXT("invalid_csv_header"), TEXT("CSV headers must be unique Unreal identifiers up to 64 characters."));
        UniqueHeaders.Add(Name.ToLower());
        Out.Headers.Add(Name);
    }
    if (!Out.Headers.Contains(KeyColumn))
        return Fail(TEXT("row_key_not_found"), TEXT("row_key_column must match one CSV header exactly."));
    if (Out.Headers.Contains(TEXT("Name")) && KeyColumn != TEXT("Name"))
        return Fail(TEXT("reserved_csv_header"), TEXT("A non-key Name column conflicts with Unreal's DataTable row identifier."));

    TArray<TSet<FName>> RowKeys;
    TSet<FName> SeenRows;
    Out.RowCount = Rows.Num() - 1;
    RowKeys.Reserve(Out.RowCount);
    for (int32 R = 1; R < Rows.Num(); ++R)
    {
        if (Rows[R].Num() != Out.Headers.Num())
            return Fail(TEXT("csv_row_width_mismatch"), TEXT("Every CSV record must contain exactly the header column count."));
        const FString RowKey(Rows[R][Out.Headers.IndexOfByKey(KeyColumn)]);
        if (RowKey.IsEmpty() || RowKey.Len() > 1024 || SeenRows.Contains(FName(*RowKey)))
            return Fail(TEXT("invalid_csv_row_key"), TEXT("DataTable row keys must be nonempty, unique, and at most 1024 characters."));
        SeenRows.Add(FName(*RowKey));
    }

    for (int32 C = 0; C < Out.Headers.Num(); ++C)
    {
        const FString& Header = Out.Headers[C];
        if (Header == KeyColumn) { Out.Types.Add(TEXT("row_key")); continue; }
        FString OverrideType;
        const bool HasOverride = Overrides->Values.Contains(Header);
        if (HasOverride && !Overrides->TryGetStringField(Header, OverrideType))
            return Fail(TEXT("invalid_type_override"), TEXT("Each type override value must be a string."));
        bool Any = false, AllBool = true, AllInteger = true, AllNumeric = true;
        bool IntegerOverflow32 = false;
        for (int32 R = 1; R < Rows.Num(); ++R)
        {
            const FString Cell(Rows[R][C]);
            if (Cell.IsEmpty()) continue;
            Any = true;
            const FString Lower = Cell.ToLower();
            AllBool &= Lower == TEXT("true") || Lower == TEXT("false");
            int64 IntValue = 0;
            const bool IsInteger = IsIntegerToken(Cell) && LexTryParseString(IntValue, *Cell);
            AllInteger &= IsInteger;
            if (IsInteger && (IntValue < MIN_int32 || IntValue > MAX_int32)) IntegerOverflow32 = true;
            double Number = 0;
            AllNumeric &= IsNumericToken(Cell) && LexTryParseString(Number, *Cell) && FMath::IsFinite(Number);
        }
        FString Inferred = !Any ? TEXT("string") : AllBool ? TEXT("bool") :
            AllInteger ? (IntegerOverflow32 ? TEXT("int64") : TEXT("int")) :
            AllNumeric ? TEXT("double") : TEXT("string");
        if (HasOverride)
        {
            static const TSet<FString> Allowed = {TEXT("string"), TEXT("name"), TEXT("bool"), TEXT("int"), TEXT("int64"), TEXT("double")};
            if (!Allowed.Contains(OverrideType))
                return Fail(TEXT("invalid_type_override"), TEXT("Type overrides must be string, name, bool, int, int64, or double."));
            Inferred = OverrideType;
        }
        Out.Types.Add(Inferred);
    }
    for (const auto& Pair : Overrides->Values)
    {
        if (Pair.Key == KeyColumn)
            return Fail(TEXT("invalid_type_override"), TEXT("The DataTable row-key column is not a struct member and cannot have a type override."));
        if (!UniqueHeaders.Contains(Pair.Key.ToLower()))
            return Fail(TEXT("unknown_type_override"), TEXT("A type override names a column absent from the CSV."));
    }
    Out.Key = KeyColumn;
    return true;
}

FEdGraphPinType PinType(const FString& Type)
{
    if (Type == TEXT("bool")) return FEdGraphPinType(UEdGraphSchema_K2::PC_Boolean, NAME_None, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
    if (Type == TEXT("int")) return FEdGraphPinType(UEdGraphSchema_K2::PC_Int, NAME_None, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
    if (Type == TEXT("int64")) return FEdGraphPinType(UEdGraphSchema_K2::PC_Int64, NAME_None, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
    if (Type == TEXT("double")) return FEdGraphPinType(UEdGraphSchema_K2::PC_Real, UEdGraphSchema_K2::PC_Double, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
    if (Type == TEXT("name")) return FEdGraphPinType(UEdGraphSchema_K2::PC_Name, NAME_None, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
    return FEdGraphPinType(UEdGraphSchema_K2::PC_String, NAME_None, nullptr, EPinContainerType::None, false, FEdGraphTerminalType());
}

FString PinTypeName(const FEdGraphPinType& Type)
{
    if (Type.ContainerType != EPinContainerType::None) return TEXT("unsupported");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_Boolean) return TEXT("bool");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_Int) return TEXT("int");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_Int64) return TEXT("int64");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_Real && Type.PinSubCategory == UEdGraphSchema_K2::PC_Double) return TEXT("double");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_Name) return TEXT("name");
    if (Type.PinCategory == UEdGraphSchema_K2::PC_String) return TEXT("string");
    return TEXT("unsupported");
}

FString StructSchemaFingerprint(const UUserDefinedStruct* Struct)
{
    FString Schema;
    for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
    {
        const FEdGraphPinType Type = Variable.ToPinType();
        Schema += Variable.FriendlyName;
        Schema += TEXT("|");
        Schema += Type.PinCategory.ToString();
        Schema += TEXT("|");
        Schema += Type.PinSubCategory.ToString();
        Schema += TEXT("|");
        Schema += LexToString(static_cast<uint8>(Type.ContainerType));
        Schema += TEXT("|");
        Schema += Type.PinSubCategoryObject.IsValid() ? Type.PinSubCategoryObject->GetPathName() : FString();
        Schema += TEXT("\n");
    }
    FTCHARToUTF8 Utf8(*Schema);
    FMD5 Md5;
    Md5.Update(reinterpret_cast<const uint8*>(Utf8.Get()), Utf8.Length());
    uint8 Digest[16];
    Md5.Final(Digest);
    return BytesToHex(Digest, UE_ARRAY_COUNT(Digest));
}

bool IsDefaultPlaceholder(const FStructVariableDescription& Variable)
{
    const FString& Name = Variable.FriendlyName;
    return Name == TEXT("NewVar") || Name.StartsWith(TEXT("NewVar_")) ||
        Name == TEXT("MemberVar_0") || Name.StartsWith(TEXT("MemberVar_0_"));
}

bool ValidateExistingStruct(UUserDefinedStruct* Struct, const FCsvPlan& Csv, FString& Code, FString& Message)
{
    if (!Struct || FStructureEditorUtils::IsStructureValid(Struct) != FStructureEditorUtils::Ok)
    {
        Code = TEXT("invalid_existing_struct");
        Message = TEXT("The existing User Defined Struct is not valid for a DataTable.");
        return false;
    }
    for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
    {
        if (Variable.bInvalidMember) continue;
        const int32 CsvIndex = Csv.Headers.IndexOfByKey(Variable.FriendlyName);
        if (CsvIndex == INDEX_NONE || Csv.Headers[CsvIndex] == Csv.Key) continue;
        const FString ExistingType = PinTypeName(Variable.ToPinType());
        if (ExistingType != Csv.Types[CsvIndex])
        {
            Code = TEXT("struct_type_conflict");
            Message = FString::Printf(TEXT("Existing member '%s' is %s but the CSV requires %s. Existing member types are never changed by this operation."),
                *Variable.FriendlyName, *ExistingType, *Csv.Types[CsvIndex]);
            return false;
        }
    }
    return true;
}

bool SaveAsset(UObject* Asset, FString& Filename)
{
    if (!Asset || !Asset->GetOutermost()) return false;
    const FString PackageName = Asset->GetOutermost()->GetName();
    Filename = FPackageName::LongPackageNameToFilename(PackageName, FPackageName::GetAssetPackageExtension());
    FSavePackageArgs Args;
    Args.TopLevelFlags = RF_Public | RF_Standalone;
    Args.SaveFlags = SAVE_NoError;
    return UPackage::SavePackage(Asset->GetOutermost(), Asset, *Filename, Args);
}

void DeleteNewAsset(UObject* Asset, const FString& Filename)
{
    if (Asset) Asset->MarkAsGarbage();
    if (!Filename.IsEmpty()) IFileManager::Get().Delete(*Filename, false, true);
}
}

bool FForgeCsvImport::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    { ErrorCode = Code; ErrorMessage = Message; return false; };
    if (!IsInGameThread()) return Fail(TEXT("invalid_context"), TEXT("CSV asset operations require the Editor game thread."));
    const bool bPreview = Command == TEXT("csv_import_preview");
    const bool bApply = Command == TEXT("csv_import_apply");
    if (!bPreview && !bApply) return Fail(TEXT("unknown_command"), TEXT("Unsupported CSV import command."));

    for (auto It = Previews.CreateIterator(); It; ++It)
        if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
    FString CsvPath, StructPath, TablePath, KeyColumn, PreviewId, Confirmation;
    TSharedPtr<FJsonObject> Overrides;
    if (bPreview)
    {
        static const TSet<FString> Allowed = {TEXT("csv_path"), TEXT("struct_path"), TEXT("data_table_path"), TEXT("row_key_column"), TEXT("type_overrides")};
        for (const auto& Pair : Args->Values) if (!Allowed.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown CSV preview field."));
        const TSharedPtr<FJsonObject>* OverridesValue = nullptr;
        if (!Args->TryGetStringField(TEXT("csv_path"), CsvPath) ||
            !Args->TryGetStringField(TEXT("struct_path"), StructPath) ||
            !Args->TryGetStringField(TEXT("data_table_path"), TablePath) ||
            !Args->TryGetStringField(TEXT("row_key_column"), KeyColumn))
            return Fail(TEXT("invalid_arguments"), TEXT("csv_path, struct_path, data_table_path, and row_key_column are required."));
        if (Args->TryGetObjectField(TEXT("type_overrides"), OverridesValue) && OverridesValue->IsValid()) Overrides = *OverridesValue;
        if (!Overrides.IsValid()) Overrides = MakeShared<FJsonObject>();
        auto ValidPackagePath = [](const FString& Path)
        { return Path.Len() <= 240 && FPackageName::IsValidLongPackageName(Path) && Path.StartsWith(TEXT("/Game/")); };
        if (!ValidPackagePath(StructPath) || !ValidPackagePath(TablePath) || StructPath == TablePath)
            return Fail(TEXT("unsupported_asset_path"), TEXT("Provide distinct new /Game package paths for the struct and DataTable."));
        IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        const FString StructObjectPath = StructPath + TEXT(".") + FPackageName::GetLongPackageAssetName(StructPath);
        const bool bStructAssetExists = Registry.GetAssetByObjectPath(FSoftObjectPath(StructObjectPath)).IsValid() ||
            IFileManager::Get().FileExists(*FPackageName::LongPackageNameToFilename(StructPath, FPackageName::GetAssetPackageExtension()));
        const bool bTableAssetExists = Registry.GetAssetByObjectPath(FSoftObjectPath(TablePath + TEXT(".") + FPackageName::GetLongPackageAssetName(TablePath))).IsValid() ||
            IFileManager::Get().FileExists(*FPackageName::LongPackageNameToFilename(TablePath, FPackageName::GetAssetPackageExtension()));
        if (bTableAssetExists)
            return Fail(TEXT("asset_exists"), TEXT("The destination DataTable already exists. Import is create-only for DataTables."));
        UUserDefinedStruct* ExistingStruct = bStructAssetExists ? LoadObject<UUserDefinedStruct>(nullptr, *StructObjectPath) : nullptr;
        if (bStructAssetExists && !ExistingStruct)
            return Fail(TEXT("existing_struct_type_mismatch"), TEXT("The existing struct path is not a loadable User Defined Struct asset."));
        FCsvPlan Plan;
        if (!ReadCsv(CsvPath, Overrides.ToSharedRef(), KeyColumn, Plan, ErrorCode, ErrorMessage)) return false;
        if (ExistingStruct && !ValidateExistingStruct(ExistingStruct, Plan, ErrorCode, ErrorMessage)) return false;
        if (Previews.Num() >= 32) return Fail(TEXT("preview_limit"), TEXT("Too many pending CSV previews."));
        PreviewId = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
        FPreview Preview;
        Preview.CsvPath = Plan.AbsolutePath;
        Preview.FileHash = Plan.Hash;
        Preview.StructPath = StructPath;
        Preview.TablePath = TablePath;
        Preview.KeyColumn = KeyColumn;
        Preview.Overrides = Overrides;
        Preview.Expires = FPlatformTime::Seconds() + 300;
        Preview.RowCount = Plan.RowCount;
        Preview.bStructExisted = ExistingStruct != nullptr;
        Preview.StructSchemaFingerprint = ExistingStruct ? StructSchemaFingerprint(ExistingStruct) : FString();
        Previews.Add(PreviewId, MoveTemp(Preview));
        TArray<TSharedPtr<FJsonValue>> Fields;
        int32 FirstDataField = INDEX_NONE;
        for (int32 Index = 0; Index < Plan.Headers.Num(); ++Index)
            if (Plan.Headers[Index] != KeyColumn) { FirstDataField = Index; break; }
        const TArray<FStructVariableDescription>* ExistingVariables = ExistingStruct
            ? &FStructureEditorUtils::GetVarDesc(ExistingStruct) : nullptr;
        const bool bReusePlaceholder = ExistingVariables && ExistingVariables->Num() == 1 &&
            IsDefaultPlaceholder((*ExistingVariables)[0]);
        for (int32 Index = 0; Index < Plan.Headers.Num(); ++Index)
        {
            auto Field = MakeShared<FJsonObject>();
            Field->SetStringField(TEXT("name"), Plan.Headers[Index]);
            Field->SetStringField(TEXT("type"), Plan.Types[Index]);
            Field->SetBoolField(TEXT("row_key"), Plan.Headers[Index] == KeyColumn);
            bool bAlreadyPresent = false;
            if (ExistingStruct && Plan.Headers[Index] != KeyColumn)
                for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(ExistingStruct))
                    if (!Variable.bInvalidMember && Variable.FriendlyName == Plan.Headers[Index]) { bAlreadyPresent = true; break; }
            const bool bReusesDefault = bReusePlaceholder && Index == FirstDataField;
            Field->SetBoolField(TEXT("already_present"), bAlreadyPresent);
            Field->SetStringField(TEXT("planned_action"), Plan.Headers[Index] == KeyColumn ? TEXT("row_key") :
                bAlreadyPresent ? TEXT("preserve") : bReusesDefault ? TEXT("reuse_default_placeholder") : TEXT("add"));
            if (bReusesDefault)
                Field->SetStringField(TEXT("replaces_member"), (*ExistingVariables)[0].FriendlyName);
            Fields.Add(MakeShared<FJsonValueObject>(Field));
        }
        Data->SetStringField(TEXT("preview_id"), PreviewId);
        Data->SetStringField(TEXT("csv_path"), Plan.AbsolutePath);
        Data->SetStringField(TEXT("csv_fingerprint"), Plan.Hash);
        Data->SetStringField(TEXT("struct_path"), StructPath);
        Data->SetStringField(TEXT("data_table_path"), TablePath);
        Data->SetStringField(TEXT("row_key_column"), KeyColumn);
        Data->SetNumberField(TEXT("row_count"), Plan.RowCount);
        Data->SetNumberField(TEXT("column_count"), Plan.Headers.Num());
        Data->SetBoolField(TEXT("existing_struct"), ExistingStruct != nullptr);
        Data->SetStringField(TEXT("struct_change_policy"), TEXT("Add missing CSV members only; preserve existing members; reuse one recognized empty default placeholder for the first data field; reject type conflicts."));
        Data->SetArrayField(TEXT("fields"), Fields);
        Data->SetNumberField(TEXT("expires_in_seconds"), 300);
        return true;
    }

    const TSharedPtr<FJsonObject>* ConfirmationArgs = nullptr;
    if (!Args->TryGetStringField(TEXT("preview_id"), PreviewId) ||
        !Args->TryGetStringField(TEXT("confirmation"), Confirmation) || PreviewId.IsEmpty() || PreviewId != Confirmation)
        return Fail(TEXT("confirmation_required"), TEXT("confirmation must equal the reviewed preview_id."));
    FPreview Plan;
    if (!Previews.RemoveAndCopyValue(PreviewId, Plan) || Plan.Expires <= FPlatformTime::Seconds())
        return Fail(TEXT("preview_not_found"), TEXT("CSV preview is missing, expired, or already used."));
    FCsvPlan Current;
    if (!ReadCsv(Plan.CsvPath, Plan.Overrides.ToSharedRef(), Plan.KeyColumn, Current, ErrorCode, ErrorMessage)) return false;
    if (Current.Hash != Plan.FileHash || Current.RowCount != Plan.RowCount)
        return Fail(TEXT("stale_preview"), TEXT("CSV contents changed after preview. Inspect and preview again."));
    const FString StructObjectPath = Plan.StructPath + TEXT(".") + FPackageName::GetLongPackageAssetName(Plan.StructPath);
    UUserDefinedStruct* ExistingStruct = Plan.bStructExisted ? LoadObject<UUserDefinedStruct>(nullptr, *StructObjectPath) : nullptr;
    if ((Plan.bStructExisted && (!ExistingStruct || StructSchemaFingerprint(ExistingStruct) != Plan.StructSchemaFingerprint)) ||
        (!Plan.bStructExisted && (IFileManager::Get().FileExists(*FPackageName::LongPackageNameToFilename(Plan.StructPath, FPackageName::GetAssetPackageExtension())) ||
            FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get().GetAssetByObjectPath(FSoftObjectPath(StructObjectPath)).IsValid())))
        return Fail(TEXT("stale_struct_preview"), TEXT("The struct's existence or schema changed after preview. Inspect and preview again."));
    if (Plan.bStructExisted && !ValidateExistingStruct(ExistingStruct, Current, ErrorCode, ErrorMessage)) return false;
    const FString TableObjectPath = Plan.TablePath + TEXT(".") + FPackageName::GetLongPackageAssetName(Plan.TablePath);
    if (IFileManager::Get().FileExists(*FPackageName::LongPackageNameToFilename(Plan.TablePath, FPackageName::GetAssetPackageExtension())) ||
        FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get().GetAssetByObjectPath(FSoftObjectPath(TableObjectPath)).IsValid())
        return Fail(TEXT("asset_exists"), TEXT("The destination DataTable already exists."));

    FString StructFilename = FPackageName::LongPackageNameToFilename(Plan.StructPath, FPackageName::GetAssetPackageExtension());
    TArray<uint8> ExistingStructBackup;
    if (ExistingStruct && !FFileHelper::LoadFileToArray(ExistingStructBackup, *StructFilename))
        return Fail(TEXT("backup_failed"), TEXT("Could not read a rollback copy of the existing struct package."));
    UPackage* StructPackage = ExistingStruct ? ExistingStruct->GetOutermost() : CreatePackage(*Plan.StructPath);
    if (!StructPackage) return Fail(TEXT("asset_create_failed"), TEXT("Could not access the struct package."));
    StructPackage->FullyLoad();
    UUserDefinedStruct* Struct = ExistingStruct ? ExistingStruct : FStructureEditorUtils::CreateUserDefinedStruct(
        StructPackage, *FPackageName::GetLongPackageAssetName(Plan.StructPath), RF_Public | RF_Standalone);
    if (!Struct) return Fail(TEXT("struct_create_failed"), TEXT("Unreal could not create a User Defined Struct."));
    const TArray<FStructVariableDescription> OriginalVariables = FStructureEditorUtils::GetVarDesc(Struct);
    const bool bStructCreated = ExistingStruct == nullptr;
    auto RollbackStruct = [&]()
    {
        if (bStructCreated) { DeleteNewAsset(Struct, FString()); return; }
        FStructureEditorUtils::GetVarDesc(Struct) = OriginalVariables;
        FStructureEditorUtils::CompileStructure(Struct);
    };
    TSet<int32> ReusedDefaultVariables;
    TArray<FString> AddedFields;
    const TArray<FStructVariableDescription>& InitialVariables = FStructureEditorUtils::GetVarDesc(Struct);
    if (InitialVariables.Num() == 1 && IsDefaultPlaceholder(InitialVariables[0]))
    {
        const FStructVariableDescription DefaultVariable = InitialVariables[0];
        for (int32 Index = 0; Index < Current.Headers.Num(); ++Index)
        {
            if (Current.Headers[Index] == Plan.KeyColumn) continue;
            if (!FStructureEditorUtils::ChangeVariableType(Struct, DefaultVariable.VarGuid, PinType(Current.Types[Index])) ||
                !FStructureEditorUtils::RenameVariable(Struct, DefaultVariable.VarGuid, Current.Headers[Index]))
            { RollbackStruct(); return Fail(TEXT("struct_member_failed"), TEXT("Unreal rejected the first CSV field.")); }
            ReusedDefaultVariables.Add(Index);
            AddedFields.Add(Current.Headers[Index]);
            break;
        }
    }
    for (int32 Index = 0; Index < Current.Headers.Num(); ++Index)
    {
        if (Current.Headers[Index] == Plan.KeyColumn || ReusedDefaultVariables.Contains(Index)) continue;
        bool bAlreadyPresent = false;
        for (const FStructVariableDescription& Variable : FStructureEditorUtils::GetVarDesc(Struct))
            if (!Variable.bInvalidMember && Variable.FriendlyName == Current.Headers[Index]) { bAlreadyPresent = true; break; }
        if (bAlreadyPresent) continue;
        if (!FStructureEditorUtils::AddVariable(Struct, PinType(Current.Types[Index])))
        { RollbackStruct(); return Fail(TEXT("struct_member_failed"), TEXT("Unreal rejected a CSV field type.")); }
        auto& Variables = FStructureEditorUtils::GetVarDesc(Struct);
        const FGuid AddedGuid = Variables.Last().VarGuid;
        if (!FStructureEditorUtils::RenameVariable(Struct, AddedGuid, Current.Headers[Index]))
        { RollbackStruct(); return Fail(TEXT("struct_member_failed"), TEXT("Unreal rejected a CSV field name.")); }
        AddedFields.Add(Current.Headers[Index]);
    }
    FStructureEditorUtils::CompileStructure(Struct);
    if (FStructureEditorUtils::IsStructureValid(Struct) != FStructureEditorUtils::Ok)
    { RollbackStruct(); return Fail(TEXT("invalid_row_struct"), TEXT("The updated structure is not valid for a DataTable.")); }

    UPackage* TablePackage = CreatePackage(*Plan.TablePath);
    if (!TablePackage) { RollbackStruct(); return Fail(TEXT("asset_create_failed"), TEXT("Could not create the DataTable package.")); }
    UDataTable* Table = NewObject<UDataTable>(TablePackage, *FPackageName::GetLongPackageAssetName(Plan.TablePath), RF_Public | RF_Standalone);
    Table->RowStruct = Struct;
    Table->ImportKeyField = Plan.KeyColumn;
    FString Csv;
    if (!FFileHelper::LoadFileToString(Csv, *Plan.CsvPath))
    { DeleteNewAsset(Table, FString()); RollbackStruct(); return Fail(TEXT("csv_read_failed"), TEXT("CSV could not be read during import.")); }
    const FMD5Hash ImportHash = FMD5Hash::HashFile(*Plan.CsvPath);
    if (!ImportHash.IsValid() || BytesToHex(ImportHash.GetBytes(), ImportHash.GetSize()) != Plan.FileHash)
    { DeleteNewAsset(Table, FString()); RollbackStruct(); return Fail(TEXT("stale_preview"), TEXT("CSV changed during apply. Inspect and preview again.")); }
    const TArray<FString> Problems = Table->CreateTableFromCSVString(Csv);
    if (Problems.Num() > 0 || Table->GetRowMap().Num() != Plan.RowCount)
    {
        DeleteNewAsset(Table, FString()); RollbackStruct();
        return Fail(TEXT("csv_import_failed"), Problems.Num() ? *FString::Join(Problems, TEXT(" | ")).Left(1024) : TEXT("Imported row count did not match the preview."));
    }
    FString TableFilename;
    FAssetRegistryModule& RegistryModule = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry"));
    if (bStructCreated) RegistryModule.Get().AssetCreated(Struct);
    RegistryModule.Get().AssetCreated(Table);
    const bool bStructSaved = SaveAsset(Struct, StructFilename);
    const bool bTableSaved = bStructSaved && SaveAsset(Table, TableFilename);
    if (!bTableSaved)
    {
        RegistryModule.Get().AssetDeleted(Table);
        DeleteNewAsset(Table, TableFilename);
        if (bStructCreated)
        {
            RegistryModule.Get().AssetDeleted(Struct);
            DeleteNewAsset(Struct, StructFilename);
        }
        else
        {
            if (!FFileHelper::SaveArrayToFile(ExistingStructBackup, *StructFilename))
            {
                RollbackStruct();
                return Fail(TEXT("rollback_failed"), TEXT("DataTable save failed and restoring the existing struct package also failed; inspect the package before continuing."));
            }
            RollbackStruct();
        }
        return Fail(TEXT("asset_save_failed"), TEXT("Could not save the DataTable; created packages were removed and the existing struct was restored."));
    }
    Data->SetStringField(TEXT("struct_path"), Struct->GetPathName());
    Data->SetStringField(TEXT("struct_type"), TEXT("UserDefinedStruct"));
    Data->SetNumberField(TEXT("field_count"), FStructureEditorUtils::GetVarDesc(Struct).Num());
    Data->SetNumberField(TEXT("added_field_count"), AddedFields.Num());
    TArray<TSharedPtr<FJsonValue>> AddedFieldNames;
    for (const FString& Added : AddedFields)
        AddedFieldNames.Add(MakeShared<FJsonValueString>(Added));
    Data->SetArrayField(TEXT("added_fields"), AddedFieldNames);
    Data->SetStringField(TEXT("data_table_path"), Table->GetPathName());
    Data->SetStringField(TEXT("row_struct"), Struct->GetPathName());
    Data->SetNumberField(TEXT("row_count"), Table->GetRowMap().Num());
    Data->SetBoolField(TEXT("saved"), true);
    Data->SetBoolField(TEXT("existing_struct_updated"), !bStructCreated);
    return true;
}
