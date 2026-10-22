#if WITH_DEV_AUTOMATION_TESTS

#include "ForgeDirtyPackages.h"
#include "ForgeLandscape.h"
#include "Editor.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/AutomationTest.h"
#include "Misc/Guid.h"
#include "UObject/Package.h"
#include "UObject/ObjectMacros.h"

namespace
{
	ForgeDirtyPackages::FPackagePolicyFacts MakeVerifiedSlateCoreFacts()
	{
		ForgeDirtyPackages::FPackagePolicyFacts Facts;
		Facts.PackagePath = TEXT("/Script/SlateCore");
		Facts.PackageCategory = TEXT("engine_script");
		Facts.PackageFlags = static_cast<uint32>(PKG_CompiledIn);
		Facts.bDirty = true;
		Facts.bClassificationComplete = true;
		Facts.bOwnershipScanComplete = true;
		Facts.bEngineScriptProvenanceVerified = true;
		Facts.bAssociationWithCurrentWorldDetermined = true;
		return Facts;
	}

	bool PreviewCreateWithDirtyPackage(FAutomationTestBase& Test, UPackage* DirtyPackage,
		const FString& ExpectedCategory, const TCHAR* Label)
	{
		FForgeLandscape Landscape;
		TSharedRef<FJsonObject> Request = MakeShared<FJsonObject>();
		Request->SetStringField(TEXT("action"), TEXT("create"));
		Request->SetStringField(TEXT("map_path"), TEXT("/Game/ForgeMCPTests/Landscape/L_A7K38_Policy_") +
			FGuid::NewGuid().ToString(EGuidFormats::Digits));
		Request->SetBoolField(TEXT("world_partition"), true);
		Request->SetNumberField(TEXT("components_x"), 2);
		Request->SetNumberField(TEXT("components_y"), 2);
		Request->SetNumberField(TEXT("sections_per_component"), 1);
		Request->SetNumberField(TEXT("quads_per_section"), 63);
		Request->SetNumberField(TEXT("xy_scale_cm"), 100);
		Request->SetNumberField(TEXT("z_scale"), 100);
		Request->SetNumberField(TEXT("partition_grid_size_components"), 2);

		TSharedRef<FJsonObject> Args = MakeShared<FJsonObject>();
		Args->SetObjectField(TEXT("request"), Request);
		TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
		FString ErrorCode;
		FString ErrorMessage;
		const bool bHandled = Landscape.Handle(TEXT("landscape_preview"), Args, Data, ErrorCode, ErrorMessage);
		Test.TestTrue(FString::Printf(TEXT("%s native preview completed: %s %s"), Label, *ErrorCode, *ErrorMessage), bHandled);
		if (!bHandled) return false;

		bool bApplyAllowed = true;
		Test.TestTrue(FString::Printf(TEXT("%s preview reports apply_allowed"), Label),
			Data->TryGetBoolField(TEXT("apply_allowed"), bApplyAllowed));
		Test.TestFalse(FString::Printf(TEXT("%s dirty package is rejected before Apply"), Label), bApplyAllowed);
		FString PreviewId;
		Test.TestTrue(FString::Printf(TEXT("%s preview has a confirmation identity"), Label),
			Data->TryGetStringField(TEXT("preview_id"), PreviewId) && !PreviewId.IsEmpty());
		TSharedRef<FJsonObject> ApplyArgs = MakeShared<FJsonObject>();
		ApplyArgs->SetStringField(TEXT("preview_id"), PreviewId);
		ApplyArgs->SetStringField(TEXT("confirmation"), PreviewId);
		TSharedRef<FJsonObject> ApplyData = MakeShared<FJsonObject>();
		FString ApplyErrorCode;
		FString ApplyErrorMessage;
		const bool bApplySucceeded = Landscape.Handle(TEXT("landscape_apply"), ApplyArgs,
			ApplyData, ApplyErrorCode, ApplyErrorMessage);
		Test.TestFalse(FString::Printf(TEXT("%s native Apply is rejected before mutation"), Label), bApplySucceeded);
		Test.TestEqual(FString::Printf(TEXT("%s native Apply rejection reason"), Label),
			ApplyErrorCode, FString(TEXT("landscape_safety_gate_blocked")));

		const TSharedPtr<FJsonObject>* Policy = nullptr;
		Test.TestTrue(FString::Printf(TEXT("%s preview reports dirty package policy"), Label),
			Data->TryGetObjectField(TEXT("dirty_package_preflight"), Policy) && Policy && Policy->IsValid());
		if (!Policy || !Policy->IsValid()) return false;
		const TArray<TSharedPtr<FJsonValue>>* Rows = nullptr;
		Test.TestTrue(FString::Printf(TEXT("%s preview reports blocking package rows"), Label),
			(*Policy)->TryGetArrayField(TEXT("blocking_dirty_package_sample"), Rows) && Rows);
		if (!Rows) return false;

		bool bFound = false;
		for (const TSharedPtr<FJsonValue>& Value : *Rows)
		{
			const TSharedPtr<FJsonObject> Row = Value.IsValid() ? Value->AsObject() : nullptr;
			if (!Row.IsValid()) continue;
			FString PackagePath;
			FString PackageCategory;
			Row->TryGetStringField(TEXT("package_path"), PackagePath);
			Row->TryGetStringField(TEXT("package_category"), PackageCategory);
			if (PackagePath == DirtyPackage->GetPathName())
			{
				bFound = true;
				Test.TestEqual(FString::Printf(TEXT("%s package category"), Label), PackageCategory, ExpectedCategory);
				Test.TestEqual(FString::Printf(TEXT("%s policy result"), Label),
					Row->GetStringField(TEXT("landscape_apply_policy_result")), FString(TEXT("blocks_apply")));
			}
		}
		Test.TestTrue(FString::Printf(TEXT("%s dirty package is present in preflight rows"), Label), bFound);
		return bFound;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeDirtyPackagePolicyTest,
	"ForgeMCP.DirtyPackages.DisposableExceptionPolicy",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForgeDirtyPackagePolicyTest::RunTest(const FString& Parameters)
{
	using namespace ForgeDirtyPackages;

	const FPackagePolicyDecision SlateCoreDisposable = EvaluateLandscapeApplyPolicy(
		MakeVerifiedSlateCoreFacts(), true);
	TestFalse(TEXT("Verified SlateCore exception is nonblocking only in a marked disposable project"),
		SlateCoreDisposable.bBlocksApply);
	TestTrue(TEXT("The exception remains explicit in the decision"),
		SlateCoreDisposable.bDisposableEngineScriptException);
	TestTrue(TEXT("The exception is not permitted outside the disposable project"),
		EvaluateLandscapeApplyPolicy(MakeVerifiedSlateCoreFacts(), false).bBlocksApply);

	auto ExpectBlocked = [this](const TCHAR* Label, const FPackagePolicyFacts& Facts, bool bDisposable = true)
	{
		TestTrue(Label, EvaluateLandscapeApplyPolicy(Facts, bDisposable).bBlocksApply);
	};

	FPackagePolicyFacts Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackagePath = TEXT("/Script/Engine");
	ExpectBlocked(TEXT("A different engine script package is not exempt"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageCategory = TEXT("project_content");
	ExpectBlocked(TEXT("Dirty project content blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageCategory = TEXT("external_actor");
	Facts.ExternalActorCount = 1;
	ExpectBlocked(TEXT("Dirty external actor blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageCategory = TEXT("current_world");
	Facts.bCurrentWorldPackage = true;
	ExpectBlocked(TEXT("Dirty current-world package blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageCategory = TEXT("unknown");
	Facts.bClassificationComplete = false;
	ExpectBlocked(TEXT("Unknown package ownership blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.bClassificationComplete = false;
	ExpectBlocked(TEXT("Incomplete classification blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.bOwnershipScanComplete = false;
	ExpectBlocked(TEXT("Incomplete object ownership scan blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.bAssociationWithCurrentWorldDetermined = false;
	ExpectBlocked(TEXT("Unknown current-world association blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.bAssociatedWithCurrentWorld = true;
	ExpectBlocked(TEXT("A SlateCore row associated with the current world blocks"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.AssociatedActorCount = 1;
	ExpectBlocked(TEXT("Any associated actor blocks the exception"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.bIsTransientPackage = true;
	ExpectBlocked(TEXT("Transient package state blocks the exception"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageFlags |= static_cast<uint32>(PKG_NewlyCreated);
	ExpectBlocked(TEXT("Newly created package flags block the exception"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageFlags |= static_cast<uint32>(PKG_ContainsMap);
	ExpectBlocked(TEXT("Map package flags block the exception"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageFlags |= static_cast<uint32>(PKG_ContainsMapData);
	ExpectBlocked(TEXT("Map-data package flags block the exception"), Facts);

	Facts = MakeVerifiedSlateCoreFacts();
	Facts.PackageFlags = 0;
	ExpectBlocked(TEXT("Missing compiled-in package provenance blocks the exception"), Facts);

	TestTrue(TEXT("An incomplete package snapshot blocks Apply"),
		IsLandscapeApplyPreflightBlocking(false, 0));
	TestTrue(TEXT("A blocking dirty row blocks Apply"),
		IsLandscapeApplyPreflightBlocking(true, 1));
	TestFalse(TEXT("A complete snapshot with no blocking rows passes this gate"),
		IsLandscapeApplyPreflightBlocking(true, 0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FForgeDirtyPackageNativePreviewTest,
	"ForgeMCP.DirtyPackages.NativePreviewFailClosed",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FForgeDirtyPackageNativePreviewTest::RunTest(const FString& Parameters)
{
	if (!TestNotNull(TEXT("GEditor is available for disposable native preview tests"), GEditor)) return false;
	UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
	if (!TestNotNull(TEXT("The disposable Editor has a current world"), CurrentWorld)) return false;

	const FString UniqueSuffix = FGuid::NewGuid().ToString(EGuidFormats::Digits);
	const FString ProjectPackagePath = TEXT("/Game/ForgeMCPTests/Policy/L_A7K38_DirtyProjectMap_") + UniqueSuffix;
	UPackage* DirtyProjectPackage = CreatePackage(*ProjectPackagePath);
	if (!TestNotNull(TEXT("Synthetic dirty project map package was created in memory only"), DirtyProjectPackage)) return false;
	DirtyProjectPackage->SetPackageFlags(PKG_ContainsMap | PKG_ContainsMapData);
	DirtyProjectPackage->SetDirtyFlag(true);
	PreviewCreateWithDirtyPackage(*this, DirtyProjectPackage, TEXT("project_content"), TEXT("Dirty project map"));
	DirtyProjectPackage->SetDirtyFlag(false);

	const FString ExternalPackagePath = TEXT("/Game/__ExternalActors__/ForgeMCPTests/Policy/0/AA/L_A7K38_External_") + UniqueSuffix;
	UPackage* DirtyExternalPackage = CreatePackage(*ExternalPackagePath);
	if (!TestNotNull(TEXT("Synthetic external actor package was created in memory only"), DirtyExternalPackage)) return false;
	AActor* ExternalActor = NewObject<AActor>(CurrentWorld->PersistentLevel,
		MakeUniqueObjectName(CurrentWorld->PersistentLevel, AActor::StaticClass(), TEXT("A7K38ExternalPolicyActor")),
		RF_Transient);
	if (!TestNotNull(TEXT("Synthetic external actor was created in memory only"), ExternalActor)) return false;
	ExternalActor->SetPackageExternal(true, false, DirtyExternalPackage);
	DirtyExternalPackage->SetDirtyFlag(true);
	PreviewCreateWithDirtyPackage(*this, DirtyExternalPackage, TEXT("external_actor"), TEXT("Dirty external actor"));
	DirtyExternalPackage->SetDirtyFlag(false);

	const FString UnknownPackagePath = TEXT("/ForgeMCPUnknownMount/L_A7K38_Unknown_") + UniqueSuffix;
	UPackage* DirtyUnknownPackage = CreatePackage(*UnknownPackagePath);
	if (!TestNotNull(TEXT("Synthetic unknown package was created in memory only"), DirtyUnknownPackage)) return false;
	DirtyUnknownPackage->SetDirtyFlag(true);
	PreviewCreateWithDirtyPackage(*this, DirtyUnknownPackage, TEXT("unknown"), TEXT("Unknown package ownership"));
	DirtyUnknownPackage->SetDirtyFlag(false);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
