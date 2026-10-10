#include "ForgeAssets.h"
#include "AssetRegistry/AssetRegistryModule.h"
#include "AssetRegistry/IAssetRegistry.h"
#include "AssetRegistry/ARFilter.h"
#include "AssetRegistry/AssetData.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"

namespace
{
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
}

bool FForgeAssets::Handle(const FString& Command, const TSharedRef<FJsonObject>& Args,
    TSharedRef<FJsonObject> Data, FString& ErrorCode, FString& ErrorMessage)
{
    auto Fail = [&](const TCHAR* Code, const TCHAR* Message)
    { ErrorCode = Code; ErrorMessage = Message; return false; };
    if (!IsInGameThread()) return Fail(TEXT("invalid_context"), TEXT("Asset inspection requires the game thread."));
    const bool Search = Command == TEXT("asset_search");
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
