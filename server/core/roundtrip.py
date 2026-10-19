# SPDX-License-Identifier: MIT
"""Reviewed Unreal-to-Blender FBX/OBJ handoff; retained receipts, no auto-replacement."""

import hashlib
import math
import re
import time
import uuid
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator

from server.core.connections import BridgeError
from server.core.security import protect_path
from server.core.transfer import FBX_BINARY_HEADER, MAX_ARTIFACT_BYTES, TransferModel, _reject_links
from server.core.workflow_journal import STAGES, JournalError
from server.core.workflows import WorkflowError


class SendToBlenderRequest(TransferModel):
    source_session_id: Annotated[str, Field(pattern=r"^unreal-[1-9][0-9]{0,9}$")]
    target_session_id: Annotated[str, Field(pattern=r"^blender-[1-9][0-9]{0,9}$")]
    source_asset_path: Annotated[str, Field(pattern=r"^/(?:Game|JasperPrism|Engine)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$", max_length=240)]
    # Blank means keep the source Unreal static mesh asset's object name.
    target_object: Annotated[str, Field(pattern=r"^[^\x00-\x1f\x7f]{0,128}$")] = ""
    format: Literal["fbx", "obj"] = "fbx"

    @field_validator("target_object")
    @classmethod
    def object_name_is_not_a_path(cls, value):
        if "/" in value or "\\" in value:
            raise ValueError("Blender object names cannot contain path separators")
        return value


class CompareMeshBindingRequest(TransferModel):
    source_session_id: Annotated[str, Field(pattern=r"^blender-[1-9][0-9]{0,9}$")]
    target_session_id: Annotated[str, Field(pattern=r"^unreal-[1-9][0-9]{0,9}$")]
    source_object: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")]
    target_asset_path: Annotated[str, Field(
        pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$",
        max_length=240,
    )]


def stage_fbx(source, destination, size, digest):
    """Never accept a caller-selected path; paths are derived from registrations/IDs."""
    if type(size) is not int or not 23 <= size <= MAX_ARTIFACT_BYTES:
        raise WorkflowError("invalid_artifact")
    for root in (source.parent, destination.parent):
        for path in (root, *root.parents):
            if path.exists() or path.is_symlink():
                _reject_links(path)
    _reject_links(source)
    if source.stat().st_size != size:
        raise WorkflowError("artifact_changed")
    with source.open("rb") as stream:
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) != size or not data.startswith(FBX_BINARY_HEADER) or hashlib.sha256(data).hexdigest() != digest:
        raise WorkflowError("artifact_changed")
    destination.parent.mkdir(parents=True, exist_ok=False)
    protect_path(destination.parent)
    with destination.open("xb") as stream:
        protect_path(destination)
        stream.write(data)
    return {"artifact_bytes": size, "artifact_sha256": digest}


def validate_obj(data, expected_triangles):
    """Accept only the bounded, triangle-only OBJ profile emitted by UE's native exporter."""
    if not data.startswith(b"# UnrealEd OBJ exporter") or b"\0" in data:
        raise WorkflowError("invalid_obj")
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as error:
        raise WorkflowError("invalid_obj") from error
    vertices = uvs = faces = 0
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] == "#":
            continue
        kind = fields[0]
        if kind == "v":
            if len(fields) != 4:
                raise WorkflowError("invalid_obj")
            values = fields[1:]
            vertices += 1
            if vertices > 600_000:
                raise WorkflowError("artifact_limit")
        elif kind == "vt":
            if len(fields) != 3:
                raise WorkflowError("invalid_obj")
            values = fields[1:]
            uvs += 1
            if uvs > 600_000:
                raise WorkflowError("artifact_limit")
        elif kind == "f":
            if len(fields) != 4:
                raise WorkflowError("invalid_obj")
            faces += 1
            if faces > 200_000:
                raise WorkflowError("artifact_limit")
            for reference in fields[1:]:
                parts = reference.split("/")
                if (len(parts) != 2 or not all(part.isascii() and part.isdecimal() and len(part) <= 6 for part in parts)
                        or int(parts[0]) < 1 or int(parts[0]) != int(parts[1]) or int(parts[0]) > vertices
                        or int(parts[1]) > uvs):
                    raise WorkflowError("invalid_obj")
        elif kind == "g" and len(fields) <= 2:
            continue
        elif kind == "s" and len(fields) == 2 and fields[1].isascii() and fields[1].isdecimal():
            continue
        else:
            # No mtllib/usemtl means no caller-controlled sidecar paths or material files.
            raise WorkflowError("unsupported_obj_record")
        if kind in {"v", "vt"}:
            try:
                numbers = [float(value) for value in values]
            except ValueError as error:
                raise WorkflowError("invalid_obj") from error
            if any(not math.isfinite(number) or abs(number) > 1_000_000_000 for number in numbers):
                raise WorkflowError("invalid_obj")
    if faces != expected_triangles or vertices != faces * 3 or uvs != faces * 3:
        raise WorkflowError("obj_geometry_mismatch")


def stage_mesh(source, destination, size, digest, format, expected_triangles):
    if format == "fbx":
        return stage_fbx(source, destination, size, digest)
    if format != "obj" or type(size) is not int or not 23 <= size <= MAX_ARTIFACT_BYTES:
        raise WorkflowError("invalid_artifact")
    for root in (source.parent, destination.parent):
        for path in (root, *root.parents):
            if path.exists() or path.is_symlink():
                _reject_links(path)
    _reject_links(source)
    if source.stat().st_size != size:
        raise WorkflowError("artifact_changed")
    with source.open("rb") as stream:
        data = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise WorkflowError("artifact_changed")
    validate_obj(data, expected_triangles)
    destination.parent.mkdir(parents=True, exist_ok=False)
    protect_path(destination.parent)
    with destination.open("xb") as stream:
        protect_path(destination)
        stream.write(data)
    return {"artifact_bytes": size, "artifact_sha256": digest}


class RoundtripCoordinator:
    def __init__(self, transfers):
        self.transfers = transfers
        self.previews = {}

    def registration_root(self, session):
        # Unreal and Blender use one engine-wide session directory by default.
        # ConnectionManager retains both configured app roots, which can point
        # to that same folder; count unique physical roots, not list entries.
        roots = set()
        for root in self.transfers.connections.roots:
            try:
                resolved = root.resolve(strict=True)
                if (resolved / (session.session_id + ".json")).is_file():
                    roots.add(resolved)
            except OSError:
                continue
        if len(roots) != 1:
            raise WorkflowError("session_registration_unavailable")
        return next(iter(roots))

    async def context(self, source, target):
        c = self.transfers.connections
        health = await c.request(source, "health")
        other = await c.request(target, "health")
        if "mesh_export_preview" not in health.get("capabilities", []) or "import_preview" not in other.get("capabilities", []):
            raise WorkflowError("adapter_upgrade_required")
        return {"unreal": await self.transfers.target_context(source),
                "blender": await c.request(target, "scene_info")}

    async def compare_binding(self, request: CompareMeshBindingRequest):
        """Compare revisions on both native sides without creating an apply preview."""
        t = self.transfers
        source = t.session("blender", request.source_session_id)
        target = t.session("unreal", request.target_session_id)
        blender_health = await t.connections.request(source, "health")
        unreal_health = await t.connections.request(target, "health")
        if ("binding_info" not in blender_health.get("capabilities", [])
                or "mesh_binding_info" not in unreal_health.get("capabilities", [])):
            raise WorkflowError("adapter_upgrade_required")
        blender = await t.connections.request(source, "binding_info", {"name": request.source_object})
        unreal = await t.connections.request(target, "mesh_binding_info", {"asset_path": request.target_asset_path})
        digest_pattern = re.compile(r"^[0-9a-f]{64}$")
        id_pattern = re.compile(r"^[0-9a-f]{32}$")
        binding_id = blender.get("binding_id")
        if binding_id is None or unreal.get("binding_id") is None:
            state = "unbound"
        elif not isinstance(binding_id, str) or not id_pattern.fullmatch(binding_id) or unreal.get("binding_id") != binding_id:
            state = "binding_mismatch"
        else:
            blender_revision = blender.get("source_revision_sha256")
            unreal_revision = unreal.get("source_snapshot_sha256")
            target_revision = unreal.get("target_revision_sha256")
            blender_baseline = blender.get("baseline_revision_sha256") or unreal.get("source_revision_sha256")
            if not all(isinstance(value, str) and digest_pattern.fullmatch(value)
                       for value in (blender_revision, unreal_revision, target_revision, blender_baseline)):
                state = "baseline_unavailable"
            else:
                blender_changed = blender_revision != blender_baseline
                unreal_changed = unreal_revision != target_revision
                state = ("both_changed_conflict" if blender_changed and unreal_changed else
                    "blender_changed" if blender_changed else "unreal_changed" if unreal_changed else "synchronized")
        return {"state": state, "binding_id": binding_id if isinstance(binding_id, str) else None,
            "source_session_id": source.session_id, "target_session_id": target.session_id,
            "source_object": blender.get("name"), "target_asset_path": unreal.get("asset_path"),
            "blender": blender, "unreal": unreal, "mutated": False, "saved": False,
            "replacement_authorized": False}

    async def preview(self, request):
        source = self.transfers.session("unreal", request.source_session_id)
        target = self.transfers.session("blender", request.target_session_id)
        context = await self.context(source, target)
        if not request.target_object:
            source_object_name = request.source_asset_path.rsplit(".", 1)[-1]
            if not source_object_name or len(source_object_name) > 128:
                raise WorkflowError("invalid_source_asset_name")
            request = request.model_copy(update={"target_object": source_object_name})
        export = await self.transfers.connections.request(source, "mesh_export_preview", {
            "asset_path": request.source_asset_path, "format": request.format})
        if (not isinstance(export.get("preview_id"), str) or not re.fullmatch(r"[0-9a-f]{32}", export["preview_id"])
                or not isinstance(export.get("source_snapshot_sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", export["source_snapshot_sha256"])
                or type(export.get("triangle_count")) is not int or not 1 <= export["triangle_count"] <= 200_000
                or type(export.get("vertex_count")) is not int or not 3 <= export["vertex_count"] <= 100_000):
            raise WorkflowError("invalid_native_result")
        if context["blender"].get("mode") != "OBJECT":
            raise WorkflowError("invalid_context")
        if any(o.get("name") == request.target_object for o in context["blender"].get("objects", [])):
            raise WorkflowError("destination_exists")
        now = time.monotonic()
        self.previews = {k: p for k, p in self.previews.items() if p["expires"] > now}
        if len(self.previews) >= 32:
            raise WorkflowError("preview_limit")
        operation = uuid.uuid4().hex
        binding_id = export.get("binding_id")
        if not isinstance(binding_id, str) or not re.fullmatch(r"[0-9a-f]{32}", binding_id):
            binding_id = hashlib.sha256((context["unreal"]["project_file"].casefold() + "|" + request.source_asset_path.casefold()).encode("utf-8")).hexdigest()[:32]
        self.previews[operation] = {"request": request, "context": context, "export": export,
            "binding_id": binding_id,
            "source_binding": self.transfers.binding(source), "target_binding": self.transfers.binding(target), "expires": now + 300}
        limitations = ["static mesh LOD0 only", "Unreal actor transforms are not exported",
            "Blender file and Unreal level remain unsaved", "manual handoff; no live synchronization"]
        if request.format == "obj":
            limitations.extend(["OBJ transfers triangulated geometry and UV0 only; normals and materials are omitted",
                "OBJ imports convert Unreal centimeters and X/Y/Z axes into Blender scene units"])
        else:
            limitations.append("Unreal shaders are not portable; Blender uses editable constant material placeholders")
        return {"preview_id": operation, "operation_id": operation, "binding_id": binding_id,
            "changes": request.model_dump(),
            "source": export, "target": context, "expires_in_seconds": 300,
            "format": "fbx_binary" if request.format == "fbx" else "obj",
            "overwrite": False, "saves_blend": False, "saves_unreal": False,
            "limitations": limitations}

    async def apply(self, operation, confirmation):
        if confirmation != operation:
            raise WorkflowError("confirmation_required")
        plan = self.previews.pop(operation, None)
        if plan is None or plan["expires"] <= time.monotonic():
            raise WorkflowError("preview_not_found")
        t = self.transfers
        r = plan["request"]
        source, target = t.session("unreal", r.source_session_id), t.session("blender", r.target_session_id)
        if t.binding(source) != plan["source_binding"] or t.binding(target) != plan["target_binding"] or await self.context(source, target) != plan["context"]:
            raise WorkflowError("stale_preview")
        record = t.journal.create(operation, {"workflow_kind": "send_to_blender", "request": r.model_dump(), "context": plan["context"]}, stages=STAGES[:-1])
        t.active.add(operation)
        imported = None

        def receipt(stage, outcome, evidence=None):
            nonlocal record
            record = t.journal.transition(operation, record["revision"], stage, outcome, evidence)

        try:
            receipt("export", "started")
            id_ = plan["export"]["preview_id"]
            export = await t.connections.request(source, "mesh_export_apply", {"preview_id": id_, "confirmation": id_})
            if (export.get("status") != "exported" or export.get("transfer_id") != id_
                    or export.get("format") != r.format or export.get("artifact_name") != f"mesh.{r.format}"
                    or export.get("source_snapshot_sha256") != plan["export"]["source_snapshot_sha256"]):
                raise WorkflowError("export_verification_failed")
            receipt("export", "completed", export)
            receipt("staging", "started")
            extension = r.format
            src = Path(plan["context"]["unreal"]["project_file"]).parent / "Saved/ForgeExports" / id_ / f"mesh.{extension}"
            dest = self.registration_root(target) / "transfers" / target.session_id / "incoming" / id_ / f"mesh.{extension}"
            integrity = stage_mesh(src, dest, export["artifact_bytes"], export["artifact_sha256"],
                r.format, export["triangle_count"])
            receipt("staging", "completed", integrity)
            receipt("import", "started")
            current_source = t.session("unreal", r.source_session_id)
            current_target = t.session("blender", r.target_session_id)
            if t.binding(current_source) != plan["source_binding"] or t.binding(current_target) != plan["target_binding"] or await self.context(current_source, current_target) != plan["context"]:
                raise WorkflowError("stale_target")
            args = {"transfer_id": id_, **integrity, "object_name": r.target_object,
                "format": r.format, "binding_id": plan["binding_id"]}
            preview = await t.connections.request(target, "import_preview", args)
            imported = await t.connections.request(target, "import_apply", {"preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            if imported.get("state") != "imported":
                raise WorkflowError("import_not_completed")
            if imported.get("binding_id") != plan["binding_id"]:
                raise WorkflowError("binding_verification_failed")
            receipt("import", "completed", imported)
            receipt("verification", "started")
            native = await t.connections.request(target, "object_info", {"name": r.target_object})
            if native.get("name") != r.target_object or native.get("type") != "MESH" or imported.get("triangle_count") != export["triangle_count"]:
                raise WorkflowError("import_verification_failed")
            receipt("verification", "completed", {"object": r.target_object, "triangle_count_verified": True,
                "material_equivalence_verified": False, "blend_saved": False})
            return {"operation_id": operation, "state": "completed", "receipt": record}
        except (BridgeError, WorkflowError, JournalError, OSError, ValueError, KeyError, TypeError) as error:
            code = getattr(error, "code", "invalid_native_result")
            outcome = "outcome_unknown" if isinstance(error, (JournalError, OSError)) or code in {"outcome_unknown", "timeout", "disconnected", "invalid_response"} else "partial" if imported is not None else "failed"
            try:
                if record["active_stage"] is not None:
                    receipt(record["active_stage"], outcome, {"diagnostic_code": code})
            except (JournalError, OSError):
                outcome = "outcome_unknown"
            return {"operation_id": operation, "state": outcome, "diagnostic_code": code, "automatic_native_replay_allowed": False}
        finally:
            t.active.discard(operation)
