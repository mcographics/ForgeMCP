"""Disposable native binding, deformation, stale preview and rollback acceptance."""

import sys
from pathlib import Path
from unittest.mock import patch

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge import skinning
from majestic_forge.automation import RecipeError, SceneAutomation
from majestic_forge.rigging import rig_info

automation = SceneAutomation()
source = bpy.data.objects["Cube"]
original_data = source.data
original_vertices = [list(vertex.co) for vertex in original_data.vertices]
original_selection = list(bpy.context.selected_objects)
original_active = bpy.context.view_layer.objects.active
creation = automation.preview({"operations": [{"op": "create_armature", "name": "SkinRig", "bones": [
    {"name": "Root", "head": [0,0,0], "tail": [0,0,1]},
    {"name": "Child", "head": [0,0,1], "tail": [0,0,2], "parent": "Root", "connected": True},
]}]})
assert automation.apply(creation["preview_id"],creation["preview_id"])["state"] == "completed"
rig = bpy.data.objects["SkinRig"]
weights = [item for index in range(8) for item in (
    {"vertex": index, "bone": "Root", "weight": 0.75},
    {"vertex": index, "bone": "Child", "weight": 0.25})]
op = {"op": "bind_mesh", "source": "Cube", "name": "SkinCopy", "armature": "SkinRig", "weights": weights}


def rejected(code, callback):
    try:
        callback()
    except RecipeError as error:
        assert error.code == code, (error.code, code)
    else:
        raise AssertionError(f"Expected {code}")


counts = (len(bpy.data.objects), len(bpy.data.meshes))
preview = automation.preview({"operations": [op]})
assert counts == (len(bpy.data.objects), len(bpy.data.meshes))
rig.location.x += 0.1
rejected("stale_preview", lambda: automation.apply(preview["preview_id"],preview["preview_id"]))
rig.location.x -= 0.1
preview = automation.preview({"operations": [op]})
source.data.vertices[0].co.x += 0.2
rejected("stale_preview", lambda: automation.apply(preview["preview_id"],preview["preview_id"]))
source.data.vertices[0].co.x -= 0.2
for invalid in (
    weights[:-1], weights + [weights[0]],
    [{**item, "bone": "Missing"} if i == 0 else item for i,item in enumerate(weights)],
    [{**item, "weight": float("nan")} if i == 0 else item for i,item in enumerate(weights)],
    [{**item, "vertex": 8} if i == 0 else item for i,item in enumerate(weights)],
):
    rejected("invalid_arguments", lambda: automation.preview({"operations": [{**op, "weights": invalid}]}))
preview = automation.preview({"operations": [op]})
applied = automation.apply(preview["preview_id"],preview["preview_id"])
assert applied["state"] == "completed" and not applied["saved"]
copy = bpy.data.objects["SkinCopy"]
assert copy.data != original_data and source.data == original_data
assert not source.vertex_groups and not source.modifiers
assert copy.modifiers[0].object == rig and not copy.modifiers[0].use_bone_envelopes
assert [list(vertex.co) for vertex in original_data.vertices] == original_vertices
rejected("preview_not_found", lambda: automation.apply(preview["preview_id"],preview["preview_id"]))
rejected("name_conflict", lambda: automation.preview({"operations": [op]}))
rejected("unsupported_source", lambda: automation.preview({"operations": [{**op,"name":"Another","source":"SkinCopy"}]}))
rest = rig_info("SkinRig", include_weights=True, include_evaluated=True)
skin = rest["related_meshes"][0]["skin_weights"]
assert skin["Root"]["weighted_vertices"] == 8 and abs(skin["Root"]["weight_sum"] - 6) < 1e-6
assert skin["Child"]["weighted_vertices"] == 8 and abs(skin["Child"]["weight_sum"] - 2) < 1e-6
rest_points = rest["related_meshes"][0]["evaluated_mesh"]["world_vertices"]
assert all(abs(a-b) < 1e-5 for actual,expected in zip(rest_points,original_vertices) for a,b in zip(actual,expected))
animation = automation.preview({"operations": [
    {"op":"bone_keyframe","name":"SkinRig","bone":"Root","frame":1,"data_path":"location","value":[0,0,0]},
    {"op":"bone_keyframe","name":"SkinRig","bone":"Root","frame":20,"data_path":"location","value":[0,1,0]},
]})
assert automation.apply(animation["preview_id"],animation["preview_id"])["state"] == "completed"
bpy.context.scene.frame_set(20)
end = rig_info("SkinRig", include_evaluated=True)["related_meshes"][0]["evaluated_mesh"]
assert all(abs(actual[2] - expected[2] - 1) < 1e-5 for actual,expected in zip(end["world_vertices"],rest_points))
bpy.context.scene.frame_set(1)
# Reweight an existing skin into a separate version, preserving original weights.
reweight = {"op":"reweight_mesh","source":"SkinCopy","name":"ReweightedSkin",
            "armature":"SkinRig","weights":[{"vertex":index,"bone":"Child","weight":1.0} for index in range(8)]}
original_weights = [[(assignment.group, assignment.weight) for assignment in vertex.groups] for vertex in copy.data.vertices]
copy.modifiers[0].use_deform_preserve_volume = True
preview = automation.preview({"operations":[reweight]})
copy.vertex_groups["Root"].add([0],0.5,"REPLACE")
rejected("stale_preview", lambda: automation.apply(preview["preview_id"],preview["preview_id"]))
copy.vertex_groups["Root"].add([0],0.75,"REPLACE")
preview = automation.preview({"operations":[reweight]})
reweighted = automation.apply(preview["preview_id"],preview["preview_id"])
assert reweighted["state"] == "completed", reweighted
edited = bpy.data.objects["ReweightedSkin"]
assert edited.data != copy.data and copy.data != original_data
assert edited.modifiers[0].use_deform_preserve_volume
assert [[(assignment.group, assignment.weight) for assignment in vertex.groups] for vertex in copy.data.vertices] == original_weights
assert [group.name for group in edited.vertex_groups] == ["Child"]
rig.pose.bones["Child"].rotation_mode = "XYZ"
rig.pose.bones["Child"].rotation_euler.z = 0.6
bpy.context.view_layer.update()
deformation = rig_info("SkinRig", include_weights=True, include_evaluated=True)
observed_edit = next(item for item in deformation["related_meshes"] if item["name"] == "ReweightedSkin")
observed_original = next(item for item in deformation["related_meshes"] if item["name"] == "SkinCopy")
assert observed_edit["skin_weights"]["Child"]["weight_sum"] == 8
assert observed_original["skin_weights"]["Root"]["weight_sum"] == 6
assert not observed_edit["vertex_weight_samples_truncated"]
assert observed_edit["vertex_weight_samples"] == [{"vertex":index,"weights":[{"bone":"Child","weight":1.0}]} for index in range(8)]
assert observed_original["vertex_weight_samples"][0]["weights"] == [{"bone":"Root","weight":0.75},{"bone":"Child","weight":0.25}]
skin_matrix = rig.pose.bones["Child"].matrix @ rig.data.bones["Child"].matrix_local.inverted()
expected_edit = [list(skin_matrix @ vertex.co) for vertex in original_data.vertices]
actual_edit = observed_edit["evaluated_mesh"]["world_vertices"]
assert all(abs(a-b) < 1e-5 for actual,expected in zip(actual_edit,expected_edit) for a,b in zip(actual,expected))
assert actual_edit != observed_original["evaluated_mesh"]["world_vertices"]
rig.pose.bones["Child"].rotation_euler.z = 0
bpy.context.view_layer.update()
copy.modifiers[0].use_bone_envelopes = True
rejected("unsupported_source", lambda: automation.preview({"operations":[{**reweight,"name":"BadSkin"}]}))
copy.modifiers[0].use_bone_envelopes = False
counts = (len(bpy.data.objects), len(bpy.data.meshes))
rollback_op = {**op,"name":"RollbackSkin"}
preview = automation.preview({"operations":[rollback_op]})
native_bind = skinning.bind_copy


def fail_after_native_binding(operation, created):
    native_bind(operation,created)
    raise RuntimeError("fixture: failed after real native binding")


with patch.object(skinning,"bind_copy",side_effect=fail_after_native_binding):
    failed = automation.apply(preview["preview_id"],preview["preview_id"])
assert failed["state"] == "rolled_back" and not failed["rollback_errors"], failed
assert counts == (len(bpy.data.objects), len(bpy.data.meshes))
assert "RollbackSkin" not in bpy.data.objects
reweight_rollback = {**reweight,"name":"RollbackReweight"}
preview = automation.preview({"operations":[reweight_rollback]})
with patch.object(skinning,"bind_copy",side_effect=fail_after_native_binding):
    failed_reweight = automation.apply(preview["preview_id"],preview["preview_id"])
assert failed_reweight["state"] == "rolled_back", failed_reweight
assert counts == (len(bpy.data.objects), len(bpy.data.meshes))
assert [[(assignment.group, assignment.weight) for assignment in vertex.groups] for vertex in copy.data.vertices] == original_weights
assert source.data == original_data and [list(vertex.co) for vertex in original_data.vertices] == original_vertices
# Preserve parenting and world transforms when reweighting a transformed rig.
copy.parent = rig
rig.location = (4, -3, 2)
rig.scale = (2, 0.5, 1.5)
rig.pose.bones["Child"].rotation_euler.z = 0.6
bpy.context.view_layer.update()
source_world = copy.matrix_world.copy()
parented_op = {**reweight,"name":"ParentedReweight"}
preview = automation.preview({"operations":[parented_op]})
assert automation.apply(preview["preview_id"],preview["preview_id"])["state"] == "completed"
parented_copy = bpy.data.objects["ParentedReweight"]
assert parented_copy.parent == rig and parented_copy.matrix_world == source_world
assert copy.matrix_world == source_world
deformation = rig_info("SkinRig", include_evaluated=True)
observed = next(item["evaluated_mesh"]["world_vertices"] for item in deformation["related_meshes"] if item["name"] == parented_copy.name)
world_skin = rig.matrix_world @ rig.pose.bones["Child"].matrix @ rig.data.bones["Child"].matrix_local.inverted() @ rig.matrix_world.inverted() @ source_world
expected = [list(world_skin @ vertex.co) for vertex in original_data.vertices]
assert all(abs(a-b) < 1e-5 for actual,wanted in zip(observed,expected) for a,b in zip(actual,wanted))
assert list(bpy.context.selected_objects) == original_selection
assert bpy.context.view_layer.objects.active == original_active
print("FORGEMCP_NATIVE_SKIN_BIND_WEIGHTS_ANIMATION_STALE_REPLAY_ROLLBACK_PASS")
