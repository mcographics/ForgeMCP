# SPDX-License-Identifier: MIT
"""Shared static-mesh transfer contract and staged artifact integrity checks.

This module validates declared metadata and bytes, not FBX geometry or approval.
Native export/import and post-import verification remain separate operations.
"""

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator, model_validator

from server.core.security import protect_path

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
FBX_BINARY_HEADER = b"Kaydara FBX Binary  \x00\x1a\x00"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Coordinate = Annotated[FiniteFloat, Field(ge=-1e8, le=1e8)]
Triple = Annotated[list[Coordinate], Field(min_length=3, max_length=3)]


class TransferModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


UnitValue = Annotated[FiniteFloat, Field(ge=0, le=1)]


class ConstantSurface(TransferModel):
    model: Literal["pbr_constants"]
    color_space: Literal["scene_linear"] = "scene_linear"
    base_color: Annotated[list[UnitValue], Field(min_length=3, max_length=3)]
    roughness: UnitValue
    metallic: UnitValue
    two_sided: bool


class UnsupportedSurface(TransferModel):
    model: Literal["unsupported"]
    reason: Literal["shader_graph", "transparency", "non_default_bsdf", "out_of_range", "animation"]


class MaterialSlot(TransferModel):
    index: Annotated[int, Field(strict=True, ge=0, le=31)]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    surface: Annotated[ConstantSurface | UnsupportedSurface, Field(discriminator="model")] | None = None


class StaticMeshTransferManifest(TransferModel):
    schema_version: Literal[1] = 1
    asset_kind: Literal["static_mesh"] = "static_mesh"
    format: Literal["fbx_binary"] = "fbx_binary"
    transfer_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    source_session_id: Annotated[str, Field(pattern=r"^blender-[1-9][0-9]{0,9}$")]
    target_session_id: Annotated[str, Field(pattern=r"^unreal-[1-9][0-9]{0,9}$")]
    source_object: Annotated[str, Field(min_length=1, max_length=128)]
    source_snapshot_sha256: Digest
    target_project_file: Annotated[str, Field(min_length=1, max_length=1024)]
    target_asset_path: Annotated[
        str,
        Field(
            pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)+[A-Za-z_][A-Za-z0-9_]*$", max_length=240
        ),
    ]
    artifact_name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]{0,95}\.fbx$")]
    artifact_sha256: Digest
    artifact_bytes: Annotated[int, Field(strict=True, ge=23, le=MAX_ARTIFACT_BYTES)]
    source_coordinates: Literal["blender_native"] = "blender_native"
    target_coordinates: Literal["unreal_native"] = "unreal_native"
    meters_per_source_unit: Annotated[FiniteFloat, Field(gt=0, le=1000)]
    source_bounds_min: Triple
    source_bounds_max: Triple
    source_world_bounds_min: Triple | None = None
    source_world_bounds_max: Triple | None = None
    source_world_vertices: Annotated[list[Triple], Field(max_length=256)] = Field(default_factory=list)
    world_vertices_truncated: bool = True
    vertex_count: Annotated[int, Field(strict=True, ge=3, le=100_000)]
    triangle_count: Annotated[int, Field(strict=True, ge=1, le=200_000)]
    materials: Annotated[list[MaterialSlot], Field(max_length=32)] = Field(default_factory=list)
    overwrite: Literal[False] = False

    @field_validator("schema_version", "overwrite", mode="before")
    @classmethod
    def require_exact_scalar_types(cls, value, info):
        expected = int if info.field_name == "schema_version" else bool
        if type(value) is not expected:
            raise ValueError("Schema version and overwrite policy require exact scalar types")
        return value

    @field_validator("artifact_name")
    @classmethod
    def reject_device_names(cls, value):
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10))
        if value.split(".", 1)[0].upper() in reserved:
            raise ValueError("Artifact filename must not name a Windows device")
        return value

    @field_validator("target_project_file")
    @classmethod
    def validate_project_identity(cls, value):
        paths = (PureWindowsPath(value), PurePosixPath(value))
        if (
            any(ord(c) < 32 for c in value)
            or not any(p.is_absolute() for p in paths)
            or any(".." in p.parts for p in paths)
            or not value.lower().endswith(".uproject")
        ):
            raise ValueError("Target identity must be an absolute Unreal project file path")
        return value

    @model_validator(mode="after")
    def validate_geometry_metadata(self):
        if (self.source_world_bounds_min is None) != (self.source_world_bounds_max is None):
            raise ValueError("World-space bounds must be supplied together")
        if self.source_world_bounds_min is not None and any(
            a > b for a, b in zip(self.source_world_bounds_min, self.source_world_bounds_max)
        ):
            raise ValueError("World-space bounds are invalid")
        if not self.world_vertices_truncated and len(self.source_world_vertices) != self.vertex_count:
            raise ValueError("Complete world vertices must match the declared vertex count")
        if any(a > b for a, b in zip(self.source_bounds_min, self.source_bounds_max)):
            raise ValueError("Minimum bounds must not exceed maximum bounds")
        if self.source_bounds_min == self.source_bounds_max:
            raise ValueError("Mesh bounds must have nonzero extent")
        if [slot.index for slot in self.materials] != list(range(len(self.materials))):
            raise ValueError("Material slot indices must be contiguous and ordered")
        return self


class TransferArtifactError(ValueError):
    """An artifact failed validation before reaching a native importer."""


def _reject_links(path: Path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise TransferArtifactError("Transfer staging must not contain links or reparse points")
    return info


def _file_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def verify_staged_artifact(staging_root: Path, manifest: StaticMeshTransferManifest) -> dict:
    """Verify a binary FBX in a trusted private staging root, without importing it.

    Call again immediately before native import; success is not a durable approval.
    A header match does not establish valid FBX contents or correct declared geometry.
    """
    root = Path(staging_root).absolute()
    try:
        for ancestor in (root, *root.parents):
            _reject_links(ancestor)
        if not root.is_dir():
            raise TransferArtifactError("Transfer staging root must be a directory")
        path = root / manifest.artifact_name
        before = _reject_links(path)
        if not stat.S_ISREG(before.st_mode):
            raise TransferArtifactError("Transfer artifact must be a regular file")
        if before.st_size != manifest.artifact_bytes:
            raise TransferArtifactError("Transfer artifact size does not match the manifest")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if _file_identity(before) != _file_identity(opened):
                raise TransferArtifactError("Transfer artifact changed while opening")
            if stream.read(len(FBX_BINARY_HEADER)) != FBX_BINARY_HEADER:
                raise TransferArtifactError("Transfer artifact is not binary FBX")
            stream.seek(0)
            total = 0
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > manifest.artifact_bytes:
                    raise TransferArtifactError("Transfer artifact grew during validation")
                digest.update(chunk)
            if _file_identity(os.fstat(stream.fileno())) != _file_identity(opened):
                raise TransferArtifactError("Transfer artifact changed during validation")
        if total != manifest.artifact_bytes or digest.hexdigest() != manifest.artifact_sha256:
            raise TransferArtifactError("Transfer artifact checksum does not match the manifest")
        if _file_identity(_reject_links(path)) != _file_identity(opened):
            raise TransferArtifactError("Transfer artifact was replaced during validation")
    except OSError as error:
        raise TransferArtifactError("Transfer staging file is missing or inaccessible") from error
    return {
        "transfer_id": manifest.transfer_id,
        "artifact_name": manifest.artifact_name,
        "artifact_bytes": total,
        "artifact_sha256": digest.hexdigest(),
        "status": "artifact_integrity_verified",
        "native_geometry_verified": False,
    }


def stage_unreal_artifact(
    source_root: Path, manifest: StaticMeshTransferManifest, *, save: bool = False,
    transfer_materials: bool = False,
) -> dict:
    """Copy a verified export to its explicit target project without importing it.

    Caller must establish native session identity before staging and again before
    applying an import. The manifest alone is not application authorization.
    Existing transfers are never reused, even after a failed attempt.
    """
    if type(save) is not bool or type(transfer_materials) is not bool:
        raise TransferArtifactError("Save and material-transfer policies must be Booleans")
    definitions = []
    if transfer_materials:
        folder = manifest.target_asset_path.rsplit("/", 1)[0]
        for slot in manifest.materials:
            if not isinstance(slot.surface, ConstantSurface):
                raise TransferArtifactError("Material transfer requires an explicitly supported constant-PBR surface")
            path = f"{folder}/M_{manifest.transfer_id}_{slot.index}"
            if len(path) > 240:
                raise TransferArtifactError("Generated material destination exceeds package path limits")
            definitions.append({
                "index": slot.index, "source_name": slot.name, "asset_path": path,
                **slot.surface.model_dump(exclude={"model"}),
            })
    verify_staged_artifact(source_root, manifest)
    project = Path(manifest.target_project_file).absolute()
    try:
        for ancestor in (project, *project.parents):
            _reject_links(ancestor)
        if not project.is_file():
            raise TransferArtifactError("Target project must be an existing regular file")
        # Create only missing runtime directories; reject links before using them.
        saved = project.parent / "Saved"
        saved.mkdir(exist_ok=True)
        _reject_links(saved)
        transfers = saved / "ForgeTransfers"
        transfers.mkdir(exist_ok=True)
        _reject_links(transfers)
        protect_path(transfers)
        destination = transfers / manifest.transfer_id
        destination.mkdir(exist_ok=False)
        protect_path(destination)
    except FileExistsError as error:
        raise TransferArtifactError("Target transfer already exists; no files were overwritten") from error
    except OSError as error:
        raise TransferArtifactError("Target project staging is missing or inaccessible") from error

    report = {
        "schema_version": 1,
        "transfer_id": manifest.transfer_id,
        "source_session_id": manifest.source_session_id,
        "target_session_id": manifest.target_session_id,
        "target_project_file": str(project),
        "target_asset_path": manifest.target_asset_path,
        "state": "staging_started",
        "import_started": False,
    }

    def record():
        temporary = destination / "staging-report.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            protect_path(temporary)
            json.dump(report, stream, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(destination / "staging-report.json")

    try:
        record()
        source = Path(source_root).absolute() / manifest.artifact_name
        before = _reject_links(source)
        with source.open("rb") as incoming, (destination / "mesh.fbx").open("xb") as outgoing:
            protect_path(destination / "mesh.fbx")
            opened = os.fstat(incoming.fileno())
            if _file_identity(before) != _file_identity(opened):
                raise TransferArtifactError("Source artifact changed while opening for staging")
            digest = hashlib.sha256()
            total = 0
            while chunk := incoming.read(1024 * 1024):
                total += len(chunk)
                if total > manifest.artifact_bytes:
                    raise TransferArtifactError("Source artifact grew during staging")
                digest.update(chunk)
                outgoing.write(chunk)
            outgoing.flush()
            os.fsync(outgoing.fileno())
            if (
                _file_identity(os.fstat(incoming.fileno())) != _file_identity(opened)
                or _file_identity(_reject_links(source)) != _file_identity(opened)
                or total != manifest.artifact_bytes
                or digest.hexdigest() != manifest.artifact_sha256
            ):
                raise TransferArtifactError("Source artifact changed during staging")
        staged = manifest.model_copy(update={"artifact_name": "mesh.fbx"})
        verify_staged_artifact(destination, staged)
        with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
            protect_path(destination / "manifest.json")
            stream.write(staged.model_dump_json(indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        report.update(state="staged", artifact_sha256=digest.hexdigest(), artifact_bytes=total)
    except (OSError, TransferArtifactError) as error:
        report.update(state="staging_failed", diagnostic="Artifact staging failed before native import")
        try:
            record()
        except OSError as record_error:
            raise TransferArtifactError(
                "Staging outcome unknown; inspect retained transfer before retrying"
            ) from record_error
        raise TransferArtifactError("Artifact staging failed; retained transfer requires inspection") from error
    try:
        record()
    except OSError as error:
        raise TransferArtifactError("Staging outcome unknown; inspect retained transfer before retrying") from error
    recipe = {
        "transfer_id": manifest.transfer_id,
        "artifact_sha256": manifest.artifact_sha256,
        "artifact_bytes": manifest.artifact_bytes,
        "asset_path": manifest.target_asset_path,
        "target_project_file": str(project),
        "target_session_id": manifest.target_session_id,
        "save": save,
    }
    if transfer_materials:
        recipe["material_definitions"] = definitions
    return recipe
