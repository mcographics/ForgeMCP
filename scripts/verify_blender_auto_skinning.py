"""Native heat-weight binding and solver-failure acceptance in factory Blender."""

import sys
from pathlib import Path
from unittest.mock import patch

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge import skinning
from majestic_forge.automation import SceneAutomation
from majestic_forge.rigging import rig_info

bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16)
source = bpy.context.object
source.name = "AutoSkinSource"
automation = SceneAutomation()
plan = automation.preview({"operations":[{"op":"create_armature","name":"AutoSkinRig","bones":[
    {"name":"Root","head":[0,0,-0.8],"tail":[0,0,0]},
    {"name":"Tip","head":[0,0,0],"tail":[0,0,0.8],"parent":"Root","connected":True},
]}]})
assert automation.apply(plan["preview_id"],plan["preview_id"])["state"] == "completed"
rig = bpy.data.objects["AutoSkinRig"]
source.location = rig.location = (3, -2, 1)
source.scale = rig.scale = (1.4, 0.8, 1.1)
bpy.context.view_layer.update()
source_world = source.matrix_world.copy()
before = (len(bpy.data.meshes),len(bpy.data.objects),source.data.as_pointer(),
          [list(vertex.co) for vertex in source.data.vertices],tuple(bpy.context.selected_objects),
          bpy.context.view_layer.objects.active)
operation = {"op":"auto_bind_mesh","source":source.name,"armature":rig.name,"name":"AutoSkinCopy",
             "weight_method":"blender_heat_top4"}
plan = automation.preview({"operations":[operation]})
assert (len(bpy.data.meshes),len(bpy.data.objects)) == before[:2]
assert plan["changes"][0]["weight_method"] == "blender_heat_top4"
applied = automation.apply(plan["preview_id"],plan["preview_id"])
assert applied["state"] == "completed", applied
copy = bpy.data.objects["AutoSkinCopy"]
assert len(copy.data.vertices) > 128
assert copy.data != source.data and copy.parent == rig
assert copy.matrix_world == source_world and source.matrix_world == source_world
for vertex in copy.data.vertices:
    assert 1 <= len(vertex.groups) <= 4
    assert abs(sum(assignment.weight for assignment in vertex.groups) - 1) < 1e-5
assert source.data.as_pointer() == before[2] and not source.modifiers and not source.vertex_groups
assert [list(vertex.co) for vertex in source.data.vertices] == before[3]
assert tuple(bpy.context.selected_objects) == before[4] and bpy.context.view_layer.objects.active == before[5]
rest = rig_info(rig.name, include_weights=True,include_evaluated=True)
rest_points = rest["related_meshes"][0]["evaluated_mesh"]["world_vertices"]
expected_rest = [list(source_world @ vertex.co) for vertex in source.data.vertices][:256]
assert all(abs(a-b) < 1e-5 for actual,expected in zip(rest_points,expected_rest) for a,b in zip(actual,expected))
rig.pose.bones["Tip"].rotation_mode = "XYZ"
rig.pose.bones["Tip"].rotation_euler.z = 0.5
bpy.context.view_layer.update()
deformed = rig_info(rig.name,include_evaluated=True)
points = deformed["related_meshes"][0]["evaluated_mesh"]["world_vertices"]
assert any(abs(a-b) > 0.01 for actual,expected in zip(points,rest_points) for a,b in zip(actual,expected))
rig.pose.bones["Tip"].rotation_euler.z = 0
bpy.context.view_layer.update()
counts = len(bpy.data.meshes),len(bpy.data.objects)
plan = automation.preview({"operations":[{**operation,"name":"AutoSkinFailure"}]})
with patch.object(skinning,"_run_heat",return_value={"CANCELLED"}):
    failed = automation.apply(plan["preview_id"],plan["preview_id"])
assert failed["state"] == "rolled_back" and failed["error"]["code"] == "automatic_weights_failed", failed
assert (len(bpy.data.meshes),len(bpy.data.objects)) == counts
assert tuple(bpy.context.selected_objects) == before[4] and bpy.context.view_layer.objects.active == before[5]
native_heat = skinning._run_heat


def incomplete_solver(obj, armature):
    result = native_heat(obj,armature)
    for group in obj.vertex_groups:
        group.remove([0])
    return result


plan = automation.preview({"operations":[{**operation,"name":"IncompleteAutoSkin"}]})
with patch.object(skinning,"_run_heat",side_effect=incomplete_solver):
    incomplete = automation.apply(plan["preview_id"],plan["preview_id"])
assert incomplete["state"] == "rolled_back" and incomplete["error"]["code"] == "automatic_weights_failed", incomplete
assert (len(bpy.data.meshes),len(bpy.data.objects)) == counts
assert source.data.as_pointer() == before[2] and not source.vertex_groups
original_weights = [[(copy.vertex_groups[a.group].name, a.weight) for a in vertex.groups]
                    for vertex in copy.data.vertices]
patch_op = {"op":"patch_skin_weights","source":copy.name,"armature":rig.name,
            "name":"PatchedSkin","weights":[{"vertex":300,"bone":"Root","weight":1.0}]}
plan = automation.preview({"operations":[patch_op]})
patched_result = automation.apply(plan["preview_id"],plan["preview_id"])
assert patched_result["state"] == "completed", patched_result
patched = bpy.data.objects["PatchedSkin"]
for vertex in patched.data.vertices:
    actual = [(patched.vertex_groups[a.group].name, a.weight) for a in vertex.groups]
    assert actual == ([("Root",1.0)] if vertex.index == 300 else original_weights[vertex.index])
assert [[(copy.vertex_groups[a.group].name,a.weight) for a in v.groups]
        for v in copy.data.vertices] == original_weights
counts = len(bpy.data.meshes),len(bpy.data.objects)
plan = automation.preview({"operations":[{**patch_op,"name":"StalePatchedSkin"}]})
copy.vertex_groups["Root"].add([300],0.123,"REPLACE")
try:
    automation.apply(plan["preview_id"],plan["preview_id"])
except Exception as error:
    assert getattr(error,"code",None) == "stale_preview", error
else:
    raise AssertionError("Changed source weights did not invalidate preview")
for group in copy.vertex_groups:
    group.remove([300])
for bone,weight in original_weights[300]:
    copy.vertex_groups[bone].add([300],weight,"REPLACE")
native_bind = skinning.bind_copy


def fail_after_patch(*args,**kwargs):
    native_bind(*args,**kwargs)
    raise RuntimeError("Injected failure after native partial-weight edit")


plan = automation.preview({"operations":[{**patch_op,"name":"FailedPatchedSkin"}]})
with patch.object(skinning,"bind_copy",side_effect=fail_after_patch):
    failed_patch = automation.apply(plan["preview_id"],plan["preview_id"])
assert failed_patch["state"] == "rolled_back", failed_patch
assert (len(bpy.data.meshes),len(bpy.data.objects)) == counts
assert bpy.data.objects.get("FailedPatchedSkin") is None
page = skinning.skin_info(patched.name,300,2)
assert page["vertices_returned"] == 2 and page["next_vertex_start"] == 302
assert page["vertices"][0]["weights"][0]["bone"] == "Root"
assert skinning.skin_info(patched.name,len(patched.data.vertices)-1,128)["next_vertex_start"] is None
for start,count in ((True,2),(300,False),(9999,2),(0,129)):
    try:
        skinning.skin_info(patched.name,start,count)
    except Exception as error:
        assert getattr(error,"code",None) == "invalid_arguments", error
    else:
        raise AssertionError("Invalid skin page accepted")
print("FORGEMCP_NATIVE_HEAT_WEIGHTS_PARTIAL_PATCH_PAGING_SOURCE_PRESERVATION_PASS")
