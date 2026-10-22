#include "ForgeDataTables.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/AssetData.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "Engine/DataTable.h"
#include "Math/Color.h"
#include "Math/Rotator.h"
#include "Math/Vector.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "UObject/TextProperty.h"
#include "UObject/UnrealType.h"

namespace
{
constexpr int32 MaxFields = 256;
constexpr int32 MaxRows = 100;
constexpr int32 MaxValueChars = 4096;

bool IsSupportedValue(const FProperty* Property)
{
    if (!Property || Property->ArrayDim != 1 ||
        Property->HasAnyPropertyFlags(CPF_Transient | CPF_Deprecated | CPF_SkipSerialization))
        return false;
    if (Property->IsA<FBoolProperty>() || Property->IsA<FEnumProperty>() ||
        Property->IsA<FByteProperty>() || Property->IsA<FNumericProperty>() ||
        Property->IsA<FNameProperty>() || Property->IsA<FStrProperty>() ||
        Property->IsA<FTextProperty>())
        return true;
    const FStructProperty* Struct = CastField<FStructProperty>(Property);
    return Struct && (Struct->Struct == TBaseStructure<FVector>::Get() ||
        Struct->Struct == TBaseStructure<FRotator>::Get() ||
        Struct->Struct == TBaseStructure<FLinearColor>::Get() ||
        Struct->Struct == TBaseStructure<FColor>::Get());
}

void AddVector(TSharedRef<FJsonObject> Value, const FVector& Vector)
{
    Value->SetArrayField(TEXT("value"), {
        MakeShared<FJsonValueNumber>(Vector.X), MakeShared<FJsonValueNumber>(Vector.Y),
        MakeShared<FJsonValueNumber>(Vector.Z)});
}

TSharedRef<FJsonObject> ReadValue(const FProperty* Property, const void* Row)
{
    auto Value = MakeShared<FJsonObject>();
    const void* Address = Property->ContainerPtrToValuePtr<void>(Row);
    if (const FBoolProperty* Bool = CastField<FBoolProperty>(Property))
        Value->SetBoolField(TEXT("value"), Bool->GetPropertyValue(Address));
    else if (const FEnumProperty* Enum = CastField<FEnumProperty>(Property))
    {
        const int64 Number = Enum->GetUnderlyingProperty()->GetSignedIntPropertyValue(Address);
        Value->SetStringField(TEXT("value"), Enum->GetEnum()->GetNameStringByValue(Number));
        Value->SetStringField(TEXT("numeric_value"),
            Enum->GetUnderlyingProperty()->GetNumericPropertyValueToString(Address));
    }
    else if (const FByteProperty* Byte = CastField<FByteProperty>(Property))
    {
        const uint8 Number = Byte->GetPropertyValue(Address);
        Value->SetStringField(TEXT("value"), Byte->Enum
            ? Byte->Enum->GetNameStringByValue(Number) : FString::FromInt(Number));
    }
    else if (const FNumericProperty* Number = CastField<FNumericProperty>(Property))
    {
        if (Number->IsInteger())
        {
            Value->SetStringField(TEXT("value"), Number->GetNumericPropertyValueToString(Address));
            Value->SetStringField(TEXT("numeric_encoding"), TEXT("decimal_integer"));
        }
        else
        {
            const double Floating = Number->GetFloatingPointPropertyValue(Address);
            if (FMath::IsFinite(Floating))
                Value->SetNumberField(TEXT("value"), Floating);
            else
            {
                Value->SetStringField(TEXT("value"), Number->GetNumericPropertyValueToString(Address));
                Value->SetBoolField(TEXT("non_finite"), true);
            }
        }
    }
    else if (const FNameProperty* Name = CastField<FNameProperty>(Property))
        Value->SetStringField(TEXT("value"), Name->GetPropertyValue(Address).ToString());
    else if (const FStrProperty* String = CastField<FStrProperty>(Property))
    {
        const FString Text = String->GetPropertyValue(Address);
        Value->SetStringField(TEXT("value"), Text.Left(MaxValueChars));
        Value->SetBoolField(TEXT("value_truncated"), Text.Len() > MaxValueChars);
    }
    else if (const FTextProperty* Text = CastField<FTextProperty>(Property))
    {
        const FString Display = Text->GetPropertyValue(Address).ToString();
        Value->SetStringField(TEXT("value"), Display.Left(MaxValueChars));
        Value->SetBoolField(TEXT("value_truncated"), Display.Len() > MaxValueChars);
        Value->SetStringField(TEXT("text_scope"), TEXT("Localized display text; localization identity is not included."));
    }
    else if (const FStructProperty* Struct = CastField<FStructProperty>(Property))
    {
        if (Struct->Struct == TBaseStructure<FVector>::Get())
            AddVector(Value, *static_cast<const FVector*>(Address));
        else if (Struct->Struct == TBaseStructure<FRotator>::Get())
        {
            const FRotator& Rotation = *static_cast<const FRotator*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(Rotation.Roll),
                MakeShared<FJsonValueNumber>(Rotation.Pitch), MakeShared<FJsonValueNumber>(Rotation.Yaw)});
            Value->SetStringField(TEXT("component_order"), TEXT("roll_pitch_yaw_degrees"));
        }
        else if (Struct->Struct == TBaseStructure<FLinearColor>::Get())
        {
            const FLinearColor& Color = *static_cast<const FLinearColor*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(Color.R),
                MakeShared<FJsonValueNumber>(Color.G), MakeShared<FJsonValueNumber>(Color.B),
                MakeShared<FJsonValueNumber>(Color.A)});
            Value->SetStringField(TEXT("color_encoding"), TEXT("linear_rgba"));
        }
        else
        {
            const FColor& Color = *static_cast<const FColor*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(Color.R),
                MakeShared<FJsonValueNumber>(Color.G), MakeShared<FJsonValueNumber>(Color.B),
                MakeShared<FJsonValueNumber>(Color.A)});
            Value->SetStringField(TEXT("color_encoding"), TEXT("8_bit_rgba"));
        }
    }
    return Value;
}

bool ResolveDataTable(const FString& InputPath, UDataTable*& OutTable, FString& OutPath,
    FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    {
        ErrorCode = Code;
        ErrorMessage = Message;
        return false;
    };
    if (InputPath.IsEmpty() || InputPath.Len() > 240 || InputPath.Contains(TEXT(":")))
        return Fail(TEXT("invalid_arguments"), TEXT("Provide one bounded top-level DataTable asset path."));

    FString Package = InputPath;
    int32 Dot = INDEX_NONE;
    if (InputPath.FindChar(TEXT('.'), Dot))
    {
        Package = InputPath.Left(Dot);
        if (InputPath.Mid(Dot + 1) != FPackageName::GetLongPackageAssetName(Package))
            return Fail(TEXT("invalid_arguments"), TEXT("Only an exact top-level DataTable object path is supported."));
    }
    if (!FPackageName::IsValidLongPackageName(Package) ||
        !(Package.StartsWith(TEXT("/Game/")) || Package.StartsWith(TEXT("/JasperPrism/"))))
        return Fail(TEXT("unsupported_asset_path"), TEXT("DataTable inspection is limited to /Game and /JasperPrism assets."));
    OutPath = InputPath.Contains(TEXT("."))
        ? InputPath : InputPath + TEXT(".") + FPackageName::GetLongPackageAssetName(Package);

    IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
    const FAssetData Asset = Registry.GetAssetByObjectPath(FSoftObjectPath(OutPath));
    if (!Asset.IsValid()) return Fail(TEXT("asset_not_found"), TEXT("The selected DataTable asset is not present in the current registry."));
    UObject* Object = Asset.GetAsset();
    if (!Object) return Fail(TEXT("asset_load_failed"), TEXT("The selected DataTable asset could not be loaded."));
    OutTable = Cast<UDataTable>(Object);
    if (!OutTable) return Fail(TEXT("wrong_asset_type"), TEXT("The selected asset is not a DataTable."));
    if (!OutTable->GetRowStruct())
        return Fail(TEXT("schema_unavailable"), TEXT("The DataTable has no loaded row struct."));
    return true;
}

TArray<FProperty*> GetFields(const UScriptStruct* RowStruct)
{
    TArray<FProperty*> Fields;
    for (TFieldIterator<FProperty> It(RowStruct, EFieldIteratorFlags::IncludeSuper); It; ++It)
        Fields.Add(*It);
    Fields.Sort([](const FProperty& A, const FProperty& B) { return A.GetName() < B.GetName(); });
    return Fields;
}
}

bool FForgeDataTables::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    {
        ErrorCode = Code;
        ErrorMessage = Message;
        return false;
    };
    if (!IsInGameThread())
        return Fail(TEXT("invalid_context"), TEXT("DataTable inspection requires the Editor game thread."));

    const bool Schema = Command == TEXT("get_data_table_schema");
    const bool Rows = Command == TEXT("get_data_table_rows");
    const bool Row = Command == TEXT("get_data_table_row");
    if (!Schema && !Rows && !Row)
        return Fail(TEXT("unknown_command"), TEXT("Unsupported DataTable inspection command."));

    const TSet<FString> Fields = Schema
        ? TSet<FString>{TEXT("data_table_path")}
        : Rows ? TSet<FString>{TEXT("data_table_path"), TEXT("limit"), TEXT("offset")}
               : TSet<FString>{TEXT("data_table_path"), TEXT("row_name")};
    for (const auto& Pair : Args->Values)
    {
        if (!Fields.Contains(Pair.Key) || !Pair.Value.IsValid())
            return Fail(TEXT("invalid_arguments"), TEXT("Unknown DataTable query field."));
        const EJson Expected = (Pair.Key == TEXT("limit") || Pair.Key == TEXT("offset"))
            ? EJson::Number : EJson::String;
        if (Pair.Value->Type != Expected)
            return Fail(TEXT("invalid_arguments"), TEXT("DataTable query fields must use their documented JSON types."));
    }
    FString InputPath;
    if (!Args->TryGetStringField(TEXT("data_table_path"), InputPath))
        return Fail(TEXT("invalid_arguments"), TEXT("data_table_path is required."));
    UDataTable* Table = nullptr;
    FString AssetPath;
    if (!ResolveDataTable(InputPath, Table, AssetPath, ErrorCode, ErrorMessage)) return false;
    const UScriptStruct* RowStruct = Table->GetRowStruct();
    const TArray<FProperty*> Properties = GetFields(RowStruct);
    Data->SetStringField(TEXT("data_table_path"), AssetPath);
    Data->SetStringField(TEXT("row_struct"), RowStruct->GetPathName());
    Data->SetBoolField(TEXT("loads_assets"), true);

    if (Schema)
    {
        TArray<TSharedPtr<FJsonValue>> Result;
        int32 Supported = 0;
        for (const FProperty* Property : Properties)
        {
            if (IsSupportedValue(Property)) ++Supported;
            if (Result.Num() >= MaxFields) continue;
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Property->GetName());
            Item->SetStringField(TEXT("type"), Property->GetCPPType());
            Item->SetNumberField(TEXT("array_dim"), Property->ArrayDim);
            Item->SetBoolField(TEXT("supported_value_type"), IsSupportedValue(Property));
            Result.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetArrayField(TEXT("fields"), Result);
        Data->SetNumberField(TEXT("field_count"), Properties.Num());
        Data->SetNumberField(TEXT("supported_field_count"), Supported);
        Data->SetBoolField(TEXT("truncated"), Properties.Num() > Result.Num());
        Data->SetStringField(TEXT("inspection_scope"),
            TEXT("Row-struct reflection only; values and nested containers are not traversed."));
        return true;
    }

    if (Row)
    {
        FString RowName;
        if (!Args->TryGetStringField(TEXT("row_name"), RowName) || RowName.IsEmpty() || RowName.Len() > 128)
            return Fail(TEXT("invalid_arguments"), TEXT("row_name must be between 1 and 128 characters."));
        const FName Name(*RowName);
        const uint8* RowData = Table->FindRowUnchecked(Name);
        if (!RowData) return Fail(TEXT("row_not_found"), TEXT("The exact DataTable row does not exist."));
        TArray<TSharedPtr<FJsonValue>> Result;
        int32 Supported = 0;
        int32 Omitted = 0;
        for (const FProperty* Property : Properties)
        {
            if (!IsSupportedValue(Property)) { ++Omitted; continue; }
            ++Supported;
            if (Result.Num() >= MaxFields) continue;
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Property->GetName());
            Item->SetStringField(TEXT("type"), Property->GetCPPType());
            const auto Value = ReadValue(Property, RowData);
            for (const auto& Pair : Value->Values) Item->SetField(Pair.Key, Pair.Value);
            Result.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetStringField(TEXT("row_name"), Name.ToString());
        Data->SetArrayField(TEXT("fields"), Result);
        Data->SetNumberField(TEXT("supported_field_count"), Supported);
        Data->SetNumberField(TEXT("omitted_complex_or_unsupported_field_count"), Omitted);
        Data->SetBoolField(TEXT("truncated"), Supported > Result.Num());
        Data->SetStringField(TEXT("inspection_scope"),
            TEXT("Bounded simple row values only; nested objects and containers are not traversed."));
        return true;
    }

    double Limit = 50;
    double Offset = 0;
    if ((Args->HasField(TEXT("limit")) && !Args->TryGetNumberField(TEXT("limit"), Limit)) ||
        (Args->HasField(TEXT("offset")) && !Args->TryGetNumberField(TEXT("offset"), Offset)) ||
        Limit < 1 || Limit > MaxRows || FMath::FloorToDouble(Limit) != Limit ||
        Offset < 0 || Offset > 100000 || FMath::FloorToDouble(Offset) != Offset)
        return Fail(TEXT("invalid_arguments"), TEXT("limit must be 1-100 and offset must be a nonnegative integer no greater than 100000."));
    TArray<FName> Names = Table->GetRowNames();
    Names.Sort([](const FName& A, const FName& B) { return A.ToString() < B.ToString(); });
    const int32 Start = FMath::Min(static_cast<int32>(Offset), Names.Num());
    const int32 End = FMath::Min(Start + static_cast<int32>(Limit), Names.Num());
    TArray<TSharedPtr<FJsonValue>> Result;
    for (int32 Index = Start; Index < End; ++Index)
        Result.Add(MakeShared<FJsonValueString>(Names[Index].ToString()));
    Data->SetArrayField(TEXT("row_names"), Result);
    Data->SetNumberField(TEXT("row_count"), Names.Num());
    Data->SetNumberField(TEXT("offset"), Offset);
    Data->SetNumberField(TEXT("next_offset"), End);
    Data->SetBoolField(TEXT("truncated"), End < Names.Num());
    Data->SetStringField(TEXT("pagination"), TEXT("Sorted live row-name snapshot; concurrent edits between pages may shift results."));
    return true;
}
