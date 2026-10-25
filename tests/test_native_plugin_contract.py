from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "Plugins" / "Forge"
NATIVE_MODULE = PLUGIN_ROOT / "Source" / "MajesticForge" / "Private" / "MajesticForgeModule.cpp"
DIRTY_PACKAGE_OBSERVER = PLUGIN_ROOT / "Source" / "MajesticForge" / "Private" / "ForgeDirtyPackages.cpp"
LANDSCAPE_SOURCE = PLUGIN_ROOT / "Source" / "MajesticForge" / "Private" / "ForgeLandscape.cpp"

LANDSCAPE_COMMANDS = (
    "landscape_info",
    "landscape_preview",
    "landscape_apply",
    "landscape_job_status",
    "landscape_job_cancel",
)


def test_release_plugin_source_retains_the_five_landscape_commands():
    source = NATIVE_MODULE.read_text(encoding="utf-8")

    for command in LANDSCAPE_COMMANDS:
        token = f'TEXT("{command}")'
        assert source.count(token) >= 2, f"{command} must remain advertised and dispatched"


def test_release_plugin_contains_read_only_dirty_package_observer():
    module = NATIVE_MODULE.read_text(encoding="utf-8")
    observer = DIRTY_PACKAGE_OBSERVER.read_text(encoding="utf-8")

    assert '#include "ForgeDirtyPackages.h"' in module
    assert 'TEXT("inspect_dirty_packages")' in module
    assert "ForgeDirtyPackages::Handle" in module
    assert "IsInGameThread()" in observer
    assert "Package->IsDirty()" in observer
    assert "Package->HasAnyFlags(RF_Transient)" in observer
    assert 'TEXT("inventory_id")' in observer
    assert 'TEXT("page_consistency_note")' in observer


def test_landscape_creation_preview_reports_structured_write_scope_and_unknowns():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")

    for field in (
        "exact_known_package_destinations",
        "exact_known_auxiliary_file_destinations",
        "allowed_generated_package_namespaces",
        "expected_auxiliary_file_categories",
        "existing_package_overwrite_checks",
        "potential_editor_generated_side_effects",
        "explicit_unknown_or_unbounded_effects",
        "rollback_limitations",
        "preservation_limitations",
    ):
        assert f'TEXT("{field}")' in source
    assert 'TEXT("deterministic_known_destination")' in source
    assert 'TEXT("deterministic_from_engine_default_hlod_layer_chain")' in source
    assert 'TEXT("deterministic_from_engine_FCrc_MemCrc32_package_path")' in source
    assert 'TEXT("Unreal-generated package names; namespace only")' in source
    assert 'TEXT("Apply is refused outside a marked, isolated disposable project; post-operation filesystem audit is detection, not prevention.")' in source


def test_landscape_apply_checks_disposable_marker_dirty_state_and_destinations_before_world_transition():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    apply_command = source.index('if(Command != TEXT("landscape_apply"))')
    create_start = source.index(
        'if(Action==TEXT("create") || Action==TEXT("create_in_place"))', apply_command
    )
    map_transition = source.index("GEditor->CreateNewMapForEditing(false,bWorldPartition)", create_start)
    apply_guard = source.index("IsAuthorizedDisposableProject(DisposableBlockReason)", create_start)
    dirty_guard = source.index(
        "ForgeDirtyPackages::InspectLandscapeApplyPreflight(\n                W, true, DirtyPolicy)",
        create_start,
    )
    destination_guard = source.index("CheckCreateDestinationsAbsent(P.TargetMapPackage", create_start)
    assert create_start < apply_guard < dirty_guard < destination_guard < map_transition
    assert 'TEXT("landscape_safety_gate_blocked")' in source
    assert 'TEXT("dirty_packages_block_apply")' in source
    assert 'TEXT("existing_world_authorization_required")' in source
    assert 'TEXT("existing_world_authorization_stale")' in source


def test_existing_world_landscape_grant_is_default_deny_exact_and_host_injected():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    host_auth = (Path(__file__).resolve().parents[1] / "server" / "core" / "landscape_authorization.py").read_text(encoding="utf-8")
    assert 'TEXT("_forge_landscape_authorization")' in source
    assert 'TEXT("session_id")' in source
    assert 'TEXT("project_file")' in source
    assert 'TEXT("world_path")' in source
    assert 'TEXT("expires_at_unix")' in source
    assert "WorldPackage != World->GetOutermost()->GetName()" in source
    assert "CanonicalPath(ProjectFile).Equals(CanonicalPath(FPaths::GetProjectFilePath())" in source
    assert "ParsedActions.Contains(RequiredAction)" in source
    assert "Path != W->GetOutermost()->GetName()" in source
    assert "ExistingWorldPartitionConfiguration(W)" in source
    assert 'existing_world_landscape_authorization(' in host_auth
    assert 'required=request.action == "create_in_place"' in (Path(__file__).resolve().parents[1] / "server" / "main.py").read_text(encoding="utf-8")
    assert "create_in_place" in host_auth and 'return None' in host_auth


def test_existing_world_apply_is_unsaved_until_explicit_scoped_save():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    assert 'TEXT("created_unsaved")' in source
    assert 'TEXT("explicit_save_required")' in source
    assert "HasOnlyExpectedDirtyLandscapePackages" in source
    assert "ForgeDirtyPackages::InspectLandscapeApplyPreflight(W, false, DirtyPolicy)" in source
    assert "BackupExistingWorldWriteScope" in source
    assert "SaveExistingWorldLandscapePackages" in source
    assert "ValidateExistingWorldWriteScope" in source
    assert 'TEXT("existing_world_write_scope_failed")' in source
    assert 'TEXT("dirty_package_scope_rejected")' in source


def test_existing_world_sculpting_is_bound_to_the_created_landscape_and_fresh_grant():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    assert "ReadExistingWorldAuthorization(Args, W, Action, PreviewGrant)" in source
    assert "AuthorizedExistingWorldLandscapes.Find(PreviewGrant.Id)" in source
    assert 'TEXT("landscape_outside_authorized_scope")' in source
    assert "P.ExistingWorldAuthorizationId != ApplyGrant.Id" in source
    assert "P.ExistingWorldAuthorizationExpiresAtUnix != ApplyGrant.ExpiresAtUnix" in source
    assert "!ApplyGrant.Allows(Action)" in source
    assert "CurrentScopeFingerprint != P.ExistingWorldPackageFingerprint" in source


def test_existing_world_creation_keeps_disposable_map_workflow_and_dirty_guards():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    assert 'if (!TestMap(Path) || FPackageName::DoesPackageExist(Path) || FindPackage(nullptr,*Path))' in source
    assert 'if (!SafeCreateSourceWorld(W))' in source
    assert "FEditorFileUtils::SaveLevel(W->PersistentLevel,Filename)" in source
    assert "ForgeDirtyPackages::InspectLandscapeApplyPreflight(W, false, DirtyPolicy)" in source
    assert "ForgeDirtyPackages::InspectLandscapeApplyPreflight(\n                W, true, DirtyPolicy)" in source


def test_existing_world_save_fails_closed_around_backup_and_package_scope():
    source = LANDSCAPE_SOURCE.read_text(encoding="utf-8")
    for contract in (
        "BackupExistingWorldWriteScope(W, L, BackupRoot, Snapshot, BackupError)",
        'TEXT("existing_world_backup_failed")',
        "SaveExistingWorldLandscapePackages(W, L, SaveError)",
        'TEXT("existing_world_package_save_failed")',
        "ValidateExistingWorldWriteScope(W, Snapshot, WriteScopeError)",
        'TEXT("existing_world_write_scope_failed")',
        "AuthorizedExistingWorldLandscapes.Empty()",
    ):
        assert contract in source


def test_dirty_inventory_uses_authoritative_categories_and_separates_sample_truncation():
    source = DIRTY_PACKAGE_OBSERVER.read_text(encoding="utf-8")
    assert 'TEXT("engine_script")' in source
    assert 'TEXT("engine_content")' in source
    assert 'TEXT("project_content")' in source
    assert 'TEXT("current_world")' in source
    assert 'TEXT("external_actor")' in source
    assert 'TEXT("unknown")' in source
    assert 'TEXT("unresolved_engine_script_package")' in source
    assert 'TEXT("unresolved_project_content_package")' in source
    assert 'TEXT("target_map_path_namespace_match")' in source
    assert 'FPackageName::IsScriptPackage(FStringView(Evidence.PackagePath))' in source
    assert 'PKG_CompiledIn' in source
    assert 'associated_objects_sample_truncated' in source
    assert 'ownership_scan_complete' in source
    assert '!Evidence.bEngineScriptProvenanceVerified' in source
    assert 'TEXT("/Script/SlateCore")' in source


def test_landscape_policy_exception_is_exact_and_disposable_only():
    source = DIRTY_PACKAGE_OBSERVER.read_text(encoding="utf-8")
    test_source = (PLUGIN_ROOT / "Source" / "MajesticForge" / "Private"
                   / "ForgeDirtyPackagesPolicyTests.cpp").read_text(encoding="utf-8")

    assert 'Facts.PackagePath != TEXT("/Script/SlateCore")' in source
    assert 'if (!bDisposableProject)' in source
    assert 'Facts.bClassificationComplete' in source
    assert 'Facts.bOwnershipScanComplete' in source
    assert 'Facts.bAssociationWithCurrentWorldDetermined' in source
    assert 'Facts.AssociatedActorCount != 0' in source
    assert 'Facts.ExternalActorCount != 0' in source
    assert 'PKG_ContainsMapData' in source
    assert "Dirty external actor blocks" in test_source
    assert "Unknown package ownership blocks" in test_source
    assert "An incomplete package snapshot blocks Apply" in test_source
