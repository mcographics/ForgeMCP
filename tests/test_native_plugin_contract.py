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
    create_start = source.index('if(Action==TEXT("create") || Action==TEXT("create_in_place"))')
    map_transition = source.index("GEditor->CreateNewMapForEditing(false,bWorldPartition)", create_start)
    apply_guard = source.index("IsAuthorizedDisposableProject(DisposableBlockReason)", create_start)
    dirty_guard = source.index("ForgeDirtyPackages::InspectLandscapeApplyPreflight(", create_start)
    destination_guard = source.index("CheckCreateDestinationsAbsent(P.TargetMapPackage", create_start)
    assert create_start < apply_guard < dirty_guard < destination_guard < map_transition
    assert 'TEXT("landscape_safety_gate_blocked")' in source
    assert 'TEXT("dirty_packages_block_apply")' in source
    assert 'TEXT("in_place_creation_disabled")' in source


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
