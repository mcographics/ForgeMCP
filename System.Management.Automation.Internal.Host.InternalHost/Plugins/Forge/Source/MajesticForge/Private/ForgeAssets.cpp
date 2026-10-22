#include "ForgeAssets.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "Misc/PackageName.h"
#include "Misc/SecureHash.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Modules/ModuleManager.h"
#include "ContentBrowserModule.h"
#include "IContentBrowserSingleton.h"
#include "Subsystems/AssetEditorSubsystem.h"
#include "Editor.h"
#include "Misc/App.h"
#include "Math/Color.h"
#include "Math/Rotator.h"
#include "Math/Vector.h"
#include "Misc/OutputDeviceNull.h"
#include "ScopedTransaction.h"
#include "UObject/UnrealType.h"
#include "UObject/TextProperty.h"
#include "Engine/DataAsset.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "UObject/UObjectIterator.h"

namespace
{
FString PackageFingerprint(const FString& Filename)
{
    const FMD5Hash Hash = FMD5Hash::HashFile(*Filename);
    return Hash.IsValid() ? BytesToHex(Hash.GetBytes(), Hash.GetSize()) : FString();
}

TSharedRef<FJsonObject> Describe(const FAssetData& Asset)
{
    auto Item = MakeShared<FJsonObject>();
    Item->SetStringField(TEXT("asset_path"), Asset.GetSoftObjectPath().ToString());
    Item->SetStringField(TEXT("package_name"), Asset.PackageName.ToString());
    Item->SetStringField(TEXT("package_path"), Asset.PackagePath.ToString());
    Item->SetStringField(TEXT("name"), Asset.AssetName.ToString());
    Item->SetStringField(TEXT("class_path"), Asset.AssetClassPath.ToString());
    Item->SetBoolField(TEXT("redirector"), Asset.IsRedirector());
    auto Tags = MakeShared<FJsonObject>();
    int32 Count = 0;
    bool Clipped = false;
    Asset.EnumerateTags([&](const TPair<FName, FAssetTagValueRef>& Pair)
    {
        ++Count;
        if (Count <= 64)
        {
            const FString Value = Pair.Value.AsString();
            Tags->SetStringField(Pair.Key.ToString(), Value.Left(512));
            Clipped |= Value.Len() > 512;
        }
    });
    Item->SetObjectField(TEXT("registry_tags"), Tags);
    Item->SetNumberField(TEXT("total_tags"), Count);
    Item->SetBoolField(TEXT("tags_truncated"), Count > 64 || Clipped);
    return Item;
}

TSharedRef<FJsonObject> PropertyValue(FProperty* Property, const void* Container, bool& bSupported)
{
    auto Value = MakeShared<FJsonObject>();
    bSupported = true;
    if (const FBoolProperty* BoolProp = CastField<FBoolProperty>(Property))
        Value->SetBoolField(TEXT("value"), BoolProp->GetPropertyValue_InContainer(Container));
    else if (const FEnumProperty* EnumProp = CastField<FEnumProperty>(Property))
    {
        const void* Address = EnumProp->ContainerPtrToValuePtr<void>(Container);
        const int64 Numeric = EnumProp->GetUnderlyingProperty()->GetSignedIntPropertyValue(Address);
        Value->SetStringField(TEXT("numeric_value"), EnumProp->GetUnderlyingProperty()->GetNumericPropertyValueToString(Address));
        Value->SetStringField(TEXT("value"), EnumProp->GetEnum()->GetNameStringByValue(Numeric));
    }
    else if (const FByteProperty* ByteProp = CastField<FByteProperty>(Property))
    {
        const uint8 Numeric = ByteProp->GetPropertyValue_InContainer(Container);
        Value->SetNumberField(TEXT("numeric_value"), Numeric);
        Value->SetStringField(TEXT("value"), ByteProp->Enum ? ByteProp->Enum->GetNameStringByValue(Numeric) : FString::FromInt(Numeric));
    }
    else if (const FNumericProperty* NumericProp = CastField<FNumericProperty>(Property))
    {
        if (NumericProp->IsInteger())
        {
            Value->SetStringField(TEXT("value"), NumericProp->GetNumericPropertyValueToString(NumericProp->ContainerPtrToValuePtr<void>(Container)));
            Value->SetStringField(TEXT("numeric_encoding"), TEXT("decimal_integer"));
        }
        else
        {
            const double Numeric = NumericProp->GetFloatingPointPropertyValue(NumericProp->ContainerPtrToValuePtr<void>(Container));
            if (!FMath::IsFinite(Numeric)) { bSupported = false; return Value; }
            Value->SetNumberField(TEXT("value"), Numeric);
        }
    }
    else if (const FNameProperty* NameProp = CastField<FNameProperty>(Property))
        Value->SetStringField(TEXT("value"), NameProp->GetPropertyValue_InContainer(Container).ToString().Left(512));
    else if (const FStrProperty* StringProp = CastField<FStrProperty>(Property))
    {
        const FString Text = StringProp->GetPropertyValue_InContainer(Container);
        Value->SetStringField(TEXT("value"), Text.Left(512));
        Value->SetBoolField(TEXT("value_truncated"), Text.Len() > 512);
    }
    else if (const FTextProperty* TextProp = CastField<FTextProperty>(Property))
    {
        const FString Text = TextProp->GetPropertyValue_InContainer(Container).ToString();
        Value->SetStringField(TEXT("value"), Text.Left(512));
        Value->SetBoolField(TEXT("value_truncated"), Text.Len() > 512);
        Value->SetStringField(TEXT("text_scope"), TEXT("Localized display text; not localization identity data."));
    }
    else if (const FStructProperty* StructProp = CastField<FStructProperty>(Property))
    {
        const void* Address = StructProp->ContainerPtrToValuePtr<void>(Container);
        auto AddVector = [&](const FVector& V)
        { Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z)}); };
        if (StructProp->Struct == TBaseStructure<FVector>::Get()) AddVector(*static_cast<const FVector*>(Address));
        else if (StructProp->Struct == TBaseStructure<FRotator>::Get())
        {
            const FRotator& R = *static_cast<const FRotator*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(R.Roll), MakeShared<FJsonValueNumber>(R.Pitch), MakeShared<FJsonValueNumber>(R.Yaw)});
            Value->SetStringField(TEXT("component_order"), TEXT("roll_pitch_yaw_degrees"));
        }
        else if (StructProp->Struct == TBaseStructure<FLinearColor>::Get())
        {
            const FLinearColor& C = *static_cast<const FLinearColor*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(C.R), MakeShared<FJsonValueNumber>(C.G), MakeShared<FJsonValueNumber>(C.B), MakeShared<FJsonValueNumber>(C.A)});
            Value->SetStringField(TEXT("color_encoding"), TEXT("linear_rgba"));
        }
        else if (StructProp->Struct == TBaseStructure<FColor>::Get())
        {
            const FColor& C = *static_cast<const FColor*>(Address);
            Value->SetArrayField(TEXT("value"), {MakeShared<FJsonValueNumber>(C.R), MakeShared<FJsonValueNumber>(C.G), MakeShared<FJsonValueNumber>(C.B), MakeShared<FJsonValueNumber>(C.A)});
            Value->SetStringField(TEXT("color_encoding"), TEXT("8_bit_rgba"));
        }
        else bSupported = false;
    }
    else bSupported = false;
    return Value;
}

bool DescribeProperties(UObject* Object, int32 Limit, TSharedRef<FJsonObject> Data,
    FString& ErrorCode, FString& ErrorMessage)
{
    TArray<TSharedPtr<FJsonValue>> Results;
    int32 Supported = 0;
    int32 Omitted = 0;
    for (TFieldIterator<FProperty> It(Object->GetClass(), EFieldIteratorFlags::IncludeSuper); It; ++It)
    {
        FProperty* Property = *It;
        if (Property->HasAnyPropertyFlags(CPF_Transient | CPF_Deprecated | CPF_SkipSerialization) ||
            Property->ArrayDim != 1) { ++Omitted; continue; }
        bool bSupported = false;
        auto Value = PropertyValue(Property, Object, bSupported);
        if (!bSupported) { ++Omitted; continue; }
        ++Supported;
        if (Results.Num() >= Limit) continue;
        auto Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("name"), Property->GetName().Left(128));
        Item->SetStringField(TEXT("type"), Property->GetCPPType().Left(128));
        Item->SetBoolField(TEXT("editable_in_editor"), Property->HasAnyPropertyFlags(CPF_Edit) &&
            !Property->HasAnyPropertyFlags(CPF_DisableEditOnInstance | CPF_EditConst));
        Item->SetBoolField(TEXT("read_only"), true);
        for (const auto& Pair : Value->Values) Item->SetField(Pair.Key, Pair.Value);
        Results.Add(MakeShared<FJsonValueObject>(Item));
    }
    if (Results.IsEmpty() && Supported == 0)
    {
        ErrorCode = TEXT("properties_unavailable");
        ErrorMessage = TEXT("No supported scalar, enum, text, name, vector, rotator or color properties were found.");
        return false;
    }
    Data->SetArrayField(TEXT("properties"), Results);
    Data->SetNumberField(TEXT("supported_property_count"), Supported);
    Data->SetNumberField(TEXT("returned_property_count"), Results.Num());
    Data->SetNumberField(TEXT("omitted_complex_or_non_instance_property_count"), Omitted);
    Data->SetBoolField(TEXT("truncated"), Supported > Results.Num());
    Data->SetBoolField(TEXT("loads_assets"), true);
    Data->SetStringField(TEXT("inspection_scope"), TEXT("Selected loaded asset instance; bounded simple reflected values only; no container contents or reference traversal. Unreal may load normal dependencies."));
    return true;
}

bool IsEditablePropertyType(const FProperty* Property)
{
    if (!Property) return false;
    if (Property->IsA<FBoolProperty>() || Property->IsA<FEnumProperty>() ||
        Property->IsA<FByteProperty>() || Property->IsA<FNumericProperty>() ||
        Property->IsA<FNameProperty>() || Property->IsA<FStrProperty>()) return true;
    const FStructProperty* Struct = CastField<FStructProperty>(Property);
    return Struct && (Struct->Struct == TBaseStructure<FVector>::Get() ||
        Struct->Struct == TBaseStructure<FRotator>::Get() ||
        Struct->Struct == TBaseStructure<FLinearColor>::Get() ||
        Struct->Struct == TBaseStructure<FColor>::Get());
}

bool IsEditableProperty(UObject* Object, FProperty* Property)
{
    return Object && Property && Property->ArrayDim == 1 && IsEditablePropertyType(Property) &&
        Property->HasAnyPropertyFlags(CPF_Edit) &&
        !Property->HasAnyPropertyFlags(CPF_EditConst | CPF_DisableEditOnInstance | CPF_Transient |
            CPF_Deprecated | CPF_Config | CPF_SkipSerialization) && Object->CanEditChange(Property);
}

bool ExportPropertyText(UObject* Object, FProperty* Property, FString& Out)
{
    if (!Object || !Property) return false;
    if (const FBoolProperty* Bool = CastField<FBoolProperty>(Property))
    {
        Out = Bool->GetPropertyValue_InContainer(Object) ? TEXT("true") : TEXT("false");
        return true;
    }
    if (!Property->ExportText_Direct(Out,
        Property->ContainerPtrToValuePtr<void>(Object), nullptr, Object, PPF_None, nullptr)) return false;
    return Out.Len() <= 512;
}

bool FinitePropertyValue(const FProperty* Property, const void* Value)
{
    if (const FNumericProperty* Numeric = CastField<FNumericProperty>(Property))
        return Numeric->IsInteger() || FMath::IsFinite(Numeric->GetFloatingPointPropertyValue(Value));
    const FStructProperty* Struct = CastField<FStructProperty>(Property);
    if (!Struct) return true;
    if (Struct->Struct == TBaseStructure<FVector>::Get())
    {
        const FVector& V = *static_cast<const FVector*>(Value);
        return FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z);
    }
    if (Struct->Struct == TBaseStructure<FRotator>::Get())
    {
        const FRotator& R = *static_cast<const FRotator*>(Value);
        return FMath::IsFinite(R.Roll) && FMath::IsFinite(R.Pitch) && FMath::IsFinite(R.Yaw);
    }
    if (Struct->Struct == TBaseStructure<FLinearColor>::Get())
    {
        const FLinearColor& C = *static_cast<const FLinearColor*>(Value);
        return FMath::IsFinite(C.R) && FMath::IsFinite(C.G) && FMath::IsFinite(C.B) && FMath::IsFinite(C.A);
    }
    return true;
}

bool ImportPropertyText(FProperty* Property, void* Value, UObject* Object,
    const FString& Text, FOutputDevice& ErrorOutput)
{
    if (!Property || !Value || !Object || Text.Len() > 512) return false;
    if (FBoolProperty* Bool = CastField<FBoolProperty>(Property))
    {
        if (Text.Equals(TEXT("true"), ESearchCase::IgnoreCase) || Text == TEXT("1"))
            Bool->SetPropertyValue(Value, true);
        else if (Text.Equals(TEXT("false"), ESearchCase::IgnoreCase) || Text == TEXT("0"))
            Bool->SetPropertyValue(Value, false);
        else return false;
        return true;
    }
    const TCHAR* End = Property->ImportText_Direct(*Text, Value, Object, PPF_None, &ErrorOutput);
    return End && *End == TEXT('\0');
}

bool ParsePropertyText(UObject* Object, FProperty* Property, const FString& Text, FString& Normalized)
{
    if (!Object || !Property || Text.Len() > 512 ||
        (Text.IsEmpty() && !Property->IsA<FStrProperty>())) return false;
    void* Value = FMemory::Malloc(Property->GetSize(), Property->GetMinAlignment());
    if (!Value) return false;
    Property->InitializeValue(Value);
    Property->CopyCompleteValue(Value, Property->ContainerPtrToValuePtr<void>(Object));
    FOutputDeviceNull ErrorOutput;
    bool bParsed = ImportPropertyText(Property, Value, Object, Text, ErrorOutput) &&
        FinitePropertyValue(Property, Value);
    if (bParsed)
    {
        if (const FBoolProperty* Bool = CastField<FBoolProperty>(Property))
            Normalized = Bool->GetPropertyValue(Value) ? TEXT("true") : TEXT("false");
        else
            bParsed = Property->ExportText_Direct(Normalized, Value, nullptr, Object, PPF_None, nullptr);
        bParsed = bParsed && Normalized.Len() <= 512;
    }
    Property->DestroyValue(Value);
    FMemory::Free(Value);
    return bParsed;
}
}

bool FForgeAssets::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    { ErrorCode = Code; ErrorMessage = Message; return false; };
    if (!IsInGameThread()) return Fail(TEXT("invalid_context"), TEXT("Asset inspection requires the game thread."));
    const bool Selected = Command == TEXT("get_selected_assets");
    const bool OpenAsset = Command == TEXT("open_asset");
    const bool SyncBrowser = Command == TEXT("sync_browser");
    if (Selected)
    {
        double Limit = 100;
        for (const auto& Pair : Args->Values)
            if (Pair.Key != TEXT("limit") || !Pair.Value.IsValid() || Pair.Value->Type != EJson::Number)
                return Fail(TEXT("invalid_arguments"), TEXT("Selected asset query accepts only an integer limit."));
        if ((Args->HasField(TEXT("limit")) && !Args->TryGetNumberField(TEXT("limit"), Limit)) ||
            Limit < 1 || Limit > 100 || FMath::FloorToDouble(Limit) != Limit)
            return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 100."));
        TArray<FAssetData> Assets;
        FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser")).Get().GetSelectedAssets(Assets);
        Assets.Sort([](const FAssetData& A, const FAssetData& B)
            { return A.GetSoftObjectPath().ToString() < B.GetSoftObjectPath().ToString(); });
        TArray<TSharedPtr<FJsonValue>> Results;
        for (int32 Index = 0; Index < FMath::Min(Assets.Num(), static_cast<int32>(Limit)); ++Index)
            Results.Add(MakeShared<FJsonValueObject>(Describe(Assets[Index])));
        Data->SetArrayField(TEXT("assets"), Results);
        Data->SetNumberField(TEXT("selected_count"), Assets.Num());
        Data->SetNumberField(TEXT("returned_count"), Results.Num());
        Data->SetBoolField(TEXT("truncated"), Assets.Num() > Results.Num());
        return true;
    }
    if (Command == TEXT("list_data_asset_classes"))
    {
        FString NameFilter;
        bool bIncludeAbstract = false;
        double Limit = 100, Offset = 0;
        for (const auto& Pair : Args->Values)
        {
            if (Pair.Key == TEXT("filter") && Pair.Value.IsValid() && Pair.Value->Type == EJson::String)
                NameFilter = Pair.Value->AsString();
            else if (Pair.Key == TEXT("include_abstract") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean)
                bIncludeAbstract = Pair.Value->AsBool();
            else if (Pair.Key == TEXT("limit") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
                Limit = Pair.Value->AsNumber();
            else if (Pair.Key == TEXT("offset") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
                Offset = Pair.Value->AsNumber();
            else return Fail(TEXT("invalid_arguments"), TEXT("DataAsset class query received an unknown field or wrong JSON type."));
        }
        if (NameFilter.Len() > 128 || Limit < 1 || Limit > 200 || FMath::FloorToDouble(Limit) != Limit ||
            Offset < 0 || Offset > 100000 || FMath::FloorToDouble(Offset) != Offset)
            return Fail(TEXT("invalid_arguments"), TEXT("DataAsset class query limits or filter are outside their bounds."));
        TArray<UClass*> Classes;
        for (TObjectIterator<UClass> It; It; ++It)
        {
            UClass* Class = *It;
            if (!Class || !Class->IsChildOf(UDataAsset::StaticClass()) || Class == UDataAsset::StaticClass() ||
                Class->HasAnyClassFlags(CLASS_Deprecated | CLASS_NewerVersionExists | CLASS_Hidden | CLASS_HideDropDown))
                continue;
            const FString ClassName = Class->GetName();
            if (!bIncludeAbstract && Class->HasAnyClassFlags(CLASS_Abstract)) continue;
            if (ClassName.StartsWith(TEXT("SKEL_")) || ClassName.StartsWith(TEXT("REINST_")) ||
                ClassName.StartsWith(TEXT("TRASHCLASS_")) ||
                (!NameFilter.IsEmpty() && !ClassName.Contains(NameFilter, ESearchCase::IgnoreCase) &&
                 !Class->GetPathName().Contains(NameFilter, ESearchCase::IgnoreCase)))
                continue;
            Classes.Add(Class);
        }
        Classes.Sort([](const UClass& A, const UClass& B) { return A.GetPathName() < B.GetPathName(); });
        TArray<TSharedPtr<FJsonValue>> Results;
        const int32 Start = FMath::Min(static_cast<int32>(Offset), Classes.Num());
        const int32 End = FMath::Min(Start + static_cast<int32>(Limit), Classes.Num());
        for (int32 Index = Start; Index < End; ++Index)
        {
            UClass* Class = Classes[Index];
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("class_name"), Class->GetName());
            Item->SetStringField(TEXT("class_path"), Class->GetPathName());
            Item->SetStringField(TEXT("parent_class_path"), Class->GetSuperClass() ? Class->GetSuperClass()->GetPathName() : FString());
            Item->SetStringField(TEXT("module"), Class->GetOutermost()->GetName());
            Item->SetBoolField(TEXT("abstract"), Class->HasAnyClassFlags(CLASS_Abstract));
            Item->SetBoolField(TEXT("blueprint_generated"), Class->ClassGeneratedBy != nullptr);
            Results.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetArrayField(TEXT("classes"), Results);
        Data->SetNumberField(TEXT("total_count"), Classes.Num());
        Data->SetNumberField(TEXT("offset"), Offset);
        Data->SetNumberField(TEXT("returned_count"), Results.Num());
        Data->SetBoolField(TEXT("truncated"), End < Classes.Num());
        Data->SetBoolField(TEXT("loads_assets"), false);
        Data->SetStringField(TEXT("scope"), TEXT("Loaded UDataAsset-derived classes only; transient, deprecated, hidden and skeleton/reinstantiation classes are excluded."));
        return true;
    }
    if (Command == TEXT("list_data_assets"))
    {
        FString Path = TEXT("/Game"), ClassFilter;
        bool bRecursive = true;
        double Limit = 100, Offset = 0;
        for (const auto& Pair : Args->Values)
        {
            if (Pair.Key == TEXT("path") && Pair.Value.IsValid() && Pair.Value->Type == EJson::String) Path = Pair.Value->AsString();
            else if (Pair.Key == TEXT("class_filter") && Pair.Value.IsValid() && Pair.Value->Type == EJson::String) ClassFilter = Pair.Value->AsString();
            else if (Pair.Key == TEXT("recursive") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean) bRecursive = Pair.Value->AsBool();
            else if (Pair.Key == TEXT("max_results") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Number) Limit = Pair.Value->AsNumber();
            else if (Pair.Key == TEXT("offset") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Number) Offset = Pair.Value->AsNumber();
            else return Fail(TEXT("invalid_arguments"), TEXT("DataAsset query received an unknown field or wrong JSON type."));
        }
        if (Path.Len() > 240 || !FPackageName::IsValidLongPackageName(Path) ||
            !(Path == TEXT("/Game") || Path.StartsWith(TEXT("/Game/")) ||
              Path == TEXT("/JasperPrism") || Path.StartsWith(TEXT("/JasperPrism/"))))
            return Fail(TEXT("unsupported_asset_path"), TEXT("DataAsset search is limited to /Game and /JasperPrism content."));
        if (ClassFilter.Len() > 128 || Limit < 1 || Limit > 200 || FMath::FloorToDouble(Limit) != Limit ||
            Offset < 0 || Offset > 100000 || FMath::FloorToDouble(Offset) != Offset)
            return Fail(TEXT("invalid_arguments"), TEXT("DataAsset query limits or class filter are outside their bounds."));
        FARFilter Filter;
        Filter.PackagePaths.Add(FName(*Path));
        Filter.bRecursivePaths = bRecursive;
        Filter.ClassPaths.Add(UDataAsset::StaticClass()->GetClassPathName());
        Filter.bRecursiveClasses = true;
        IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        TArray<FAssetData> Assets;
        Registry.GetAssets(Filter, Assets);
        Assets.RemoveAll([&](const FAssetData& Asset)
        {
            const FString ClassPath = Asset.AssetClassPath.ToString();
            const FString ClassName = Asset.AssetClassPath.GetAssetName().ToString();
            return !ClassFilter.IsEmpty() && !ClassName.Contains(ClassFilter, ESearchCase::IgnoreCase) &&
                !ClassPath.Contains(ClassFilter, ESearchCase::IgnoreCase);
        });
        Assets.Sort([](const FAssetData& A, const FAssetData& B)
            { return A.GetSoftObjectPath().ToString() < B.GetSoftObjectPath().ToString(); });
        const int32 Start = FMath::Min(static_cast<int32>(Offset), Assets.Num());
        const int32 End = FMath::Min(Start + static_cast<int32>(Limit), Assets.Num());
        TArray<TSharedPtr<FJsonValue>> Results;
        for (int32 Index = Start; Index < End; ++Index) Results.Add(MakeShared<FJsonValueObject>(Describe(Assets[Index])));
        Data->SetArrayField(TEXT("assets"), Results);
        Data->SetNumberField(TEXT("total_count"), Assets.Num());
        Data->SetNumberField(TEXT("offset"), Offset);
        Data->SetNumberField(TEXT("returned_count"), Results.Num());
        Data->SetBoolField(TEXT("truncated"), End < Assets.Num());
        Data->SetBoolField(TEXT("registry_loading"), Registry.IsLoadingAssets());
        Data->SetBoolField(TEXT("loads_assets"), false);
        return true;
    }
    if (Command == TEXT("data_asset_schema"))
    {
        FString ClassPath;
        bool bIncludeInherited = true;
        double Limit = 200;
        for (const auto& Pair : Args->Values)
        {
            if (Pair.Key == TEXT("class_path") && Pair.Value.IsValid() && Pair.Value->Type == EJson::String)
                ClassPath = Pair.Value->AsString();
            else if (Pair.Key == TEXT("include_inherited") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Boolean)
                bIncludeInherited = Pair.Value->AsBool();
            else if (Pair.Key == TEXT("limit") && Pair.Value.IsValid() && Pair.Value->Type == EJson::Number)
                Limit = Pair.Value->AsNumber();
            else return Fail(TEXT("invalid_arguments"), TEXT("DataAsset schema query received an unknown field or wrong JSON type."));
        }
        if (ClassPath.Len() < 8 || ClassPath.Len() > 512 ||
            !(ClassPath.StartsWith(TEXT("/Script/")) || ClassPath.StartsWith(TEXT("/Game/"))) ||
            Limit < 1 || Limit > 256 || FMath::FloorToDouble(Limit) != Limit)
            return Fail(TEXT("invalid_arguments"), TEXT("Provide a loaded /Script or /Game DataAsset class path and a limit from 1 to 256."));
        UClass* AssetClass = nullptr;
        for (TObjectIterator<UClass> It; It; ++It)
        {
            UClass* Candidate = *It;
            if (Candidate && Candidate->GetPathName() == ClassPath)
            {
                AssetClass = Candidate;
                break;
            }
        }
        if (!AssetClass)
            return Fail(TEXT("class_not_loaded"), TEXT("The exact DataAsset class is not loaded; discover loaded classes first."));
        if (!AssetClass->IsChildOf(UDataAsset::StaticClass()) || AssetClass == UDataAsset::StaticClass() ||
            AssetClass->HasAnyClassFlags(CLASS_Deprecated | CLASS_NewerVersionExists))
            return Fail(TEXT("unsupported_data_asset_class"), TEXT("Schema inspection accepts only current UDataAsset-derived classes."));

        TArray<FProperty*> Properties;
        TSet<FName> SeenNames;
        for (TFieldIterator<FProperty> It(AssetClass, EFieldIteratorFlags::IncludeSuper); It; ++It)
        {
            FProperty* Property = *It;
            if (!Property || Property->HasAnyPropertyFlags(CPF_Transient | CPF_Deprecated | CPF_SkipSerialization) ||
                (!bIncludeInherited && Property->GetOwnerClass() != AssetClass) || SeenNames.Contains(Property->GetFName()))
                continue;
            SeenNames.Add(Property->GetFName());
            Properties.Add(Property);
        }
        Properties.Sort([](const FProperty& A, const FProperty& B)
        {
            if (A.GetFName() == B.GetFName())
                return A.GetOwnerClass()->GetPathName() < B.GetOwnerClass()->GetPathName();
            return A.GetFName().LexicalLess(B.GetFName());
        });
        TArray<TSharedPtr<FJsonValue>> Results;
        const int32 Returned = FMath::Min(Properties.Num(), static_cast<int32>(Limit));
        for (int32 Index = 0; Index < Returned; ++Index)
        {
            FProperty* Property = Properties[Index];
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Property->GetName().Left(128));
            Item->SetStringField(TEXT("type"), Property->GetCPPType().Left(192));
            Item->SetStringField(TEXT("property_class"), Property->GetClass()->GetName());
            Item->SetStringField(TEXT("owner_class_path"), Property->GetOwnerClass()->GetPathName());
            Item->SetNumberField(TEXT("array_dim"), Property->ArrayDim);
            Item->SetBoolField(TEXT("inherited"), Property->GetOwnerClass() != AssetClass);
            Item->SetBoolField(TEXT("editor_editable"), Property->HasAnyPropertyFlags(CPF_Edit) &&
                !Property->HasAnyPropertyFlags(CPF_EditConst | CPF_DisableEditOnInstance | CPF_Transient | CPF_Deprecated));
            Item->SetBoolField(TEXT("blueprint_visible"), Property->HasAnyPropertyFlags(CPF_BlueprintVisible));
            FString ValueKind = TEXT("unsupported_complex_or_native_type");
            if (Property->IsA<FBoolProperty>()) ValueKind = TEXT("boolean");
            else if (const FNumericProperty* Numeric = CastField<FNumericProperty>(Property))
                ValueKind = Numeric->IsInteger() ? TEXT("integer") : TEXT("floating_point");
            else if (Property->IsA<FEnumProperty>()) ValueKind = TEXT("enum");
            else if (const FByteProperty* Byte = CastField<FByteProperty>(Property))
                ValueKind = Byte->Enum ? TEXT("enum") : TEXT("byte");
            else if (Property->IsA<FNameProperty>()) ValueKind = TEXT("name");
            else if (Property->IsA<FStrProperty>()) ValueKind = TEXT("string");
            else if (Property->IsA<FTextProperty>()) ValueKind = TEXT("text");
            else if (const FStructProperty* Struct = CastField<FStructProperty>(Property))
            {
                ValueKind = TEXT("struct");
                Item->SetStringField(TEXT("struct_path"), Struct->Struct->GetPathName());
            }
            else if (const FClassProperty* ClassProperty = CastField<FClassProperty>(Property))
            {
                ValueKind = TEXT("class_reference");
                Item->SetStringField(TEXT("allowed_class_path"), ClassProperty->MetaClass->GetPathName());
            }
            else if (const FObjectPropertyBase* ObjectProperty = CastField<FObjectPropertyBase>(Property))
            {
                ValueKind = TEXT("object_reference");
                Item->SetStringField(TEXT("allowed_class_path"), ObjectProperty->PropertyClass->GetPathName());
            }
            else if (const FArrayProperty* Array = CastField<FArrayProperty>(Property))
            {
                ValueKind = TEXT("array");
                Item->SetStringField(TEXT("element_type"), Array->Inner->GetCPPType().Left(192));
            }
            else if (const FSetProperty* Set = CastField<FSetProperty>(Property))
            {
                ValueKind = TEXT("set");
                Item->SetStringField(TEXT("element_type"), Set->ElementProp->GetCPPType().Left(192));
            }
            else if (const FMapProperty* Map = CastField<FMapProperty>(Property))
            {
                ValueKind = TEXT("map");
                Item->SetStringField(TEXT("key_type"), Map->KeyProp->GetCPPType().Left(192));
                Item->SetStringField(TEXT("value_type"), Map->ValueProp->GetCPPType().Left(192));
            }
            Item->SetStringField(TEXT("value_kind"), ValueKind);
            if (const FEnumProperty* Enum = CastField<FEnumProperty>(Property))
            {
                UEnum* EnumType = Enum->GetEnum();
                Item->SetStringField(TEXT("enum_path"), EnumType->GetPathName());
                TArray<TSharedPtr<FJsonValue>> Entries;
                const int32 EnumCount = FMath::Min(EnumType->NumEnums(), 128);
                for (int32 EnumIndex = 0; EnumIndex < EnumCount; ++EnumIndex)
                {
                    auto Entry = MakeShared<FJsonObject>();
                    Entry->SetStringField(TEXT("name"), EnumType->GetNameStringByIndex(EnumIndex));
                    Entry->SetStringField(TEXT("value"), LexToString(EnumType->GetValueByIndex(EnumIndex)));
                    Entries.Add(MakeShared<FJsonValueObject>(Entry));
                }
                Item->SetArrayField(TEXT("enum_values"), Entries);
                Item->SetBoolField(TEXT("enum_values_truncated"), EnumType->NumEnums() > EnumCount);
            }
            else if (const FByteProperty* Byte = CastField<FByteProperty>(Property); Byte && Byte->Enum)
            {
                UEnum* EnumType = Byte->Enum;
                Item->SetStringField(TEXT("enum_path"), EnumType->GetPathName());
                TArray<TSharedPtr<FJsonValue>> Entries;
                const int32 EnumCount = FMath::Min(EnumType->NumEnums(), 128);
                for (int32 EnumIndex = 0; EnumIndex < EnumCount; ++EnumIndex)
                {
                    auto Entry = MakeShared<FJsonObject>();
                    Entry->SetStringField(TEXT("name"), EnumType->GetNameStringByIndex(EnumIndex));
                    Entry->SetStringField(TEXT("value"), LexToString(EnumType->GetValueByIndex(EnumIndex)));
                    Entries.Add(MakeShared<FJsonValueObject>(Entry));
                }
                Item->SetArrayField(TEXT("enum_values"), Entries);
                Item->SetBoolField(TEXT("enum_values_truncated"), EnumType->NumEnums() > EnumCount);
            }
            Results.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetStringField(TEXT("class_path"), AssetClass->GetPathName());
        Data->SetStringField(TEXT("parent_class_path"), AssetClass->GetSuperClass() ? AssetClass->GetSuperClass()->GetPathName() : FString());
        Data->SetBoolField(TEXT("abstract"), AssetClass->HasAnyClassFlags(CLASS_Abstract));
        Data->SetBoolField(TEXT("blueprint_generated"), AssetClass->ClassGeneratedBy != nullptr);
        Data->SetBoolField(TEXT("include_inherited"), bIncludeInherited);
        Data->SetArrayField(TEXT("properties"), Results);
        Data->SetNumberField(TEXT("property_count"), Properties.Num());
        Data->SetNumberField(TEXT("returned_count"), Results.Num());
        Data->SetBoolField(TEXT("truncated"), Properties.Num() > Results.Num());
        Data->SetBoolField(TEXT("loads_assets"), false);
        Data->SetStringField(TEXT("scope"), TEXT("Reflected property schema only; no DataAsset instances or referenced objects are loaded."));
        return true;
    }
    if (Command == TEXT("data_asset_edit_preview") || Command == TEXT("data_asset_edit_apply"))
    {
        const bool bPreview = Command == TEXT("data_asset_edit_preview");
        const TSet<FString> Fields = bPreview
            ? TSet<FString>{TEXT("asset_path"), TEXT("properties"), TEXT("save")}
            : TSet<FString>{TEXT("preview_id"), TEXT("confirmation")};
        for (const auto& Pair : Args->Values)
        {
            if (!Fields.Contains(Pair.Key) || !Pair.Value.IsValid() ||
                (Pair.Key == TEXT("properties") ? Pair.Value->Type != EJson::Array :
                 Pair.Key == TEXT("save") ? Pair.Value->Type != EJson::Boolean : Pair.Value->Type != EJson::String))
                return Fail(TEXT("invalid_arguments"), TEXT("DataAsset edit fields must use the documented JSON types."));
        }
        if ((bPreview && (!Args->HasField(TEXT("asset_path")) || !Args->HasField(TEXT("properties")) ||
                          Args->Values.Num() < 2 || Args->Values.Num() > 3)) ||
            (!bPreview && Args->Values.Num() != 2))
            return Fail(TEXT("invalid_arguments"), TEXT("DataAsset edit fields are incomplete."));

        IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        auto ResolveAsset = [&](const FString& InputPath, FString& ObjectPath, FString& PackagePath,
                                FString& Filename, FAssetData& AssetData, UObject*& Object)
        {
            if (InputPath.Len() > 512 || InputPath.Contains(TEXT(":"))) return false;
            PackagePath = InputPath;
            const int32 Dot = InputPath.Find(TEXT("."), ESearchCase::CaseSensitive);
            if (Dot != INDEX_NONE)
            {
                PackagePath = InputPath.Left(Dot);
                const FString ObjectName = InputPath.Mid(Dot + 1);
                if (ObjectName != FPackageName::GetLongPackageAssetName(PackagePath)) return false;
            }
            if (!FPackageName::IsValidLongPackageName(PackagePath) ||
                !(PackagePath.StartsWith(TEXT("/Game/")) || PackagePath.StartsWith(TEXT("/JasperPrism/"))))
                return false;
            ObjectPath = PackagePath + TEXT(".") + FPackageName::GetLongPackageAssetName(PackagePath);
            if (!FPackageName::TryConvertLongPackageNameToFilename(
                    PackagePath, Filename, FPackageName::GetAssetPackageExtension())) return false;
            AssetData = Registry.GetAssetByObjectPath(FSoftObjectPath(ObjectPath));
            Object = AssetData.IsValid() ? AssetData.GetAsset() : nullptr;
            return IsValid(Object) && Object->IsA<UDataAsset>() && Object->GetPathName() == ObjectPath &&
                Object->GetOutermost() && Object->GetOutermost()->GetName() == PackagePath;
        };

        if (bPreview)
        {
            FString InputPath;
            if (!Args->TryGetStringField(TEXT("asset_path"), InputPath) || InputPath.IsEmpty())
                return Fail(TEXT("invalid_arguments"), TEXT("Provide one exact DataAsset object or package path."));
            const TArray<TSharedPtr<FJsonValue>>* Entries = nullptr;
            if (!Args->TryGetArrayField(TEXT("properties"), Entries) || !Entries || Entries->Num() < 1 || Entries->Num() > 32)
                return Fail(TEXT("invalid_arguments"), TEXT("Edit between one and 32 DataAsset properties per preview."));
            FString ObjectPath, PackagePath, Filename;
            FAssetData AssetData;
            UObject* Object = nullptr;
            if (!ResolveAsset(InputPath, ObjectPath, PackagePath, Filename, AssetData, Object))
                return Fail(TEXT("asset_not_found"), TEXT("The exact loaded local DataAsset was not found at an allowed package path."));
            UPackage* Package = Object->GetOutermost();
            if (Package->IsDirty())
                return Fail(TEXT("asset_already_dirty"), TEXT("Save or revert this DataAsset before previewing edits."));
            const FString DiskFingerprint = PackageFingerprint(Filename);
            if (DiskFingerprint.IsEmpty())
                return Fail(TEXT("package_fingerprint_failed"), TEXT("The existing DataAsset package file could not be fingerprinted."));

            TArray<FDataAssetEditValue> Values;
            TSet<FString> Names;
            for (const TSharedPtr<FJsonValue>& Entry : *Entries)
            {
                if (!Entry.IsValid() || Entry->Type != EJson::Object)
                    return Fail(TEXT("invalid_arguments"), TEXT("Each DataAsset edit requires a property name and text value."));
                const TSharedPtr<FJsonObject> Item = Entry->AsObject();
                if (!Item.IsValid() || Item->Values.Num() != 2 ||
                    !Item->HasField(TEXT("name")) || !Item->HasField(TEXT("value")))
                    return Fail(TEXT("invalid_arguments"), TEXT("Each DataAsset edit requires exactly name and value fields."));
                FString Name, Proposed;
                if (!Item->TryGetStringField(TEXT("name"), Name) || Name.IsEmpty() || Name.Len() > 128 ||
                    !Item->TryGetStringField(TEXT("value"), Proposed) || Proposed.Len() > 512)
                    return Fail(TEXT("invalid_arguments"), TEXT("DataAsset property names and values must be bounded strings."));
                for (int32 Index = 0; Index < Name.Len(); ++Index)
                {
                    const TCHAR C = Name[Index];
                    if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
                        (Index > 0 && C >= '0' && C <= '9')))
                        return Fail(TEXT("invalid_arguments"), TEXT("Property names must be exact reflected identifiers."));
                }
                if (Names.Contains(Name))
                    return Fail(TEXT("duplicate_property"), TEXT("A DataAsset property may be edited only once per batch."));
                Names.Add(Name);
                FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Name));
                FString Before, Normalized;
                if (!IsEditableProperty(Object, Property))
                    return Fail(TEXT("property_not_editable"), TEXT("Only supported editable scalar, enum, string/name and common math/color properties can be changed."));
                if (!ExportPropertyText(Object, Property, Before))
                    return Fail(TEXT("property_read_failed"), TEXT("A DataAsset property could not be exported through Unreal reflection."));
                if (!ParsePropertyText(Object, Property, Proposed, Normalized))
                {
                    ErrorCode = TEXT("invalid_property_value");
                    ErrorMessage = FString::Printf(TEXT("DataAsset value for property '%s' could not be parsed for its reflected native type."), *Name);
                    return false;
                }
                Values.Add({Name, Property->GetCPPType(), Before, Normalized});
            }

            for (auto It = DataAssetEditPreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (DataAssetEditPreviews.Num() >= 32)
                return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired DataAsset edit previews are allowed."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FDataAssetEditPreview Plan;
            Plan.Target = Object;
            Plan.AssetPath = ObjectPath;
            Plan.ClassPath = Object->GetClass()->GetPathName();
            Plan.PackagePath = PackagePath;
            Plan.Filename = Filename;
            Plan.DiskFingerprint = DiskFingerprint;
            Plan.Properties = MoveTemp(Values);
            Plan.bSave = Args->HasField(TEXT("save")) && Args->GetBoolField(TEXT("save"));
            Plan.Expires = FPlatformTime::Seconds() + 300.0;
            if (Plan.bSave)
                Plan.BackupPath = FPaths::ConvertRelativePathToFull(FPaths::Combine(
                    FPaths::ProjectSavedDir(), TEXT("ForgeMCP"), TEXT("Backups"), TEXT("DataAssets"),
                    Id + FPackageName::GetAssetPackageExtension()));
            DataAssetEditPreviews.Add(Id, MoveTemp(Plan));
            const FDataAssetEditPreview& Stored = DataAssetEditPreviews.FindChecked(Id);
            TArray<TSharedPtr<FJsonValue>> PropertyResults;
            for (const FDataAssetEditValue& Value : Stored.Properties)
            {
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("name"), Value.Name);
                Item->SetStringField(TEXT("type"), Value.Type);
                Item->SetStringField(TEXT("current_value"), Value.BeforeValue);
                Item->SetStringField(TEXT("proposed_value"), Value.ProposedValue);
                PropertyResults.Add(MakeShared<FJsonValueObject>(Item));
            }
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("asset_path"), ObjectPath);
            Data->SetStringField(TEXT("class_path"), Stored.ClassPath);
            Data->SetArrayField(TEXT("properties"), PropertyResults);
            Data->SetBoolField(TEXT("save"), Stored.bSave);
            Data->SetBoolField(TEXT("overwrites_existing_asset"), Stored.bSave);
            Data->SetStringField(TEXT("package_fingerprint"), Stored.DiskFingerprint);
            Data->SetStringField(TEXT("backup_path"), Stored.BackupPath);
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            Data->SetStringField(TEXT("scope"), TEXT("Reviewed edits to one existing DataAsset; only listed supported properties change; save is explicit and keeps a verified original package backup."));
            return true;
        }

        FString Id, Confirmation;
        if (!Args->TryGetStringField(TEXT("preview_id"), Id) || !Args->TryGetStringField(TEXT("confirmation"), Confirmation) ||
            Id.Len() != 32 || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must exactly match the reviewed DataAsset edit preview ID."));
        FDataAssetEditPreview* Stored = DataAssetEditPreviews.Find(Id);
        if (!Stored) return Fail(TEXT("preview_not_found"), TEXT("The DataAsset edit preview is absent, expired or already used."));
        const FDataAssetEditPreview Plan = *Stored;
        DataAssetEditPreviews.Remove(Id);
        UObject* Object = Plan.Target.Get();
        if (Plan.Expires <= FPlatformTime::Seconds() || !Object || Object->GetPathName() != Plan.AssetPath ||
            Object->GetClass()->GetPathName() != Plan.ClassPath || !Object->IsA<UDataAsset>() ||
            Object->GetOutermost()->GetName() != Plan.PackagePath || Object->GetOutermost()->IsDirty() ||
            PackageFingerprint(Plan.Filename) != Plan.DiskFingerprint)
            return Fail(TEXT("stale_preview"), TEXT("The DataAsset identity, dirty state or saved package changed after preview."));

        for (const FDataAssetEditValue& Value : Plan.Properties)
        {
            FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Value.Name));
            FString Current, Normalized;
            if (!IsEditableProperty(Object, Property) || !ExportPropertyText(Object, Property, Current) ||
                Current != Value.BeforeValue || !ParsePropertyText(Object, Property, Value.ProposedValue, Normalized) ||
                Normalized != Value.ProposedValue)
                return Fail(TEXT("stale_preview"), TEXT("A reviewed DataAsset property changed or is no longer editable."));
        }

        UPackage* Package = Object->GetOutermost();
        FScopedTransaction Transaction(NSLOCTEXT("ForgeMCP", "EditDataAssetProperties", "ForgeMCP Edit DataAsset Properties"));
        const bool bAddedTransactionalFlag = !Object->HasAnyFlags(RF_Transactional);
        if (bAddedTransactionalFlag) Object->SetFlags(RF_Transactional);
        if (!Object->Modify())
        {
            Transaction.Cancel();
            if (bAddedTransactionalFlag) Object->ClearFlags(RF_Transactional);
            return Fail(TEXT("transaction_unavailable"), TEXT("Unreal could not record the DataAsset in an Editor transaction."));
        }
        FOutputDeviceNull ErrorOutput;
        auto RestoreProperties = [&]()
        {
            bool bRestored = true;
            for (int32 Index = Plan.Properties.Num() - 1; Index >= 0; --Index)
            {
                const FDataAssetEditValue& Value = Plan.Properties[Index];
                FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Value.Name));
                if (!Property) { bRestored = false; continue; }
                Object->PreEditChange(Property);
                if (!ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Object),
                    Object, Value.BeforeValue, ErrorOutput)) bRestored = false;
                FPropertyChangedEvent Change(Property, EPropertyChangeType::ValueSet);
                Object->PostEditChangeProperty(Change);
            }
            Transaction.Cancel();
            if (bAddedTransactionalFlag) Object->ClearFlags(RF_Transactional);
            Package->SetDirtyFlag(false);
            return bRestored;
        };
        auto RollbackFailure = [&](const TCHAR* Code, const TCHAR* Message)
        {
            const bool bRestored = RestoreProperties();
            return Fail(bRestored ? Code : TEXT("rollback_failed"), bRestored ? Message :
                TEXT("DataAsset edit failed and in-memory rollback could not be verified; inspect the listed original package backup."));
        };

        for (const FDataAssetEditValue& Value : Plan.Properties)
        {
            FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Value.Name));
            Object->PreEditChange(Property);
            if (!ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Object),
                Object, Value.ProposedValue, ErrorOutput))
                return RollbackFailure(TEXT("property_edit_failed"), TEXT("A DataAsset property failed native apply; all values were restored."));
            FPropertyChangedEvent Change(Property, EPropertyChangeType::ValueSet);
            Object->PostEditChangeProperty(Change);
            FString Observed;
            if (!ExportPropertyText(Object, Property, Observed) || Observed != Value.ProposedValue)
                return RollbackFailure(TEXT("property_verification_failed"), TEXT("A DataAsset value failed native read-back; all values were restored."));
        }

        if (Plan.bSave)
        {
            const FString BackupDirectory = FPaths::GetPath(Plan.BackupPath);
            if (Plan.BackupPath.IsEmpty() || !IFileManager::Get().MakeDirectory(*BackupDirectory, true) ||
                IFileManager::Get().Copy(*Plan.BackupPath, *Plan.Filename, false, false) != COPY_OK ||
                PackageFingerprint(Plan.BackupPath) != Plan.DiskFingerprint)
            {
                if (!Plan.BackupPath.IsEmpty() && IFileManager::Get().FileExists(*Plan.BackupPath))
                    IFileManager::Get().Delete(*Plan.BackupPath, false, true);
                return RollbackFailure(TEXT("backup_failed"), TEXT("The original DataAsset package could not be backed up and verified; in-memory edits were rolled back."));
            }
            FSavePackageArgs SaveArgs;
            SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
            SaveArgs.SaveFlags = SAVE_NoError;
            const bool bSaved = UPackage::SavePackage(Package, Object, *Plan.Filename, SaveArgs);
            const FString SavedFingerprint = PackageFingerprint(Plan.Filename);
            if (!bSaved || SavedFingerprint.IsEmpty())
            {
                const bool bDiskRestored = IFileManager::Get().Copy(*Plan.Filename, *Plan.BackupPath, true, true) == COPY_OK &&
                    PackageFingerprint(Plan.Filename) == Plan.DiskFingerprint;
                const bool bMemoryRestored = RestoreProperties();
                return Fail(bDiskRestored && bMemoryRestored ? TEXT("asset_save_failed") : TEXT("rollback_failed"),
                    bDiskRestored && bMemoryRestored ? TEXT("DataAsset save verification failed; disk and memory state were restored from the verified backup.") :
                    TEXT("DataAsset save failed and restoration is incomplete; preserve the backup and inspect package state before retrying."));
            }
            Package->SetDirtyFlag(false);
            Data->SetStringField(TEXT("saved_package_fingerprint"), SavedFingerprint);
        }
        TArray<TSharedPtr<FJsonValue>> Results;
        for (const FDataAssetEditValue& Value : Plan.Properties)
        {
            FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Value.Name));
            FString Observed;
            ExportPropertyText(Object, Property, Observed);
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Value.Name);
            Item->SetStringField(TEXT("type"), Value.Type);
            Item->SetStringField(TEXT("previous_value"), Value.BeforeValue);
            Item->SetStringField(TEXT("value"), Observed);
            Results.Add(MakeShared<FJsonValueObject>(Item));
        }
        Data->SetStringField(TEXT("asset_path"), Object->GetPathName());
        Data->SetArrayField(TEXT("properties"), Results);
        Data->SetBoolField(TEXT("saved"), Plan.bSave);
        Data->SetBoolField(TEXT("package_dirty"), Package->IsDirty());
        Data->SetBoolField(TEXT("native_readback_verified"), true);
        Data->SetStringField(TEXT("backup_path"), Plan.BackupPath);
        Data->SetBoolField(TEXT("backup_preserved"), Plan.bSave && PackageFingerprint(Plan.BackupPath) == Plan.DiskFingerprint);
        Data->SetBoolField(TEXT("overwrote_existing_asset"), Plan.bSave);
        Data->SetStringField(TEXT("verification_scope"), Plan.bSave
            ? TEXT("Native property values read back and package save produced a valid file; reopen verification requires a fresh editor load.")
            : TEXT("Native property values read back in memory; package remains unsaved."));
        return true;
    }
    if (Command == TEXT("data_asset_create_preview") || Command == TEXT("data_asset_create_apply"))
    {
        const bool bPreview = Command == TEXT("data_asset_create_preview");
        const TSet<FString> Fields = bPreview
            ? TSet<FString>{TEXT("asset_path"), TEXT("class_path"), TEXT("properties"), TEXT("save")}
            : TSet<FString>{TEXT("preview_id"), TEXT("confirmation")};
        for (const auto& Pair : Args->Values)
            if (!Fields.Contains(Pair.Key) || !Pair.Value.IsValid() ||
                (bPreview && Pair.Key == TEXT("properties") ? Pair.Value->Type != EJson::Array : Pair.Value->Type != EJson::String && Pair.Key != TEXT("save")) ||
                (Pair.Key == TEXT("save") && Pair.Value->Type != EJson::Boolean))
                return Fail(TEXT("invalid_arguments"), TEXT("DataAsset creation requires only its documented fields and JSON types."));
        if ((bPreview && (Args->Values.Num() < 2 || Args->Values.Num() > 4)) ||
            (!bPreview && Args->Values.Num() != 2))
            return Fail(TEXT("invalid_arguments"), TEXT("DataAsset creation fields are incomplete."));

        IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        auto ResolveTarget = [&](const FString& InputPath, FString& PackagePath, FString& AssetName, FString& ObjectPath, FString& Filename)
        {
            PackagePath = InputPath;
            if (PackagePath.Contains(TEXT(".")) || PackagePath.Contains(TEXT(":")) || PackagePath.Len() > 240 ||
                !FPackageName::IsValidLongPackageName(PackagePath) ||
                !(PackagePath.StartsWith(TEXT("/Game/")) || PackagePath.StartsWith(TEXT("/JasperPrism/"))))
                return false;
            AssetName = FPackageName::GetLongPackageAssetName(PackagePath);
            if (AssetName.IsEmpty() || AssetName.Len() > 64) return false;
            for (int32 Index = 0; Index < AssetName.Len(); ++Index)
            {
                const TCHAR C = AssetName[Index];
                if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
                    (Index > 0 && C >= '0' && C <= '9'))) return false;
            }
            ObjectPath = PackagePath + TEXT(".") + AssetName;
            return FPackageName::TryConvertLongPackageNameToFilename(
                PackagePath, Filename, FPackageName::GetAssetPackageExtension());
        };
        auto TargetAbsent = [&](const FString& PackagePath, const FString& ObjectPath, const FString& Filename)
        {
            return !Registry.GetAssetByObjectPath(FSoftObjectPath(ObjectPath)).IsValid() &&
                !IFileManager::Get().FileExists(*Filename) && FindPackage(nullptr, *PackagePath) == nullptr;
        };

        if (bPreview)
        {
            FString AssetPath, ClassPath, PackagePath, AssetName, ObjectPath, Filename;
            if (!Args->TryGetStringField(TEXT("asset_path"), AssetPath) ||
                !Args->TryGetStringField(TEXT("class_path"), ClassPath) ||
                !ResolveTarget(AssetPath, PackagePath, AssetName, ObjectPath, Filename) ||
                ClassPath.Len() < 8 || ClassPath.Len() > 512 ||
                !(ClassPath.StartsWith(TEXT("/Script/")) || ClassPath.StartsWith(TEXT("/Game/"))))
                return Fail(TEXT("invalid_arguments"), TEXT("Provide an exact /Game or /JasperPrism package path and a loaded DataAsset class path."));
            if (!TargetAbsent(PackagePath, ObjectPath, Filename))
                return Fail(TEXT("asset_exists"), TEXT("The exact DataAsset target exists in memory, the Asset Registry, or on disk."));

            UClass* AssetClass = nullptr;
            for (TObjectIterator<UClass> It; It; ++It)
                if (*It && (*It)->GetPathName() == ClassPath) { AssetClass = *It; break; }
            if (!AssetClass)
                return Fail(TEXT("class_not_loaded"), TEXT("Discover the exact loaded DataAsset class before creation."));
            if (!AssetClass->IsChildOf(UDataAsset::StaticClass()) || AssetClass == UDataAsset::StaticClass() ||
                AssetClass->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists | CLASS_Hidden | CLASS_HideDropDown))
                return Fail(TEXT("unsupported_data_asset_class"), TEXT("Creation requires a concrete, current, visible UDataAsset-derived class."));

            TArray<TPair<FString, FString>> Values;
            TSet<FString> Names;
            if (const TArray<TSharedPtr<FJsonValue>>* PropertyValues = nullptr; Args->TryGetArrayField(TEXT("properties"), PropertyValues))
            {
                if (PropertyValues->Num() > 32)
                    return Fail(TEXT("invalid_arguments"), TEXT("At most 32 initial DataAsset property values are supported."));
                UObject* Defaults = AssetClass->GetDefaultObject();
                for (const TSharedPtr<FJsonValue>& Entry : *PropertyValues)
                {
                    const TSharedPtr<FJsonObject>* PropertyObject = nullptr;
                    if (!Entry.IsValid() || !Entry->TryGetObject(PropertyObject) || !PropertyObject || !PropertyObject->IsValid() ||
                        (*PropertyObject)->Values.Num() != 2)
                        return Fail(TEXT("invalid_arguments"), TEXT("Each initial property requires exactly a name and text value."));
                    FString PropertyName, Proposed;
                    if (!(*PropertyObject)->TryGetStringField(TEXT("name"), PropertyName) || PropertyName.Len() > 128 ||
                        !(*PropertyObject)->TryGetStringField(TEXT("value"), Proposed) || Proposed.Len() > 512)
                        return Fail(TEXT("invalid_arguments"), TEXT("Initial property names and text values must be bounded strings."));
                    for (int32 Index = 0; Index < PropertyName.Len(); ++Index)
                    {
                        const TCHAR C = PropertyName[Index];
                        if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
                            (Index > 0 && C >= '0' && C <= '9')))
                            return Fail(TEXT("invalid_arguments"), TEXT("Property names must be exact reflected identifiers."));
                    }
                    if (Names.Contains(PropertyName))
                        return Fail(TEXT("duplicate_property"), TEXT("Initial DataAsset properties must be unique."));
                    Names.Add(PropertyName);
                    FProperty* Property = FindFProperty<FProperty>(AssetClass, FName(*PropertyName));
                    if (!IsEditableProperty(Defaults, Property))
                        return Fail(TEXT("property_not_editable"), TEXT("Initial values require an editable supported scalar, enum, name/string, vector, rotator or color property."));
                    FString Normalized;
                    if (!ParsePropertyText(Defaults, Property, Proposed, Normalized))
                        return Fail(TEXT("invalid_property_value"), TEXT("An initial value could not be parsed as its native reflected property type."));
                    Values.Emplace(PropertyName, Normalized);
                }
            }

            for (auto It = DataAssetCreatePreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (DataAssetCreatePreviews.Num() >= 32)
                return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired DataAsset creation previews are allowed."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FDataAssetCreatePreview Plan;
            Plan.AssetClass = AssetClass;
            Plan.ClassPath = ClassPath;
            Plan.PackagePath = PackagePath;
            Plan.AssetName = AssetName;
            Plan.Properties = MoveTemp(Values);
            Plan.bSave = Args->HasField(TEXT("save")) ? Args->GetBoolField(TEXT("save")) : false;
            Plan.Expires = FPlatformTime::Seconds() + 300.0;
            DataAssetCreatePreviews.Add(Id, MoveTemp(Plan));
            const FDataAssetCreatePreview& Stored = DataAssetCreatePreviews.FindChecked(Id);
            TArray<TSharedPtr<FJsonValue>> PropertyResults;
            for (const TPair<FString, FString>& Value : Stored.Properties)
            {
                FProperty* Property = FindFProperty<FProperty>(AssetClass, FName(*Value.Key));
                auto Item = MakeShared<FJsonObject>();
                Item->SetStringField(TEXT("name"), Value.Key);
                Item->SetStringField(TEXT("type"), Property ? Property->GetCPPType() : FString());
                Item->SetStringField(TEXT("normalized_value"), Value.Value);
                PropertyResults.Add(MakeShared<FJsonValueObject>(Item));
            }
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("asset_path"), ObjectPath);
            Data->SetStringField(TEXT("class_path"), ClassPath);
            Data->SetArrayField(TEXT("initial_properties"), PropertyResults);
            Data->SetBoolField(TEXT("save"), Stored.bSave);
            Data->SetBoolField(TEXT("overwrites_existing_asset"), false);
            Data->SetNumberField(TEXT("expires_in_seconds"), 300);
            Data->SetStringField(TEXT("scope"), TEXT("Create one new UDataAsset-derived object; no existing asset is loaded, overwritten or saved unless save=true."));
            return true;
        }

        FString Id, Confirmation;
        if (!Args->TryGetStringField(TEXT("preview_id"), Id) || !Args->TryGetStringField(TEXT("confirmation"), Confirmation) ||
            Id.Len() != 32 || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must exactly match the reviewed DataAsset preview ID."));
        FDataAssetCreatePreview* Stored = DataAssetCreatePreviews.Find(Id);
        if (!Stored) return Fail(TEXT("preview_not_found"), TEXT("DataAsset creation preview is absent, expired, or already used."));
        const FDataAssetCreatePreview Plan = *Stored;
        DataAssetCreatePreviews.Remove(Id);
        UClass* AssetClass = Plan.AssetClass.Get();
        FString ObjectPath, Filename, ConfirmedPackage, ConfirmedName;
        if (Plan.Expires <= FPlatformTime::Seconds() || !AssetClass || AssetClass->GetPathName() != Plan.ClassPath ||
            !ResolveTarget(Plan.PackagePath, ConfirmedPackage, ConfirmedName, ObjectPath, Filename) ||
            ConfirmedPackage != Plan.PackagePath || ConfirmedName != Plan.AssetName ||
            !TargetAbsent(Plan.PackagePath, ObjectPath, Filename))
            return Fail(TEXT("stale_preview"), TEXT("DataAsset class or target package state changed after preview."));

        UPackage* Package = CreatePackage(*Plan.PackagePath);
        UObject* Asset = Package ? NewObject<UObject>(Package, AssetClass, FName(*Plan.AssetName),
            RF_Public | RF_Standalone | RF_Transactional) : nullptr;
        if (!Asset)
            return Fail(TEXT("asset_creation_failed"), TEXT("Unreal could not construct the new DataAsset instance."));
        bool bRegistered = false;
        auto RollbackCreatedAsset = [&]()
        {
            if (bRegistered)
            {
                Registry.AssetDeleted(Asset);
                bRegistered = false;
            }
            Asset->ClearFlags(RF_Public | RF_Standalone | RF_Transactional);
            Asset->Rename(nullptr, GetTransientPackage(), REN_DontCreateRedirectors | REN_NonTransactional);
            Asset->MarkAsGarbage();
            Package->SetDirtyFlag(false);
        };
        TArray<TSharedPtr<FJsonValue>> AppliedProperties;
        for (const TPair<FString, FString>& Value : Plan.Properties)
        {
            FProperty* Property = FindFProperty<FProperty>(AssetClass, FName(*Value.Key));
            FString Normalized;
            if (!IsEditableProperty(Asset, Property) || !ParsePropertyText(Asset, Property, Value.Value, Normalized) || Normalized != Value.Value)
            {
                RollbackCreatedAsset();
                return Fail(TEXT("property_application_failed"), TEXT("An initial DataAsset property failed revalidation; the new asset was removed."));
            }
            Asset->PreEditChange(Property);
            FOutputDeviceNull ErrorOutput;
            if (!ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Asset),
                Asset, Value.Value, ErrorOutput))
            {
                RollbackCreatedAsset();
                return Fail(TEXT("property_application_failed"), TEXT("An initial DataAsset property could not be applied; the new asset was removed."));
            }
            FPropertyChangedEvent Change(Property, EPropertyChangeType::ValueSet);
            Asset->PostEditChangeProperty(Change);
            FString Observed;
            if (!ExportPropertyText(Asset, Property, Observed) || Observed != Value.Value)
            {
                RollbackCreatedAsset();
                return Fail(TEXT("property_verification_failed"), TEXT("An initial DataAsset property failed read-back; the new asset was removed."));
            }
            auto Item = MakeShared<FJsonObject>();
            Item->SetStringField(TEXT("name"), Value.Key);
            Item->SetStringField(TEXT("type"), Property->GetCPPType());
            Item->SetStringField(TEXT("value"), Observed);
            AppliedProperties.Add(MakeShared<FJsonValueObject>(Item));
        }
        FAssetRegistryModule::AssetCreated(Asset);
        bRegistered = true;
        Package->MarkPackageDirty();
        bool bSaved = false;
        if (Plan.bSave)
        {
            if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Filename), true))
            {
                RollbackCreatedAsset();
                return Fail(TEXT("asset_save_failed"), TEXT("Unreal could not create the destination content directory."));
            }
            FSavePackageArgs SaveArgs;
            SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
            SaveArgs.SaveFlags = SAVE_NoError;
            bSaved = UPackage::SavePackage(Package, Asset, *Filename, SaveArgs);
            if (!bSaved || !IFileManager::Get().FileExists(*Filename))
            {
                if (IFileManager::Get().FileExists(*Filename)) IFileManager::Get().Delete(*Filename, false, true);
                RollbackCreatedAsset();
                return Fail(TEXT("asset_save_failed"), TEXT("The new DataAsset package failed save verification and was removed."));
            }
        }
        Data->SetStringField(TEXT("asset_path"), Asset->GetPathName());
        Data->SetStringField(TEXT("class_path"), AssetClass->GetPathName());
        Data->SetArrayField(TEXT("properties"), AppliedProperties);
        Data->SetBoolField(TEXT("saved"), bSaved);
        Data->SetBoolField(TEXT("package_dirty"), Package->IsDirty());
        Data->SetBoolField(TEXT("overwrote_existing_asset"), false);
        Data->SetBoolField(TEXT("native_readback_verified"), true);
        Data->SetStringField(TEXT("verification_scope"), bSaved
            ? TEXT("New package exists and property values were verified in memory; asset was not closed and reopened.")
            : TEXT("Property values were verified in memory; asset remains unsaved in the editor."));
        return true;
    }
    if (OpenAsset || SyncBrowser)
    {
        if (Args->Values.Num() != 1 || !Args->HasField(TEXT("asset_path")) ||
            !Args->Values[TEXT("asset_path")].IsValid() || Args->Values[TEXT("asset_path")]->Type != EJson::String)
            return Fail(TEXT("invalid_arguments"), TEXT("Provide only one exact asset_path string."));
        FString AssetPath;
        Args->TryGetStringField(TEXT("asset_path"), AssetPath);
        if (AssetPath.Len() > 240 || AssetPath.Contains(TEXT(":")))
            return Fail(TEXT("invalid_arguments"), TEXT("Asset path must be a bounded package or object path."));
        FString Package = AssetPath;
        int32 Dot = INDEX_NONE;
        if (AssetPath.FindChar(TEXT('.'), Dot))
        {
            Package = AssetPath.Left(Dot);
            if (AssetPath.Mid(Dot + 1) != FPackageName::GetLongPackageAssetName(Package))
                return Fail(TEXT("invalid_arguments"), TEXT("Only an exact top-level package asset path is supported."));
        }
        if (!FPackageName::IsValidLongPackageName(Package) ||
            !(Package.StartsWith(TEXT("/Game/")) || Package.StartsWith(TEXT("/JasperPrism/"))))
            return Fail(TEXT("unsupported_asset_path"), TEXT("Browser operations are limited to /Game and /JasperPrism assets."));
        if (!AssetPath.Contains(TEXT("."))) AssetPath += TEXT(".") + FPackageName::GetLongPackageAssetName(Package);
        IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
        const FAssetData Asset = Registry.GetAssetByObjectPath(FSoftObjectPath(AssetPath));
        if (!Asset.IsValid()) return Fail(TEXT("asset_not_found"), TEXT("Asset is not present in the current registry."));
        if (SyncBrowser)
        {
            TArray<FAssetData> Targets{Asset};
            FModuleManager::LoadModuleChecked<FContentBrowserModule>(TEXT("ContentBrowser")).Get().SyncBrowserToAssets(Targets, false, true);
            Data->SetObjectField(TEXT("asset"), Describe(Asset));
            Data->SetBoolField(TEXT("sync_requested"), true);
            Data->SetStringField(TEXT("verification_scope"), TEXT("Content Browser navigation request accepted; visual focus is not verified."));
            return true;
        }
        if (FApp::IsUnattended())
            return Fail(TEXT("interactive_editor_required"), TEXT("Opening asset editors requires an interactive Unreal Editor session."));
        UObject* Object = Asset.GetAsset();
        if (!Object) return Fail(TEXT("asset_load_failed"), TEXT("The selected asset could not be loaded."));
        UAssetEditorSubsystem* Editors = GEditor ? GEditor->GetEditorSubsystem<UAssetEditorSubsystem>() : nullptr;
        if (!Editors || !Editors->OpenEditorForAsset(Object))
            return Fail(TEXT("asset_open_failed"), TEXT("Unreal did not open an editor for this asset."));
        Data->SetObjectField(TEXT("asset"), Describe(Asset));
        Data->SetBoolField(TEXT("opened"), true);
        Data->SetBoolField(TEXT("saved"), false);
        return true;
    }
    const bool Search = Command == TEXT("asset_search");
    const bool Properties = Command == TEXT("asset_property_info");
    const bool EditPreview = Command == TEXT("asset_property_edit_preview");
    const bool EditApply = Command == TEXT("asset_property_edit_apply");
    if (EditPreview || EditApply)
    {
        const TSet<FString> EditFields = EditPreview
            ? TSet<FString>{TEXT("asset_path"), TEXT("property_name"), TEXT("property_value")}
            : TSet<FString>{TEXT("preview_id"), TEXT("confirmation")};
        for (const auto& Pair : Args->Values)
            if (!EditFields.Contains(Pair.Key) || !Pair.Value.IsValid() || Pair.Value->Type != EJson::String)
                return Fail(TEXT("invalid_arguments"), TEXT("Asset property edits require only their documented string fields."));
        if (Args->Values.Num() != EditFields.Num())
            return Fail(TEXT("invalid_arguments"), TEXT("Asset property edit fields are incomplete."));
        if (EditPreview)
        {
            FString AssetPath, PropertyName, Proposed;
            if (!Args->TryGetStringField(TEXT("asset_path"), AssetPath) || AssetPath.Len() > 240 ||
                !Args->TryGetStringField(TEXT("property_name"), PropertyName) || PropertyName.Len() > 128 ||
                !Args->TryGetStringField(TEXT("property_value"), Proposed) || Proposed.Len() > 512)
                return Fail(TEXT("invalid_arguments"), TEXT("Asset path, property name or property value is outside its limit."));
            for (int32 Index = 0; Index < PropertyName.Len(); ++Index)
            {
                const TCHAR C = PropertyName[Index];
                if (!((C >= 'a' && C <= 'z') || (C >= 'A' && C <= 'Z') || C == '_' ||
                    (Index > 0 && C >= '0' && C <= '9')))
                    return Fail(TEXT("invalid_arguments"), TEXT("Property names must be exact reflected identifiers."));
            }
            FString Package = AssetPath;
            int32 Dot = INDEX_NONE;
            if (AssetPath.FindChar(TEXT('.'), Dot)) Package = AssetPath.Left(Dot);
            if (!FPackageName::IsValidLongPackageName(Package) ||
                !(Package.StartsWith(TEXT("/Game/")) || Package.StartsWith(TEXT("/JasperPrism/"))))
                return Fail(TEXT("unsupported_asset_path"), TEXT("Property edits are limited to /Game and /JasperPrism assets."));
            if (!AssetPath.Contains(TEXT("."))) AssetPath += TEXT(".") + FPackageName::GetLongPackageAssetName(Package);
            IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
            const FAssetData Asset = Registry.GetAssetByObjectPath(FSoftObjectPath(AssetPath));
            UObject* Object = Asset.IsValid() ? Asset.GetAsset() : nullptr;
            if (!Object) return Fail(TEXT("asset_load_failed"), TEXT("The selected asset could not be loaded."));
            if (Object->GetOutermost()->IsDirty())
                return Fail(TEXT("asset_already_dirty"), TEXT("Save or revert this asset before previewing an edit."));
            FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*PropertyName));
            if (!IsEditableProperty(Object, Property))
                return Fail(TEXT("property_not_editable"), TEXT("The exact property is not in the supported editable property set."));
            FString Before, Normalized;
            if (!ExportPropertyText(Object, Property, Before) || !ParsePropertyText(Object, Property, Proposed, Normalized))
                return Fail(TEXT("invalid_property_value"), TEXT("The proposed value could not be parsed as this native property type."));
            if (Before == Normalized) return Fail(TEXT("no_change"), TEXT("The proposed property value already matches the current value."));
            for (auto It = PropertyEditPreviews.CreateIterator(); It; ++It)
                if (It.Value().Expires <= FPlatformTime::Seconds()) It.RemoveCurrent();
            if (PropertyEditPreviews.Num() >= 32)
                return Fail(TEXT("preview_limit"), TEXT("At most 32 unexpired asset-property previews are allowed."));
            const FString Id = FGuid::NewGuid().ToString(EGuidFormats::Digits).ToLower();
            FPropertyEditPreview Plan;
            Plan.Target = Object;
            Plan.AssetPath = Object->GetPathName();
            Plan.ClassPath = Object->GetClass()->GetPathName();
            Plan.PropertyName = PropertyName;
            Plan.BeforeValue = Before;
            Plan.ProposedValue = Normalized;
            Plan.Expires = FPlatformTime::Seconds() + 300.0;
            PropertyEditPreviews.Add(Id, MoveTemp(Plan));
            Data->SetStringField(TEXT("preview_id"), Id);
            Data->SetStringField(TEXT("asset_path"), Object->GetPathName());
            Data->SetStringField(TEXT("class_path"), Object->GetClass()->GetPathName());
            Data->SetStringField(TEXT("property_name"), PropertyName);
            Data->SetStringField(TEXT("property_type"), Property->GetCPPType());
            Data->SetStringField(TEXT("current_value"), Before);
            Data->SetStringField(TEXT("proposed_value"), Normalized);
            Data->SetBoolField(TEXT("save_package"), false);
            Data->SetBoolField(TEXT("will_enable_transaction_tracking"), !Object->HasAnyFlags(RF_Transactional));
            Data->SetStringField(TEXT("apply_scope"), TEXT("Reviewed in-memory property edit only; package saving is not performed."));
            return true;
        }

        FString Id, Confirmation;
        if (!Args->TryGetStringField(TEXT("preview_id"), Id) || !Args->TryGetStringField(TEXT("confirmation"), Confirmation) ||
            Id.Len() != 32 || Id != Confirmation)
            return Fail(TEXT("confirmation_required"), TEXT("Confirmation must exactly match the reviewed preview ID."));
        FPropertyEditPreview* Stored = PropertyEditPreviews.Find(Id);
        if (!Stored) return Fail(TEXT("preview_not_found"), TEXT("Asset property preview is absent, expired or already used."));
        const FPropertyEditPreview Plan = *Stored;
        PropertyEditPreviews.Remove(Id);
        UObject* Object = Plan.Target.Get();
        if (Plan.Expires <= FPlatformTime::Seconds() || !Object || Object->GetPathName() != Plan.AssetPath ||
            Object->GetClass()->GetPathName() != Plan.ClassPath || Object->GetOutermost()->IsDirty())
            return Fail(TEXT("stale_preview"), TEXT("The asset identity or package state changed; preview the edit again."));
        FProperty* Property = FindFProperty<FProperty>(Object->GetClass(), FName(*Plan.PropertyName));
        FString Current, Normalized;
        if (!IsEditableProperty(Object, Property) || !ExportPropertyText(Object, Property, Current) ||
            Current != Plan.BeforeValue || !ParsePropertyText(Object, Property, Plan.ProposedValue, Normalized) ||
            Normalized != Plan.ProposedValue)
            return Fail(TEXT("stale_preview"), TEXT("The target property changed or is no longer editable."));

        UPackage* Package = Object->GetOutermost();
        FScopedTransaction Transaction(NSLOCTEXT("ForgeMCP", "EditAssetProperty", "ForgeMCP Edit Asset Property"));
        const bool bAddedTransactionalFlag = !Object->HasAnyFlags(RF_Transactional);
        if (bAddedTransactionalFlag) Object->SetFlags(RF_Transactional);
        if (!Object->Modify())
        {
            Transaction.Cancel();
            if (bAddedTransactionalFlag) Object->ClearFlags(RF_Transactional);
            return Fail(TEXT("transaction_unavailable"), TEXT("Unreal could not record the asset in an Editor transaction."));
        }
        Object->PreEditChange(Property);
        FOutputDeviceNull ErrorOutput;
        if (!ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Object),
            Object, Plan.ProposedValue, ErrorOutput))
        {
            ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Object),
                Object, Plan.BeforeValue, ErrorOutput);
            FPropertyChangedEvent FailedEvent(Property, EPropertyChangeType::ValueSet);
            Object->PostEditChangeProperty(FailedEvent);
            Transaction.Cancel();
            if (bAddedTransactionalFlag) Object->ClearFlags(RF_Transactional);
            Package->SetDirtyFlag(false);
            return Fail(TEXT("property_edit_failed"), TEXT("Native property application failed; the original value was restored."));
        }
        FPropertyChangedEvent ChangedEvent(Property, EPropertyChangeType::ValueSet);
        Object->PostEditChangeProperty(ChangedEvent);
        FString Applied;
        if (!ExportPropertyText(Object, Property, Applied) || Applied != Plan.ProposedValue)
        {
            Object->PreEditChange(Property);
            ImportPropertyText(Property, Property->ContainerPtrToValuePtr<void>(Object),
                Object, Plan.BeforeValue, ErrorOutput);
            FPropertyChangedEvent RollbackEvent(Property, EPropertyChangeType::ValueSet);
            Object->PostEditChangeProperty(RollbackEvent);
            Transaction.Cancel();
            if (bAddedTransactionalFlag) Object->ClearFlags(RF_Transactional);
            Package->SetDirtyFlag(false);
            return Fail(TEXT("property_verification_failed"), TEXT("The applied value failed verification and the original value was restored."));
        }
        Data->SetStringField(TEXT("asset_path"), Object->GetPathName());
        Data->SetStringField(TEXT("property_name"), Plan.PropertyName);
        Data->SetStringField(TEXT("property_type"), Property->GetCPPType());
        Data->SetStringField(TEXT("previous_value"), Plan.BeforeValue);
        Data->SetStringField(TEXT("applied_value"), Applied);
        Data->SetBoolField(TEXT("package_dirty"), Object->GetOutermost()->IsDirty());
        Data->SetBoolField(TEXT("saved"), false);
        Data->SetBoolField(TEXT("undo_transaction_recorded"), true);
        Data->SetBoolField(TEXT("transactional_flag_added"), bAddedTransactionalFlag);
        return true;
    }
    const TSet<FString> Fields = Search
        ? TSet<FString>{TEXT("path"), TEXT("class_path"), TEXT("name_contains"), TEXT("recursive"), TEXT("limit"), TEXT("offset")}
        : TSet<FString>{TEXT("asset_path"), TEXT("limit")};
    for (const auto& Pair : Args->Values)
    {
        if (!Fields.Contains(Pair.Key)) return Fail(TEXT("invalid_arguments"), TEXT("Unknown asset query field."));
        const EJson Expected = Pair.Key == TEXT("recursive") ? EJson::Boolean
            : (Pair.Key == TEXT("limit") || Pair.Key == TEXT("offset")) ? EJson::Number : EJson::String;
        if (!Pair.Value.IsValid() || Pair.Value->Type != Expected)
            return Fail(TEXT("invalid_arguments"), TEXT("Asset query fields must use their exact JSON types."));
    }
    double Limit = 100, Offset = 0;
    if ((Args->HasField(TEXT("limit")) && !Args->TryGetNumberField(TEXT("limit"), Limit)) ||
        Limit < 1 || Limit > 200 || FMath::FloorToDouble(Limit) != Limit)
        return Fail(TEXT("invalid_arguments"), TEXT("limit must be an integer from 1 to 200."));
    IAssetRegistry& Registry = FModuleManager::LoadModuleChecked<FAssetRegistryModule>(TEXT("AssetRegistry")).Get();
    Data->SetBoolField(TEXT("registry_loading"), Registry.IsLoadingAssets());
    Data->SetBoolField(TEXT("loads_assets"), false);
    if (Search)
    {
        FString Path = TEXT("/Game"), ClassPath, Name;
        bool Recursive = true;
        if ((Args->HasField(TEXT("path")) && !Args->TryGetStringField(TEXT("path"), Path)) ||
            (Args->HasField(TEXT("class_path")) && !Args->TryGetStringField(TEXT("class_path"), ClassPath)) ||
            (Args->HasField(TEXT("name_contains")) && !Args->TryGetStringField(TEXT("name_contains"), Name)) ||
            (Args->HasField(TEXT("recursive")) && !Args->TryGetBoolField(TEXT("recursive"), Recursive)) ||
            (Args->HasField(TEXT("offset")) && !Args->TryGetNumberField(TEXT("offset"), Offset)) ||
            Path.Len() > 240 || !FPackageName::IsValidLongPackageName(Path) ||
            Name.Len() > 64 || ClassPath.Len() > 240 || Offset < 0 || Offset > 100000 || FMath::FloorToDouble(Offset) != Offset)
            return Fail(TEXT("invalid_arguments"), TEXT("Invalid bounded registry query."));
        FARFilter Filter;
        Filter.PackagePaths.Add(FName(*Path));
        Filter.bRecursivePaths = Recursive;
        if (!ClassPath.IsEmpty())
        {
            if (!ClassPath.StartsWith(TEXT("/Script/")) || !ClassPath.Contains(TEXT(".")))
                return Fail(TEXT("invalid_arguments"), TEXT("class_path must be an exact native /Script/ class path."));
            Filter.ClassPaths.Add(FTopLevelAssetPath(ClassPath));
        }
        TArray<FAssetData> Assets;
        Registry.GetAssets(Filter, Assets);
        Assets.RemoveAll([&](const FAssetData& Asset) { return !Asset.AssetName.ToString().Contains(Name); });
        Assets.Sort([](const FAssetData& A, const FAssetData& B)
            { return A.GetSoftObjectPath().ToString() < B.GetSoftObjectPath().ToString(); });
        TArray<TSharedPtr<FJsonValue>> Results;
        const int32 Start = FMath::Min(static_cast<int32>(Offset), Assets.Num());
        const int32 End = FMath::Min(Start + static_cast<int32>(Limit), Assets.Num());
        for (int32 Index = Start; Index < End; ++Index)
            Results.Add(MakeShared<FJsonValueObject>(Describe(Assets[Index])));
        Data->SetArrayField(TEXT("assets"), Results);
        Data->SetNumberField(TEXT("total_count"), Assets.Num());
        Data->SetNumberField(TEXT("offset"), Offset);
        Data->SetNumberField(TEXT("next_offset"), End);
        Data->SetBoolField(TEXT("truncated"), End < Assets.Num());
        Data->SetStringField(TEXT("pagination"), TEXT("Live sorted registry snapshot; changes between pages may shift results."));
        return true;
    }
    FString AssetPath;
    if (!Args->TryGetStringField(TEXT("asset_path"), AssetPath) || AssetPath.Len() > 240)
        return Fail(TEXT("invalid_arguments"), TEXT("Expected a bounded package or object path."));
    FString Package = AssetPath;
    int32 Dot;
    if (AssetPath.FindChar(TEXT('.'), Dot)) Package = AssetPath.Left(Dot);
    if (!FPackageName::IsValidLongPackageName(Package) || AssetPath.Contains(TEXT(":")))
        return Fail(TEXT("invalid_arguments"), TEXT("Invalid asset package path."));
    if (!AssetPath.Contains(TEXT("."))) AssetPath += TEXT(".") + FPackageName::GetLongPackageAssetName(Package);
    const FAssetData Asset = Registry.GetAssetByObjectPath(FSoftObjectPath(AssetPath));
    if (!Asset.IsValid()) return Fail(TEXT("asset_not_found"), TEXT("Asset is not present in the current registry."));
    if (Properties)
    {
        if (!(Package.StartsWith(TEXT("/Game/")) || Package.StartsWith(TEXT("/JasperPrism/"))))
            return Fail(TEXT("unsupported_asset_path"), TEXT("Property inspection is limited to project content and /JasperPrism assets."));
        UObject* Loaded = Asset.GetAsset();
        if (!Loaded) return Fail(TEXT("asset_load_failed"), TEXT("The selected asset could not be loaded for read-only inspection."));
        Data->SetStringField(TEXT("asset_path"), Loaded->GetPathName());
        Data->SetStringField(TEXT("class_path"), Loaded->GetClass()->GetPathName());
        if (!DescribeProperties(Loaded, static_cast<int32>(Limit), Data, ErrorCode, ErrorMessage)) return false;
        return true;
    }
    Data->SetObjectField(TEXT("asset"), Describe(Asset));
    TArray<FName> Dependencies, Referencers;
    Registry.GetDependencies(Asset.PackageName, Dependencies, UE::AssetRegistry::EDependencyCategory::Package);
    Registry.GetReferencers(Asset.PackageName, Referencers, UE::AssetRegistry::EDependencyCategory::Package);
    auto AddNames = [&](const TCHAR* Field, TArray<FName>& Names)
    {
        Names.Sort([](const FName& A, const FName& B) { return A.ToString() < B.ToString(); });
        TArray<TSharedPtr<FJsonValue>> Values;
        for (int32 Index = 0; Index < FMath::Min(Names.Num(), static_cast<int32>(Limit)); ++Index)
            Values.Add(MakeShared<FJsonValueString>(Names[Index].ToString()));
        Data->SetArrayField(Field, Values);
        Data->SetNumberField(FString(Field) + TEXT("_total"), Names.Num());
        Data->SetBoolField(FString(Field) + TEXT("_truncated"), Names.Num() > Values.Num());
    };
    AddNames(TEXT("dependencies"), Dependencies);
    AddNames(TEXT("referencers"), Referencers);
    Data->SetStringField(TEXT("reference_scope"), TEXT("Registry package dependencies and referencers; not live object references."));
    return true;
}
