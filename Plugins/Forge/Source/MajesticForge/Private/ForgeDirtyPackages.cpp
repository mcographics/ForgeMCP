#include "ForgeDirtyPackages.h"

#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LandscapeProxy.h"
#include "Modules/ModuleManager.h"
#include "Materials/MaterialInterface.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "HAL/PlatformTime.h"
#include "Misc/Guid.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"
#include "UObject/UObjectHash.h"
#include "UObject/UObjectIterator.h"

namespace ForgeDirtyPackages
{
	namespace
	{
		constexpr int32 MaxPackagesToInspect = 50000;
		constexpr int32 MaxPageSize = 50;
		constexpr int32 MaxAssociatedObjectsPerPackage = 4;
		constexpr int32 MaxObjectsToClassifyPerPackage = 100000;
		constexpr int32 MaxNameCharacters = 1024;
		constexpr int64 MaxSnapshotJsonBytes = 8 * 1024 * 1024;
		constexpr double SnapshotLifetimeSeconds = 60.0;

		struct FInventorySnapshot
		{
			FString Id;
			double ExpiresAt = 0.0;
			int32 PackagesInspected = 0;
			bool bComplete = false;
			bool bSnapshotLimitReached = false;
			int64 SerializedBytes = 0;
			FString CurrentLevelPackage;
			FString TargetMapPath;
			TArray<TSharedPtr<FJsonObject>> DirtyPackageRows;
		};

		FInventorySnapshot CurrentSnapshot;

		bool ReadBoundedInteger(const TSharedRef<FJsonObject>& Args, const TCHAR* FieldName,
			int64 DefaultValue, int64 Minimum, int64 Maximum, int64& OutValue)
		{
			OutValue = DefaultValue;
			const TSharedPtr<FJsonValue>* Value = Args->Values.Find(FieldName);
			if (!Value)
			{
				return true;
			}

			double Number = 0.0;
			if (!Value->IsValid() || (*Value)->Type != EJson::Number || !(*Value)->TryGetNumber(Number) ||
				!FMath::IsFinite(Number) || FMath::FloorToDouble(Number) != Number ||
				Number < static_cast<double>(Minimum) || Number > static_cast<double>(Maximum))
			{
				return false;
			}

			OutValue = static_cast<int64>(Number);
			return true;
		}

		FString CanonicalAbsolutePath(FString Path)
		{
			Path = FPaths::ConvertRelativePathToFull(Path);
			FPaths::NormalizeFilename(Path);
			FPaths::CollapseRelativeDirectories(Path);
			while (Path.Len() > 3 && Path.EndsWith(TEXT("/"))) Path.LeftChopInline(1);
			return Path;
		}

		bool IsUnderDirectory(const FString& CandidatePath, const FString& DirectoryPath)
		{
			const FString Candidate = CanonicalAbsolutePath(CandidatePath);
			FString Directory = CanonicalAbsolutePath(DirectoryPath);
			if (!Directory.EndsWith(TEXT("/"))) Directory.AppendChar(TEXT('/'));
			return Candidate.StartsWith(Directory, ESearchCase::IgnoreCase);
		}

		bool TryGetPackageFilename(const FString& PackagePath, FString& OutFilename)
		{
			if (!FPackageName::TryConvertLongPackageNameToFilename(PackagePath, OutFilename))
			{
				return false;
			}
			OutFilename = CanonicalAbsolutePath(OutFilename);
			return true;
		}

		bool IsVerifiedEngineScriptPackage(UPackage* Package, const FString& PackagePath)
		{
			if (!Package || !FPackageName::IsScriptPackage(FStringView(PackagePath)) ||
				(Package->GetPackageFlags() & PKG_CompiledIn) == 0)
			{
				return false;
			}

			const FString ModuleName = PackagePath.Mid(8);
			if (ModuleName.IsEmpty()) return false;

#if !IS_MONOLITHIC
			const FName ModuleFName(*ModuleName);
			FModuleManager& ModuleManager = FModuleManager::Get();
			if (!ModuleManager.IsModuleLoaded(ModuleFName)) return false;
			const FString ModuleFilename = ModuleManager.GetModuleFilename(ModuleFName);
			return !ModuleFilename.IsEmpty() && IsUnderDirectory(ModuleFilename, FPaths::EngineDir());
#else
			// A monolithic executable does not provide a module-file provenance proof.
			return false;
#endif
		}

		bool IsTargetMapNamespaceMatch(const FString& PackagePath, const FString& TargetMapPath)
		{
			if (TargetMapPath.IsEmpty()) return false;
			const FString ExternalActorsPrefix = TEXT("/Game/__ExternalActors__/") + TargetMapPath.Mid(6) + TEXT("/");
			const FString ExternalObjectsPrefix = TEXT("/Game/__ExternalObjects__/") + TargetMapPath.Mid(6) + TEXT("/");
			return PackagePath.Equals(TargetMapPath, ESearchCase::IgnoreCase) ||
				PackagePath.StartsWith(ExternalActorsPrefix, ESearchCase::IgnoreCase) ||
				PackagePath.StartsWith(ExternalObjectsPrefix, ESearchCase::IgnoreCase);
		}

		struct FPackageEvidence : FPackagePolicyFacts
		{
			FString PackageDomain = TEXT("unknown");
			FString ClassificationBasis;
			FString FirstActorPath;
			FString ModuleName;
			int32 AssociatedObjectCount = 0;
			bool bScriptPackageCandidate = false;
			bool bProjectMembershipDetermined = false;
			bool bBelongsToProject = false;
			bool bExternalActorNamespaceCandidate = false;
			bool bObjectSampleTruncated = false;
			TArray<TSharedPtr<FJsonValue>> AssociatedObjects;
		};

		FPackageEvidence InspectPackage(UPackage* Package, UWorld* CurrentWorld)
		{
			FPackageEvidence Evidence;
			if (!Package) return Evidence;
			Evidence.PackagePath = Package->GetPathName();
			Evidence.bDirty = Package->IsDirty();
			Evidence.bIsTransientPackage = Package->HasAnyFlags(RF_Transient);
			Evidence.PackageFlags = static_cast<uint32>(Package->GetPackageFlags());
			Evidence.bCurrentWorldPackage = CurrentWorld && Package == CurrentWorld->GetPackage();
			Evidence.bExternalActorNamespaceCandidate = Evidence.PackagePath.Contains(
				TEXT("/__ExternalActors__/"), ESearchCase::IgnoreCase);

			FString PackageFilename;
			if (TryGetPackageFilename(Evidence.PackagePath, PackageFilename))
			{
				Evidence.bProjectMembershipDetermined = true;
				Evidence.bBelongsToProject = IsUnderDirectory(PackageFilename, FPaths::ProjectDir());
			}

			const bool bScriptPackage = FPackageName::IsScriptPackage(FStringView(Evidence.PackagePath));
			Evidence.bScriptPackageCandidate = bScriptPackage;
			if (bScriptPackage)
			{
				Evidence.bEngineScriptProvenanceVerified = IsVerifiedEngineScriptPackage(Package, Evidence.PackagePath);
				Evidence.PackageDomain = Evidence.bEngineScriptProvenanceVerified ? TEXT("engine_script") : TEXT("unknown");
				Evidence.ClassificationBasis = Evidence.bEngineScriptProvenanceVerified
					? TEXT("script_package_compiled_in_loaded_engine_module")
					: TEXT("script_package_provenance_unverified");
				Evidence.ModuleName = Evidence.PackagePath.Mid(8);
			}
			else if (TryGetPackageFilename(Evidence.PackagePath, PackageFilename) &&
				IsUnderDirectory(PackageFilename, FPaths::EngineContentDir()))
			{
				Evidence.PackageDomain = TEXT("engine_content");
				Evidence.ClassificationBasis = TEXT("resolved_package_file_under_engine_content_root");
			}
			else if (TryGetPackageFilename(Evidence.PackagePath, PackageFilename) &&
				IsUnderDirectory(PackageFilename, FPaths::ProjectDir()))
			{
				Evidence.PackageDomain = TEXT("project_content");
				Evidence.ClassificationBasis = TEXT("resolved_package_file_under_project_root");
			}
			else
			{
				Evidence.ClassificationBasis = TEXT("package_mount_or_file_location_unresolved");
			}

			TArray<TSharedPtr<FJsonValue>>& AssociatedObjects = Evidence.AssociatedObjects;
			AssociatedObjects.Reserve(MaxAssociatedObjectsPerPackage);
			bool bScanComplete = true;
			ForEachObjectWithPackage(Package, [&](UObject* Object)
			{
				if (!Object) return true;
				if (Evidence.AssociatedObjectCount >= MaxObjectsToClassifyPerPackage)
				{
					bScanComplete = false;
					return false;
				}
				++Evidence.AssociatedObjectCount;
				const FString ObjectPath = Object->GetPathName();
				if (AssociatedObjects.Num() < MaxAssociatedObjectsPerPackage)
				{
					TSharedRef<FJsonObject> ObjectInfo = MakeShared<FJsonObject>();
					ObjectInfo->SetStringField(TEXT("object_name"), Object->GetName().Left(MaxNameCharacters));
					ObjectInfo->SetStringField(TEXT("object_path"), ObjectPath.Left(MaxNameCharacters));
					ObjectInfo->SetStringField(TEXT("class_path"), Object->GetClass()->GetPathName().Left(MaxNameCharacters));
					ObjectInfo->SetBoolField(TEXT("is_actor"), Object->IsA<AActor>());
					if (Object->IsA<AActor>()) ObjectInfo->SetStringField(TEXT("actor_path"), ObjectPath.Left(MaxNameCharacters));
					AssociatedObjects.Add(MakeShared<FJsonValueObject>(ObjectInfo));
				}
				else
				{
					Evidence.bObjectSampleTruncated = true;
				}

				if (AActor* Actor = Cast<AActor>(Object))
				{
					++Evidence.AssociatedActorCount;
					if (Evidence.FirstActorPath.IsEmpty()) Evidence.FirstActorPath = ObjectPath;
					Evidence.bAssociatedWithCurrentWorld |= CurrentWorld && Actor->GetWorld() == CurrentWorld;
					if (Actor->GetPackage() == Package && Actor->IsPackageExternal())
					{
						++Evidence.ExternalActorCount;
					}
				}
				return true;
			}, false);
			Evidence.bOwnershipScanComplete = bScanComplete;
			Evidence.bAssociationWithCurrentWorldDetermined = bScanComplete;

			if (Evidence.bCurrentWorldPackage)
			{
				Evidence.PackageCategory = TEXT("current_world");
				Evidence.ClassificationBasis += TEXT("; current_editor_world_package");
			}
			else if (Evidence.ExternalActorCount > 0)
			{
				Evidence.PackageCategory = TEXT("external_actor");
				Evidence.ClassificationBasis += TEXT("; actor_reports_external_package_ownership");
			}
			else if (Evidence.bAssociatedWithCurrentWorld)
			{
				Evidence.PackageCategory = TEXT("current_world");
				Evidence.ClassificationBasis += TEXT("; actor_world_pointer_matches_current_editor_world");
			}
			else if (Evidence.bExternalActorNamespaceCandidate)
			{
				Evidence.PackageCategory = TEXT("unknown");
				Evidence.ClassificationBasis += TEXT("; external_actor_namespace_without_loaded_owner_proof");
			}
			else
			{
				Evidence.PackageCategory = Evidence.PackageDomain;
			}
			Evidence.bClassificationComplete = Evidence.PackageCategory != TEXT("unknown") && bScanComplete;
			return Evidence;
		}

		FPackagePolicyFacts ToPolicyFacts(const FPackageEvidence& Evidence)
		{
			FPackagePolicyFacts Facts;
			Facts.PackagePath = Evidence.PackagePath;
			Facts.PackageCategory = Evidence.PackageCategory;
			Facts.PackageFlags = Evidence.PackageFlags;
			Facts.AssociatedActorCount = Evidence.AssociatedActorCount;
			Facts.ExternalActorCount = Evidence.ExternalActorCount;
			Facts.bDirty = Evidence.bDirty;
			Facts.bClassificationComplete = Evidence.bClassificationComplete;
			Facts.bOwnershipScanComplete = Evidence.bOwnershipScanComplete;
			Facts.bEngineScriptProvenanceVerified = Evidence.bEngineScriptProvenanceVerified;
			Facts.bIsTransientPackage = Evidence.bIsTransientPackage;
			Facts.bCurrentWorldPackage = Evidence.bCurrentWorldPackage;
			Facts.bAssociatedWithCurrentWorld = Evidence.bAssociatedWithCurrentWorld;
			Facts.bAssociationWithCurrentWorldDetermined = Evidence.bAssociationWithCurrentWorldDetermined;
			return Facts;
		}

		TSharedRef<FJsonObject> DescribePackage(const FPackageEvidence& Evidence,
			const FString& PackageName, const FString& TargetMapPath)
		{
			const bool bTargetNamespaceMatch = IsTargetMapNamespaceMatch(Evidence.PackagePath, TargetMapPath);
			const bool bIsScriptPackage = Evidence.bScriptPackageCandidate;
			TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
			Result->SetStringField(TEXT("package_name"), PackageName.Left(MaxNameCharacters));
			Result->SetStringField(TEXT("package_path"), Evidence.PackagePath.Left(MaxNameCharacters));
			Result->SetBoolField(TEXT("is_dirty"), Evidence.bDirty);
			Result->SetBoolField(TEXT("is_transient_package"), Evidence.bIsTransientPackage);
			Result->SetNumberField(TEXT("package_flags"), Evidence.PackageFlags);
			Result->SetBoolField(TEXT("package_newly_created"), (Evidence.PackageFlags & static_cast<uint32>(PKG_NewlyCreated)) != 0);
			Result->SetBoolField(TEXT("package_contains_map"), (Evidence.PackageFlags & static_cast<uint32>(PKG_ContainsMap)) != 0);
			Result->SetBoolField(TEXT("package_contains_map_data"), (Evidence.PackageFlags & static_cast<uint32>(PKG_ContainsMapData)) != 0);
			Result->SetBoolField(TEXT("package_compiled_in"), (Evidence.PackageFlags & static_cast<uint32>(PKG_CompiledIn)) != 0);
			Result->SetStringField(TEXT("classification"), Evidence.PackageCategory);
			Result->SetStringField(TEXT("package_category"), Evidence.PackageCategory);
			Result->SetStringField(TEXT("package_domain"), Evidence.PackageDomain);
			Result->SetBoolField(TEXT("script_package_candidate"), Evidence.bScriptPackageCandidate);
			Result->SetStringField(TEXT("classification_basis"), Evidence.ClassificationBasis);
			Result->SetBoolField(TEXT("classification_complete"), Evidence.bClassificationComplete);
			Result->SetBoolField(TEXT("ownership_scan_complete"), Evidence.bOwnershipScanComplete);
			Result->SetNumberField(TEXT("associated_object_count_scanned"), Evidence.AssociatedObjectCount);
			Result->SetNumberField(TEXT("associated_actor_count"), Evidence.AssociatedActorCount);
			Result->SetNumberField(TEXT("external_actor_count"), Evidence.ExternalActorCount);
			Result->SetBoolField(TEXT("contains_external_actor"), Evidence.ExternalActorCount > 0);
			Result->SetBoolField(TEXT("engine_script_provenance_verified"), Evidence.bEngineScriptProvenanceVerified);
			Result->SetBoolField(TEXT("unresolved_engine_script_package"), bIsScriptPackage &&
				(!Evidence.bEngineScriptProvenanceVerified || !Evidence.bClassificationComplete));
			Result->SetBoolField(TEXT("unresolved_project_content_package"), Evidence.PackageDomain == TEXT("project_content") &&
				!Evidence.bClassificationComplete);
			Result->SetStringField(TEXT("target_map_path"), TargetMapPath);
			Result->SetBoolField(TEXT("target_map_path_namespace_match"), bTargetNamespaceMatch);
			Result->SetStringField(TEXT("target_map_association_basis"), bTargetNamespaceMatch ?
				TEXT("package_path_namespace_match_only") : TEXT("not_determined_from_package_path"));
			Result->SetBoolField(TEXT("project_membership_determined"), Evidence.bProjectMembershipDetermined);
			if (Evidence.bProjectMembershipDetermined)
			{
				Result->SetBoolField(TEXT("belongs_to_test_project"), Evidence.bBelongsToProject);
			}
			else
			{
				Result->SetField(TEXT("belongs_to_test_project"), MakeShared<FJsonValueNull>());
			}
			Result->SetBoolField(TEXT("is_current_level_package"), Evidence.bCurrentWorldPackage);
			Result->SetBoolField(TEXT("associated_with_current_level_determined"), Evidence.bAssociationWithCurrentWorldDetermined);
			if (Evidence.bAssociationWithCurrentWorldDetermined)
			{
				Result->SetBoolField(TEXT("associated_with_current_level"), Evidence.bAssociatedWithCurrentWorld);
			}
			else
			{
				Result->SetField(TEXT("associated_with_current_level"), MakeShared<FJsonValueNull>());
			}
			const bool bSingleActorPathDetermined = Evidence.bOwnershipScanComplete && Evidence.AssociatedActorCount == 1;
			Result->SetBoolField(TEXT("associated_actor_determined"), bSingleActorPathDetermined);
			if (bSingleActorPathDetermined && !Evidence.FirstActorPath.IsEmpty())
				Result->SetStringField(TEXT("associated_actor_path"), Evidence.FirstActorPath.Left(MaxNameCharacters));
			else Result->SetField(TEXT("associated_actor_path"), MakeShared<FJsonValueNull>());
			Result->SetArrayField(TEXT("associated_objects"), Evidence.AssociatedObjects);
			Result->SetBoolField(TEXT("associated_objects_truncated"), Evidence.bObjectSampleTruncated);
			Result->SetBoolField(TEXT("associated_objects_sample_truncated"), Evidence.bObjectSampleTruncated);
			Result->SetBoolField(TEXT("external_actor_namespace_candidate"), Evidence.bExternalActorNamespaceCandidate);
			return Result;
		}

		bool BuildInventorySnapshot(UWorld* CurrentWorld, const FString& TargetMapPath,
			FString& OutErrorCode, FString& OutErrorMessage)
		{
			CurrentSnapshot = FInventorySnapshot();
			CurrentSnapshot.CurrentLevelPackage = CurrentWorld->GetPackage()->GetPathName();
			CurrentSnapshot.TargetMapPath = TargetMapPath;
			CurrentSnapshot.DirtyPackageRows.Reserve(128);
			CurrentSnapshot.bComplete = true;
			TArray<UPackage*> DirtyPackages;
			DirtyPackages.Reserve(128);

			for (TObjectIterator<UPackage> It; It; ++It)
			{
				if (CurrentSnapshot.PackagesInspected >= MaxPackagesToInspect)
				{
					CurrentSnapshot.bComplete = false;
					break;
				}

				UPackage* Package = *It;
				++CurrentSnapshot.PackagesInspected;
				if (!Package || !Package->IsDirty())
				{
					continue;
				}
				DirtyPackages.Add(Package);
			}

			DirtyPackages.Sort([](const UPackage& A, const UPackage& B)
			{
				return A.GetPathName().Compare(B.GetPathName(), ESearchCase::CaseSensitive) < 0;
			});

			for (UPackage* Package : DirtyPackages)
			{
				const FPackageEvidence Evidence = InspectPackage(Package, CurrentWorld);
				TSharedRef<FJsonObject> PackageRow = DescribePackage(Evidence, Package->GetName(), TargetMapPath);
				FString SerializedRow;
				TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer =
					TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&SerializedRow);
				if (!FJsonSerializer::Serialize(PackageRow, Writer))
				{
					OutErrorCode = TEXT("snapshot_serialization_failed");
					OutErrorMessage = TEXT("A dirty package row could not be retained for stable pagination.");
					CurrentSnapshot = FInventorySnapshot();
					return false;
				}

				const int64 RowBytes = static_cast<int64>(SerializedRow.Len()) * sizeof(TCHAR);
				if (CurrentSnapshot.SerializedBytes + RowBytes > MaxSnapshotJsonBytes)
				{
					CurrentSnapshot.bComplete = false;
					CurrentSnapshot.bSnapshotLimitReached = true;
					break;
				}
				CurrentSnapshot.SerializedBytes += RowBytes;
				CurrentSnapshot.DirtyPackageRows.Add(PackageRow);
			}

			CurrentSnapshot.Id = FGuid::NewGuid().ToString(EGuidFormats::Digits);
			CurrentSnapshot.ExpiresAt = FPlatformTime::Seconds() + SnapshotLifetimeSeconds;
			return true;
		}
	}

	FPackagePolicyDecision EvaluateLandscapeApplyPolicy(const FPackagePolicyFacts& Facts,
		bool bDisposableProject)
	{
		FPackagePolicyDecision Decision;
		if (!Facts.bDirty)
		{
			Decision.bBlocksApply = false;
			Decision.Reason = TEXT("package_not_dirty");
			return Decision;
		}
		if (!bDisposableProject)
		{
			Decision.Reason = TEXT("dirty_package_requires_disposable_project");
			return Decision;
		}
		if (!Facts.bClassificationComplete || !Facts.bOwnershipScanComplete ||
			!Facts.bAssociationWithCurrentWorldDetermined)
		{
			Decision.Reason = TEXT("dirty_package_classification_or_ownership_is_incomplete");
			return Decision;
		}

		const uint32 NewlyCreatedFlag = static_cast<uint32>(PKG_NewlyCreated);
		const uint32 ContainsMapFlag = static_cast<uint32>(PKG_ContainsMap);
		const uint32 ContainsMapDataFlag = static_cast<uint32>(PKG_ContainsMapData);
		const uint32 CompiledInFlag = static_cast<uint32>(PKG_CompiledIn);
		const bool bHasUnsafePackageFlags =
			(Facts.PackageFlags & (NewlyCreatedFlag | ContainsMapFlag | ContainsMapDataFlag)) != 0;
		if (Facts.PackagePath != TEXT("/Script/SlateCore") ||
			Facts.PackageCategory != TEXT("engine_script") ||
			!Facts.bEngineScriptProvenanceVerified ||
			Facts.bIsTransientPackage || Facts.bCurrentWorldPackage || Facts.bAssociatedWithCurrentWorld ||
			Facts.AssociatedActorCount != 0 || Facts.ExternalActorCount != 0 ||
			(Facts.PackageFlags & CompiledInFlag) == 0 || bHasUnsafePackageFlags)
		{
			Decision.Reason = TEXT("dirty_package_is_not_the_exact_verified_disposable_engine_script_exception");
			return Decision;
		}

		Decision.bBlocksApply = false;
		Decision.bDisposableEngineScriptException = true;
		Decision.Reason = TEXT("explicit_disposable_only_verified_engine_script_exception");
		return Decision;
	}

	bool IsLandscapeApplyPreflightBlocking(bool bInventoryComplete, int32 BlockingDirtyPackageCount)
	{
		return !bInventoryComplete || BlockingDirtyPackageCount > 0;
	}

	bool InspectLandscapeApplyPreflight(UWorld* CurrentWorld, bool bDisposableProject,
		const TSharedRef<FJsonObject>& OutPolicy)
	{
		constexpr int32 MaxRowsPerResult = 32;
		int32 Inspected = 0;
		int32 DirtyCount = 0;
		int32 BlockingCount = 0;
		int32 ExceptionCount = 0;
		int32 UnresolvedCount = 0;
		bool bInventoryComplete = CurrentWorld != nullptr;
		bool bRowsTruncated = false;
		TArray<TSharedPtr<FJsonValue>> BlockingRows;
		TArray<TSharedPtr<FJsonValue>> ExceptionRows;
		if (!IsInGameThread())
		{
			OutPolicy->SetBoolField(TEXT("inventory_complete"), false);
			OutPolicy->SetBoolField(TEXT("policy_evidence_complete"), false);
			OutPolicy->SetStringField(TEXT("preflight_error"), TEXT("wrong_thread"));
			return false;
		}

		if (CurrentWorld)
		{
			for (TObjectIterator<UPackage> It; It; ++It)
			{
				if (Inspected >= MaxPackagesToInspect)
				{
					bInventoryComplete = false;
					break;
				}
				++Inspected;
				UPackage* Package = *It;
				if (!Package || !Package->IsDirty()) continue;

				++DirtyCount;
				const FPackageEvidence Evidence = InspectPackage(Package, CurrentWorld);
				const FPackagePolicyDecision Decision = EvaluateLandscapeApplyPolicy(
					ToPolicyFacts(Evidence), bDisposableProject);
				if (!Evidence.bClassificationComplete || !Evidence.bOwnershipScanComplete ||
					!Evidence.bAssociationWithCurrentWorldDetermined)
				{
					++UnresolvedCount;
				}

				TSharedRef<FJsonObject> Row = DescribePackage(Evidence, Package->GetName(), FString());
				Row->SetStringField(TEXT("landscape_apply_policy_result"),
					Decision.bDisposableEngineScriptException ? TEXT("explicit_disposable_exception") :
					(Decision.bBlocksApply ? TEXT("blocks_apply") : TEXT("not_blocking")));
				Row->SetStringField(TEXT("landscape_apply_policy_reason"), Decision.Reason);
				if (Decision.bDisposableEngineScriptException)
				{
					++ExceptionCount;
					if (ExceptionRows.Num() < MaxRowsPerResult)
						ExceptionRows.Add(MakeShared<FJsonValueObject>(Row));
					else
						bRowsTruncated = true;
				}
				else if (Decision.bBlocksApply)
				{
					++BlockingCount;
					if (BlockingRows.Num() < MaxRowsPerResult)
						BlockingRows.Add(MakeShared<FJsonValueObject>(Row));
					else
						bRowsTruncated = true;
				}
			}
		}

		OutPolicy->SetNumberField(TEXT("loaded_packages_inspected"), Inspected);
		OutPolicy->SetNumberField(TEXT("dirty_loaded_packages_observed"), DirtyCount);
		OutPolicy->SetBoolField(TEXT("inventory_complete"), bInventoryComplete);
		OutPolicy->SetBoolField(TEXT("policy_evidence_complete"), UnresolvedCount == 0);
		OutPolicy->SetNumberField(TEXT("unresolved_dirty_package_classifications"), UnresolvedCount);
		OutPolicy->SetNumberField(TEXT("blocking_dirty_loaded_packages"), BlockingCount);
		OutPolicy->SetNumberField(TEXT("disposable_engine_script_exceptions_applied"), ExceptionCount);
		OutPolicy->SetBoolField(TEXT("dirty_package_rows_truncated"), bRowsTruncated);
		OutPolicy->SetBoolField(TEXT("all_dirty_packages_block_apply"), BlockingCount > 0 || !bInventoryComplete);
		OutPolicy->SetStringField(TEXT("policy_exception_scope"),
			TEXT("Only /Script/SlateCore with compiled-in engine-module provenance, complete ownership scan, no actor/world association, safe package flags, and a verified marked disposable project."));
		OutPolicy->SetArrayField(TEXT("blocking_dirty_package_sample"), BlockingRows);
		OutPolicy->SetArrayField(TEXT("disposable_engine_script_exception_rows"), ExceptionRows);
		return bInventoryComplete;
	}

	bool Handle(const TSharedRef<FJsonObject>& Args, const TSharedRef<FJsonObject>& OutData,
		FString& OutErrorCode, FString& OutErrorMessage)
	{
		if (!IsInGameThread())
		{
			OutErrorCode = TEXT("wrong_thread");
			OutErrorMessage = TEXT("Dirty package inspection must run on the Editor game thread.");
			return false;
		}
		if (!GEditor)
		{
			OutErrorCode = TEXT("editor_unavailable");
			OutErrorMessage = TEXT("Editor context is unavailable.");
			return false;
		}
		if (GEditor->PlayWorld)
		{
			OutErrorCode = TEXT("pie_active");
			OutErrorMessage = TEXT("Dirty package inspection is unavailable while PIE is active.");
			return false;
		}

		for (const TPair<FString, TSharedPtr<FJsonValue>>& Field : Args->Values)
		{
			if (Field.Key != TEXT("limit") && Field.Key != TEXT("offset") && Field.Key != TEXT("snapshot_id") &&
				Field.Key != TEXT("target_map_path"))
			{
				OutErrorCode = TEXT("invalid_arguments");
				OutErrorMessage = TEXT("Only limit, offset, snapshot_id, and target_map_path are accepted.");
				return false;
			}
		}

		int64 Limit = MaxPageSize;
		int64 Offset = 0;
		if (!ReadBoundedInteger(Args, TEXT("limit"), MaxPageSize, 1, MaxPageSize, Limit) ||
			!ReadBoundedInteger(Args, TEXT("offset"), 0, 0, MaxPackagesToInspect, Offset))
		{
			OutErrorCode = TEXT("invalid_arguments");
			OutErrorMessage = TEXT("limit must be 1..50 and offset must be 0..50000; both must be integers.");
			return false;
		}

		FString RequestedSnapshotId;
		FString RequestedTargetMapPath;
		const bool bTargetMapFieldPresent = Args->Values.Contains(TEXT("target_map_path"));
		const bool bHasTargetMapPath = Args->TryGetStringField(TEXT("target_map_path"), RequestedTargetMapPath);
		if (bTargetMapFieldPresent && !bHasTargetMapPath)
		{
			OutErrorCode = TEXT("invalid_target_map_path");
			OutErrorMessage = TEXT("target_map_path must be a string.");
			return false;
		}
		if (bHasTargetMapPath && !RequestedTargetMapPath.IsEmpty() &&
			(!RequestedTargetMapPath.StartsWith(TEXT("/Game/ForgeMCPTests/Landscape/"), ESearchCase::CaseSensitive) ||
			 RequestedTargetMapPath.Contains(TEXT("..")) || RequestedTargetMapPath.Contains(TEXT("\\"))))
		{
			OutErrorCode = TEXT("invalid_target_map_path");
			OutErrorMessage = TEXT("target_map_path must be a disposable /Game/ForgeMCPTests/Landscape package path.");
			return false;
		}
		const TSharedPtr<FJsonValue>* SnapshotValue = Args->Values.Find(TEXT("snapshot_id"));
		if (SnapshotValue)
		{
			if (!SnapshotValue->IsValid() || !(*SnapshotValue)->TryGetString(RequestedSnapshotId) ||
				RequestedSnapshotId.Len() != 32)
			{
				OutErrorCode = TEXT("invalid_arguments");
				OutErrorMessage = TEXT("snapshot_id must be a 32-character inventory ID returned by the first page.");
				return false;
			}
		}
		else if (Offset != 0)
		{
			OutErrorCode = TEXT("snapshot_id_required");
			OutErrorMessage = TEXT("Pages after the first require the snapshot_id returned by the first page.");
			return false;
		}

		UWorld* CurrentWorld = GEditor->GetEditorWorldContext().World();
		if (!CurrentWorld || !CurrentWorld->GetPackage())
		{
			OutErrorCode = TEXT("world_unavailable");
			OutErrorMessage = TEXT("No editor world package is available for current-level association.");
			return false;
		}

		if (RequestedSnapshotId.IsEmpty())
		{
			if (!BuildInventorySnapshot(CurrentWorld, RequestedTargetMapPath, OutErrorCode, OutErrorMessage))
			{
				return false;
			}
		}
		else if (CurrentSnapshot.Id.IsEmpty() || RequestedSnapshotId != CurrentSnapshot.Id ||
			FPlatformTime::Seconds() > CurrentSnapshot.ExpiresAt)
		{
			CurrentSnapshot = FInventorySnapshot();
			OutErrorCode = TEXT("snapshot_expired");
			OutErrorMessage = TEXT("The dirty package inventory snapshot is absent, expired, or superseded; request a new first page.");
			return false;
		}
		else if (bHasTargetMapPath && RequestedTargetMapPath != CurrentSnapshot.TargetMapPath)
		{
			OutErrorCode = TEXT("snapshot_context_mismatch");
			OutErrorMessage = TEXT("target_map_path differs from the context captured by this inventory snapshot.");
			return false;
		}

		const int32 BeginIndex = FMath::Min(static_cast<int32>(Offset), CurrentSnapshot.DirtyPackageRows.Num());
		const int32 EndIndex = FMath::Min(BeginIndex + static_cast<int32>(Limit), CurrentSnapshot.DirtyPackageRows.Num());
		TArray<TSharedPtr<FJsonValue>> PackageResults;
		PackageResults.Reserve(EndIndex - BeginIndex);
		for (int32 Index = BeginIndex; Index < EndIndex; ++Index)
		{
			PackageResults.Add(MakeShared<FJsonValueObject>(CurrentSnapshot.DirtyPackageRows[Index].ToSharedRef()));
		}

		TArray<TSharedPtr<FJsonValue>> InspectionErrors;
		OutData->SetStringField(TEXT("inventory_scope"), TEXT("Loaded UPackage objects in the current Editor process only."));
		OutData->SetStringField(TEXT("inventory_id"), CurrentSnapshot.Id);
		OutData->SetNumberField(TEXT("snapshot_lifetime_seconds"), SnapshotLifetimeSeconds);
		OutData->SetStringField(TEXT("current_level_package"), CurrentSnapshot.CurrentLevelPackage.Left(MaxNameCharacters));
		OutData->SetStringField(TEXT("proposed_target_map_path"), CurrentSnapshot.TargetMapPath);
		OutData->SetNumberField(TEXT("packages_inspected"), CurrentSnapshot.PackagesInspected);
		OutData->SetBoolField(TEXT("inventory_complete"), CurrentSnapshot.bComplete);
		OutData->SetBoolField(TEXT("snapshot_limit_reached"), CurrentSnapshot.bSnapshotLimitReached);
		OutData->SetNumberField(TEXT("dirty_loaded_packages_observed"), CurrentSnapshot.DirtyPackageRows.Num());
		if (CurrentSnapshot.bComplete)
		{
			OutData->SetNumberField(TEXT("total_dirty_loaded_packages"), CurrentSnapshot.DirtyPackageRows.Num());
		}
		else
		{
			OutData->SetField(TEXT("total_dirty_loaded_packages"), MakeShared<FJsonValueNull>());
		}
		OutData->SetNumberField(TEXT("offset"), Offset);
		OutData->SetNumberField(TEXT("limit"), Limit);
		OutData->SetNumberField(TEXT("returned_count"), PackageResults.Num());
		OutData->SetBoolField(TEXT("has_more_observed_results"), EndIndex < CurrentSnapshot.DirtyPackageRows.Num());
		if (EndIndex < CurrentSnapshot.DirtyPackageRows.Num())
		{
			OutData->SetNumberField(TEXT("next_offset"), EndIndex);
		}
		else
		{
			OutData->SetField(TEXT("next_offset"), MakeShared<FJsonValueNull>());
		}
		OutData->SetArrayField(TEXT("packages"), PackageResults);
		OutData->SetArrayField(TEXT("inspection_errors"), InspectionErrors);
		OutData->SetStringField(TEXT("unloaded_package_note"),
			TEXT("Packages absent from the loaded UObject inventory were not inspected and are not classified as clean."));
		OutData->SetStringField(TEXT("page_consistency_note"),
			TEXT("All pages with this inventory_id use copied records from one game-thread scan; request remaining pages within snapshot_lifetime_seconds."));
		OutData->SetBoolField(TEXT("read_only"), true);
		return true;
	}
}
