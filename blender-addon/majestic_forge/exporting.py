# SPDX-License-Identifier: MIT
"""Reviewed native static-mesh FBX export; no caller-selected filesystem paths."""

import hashlib
import json
import math
import os
import secrets
import stat
import time
from pathlib import Path

import bpy

from .automation import RecipeError
from .materials import material_info, transfer_surface
from .security import protect_path

MAX_BYTES = 64 * 1024 * 1024
HEADER = b"Kaydara FBX Binary  \x00\x1a\x00"


def generate_face_uvs(mesh):
    """Pack independent planar face islands on an export-only mesh copy."""
    if mesh.uv_layers:
        return
    columns = max(1, math.ceil(math.sqrt(len(mesh.polygons))))
    layer = mesh.uv_layers.new(name="ForgeExportUV")
    for polygon in mesh.polygons:
        # Dominant-normal projection avoids collapsing an axis-aligned box face.
        drop = max(range(3), key=lambda axis: abs(polygon.normal[axis]))
        axes = [axis for axis in range(3) if axis != drop]
        points = [mesh.vertices[mesh.loops[i].vertex_index].co for i in polygon.loop_indices]
        low = [min(point[axis] for point in points) for axis in axes]
        spans = [max(point[axis] for point in points) - lo for axis, lo in zip(axes, low)]
        if any(span <= 1e-12 for span in spans):
            raise RecipeError("invalid_geometry", "Cannot generate UVs for a collapsed face.")
        cell = (polygon.index % columns, polygon.index // columns)
        for index, point in zip(polygon.loop_indices, points):
            layer.data[index].uv = [
                (cell[component] + 0.05 + 0.9 * (point[axis] - low[component]) / spans[component]) / columns
                for component, axis in enumerate(axes)
            ]
    mesh.calc_loop_triangles()
    for triangle in mesh.loop_triangles:
        a, b, c = [layer.data[index].uv for index in triangle.loops]
        area = abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x))
        if area <= 1e-12:
            raise RecipeError("invalid_geometry", "Generated UVs contain a collapsed triangle.")


def _snapshot(name):
    # Scripted transform edits may leave matrix_world unevaluated until Blender's
    # next event-loop update. Fingerprint the current evaluated object state.
    bpy.context.view_layer.update()
    if not isinstance(name, str) or not 1 <= len(name) <= 128:
        raise RecipeError("invalid_arguments", "Expected an exact mesh object name.")
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != "MESH" or obj not in list(bpy.context.view_layer.objects):
        raise RecipeError("object_not_found", "Mesh must be in the active scene and view layer.")
    if bpy.context.mode != "OBJECT":
        raise RecipeError("unsupported_context", "Static mesh export requires Object mode.")
    if (
        obj.parent
        or obj.modifiers
        or obj.constraints
        or obj.data.shape_keys
        or obj.animation_data
        or obj.data.animation_data
    ):
        raise RecipeError(
            "unsupported_source",
            "This export stage requires a static unparented mesh without modifiers, constraints, shape keys or animation.",
        )
    mesh = obj.data
    mesh.calc_loop_triangles()
    if not 3 <= len(mesh.vertices) <= 100_000 or not 1 <= len(mesh.loop_triangles) <= 200_000:
        raise RecipeError("export_limit", "Mesh exceeds static-transfer geometry limits.")
    if len(obj.material_slots) > 32 or len(mesh.attributes) > 32:
        raise RecipeError("export_limit", "Mesh exceeds material or attribute limits.")
    if any(slot.material is None for slot in obj.material_slots):
        raise RecipeError(
            "unsupported_source", "Empty material slots must be resolved before export."
        )
    vertices = [list(v.co) for v in mesh.vertices]
    if any(not math.isfinite(c) or abs(c) > 1e8 for v in vertices for c in v):
        raise RecipeError("invalid_geometry", "Mesh coordinates must be finite and bounded.")
    attributes = []
    if sum(len(a.data) for a in mesh.attributes) > 2_000_000:
        raise RecipeError("export_limit", "Mesh attribute data exceeds fingerprint limits.")
    for attribute in mesh.attributes:
        values = []
        for item in attribute.data:
            for field in ("value", "vector", "color"):
                if hasattr(item, field):
                    value = getattr(item, field)
                    values.append(value if type(value) in (int, float, bool, str) else list(value))
                    break
            else:
                raise RecipeError("unsupported_source", "Mesh attribute cannot be fingerprinted.")
        attributes.append([attribute.name, attribute.data_type, attribute.domain, values])
    unit = bpy.context.scene.unit_settings
    meters = 1.0 if unit.system == "NONE" else unit.scale_length
    if not math.isfinite(meters) or not 0 < meters <= 1000:
        raise RecipeError("invalid_units", "Scene unit scale is outside transfer limits.")
    bounds_min = [min(v[i] for v in vertices) for i in range(3)]
    bounds_max = [max(v[i] for v in vertices) for i in range(3)]
    if bounds_min == bounds_max:
        raise RecipeError("invalid_geometry", "Mesh bounds have no extent.")
    materials = []
    for slot in obj.material_slots:
        material = slot.material
        info = material_info(material.name)
        if info["truncated"] or any(n["sockets_truncated"] for n in info["nodes"]):
            raise RecipeError("unsupported_source", "Material graph exceeds fingerprint limits.")
        if any(n["type"] in {"ShaderNodeTexImage", "ShaderNodeGroup"} for n in info["nodes"]):
            raise RecipeError(
                "unsupported_source",
                "Texture and group materials require a future texture-transfer stage.",
            )
        info.update(
            roughness=material.roughness,
            metallic=material.metallic,
            specular_intensity=material.specular_intensity,
            transfer_surface=transfer_surface(material),
        )
        materials.append(info)
    state = {
        "scene": bpy.context.scene.as_pointer(),
        "object": obj.as_pointer(),
        "mesh": mesh.as_pointer(),
        "file": bpy.data.filepath,
        "frame": bpy.context.scene.frame_current,
        "units": [unit.system, unit.scale_length],
        "vertices": vertices,
        "edges": [list(e.vertices) for e in mesh.edges],
        "polygons": [[list(p.vertices), p.material_index, p.use_smooth] for p in mesh.polygons],
        "attributes": attributes,
        "materials": materials,
        "matrix": [list(row) for row in obj.matrix_world],
    }
    try:
        digest = hashlib.sha256(
            json.dumps(state, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
    except (ValueError, TypeError) as error:
        raise RecipeError(
            "unsupported_source", "Source state cannot be safely fingerprinted."
        ) from error
    world_vertices = [list(obj.matrix_world @ v.co) for v in mesh.vertices]
    if any(not math.isfinite(c) or abs(c) > 1e8 for v in world_vertices for c in v):
        raise RecipeError("invalid_geometry", "World-space coordinates exceed transfer limits.")
    return (
        obj,
        digest,
        {
            "source_object": name,
            "source_snapshot_sha256": digest,
            "source_bounds_min": bounds_min,
            "source_bounds_max": bounds_max,
            "vertex_count": len(vertices),
            "triangle_count": len(mesh.loop_triangles),
            "meters_per_source_unit": meters,
            "source_world_matrix": [list(row) for row in obj.matrix_world],
            "source_world_bounds_min": [min(v[i] for v in world_vertices) for i in range(3)],
            "source_world_bounds_max": [max(v[i] for v in world_vertices) for i in range(3)],
            "source_world_vertices": world_vertices[:256],
            "world_vertices_truncated": len(world_vertices) > 256,
            "materials": [
                {"index": i, "name": s.material.name, "surface": transfer_surface(s.material)}
                for i, s in enumerate(obj.material_slots)
            ],
        },
    )


def _private_root(root):
    root = Path(root).absolute()
    for path in (root, *root.parents):
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RecipeError(
                    "unsafe_staging", "Export staging must not use links or reparse points."
                )
    root.mkdir(parents=True, exist_ok=True)
    protect_path(root)
    return root


class StaticMeshExporter:
    def __init__(self, staging_root):
        self.staging_root = Path(staging_root)
        self.previews = {}

    def preview(self, name):
        _, digest, metadata = _snapshot(name)
        now = time.monotonic()
        self.previews = {key: p for key, p in self.previews.items() if p["expires"] > now}
        if len(self.previews) >= 32:
            raise RecipeError("preview_limit", "Too many pending export previews.")
        preview_id = secrets.token_hex(16)
        self.previews[preview_id] = {"name": name, "digest": digest, "expires": now + 300}
        return {
            "preview_id": preview_id,
            "expires_in_seconds": 300,
            "source_session_id": f"blender-{os.getpid()}",
            **metadata,
            "format": "fbx_binary",
            "overwrite": False,
            "export_settings": {
                "axis_forward": "-Y",
                "axis_up": "Z",
                "apply_scale_options": "FBX_SCALE_UNITS",
                "missing_uv_policy": "generate_face_islands_on_export_copy",
                "generates_uvs": not bool(bpy.context.scene.objects[name].data.uv_layers),
            },
            "limitations": [
                "static mesh only",
                "textures are not copied",
                "Unreal import is a separate stage",
            ],
            "changes": [
                "Write a new FBX and export report in private transfer staging; do not save the scene"
            ],
        }

    @staticmethod
    def _record(directory, report):
        temporary = directory / "export-report.tmp"
        with temporary.open("x", encoding="utf-8") as stream:
            protect_path(temporary)
            stream.write(json.dumps(report, allow_nan=False, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(directory / "export-report.json")

    @staticmethod
    def _write_fbx(obj, path):
        if not obj.data.uv_layers:
            temporary_mesh = obj.data.copy()
            temporary_object = None
            try:
                generate_face_uvs(temporary_mesh)
                temporary_object = obj.copy()
                temporary_object.data = temporary_mesh
                bpy.context.scene.collection.objects.link(temporary_object)
                return StaticMeshExporter._export_object(temporary_object, path)
            finally:
                if temporary_object is not None:
                    bpy.data.objects.remove(temporary_object, do_unlink=True)
                bpy.data.meshes.remove(temporary_mesh)
        return StaticMeshExporter._export_object(obj, path)

    @staticmethod
    def _export_object(obj, path):
        with bpy.context.temp_override(
            selected_objects=[obj], selected_editable_objects=[obj], active_object=obj, object=obj
        ):
            return bpy.ops.export_scene.fbx(
                filepath=str(path),
                check_existing=False,
                use_selection=True,
                object_types={"MESH"},
                use_mesh_modifiers=False,
                mesh_smooth_type="FACE",
                bake_anim=False,
                add_leaf_bones=False,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options="FBX_SCALE_UNITS",
                axis_forward="-Y",
                axis_up="Z",
                bake_space_transform=False,
                path_mode="STRIP",
                embed_textures=False,
            )

    def apply(self, preview_id, confirmation):
        if not isinstance(preview_id, str) or confirmation != preview_id:
            raise RecipeError(
                "confirmation_required", "Confirmation must equal the reviewed export preview ID."
            )
        plan = self.previews.pop(preview_id, None)
        if plan is None or plan["expires"] <= time.monotonic():
            raise RecipeError("preview_not_found", "Export preview expired or was consumed.")
        obj, digest, metadata = _snapshot(plan["name"])
        if digest != plan["digest"]:
            raise RecipeError("stale_preview", "Source state changed after export preview.")
        try:
            root = _private_root(self.staging_root)
            directory = root / preview_id
            directory.mkdir(exist_ok=False)
            protect_path(directory)
        except FileExistsError as error:
            raise RecipeError(
                "destination_exists", "Transfer staging already exists; no files were overwritten."
            ) from error
        except OSError as error:
            raise RecipeError(
                "staging_unavailable", "Private transfer staging is unavailable."
            ) from error
        path = directory / "mesh.fbx"
        report = {
            "transfer_id": preview_id,
            "source_session_id": f"blender-{os.getpid()}",
            **metadata,
            "artifact_name": path.name,
            "format": "fbx_binary",
            "status": "export_started",
            "saved_scene": False,
            "overwrite": False,
        }
        try:
            self._record(directory, report)
        except OSError as error:
            raise RecipeError(
                "report_failed",
                "Export did not start because its recovery record could not be written.",
            ) from error
        try:
            if self._write_fbx(obj, path) != {"FINISHED"}:
                raise RecipeError("export_failed", "Native FBX exporter did not finish.")
            protect_path(path)
            if not 23 <= path.stat().st_size <= MAX_BYTES:
                raise RecipeError("export_limit", "Exported artifact exceeds size limits.")
            data = path.read_bytes()
            if not data.startswith(HEADER):
                raise RecipeError("export_failed", "Native exporter did not produce binary FBX.")
            if _snapshot(plan["name"])[1] != digest:
                raise RecipeError(
                    "source_changed",
                    "Source changed during native export; inspect before proceeding.",
                )
            report.update(
                status="exported",
                artifact_bytes=len(data),
                artifact_sha256=hashlib.sha256(data).hexdigest(),
            )
        except Exception as error:
            report.update(
                status="export_failed", error_code=getattr(error, "code", "native_export_failed")
            )
            raise RecipeError(
                "export_failed", f"Native export failed; retained staging record {preview_id}."
            ) from error
        finally:
            try:
                self._record(directory, report)
            except OSError as error:
                raise RecipeError(
                    "outcome_unknown",
                    f"Export recovery record could not be updated; inspect staging {preview_id} before retrying.",
                ) from error
        return report
