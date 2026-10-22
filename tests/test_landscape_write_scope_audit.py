"""Write-scope audit accepts only exact native destinations and declared namespaces."""

import pytest

from scripts.run_isolated_landscape_acceptance import (
    _audit_write_set,
    _classify_write,
    _native_scope_paths,
)


def test_native_hlod_and_world_state_destinations_are_exactly_audited(tmp_path):
    project_root = tmp_path.resolve()
    map_file = project_root / "Content/ForgeMCPTests/Landscape/L_A7K38_WP_1234abcd.umap"
    hlod_file = project_root / "Content/ForgeMCPTests/Landscape/L_A7K38_WP_1234abcd_HLODLayer_Instanced.uasset"
    world_state = project_root / "Saved/Config/WorldState/1719541685.json"
    scope = {
        "exact_known_package_destinations": [
            {"filename": str(map_file)},
            {"filename": str(hlod_file)},
        ],
        "exact_known_auxiliary_file_destinations": [
            {"filename": str(world_state)},
        ],
    }

    exact_files, package_stems = _native_scope_paths(scope, project_root)
    assert _classify_write(map_file.relative_to(project_root).as_posix(), "L_A7K38_WP_1234abcd",
                           exact_files, package_stems) == "exact native preview destination"
    assert _classify_write(hlod_file.relative_to(project_root).as_posix(), "L_A7K38_WP_1234abcd",
                           exact_files, package_stems) == "exact native preview destination"
    assert _classify_write(world_state.relative_to(project_root).as_posix(), "L_A7K38_WP_1234abcd",
                           exact_files, package_stems) == "exact native preview destination"
    hlod_sidecar = hlod_file.with_suffix(".uexp").relative_to(project_root).as_posix()
    assert _classify_write(hlod_sidecar, "L_A7K38_WP_1234abcd",
                           exact_files, package_stems) == "approved package sidecar"

    before = {}
    after = {
        map_file.relative_to(project_root).as_posix(): (10, "a" * 64),
        hlod_file.relative_to(project_root).as_posix(): (20, "b" * 64),
        world_state.relative_to(project_root).as_posix(): (30, "c" * 64),
        "Saved/Config/Unexpected.ini": (40, "d" * 64),
    }
    audit = _audit_write_set(before, after, "L_A7K38_WP_1234abcd", scope, project_root)
    assert audit["out_of_scope_paths"] == ["Saved/Config/Unexpected.ini"]
    assert audit["change_count"] == 4


def test_native_scope_path_outside_disposable_root_is_rejected(tmp_path):
    scope = {
        "exact_known_package_destinations": [
            {"filename": str(tmp_path.parent / "outside.uasset")},
        ],
        "exact_known_auxiliary_file_destinations": [],
    }
    with pytest.raises(RuntimeError, match="escaped the disposable project root"):
        _native_scope_paths(scope, tmp_path)


def test_native_scope_schema_missing_destinations_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="omitted exact_known_auxiliary_file_destinations"):
        _native_scope_paths({"exact_known_package_destinations": []}, tmp_path)
