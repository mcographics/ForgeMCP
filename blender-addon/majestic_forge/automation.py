# SPDX-License-Identifier: MIT
"""Original bounded scene recipes, executed by the bridge on Blender's main thread."""

import hashlib
import json
import math
import re
import secrets
import time

import bpy

from .materials import (
    add_existing_graph_nodes,
    construct_graph,
    editable_input,
    graph_validate,
    material_info,
    restore_existing_graph_state,
    validate_existing_graph_edit,
)

MODIFIER_SETTINGS = {
    "SUBSURF": {
        "levels": ("int", 0, 6),
        "render_levels": ("int", 0, 6),
        "subdivision_type": ("enum", ("CATMULL_CLARK", "SIMPLE", "LINEAR")),
    },
    "BEVEL": {
        "width": ("float", 0.0, 100000.0),
        "segments": ("int", 1, 12),
        "limit_method": ("enum", ("NONE", "ANGLE", "WEIGHT", "VGROUP")),
    },
    "SOLIDIFY": {
        "thickness": ("float", -100000.0, 100000.0),
        "offset": ("float", -1.0, 1.0),
        "use_rim": ("bool",),
    },
    "WEIGHTED_NORMAL": {
        "keep_sharp": ("bool",),
        "weight": ("int", 1, 1000),
    },
}
MAX_RECIPE_BYTES = 256 * 1024


def validate_modifier_settings(modifier_type, settings):
    if modifier_type not in MODIFIER_SETTINGS:
        raise RecipeError("command_not_allowed", "This modifier type is not in the reviewed allowlist.")
    if not isinstance(settings, dict) or len(settings) > 8:
        raise RecipeError("invalid_arguments", "Modifier settings must be a bounded object.")
    for key, value in settings.items():
        spec = MODIFIER_SETTINGS[modifier_type].get(key)
        if spec is None:
            raise RecipeError("invalid_arguments", "Modifier setting is not supported for this type.")
        if spec[0] == "bool":
            valid = type(value) is bool
        elif spec[0] == "int":
            valid = type(value) is int and spec[1] <= value <= spec[2]
        elif spec[0] == "float":
            valid = type(value) in (int, float) and math.isfinite(value) and spec[1] <= value <= spec[2]
        else:
            valid = isinstance(value, str) and value in spec[1]
        if not valid:
            raise RecipeError("invalid_arguments", "Modifier setting has an invalid type or value.")


def apply_modifier_settings(modifier, settings):
    for key, value in settings.items():
        setattr(modifier, key, value)
    for key, value in settings.items():
        actual = getattr(modifier, key)
        if type(actual) is float:
            if not math.isclose(actual, float(value), rel_tol=1e-6, abs_tol=1e-7):
                raise RuntimeError("Modifier setting verification failed")
        elif actual != value:
            raise RuntimeError("Modifier setting verification failed")


def validate_topology_edit(obj):
    if obj.type != "MESH" or obj.library or obj.mode == "EDIT":
        raise RecipeError("invalid_context", "Topology edits require a local mesh in Object Mode.")
    mesh = obj.data
    known_attributes = {
        "position", "edge_verts", "corner_vert", "corner_edge", "face_offset",
        "material_index", "sharp_face", "sharp_edge", "crease_edge",
        "bevel_weight_edge", "crease_vert", "bevel_weight_vert",
    }
    has_vertex_weights = any(vertex.groups for vertex in mesh.vertices)
    has_custom_attributes = any(
        attribute.name not in known_attributes and not attribute.name.startswith(".")
        for attribute in mesh.attributes
    )
    if (mesh.shape_keys is not None or len(mesh.uv_layers) or len(mesh.color_attributes)
            or len(mesh.materials) > 1 or has_vertex_weights or has_custom_attributes):
        raise RecipeError(
            "unsupported_mesh_data",
            "Topology replacement requires an unskinned mesh without UVs, color/custom attributes, shape keys, or multiple material slots.",
        )


def replace_mesh_geometry(mesh, vertices, faces):
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    if len(mesh.vertices) != len(vertices) or len(mesh.polygons) != len(faces):
        raise RuntimeError("Mesh geometry did not verify after replacement")


class RecipeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def vector(value, size=3):
    if (
        not isinstance(value, list)
        or len(value) != size
        or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1e8 for x in value)
    ):
        raise RecipeError("invalid_arguments", "Expected a bounded finite vector.")
    return value


def object_info(name):
    obj = bpy.context.scene.objects.get(name)
    if obj is None:
        raise RecipeError("object_not_found", "Object is not in the active scene.")
    return {
        "name": obj.name,
        "type": obj.type,
        "location": list(obj.location),
        "rotation_euler": list(obj.rotation_euler),
        "rotation_mode": obj.rotation_mode,
        "scale": list(obj.scale),
        "collections": [c.name for c in obj.users_collection],
        "materials": [m.name if m else None for m in getattr(obj.data, "materials", [])],
        "modifiers": [
            {
                "name": m.name,
                "type": m.type,
                "show_viewport": m.show_viewport,
                "show_render": m.show_render,
                "settings": {
                    key: getattr(m, key)
                    for key in MODIFIER_SETTINGS.get(m.type, {})
                    if hasattr(m, key) and type(getattr(m, key)) in (bool, int, float, str)
                },
            }
            for m in obj.modifiers
        ],
        "mesh": {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "faces": len(obj.data.polygons),
        }
        if obj.type == "MESH"
        else None,
        "action": obj.animation_data.action.name
        if obj.animation_data and obj.animation_data.action
        else None,
    }


def mesh_geometry_info(name, vertex_start=0, vertex_count=128, face_start=0, face_count=128):
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != "MESH":
        raise RecipeError("mesh_not_found", "A mesh object with this exact name is not in the active scene.")
    if (type(vertex_start) is not int or type(face_start) is not int
            or type(vertex_count) is not int or type(face_count) is not int
            or vertex_start < 0 or face_start < 0 or not 1 <= vertex_count <= 256
            or not 1 <= face_count <= 256):
        raise RecipeError("invalid_arguments", "Mesh geometry pages require nonnegative offsets and counts from 1 to 256.")
    mesh = obj.data
    vertex_end = min(len(mesh.vertices), vertex_start + vertex_count)
    face_end = min(len(mesh.polygons), face_start + face_count)
    return {
        "name": obj.name,
        "mesh_data": mesh.name,
        "vertex_total": len(mesh.vertices),
        "face_total": len(mesh.polygons),
        "vertex_start": vertex_start,
        "vertices": [{"index": i, "position": list(mesh.vertices[i].co)}
                     for i in range(vertex_start, vertex_end)],
        "face_start": face_start,
        "faces": [{"index": i, "vertices": list(mesh.polygons[i].vertices),
                   "material_index": mesh.polygons[i].material_index,
                   "smooth": mesh.polygons[i].use_smooth}
                  for i in range(face_start, face_end)],
        "vertices_truncated": vertex_end < len(mesh.vertices),
        "faces_truncated": face_end < len(mesh.polygons),
    }


def mesh_edge_info(name, edge_start=0, edge_count=128):
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != "MESH":
        raise RecipeError("mesh_not_found", "A mesh object with this exact name is not in the active scene.")
    if type(edge_start) is not int or type(edge_count) is not int or edge_start < 0 or not 1 <= edge_count <= 256:
        raise RecipeError("invalid_arguments", "Mesh edge pages require a nonnegative offset and a count from 1 to 256.")
    mesh = obj.data
    if edge_start > len(mesh.edges):
        raise RecipeError("invalid_arguments", "Mesh edge page offset is beyond the edge count.")
    end = min(len(mesh.edges), edge_start + edge_count)
    return {"name": obj.name, "mesh_data": mesh.name, "edge_total": len(mesh.edges),
        "edge_start": edge_start,
        "edges": [{"index": index, "vertices": list(mesh.edges[index].vertices),
                   "seam": bool(mesh.edges[index].use_seam),
                   "sharp": bool(mesh.edges[index].use_edge_sharp)}
                  for index in range(edge_start, end)],
        "truncated": end < len(mesh.edges)}


def apply_mesh_edge_seams(mesh, changes):
    for change in changes:
        mesh.edges[change["index"]].use_seam = change["seam"]
    mesh.update()
    if any(mesh.edges[item["index"]].use_seam is not item["seam"] for item in changes):
        raise RuntimeError("Mesh seam flag verification failed")


def mesh_uv_info(name, layer_name="", loop_start=0, loop_count=128):
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != "MESH":
        raise RecipeError("mesh_not_found", "A mesh object with this exact name is not in the active scene.")
    if (type(loop_start) is not int or type(loop_count) is not int or loop_start < 0
            or not 1 <= loop_count <= 256):
        raise RecipeError("invalid_arguments", "UV pages require a nonnegative offset and a count from 1 to 256.")
    layers = obj.data.uv_layers
    layer = layers.get(layer_name) if layer_name else layers.active
    if layer is None:
        raise RecipeError("uv_layer_not_found", "The requested UV layer does not exist on this mesh.")
    if loop_start > len(layer.data):
        raise RecipeError("invalid_arguments", "UV page offset is beyond the layer loop count.")
    loop_end = min(len(layer.data), loop_start + loop_count)
    return {
        "name": obj.name,
        "mesh_data": obj.data.name,
        "layer": layer.name,
        "layers": [item.name for item in layers],
        "loop_total": len(layer.data),
        "loop_start": loop_start,
        "loops": [{"index": index, "vertex_index": obj.data.loops[index].vertex_index,
                   "uv": list(layer.data[index].uv)} for index in range(loop_start, loop_end)],
        "truncated": loop_end < len(layer.data),
    }


def apply_uv_coordinates(layer, loop_start, uv_values):
    for index, uv in enumerate(uv_values, loop_start):
        layer.data[index].uv = uv
    for index, uv in enumerate(uv_values, loop_start):
        observed = tuple(layer.data[index].uv)
        if any(not math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-7)
               for actual, expected in zip(observed, uv, strict=True)):
            raise RuntimeError("UV coordinate verification failed")


def create_uv_layer(mesh, name, uv_values):
    layer = mesh.uv_layers.new(name=name, do_init=False)
    if uv_values:
        apply_uv_coordinates(layer, 0, uv_values)
    return layer


def smart_project_uvs(obj, layer_name, angle_limit, island_margin):
    mesh = obj.data
    layer = mesh.uv_layers.get(layer_name) or create_uv_layer(mesh, layer_name, [])
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = list(bpy.context.selected_objects)
    if bpy.context.mode != "OBJECT":
        raise RecipeError("invalid_context", "Smart UV projection requires Object Mode.")
    try:
        for selected in previous_selected:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mesh.uv_layers.active_index = list(mesh.uv_layers).index(layer)
        if not mesh.uv_layers.active or mesh.uv_layers.active.name != layer_name:
            raise RuntimeError("Could not activate the requested UV layer")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        result = bpy.ops.uv.smart_project(
            angle_limit=angle_limit, island_margin=island_margin,
            margin_method="FRACTION", rotate_method="AXIS_ALIGNED_Y",
            correct_aspect=True, scale_to_bounds=True,
        )
        if result != {"FINISHED"}:
            raise RuntimeError("Blender smart UV projection did not finish")
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh.update()
        observed = mesh.uv_layers.get(layer_name)
        if observed is None or len(observed.data) != len(mesh.loops):
            raise RuntimeError("Smart UV projection produced an incomplete UV layer")
        if any(not math.isfinite(float(axis)) or axis < -1e-6 or axis > 1.000001
               for item in observed.data for axis in item.uv):
            raise RuntimeError("Smart UV projection produced coordinates outside 0..1")
        return len(observed.data)
    finally:
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        for selected in previous_selected:
            if selected.name in bpy.context.view_layer.objects:
                selected.select_set(True)
        bpy.context.view_layer.objects.active = (
            previous_active if previous_active and previous_active.name in bpy.context.view_layer.objects else None
        )


def unwrap_uvs(obj, layer_name, method, margin):
    mesh = obj.data
    layer = mesh.uv_layers.get(layer_name) or create_uv_layer(mesh, layer_name, [])
    if not any(edge.use_seam for edge in mesh.edges):
        raise RecipeError("uv_seams_required", "Mark at least one mesh edge as a seam before seam-based unwrap.")
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = list(bpy.context.selected_objects)
    if bpy.context.mode != "OBJECT":
        raise RecipeError("invalid_context", "Seam-based UV unwrap requires Object Mode.")
    try:
        for selected in previous_selected:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mesh.uv_layers.active_index = list(mesh.uv_layers).index(layer)
        if not mesh.uv_layers.active or mesh.uv_layers.active.name != layer_name:
            raise RuntimeError("Could not activate the requested UV layer")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        result = bpy.ops.uv.unwrap(method=method, margin=margin, correct_aspect=True)
        if result != {"FINISHED"}:
            raise RuntimeError("Blender seam-based UV unwrap did not finish")
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh.update()
        observed = mesh.uv_layers.get(layer_name)
        if observed is None or len(observed.data) != len(mesh.loops):
            raise RuntimeError("Seam-based unwrap produced an incomplete UV layer")
        if any(not math.isfinite(float(axis)) or axis < -1e-6 or axis > 1.000001
               for item in observed.data for axis in item.uv):
            raise RuntimeError("Seam-based unwrap produced coordinates outside 0..1")
        return len(observed.data)
    finally:
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        for selected in previous_selected:
            if selected.name in bpy.context.view_layer.objects:
                selected.select_set(True)
        bpy.context.view_layer.objects.active = (
            previous_active if previous_active and previous_active.name in bpy.context.view_layer.objects else None
        )


def pack_uv_islands(obj, layer_name, margin):
    mesh = obj.data
    layer = mesh.uv_layers.get(layer_name)
    if layer is None:
        raise RecipeError("uv_layer_not_found", "UV island packing requires an existing UV layer.")
    if bpy.context.mode != "OBJECT":
        raise RecipeError("invalid_context", "UV island packing requires Object Mode.")
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = list(bpy.context.selected_objects)
    try:
        for selected in previous_selected:
            selected.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mesh.uv_layers.active_index = list(mesh.uv_layers).index(layer)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        result = bpy.ops.uv.pack_islands(rotate=True, margin=margin)
        if result != {"FINISHED"}:
            raise RuntimeError("Blender UV island packing did not finish")
        bpy.ops.object.mode_set(mode="OBJECT")
        mesh.update()
        observed = mesh.uv_layers.get(layer_name)
        if observed is None or len(observed.data) != len(mesh.loops):
            raise RuntimeError("UV island packing produced an incomplete UV layer")
        if any(not math.isfinite(float(axis)) or axis < -1e-6 or axis > 1.000001
               for item in observed.data for axis in item.uv):
            raise RuntimeError("UV island packing produced coordinates outside 0..1")
        return len(observed.data)
    finally:
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for selected in bpy.context.selected_objects:
            selected.select_set(False)
        for selected in previous_selected:
            if selected.name in bpy.context.view_layer.objects:
                selected.select_set(True)
        bpy.context.view_layer.objects.active = (
            previous_active if previous_active and previous_active.name in bpy.context.view_layer.objects else None
        )


def action_curves(action):
    if action is None:
        return []
    curves = list(getattr(action, "fcurves", []))
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                curves.extend(bag.fcurves)
    return [
        [curve.data_path, curve.array_index, [list(p.co) for p in curve.keyframe_points]]
        for curve in curves
    ]


def action_curve_entries(action):
    """Return bounded curve references with Blender 5.2 Action container identity."""
    entries = []
    seen = set()

    def append(curves, layer="", strip_index=-1, slot=""):
        for curve in curves:
            pointer = curve.as_pointer()
            if pointer in seen:
                continue
            seen.add(pointer)
            entries.append((curve, layer, strip_index, slot))
            if len(entries) > 10000:
                raise RecipeError("operation_limit", "Action inspection is limited to 10,000 F-curves.")

    legacy_curves = getattr(action, "fcurves", None)
    if legacy_curves is not None:
        append(legacy_curves)
    for layer in getattr(action, "layers", []):
        for strip_index, strip in enumerate(layer.strips):
            for bag in getattr(strip, "channelbags", []):
                slot = getattr(bag, "slot", None)
                append(bag.fcurves, layer.name, strip_index, slot.identifier if slot else "")
    return entries


def animation_info(name, curve_start=0, curve_count=16, keyframe_start=0, keyframe_count=64):
    obj = bpy.context.scene.objects.get(name)
    if obj is None:
        raise RecipeError("object_not_found", "Object is not in the active scene.")
    bounds = ((curve_start, 0, 10000), (curve_count, 1, 32),
              (keyframe_start, 0, 1000000), (keyframe_count, 1, 128))
    if any(type(value) is not int or not minimum <= value <= maximum
           for value, minimum, maximum in bounds):
        raise RecipeError("invalid_arguments", "Animation pages require bounded integer offsets and counts.")
    animation = obj.animation_data
    action = animation.action if animation else None
    base = {"object": obj.name, "object_type": obj.type,
            "has_animation_data": animation is not None,
            "action": action.name if action else None,
            "action_slot": animation.action_slot.identifier
            if animation and getattr(animation, "action_slot", None) else None}
    if action is None:
        return {**base, "frame_range": None, "curve_total": 0,
                "curve_start": curve_start, "curves": [], "curve_count": 0,
                "truncated": False}
    entries = action_curve_entries(action)
    if curve_start > len(entries):
        raise RecipeError("invalid_arguments", "Curve page offset is beyond the Action curve count.")
    end = min(len(entries), curve_start + curve_count)
    curves = []
    for index in range(curve_start, end):
        curve, layer_name, strip_index, slot_name = entries[index]
        keys = curve.keyframe_points
        key_end = min(len(keys), keyframe_start + keyframe_count)
        keyframes = []
        for key_index in range(keyframe_start, key_end):
            point = keys[key_index]
            frame, value = float(point.co.x), float(point.co.y)
            if not math.isfinite(frame) or not math.isfinite(value):
                raise RecipeError("invalid_animation_data", "Action contains a non-finite keyframe.")
            keyframes.append({"index": key_index, "frame": frame, "value": value,
                              "interpolation": point.interpolation, "type": point.type})
        curves.append({"index": index, "data_path": curve.data_path[:256],
            "array_index": curve.array_index, "group": curve.group.name[:128] if curve.group else None,
            "layer": layer_name, "strip_index": strip_index, "slot": slot_name or None,
            "mute": bool(curve.mute), "extrapolation": curve.extrapolation,
            "keyframe_total": len(keys), "keyframe_start": keyframe_start,
            "keyframes": keyframes, "keyframes_truncated": key_end < len(keys)})
    return {**base, "frame_range": [float(action.frame_range[0]), float(action.frame_range[1])],
            "curve_total": len(entries), "curve_start": curve_start, "curves": curves,
            "curve_count": len(curves), "truncated": end < len(entries)}


def _set_frame(scene, frame):
    scene.frame_set(frame)
    if scene.frame_current != frame:
        raise RecipeError("native_verification_failed", "Native timeline frame differs from preview.")


def fingerprint(operations):
    scene = bpy.context.scene
    touched = {op.get("name") for op in operations} | {
        op.get("source") for op in operations if op.get("op") in {"duplicate_object", "bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"}
    }
    state = {
        "scene": scene.as_pointer(),
        "file": bpy.data.filepath,
        "objects": sorted((o.name, o.as_pointer()) for o in scene.objects),
        "materials": sorted((m.name, m.as_pointer()) for m in bpy.data.materials),
        "collections": sorted((c.name, c.as_pointer()) for c in bpy.data.collections),
        "timing": [
            scene.render.fps,
            scene.render.fps_base,
            scene.frame_start,
            scene.frame_end,
            scene.frame_current,
            scene.frame_subframe,
        ],
        "targets": [],
        "material_targets": [],
        "material_graph_targets": [],
        "bindings": [],
        "ik_setups": [],
        "uv_targets": [],
        "edge_targets": [],
    }
    geometry = {op.get("name") for op in operations if op.get("op") in {"set_vertices", "set_mesh_geometry", "create_uv_layer", "smart_uv_project", "unwrap_uv", "pack_uv_islands", "set_mesh_edge_seams"}} | {
        op.get("source") for op in operations if op.get("op") == "duplicate_object"
    }
    for op in operations:
        if op.get("op") == "create_ik_constraint":
            from .rigging import ik_setup_facts
            state["ik_setups"].append(ik_setup_facts(op))
        if op.get("op") in {"bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"}:
            from .skinning import binding_facts
            state["bindings"].append(binding_facts(op))
        if op.get("op") == "set_material_input":
            info = material_info(op["name"])
            pin = editable_input(op["name"], op["node"], op["socket"], op["value"])
            value = pin.default_value
            info["target_default"] = value if type(value) in (int, float) else list(value)
            state["material_targets"].append(info)
        if op.get("op") == "edit_material_graph":
            validate_existing_graph_edit(op["name"], op.get("shader_nodes", []), op.get("shader_links", []),
                                         op.get("shader_node_edits", []))
            state["material_graph_targets"].append(material_info(op["name"]))
        if op.get("op") in {"set_uv_coordinates", "create_uv_layer", "smart_uv_project", "unwrap_uv", "pack_uv_islands"}:
            obj = scene.objects.get(op["name"])
            layer = obj.data.uv_layers.get(op["uv_layer"]) if obj and obj.type == "MESH" else None
            start = op.get("uv_start", 0)
            end = start + len(op.get("uv_values", []))
            state["uv_targets"].append({
                "object": op["name"], "layer": op["uv_layer"],
                "layers": [item.name for item in obj.data.uv_layers] if obj and obj.type == "MESH" else None,
                "start": start,
                "values": [list(layer.data[index].uv) for index in range(start, end)]
                         if layer and end <= len(layer.data) else None,
                "all_values": [list(item.uv) for item in layer.data]
                              if op.get("op") in {"smart_uv_project", "unwrap_uv", "pack_uv_islands"} and layer else None,
            })
        if op.get("op") in {"set_mesh_edge_seams", "unwrap_uv"}:
            obj = scene.objects.get(op["name"])
            edge_indices = ([item["index"] for item in op["edge_seams"]]
                            if op.get("op") == "set_mesh_edge_seams" else list(range(len(obj.data.edges)) if obj and obj.type == "MESH" else []))
            state["edge_targets"].append({
                "object": op["name"],
                "data_id": obj.data.as_pointer() if obj and obj.type == "MESH" else None,
                "edges": [{"index": index, "seam": bool(obj.data.edges[index].use_seam)}
                          for index in edge_indices]
                         if obj and obj.type == "MESH" and all(index < len(obj.data.edges) for index in edge_indices) else None,
            })
    for name in sorted(n for n in touched if isinstance(n, str)):
        obj = scene.objects.get(name)
        if obj:
            item = object_info(name)
            item["data_id"] = obj.data.as_pointer() if obj.data else None
            item["animation"] = action_curves(
                obj.animation_data.action if obj.animation_data else None
            )
            item["pose_bones"] = [
                {
                    "name": op["bone"],
                    "rotation_mode": obj.pose.bones[op["bone"]].rotation_mode,
                    "data_path": op["data_path"],
                    "value": list(getattr(obj.pose.bones[op["bone"]], op["data_path"])),
                }
                for op in operations
                if op.get("op") == "bone_keyframe"
                and op.get("name") == name
                and obj.type == "ARMATURE"
                and obj.pose.bones.get(op.get("bone")) is not None
            ]
            if name in geometry and obj.type == "MESH":
                item["vertices"] = [list(v.co) for v in obj.data.vertices]
                item["faces"] = [list(poly.vertices) for poly in obj.data.polygons]
            state["targets"].append(item)
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


class SceneAutomation:
    def __init__(self):
        self.previews = {}

    def validate(self, recipe):
        if not isinstance(recipe, dict) or set(recipe) != {"operations"}:
            raise RecipeError("invalid_arguments", "Expected an operations recipe.")
        operations = recipe["operations"]
        if not isinstance(operations, list) or not 1 <= len(operations) <= 32:
            raise RecipeError("invalid_arguments", "Use 1 to 32 operations.")
        if len(json.dumps(operations, separators=(",", ":"), allow_nan=False).encode("utf-8")) > MAX_RECIPE_BYTES:
            raise RecipeError("invalid_arguments", "Scene recipe exceeds the 256 KiB operation limit.")
        objects = {o.name: o.type for o in bpy.context.scene.objects}
        modifier_names = {
            o.name: {modifier.name for modifier in o.modifiers}
            for o in bpy.context.scene.objects if o.type == "MESH"
        }
        armatures = {name.casefold() for name in bpy.data.armatures.keys()}
        mesh_sizes = {
            o.name: len(o.data.vertices) for o in bpy.context.scene.objects if o.type == "MESH"
        }
        mesh_loops = {o.name: len(o.data.loops) for o in bpy.context.scene.objects if o.type == "MESH"}
        mesh_edge_counts = {o.name: len(o.data.edges) for o in bpy.context.scene.objects if o.type == "MESH"}
        mesh_seams = {o.name: [bool(edge.use_seam) for edge in o.data.edges]
                      for o in bpy.context.scene.objects if o.type == "MESH"}
        uv_layer_names = {o.name: {layer.name for layer in o.data.uv_layers} for o in bpy.context.scene.objects if o.type == "MESH"}
        materials = set(bpy.data.materials.keys())
        collections = set(bpy.data.collections.keys())
        allowed = {
            "op",
            "name",
            "vertices",
            "faces",
            "location",
            "rotation",
            "scale",
            "color",
            "material",
            "collection",
            "source",
            "bone",
            "node",
            "socket",
            "value",
            "data_path",
            "frame",
            "curve_index",
            "keyframe_index",
            "key_frame",
            "key_value",
            "fps",
            "frame_start",
            "frame_end",
            "shader_nodes",
            "shader_links",
            "shader_node_edits",
            "bones",
            "armature",
            "weights",
            "weight_method",
            "ik",
            "modifier_type",
            "modifier_name",
            "modifier_settings",
            "uv_layer",
            "uv_start",
            "uv_values",
            "uv_angle_limit",
            "uv_island_margin",
            "edge_seams",
            "uv_unwrap_method",
            "uv_margin",
        }
        for op in operations:
            if not isinstance(op, dict) or set(op) - allowed:
                raise RecipeError("invalid_arguments", "Unknown recipe fields.")
            kind, name = op.get("op"), op.get("name", "")
            if kind not in {"set_uv_coordinates", "create_uv_layer", "smart_uv_project", "unwrap_uv", "pack_uv_islands"} and (
                op.get("uv_layer") or op.get("uv_start", 0) != 0 or op.get("uv_values")
                or op.get("uv_angle_limit", 1.1519173063162575) != 1.1519173063162575
                or op.get("uv_island_margin", 0.02) != 0.02
                or op.get("uv_unwrap_method", "ANGLE_BASED") != "ANGLE_BASED"
                or op.get("uv_margin", 0.001) != 0.001
            ):
                raise RecipeError("invalid_arguments", "UV fields belong only to UV operations.")
            if kind != "set_mesh_edge_seams" and op.get("edge_seams"):
                raise RecipeError("invalid_arguments", "Edge seam changes belong only to set_mesh_edge_seams.")
            if kind not in {"create_material", "edit_material_graph"} and (op.get("shader_nodes") or op.get("shader_links") or op.get("shader_node_edits")):
                raise RecipeError("invalid_arguments", "Shader graph fields belong only to material creation or graph edits.")
            if kind not in {
                "create_mesh",
                "set_vertices",
                "set_mesh_geometry",
                "set_uv_coordinates",
                "create_uv_layer",
                "smart_uv_project",
                "unwrap_uv",
                "pack_uv_islands",
                "set_mesh_edge_seams",
                "set_transform",
                "create_material",
                "assign_material",
                "create_collection",
                "keyframe",
                "set_keyframe",
                "scene_settings",
                "duplicate_object",
                "set_material_input",
                "edit_material_graph",
                "create_armature",
                "bone_keyframe",
                "bind_mesh",
                "reweight_mesh",
                "auto_bind_mesh",
                "patch_skin_weights",
                "create_ik_constraint",
                "create_empty",
                "set_frame",
                "add_modifier",
                "set_modifier_settings",
            }:
                raise RecipeError("command_not_allowed", "Operation is not allowlisted.")
            if kind != "auto_bind_mesh" and op.get("weight_method"):
                raise RecipeError("invalid_arguments", "Automatic method belongs only to auto_bind_mesh.")
            if kind != "create_ik_constraint" and op.get("ik") is not None:
                raise RecipeError("invalid_arguments", "IK specs belong only to IK setup.")
            if kind not in {"bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"} and (op.get("armature") or op.get("weights")):
                raise RecipeError("invalid_arguments", "Skin binding fields belong only to bind_mesh.")
            if kind != "bone_keyframe" and op.get("bone", "") not in ("", None):
                raise RecipeError("invalid_arguments", "Bone names belong only to bone_keyframe operations.")
            if kind not in {"scene_settings", "set_frame"} and (
                not isinstance(name, str)
                or not 1 <= len(name) <= 64
                or any(ord(c) < 32 for c in name)
            ):
                raise RecipeError("invalid_arguments", "Use a nonempty bounded datablock name.")
            for field in ("location", "rotation", "scale"):
                if op.get(field) is not None:
                    vector(op[field])
            if kind in {"set_vertices", "set_mesh_geometry", "set_uv_coordinates", "set_transform", "assign_material", "keyframe", "bone_keyframe"}:
                existing = bpy.context.scene.objects.get(name)
                if existing and (existing.library or existing.mode == "EDIT"):
                    raise RecipeError(
                        "invalid_context", "Linked or edit-mode objects cannot be changed."
                    )
            if op.get("scale") is not None and any(abs(x) < 1e-8 for x in op["scale"]):
                raise RecipeError("invalid_arguments", "Zero scale is not allowed.")
            if kind == "set_frame":
                if (op.get("name", "") != "" or type(op.get("frame")) is not int
                        or not -100000 <= op["frame"] <= 100000):
                    raise RecipeError("invalid_arguments", "Use an integer timeline frame within +/-100000.")
            elif kind == "create_empty":
                if name in bpy.data.objects or name in objects:
                    raise RecipeError("name_conflict", "Empty name already exists.")
                if op.get("collection") and op["collection"] not in collections:
                    raise RecipeError("collection_not_found", "Empty collection was not found.")
                objects[name] = "EMPTY"
            elif kind == "create_ik_constraint":
                from .rigging import validate_ik_setup
                validate_ik_setup(op)
                if sum(item.get("op") == "create_ik_constraint" for item in operations) > 1:
                    raise RecipeError("invalid_arguments", "Review one IK setup per batch.")
            elif kind == "set_material_input":
                if name not in bpy.data.materials:
                    raise RecipeError("material_not_found", "Inspect an existing material before editing.")
                if any(not isinstance(op.get(key), str) or not 1 <= len(op[key]) <= 64 for key in ("node", "socket")):
                    raise RecipeError("invalid_arguments", "Expected bounded node and socket identifiers.")
                try:
                    editable_input(name, op["node"], op["socket"], op.get("value"))
                except ValueError as error:
                    raise RecipeError("invalid_arguments", str(error)) from error
            elif kind == "edit_material_graph":
                try:
                    validate_existing_graph_edit(name, op.get("shader_nodes", []), op.get("shader_links", []),
                                                 op.get("shader_node_edits", []))
                except ValueError as error:
                    raise RecipeError("invalid_arguments", str(error)) from error
            elif kind in {"bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"}:
                from .skinning import validate_binding
                source, _ = validate_binding(op)
                if name in bpy.data.objects or name in objects:
                    raise RecipeError("name_conflict", "Binding output name already exists.")
                if op.get("collection") and op["collection"] not in collections:
                    raise RecipeError("collection_not_found", "Binding collection was not found.")
                objects[name], mesh_sizes[name] = "MESH", len(source.data.vertices)
                mesh_loops[name] = len(source.data.loops)
                mesh_edge_counts[name] = len(source.data.edges)
                mesh_seams[name] = [bool(edge.use_seam) for edge in source.data.edges]
            elif kind == "duplicate_object":
                source = op.get("source")
                if not isinstance(source, str) or source not in objects:
                    raise RecipeError("object_not_found", "Duplicate source was not found.")
                if name in bpy.data.objects or name in objects:
                    raise RecipeError("name_conflict", "Duplicate object name already exists.")
                original = bpy.context.scene.objects.get(source)
                if objects[source] not in {"MESH", "EMPTY"} or (
                    original and (original.library or original.mode == "EDIT")
                ):
                    raise RecipeError("invalid_context", "Duplicate requires a local mesh or empty in object mode.")
                if objects[source] == "MESH" and mesh_sizes[source] > 100000:
                    raise RecipeError("invalid_arguments", "Duplicate mesh exceeds 100000 vertices.")
                if op.get("collection") and op["collection"] not in collections:
                    raise RecipeError("collection_not_found", "Duplicate destination collection was not found.")
                objects[name] = objects[source]
                if source in mesh_sizes:
                    mesh_sizes[name] = mesh_sizes[source]
                    mesh_loops[name] = mesh_loops.get(source, 0)
                    mesh_edge_counts[name] = mesh_edge_counts.get(source, 0)
                    mesh_seams[name] = list(mesh_seams.get(source, []))
                    uv_layer_names[name] = set(uv_layer_names.get(source, set()))
            elif kind == "create_armature":
                bones = op.get("bones", [])
                data_name = f"{name}_Armature"
                if not isinstance(bones, list) or not 1 <= len(bones) <= 64:
                    raise RecipeError("invalid_arguments", "Armatures require 1 to 64 bones.")
                if (
                    name in bpy.data.objects
                    or name in objects
                    or data_name.casefold() in armatures
                ):
                    raise RecipeError("name_conflict", "Armature object or data name already exists.")
                if op.get("collection") and op["collection"] not in collections:
                    raise RecipeError("collection_not_found", "Armature destination collection was not found.")
                if bpy.context.mode != "OBJECT":
                    raise RecipeError("invalid_context", "Armature creation requires Object mode.")

                specs = {}
                allowed_bone_fields = {"name", "head", "tail", "parent", "connected", "deform"}
                for bone in bones:
                    if not isinstance(bone, dict) or set(bone) - allowed_bone_fields:
                        raise RecipeError("invalid_arguments", "Rig bone fields are invalid.")
                    bone_name = bone.get("name")
                    if (
                        not isinstance(bone_name, str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", bone_name)
                        or bone_name.casefold() in specs
                    ):
                        raise RecipeError("invalid_arguments", "Rig bone names must be unique identifiers.")
                    head, tail = vector(bone.get("head")), vector(bone.get("tail"))
                    if any(abs(coordinate) > 100000 for coordinate in head + tail):
                        raise RecipeError("invalid_arguments", "Rig bone coordinates exceed 100000 Blender units.")
                    if math.dist(head, tail) <= 1e-6:
                        raise RecipeError("invalid_arguments", "Rig bones need distinct head and tail positions.")
                    parent = bone.get("parent")
                    if parent is not None and (
                        not isinstance(parent, str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", parent)
                    ):
                        raise RecipeError("invalid_arguments", "Rig bone parent must be an identifier or null.")
                    if type(bone.get("connected", False)) is not bool or type(
                        bone.get("deform", True)
                    ) is not bool:
                        raise RecipeError("invalid_arguments", "Rig bone connected/deform flags must be booleans.")
                    specs[bone_name.casefold()] = bone
                for bone in specs.values():
                    parent = bone.get("parent")
                    if parent is not None and parent.casefold() not in specs:
                        raise RecipeError("invalid_arguments", "Rig bone parent was not found in the armature.")
                    if bone.get("connected", False):
                        if parent is None:
                            raise RecipeError("invalid_arguments", "Connected rig bones require a parent.")
                        parent_tail = specs[parent.casefold()]["tail"]
                        if math.dist(vector(parent_tail), vector(bone["head"])) > 1e-4:
                            raise RecipeError("invalid_arguments", "Connected bone heads must match parent tails.")
                for bone_name in specs:
                    visited = set()
                    current = bone_name
                    while specs[current].get("parent") is not None:
                        current = specs[current]["parent"].casefold()
                        if current in visited or current == bone_name:
                            raise RecipeError("invalid_arguments", "Rig bone hierarchy cannot contain parent cycles.")
                        visited.add(current)
                objects[name] = "ARMATURE"
                armatures.add(data_name.casefold())
            elif kind in {"create_mesh", "set_vertices", "set_mesh_geometry"}:
                vertices = op.get("vertices", [])
                max_vertices = 512 if kind == "set_mesh_geometry" else 128
                if not isinstance(vertices, list) or not 1 <= len(vertices) <= max_vertices:
                    raise RecipeError("invalid_arguments", f"Use 1 to {max_vertices} vertices.")
                for value in vertices:
                    vector(value)
                if kind == "create_mesh":
                    if (
                        name in bpy.data.objects
                        or name in objects
                        or name + "_Mesh" in bpy.data.meshes
                    ):
                        raise RecipeError("name_conflict", "Mesh/object name already exists.")
                    faces = op.get("faces", [])
                    if not isinstance(faces, list) or len(faces) > 128:
                        raise RecipeError("invalid_arguments", "Too many faces.")
                    for face in faces:
                        if (
                            not isinstance(face, list)
                            or not 3 <= len(face) <= 32
                            or len(set(face)) != len(face)
                            or any(type(i) is not int or not 0 <= i < len(vertices) for i in face)
                        ):
                            raise RecipeError("invalid_arguments", "Face indices are invalid.")
                    collection = op.get("collection", "")
                    if collection and collection not in collections:
                        raise RecipeError("collection_not_found", "Collection was not found.")
                    objects[name], mesh_sizes[name] = "MESH", len(vertices)
                    mesh_loops[name] = sum(len(face) for face in faces)
                    mesh_edge_counts[name] = len({tuple(sorted((face[i], face[(i + 1) % len(face)])))
                                                   for face in faces for i in range(len(face))})
                    mesh_seams[name] = [False] * mesh_edge_counts[name]
                    uv_layer_names[name] = set()
                elif kind == "set_vertices" and (objects.get(name) != "MESH" or mesh_sizes[name] != len(vertices)):
                    raise RecipeError(
                        "invalid_arguments",
                        "Vertex edits require a mesh with matching vertex count.",
                    )
                elif kind == "set_mesh_geometry":
                    if objects.get(name) != "MESH":
                        raise RecipeError("object_not_found", "Topology edits require an existing mesh object.")
                    faces = op.get("faces", [])
                    if not isinstance(faces, list) or len(faces) > 512:
                        raise RecipeError("invalid_arguments", "Use at most 512 mesh faces.")
                    for face in faces:
                        if (not isinstance(face, list) or not 3 <= len(face) <= 32
                                or len(set(face)) != len(face)
                                or any(type(index) is not int or not 0 <= index < len(vertices) for index in face)):
                            raise RecipeError("invalid_arguments", "Mesh face indices are invalid.")
                    existing = bpy.context.scene.objects.get(name)
                    if existing:
                        validate_topology_edit(existing)
                    mesh_sizes[name] = len(vertices)
                    mesh_loops[name] = sum(len(face) for face in faces)
                    mesh_edge_counts[name] = len({tuple(sorted((face[i], face[(i + 1) % len(face)])))
                                                   for face in faces for i in range(len(face))})
                    mesh_seams[name] = [False] * mesh_edge_counts[name]
            elif kind == "create_uv_layer":
                if objects.get(name) != "MESH":
                    raise RecipeError("mesh_not_found", "UV layer creation requires a mesh object.")
                obj = bpy.context.scene.objects.get(name)
                if obj and (obj.library or obj.mode == "EDIT"):
                    raise RecipeError("invalid_context", "UV layer creation requires a local mesh in Object Mode.")
                layer_name = op.get("uv_layer")
                if not isinstance(layer_name, str) or not 1 <= len(layer_name) <= 64 or any(ord(c) < 32 for c in layer_name):
                    raise RecipeError("invalid_arguments", "Specify a bounded UV layer name.")
                if layer_name in uv_layer_names.get(name, set()):
                    raise RecipeError("name_conflict", "UV layer name already exists on this mesh.")
                values = op.get("uv_values", [])
                if values and (len(values) != mesh_loops.get(name, 0) or len(values) > 512):
                    raise RecipeError("invalid_arguments", "Initial UV coordinates must match all mesh loops and fit the 512-loop limit.")
                for value in values:
                    vector(value, 2)
                    if any(abs(component) > 1000000 for component in value):
                        raise RecipeError("invalid_arguments", "UV coordinates exceed the supported numeric range.")
                uv_layer_names.setdefault(name, set()).add(layer_name)
            elif kind == "smart_uv_project":
                if (op.get("uv_values") or op.get("uv_start", 0) != 0
                        or op.get("uv_unwrap_method", "ANGLE_BASED") != "ANGLE_BASED"
                        or op.get("uv_margin", 0.001) != 0.001):
                    raise RecipeError("invalid_arguments", "Smart UV projection does not accept coordinates or seam unwrap settings.")
                if objects.get(name) != "MESH":
                    raise RecipeError("mesh_not_found", "Smart UV projection requires a mesh object.")
                obj = bpy.context.scene.objects.get(name)
                if obj and (obj.library or obj.mode == "EDIT"):
                    raise RecipeError("invalid_context", "Smart UV projection requires a local mesh in Object Mode.")
                if bpy.context.mode != "OBJECT":
                    raise RecipeError("invalid_context", "Smart UV projection requires Object Mode.")
                if mesh_loops.get(name, 0) > 200000:
                    raise RecipeError("operation_limit", "Smart UV projection is limited to 200,000 mesh loops.")
                layer_name = op.get("uv_layer")
                if not isinstance(layer_name, str) or not 1 <= len(layer_name) <= 64 or any(ord(c) < 32 for c in layer_name):
                    raise RecipeError("invalid_arguments", "Specify a bounded UV layer name.")
                angle = op.get("uv_angle_limit", 1.1519173063162575)
                margin = op.get("uv_island_margin", 0.02)
                if (type(angle) not in (int, float) or not math.isfinite(angle)
                        or not 0 <= angle <= math.pi / 2):
                    raise RecipeError("invalid_arguments", "UV angle limit must be between zero and 90 degrees.")
                if (type(margin) not in (int, float) or not math.isfinite(margin)
                        or not 0 <= margin <= 0.5):
                    raise RecipeError("invalid_arguments", "UV island margin must be between zero and 0.5.")
                uv_layer_names.setdefault(name, set()).add(layer_name)
            elif kind == "unwrap_uv":
                if (op.get("uv_values") or op.get("uv_start", 0) != 0
                        or op.get("uv_angle_limit", 1.1519173063162575) != 1.1519173063162575
                        or op.get("uv_island_margin", 0.02) != 0.02):
                    raise RecipeError("invalid_arguments", "Seam-based unwrap does not accept coordinates or smart-project settings.")
                if objects.get(name) != "MESH":
                    raise RecipeError("mesh_not_found", "Seam-based UV unwrap requires a mesh object.")
                obj = bpy.context.scene.objects.get(name)
                if obj and (obj.library or obj.mode == "EDIT"):
                    raise RecipeError("invalid_context", "Seam-based UV unwrap requires a local mesh in Object Mode.")
                if bpy.context.mode != "OBJECT":
                    raise RecipeError("invalid_context", "Seam-based UV unwrap requires Object Mode.")
                if mesh_loops.get(name, 0) > 200000:
                    raise RecipeError("operation_limit", "Seam-based UV unwrap is limited to 200,000 mesh loops.")
                layer_name = op.get("uv_layer")
                if not isinstance(layer_name, str) or not 1 <= len(layer_name) <= 64 or any(ord(c) < 32 for c in layer_name):
                    raise RecipeError("invalid_arguments", "Specify a bounded UV layer name.")
                if not any(mesh_seams.get(name, [])):
                    raise RecipeError("uv_seams_required", "Mark at least one mesh edge as a seam before seam-based unwrap.")
                if op.get("uv_unwrap_method", "ANGLE_BASED") not in {"ANGLE_BASED", "CONFORMAL"}:
                    raise RecipeError("invalid_arguments", "Choose ANGLE_BASED or CONFORMAL UV unwrap.")
                margin = op.get("uv_margin", 0.001)
                if type(margin) not in (int, float) or not math.isfinite(margin) or not 0 <= margin <= 0.5:
                    raise RecipeError("invalid_arguments", "UV unwrap margin must be between zero and 0.5.")
                uv_layer_names.setdefault(name, set()).add(layer_name)
            elif kind == "pack_uv_islands":
                if (op.get("uv_values") or op.get("uv_start", 0) != 0
                        or op.get("uv_angle_limit", 1.1519173063162575) != 1.1519173063162575
                        or op.get("uv_island_margin", 0.02) != 0.02
                        or op.get("uv_unwrap_method", "ANGLE_BASED") != "ANGLE_BASED"):
                    raise RecipeError("invalid_arguments", "UV island packing accepts only its target layer and margin.")
                if objects.get(name) != "MESH":
                    raise RecipeError("mesh_not_found", "UV island packing requires a mesh object.")
                obj = bpy.context.scene.objects.get(name)
                if (obj and (obj.library or obj.mode == "EDIT")) or bpy.context.mode != "OBJECT":
                    raise RecipeError("invalid_context", "UV island packing requires a local mesh in Object Mode.")
                if mesh_loops.get(name, 0) > 200000:
                    raise RecipeError("operation_limit", "UV island packing is limited to 200,000 mesh loops.")
                layer_name = op.get("uv_layer")
                if not isinstance(layer_name, str) or layer_name not in uv_layer_names.get(name, set()):
                    raise RecipeError("uv_layer_not_found", "UV island packing requires an existing UV layer.")
                margin = op.get("uv_margin", 0.001)
                if type(margin) not in (int, float) or not math.isfinite(margin) or not 0 <= margin <= 0.5:
                    raise RecipeError("invalid_arguments", "UV packing margin must be between zero and 0.5.")
            elif kind == "set_mesh_edge_seams":
                if objects.get(name) != "MESH":
                    raise RecipeError("mesh_not_found", "Mesh seam edits require a mesh object.")
                obj = bpy.context.scene.objects.get(name)
                if obj and (obj.library or obj.mode == "EDIT"):
                    raise RecipeError("invalid_context", "Mesh seam edits require a local mesh in Object Mode.")
                if bpy.context.mode != "OBJECT":
                    raise RecipeError("invalid_context", "Mesh seam edits require Object Mode.")
                changes = op.get("edge_seams")
                if not isinstance(changes, list) or not 1 <= len(changes) <= 512:
                    raise RecipeError("invalid_arguments", "Use 1 to 512 edge seam changes.")
                indices = set()
                for item in changes:
                    if (not isinstance(item, dict) or set(item) != {"index", "seam"}
                            or type(item["index"]) is not int or type(item["seam"]) is not bool
                            or not 0 <= item["index"] < mesh_edge_counts.get(name, 0)
                            or item["index"] in indices):
                        raise RecipeError("invalid_arguments", "Edge seam changes need unique valid indices and boolean values.")
                    indices.add(item["index"])
                    mesh_seams[name][item["index"]] = item["seam"]
            elif kind == "set_uv_coordinates":
                obj = bpy.context.scene.objects.get(name)
                if obj is None or obj.type != "MESH":
                    raise RecipeError("mesh_not_found", "UV edits require an existing mesh in the active scene.")
                if obj.library or obj.mode == "EDIT":
                    raise RecipeError("invalid_context", "UV edits require a local mesh in Object Mode.")
                layer_name = op.get("uv_layer")
                if not isinstance(layer_name, str) or not 1 <= len(layer_name) <= 64:
                    raise RecipeError("invalid_arguments", "Specify an exact UV layer name.")
                layer = obj.data.uv_layers.get(layer_name)
                values, start = op.get("uv_values"), op.get("uv_start", 0)
                if layer is None and layer_name not in uv_layer_names.get(name, set()):
                    raise RecipeError("uv_layer_not_found", "The specified UV layer does not exist.")
                loop_count = mesh_loops.get(name, len(layer.data) if layer else 0)
                if (type(start) is not int or start < 0 or not isinstance(values, list)
                        or not 1 <= len(values) <= 512 or start + len(values) > loop_count):
                    raise RecipeError("invalid_arguments", "UV edit range must fit within 1 to 512 existing loops.")
                for value in values:
                    vector(value, 2)
                    if any(abs(component) > 1000000 for component in value):
                        raise RecipeError("invalid_arguments", "UV coordinates exceed the supported numeric range.")
            elif kind in {"set_transform", "assign_material", "keyframe", "bone_keyframe"}:
                if name not in objects:
                    raise RecipeError("object_not_found", "Object was not found.")
                existing = bpy.context.scene.objects.get(name)
                if existing and (existing.library or existing.mode == "EDIT"):
                    raise RecipeError(
                        "invalid_context", "Linked or edit-mode objects cannot be changed."
                    )
                if kind == "assign_material" and (
                    objects[name] != "MESH" or op.get("material") not in materials
                ):
                    raise RecipeError(
                        "material_not_found",
                        "Material assignment requires a mesh and known material.",
                    )
                if kind == "keyframe" and (
                    op.get("data_path", "location") not in {"location", "rotation_euler", "scale"}
                    or type(op.get("frame", 1)) is not int
                    or not -100000 <= op.get("frame", 1) <= 100000
                ):
                    raise RecipeError("invalid_arguments", "Invalid transform keyframe.")
                if kind == "keyframe" and op.get("value") is not None:
                    values = vector(op["value"])
                    if op.get("data_path", "location") == "scale" and any(abs(value)<1e-8 for value in values):
                        raise RecipeError("invalid_arguments", "Object scale keyframes cannot use zero scale.")
                if kind == "bone_keyframe":
                    bone_name = op.get("bone")
                    data_path = op.get("data_path", "location")
                    pose_bone = existing.pose.bones.get(bone_name) if existing and existing.type == "ARMATURE" and isinstance(bone_name, str) else None
                    if pose_bone is None:
                        raise RecipeError("bone_not_found", "Pose bone was not found on the active scene armature.")
                    expected_size = 4 if data_path == "rotation_quaternion" else 3
                    if data_path not in {"location", "rotation_euler", "rotation_quaternion", "scale"}:
                        raise RecipeError("invalid_arguments", "Unsupported pose-bone keyframe property.")
                    if type(op.get("frame", 1)) is not int or not -100000 <= op.get("frame", 1) <= 100000:
                        raise RecipeError("invalid_arguments", "Invalid pose-bone keyframe frame.")
                    values = vector(op.get("value"), expected_size)
                    if data_path == "rotation_quaternion":
                        if pose_bone.rotation_mode != "QUATERNION":
                            raise RecipeError("invalid_context", "The pose bone must use quaternion rotation for quaternion keyframes.")
                        norm = math.sqrt(sum(value * value for value in values))
                        if abs(norm - 1.0) > 1e-3:
                            raise RecipeError("invalid_arguments", "Pose-bone quaternions must be normalized.")
                    elif data_path == "rotation_euler" and pose_bone.rotation_mode in {"QUATERNION", "AXIS_ANGLE"}:
                        raise RecipeError("invalid_context", "The pose bone must use Euler rotation for Euler keyframes.")
                    if data_path == "scale" and any(abs(value) < 1e-8 for value in values):
                        raise RecipeError("invalid_arguments", "Pose-bone scale keyframes cannot use zero scale.")
            elif kind == "set_keyframe":
                existing = bpy.context.scene.objects.get(name)
                animation = existing.animation_data if existing else None
                action = animation.action if animation else None
                if existing is None or action is None:
                    raise RecipeError("animation_not_found", "An active Action is required to edit a keyframe.")
                if existing.library or existing.mode == "EDIT":
                    raise RecipeError("invalid_context", "Linked or edit-mode objects cannot change Actions.")
                curve_index, key_index = op.get("curve_index"), op.get("keyframe_index")
                target_frame, target_value = op.get("key_frame"), op.get("key_value")
                if (type(curve_index) is not int or type(key_index) is not int
                        or not 0 <= curve_index < 10000 or not 0 <= key_index <= 100000
                        or type(target_frame) not in (int, float) or not math.isfinite(target_frame)
                        or not -100000 <= target_frame <= 100000
                        or type(target_value) not in (int, float) or not math.isfinite(target_value)
                        or abs(target_value) > 100000000):
                    raise RecipeError("invalid_arguments", "Action key edit values are outside supported bounds.")
                entries = action_curve_entries(action)
                if curve_index >= len(entries):
                    raise RecipeError("curve_not_found", "Action curve index was not found.")
                points = entries[curve_index][0].keyframe_points
                if key_index >= len(points):
                    raise RecipeError("keyframe_not_found", "Action keyframe index was not found.")
                if any(index != key_index and abs(float(point.co.x) - target_frame) < 1e-6
                       for index, point in enumerate(points)):
                    raise RecipeError("keyframe_collision", "Another key already occupies the requested frame.")
            elif any(op.get(field) is not None for field in (
                "curve_index", "keyframe_index", "key_frame", "key_value"
            )):
                raise RecipeError("invalid_arguments", "Action key edit fields belong only to set_keyframe.")
            elif kind == "create_material":
                if name in materials:
                    raise RecipeError("name_conflict", "Material already exists.")
                color = vector(op.get("color"), 4)
                if any(not 0 <= c <= 1 for c in color):
                    raise RecipeError("invalid_arguments", "Color must be in 0..1.")
                try:
                    graph_validate(op.get("shader_nodes", []), op.get("shader_links", []))
                except ValueError as error:
                    raise RecipeError("invalid_arguments", str(error)) from error
                materials.add(name)
            elif kind == "create_collection":
                if name in collections:
                    raise RecipeError("name_conflict", "Collection already exists.")
                collections.add(name)
            elif kind == "add_modifier":
                modifier_type = op.get("modifier_type")
                modifier_name = op.get("modifier_name")
                settings = op.get("modifier_settings", {})
                if objects.get(name) != "MESH":
                    raise RecipeError("invalid_arguments", "Modifiers can be added only to mesh objects.")
                existing = bpy.context.scene.objects.get(name)
                if existing and (existing.library or existing.mode == "EDIT"):
                    raise RecipeError("invalid_context", "Linked or edit-mode meshes cannot be modified.")
                validate_modifier_settings(modifier_type, settings)
                if (not isinstance(modifier_name, str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", modifier_name)):
                    raise RecipeError("invalid_arguments", "Use a bounded modifier identifier.")
                if modifier_name in modifier_names.get(name, set()):
                    raise RecipeError("name_conflict", "Modifier name already exists on this object.")
                modifier_names.setdefault(name, set()).add(modifier_name)
            elif kind == "set_modifier_settings":
                existing = bpy.context.scene.objects.get(name)
                if objects.get(name) != "MESH" or existing is None:
                    raise RecipeError("invalid_arguments", "Modifier edits require an existing mesh object.")
                if existing.library or existing.mode == "EDIT":
                    raise RecipeError("invalid_context", "Linked or edit-mode meshes cannot be modified.")
                modifier_name = op.get("modifier_name")
                if (not isinstance(modifier_name, str)
                        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", modifier_name)):
                    raise RecipeError("invalid_arguments", "Use a bounded modifier identifier.")
                modifier = existing.modifiers.get(modifier_name)
                if modifier is None:
                    raise RecipeError("modifier_not_found", "The named modifier does not exist on this object.")
                settings = op.get("modifier_settings", {})
                if not settings:
                    raise RecipeError("invalid_arguments", "Provide at least one modifier setting to change.")
                validate_modifier_settings(modifier.type, settings)
            elif kind == "scene_settings":
                fps, start, end = (
                    op.get("fps", 30),
                    op.get("frame_start", 1),
                    op.get("frame_end", 250),
                )
                if (
                    any(type(v) is not int for v in (fps, start, end))
                    or not 1 <= fps <= 240
                    or not -100000 <= start <= end <= 100000
                ):
                    raise RecipeError("invalid_arguments", "Invalid scene timing.")
        return operations

    def preview(self, recipe):
        operations = self.validate(recipe)
        now = time.monotonic()
        self.previews = {
            key: value for key, value in self.previews.items() if value["expires"] > now
        }
        if len(self.previews) >= 32:
            raise RecipeError("preview_limit", "Too many pending previews.")
        preview_id = secrets.token_hex(16)
        self.previews[preview_id] = {
            "operations": json.loads(json.dumps(operations)),
            "fingerprint": fingerprint(operations),
            "expires": now + 600,
        }
        return {
            "preview_id": preview_id,
            "expires_in_seconds": 600,
            "scene": bpy.context.scene.name,
            "changes": operations,
            "saves_file": False,
            "material_edits": [material_info(name) for name in sorted({op["name"] for op in operations
                               if op["op"] in {"set_material_input", "edit_material_graph"}})],
            "recovery": "Failed batches remove newly created datablocks and restore touched objects, material defaults, and scene timing.",
        }

    def apply(self, preview_id, confirmation):
        if not isinstance(preview_id, str) or confirmation != preview_id:
            raise RecipeError(
                "confirmation_required", "confirmation must equal the reviewed preview_id."
            )
        plan = self.previews.pop(preview_id, None)
        if not plan or plan["expires"] <= time.monotonic():
            raise RecipeError(
                "preview_not_found", "Preview is expired, consumed, or belongs to another session."
            )
        operations = plan["operations"]
        if fingerprint(operations) != plan["fingerprint"]:
            raise RecipeError(
                "stale_preview", "Scene changed after preview; inspect and preview again."
            )
        self.validate({"operations": operations})
        return self.execute(operations)

    def execute(self, operations):
        scene = bpy.context.scene
        timing = (
            scene.render.fps,
            scene.render.fps_base,
            scene.frame_start,
            scene.frame_end,
            scene.frame_current,
            scene.frame_subframe,
        )
        created, snapshots, pose_snapshots, action_copies, material_defaults = [], {}, {}, {}, {}
        created_graph_nodes, created_graph_links = [], []
        graph_snapshots = {}
        created_constraints = []
        created_modifiers = []
        modifier_settings_snapshots = {}
        results = []

        def remember(obj):
            if obj.name in snapshots or any(
                kind == "objects" and value == obj for kind, value in created
            ):
                return
            animation = obj.animation_data
            snapshots[obj.name] = (
                obj,
                obj.data,
                obj.location.copy(),
                obj.rotation_euler.copy(),
                obj.scale.copy(),
                animation.action if animation else None,
                getattr(animation, "action_slot", None),
                animation is not None,
            )

        def remember_pose_bone(obj, pose_bone):
            key = (obj.name, pose_bone.name)
            if key not in pose_snapshots:
                pose_snapshots[key] = (
                    pose_bone,
                    pose_bone.location.copy(),
                    pose_bone.rotation_euler.copy(),
                    pose_bone.rotation_quaternion.copy(),
                    pose_bone.scale.copy(),
                    pose_bone.rotation_mode,
                )

        def ensure_action_copy(obj):
            animation = obj.animation_data_create()
            if obj.name not in action_copies:
                previous = animation.action
                if previous:
                    slot = getattr(animation, "action_slot", None)
                    copied = previous.copy()
                    created.append(("actions", copied))
                    animation.action = copied
                    if slot:
                        animation.action_slot = next(
                            s for s in copied.slots if s.identifier == slot.identifier
                        )
                action_copies[obj.name] = True
            return animation

        try:
            for op in operations:
                kind, name = op["op"], op.get("name", "")
                if kind == "create_empty":
                    obj = bpy.data.objects.new(name,None)
                    created.append(("objects",obj))
                    col = bpy.data.collections.get(op.get("collection","")) or scene.collection
                    col.objects.link(obj)
                    obj.empty_display_type = "ARROWS"
                    obj.empty_display_size = 0.2
                    for field,prop in (("location","location"),("rotation","rotation_euler"),("scale","scale")):
                        if op.get(field) is not None:
                            setattr(obj,prop,op[field])
                elif kind == "create_ik_constraint":
                    from .rigging import create_ik_setup
                    ik_result = create_ik_setup(op, created_constraints)
                elif kind == "create_collection":
                    col = bpy.data.collections.new(name)
                    created.append(("collections", col))
                    scene.collection.children.link(col)
                elif kind == "add_modifier":
                    obj = scene.objects[name]
                    modifier = obj.modifiers.new(op["modifier_name"], op["modifier_type"])
                    created_modifiers.append((obj, modifier))
                    apply_modifier_settings(modifier, op.get("modifier_settings", {}))
                elif kind == "set_modifier_settings":
                    obj = scene.objects[name]
                    modifier = obj.modifiers.get(op["modifier_name"])
                    settings = op["modifier_settings"]
                    for key in settings:
                        snapshot_key = (obj.name, modifier.name, key)
                        modifier_settings_snapshots.setdefault(
                            snapshot_key, (modifier, getattr(modifier, key)))
                    apply_modifier_settings(modifier, settings)
                elif kind == "create_armature":
                    armature_data = bpy.data.armatures.new(name + "_Armature")
                    created.append(("armatures", armature_data))
                    obj = bpy.data.objects.new(name, armature_data)
                    created.append(("objects", obj))
                    collection = bpy.data.collections.get(op.get("collection", "")) or scene.collection
                    collection.objects.link(obj)
                    view_layer = bpy.context.view_layer
                    previous_active = view_layer.objects.active
                    previous_selected = list(bpy.context.selected_objects)
                    try:
                        for selected in bpy.context.selected_objects:
                            selected.select_set(False)
                        obj.select_set(True)
                        view_layer.objects.active = obj
                        bpy.ops.object.mode_set(mode="EDIT")
                        edit_bones = {}
                        for bone in op["bones"]:
                            edit_bone = armature_data.edit_bones.new(bone["name"])
                            edit_bone.head = bone["head"]
                            edit_bone.tail = bone["tail"]
                            edit_bone.use_deform = bone.get("deform", True)
                            edit_bones[bone["name"].casefold()] = edit_bone
                        for bone in op["bones"]:
                            edit_bone = edit_bones[bone["name"].casefold()]
                            if bone.get("parent") is not None:
                                edit_bone.parent = edit_bones[bone["parent"].casefold()]
                                edit_bone.use_connect = bone.get("connected", False)
                        bpy.ops.object.mode_set(mode="OBJECT")
                    finally:
                        if obj.mode != "OBJECT":
                            bpy.ops.object.mode_set(mode="OBJECT")
                        for selected in bpy.context.selected_objects:
                            selected.select_set(False)
                        for selected in previous_selected:
                            if selected.name in view_layer.objects:
                                selected.select_set(True)
                        view_layer.objects.active = (
                            previous_active
                            if previous_active and previous_active.name in view_layer.objects
                            else None
                        )
                elif kind == "create_material":
                    mat = bpy.data.materials.new(name)
                    created.append(("materials", mat))
                    mat.diffuse_color = op["color"]
                    mat.use_nodes = True
                    if op.get("shader_nodes"):
                        construct_graph(mat, op["shader_nodes"], op.get("shader_links", []))
                    else:
                        mat.node_tree.nodes.get("Principled BSDF").inputs[
                            "Base Color"
                        ].default_value = op["color"]
                elif kind == "create_mesh":
                    mesh = bpy.data.meshes.new(name + "_Mesh")
                    created.append(("meshes", mesh))
                    mesh.from_pydata(op["vertices"], [], op.get("faces", []))
                    mesh.update()
                    obj = bpy.data.objects.new(name, mesh)
                    created.append(("objects", obj))
                    col = bpy.data.collections.get(op.get("collection", "")) or scene.collection
                    col.objects.link(obj)
                    for field, prop in (
                        ("location", "location"),
                        ("rotation", "rotation_euler"),
                        ("scale", "scale"),
                    ):
                        if op.get(field) is not None:
                            setattr(obj, prop, op[field])
                elif kind in {"bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"}:
                    from .skinning import bind_copy
                    bind_copy(op, created)
                elif kind == "duplicate_object":
                    source = scene.objects[op["source"]]
                    obj = source.copy()
                    created.append(("objects", obj))
                    obj.name = name
                    if source.type == "MESH":
                        obj.data = source.data.copy()
                        created.append(("meshes", obj.data))
                    if obj.animation_data and obj.animation_data.action:
                        slot = getattr(obj.animation_data, "action_slot", None)
                        copied = obj.animation_data.action.copy()
                        created.append(("actions", copied))
                        obj.animation_data.action = copied
                        action_copies[obj.name] = True
                        if slot:
                            obj.animation_data.action_slot = next(
                                s for s in copied.slots if s.identifier == slot.identifier
                            )
                    col = bpy.data.collections.get(op.get("collection", "")) or scene.collection
                    col.objects.link(obj)
                    for field, prop in (("location", "location"), ("rotation", "rotation_euler"),
                                        ("scale", "scale")):
                        if op.get(field) is not None:
                            setattr(obj, prop, op[field])
                elif kind == "set_material_input":
                    pin = editable_input(name, op["node"], op["socket"], op["value"])
                    key = (name, op["node"], pin.identifier)
                    if key not in material_defaults:
                        old = pin.default_value
                        material_defaults[key] = (pin, old if type(old) in (int, float) else list(old))
                    pin.default_value = op["value"]
                elif kind == "edit_material_graph":
                    graph_snapshots.setdefault(name, material_info(name))
                    add_existing_graph_nodes(name, op.get("shader_nodes", []), op.get("shader_links", []),
                                             created_graph_nodes, created_graph_links,
                                             op.get("shader_node_edits", []))
                elif kind == "set_frame":
                    _set_frame(scene,op["frame"])
                elif kind == "scene_settings":
                    scene.render.fps, scene.render.fps_base = op.get("fps", 30), 1.0
                    scene.frame_start, scene.frame_end = (
                        op.get("frame_start", 1),
                        op.get("frame_end", 250),
                    )
                else:
                    obj = scene.objects[name]
                    remember(obj)
                    if kind == "set_transform":
                        for field, prop in (
                            ("location", "location"),
                            ("rotation", "rotation_euler"),
                            ("scale", "scale"),
                        ):
                            if op.get(field) is not None:
                                setattr(obj, prop, op[field])
                    elif kind in {"set_vertices", "set_mesh_geometry", "set_uv_coordinates", "create_uv_layer", "smart_uv_project", "unwrap_uv", "pack_uv_islands", "set_mesh_edge_seams", "assign_material"}:
                        if obj.name not in {
                            value.name for category, value in created if category == "objects"
                        } and not any(
                            category == "meshes" and value == obj.data
                            for category, value in created
                        ):
                            obj.data = obj.data.copy()
                            created.append(("meshes", obj.data))
                        if kind == "set_vertices":
                            for vert, co in zip(obj.data.vertices, op["vertices"], strict=True):
                                vert.co = co
                            obj.data.update()
                        elif kind == "set_mesh_geometry":
                            replace_mesh_geometry(obj.data, op["vertices"], op.get("faces", []))
                        elif kind == "set_uv_coordinates":
                            layer = obj.data.uv_layers.get(op["uv_layer"])
                            apply_uv_coordinates(layer, op.get("uv_start", 0), op["uv_values"])
                        elif kind == "create_uv_layer":
                            create_uv_layer(obj.data, op["uv_layer"], op.get("uv_values", []))
                        elif kind == "smart_uv_project":
                            smart_project_uvs(
                                obj, op["uv_layer"], op.get("uv_angle_limit", 1.1519173063162575),
                                op.get("uv_island_margin", 0.02))
                        elif kind == "unwrap_uv":
                            unwrap_uvs(obj, op["uv_layer"], op.get("uv_unwrap_method", "ANGLE_BASED"),
                                       op.get("uv_margin", 0.001))
                        elif kind == "pack_uv_islands":
                            pack_uv_islands(obj, op["uv_layer"], op.get("uv_margin", 0.001))
                        elif kind == "set_mesh_edge_seams":
                            apply_mesh_edge_seams(obj.data, op["edge_seams"])
                        else:
                            obj.data.materials.append(bpy.data.materials[op["material"]])
                    elif kind == "keyframe":
                        ensure_action_copy(obj)
                        if op.get("value") is not None:
                            setattr(obj,op.get("data_path","location"),op["value"])
                        before = set(bpy.data.actions)
                        if not obj.keyframe_insert(
                            data_path=op.get("data_path", "location"), frame=op.get("frame", 1)
                        ):
                            raise RuntimeError("Keyframe insertion failed")
                        created.extend(
                            ("actions", action) for action in set(bpy.data.actions) - before
                        )
                    elif kind == "set_keyframe":
                        ensure_action_copy(obj)
                        entries = action_curve_entries(obj.animation_data.action)
                        curve = entries[op["curve_index"]][0]
                        point = curve.keyframe_points[op["keyframe_index"]]
                        point.co.x = op["key_frame"]
                        point.co.y = op["key_value"]
                        curve.update()
                        observed_index = next((index for index, candidate in enumerate(curve.keyframe_points)
                                               if abs(float(candidate.co.x) - op["key_frame"]) < 1e-6), None)
                        if (observed_index is None
                                or abs(float(curve.keyframe_points[observed_index].co.y) - op["key_value"]) > 1e-6):
                            raise RuntimeError("Edited Action key did not retain its requested coordinates")
                    elif kind == "bone_keyframe":
                        pose_bone = obj.pose.bones[op["bone"]]
                        remember_pose_bone(obj, pose_bone)
                        ensure_action_copy(obj)
                        before = set(bpy.data.actions)
                        setattr(pose_bone, op["data_path"], op["value"])
                        if not pose_bone.keyframe_insert(
                            data_path=op["data_path"], frame=op["frame"], group=pose_bone.name
                        ):
                            raise RuntimeError("Pose-bone keyframe insertion failed")
                        created.extend(
                            ("actions", action) for action in set(bpy.data.actions) - before
                        )
                result = {"op": kind, "name": name, "state": "completed"}
                if kind == "set_frame":
                    result.update(frame=scene.frame_current,native_frame_verified=True)
                if kind == "set_keyframe":
                    result.update(curve_index=op["curve_index"],
                                  keyframe_index=observed_index,
                                  frame=float(op["key_frame"]), value=float(op["key_value"]),
                                  native_keyframe_verified=True)
                if kind in {"add_modifier", "set_modifier_settings"}:
                    result.update(modifier=op["modifier_name"],
                                  applied_settings=dict(op["modifier_settings"]),
                                  native_settings_verified=True)
                if kind == "set_mesh_geometry":
                    result.update(vertices=len(scene.objects[name].data.vertices),
                                  faces=len(scene.objects[name].data.polygons),
                                  native_geometry_verified=True)
                if kind == "set_uv_coordinates":
                    result.update(uv_layer=op["uv_layer"], uv_start=op.get("uv_start", 0),
                                  uv_count=len(op["uv_values"]), native_uvs_verified=True)
                if kind == "create_uv_layer":
                    result.update(uv_layer=op["uv_layer"], uv_count=len(op.get("uv_values", [])),
                                  native_uv_layer_verified=scene.objects[name].data.uv_layers.get(op["uv_layer"]) is not None)
                if kind == "smart_uv_project":
                    layer = scene.objects[name].data.uv_layers.get(op["uv_layer"])
                    result.update(uv_layer=op["uv_layer"], uv_loop_count=len(layer.data) if layer else 0,
                                  native_uv_projection_verified=layer is not None and len(layer.data) == len(scene.objects[name].data.loops))
                if kind == "unwrap_uv":
                    layer = scene.objects[name].data.uv_layers.get(op["uv_layer"])
                    result.update(uv_layer=op["uv_layer"], uv_loop_count=len(layer.data) if layer else 0,
                                  unwrap_method=op.get("uv_unwrap_method", "ANGLE_BASED"),
                                  native_seam_unwrap_verified=layer is not None and len(layer.data) == len(scene.objects[name].data.loops))
                if kind == "pack_uv_islands":
                    layer = scene.objects[name].data.uv_layers.get(op["uv_layer"])
                    result.update(uv_layer=op["uv_layer"], uv_loop_count=len(layer.data) if layer else 0,
                                  packing_margin=op.get("uv_margin", 0.001),
                                  native_uv_packing_verified=layer is not None and len(layer.data) == len(scene.objects[name].data.loops))
                if kind == "set_mesh_edge_seams":
                    result.update(edge_count=len(op["edge_seams"]), native_seams_verified=True)
                if kind == "edit_material_graph":
                    observed = material_info(name)
                    node_names = {node["id"] for node in observed["nodes"]}
                    link_keys = {(link["from_node"], link["from_socket"],
                                  link["to_node"], link["to_socket"])
                                 for link in observed["links"]}
                    expected_nodes = {node["id"] for node in op.get("shader_nodes", [])}
                    expected_links = {(link["from_node"], link["from_socket"],
                                       link["to_node"], link["to_socket"])
                                      for link in op.get("shader_links", [])}
                    observed_by_id = {node["id"]: node for node in observed["nodes"]}
                    for edit in op.get("shader_node_edits", []):
                        node = observed_by_id.get(edit["id"])
                        if node is None:
                            raise RuntimeError("Edited material node is missing on native read-back")
                        if edit.get("x") is not None and abs(node["location"][0] - edit["x"]) > 1e-5:
                            raise RuntimeError("Edited material node X position failed native read-back")
                        if edit.get("y") is not None and abs(node["location"][1] - edit["y"]) > 1e-5:
                            raise RuntimeError("Edited material node Y position failed native read-back")
                        if edit.get("operation") and node["operation"] != edit["operation"]:
                            raise RuntimeError("Edited material node operation failed native read-back")
                        if edit.get("blend_type") and node["blend_type"] != edit["blend_type"]:
                            raise RuntimeError("Edited material node blend type failed native read-back")
                        input_map = {pin["identifier"]: pin for pin in node["inputs"]}
                        for socket_name, value in edit.get("inputs", {}).items():
                            pin = input_map.get(socket_name) or next(
                                (item for item in node["inputs"] if item["name"] == socket_name), None
                            )
                            actual = pin.get("default") if pin else None
                            if isinstance(value, list):
                                if not isinstance(actual, list) or len(actual) != len(value) or any(
                                        abs(float(a) - float(b)) > 1e-6 for a, b in zip(actual, value)):
                                    raise RuntimeError("Edited material socket default failed native read-back")
                            elif actual is None or abs(float(actual) - float(value)) > 1e-6:
                                raise RuntimeError("Edited material socket default failed native read-back")
                    if not expected_nodes <= node_names or not expected_links <= link_keys:
                        raise RuntimeError("Material graph additions did not verify on native read-back")
                    result.update(added_nodes=sorted(expected_nodes), added_links=len(expected_links),
                                  edited_nodes=[edit["id"] for edit in op.get("shader_node_edits", [])],
                                  native_graph_verified=True)
                if kind == "create_ik_constraint":
                    result.update(ik_result)
                    result.update(bone=op["ik"]["bone"],constraint=op["ik"]["constraint"],
                                  target=op["ik"]["target"],native_settings_verified=True,
                                  requires_deformation_review=True)
                if kind in {"bind_mesh", "reweight_mesh", "auto_bind_mesh", "patch_skin_weights"}:
                    result.update(source=op["source"], armature=op["armature"],
                                  source_preserved=True, weight_assignments=sum(len(vertex.groups) for vertex in scene.objects[name].data.vertices),
                                  native_weights_verified=True, overwrites_existing_skin=False)
                    if kind == "auto_bind_mesh":
                        result["weight_method"] = "blender_heat_top4"
                        result["requires_deformation_review"] = True
                    if kind == "patch_skin_weights":
                        result["changed_vertices"] = sorted({item["vertex"] for item in op["weights"]})
                        result["untouched_weights_preserved"] = True
                if kind == "bone_keyframe":
                    result["bone"] = op["bone"]
                    result["data_path"] = op["data_path"]
                    result["frame"] = op["frame"]
                results.append(result)
            return {
                "state": "completed",
                "operations": results,
                "objects": [
                    object_info(name)
                    for name in sorted({op.get("name", "") for op in operations})
                    if scene.objects.get(name)
                ],
                "saved": False,
                "materials": [material_info(name) for name in sorted({op["name"] for op in operations
                              if op["op"] in {"create_material", "set_material_input", "edit_material_graph"}})],
                "preserved_datablocks": [
                    data.name for _, data, *rest in snapshots.values() if data
                ],
            }
        except Exception as operation_error:
            rollback_errors = []
            for material, link in reversed(created_graph_links):
                try:
                    if link in material.node_tree.links:
                        material.node_tree.links.remove(link)
                except Exception:
                    rollback_errors.append("material_graph_link_cleanup_failed")
            for material, node in reversed(created_graph_nodes):
                try:
                    if material.node_tree.nodes.get(node.name) == node:
                        material.node_tree.nodes.remove(node)
                except Exception:
                    rollback_errors.append("material_graph_node_cleanup_failed")
            for name, before in graph_snapshots.items():
                try:
                    restore_existing_graph_state(name, before)
                    if material_info(name) != before:
                        raise RuntimeError("Material graph rollback verification failed")
                except Exception:
                    rollback_errors.append("material_graph_restore_verification_failed")
            for modifier, key, old_value in reversed([
                (value[0], setting, value[1])
                for (_, _, setting), value in modifier_settings_snapshots.items()
            ]):
                try:
                    setattr(modifier, key, old_value)
                    if getattr(modifier, key) != old_value:
                        raise RuntimeError("Modifier rollback verification failed")
                except Exception:
                    rollback_errors.append("modifier_setting_restore_failed")
            for obj, modifier in reversed(created_modifiers):
                try:
                    if obj.modifiers.get(modifier.name) == modifier:
                        obj.modifiers.remove(modifier)
                except Exception:
                    rollback_errors.append("modifier_cleanup_failed")
            for pose_bone, constraint in reversed(created_constraints):
                try:
                    pose_bone.constraints.remove(constraint)
                except Exception:
                    rollback_errors.append("constraint_cleanup_failed")
            for pin, old in material_defaults.values():
                try:
                    pin.default_value = old
                except Exception:
                    rollback_errors.append("material_default_restore_failed")
            scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end = timing[:4]
            for (
                obj,
                data,
                location,
                rotation,
                scale,
                action,
                slot,
                had_animation,
            ) in snapshots.values():
                try:
                    obj.data, obj.location, obj.rotation_euler, obj.scale = (
                        data,
                        location,
                        rotation,
                        scale,
                    )
                    if had_animation:
                        obj.animation_data.action = action
                        if slot:
                            obj.animation_data.action_slot = slot
                    elif obj.animation_data:
                        obj.animation_data_clear()
                except Exception:
                    rollback_errors.append("object_restore_failed")
            for pose_bone, location, rotation_euler, rotation_quaternion, scale, rotation_mode in pose_snapshots.values():
                try:
                    pose_bone.location = location
                    pose_bone.rotation_euler = rotation_euler
                    pose_bone.rotation_quaternion = rotation_quaternion
                    pose_bone.scale = scale
                    pose_bone.rotation_mode = rotation_mode
                except Exception:
                    rollback_errors.append("pose_bone_restore_failed")
            # Copies allocate an object before its independent mesh/Action. Remove
            # newly created objects first so deleting their data cannot invalidate
            # an object reference that remains in the cleanup list.
            cleanup = [item for item in reversed(created) if item[0] == "objects"] + [
                item for item in reversed(created) if item[0] != "objects"
            ]
            for category, value in cleanup:
                try:
                    getattr(bpy.data, category).remove(value, do_unlink=True)
                except Exception:
                    rollback_errors.append("datablock_cleanup_failed")
            try:
                # Evaluate only after original Actions/constraints have been restored.
                scene.frame_set(timing[4],subframe=timing[5])
            except Exception:
                rollback_errors.append("scene_frame_restore_failed")
            return {
                "state": "rolled_back" if not rollback_errors else "partial",
                "completed_before_failure": results,
                "rollback_errors": rollback_errors,
                "error": {
                    "code": getattr(operation_error, "code", "operation_failed"),
                    "message": "Scene operation failed; inspect rollback status.",
                },
                "saved": False,
            }
