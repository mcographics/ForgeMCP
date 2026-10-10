"""Bounded, read-only inspection of Blender armatures and mesh skin weights."""

import math

import bpy

from .automation import RecipeError


def rig_info(name, include_weights=False):
    if not isinstance(name, str) or not 1 <= len(name) <= 64 or type(include_weights) is not bool:
        raise RecipeError("invalid_arguments", "Expected an armature name and boolean weight flag.")
    scene = bpy.context.scene
    armature = scene.objects.get(name) if scene else None
    if armature is None or armature.type != "ARMATURE":
        raise RecipeError("rig_not_found", "Named armature was not found in the active scene.")

    all_bones = list(armature.data.bones)
    bones = []
    for bone in all_bones[:512]:
        head = list(bone.head_local)
        tail = list(bone.tail_local)
        if any(not math.isfinite(float(value)) for value in (*head, *tail, bone.length)):
            raise RecipeError("invalid_scene_data", "Armature contains non-finite bone values.")
        pose_bone = armature.pose.bones.get(bone.name)
        pose = None
        if pose_bone is not None:
            pose_values = (
                list(pose_bone.location),
                list(pose_bone.rotation_euler),
                list(pose_bone.rotation_quaternion),
                list(pose_bone.scale),
            )
            if any(not math.isfinite(float(value)) for values in pose_values for value in values):
                raise RecipeError("invalid_scene_data", "Armature pose contains non-finite values.")
            pose = {
                "location": pose_values[0],
                "rotation_euler": pose_values[1],
                "rotation_quaternion": pose_values[2],
                "rotation_mode": pose_bone.rotation_mode,
                "scale": pose_values[3],
            }
        bones.append(
            {
                "name": bone.name,
                "parent": bone.parent.name if bone.parent else None,
                "connected": bool(bone.use_connect),
                "deform": bool(bone.use_deform),
                "length": float(bone.length),
                "head_local": head,
                "tail_local": tail,
                "pose": pose,
            }
        )

    scene_objects = scene.objects
    related = []
    scan_limit = 10000
    truncated_objects = len(scene_objects) > scan_limit
    total_vertices_scanned = 0
    total_assignments_scanned = 0
    for object_index, obj in enumerate(scene_objects):
        if object_index >= scan_limit:
            break
        if obj.type != "MESH":
            continue
        uses_armature = obj.parent == armature or any(
            modifier.type == "ARMATURE" and modifier.object == armature for modifier in obj.modifiers
        )
        if not uses_armature:
            continue
        if len(related) >= 128:
            if include_weights:
                raise RecipeError("operation_too_large", "Weight inspection is limited to 32 related meshes.")
            truncated_objects = True
            break
        if include_weights and (len(all_bones) > 256 or len(related) >= 32):
            raise RecipeError(
                "operation_too_large",
                "Weight inspection is limited to 256 bones and 32 related meshes.",
            )
        entry = {
            "name": obj.name,
            "vertices": len(obj.data.vertices),
            "vertex_groups": [group.name for group in list(obj.vertex_groups)[:512]],
            "vertex_groups_truncated": len(obj.vertex_groups) > 512,
        }
        if include_weights:
            total_vertices_scanned += entry["vertices"]
            if total_vertices_scanned > 100_000:
                raise RecipeError(
                    "operation_too_large",
                    "Weight inspection is limited to 100000 total vertices per query.",
                )
            group_bones = {
                group.index: group.name
                for group in obj.vertex_groups
                if group.name in armature.data.bones
            }
            stats = {
                bone.name: {"weighted_vertices": 0, "weight_sum": 0.0, "maximum_weight": 0.0}
                for bone in armature.data.bones
            }
            assignment_count = 0
            for vertex in obj.data.vertices:
                for assignment in vertex.groups:
                    assignment_count += 1
                    total_assignments_scanned += 1
                    if total_assignments_scanned > 2_000_000:
                        raise RecipeError(
                            "operation_too_large",
                            "Weight inspection is limited to two million vertex-group assignments per query.",
                        )
                    bone_name = group_bones.get(assignment.group)
                    if bone_name is None:
                        continue
                    values = stats[bone_name]
                    weight = float(assignment.weight)
                    if not math.isfinite(weight):
                        raise RecipeError("invalid_scene_data", "Mesh contains a non-finite skin weight.")
                    values["weighted_vertices"] += 1
                    values["weight_sum"] += weight
                    values["maximum_weight"] = max(values["maximum_weight"], weight)
            entry["skin_weights"] = stats
            entry["weight_assignments_scanned"] = assignment_count
            entry["vertices_scanned"] = entry["vertices"]
        related.append(entry)

    return {
        "name": armature.name,
        "data": armature.data.name,
        "bone_count": len(all_bones),
        "bones": bones,
        "bones_truncated": len(all_bones) > len(bones),
        "related_meshes": related,
        "related_meshes_truncated": truncated_objects,
        "weights_included": include_weights,
    }
