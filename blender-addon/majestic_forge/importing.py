# SPDX-License-Identifier: MIT
"""Bounded private FBX/OBJ importer; new object only, main thread, no scene save."""

import hashlib
import json
import math
import re
import time
import uuid
from pathlib import Path

import bmesh
import bpy

from .automation import RecipeError
from .exporting import _snapshot


class StaticMeshImporter:
    def __init__(self, root):
        self.root = Path(root)
        self.previews = {}

    def context(self):
        if bpy.context.mode != "OBJECT":
            raise RecipeError("invalid_context", "Switch to Object mode before importing.")
        return hashlib.sha256(json.dumps({"scene": bpy.context.scene.as_pointer(), "file": bpy.data.filepath,
            "units": [bpy.context.scene.unit_settings.system, bpy.context.scene.unit_settings.scale_length],
            "objects": [(o.name, o.as_pointer(), [list(r) for r in o.matrix_world]) for o in bpy.data.objects]}, sort_keys=True).encode()).hexdigest()

    def artifact(self, args):
        required = {"transfer_id", "artifact_bytes", "artifact_sha256", "object_name", "binding_id"}
        if set(args) - (required | {"format"}) or not required <= set(args) or not isinstance(args["transfer_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", args["transfer_id"]) or not isinstance(args["binding_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", args["binding_id"]):
            raise RecipeError("invalid_arguments", "Expected a generated transfer ID and checksum.")
        format_ = args.get("format", "fbx")
        if not isinstance(format_, str) or format_ not in {"fbx", "obj"}:
            raise RecipeError("unsupported_format", "Choose FBX or OBJ.")
        if not isinstance(args["object_name"], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", args["object_name"]):
            raise RecipeError("invalid_arguments", "Expected a bounded destination object name.")
        if type(args["artifact_bytes"]) is not int or not 23 <= args["artifact_bytes"] <= 64*1024*1024 or not isinstance(args["artifact_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", args["artifact_sha256"]):
            raise RecipeError("invalid_arguments", "Invalid artifact integrity metadata.")
        # Validate ancestors without creating anything during preview.
        path = self.root / "incoming" / args["transfer_id"] / f"mesh.{format_}"
        import stat
        for ancestor in (path, *path.parents):
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise RecipeError("unsafe_staging", "Staging links are not allowed.")
        if path.stat().st_size != args["artifact_bytes"]:
            raise RecipeError("artifact_changed", "Artifact size changed.")
        with path.open("rb") as stream:
            data = stream.read(64*1024*1024+1)
        if (len(data) != args["artifact_bytes"] or hashlib.sha256(data).hexdigest() != args["artifact_sha256"]
                or (format_ == "fbx" and not data.startswith(b"Kaydara FBX Binary  \x00\x1a\x00"))
                or (format_ == "obj" and not self.validate_obj(data))):
            raise RecipeError("artifact_changed", "Artifact checksum changed.")
        return path

    @staticmethod
    def validate_obj(data):
        if not data.startswith(b"# UnrealEd OBJ exporter") or b"\0" in data:
            return False
        try:
            text = data.decode("ascii")
        except UnicodeDecodeError:
            return False
        vertices = uvs = faces = 0
        for line in text.splitlines():
            fields = line.split()
            if not fields or fields[0] == "#":
                continue
            kind = fields[0]
            if kind in {"v", "vt"}:
                count = 3 if kind == "v" else 2
                if len(fields) != count + 1:
                    return False
                try:
                    values = [float(value) for value in fields[1:]]
                except ValueError:
                    return False
                if any(not math.isfinite(value) or abs(value) > 1_000_000_000 for value in values):
                    return False
                if kind == "v":
                    vertices += 1
                else:
                    uvs += 1
                if vertices > 600_000 or uvs > 600_000:
                    return False
            elif kind == "f":
                if len(fields) != 4:
                    return False
                faces += 1
                if faces > 200_000:
                    return False
                for reference in fields[1:]:
                    parts = reference.split("/")
                    if (len(parts) != 2 or not all(part.isascii() and part.isdecimal() and len(part) <= 6 for part in parts)
                            or int(parts[0]) < 1 or int(parts[0]) != int(parts[1]) or int(parts[0]) > vertices
                            or int(parts[1]) > uvs):
                        return False
            elif kind == "g" and len(fields) <= 2:
                continue
            elif kind == "s" and len(fields) == 2 and fields[1].isascii() and fields[1].isdecimal():
                continue
            else:
                # Never follow OBJ/MTL sidecars from an imported artifact.
                return False
        return faces > 0 and vertices == faces * 3 and uvs == faces * 3

    def preview(self, args):
        path = self.artifact(args)
        state = self.context()
        if args["object_name"] in bpy.data.objects:
            raise RecipeError("destination_exists", "Choose a new Blender object name.")
        now = time.monotonic()
        self.previews = {k: v for k, v in self.previews.items() if v["expires"] > now}
        if len(self.previews) >= 32:
            raise RecipeError("preview_limit", "Too many pending previews.")
        id_ = uuid.uuid4().hex
        self.previews[id_] = {"args": dict(args), "snapshot": state, "expires": now+300}
        return {"preview_id": id_, "object_name": args["object_name"], "artifact_name": path.name,
                "format": args.get("format", "fbx"), "overwrite": False, "saves_blend": False}

    def apply(self, id_, confirmation):
        if id_ != confirmation:
            raise RecipeError("confirmation_required", "Review and confirm the preview.")
        plan = self.previews.pop(id_, None)
        if not plan or plan["expires"] <= time.monotonic():
            raise RecipeError("preview_not_found", "Preview expired or was consumed.")
        args = plan["args"]
        if self.context() != plan["snapshot"] or args["object_name"] in bpy.data.objects:
            raise RecipeError("stale_preview", "Blender scene changed; preview again.")
        path = self.artifact(args)
        before = {kind: set(getattr(bpy.data, kind)) for kind in ("objects", "meshes", "materials", "images", "actions", "armatures", "collections")}
        selected = list(bpy.context.selected_objects)
        active = bpy.context.view_layer.objects.active
        received = None
        try:
            format_ = args.get("format", "fbx")
            if format_ == "fbx":
                # Native importer uses embedded axis/unit metadata; no texture discovery.
                result = bpy.ops.import_scene.fbx(filepath=str(path), use_image_search=False, use_anim=False)
            else:
                # UE's OBJ exporter writes X=forward, Y=up, Z=right in centimeters.
                # Convert that basis to Blender's -Y-forward/Z-up and centimeters to meters.
                unit = bpy.context.scene.unit_settings
                meters_per_unit = 1.0 if unit.system == "NONE" else unit.scale_length
                if not math.isfinite(meters_per_unit) or not 0 < meters_per_unit <= 1000:
                    raise RecipeError("invalid_units", "Blender scene unit scale is outside transfer limits.")
                result = bpy.ops.wm.obj_import(filepath=str(path), global_scale=0.01 / meters_per_unit,
                    forward_axis="NEGATIVE_X", up_axis="Y", use_split_objects=False,
                    use_split_groups=False, validate_meshes=True)
            created = set(bpy.data.objects)-before["objects"]
            if result != {"FINISHED"} or len(created) != 1:
                raise RecipeError("unsupported_source", "Expected exactly one static mesh in the FBX.")
            obj = next(iter(created))
            if obj.type != "MESH" or obj.parent or obj.modifiers or obj.animation_data or obj.data.shape_keys:
                raise RecipeError("unsupported_source", "Only standalone static geometry is supported.")
            obj.data.calc_loop_triangles()
            mesh = obj.data
            vertex_limit = 600000 if format_ == "obj" else 100000
            if not 3 <= len(mesh.vertices) <= vertex_limit or not 1 <= len(mesh.loop_triangles) <= 200000 or len(obj.material_slots) > 32 or any(not math.isfinite(c) for v in mesh.vertices for c in v.co):
                raise RecipeError("import_limit", "Imported geometry exceeds limits.")
            if format_ == "obj":
                bm = bmesh.new()
                try:
                    bm.from_mesh(mesh)
                    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-8 / meters_per_unit)
                    bm.to_mesh(mesh)
                    mesh.update()
                finally:
                    bm.free()
                if len(mesh.vertices) > 100000:
                    raise RecipeError("import_limit", "Welded OBJ geometry exceeds 100,000 vertices.")
                mesh.calc_loop_triangles()
            # Replace only importer-created surface data with explicit editable placeholders.
            names = [s.name for s in obj.material_slots]
            if format_ == "obj" and not names:
                names = ["ForgeOBJ_Material"]
            mesh.materials.clear()
            for name in names:
                material = bpy.data.materials.new(name + "_ForgeEditable")
                material.use_nodes = True
                mesh.materials.append(material)
            # Bake native coordinate conversion into this new mesh, never a source object.
            mesh.transform(obj.matrix_world)
            obj.matrix_world.identity()
            obj.name = args["object_name"]
            for kind in ("materials", "images"):
                data = getattr(bpy.data, kind)
                for block in list(set(data)-before[kind]):
                    if block.users == 0:
                        data.remove(block)
            obj["forge_source_transfer"] = args["transfer_id"]
            obj["forge_binding_id"] = args["binding_id"]
            obj["forge_source_format"] = format_.upper()
            _, _, received_state = _snapshot(obj.name)
            obj["forge_target_revision"] = received_state["source_snapshot_sha256"]
            received = obj
            return {"state": "imported", "name": obj.name, "format": format_,
                "binding_id": args["binding_id"],
                "target_revision_sha256": obj["forge_target_revision"],
                "vertex_count": len(mesh.vertices),
                "triangle_count": len(mesh.loop_triangles), "saves_blend": False,
                "material_equivalence": False}
        except Exception as error:
            for kind in before:
                data = getattr(bpy.data, kind)
                for block in list(set(data)-before[kind]):
                    data.remove(block, do_unlink=True)
            if isinstance(error, RecipeError):
                raise
            raise RecipeError("import_failed", "Native import failed; new datablocks rolled back.") from error
        finally:
            for obj in bpy.context.selected_objects:
                obj.select_set(False)
            if received is not None:
                received.select_set(True)
                bpy.context.view_layer.objects.active = received
            else:
                for obj in selected:
                    obj.select_set(True)
                bpy.context.view_layer.objects.active = active
