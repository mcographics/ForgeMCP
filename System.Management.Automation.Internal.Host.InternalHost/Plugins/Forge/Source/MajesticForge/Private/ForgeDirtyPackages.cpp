#include "ForgeDirtyPackages.h"

#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "LandscapeProxy.h"
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

		bool IsWithinProject(const FString& PackageName, bool& bIsDeterminable)
		{
			FString Filename;
			if (!FPackageName::TryConvertLongPackageNameToFilename(PackageName, Filename))
			{
				bIsDeterminable = false;
				return false;
			}
			bIsDeterminable = true;

			FString FullFilename = FPaths::ConvertRelativePathToFull(Filename);
			FString ProjectDirectory = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
			FullFilename.ReplaceInline(TEXT("\\"), TEXT("/"));
			ProjectDirectory.ReplaceInline(TEXT("\\"), TEXT("/"));
			if (!ProjectDirectory.EndsWith(TEXT("/")))
			{
				ProjectDirectory.AppendChar(TEXT('/'));
			}
			return FullFilename.StartsWith(ProjectDirectory, ESearchCase::IgnoreCase);
		}

		FString ClassifyObject(const UObject* Object)
		{
			if (Object->IsA<UWorld>()) return TEXT("world");
			if (Object->IsA<ALandscapeProxy>()) return TEXT("landscape");
			if (Object->IsA<UBlueprint>()) return TEXT("blueprint");
			if (Object->IsA<UMaterialInterface>()) return TEXT("material");
			if (Object->IsA<UTexture>()) return TEXT("texture");
			if (Object->IsA<UStaticMesh>()) return TEXT("static_mesh");
			return TEXT("other");
		}

		TSharedRef<FJsonObject> DescribePackage(UPackage* Package, UWorld* CurrentWorld)
		{
			const FString PackagePath = Package->GetPathName();
			const bool bCurrentLevelPackage = CurrentWorld && Package == CurrentWorld->GetPackage();
			const bool bExternalActorPackage = PackagePath.Contains(TEXT("/__ExternalActors__/"), ESearchCase::IgnoreCase) ||
				PackagePath.Contains(TEXT("/ExternalActors/"), ESearchCase::IgnoreCase);
			bool bProjectMembershipDetermined = false;
			const bool bBelongsToProject = IsWithinProject(PackagePath, bProjectMembershipDetermined);
			FString Classification = bCurrentLevelPackage ? TEXT("current_level") :
				(bExternalActorPackage ? TEXT("world_partition_external_actor") : TEXT("other"));
			FString AssociatedActorPath;
			bool bAssociatedWithCurrentLevel = bCurrentLevelPackage;
			bool bAssociatedObjectsTruncated = false;
			TArray<TSharedPtr<FJsonValue>> AssociatedObjects;
			AssociatedObjects.Reserve(MaxAssociatedObjectsPerPackage);

			ForEachObjectWithPackage(Package, [&](UObject* Object)
			{
				if (!Object)
				{
					return true;
				}
				if (AssociatedObjects.Num() >= MaxAssociatedObjectsPerPackage)
				{
					bAssociatedObjectsTruncated = true;
					return false;
				}

				const FString ObjectPath = Object->GetPathName();
				const FString ObjectClass = Object->GetClass()->GetPathName();
				const FString ObjectClassification = ClassifyObject(Object);
				if (Classification == TEXT("other") || Classification == TEXT("world_partition_external_actor"))
				{
					if (ObjectClassification != TEXT("other"))
					{
						Classification = ObjectClassification;
					}
				}

				TSharedRef<FJsonObject> ObjectInfo = MakeShared<FJsonObject>();
				ObjectInfo->SetStringField(TEXT("object_name"), Object->GetName().Left(MaxNameCharacters));
				ObjectInfo->SetStringField(TEXT("object_path"), ObjectPath.Left(MaxNameCharacters));
				ObjectInfo->SetStringField(TEXT("class_path"), ObjectClass.Left(MaxNameCharacters));
				ObjectInfo->SetBoolField(TEXT("is_actor"), Object->IsA<AActor>());
				if (AActor* Actor = Cast<AActor>(Object))
				{
					if (AssociatedActorPath.IsEmpty())
					{
						AssociatedActorPath = ObjectPath;
					}
					bAssociatedWithCurrentLevel |= Actor->GetWorld() == CurrentWorld;
					ObjectInfo->SetStringField(TEXT("actor_path"), ObjectPath.Left(MaxNameCharacters));
				}
				AssociatedObjects.Add(MakeShared<FJsonValueObject>(ObjectInfo));
				return true;
			}, false);

			TSharedRef<FJsonObject> Result = MakeShared<FJsonObject>();
			Result->SetStringField(TEXT("package_name"), Package->GetName().Left(MaxNameCharacters));
			Result->SetStringField(TEXT("package_path"), PackagePath.Left(MaxNameCharacters));
			Result->SetBoolField(TEXT("is_dirty"), Package->IsDirty());
			Result->SetBoolField(TEXT("is_transient_package"), Package->HasAnyFlags(RF_Transient));
			Result->SetStringField(TEXT("classification"), Classification);
			Result->SetBoolField(TEXT("project_membership_determined"), bProjectMembershipDetermined);
			if (bProjectMembershipDetermined)
			{
				Result->SetBoolField(TEXT("belongs_to_test_project"), bBelongsToProject);
			}
			else
			{
				Result->SetField(TEXT("belongs_to_test_project"), MakeShared<FJsonValueNull>());
			}
			Result->SetBoolField(TEXT("is_current_level_package"), bCurrentLevelPackage);
			Result->SetBoolField(TEXT("associated_with_current_level_determined"),
				bAssociatedWithCurrentLevel || !bAssociatedObjectsTruncated);
			if (bAssociatedWithCurrentLevel || !bAssociatedObjectsTruncated)
			{
				Result->SetBoolField(TEXT("associated_with_current_level"), bAssociatedWithCurrentLevel);
			}
			else
			{
				Result->SetField(TEXT("associated_with_current_level"), MakeShared<FJsonValueNull>());
			}
			Result->SetBoolField(TEXT("associated_actor_determined"),
				!AssociatedActorPath.IsEmpty() || !bAssociatedObjectsTruncated);
			if (!AssociatedActorPath.IsEmpty())
			{
				Result->SetStringField(TEXT("associated_actor_path"), AssociatedActorPath.Left(MaxNameCharacters));
			}
			else
			{
				Result->SetField(TEXT("associated_actor_path"), MakeShared<FJsonValueNull>());
			}
			Result->SetArrayField(TEXT("associated_objects"), AssociatedObjects);
			Result->SetBoolField(TEXT("associated_objects_truncated"), bAssociatedObjectsTruncated);
			Result->SetBoolField(TEXT("classification_complete"),
				Classification != TEXT("other") || !bAssociatedObjectsTruncated);
			return Result;
		}

		bool BuildInventorySnapshot(UWorld* CurrentWorld, FString& OutErrorCode, FString& OutErrorMessage)
		{
			CurrentSnapshot = FInventorySnapshot();
			CurrentSnapshot.CurrentLevelPackage = CurrentWorld->GetPackage()->GetPathName();
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
				TSharedRef<FJsonObject> PackageRow = DescribePackage(Package, CurrentWorld);
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
			if (Field.Key != TEXT("limit") && Field.Key != TEXT("offset") && Field.Key != TEXT("snapshot_id"))
			{
				OutErrorCode = TEXT("invalid_arguments");
				OutErrorMessage = TEXT("Only limit, offset, and snapshot_id are accepted.");
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
			if (!BuildInventorySnapshot(CurrentWorld, OutErrorCode, OutErrorMessage))
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
