# SPDX-License-Identifier: MIT
"""Reviewed native Blender-to-Unreal static-mesh workflow with durable receipts."""

import hashlib
import math
import time
import uuid
from pathlib import Path
from typing import Annotated

from pydantic import Field, model_validator

from server.core.connections import BridgeError
from server.core.transfer import (
    ConstantSurface,
    StaticMeshTransferManifest,
    TransferArtifactError,
    TransferModel,
    stage_unreal_artifact,
)
from server.core.workflow_journal import STAGES, JournalError

Vector = Annotated[list[Annotated[float, Field(ge=-1e8, le=1e8, allow_inf_nan=False)]],
                   Field(min_length=3, max_length=3)]


class TransferRequest(TransferModel):
    source_session_id: Annotated[str, Field(pattern=r"^blender-[1-9][0-9]{0,9}$")]
    target_session_id: Annotated[str, Field(pattern=r"^unreal-[1-9][0-9]{0,9}$")]
    source_object: Annotated[str, Field(min_length=1, max_length=128)]
    target_asset_path: Annotated[str, Field(
        pattern=r"^/Game/(?:[A-Za-z_][A-Za-z0-9_]*/)+[A-Za-z_][A-Za-z0-9_]*$", max_length=240)]
    save_assets: bool = True
    place: bool = True
    location: Vector = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: Vector = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    scale: Vector = Field(default_factory=lambda: [1.0, 1.0, 1.0])

    @model_validator(mode="after")
    def nonzero_scale(self):
        if any(abs(v) < 1e-8 for v in self.scale):
            raise ValueError("Placement scale must be nonzero")
        return self


class WorkflowError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def close_vector(actual, expected):
    return (isinstance(actual, list) and len(actual) == len(expected)
            and all(type(a) in (int, float) and math.isfinite(a)
                    and abs(a - b) <= max(0.001, abs(b) * 1e-6)
                    for a, b in zip(actual, expected)))


def converted(point, meters):
    x, y, z = point
    return [-y * meters * 100, -x * meters * 100, z * meters * 100]


def verify_import(manifest, result):
    path = manifest.target_asset_path + "." + manifest.target_asset_path.rsplit("/", 1)[1]
    if (result.get("state") != "imported" or result.get("asset_path") != path
            or result.get("class_path") != "/Script/Engine.StaticMesh"
            or result.get("vertex_count") != manifest.vertex_count
            or result.get("triangle_count") != manifest.triangle_count):
        raise WorkflowError("import_verification_failed")
    lo, hi = manifest.source_world_bounds_min, manifest.source_world_bounds_max
    expected_min = converted([hi[0], hi[1], lo[2]], manifest.meters_per_source_unit)
    expected_max = converted([lo[0], lo[1], hi[2]], manifest.meters_per_source_unit)
    if not close_vector(result.get("bounds_min_cm"), expected_min) or not close_vector(result.get("bounds_max_cm"), expected_max):
        raise WorkflowError("geometry_verification_failed")
    positions_verified = False
    if not manifest.world_vertices_truncated:
        actual = result.get("vertex_positions_cm")
        if result.get("vertices_truncated") is not False or not isinstance(actual, list) or len(actual) != manifest.vertex_count:
            raise WorkflowError("geometry_verification_failed")
        if any(not isinstance(p, list) or len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in actual):
            raise WorkflowError("geometry_verification_failed")
        expected = sorted(converted(p, manifest.meters_per_source_unit) for p in manifest.source_world_vertices)
        if not all(close_vector(a, b) for a, b in zip(sorted(actual), expected)):
            raise WorkflowError("geometry_verification_failed")
        positions_verified = True
    materials = result.get("materials", [])
    if not isinstance(materials, list) or len(materials) != len(manifest.materials):
        raise WorkflowError("material_verification_failed")
    folder = manifest.target_asset_path.rsplit("/", 1)[0]
    for slot, native in zip(manifest.materials, materials):
        expected_path = f"{folder}/M_{manifest.transfer_id}_{slot.index}"
        expected_path += "." + expected_path.rsplit("/", 1)[1]
        surface = slot.surface
        if (native.get("asset_path") != expected_path or native.get("native_graph_verified") is not True
                or native.get("color_space") != "scene_linear" or native.get("two_sided") != surface.two_sided
                or not close_vector(native.get("base_color"), surface.base_color)
                or not close_vector([native.get("roughness"), native.get("metallic")], [surface.roughness, surface.metallic])):
            raise WorkflowError("material_verification_failed")
    return {"geometry_bounds_and_counts_verified": True,
            "complete_vertex_positions_verified": positions_verified,
            "material_constant_graphs_verified": True, "shader_compile_verified": False,
            "visual_equivalence_verified": False}


def _quaternion(rotation):
    pitch, yaw, roll = (math.radians(v) / 2 for v in rotation)
    sp, cp, sy, cy, sr, cr = math.sin(pitch), math.cos(pitch), math.sin(yaw), math.cos(yaw), math.sin(roll), math.cos(roll)
    return [sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy]


class TransferCoordinator:
    def __init__(self, connections, journal):
        self.connections, self.journal = connections, journal
        self.previews = {}
        self.active = set()

    def session(self, kind, session_id):
        matches = [s for s in self.connections.discover() if s.kind == kind and s.session_id == session_id]
        if len(matches) != 1:
            raise WorkflowError("session_not_found" if not matches else "ambiguous_session")
        return matches[0]

    @staticmethod
    def binding(session):
        return hashlib.sha256(session.token.encode()).hexdigest()

    async def target_context(self, session):
        health = await self.connections.request(session, "health")
        if type(health.get("transfer_contract_version")) is not int or health["transfer_contract_version"] != 1:
            raise WorkflowError("adapter_upgrade_required")
        info = await self.connections.request(session, "project_info")
        if info.get("play_in_editor") is not False:
            raise WorkflowError("invalid_context")
        return {"project_file": str(Path(info["project_file"]).absolute()), "level": info["level"]}

    def manifest(self, metadata, request, context, transfer_id, *, exported=False):
        names = ("source_object", "source_session_id", "source_snapshot_sha256", "source_bounds_min",
                 "source_bounds_max", "vertex_count", "triangle_count", "meters_per_source_unit", "materials",
                 "source_world_bounds_min", "source_world_bounds_max", "source_world_vertices", "world_vertices_truncated")
        if any(name not in metadata for name in names):
            raise WorkflowError("adapter_upgrade_required")
        values = {name: metadata[name] for name in names}
        values.update(transfer_id=transfer_id, target_session_id=request.target_session_id,
                      target_project_file=context["project_file"], target_asset_path=request.target_asset_path,
                      artifact_name="mesh.fbx", artifact_sha256=metadata["artifact_sha256"] if exported else "0" * 64,
                      artifact_bytes=metadata["artifact_bytes"] if exported else 23)
        manifest = StaticMeshTransferManifest.model_validate(values)
        if manifest.source_world_bounds_min is None or manifest.source_world_bounds_max is None:
            raise WorkflowError("adapter_upgrade_required")
        if manifest.source_session_id != request.source_session_id or manifest.source_object != request.source_object:
            raise WorkflowError("source_identity_mismatch")
        if any(not isinstance(slot.surface, ConstantSurface) for slot in manifest.materials):
            raise WorkflowError("unsupported_material_surface")
        return manifest

    async def preview(self, request):
        source = self.session("blender", request.source_session_id)
        target = self.session("unreal", request.target_session_id)
        context = await self.target_context(target)
        try:
            await self.connections.request(target, "asset_info", {"asset_path": request.target_asset_path})
        except BridgeError as error:
            if error.code != "asset_not_found":
                raise
        else:
            raise WorkflowError("destination_exists")
        health = await self.connections.request(source, "health")
        if type(health.get("transfer_contract_version")) is not int or health["transfer_contract_version"] != 1:
            raise WorkflowError("adapter_upgrade_required")
        exported = await self.connections.request(source, "export_preview", {"name": request.source_object})
        manifest = self.manifest(exported, request, context, exported["preview_id"])
        now = time.monotonic()
        self.previews = {k: p for k, p in self.previews.items() if p["expires"] > now}
        if len(self.previews) >= 32:
            raise WorkflowError("preview_limit")
        operation_id = uuid.uuid4().hex
        self.previews[operation_id] = {"request": request, "context": context, "manifest": manifest,
                                      "export_preview_id": exported["preview_id"], "expires": now + 300,
                                      "source_binding": self.binding(source), "target_binding": self.binding(target)}
        return {"operation_id": operation_id, "preview_id": operation_id, "expires_in_seconds": 300,
                "source": manifest.model_dump(exclude={"artifact_sha256", "artifact_bytes"}),
                "target": context, "changes": request.model_dump(), "saves_source_scene": False,
                "saves_level": False, "overwrite": False,
                "limitations": ["opaque constant-PBR material profile", "shader/visual verification remains separate",
                                "complete vertex-position comparison is limited to 256 vertices; all meshes receive bounds/count checks"]}

    async def reconcile(self, operation_id, target_session_id):
        """Observe current native state without changing receipts or replaying steps."""
        record = self.journal.read(operation_id)
        request = TransferRequest.model_validate(record["plan"]["request"])
        recorded_context = record["plan"]["target"]
        target = self.session("unreal", target_session_id)
        context = await self.target_context(target)
        if Path(context["project_file"]).resolve() != Path(recorded_context["project_file"]).resolve():
            raise WorkflowError("wrong_target_project")
        asset_path = request.target_asset_path + "." + request.target_asset_path.rsplit("/", 1)[1]
        result = {"operation_id": operation_id, "recorded_state": record["state"],
                  "observed_session_id": target_session_id, "target_project_verified": True,
                  "recorded_level_matches": context["level"] == recorded_context["level"],
                  "receipt_modified": False, "automatic_native_replay_allowed": False,
                  "recovery_completed": False, "saved_contents_verified": False}
        try:
            mesh = await self.connections.request(target, "mesh_info", {"asset_path": asset_path})
        except BridgeError as error:
            if error.code != "mesh_not_loaded":
                raise
            result.update(mesh_loaded=False, geometry_and_materials_verified=False)
            try:
                result["registry_asset"] = await self.connections.request(target, "asset_info", {"asset_path": asset_path})
            except BridgeError as registry_error:
                if registry_error.code != "asset_not_found":
                    raise
                result["registry_asset"] = None
            result["limitation"] = "Mesh not loaded; registry evidence does not prove absence from disk or asset contents."
            return result
        result.update(mesh_loaded=True, native_mesh=mesh, geometry_and_materials_verified=False)
        exports = [e["evidence"] for e in record["events"] if e["stage"] == "export" and e["outcome"] == "completed"]
        if not exports and record["plan"].get("workflow_kind") == "retained_export_recovery":
            exports = [record["plan"]["retained_export"]]
        if exports:
            export = exports[-1]
            manifest = self.manifest(export, request, recorded_context, export["transfer_id"], exported=True)
            try:
                result["checks"] = verify_import(manifest, {**mesh, "state": "imported"})
                result["geometry_and_materials_verified"] = True
            except WorkflowError as error:
                result["verification_error"] = error.code
        result["limitation"] = "Current loaded mesh only; actor placement and saved disk contents require separate verification."
        return result

    async def apply(self, operation_id, confirmation):
        if operation_id != confirmation:
            raise WorkflowError("confirmation_required")
        plan = self.previews.pop(operation_id, None)
        if plan is None or plan["expires"] <= time.monotonic():
            raise WorkflowError("preview_not_found")
        request = plan["request"]
        source = self.session("blender", request.source_session_id)
        target = self.session("unreal", request.target_session_id)
        if self.binding(source) != plan["source_binding"] or self.binding(target) != plan["target_binding"] or await self.target_context(target) != plan["context"]:
            raise WorkflowError("stale_preview")
        record = self.journal.create(operation_id, {"request": request.model_dump(),
            "target": plan["context"], "export_preview_id": plan["export_preview_id"]},
            stages=STAGES if request.place else STAGES[:-1])
        self.active.add(operation_id)
        imported = None

        def receipt(stage, outcome, evidence=None):
            nonlocal record
            record = self.journal.transition(operation_id, record["revision"], stage, outcome, evidence)

        async def check_target():
            current = self.session("unreal", request.target_session_id)
            if self.binding(current) != plan["target_binding"] or await self.target_context(current) != plan["context"]:
                raise WorkflowError("stale_target")

        try:
            receipt("export", "started")
            export = await self.connections.request(source, "export_apply", {
                "preview_id": plan["export_preview_id"], "confirmation": plan["export_preview_id"]})
            if export.get("status") != "exported" or export.get("transfer_id") != plan["export_preview_id"]:
                raise WorkflowError("export_not_completed")
            manifest = self.manifest(export, request, plan["context"], plan["export_preview_id"], exported=True)
            before = plan["manifest"].model_dump(exclude={"artifact_sha256", "artifact_bytes"})
            if manifest.model_dump(exclude={"artifact_sha256", "artifact_bytes"}) != before:
                raise WorkflowError("source_changed")
            receipt("export", "completed", export)
            receipt("staging", "started")
            await check_target()
            roots = [root for root in self.connections.roots if (root / (source.session_id + ".json")).is_file()]
            if not roots:
                raise WorkflowError("source_staging_unavailable")
            artifact_root = roots[0] / "transfers" / source.session_id / manifest.transfer_id
            recipe = stage_unreal_artifact(artifact_root, manifest, save=request.save_assets, transfer_materials=True)
            receipt("staging", "completed", {"recipe": recipe, "recoverable_export_retained": True})
            receipt("import", "started")
            await check_target()
            preview = await self.connections.request(target, "mesh_import_preview", {"recipe": recipe})
            imported = await self.connections.request(target, "mesh_import_apply", {
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            if imported.get("state") != "imported":
                state = imported.get("state")
                receipt("import", state if state in {"partial", "rolled_back", "outcome_unknown"} else "outcome_unknown", imported)
                return {"operation_id": operation_id, "state": record["state"], "receipt": record}
            receipt("import", "completed", imported)
            receipt("verification", "started")
            checks = verify_import(manifest, imported)
            if request.save_assets and (imported.get("saved") is not True or any(m.get("saved") is not True for m in imported.get("materials", []))):
                raise WorkflowError("save_verification_failed")
            receipt("verification", "completed", checks)
            if request.place:
                receipt("placement", "started")
                await check_target()
                actor_recipe = {"operations": [{"op": "spawn", "class_path": "/Script/Engine.StaticMeshActor",
                    "mesh_path": imported["asset_path"], "label": "ForgeTransfer_" + operation_id,
                    "location": request.location, "rotation": request.rotation, "scale": request.scale}]}
                preview = await self.connections.request(target, "actor_preview", {"recipe": actor_recipe})
                placed = await self.connections.request(target, "actor_apply", {
                    "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
                if placed.get("state") != "completed" or len(placed.get("actors", [])) != 1:
                    raise WorkflowError("placement_not_completed")
                actor = placed["actors"][0]
                inspected = await self.connections.request(target, "actor_info", {"actor_path": actor["path"]})
                rotation = inspected.get("actor", {}).get("rotation")
                if not isinstance(rotation, list) or len(rotation) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in rotation):
                    raise WorkflowError("placement_verification_failed")
                a, b = _quaternion(rotation), _quaternion(request.rotation)
                if (inspected["actor"] != actor or actor.get("static_mesh") != imported["asset_path"]
                        or not close_vector(actor.get("location"), request.location)
                        or not close_vector(actor.get("scale"), request.scale)
                        or abs(abs(sum(x * y for x, y in zip(a, b))) - 1) > 1e-6
                        or (manifest.materials and actor.get("material_assets") != [m["asset_path"] for m in imported["materials"]])):
                    raise WorkflowError("placement_verification_failed")
                receipt("placement", "completed", {"native_result": placed, "level_saved": False})
            return {"operation_id": operation_id, "state": "completed", "receipt": record}
        except (JournalError, OSError) as error:
            return {"operation_id": operation_id, "state": "outcome_unknown",
                    "diagnostic_code": "receipt_unavailable",
                    "storage_error_code": error.code if isinstance(error, JournalError) else
                        f"os_error_{getattr(error, 'winerror', None) or error.errno or 0}",
                    "automatic_native_replay_allowed": False}
        except (BridgeError, WorkflowError, TransferArtifactError, ValueError, KeyError, TypeError) as error:
            code = getattr(error, "code", "invalid_native_result")
            uncertain = code in {"outcome_unknown", "timeout", "disconnected", "invalid_response"}
            outcome = "outcome_unknown" if uncertain else "partial" if imported is not None else "failed"
            if record["active_stage"] is not None:
                try:
                    receipt(record["active_stage"], outcome, {"diagnostic_code": code})
                except (JournalError, OSError):
                    outcome = "outcome_unknown"
            return {"operation_id": operation_id, "state": outcome, "diagnostic_code": code,
                    "automatic_native_replay_allowed": False}
        finally:
            self.active.discard(operation_id)
