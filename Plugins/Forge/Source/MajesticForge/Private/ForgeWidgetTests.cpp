#if WITH_DEV_AUTOMATION_TESTS
#include "ForgeWidgets.h"
#include "Misc/AutomationTest.h"
#include "WidgetBlueprint.h"
#include "Blueprint/WidgetTree.h"
#include "Components/CanvasPanel.h"
#include "Components/TextBlock.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeWidgetHideRecoveryTest, "ForgeMCP.Widgets.HideAndRecovery",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeWidgetHideRecoveryTest::RunTest(const FString& Parameters)
{
    UWidgetBlueprint* Blueprint = NewObject<UWidgetBlueprint>(GetTransientPackage());
    Blueprint->WidgetTree = NewObject<UWidgetTree>(Blueprint);
    UCanvasPanel* Root = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
    Blueprint->WidgetTree->RootWidget = Root;
    UTextBlock* Primary = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("PrimaryDistance"));
    UTextBlock* Extra = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("ExtraDistance"));
    Root->AddChild(Primary); Root->AddChild(Extra);
    Primary->SetVisibility(ESlateVisibility::Visible); Extra->SetVisibility(ESlateVisibility::Visible);
    Primary->SetText(FText::FromString(TEXT("123.45 km")));
    Extra->SetText(FText::FromString(TEXT("987.65 km")));
    for (const FString Name : {FString(TEXT("PrimaryDistance")), FString(TEXT("ExtraDistance"))})
    {
        FDelegateEditorBinding Binding;
        Binding.ObjectName = Name; Binding.PropertyName = TEXT("Visibility");
        Binding.FunctionName = TEXT("GetDistanceVisibility"); Blueprint->Bindings.Add(Binding);
    }
    auto Before = MakeShared<FJsonObject>(); FString Error;
    TestTrue(TEXT("Snapshot succeeds"), ForgeWidgets::Snapshot(Blueprint, Before));
    TestFalse(TEXT("Unknown widget rejected"), ForgeWidgets::ValidateHide(Blueprint, TEXT("Missing"), Error));
    TestFalse(TEXT("Non-text widget rejected"), ForgeWidgets::ValidateHide(Blueprint, TEXT("Root"), Error));
    TestTrue(TEXT("Exact text accepted"), ForgeWidgets::ValidateHide(Blueprint, TEXT("ExtraDistance"), Error));
    TestTrue(TEXT("Hide succeeds"), ForgeWidgets::HideText(Blueprint, TEXT("ExtraDistance")));
    TestTrue(TEXT("Extra text collapsed"), Extra->GetVisibility() == ESlateVisibility::Collapsed);
    TestTrue(TEXT("Primary text preserved"), Primary->GetVisibility() == ESlateVisibility::Visible);
    TestEqual(TEXT("Only selected visibility binding removed"), Blueprint->Bindings.Num(), 1);
    TestEqual(TEXT("Primary binding preserved"), Blueprint->Bindings[0].ObjectName, FString(TEXT("PrimaryDistance")));
    TestTrue(TEXT("Recovery succeeds"), ForgeWidgets::Restore(Blueprint, Before));
    TestTrue(TEXT("Visibility restored"), Extra->GetVisibility() == ESlateVisibility::Visible);
    TestEqual(TEXT("Both bindings restored"), Blueprint->Bindings.Num(), 2);
    TestEqual(TEXT("Text unchanged"), Extra->GetText().ToString(), FString(TEXT("987.65 km")));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeWidgetBoundTest, "ForgeMCP.Widgets.Bounds",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FForgeWidgetBoundTest::RunTest(const FString& Parameters)
{
    UWidgetBlueprint* Blueprint = NewObject<UWidgetBlueprint>(GetTransientPackage());
    Blueprint->WidgetTree = NewObject<UWidgetTree>(Blueprint);
    UCanvasPanel* Root = Blueprint->WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("Root"));
    Blueprint->WidgetTree->RootWidget = Root;
    for (int32 Index = 0; Index < 257; ++Index)
    {
        UTextBlock* Text = Blueprint->WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(),
            FName(*FString::Printf(TEXT("Distance%d"), Index)));
        Root->AddChild(Text);
    }
    auto State = MakeShared<FJsonObject>();
    TestFalse(TEXT("Oversized mutation snapshot rejected"), ForgeWidgets::Snapshot(Blueprint, State));
    TestTrue(TEXT("Read-only truncation reported"), ForgeWidgets::Inspect(Blueprint)->GetBoolField(TEXT("truncated")));
    return true;
}
#endif
