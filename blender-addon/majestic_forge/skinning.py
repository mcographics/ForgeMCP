# SPDX-License-Identifier: MIT
"""Reviewed explicit or native heat skin weights on independent mesh copies."""

import math
import re

import bpy

from .automation import RecipeError


def validate_binding(op):
    source = bpy.context.scene.objects.get(op.get("source", ""))
    rig = bpy.context.scene.objects.get(op.get("armature", ""))
    if source is None or source.type != "MESH" or rig is None or rig.type != "ARMATURE":
        raise RecipeError("object_not_found", "Binding requires an existing mesh and armature in the active scene.")
    automatic = op.get("op") == "auto_bind_mesh"
    patching = op.get("op") == "patch_skin_weights"
    vertex_limit, face_limit = (10000, 20000) if automatic or patching else (128, 128)
    if not 1 <= len(source.data.vertices) <= vertex_limit or len(rig.data.bones) > 64 or len(source.data.polygons) > face_limit or len(source.vertex_groups) > 64:
        raise RecipeError("operation_too_large", f"This skinning method supports {vertex_limit} vertices, {face_limit} faces and 64 bones/groups.")
    if (source.library or source.data.library or rig.library or rig.data.library or source.mode != "OBJECT"
            or rig.mode != "OBJECT" or bpy.context.mode != "OBJECT" or source.constraints
            or source.data.shape_keys or source.animation_data or source.data.animation_data):
        raise RecipeError("unsupported_source", "Skinning requires a local static mesh and local armature in Object mode.")
    if op.get("op") in {"reweight_mesh", "patch_skin_weights"}:
        if len(source.modifiers) != 1 or source.modifiers[0].type != "ARMATURE":
            raise RecipeError("unsupported_source", "Reweighting requires exactly one Armature modifier.")
        modifier = source.modifiers[0]
        if (modifier.object != rig or source.parent not in (None, rig) or (source.parent and source.parent_type != "OBJECT") or not modifier.use_vertex_groups
                or modifier.use_bone_envelopes or modifier.use_multi_modifier or modifier.vertex_group
                or not modifier.show_viewport or not modifier.show_render):
            raise RecipeError("unsupported_source", "Reweighting requires an enabled unmasked vertex-group skin on the same armature.")
        if any(group.name not in rig.data.bones for group in source.vertex_groups):
            raise RecipeError("unsupported_source", "Non-bone vertex groups are outside the reweight profile.")
        if sum(len(vertex.groups) for vertex in source.data.vertices) > (40000 if patching else 512):
            raise RecipeError("operation_too_large", "Original skin exceeds this method's assignment limit.")
    elif source.parent or source.modifiers or source.vertex_groups:
        raise RecipeError("unsupported_source", "Binding requires an unbound source mesh.")
    if source.name not in bpy.context.view_layer.objects or rig.name not in bpy.context.view_layer.objects:
        raise RecipeError("invalid_context", "Mesh and armature must be in the active view layer.")
    if len(source.data.attributes) > 16 or sum(len(a.data) for a in source.data.attributes) > (200000 if automatic or patching else 8192):
        raise RecipeError("operation_too_large", "Source attribute data exceeds the binding limit.")
    if any(attribute.data_type == "STRING" for attribute in source.data.attributes):
        raise RecipeError("unsupported_source", "String mesh attributes are outside the binding profile.")
    if any(not math.isfinite(value) or abs(value) > 1e8 for vertex in source.data.vertices for value in vertex.co):
        raise RecipeError("invalid_scene_data", "Source mesh positions must be finite and bounded.")
    weights = op.get("weights", [])
    if automatic:
        if op.get("weight_method") != "blender_heat_top4" or not isinstance(weights, list) or weights or not source.data.polygons:
            raise RecipeError("invalid_arguments", "Automatic binding requires blender_heat_top4, a faced mesh, and no explicit weights.")
        if not any(bone.use_deform for bone in rig.data.bones):
            raise RecipeError("unsupported_source", "Automatic weighting requires deform bones.")
        _check_transforms(source, rig)
        return source, rig
    if not isinstance(weights, list) or not 1 <= len(weights) <= 512:
        raise RecipeError("invalid_arguments", "Use 1 to 512 explicit skin assignments.")
    totals, influences, seen = {}, {}, set()
    for item in weights:
        if not isinstance(item, dict) or set(item) != {"vertex", "bone", "weight"}:
            raise RecipeError("invalid_arguments", "Expected explicit vertex, bone and weight fields.")
        index, bone, weight = item["vertex"], item["bone"], item["weight"]
        if (type(index) is not int or not 0 <= index < len(source.data.vertices)
                or not isinstance(bone, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", bone)
                or bone not in rig.data.bones or not rig.data.bones[bone].use_deform
                or type(weight) not in (int, float) or not math.isfinite(weight) or not 0 < weight <= 1):
            raise RecipeError("invalid_arguments", "Skin assignment references an invalid vertex, deform bone or weight.")
        if (index, bone) in seen:
            raise RecipeError("invalid_arguments", "Skin assignments must be unique.")
        seen.add((index, bone))
        totals[index] = totals.get(index, 0) + weight
        influences[index] = influences.get(index, 0) + 1
    if (not patching and len(totals) != len(source.data.vertices)) or any(abs(v - 1) > 1e-5 for v in totals.values()) or any(v > 4 for v in influences.values()):
        raise RecipeError("invalid_arguments", "Every source vertex needs normalized weights with at most four influences.")
    if patching:
        if len(totals) > 128:
            raise RecipeError("operation_too_large", "A weight patch supports 128 selected vertices.")
        for vertex in source.data.vertices:
            if vertex.index in totals:
                continue
            values = [assignment.weight for assignment in vertex.groups]
            if (not 1 <= len(values) <= 4 or any(not math.isfinite(value) or value <= 0 for value in values)
                    or abs(sum(values) - 1) > 1e-5
                    or any(not rig.data.bones[source.vertex_groups[a.group].name].use_deform for a in vertex.groups)):
                raise RecipeError("unsupported_source", "Untouched vertices must have normalized deform-bone weights.")
    _check_transforms(source, rig)
    return source, rig


def _check_transforms(source, rig):
    bpy.context.view_layer.update()
    if any(not math.isfinite(value) for obj in (source, rig) for row in obj.matrix_world for value in row):
        raise RecipeError("invalid_scene_data", "Binding transforms must be finite.")
    if abs(source.matrix_world.determinant()) < 1e-12 or abs(rig.matrix_world.determinant()) < 1e-12:
        raise RecipeError("invalid_context", "Binding requires nonsingular mesh and armature transforms.")


def binding_facts(op):
    source, rig = validate_binding(op)
    bpy.context.view_layer.update()
    attributes = []
    for attribute in source.data.attributes:
        values = []
        for item in attribute.data:
            for field in ("value", "vector", "color"):
                if hasattr(item, field):
                    value = getattr(item, field)
                    values.append(value if isinstance(value, (int, float, bool, str)) else list(value))
        attributes.append([attribute.name, attribute.data_type, attribute.domain, values])
    facts = {"source_data": source.data.as_pointer(), "rig_data": rig.data.as_pointer(),
            "vertices": [list(v.co) for v in source.data.vertices],
            "faces": [list(p.vertices) for p in source.data.polygons], "attributes": attributes,
            "original_groups": [[group.name, group.lock_weight] for group in source.vertex_groups],
            "original_weights": [[vertex.index, assignment.group, assignment.weight]
                                 for vertex in source.data.vertices for assignment in vertex.groups],
            "parent": source.parent.as_pointer() if source.parent else None,
            "parent_inverse": [list(row) for row in source.matrix_parent_inverse],
            "preserve_volume": bool(source.modifiers[0].use_deform_preserve_volume) if source.modifiers else False,
            "source_world": [list(row) for row in source.matrix_world],
            "rig_world": [list(row) for row in rig.matrix_world],
            "bones": [[bone.name, bone.parent.name if bone.parent else None, bone.use_deform,
                       list(bone.head_local), list(bone.tail_local),
                       bone.head_radius, bone.tail_radius, bone.envelope_distance,
                       bone.envelope_weight, bone.use_envelope_multiply, bone.bbone_segments,
                       [list(row) for row in rig.pose.bones[bone.name].matrix]] for bone in rig.data.bones]}
    def check_finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise RecipeError("invalid_scene_data", "Binding state contains non-finite values.")
        if isinstance(value, dict):
            for item in value.values():
                check_finite(item)
        elif isinstance(value, list):
            for item in value:
                check_finite(item)
    check_finite(facts)
    return facts


def bind_copy(op, created):
    source, rig = validate_binding(op)
    obj = source.copy()
    created.append(("objects", obj))
    obj.name = op["name"]
    obj.data = source.data.copy()
    created.append(("meshes", obj.data))
    collection = bpy.data.collections.get(op.get("collection", "")) or bpy.context.scene.collection
    collection.objects.link(obj)
    obj.select_set(False)
    if op.get("op") == "auto_bind_mesh":
        _automatic_weights(obj, rig)
        return obj
    preserve_volume = False
    if op.get("op") in {"reweight_mesh", "patch_skin_weights"}:
        preserve_volume = obj.modifiers[0].use_deform_preserve_volume
        obj.modifiers.remove(obj.modifiers[0])
        if op.get("op") == "patch_skin_weights":
            touched = sorted({item["vertex"] for item in op["weights"]})
            for group in obj.vertex_groups:
                group.remove(touched)
        else:
            obj.vertex_groups.clear()
    groups = {}
    for item in op["weights"]:
        bone = item["bone"]
        if bone not in groups:
            groups[bone] = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
        groups[bone].add([item["vertex"]], item["weight"], "REPLACE")
    modifier = obj.modifiers.new("ForgeMCP Armature", "ARMATURE")
    modifier.object = rig
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False
    modifier.use_deform_preserve_volume = preserve_volume
    bpy.context.view_layer.update()
    # Check actual native assignments, not just the submitted recipe.
    expected = {(item["vertex"], item["bone"]): item["weight"] for item in op["weights"]}
    actual = {(vertex.index, obj.vertex_groups[assignment.group].name): assignment.weight
              for vertex in obj.data.vertices for assignment in vertex.groups}
    if op.get("op") == "patch_skin_weights":
        touched = {item["vertex"] for item in op["weights"]}
        expected.update({(vertex.index, source.vertex_groups[a.group].name): a.weight
                         for vertex in source.data.vertices if vertex.index not in touched for a in vertex.groups})
    if set(actual) != set(expected) or any(abs(actual[key] - expected[key]) > 1e-6 for key in expected):
        raise RuntimeError("Native skin assignment verification failed")
    return obj


def _run_heat(obj, rig):
    return bpy.ops.object.parent_set(type="ARMATURE_AUTO", keep_transform=True)


def skin_info(name, vertex_start=0, vertex_count=128):
    if (not isinstance(name, str) or not 1 <= len(name) <= 64
            or type(vertex_start) is not int or not 0 <= vertex_start <= 9999
            or type(vertex_count) is not int or not 1 <= vertex_count <= 128):
        raise RecipeError("invalid_arguments", "Expected a mesh name and bounded vertex range.")
    obj = bpy.context.scene.objects.get(name)
    if obj is None or obj.type != "MESH":
        raise RecipeError("object_not_found", "Mesh was not found in the active scene.")
    if obj.mode != "OBJECT":
        raise RecipeError("invalid_context", "Inspect source weights in Object mode.")
    if len(obj.data.vertices) > 10000 or len(obj.vertex_groups) > 64:
        raise RecipeError("operation_too_large", "Skin inspection supports 10000 vertices and 64 groups.")
    if vertex_start >= len(obj.data.vertices):
        raise RecipeError("invalid_arguments", "Vertex range begins outside the mesh.")
    stop = min(len(obj.data.vertices), vertex_start + vertex_count)
    vertices, assignment_count = [], 0
    for vertex in obj.data.vertices[vertex_start:stop]:
        weights = []
        for assignment in vertex.groups:
            assignment_count += 1
            if assignment_count > 512:
                raise RecipeError("operation_too_large", "Reduce the range to inspect more than 512 assignments.")
            if not math.isfinite(assignment.weight):
                raise RecipeError("invalid_scene_data", "Skin contains non-finite weights.")
            group = obj.vertex_groups[assignment.group]
            weights.append({"bone":group.name,"weight":assignment.weight,"locked":group.lock_weight})
        vertices.append({"vertex":vertex.index,"weights":weights,
                         "weight_sum":sum(item["weight"] for item in weights)})
    return {"name":obj.name,"data":obj.data.name,"vertex_count":len(obj.data.vertices),
            "vertex_start":vertex_start,"vertices_returned":len(vertices),"vertices":vertices,
            "next_vertex_start":stop if stop < len(obj.data.vertices) else None,
            "coordinate_indices":"source_mesh", "scene_frame":bpy.context.scene.frame_current,
            "armature_modifiers":[{"name":m.name,"armature":m.object.name if m.object else None}
                                  for m in obj.modifiers if m.type == "ARMATURE"],
            "read_only":True}


def _automatic_weights(obj, rig):
    layer = bpy.context.view_layer
    selected = list(bpy.context.selected_objects)
    active = layer.objects.active
    world = obj.matrix_world.copy()
    try:
        for item in selected:
            item.select_set(False)
        obj.select_set(True)
        rig.select_set(True)
        layer.objects.active = rig
        try:
            finished = _run_heat(obj, rig)
        except RuntimeError as error:
            raise RecipeError("automatic_weights_failed", "Native automatic weighting failed.") from error
        if finished != {"FINISHED"}:
            raise RecipeError("automatic_weights_failed", "Native automatic weights did not finish.")
        obj.matrix_world = world
    finally:
        for item in list(bpy.context.selected_objects):
            item.select_set(False)
        for item in selected:
            item.select_set(True)
        layer.objects.active = active
    modifiers = [modifier for modifier in obj.modifiers if modifier.type == "ARMATURE" and modifier.object == rig]
    if len(modifiers) != 1 or obj.parent != rig:
        raise RecipeError("automatic_weights_failed", "Native automatic binding did not create the expected skin.")
    modifier = modifiers[0]
    modifier.use_vertex_groups = True
    modifier.use_bone_envelopes = False
    groups = {group.index: group for group in obj.vertex_groups
              if group.name in rig.data.bones and rig.data.bones[group.name].use_deform}
    expected = {}
    for vertex in obj.data.vertices:
        values = [(groups[a.group], float(a.weight)) for a in vertex.groups if a.group in groups]
        if any(not math.isfinite(weight) or weight < 0 for _, weight in values):
            raise RecipeError("automatic_weights_failed", "Native solver produced invalid weights.")
        values = sorted(((group, weight) for group, weight in values if weight > 0),
                        key=lambda item: (-item[1], item[0].name))[:4]
        total = sum(weight for _, weight in values)
        if total <= 1e-12:
            raise RecipeError("automatic_weights_failed", "Native solver left an unweighted vertex.")
        expected[vertex.index] = [(group, weight / total) for group, weight in values]
    # Normalize and limit influences only after all vertices passed solver checks.
    for group in obj.vertex_groups:
        group.remove(list(range(len(obj.data.vertices))))
    for index, values in expected.items():
        for group, weight in values:
            group.add([index], weight, "REPLACE")
    for vertex in obj.data.vertices:
        actual = {a.group: a.weight for a in vertex.groups}
        wanted = {group.index: weight for group, weight in expected[vertex.index]}
        if (set(actual) != set(wanted) or len(actual) > 4
                or abs(sum(actual.values()) - 1) > 1e-5
                or any(abs(actual[index] - weight) > 1e-6 for index, weight in wanted.items())):
            raise RecipeError("automatic_weights_failed", "Automatic weight verification failed.")
    layer.update()
