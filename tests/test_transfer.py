import hashlib
import json

import pytest
from pydantic import ValidationError

from server.core.transfer import (
    FBX_BINARY_HEADER,
    StaticMeshTransferManifest,
    TransferArtifactError,
    stage_unreal_artifact,
    verify_staged_artifact,
)


def manifest_data(data):
    return dict(
        transfer_id="a" * 32,
        source_session_id="blender-123",
        target_session_id="unreal-456",
        source_object="Cube",
        source_snapshot_sha256="b" * 64,
        target_project_file="G:/ForgeMCPTest/Test.uproject",
        target_asset_path="/Game/ForgeTransfer/SM_Cube",
        artifact_name="SM_Cube.fbx",
        artifact_sha256=hashlib.sha256(data).hexdigest(),
        artifact_bytes=len(data),
        meters_per_source_unit=1.0,
        source_bounds_min=[-1, -1, -1],
        source_bounds_max=[1, 1, 1],
        vertex_count=8,
        triangle_count=12,
        materials=[{"index": 0, "name": "Material"}],
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("artifact_name", "../Cube.fbx"),
        ("artifact_name", "C:/Cube.fbx"),
        ("artifact_name", "Cube.fbx:stream"),
        ("artifact_name", "Cube.exe"),
        ("artifact_name", "CON.fbx"),
        ("artifact_name", "nul.fbx"),
        ("target_asset_path", "/Engine/Cube"),
        ("target_asset_path", "/Game/../Cube"),
        ("source_session_id", "unreal-123"),
        ("target_session_id", "blender-456"),
        ("target_project_file", "C:/file.txt"),
        ("target_project_file", "relative.uproject"),
        ("target_project_file", "G:/../Test.uproject"),
        ("target_project_file", "G:/\x00Test.uproject"),
        ("meters_per_source_unit", float("nan")),
        ("meters_per_source_unit", 0),
        ("source_bounds_max", [-2, -2, -2]),
        ("source_bounds_max", [-1, -1, -1]),
        ("source_bounds_max", [1e100, 1, 1]),
        ("vertex_count", True),
        ("vertex_count", 100_001),
        ("materials", [{"index": 1, "name": "Material"}]),
        ("overwrite", True),
        ("overwrite", 0),
        ("schema_version", True),
        ("schema_version", 1.0),
        ("artifact_bytes", 64 * 1024 * 1024 + 1),
        ("script", "arbitrary code"),
    ],
)
def test_invalid_transfer_contract_rejected(field, value):
    values = manifest_data(FBX_BINARY_HEADER + b"fixture")
    values[field] = value
    with pytest.raises(ValidationError):
        StaticMeshTransferManifest.model_validate(values)


def test_artifact_integrity_does_not_claim_geometry_validation(tmp_path):
    data = FBX_BINARY_HEADER + b"not a real FBX geometry fixture"
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(data))
    (tmp_path / manifest.artifact_name).write_bytes(data)
    result = verify_staged_artifact(tmp_path, manifest)
    assert result["status"] == "artifact_integrity_verified"
    assert result["native_geometry_verified"] is False
    assert manifest.model_dump()["source_session_id"] == "blender-123"


def staging_fixture(tmp_path):
    source = tmp_path / "blender"
    source.mkdir()
    target = tmp_path / "unreal"
    target.mkdir()
    project = target / "Host.uproject"
    project.write_text("{}", encoding="utf-8")
    data = FBX_BINARY_HEADER + b"fixture"
    values = manifest_data(data)
    values["target_project_file"] = str(project)
    manifest = StaticMeshTransferManifest.model_validate(values)
    (source / manifest.artifact_name).write_bytes(data)
    return source, target, manifest, data


def test_staging_preserves_source_and_rejects_existing_transfer(tmp_path):
    source, target, manifest, data = staging_fixture(tmp_path)
    recipe = stage_unreal_artifact(source, manifest, save=True)
    destination = target / "Saved" / "ForgeTransfers" / manifest.transfer_id
    assert (destination / "mesh.fbx").read_bytes() == data
    assert (source / manifest.artifact_name).read_bytes() == data
    assert recipe["target_session_id"] == "unreal-456"
    assert recipe["save"] is True
    stored = StaticMeshTransferManifest.model_validate_json(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert stored.artifact_name == "mesh.fbx"
    assert verify_staged_artifact(destination, stored)["native_geometry_verified"] is False
    report = json.loads((destination / "staging-report.json").read_text(encoding="utf-8"))
    assert report["state"] == "staged"
    assert report["import_started"] is False
    with pytest.raises(TransferArtifactError, match="already exists"):
        stage_unreal_artifact(source, manifest)
    assert (destination / "mesh.fbx").read_bytes() == data


def test_staging_rejects_corruption_before_target_writes(tmp_path):
    source, target, manifest, data = staging_fixture(tmp_path)
    (source / manifest.artifact_name).write_bytes(data[:-1] + b"x")
    with pytest.raises(TransferArtifactError, match="checksum"):
        stage_unreal_artifact(source, manifest)
    assert not (target / "Saved").exists()


def test_staging_retains_failed_record_if_source_changes_during_copy(tmp_path, monkeypatch):
    import server.core.transfer as transfer

    source, target, manifest, data = staging_fixture(tmp_path)
    protect = transfer.protect_path

    def change_source(path):
        protect(path)
        if path.name == "mesh.fbx":
            (source / manifest.artifact_name).write_bytes(data[:-1] + b"x")

    monkeypatch.setattr(transfer, "protect_path", change_source)
    with pytest.raises(TransferArtifactError, match="retained transfer"):
        stage_unreal_artifact(source, manifest)
    destination = target / "Saved" / "ForgeTransfers" / manifest.transfer_id
    report = json.loads((destination / "staging-report.json").read_text(encoding="utf-8"))
    assert report["state"] == "staging_failed"
    assert report["import_started"] is False
    assert not (destination / "manifest.json").exists()


def test_staging_requires_real_target_and_exact_save_policy(tmp_path):
    source, target, manifest, _ = staging_fixture(tmp_path)
    with pytest.raises(TransferArtifactError, match="Boolean"):
        stage_unreal_artifact(source, manifest, save=1)
    (target / "Host.uproject").unlink()
    with pytest.raises(TransferArtifactError, match="missing"):
        stage_unreal_artifact(source, manifest)
    assert not (target / "Saved").exists()


def test_material_staging_requires_supported_surface_and_generates_new_packages(tmp_path):
    source, target, manifest, _ = staging_fixture(tmp_path)
    with pytest.raises(TransferArtifactError, match="supported constant-PBR"):
        stage_unreal_artifact(source, manifest, transfer_materials=True)
    assert not (target / "Saved").exists()
    values = manifest.model_dump()
    values["materials"][0]["surface"] = {
        "model": "pbr_constants", "base_color": [0.1, 0.2, 0.3],
        "roughness": 0.27, "metallic": 0.63,
        "two_sided": True,
    }
    manifest = StaticMeshTransferManifest.model_validate(values)
    recipe = stage_unreal_artifact(source, manifest, transfer_materials=True, save=True)
    definition = recipe["material_definitions"][0]
    assert definition["asset_path"] == f"/Game/ForgeTransfer/M_{manifest.transfer_id}_0"
    assert definition["base_color"] == [0.1, 0.2, 0.3]
    assert definition["color_space"] == "scene_linear"
    assert definition["roughness"] == 0.27
    assert definition["metallic"] == 0.63


def test_replacement_staging_carries_only_reviewed_revisions_and_slot_identity(tmp_path):
    source, target, manifest, _ = staging_fixture(tmp_path)
    recipe = stage_unreal_artifact(source, manifest, save=True, replace_existing=True,
        expected_source_baseline_sha256="a" * 64, expected_target_revision_sha256="b" * 64)
    assert recipe["replace_existing"] is True
    assert recipe["expected_source_baseline_sha256"] == "a" * 64
    assert recipe["expected_target_revision_sha256"] == "b" * 64
    assert recipe["material_slot_names"] == [slot.name for slot in manifest.materials]
    assert "material_definitions" not in recipe
    with pytest.raises(TransferArtifactError, match="Replacement requires"):
        stage_unreal_artifact(source, manifest, replace_existing=True,
            expected_source_baseline_sha256="a" * 64, expected_target_revision_sha256="b" * 64)


@pytest.mark.parametrize("field,value", [
    ("base_color", [0.1, 0.2, 2]), ("base_color", [0.1, 0.2]),
    ("roughness", float("nan")), ("metallic", -1),
    ("two_sided", 1),
    ("color_space", "srgb"), ("script", "execute"),
])
def test_material_surface_rejects_invalid_constants_and_unknown_fields(field, value):
    values = manifest_data(FBX_BINARY_HEADER + b"fixture")
    surface = {"model": "pbr_constants", "base_color": [0.1, 0.2, 0.3],
               "roughness": 0.5, "metallic": 0.0, "two_sided": True, field: value}
    values["materials"][0]["surface"] = surface
    with pytest.raises(ValidationError):
        StaticMeshTransferManifest.model_validate(values)


def test_changed_bytes_rejected_before_import(tmp_path):
    data = FBX_BINARY_HEADER + b"one"
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(data))
    path = tmp_path / manifest.artifact_name
    path.write_bytes(data)
    verify_staged_artifact(tmp_path, manifest)
    path.write_bytes(FBX_BINARY_HEADER + b"two")
    with pytest.raises(TransferArtifactError, match="checksum"):
        verify_staged_artifact(tmp_path, manifest)


def test_changed_size_missing_and_wrong_format_rejected(tmp_path):
    data = FBX_BINARY_HEADER + b"fixture"
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(data))
    path = tmp_path / manifest.artifact_name
    with pytest.raises(TransferArtifactError, match="missing"):
        verify_staged_artifact(tmp_path, manifest)
    path.write_bytes(data + b"extra")
    with pytest.raises(TransferArtifactError, match="size"):
        verify_staged_artifact(tmp_path, manifest)
    invalid = b"x" * len(data)
    path.write_bytes(invalid)
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(invalid))
    with pytest.raises(TransferArtifactError, match="binary FBX"):
        verify_staged_artifact(tmp_path, manifest)


def test_linked_artifact_rejected(tmp_path):
    data = FBX_BINARY_HEADER + b"fixture"
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(data))
    target = tmp_path / "outside.fbx"
    target.write_bytes(data)
    try:
        (tmp_path / manifest.artifact_name).symlink_to(target)
    except OSError:
        pytest.skip("Symbolic link creation unavailable for this Windows account")
    with pytest.raises(TransferArtifactError, match="links"):
        verify_staged_artifact(tmp_path, manifest)


def test_linked_staging_root_rejected(tmp_path):
    data = FBX_BINARY_HEADER + b"fixture"
    manifest = StaticMeshTransferManifest.model_validate(manifest_data(data))
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / manifest.artifact_name).write_bytes(data)
    staging = tmp_path / "staging"
    try:
        staging.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic link creation unavailable for this Windows account")
    with pytest.raises(TransferArtifactError, match="links"):
        verify_staged_artifact(staging, manifest)
