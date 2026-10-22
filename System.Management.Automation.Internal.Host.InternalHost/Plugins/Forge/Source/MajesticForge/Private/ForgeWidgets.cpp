#include "ForgeWidgets.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/PanelWidget.h"
#include "Components/TextBlock.h"
#include "Misc/FeedbackContext.h"

namespace
{
constexpr int32 MaxWidgets = 256;
constexpr int32 MaxBindings = 512;
UTextBlock* FindText(UWidgetBlueprint* Blueprint, const FString& Name)
{
    return Blueprint && Blueprint->WidgetTree
        ? Cast<UTextBlock>(Blueprint->WidgetTree->FindWidget(FName(*Name))) : nullptr;
}
}
namespace ForgeWidgets
{
TSharedRef<FJsonObject> Inspect(UBlueprint* Blueprint)
{
    auto Data = MakeShared<FJsonObject>();
    UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint);
    Data->SetBoolField(TEXT("is_widget_blueprint"), WidgetBP != nullptr);
    if (!WidgetBP) return Data;
    TArray<UWidget*> Widgets;
    if (WidgetBP->WidgetTree) WidgetBP->WidgetTree->GetAllWidgets(Widgets);
    TArray<TSharedPtr<FJsonValue>> Entries, Bindings;
    for (UWidget* Widget : Widgets)
    {
        if (!Widget || Entries.Num() >= MaxWidgets) break;
        auto Entry = MakeShared<FJsonObject>();
        Entry->SetStringField(TEXT("name"), Widget->GetName());
        Entry->SetStringField(TEXT("class_path"), Widget->GetClass()->GetPathName());
        Entry->SetStringField(TEXT("parent"), Widget->GetParent() ? Widget->GetParent()->GetName() : TEXT(""));
        Entry->SetStringField(TEXT("visibility"), StaticEnum<ESlateVisibility>()->GetNameStringByValue(static_cast<int64>(Widget->GetVisibility())));
        if (UTextBlock* Text = Cast<UTextBlock>(Widget))
        {
            Entry->SetStringField(TEXT("text"), Text->GetText().ToString().Left(512));
            Entry->SetBoolField(TEXT("auto_wrap"), Text->GetAutoWrapText());
            Entry->SetNumberField(TEXT("font_size"), Text->GetFont().Size);
        }
        Entries.Add(MakeShared<FJsonValueObject>(Entry));
    }
    for (const FDelegateEditorBinding& Binding : WidgetBP->Bindings)
    {
        if (Bindings.Num() >= MaxBindings) break;
        auto Entry = MakeShared<FJsonObject>();
        Entry->SetStringField(TEXT("widget"), Binding.ObjectName);
        Entry->SetStringField(TEXT("property"), Binding.PropertyName.ToString());
        Entry->SetStringField(TEXT("function"), Binding.FunctionName.ToString());
        Entry->SetStringField(TEXT("source_property"), Binding.SourceProperty.ToString());
        Bindings.Add(MakeShared<FJsonValueObject>(Entry));
    }
    Data->SetArrayField(TEXT("widgets"), Entries);
    Data->SetArrayField(TEXT("bindings"), Bindings);
    Data->SetNumberField(TEXT("widget_count"), Widgets.Num());
    Data->SetBoolField(TEXT("truncated"), Widgets.Num() > MaxWidgets || WidgetBP->Bindings.Num() > MaxBindings);
    Data->SetStringField(TEXT("scope"), TEXT("Designer template tree and editor bindings; not live viewport instances or inherited trees."));
    return Data;
}
bool Snapshot(UBlueprint* Blueprint, TSharedRef<FJsonObject> State)
{
    UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint);
    if (!WidgetBP) return true;
    TArray<UWidget*> Widgets;
    if (WidgetBP->WidgetTree) WidgetBP->WidgetTree->GetAllWidgets(Widgets);
    if (Widgets.Num() > MaxWidgets || WidgetBP->Bindings.Num() > MaxBindings) return false;
    State->SetObjectField(TEXT("widget_tree"), Inspect(Blueprint));
    TArray<TSharedPtr<FJsonValue>> Exported;
    for (const FDelegateEditorBinding& Binding : WidgetBP->Bindings)
    {
        FString Value;
        FDelegateEditorBinding::StaticStruct()->ExportText(Value, &Binding, nullptr, nullptr, PPF_None, nullptr);
        if (Value.Len() > 16384) return false;
        Exported.Add(MakeShared<FJsonValueString>(Value));
    }
    State->SetArrayField(TEXT("widget_binding_recovery"), Exported);
    return true;
}
bool Restore(UBlueprint* Blueprint, TSharedRef<FJsonObject> State)
{
    UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint);
    if (!WidgetBP) return !State->HasField(TEXT("widget_tree"));
    const TSharedPtr<FJsonObject>* Tree;
    const TArray<TSharedPtr<FJsonValue>>* Exports;
    if (!State->TryGetObjectField(TEXT("widget_tree"), Tree) ||
        !State->TryGetArrayField(TEXT("widget_binding_recovery"), Exports)) return false;
    TArray<FDelegateEditorBinding> Restored;
    for (const auto& Value : *Exports)
    {
        FDelegateEditorBinding Binding;
        if (!FDelegateEditorBinding::StaticStruct()->ImportText(*Value->AsString(), &Binding, nullptr, PPF_None, GWarn, TEXT("ForgeWidgetRecovery"))) return false;
        Restored.Add(Binding);
    }
    for (const auto& Value : (*Tree)->GetArrayField(TEXT("widgets")))
    {
        const auto Entry = Value->AsObject();
        UWidget* Widget = WidgetBP->WidgetTree ? WidgetBP->WidgetTree->FindWidget(FName(*Entry->GetStringField(TEXT("name")))) : nullptr;
        const int64 Visibility = StaticEnum<ESlateVisibility>()->GetValueByNameString(Entry->GetStringField(TEXT("visibility")));
        if (!Widget || Visibility == INDEX_NONE) return false;
        Widget->SetVisibility(static_cast<ESlateVisibility>(Visibility));
    }
    WidgetBP->Bindings = MoveTemp(Restored);
    return true;
}
bool ValidateHide(UBlueprint* Blueprint, const FString& Name, FString& Error)
{
    if (!FindText(Cast<UWidgetBlueprint>(Blueprint), Name))
    {
        Error = TEXT("hide_text requires an exact inspected TextBlock in this Widget Blueprint's template tree.");
        return false;
    }
    return true;
}
bool HideText(UBlueprint* Blueprint, const FString& Name)
{
    UWidgetBlueprint* WidgetBP = Cast<UWidgetBlueprint>(Blueprint);
    UTextBlock* Text = FindText(WidgetBP, Name);
    if (!Text) return false;
    WidgetBP->Modify(); WidgetBP->WidgetTree->Modify(); Text->Modify();
    // A visibility binding would override the template setting at runtime.
    // Remove only this explicitly selected text element's visibility binding.
    WidgetBP->Bindings.RemoveAll([&Name](const FDelegateEditorBinding& Binding)
    { return Binding.ObjectName == Name && Binding.PropertyName == FName(TEXT("Visibility")); });
    Text->SetVisibility(ESlateVisibility::Collapsed);
    return true;
}
}
