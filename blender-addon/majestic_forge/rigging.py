# SPDX-License-Identifier: MIT
"""Bounded, read-only inspection of Blender armatures and mesh skin weights."""

import math
import re

import bpy

from .automation import RecipeError


def validate_ik_setup(op):
    spec = op.get("ik")
    required = {"bone","constraint","target","chain_count"}
    if not isinstance(spec,dict) or not required <= set(spec) or set(spec)-required-{"iterations","pole_target","pole_angle"}:
        raise RecipeError("invalid_arguments", "Expected a bounded IK spec.")
    if any(not isinstance(spec[key],str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}",spec[key])
           for key in ("bone","constraint","target")):
        raise RecipeError("invalid_arguments", "Use exact bounded IK identifiers.")
    if (type(spec["chain_count"]) is not int or not 1 <= spec["chain_count"] <= 16
            or type(spec.get("iterations",64)) is not int or not 1 <= spec.get("iterations",64) <= 256):
        raise RecipeError("invalid_arguments", "IK supports 1..16 bones and 1..256 iterations.")
    rig = bpy.context.scene.objects.get(op.get("name",""))
    target = bpy.context.scene.objects.get(spec["target"])
    pole_name,pole_angle = spec.get("pole_target"),spec.get("pole_angle",0.0)
    if (type(pole_angle) not in (int,float) or not math.isfinite(pole_angle) or abs(pole_angle)>math.pi
            or (pole_name is None and pole_angle != 0)):
        raise RecipeError("invalid_arguments", "Pole angle must be finite radians within +/-pi and requires a pole target.")
    pole = None
    if pole_name is not None:
        if (not isinstance(pole_name,str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}",pole_name)
                or pole_name == spec["target"] or spec["chain_count"] < 2):
            raise RecipeError("invalid_arguments", "Pole IK requires a distinct control and at least two bones.")
        pole = bpy.context.scene.objects.get(pole_name)
        if pole is None or pole.type != "EMPTY":
            raise RecipeError("object_not_found", "Pole target must be an existing Empty.")
    if rig is None or rig.type != "ARMATURE" or target is None or target.type != "EMPTY":
        raise RecipeError("object_not_found", "IK requires an existing armature and Empty target.")
    if len(rig.data.bones) > 64:
        raise RecipeError("operation_too_large", "IK setup supports rigs with at most 64 bones.")
    # Newly linked controls may not enter view-layer collections until update.
    bpy.context.view_layer.update()
    controls = (rig,target,pole) if pole else (rig,target)
    for obj in controls:
        if (obj.library or (obj.data and obj.data.library) or obj.parent or obj.constraints
                or obj.mode != "OBJECT" or obj.name not in bpy.context.view_layer.objects
                or (obj.animation_data and (obj.animation_data.drivers or obj.animation_data.nla_tracks))):
            raise RecipeError("unsupported_source", "IK setup requires local unparented objects without object constraints, drivers or NLA.")
    if bpy.context.mode != "OBJECT":
        raise RecipeError("invalid_context", "Review IK setup in Object mode.")
    bone = rig.pose.bones.get(spec["bone"])
    if bone is None:
        raise RecipeError("bone_not_found", "IK owner bone was not found.")
    if spec["constraint"] in bone.constraints:
        raise RecipeError("name_conflict", "IK constraint name already exists.")
    chain = []
    current = bone
    for _ in range(spec["chain_count"]):
        if current is None:
            raise RecipeError("invalid_arguments", "IK chain exceeds available ancestors.")
        if current.constraints or current.bone.length <= 1e-8:
            raise RecipeError("unsupported_source", "IK setup requires a nonzero unconstrained chain.")
        chain.append(current)
        current = current.parent
    bpy.context.view_layer.update()
    if (any(not math.isfinite(value) for obj in controls for row in obj.matrix_world for value in row)
            or any(not math.isfinite(value) for item in rig.pose.bones
                   for matrix in (item.matrix_basis,item.bone.matrix_local) for row in matrix for value in row)):
        raise RecipeError("invalid_scene_data", "IK transforms must be finite.")
    if abs(rig.matrix_world.determinant()) < 1e-12:
        raise RecipeError("invalid_context", "IK rig transform must be nonsingular.")
    if pole:
        root = rig.matrix_world @ chain[-1].head
        axis = target.matrix_world.translation-root
        direction = pole.matrix_world.translation-root
        if axis.length < 1e-8 or direction.length < 1e-8 or axis.normalized().cross(direction.normalized()).length < 1e-6:
            raise RecipeError("invalid_arguments", "Pole control must define a non-collinear bend plane.")
    return rig,bone,target


def ik_setup_facts(op):
    rig,bone,target = validate_ik_setup(op)
    from .automation import action_curves
    pole = bpy.context.scene.objects.get(op["ik"].get("pole_target")) if op["ik"].get("pole_target") else None
    controls = (rig,target,pole) if pole else (rig,target)
    return {"rig":rig.as_pointer(),"data":rig.data.as_pointer(),"bone":bone.name,
            "target":target.as_pointer(),
            "pole":pole.as_pointer() if pole else None,
            "matrices":[[list(row) for row in obj.matrix_world] for obj in controls],
            "actions":[action_curves(obj.animation_data.action if obj.animation_data else None)
                       for obj in controls],
            "bones":[{"name":item.name,"parent":item.parent.name if item.parent else None,
                      "rest":[list(row) for row in item.bone.matrix_local],
                      "pose":[list(row) for row in item.matrix_basis],
                      "evaluated":[list(row) for row in item.matrix],
                      "ik_settings":{field:getattr(item,field) for field in
                                     ("use_ik_limit_x","use_ik_limit_y","use_ik_limit_z",
                                      "ik_min_x","ik_min_y","ik_min_z","ik_max_x","ik_max_y","ik_max_z",
                                      "ik_stiffness_x","ik_stiffness_y","ik_stiffness_z","ik_stretch")},
                      "length":item.bone.length,"ik_locks":[item.lock_ik_x,item.lock_ik_y,item.lock_ik_z],
                      "constraints":_constraint_info(item.constraints)} for item in rig.pose.bones]}


def create_ik_setup(op, created_constraints):
    rig,bone,target = validate_ik_setup(op)
    spec = op["ik"]
    constraint = bone.constraints.new("IK")
    created_constraints.append((bone,constraint))
    constraint.name = spec["constraint"]
    constraint.target = target
    if spec.get("pole_target"):
        constraint.pole_target = bpy.context.scene.objects[spec["pole_target"]]
        constraint.pole_angle = spec.get("pole_angle",0.0)
    constraint.chain_count = spec["chain_count"]
    constraint.iterations = spec.get("iterations",64)
    constraint.use_tail = True
    constraint.use_stretch = False
    constraint.use_location = True
    constraint.use_rotation = False
    constraint.influence = 1.0
    if (constraint.name != spec["constraint"] or constraint.target != target
            or constraint.chain_count != spec["chain_count"]):
        raise RecipeError("native_verification_failed", "Native IK settings differ from the preview.")
    bpy.context.view_layer.update()
    if spec.get("pole_target") and (constraint.pole_target.name != spec["pole_target"]
            or abs(constraint.pole_angle-spec.get("pole_angle",0.0)) > 1e-6):
        raise RecipeError("native_verification_failed", "Native pole settings differ from the preview.")
    if any(not math.isfinite(value) for row in bone.matrix for value in row):
        raise RecipeError("native_verification_failed", "Native IK evaluation is non-finite.")
    evaluated = rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tail = evaluated.matrix_world @ evaluated.pose.bones[bone.name].tail
    target_world = target.matrix_world.translation
    distance = (tail-target_world).length
    if not math.isfinite(distance):
        raise RecipeError("native_verification_failed", "Native IK target distance is non-finite.")
    return {"pole_target":spec.get("pole_target"),"pole_angle":spec.get("pole_angle",0.0),
            "evaluated_tail_world":list(tail),"target_world":list(target_world),
            "target_distance_world":distance,"position_tolerance_world":1e-4,
            "target_reached":distance <= 1e-4,"coordinate_space":"blender_world",
            "warnings":[] if distance <= 1e-4 else [{"code":"ik_target_not_reached",
                "message":"Constraint created, but evaluated tip remains outside tolerance; review reach, rest bend and pole angle."}],
            "evaluated_frame":bpy.context.scene.frame_current}


def _constraint_info(constraints):
    """Fixed public properties only; inspecting constraints never evaluates scripts."""
    output = []
    for constraint in list(constraints)[:32]:
        item = {"name":constraint.name,"type":constraint.type,
                "muted":bool(constraint.mute),"influence":float(constraint.influence),
                "valid":bool(constraint.is_valid),
                "owner_space":constraint.owner_space,"target_space":constraint.target_space}
        for field in ("target", "pole_target"):
            if hasattr(constraint,field):
                target = getattr(constraint,field)
                item[field] = {"name":target.name,"type":target.type} if target else None
        for field in ("subtarget", "pole_subtarget"):
            if hasattr(constraint,field):
                item[field] = getattr(constraint,field)
        if constraint.type == "IK":
            item["ik"] = {field:getattr(constraint,field) for field in
                          ("chain_count","iterations","pole_angle","use_tail","use_stretch",
                           "use_location","use_rotation")}
        numbers = [item["influence"]] + list(item.get("ik",{}).values())
        if any(isinstance(value,(float,int)) and not math.isfinite(value) for value in numbers):
            raise RecipeError("invalid_scene_data", "Constraint contains non-finite settings.")
        output.append(item)
    return {"count":len(constraints),"items":output,"truncated":len(constraints)>32}


def rig_info(name, include_weights=False, include_evaluated=False):
    if (not isinstance(name, str) or not 1 <= len(name) <= 64 or
            type(include_weights) is not bool or type(include_evaluated) is not bool):
        raise RecipeError("invalid_arguments", "Expected an armature name and boolean weight flag.")
    scene = bpy.context.scene
    armature = scene.objects.get(name) if scene else None
    if armature is None or armature.type != "ARMATURE":
        raise RecipeError("rig_not_found", "Named armature was not found in the active scene.")

    all_bones = list(armature.data.bones)
    if sum(len(bone.constraints) for bone in armature.pose.bones) > 512:
        raise RecipeError("operation_too_large", "Rig inspection supports at most 512 pose constraints.")
    evaluated = None
    if include_evaluated:
        if len(all_bones) > 256:
            raise RecipeError("operation_too_large", "Evaluated pose inspection is limited to 256 bones.")
        if armature.name not in bpy.context.view_layer.objects:
            raise RecipeError("invalid_context", "Armature must be in the active view layer.")
        bpy.context.view_layer.update()
        evaluated = armature.evaluated_get(bpy.context.evaluated_depsgraph_get())
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
                "constraints": _constraint_info(pose_bone.constraints),
                "locks": {"location":list(pose_bone.lock_location),
                          "rotation":list(pose_bone.lock_rotation),"scale":list(pose_bone.lock_scale)},
                "ik_locks": [pose_bone.lock_ik_x,pose_bone.lock_ik_y,pose_bone.lock_ik_z],
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
        if evaluated is not None:
            evaluated_bone = evaluated.pose.bones.get(bone.name)
            if evaluated_bone is None:
                raise RecipeError("invalid_scene_data", "Evaluated bone was not found.")
            world_matrix = evaluated.matrix_world @ evaluated_bone.matrix
            values = {"matrix_armature": [list(row) for row in evaluated_bone.matrix],
                      "matrix_world": [list(row) for row in world_matrix],
                      "head_world": list(evaluated.matrix_world @ evaluated_bone.head),
                      "tail_world": list(evaluated.matrix_world @ evaluated_bone.tail)}
            flat = [value for field in ("matrix_armature", "matrix_world") for row in values[field] for value in row]
            flat += values["head_world"] + values["tail_world"]
            if any(not math.isfinite(float(value)) for value in flat):
                raise RecipeError("invalid_scene_data", "Evaluated pose contains non-finite values.")
            bones[-1]["evaluated_pose"] = values

    scene_objects = scene.objects
    related = []
    scan_limit = 10000
    truncated_objects = len(scene_objects) > scan_limit
    total_vertices_scanned = 0
    total_assignments_scanned = 0
    total_evaluated_vertices = 0
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
        if include_evaluated:
            if len(related) >= 32:
                raise RecipeError("operation_too_large", "Evaluated inspection is limited to 32 related meshes.")
            if obj.name not in bpy.context.view_layer.objects:
                raise RecipeError("invalid_context", "Related meshes must be in the active view layer.")
            evaluated_object = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            evaluated_mesh = None
            try:
                evaluated_mesh = evaluated_object.to_mesh()
                if evaluated_mesh is None:
                    raise RecipeError("invalid_scene_data", "Related mesh has no evaluated geometry.")
                total_evaluated_vertices += len(evaluated_mesh.vertices)
                if total_evaluated_vertices > 100_000:
                    raise RecipeError("operation_too_large", "Evaluated inspection is limited to 100000 total vertices.")
                points = []
                low, high = [math.inf] * 3, [-math.inf] * 3
                for vertex in evaluated_mesh.vertices:
                    point = list(evaluated_object.matrix_world @ vertex.co)
                    if any(not math.isfinite(value) for value in point):
                        raise RecipeError("invalid_scene_data", "Evaluated mesh contains non-finite positions.")
                    for axis in range(3):
                        low[axis] = min(low[axis], point[axis])
                        high[axis] = max(high[axis], point[axis])
                    if len(points) < 256:
                        points.append(point)
                entry["evaluated_mesh"] = {
                    "frame": scene.frame_current,
                    "vertex_count": len(evaluated_mesh.vertices),
                    "face_count": len(evaluated_mesh.polygons),
                    "world_vertices": points,
                    "vertices_truncated": len(evaluated_mesh.vertices) > len(points),
                    "world_bounds_min": low if points else None,
                    "world_bounds_max": high if points else None,
                    "includes_modifier_stack": True,
                    "coordinate_space": "blender_world",
                    "vertex_indices_match_source": False,
                }
            finally:
                if evaluated_mesh is not None:
                    evaluated_object.to_mesh_clear()
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
            weight_samples, sample_assignments = [], 0
            samples_truncated = len(obj.data.vertices) > 128
            for vertex in obj.data.vertices:
                vertex_weights = []
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
                    if vertex.index < 128:
                        if sample_assignments < 512:
                            vertex_weights.append({"bone": bone_name, "weight": weight})
                            sample_assignments += 1
                        else:
                            samples_truncated = True
                if vertex.index < 128:
                    weight_samples.append({"vertex": vertex.index, "weights": vertex_weights})
            entry["skin_weights"] = stats
            entry["vertex_weight_samples"] = weight_samples
            entry["vertex_weight_samples_truncated"] = samples_truncated
            entry["weight_assignments_scanned"] = assignment_count
            entry["vertices_scanned"] = entry["vertices"]
        related.append(entry)

    return {
        "name": armature.name,
        "object_constraints": _constraint_info(armature.constraints),
        "data": armature.data.name,
        "bone_count": len(all_bones),
        "bones": bones,
        "bones_truncated": len(all_bones) > len(bones),
        "related_meshes": related,
        "related_meshes_truncated": truncated_objects,
        "weights_included": include_weights,
        "evaluated_pose_included": include_evaluated,
        "evaluated_meshes_included": include_evaluated,
        "evaluated_frame": scene.frame_current if include_evaluated else None,
    }
