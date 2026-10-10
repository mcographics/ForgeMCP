"""Original bounded scene recipes, executed by the bridge on Blender's main thread."""

import hashlib
import json
import math
import re
import secrets
import time

import bpy

from .materials import construct_graph, editable_input, graph_validate, material_info


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
        "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
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


def fingerprint(operations):
    scene = bpy.context.scene
    touched = {op.get("name") for op in operations} | {
        op.get("source") for op in operations if op.get("op") == "duplicate_object"
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
        ],
        "targets": [],
        "material_targets": [],
    }
    geometry = {op.get("name") for op in operations if op.get("op") == "set_vertices"} | {
        op.get("source") for op in operations if op.get("op") == "duplicate_object"
    }
    for op in operations:
        if op.get("op") == "set_material_input":
            info = material_info(op["name"])
            pin = editable_input(op["name"], op["node"], op["socket"], op["value"])
            value = pin.default_value
            info["target_default"] = value if type(value) in (int, float) else list(value)
            state["material_targets"].append(info)
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
        objects = {o.name: o.type for o in bpy.context.scene.objects}
        armatures = {name.casefold() for name in bpy.data.armatures.keys()}
        mesh_sizes = {
            o.name: len(o.data.vertices) for o in bpy.context.scene.objects if o.type == "MESH"
        }
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
            "fps",
            "frame_start",
            "frame_end",
            "shader_nodes",
            "shader_links",
            "bones",
        }
        for op in operations:
            if not isinstance(op, dict) or set(op) - allowed:
                raise RecipeError("invalid_arguments", "Unknown recipe fields.")
            kind, name = op.get("op"), op.get("name", "")
            if kind != "create_material" and (op.get("shader_nodes") or op.get("shader_links")):
                raise RecipeError("invalid_arguments", "Shader graphs belong to new material creation.")
            if kind not in {
                "create_mesh",
                "set_vertices",
                "set_transform",
                "create_material",
                "assign_material",
                "create_collection",
                "keyframe",
                "scene_settings",
                "duplicate_object",
                "set_material_input",
                "create_armature",
                "bone_keyframe",
            }:
                raise RecipeError("command_not_allowed", "Operation is not allowlisted.")
            if kind != "bone_keyframe" and op.get("bone", "") not in ("", None):
                raise RecipeError("invalid_arguments", "Bone names belong only to bone_keyframe operations.")
            if kind != "scene_settings" and (
                not isinstance(name, str)
                or not 1 <= len(name) <= 64
                or any(ord(c) < 32 for c in name)
            ):
                raise RecipeError("invalid_arguments", "Use a nonempty bounded datablock name.")
            for field in ("location", "rotation", "scale"):
                if op.get(field) is not None:
                    vector(op[field])
            if kind in {"set_vertices", "set_transform", "assign_material", "keyframe", "bone_keyframe"}:
                existing = bpy.context.scene.objects.get(name)
                if existing and (existing.library or existing.mode == "EDIT"):
                    raise RecipeError(
                        "invalid_context", "Linked or edit-mode objects cannot be changed."
                    )
            if op.get("scale") is not None and any(abs(x) < 1e-8 for x in op["scale"]):
                raise RecipeError("invalid_arguments", "Zero scale is not allowed.")
            if kind == "set_material_input":
                if name not in bpy.data.materials:
                    raise RecipeError("material_not_found", "Inspect an existing material before editing.")
                if any(not isinstance(op.get(key), str) or not 1 <= len(op[key]) <= 64 for key in ("node", "socket")):
                    raise RecipeError("invalid_arguments", "Expected bounded node and socket identifiers.")
                try:
                    editable_input(name, op["node"], op["socket"], op.get("value"))
                except ValueError as error:
                    raise RecipeError("invalid_arguments", str(error)) from error
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
            elif kind in {"create_mesh", "set_vertices"}:
                vertices = op.get("vertices", [])
                if not isinstance(vertices, list) or not 1 <= len(vertices) <= 128:
                    raise RecipeError("invalid_arguments", "Use 1 to 128 vertices.")
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
                elif objects.get(name) != "MESH" or mesh_sizes[name] != len(vertices):
                    raise RecipeError(
                        "invalid_arguments",
                        "Vertex edits require a mesh with matching vertex count.",
                    )
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
                               if op["op"] == "set_material_input"})],
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
        )
        created, snapshots, pose_snapshots, action_copies, material_defaults = [], {}, {}, {}, {}
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
                if kind == "create_collection":
                    col = bpy.data.collections.new(name)
                    created.append(("collections", col))
                    scene.collection.children.link(col)
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
                    elif kind in {"set_vertices", "assign_material"}:
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
                        else:
                            obj.data.materials.append(bpy.data.materials[op["material"]])
                    elif kind == "keyframe":
                        ensure_action_copy(obj)
                        before = set(bpy.data.actions)
                        if not obj.keyframe_insert(
                            data_path=op.get("data_path", "location"), frame=op.get("frame", 1)
                        ):
                            raise RuntimeError("Keyframe insertion failed")
                        created.extend(
                            ("actions", action) for action in set(bpy.data.actions) - before
                        )
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
                              if op["op"] in {"create_material", "set_material_input"}})],
                "preserved_datablocks": [
                    data.name for _, data, *rest in snapshots.values() if data
                ],
            }
        except Exception:
            rollback_errors = []
            for pin, old in material_defaults.values():
                try:
                    pin.default_value = old
                except Exception:
                    rollback_errors.append("material_default_restore_failed")
            scene.render.fps, scene.render.fps_base, scene.frame_start, scene.frame_end = timing[:4]
            if scene.frame_current != timing[4]:
                scene.frame_set(timing[4])
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
            return {
                "state": "rolled_back" if not rollback_errors else "partial",
                "completed_before_failure": results,
                "rollback_errors": rollback_errors,
                "error": {
                    "code": "operation_failed",
                    "message": "Scene operation failed; inspect rollback status.",
                },
                "saved": False,
            }
