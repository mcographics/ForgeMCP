"""Validate armature creation and inspection in a disposable factory-startup scene."""

import os
import sys
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge
from majestic_forge.automation import SceneAutomation
from majestic_forge.rigging import rig_info

assert majestic_forge.bl_info["name"] == "ForgeMCP"
assert majestic_forge.MAJESTICFORGE_PT_Connection.bl_category == "ForgeMCP"
assert majestic_forge.MAJESTICFORGE_PT_Connection.bl_label == "ForgeMCP Connection"

before = {obj.name for obj in bpy.context.scene.objects}
bpy.ops.object.armature_add(enter_editmode=False, location=(0.0, 0.0, 0.0))
armature = bpy.context.object
armature.name = "ForgeRigProbe"
armature.data.name = "ForgeRigProbeData"
bpy.ops.object.mode_set(mode="EDIT")
root = armature.data.edit_bones[0]
root.name = "Root"
root.head = (0.0, 0.0, 0.0)
root.tail = (0.0, 0.0, 1.0)
child = armature.data.edit_bones.new("Child")
child.head = root.tail
child.tail = (0.0, 0.0, 2.0)
child.parent = root
child.use_connect = True
bpy.ops.object.mode_set(mode="OBJECT")

mesh = bpy.data.meshes.new("ForgeWeightedMeshData")
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
mesh.update()
skinned = bpy.data.objects.new("ForgeWeightedMesh", mesh)
bpy.context.scene.collection.objects.link(skinned)
skinned.parent = armature
modifier = skinned.modifiers.new("ForgeArmature", "ARMATURE")
modifier.object = armature
root_group = skinned.vertex_groups.new(name="Root")
child_group = skinned.vertex_groups.new(name="Child")
root_group.add([0, 1], 0.75, "REPLACE")
child_group.add([1, 2], 0.25, "REPLACE")

structure = rig_info("ForgeRigProbe")
assert structure["bone_count"] == 2
assert [bone["name"] for bone in structure["bones"]] == ["Root", "Child"]
assert structure["bones"][1]["parent"] == "Root" and structure["bones"][1]["connected"]
assert len(structure["related_meshes"]) == 1
assert not structure["weights_included"]
weights = rig_info("ForgeRigProbe", True)
skin = weights["related_meshes"][0]["skin_weights"]
assert skin["Root"]["weighted_vertices"] == 2 and abs(skin["Root"]["weight_sum"] - 1.5) < 1e-6
assert skin["Child"]["weighted_vertices"] == 2 and abs(skin["Child"]["weight_sum"] - 0.5) < 1e-6
assert weights["related_meshes"][0]["weight_assignments_scanned"] == 4
original_vertices = [list(vertex.co) for vertex in mesh.vertices]
before_evaluation = (len(bpy.data.meshes), len(bpy.data.objects), bpy.context.scene.frame_current)
rest = rig_info("ForgeRigProbe", include_evaluated=True)
rest_mesh = rest["related_meshes"][0]["evaluated_mesh"]
assert rest_mesh["vertex_count"] == 3 and not rest_mesh["vertices_truncated"]
# Blender bone-local Y is aligned with this bone's world Z axis.
armature.pose.bones["Root"].location = (0, 1, 0)
bpy.context.view_layer.update()
deformed = rig_info("ForgeRigProbe", include_evaluated=True)
deformed_mesh = deformed["related_meshes"][0]["evaluated_mesh"]
assert abs(deformed_mesh["world_vertices"][0][2] - rest_mesh["world_vertices"][0][2] - 1.0) < 1e-5
assert deformed_mesh["world_vertices"] != rest_mesh["world_vertices"]
assert [list(vertex.co) for vertex in mesh.vertices] == original_vertices
assert before_evaluation == (len(bpy.data.meshes), len(bpy.data.objects), bpy.context.scene.frame_current)
armature.pose.bones["Root"].location = (0, 0, 0)
bpy.context.view_layer.update()
pose_automation = SceneAutomation()
animation = pose_automation.preview({"operations": [
    {"op": "bone_keyframe", "name": armature.name, "bone": "Root", "data_path": "location",
     "frame": 1, "value": [0, 0, 0]},
    {"op": "bone_keyframe", "name": armature.name, "bone": "Root", "data_path": "location",
     "frame": 20, "value": [0, 1, 0]},
]})
assert pose_automation.apply(animation["preview_id"], animation["preview_id"])["state"] == "completed"
bpy.context.scene.frame_set(20)
animated_end = rig_info(armature.name, include_evaluated=True)["related_meshes"][0]["evaluated_mesh"]
assert animated_end["frame"] == 20
assert abs(animated_end["world_vertices"][0][2] - 1) < 1e-5
bpy.context.scene.frame_set(1)
animated_start = rig_info(armature.name, include_evaluated=True)["related_meshes"][0]["evaluated_mesh"]
assert animated_start["world_vertices"] == rest_mesh["world_vertices"]
assert [list(vertex.co) for vertex in mesh.vertices] == original_vertices
# Errors after to_mesh() must release the temporary native mesh too.
skinned.location.x = float("nan")
bpy.context.view_layer.update()
try:
    rig_info(armature.name, include_evaluated=True)
except Exception as error:
    assert getattr(error, "code", None) == "invalid_scene_data"
else:
    raise AssertionError("Non-finite evaluated geometry must be rejected")
skinned.location.x = 0
bpy.context.view_layer.update()
assert len(bpy.data.meshes) == before_evaluation[0]
# Samples are bounded, but bounds must cover vertices outside the sample.
large_mesh = bpy.data.meshes.new("ForgeEvaluatedSampleLimit")
large_mesh.from_pydata([(index, 0, 0) for index in range(300)], [], [])
large_mesh.update()
large_object = bpy.data.objects.new("ForgeEvaluatedSampleLimit", large_mesh)
bpy.context.scene.collection.objects.link(large_object)
large_object.parent = armature
try:
    sampled = rig_info(armature.name, include_evaluated=True)
    observed = next(item["evaluated_mesh"] for item in sampled["related_meshes"] if item["name"] == large_object.name)
    assert len(observed["world_vertices"]) == 256 and observed["vertices_truncated"]
    assert observed["vertex_count"] == 300 and observed["world_bounds_max"] == [299, 0, 0]
finally:
    bpy.data.objects.remove(large_object, do_unlink=True)
    bpy.data.meshes.remove(large_mesh)
assert len(bpy.data.meshes) == before_evaluation[0]
try:
    rig_info("Cube")
except Exception as error:
    assert getattr(error, "code", None) == "rig_not_found"
else:
    raise AssertionError("A mesh object must not be accepted as an armature.")
assert before.issubset({obj.name for obj in bpy.context.scene.objects})

selected_before = {obj.name for obj in bpy.context.selected_objects}
ik_target = bpy.data.objects.new("ForgeRigIKTarget",None)
bpy.context.scene.collection.objects.link(ik_target)
ik_target.location = (0.5,0,1.5)
ik = armature.pose.bones["Child"].constraints.new("IK")
ik.name = "ForgeInspectIK"
ik.target = ik_target
ik.chain_count = 2
ik.iterations = 64
ik.pole_angle = 0.25
ik.use_stretch = False
ik.mute = True
armature.pose.bones["Child"].lock_ik_x = True
constraint_before = (len(bpy.data.objects),bpy.context.scene.frame_current,ik.as_pointer())
constraint_report = rig_info(armature.name)
child_pose = constraint_report["bones"][1]["pose"]
assert child_pose["constraints"]["count"] == 1 and not child_pose["constraints"]["truncated"]
assert child_pose["ik_locks"] == [True,False,False]
reported_ik = child_pose["constraints"]["items"][0]
assert reported_ik["target"] == {"name":ik_target.name,"type":"EMPTY"}
assert reported_ik["muted"] and reported_ik["ik"]["chain_count"] == 2
assert reported_ik["ik"]["iterations"] == 64 and not reported_ik["ik"]["use_stretch"]
assert abs(reported_ik["ik"]["pole_angle"]-0.25) < 1e-6
assert constraint_before == (len(bpy.data.objects),bpy.context.scene.frame_current,ik.as_pointer())
assert {obj.name for obj in bpy.context.selected_objects} == selected_before
root_constraints = armature.pose.bones["Root"].constraints
for index in range(33):
    extra = root_constraints.new("LIMIT_LOCATION")
    extra.mute = True
bounded = rig_info(armature.name)["bones"][0]["pose"]["constraints"]
assert bounded["count"] == 33 and len(bounded["items"]) == 32 and bounded["truncated"]
for index in range(479):
    extra = root_constraints.new("LIMIT_LOCATION")
    extra.mute = True
try:
    rig_info(armature.name)
except Exception as error:
    assert getattr(error,"code",None) == "operation_too_large", error
else:
    raise AssertionError("Excessive constraint inspection was not rejected")
for extra in list(root_constraints):
    root_constraints.remove(extra)
active_before = bpy.context.view_layer.objects.active
rig_automation = SceneAutomation()
create_rig_recipe = {"operations": [{
    "op": "create_armature",
    "name": "ForgeRigCreatedByRecipe",
    "bones": [
        {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
        {"name": "Spine", "head": [0, 0, 1], "tail": [0, 0, 2],
         "parent": "Root", "connected": True},
    ],
}]}
object_count_before_preview = len(bpy.context.scene.objects)
preview = rig_automation.preview(create_rig_recipe)
assert len(bpy.context.scene.objects) == object_count_before_preview
created = rig_automation.apply(preview["preview_id"], preview["preview_id"])
assert created["state"] == "completed" and not created["saved"]
created_rig = rig_info("ForgeRigCreatedByRecipe")
assert created_rig["bone_count"] == 2
assert created_rig["bones"][1]["parent"] == "Root" and created_rig["bones"][1]["connected"]
assert {obj.name for obj in bpy.context.selected_objects} == selected_before
assert bpy.context.view_layer.objects.active == active_before

if os.environ.get("FORGE_VALIDATION_SKIP_BRIDGE") != "1":
    # Larger unbound fixture for MCP automatic binding and partial-weight edits.
    fixture_selected = list(bpy.context.selected_objects)
    fixture_active = bpy.context.view_layer.objects.active
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.8, location=(0,0,1))
    bpy.context.object.name = "ForgeMCPLargeSkinSource"
    bpy.context.object.select_set(False)
    for item in fixture_selected:
        item.select_set(True)
    bpy.context.view_layer.objects.active = fixture_active
    majestic_forge.register()
    try:
        pid_file = Path(os.environ.get("FORGE_VALIDATION_PID_FILE", "Saved/Milestone2/blender-rig-probe.pid"))
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()), encoding="ascii")
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            stop_file = os.environ.get("FORGE_VALIDATION_STOP_FILE")
            if stop_file and Path(stop_file).is_file():
                break
            majestic_forge._tick()
            time.sleep(0.02)
    finally:
        majestic_forge.unregister()
else:
    print("FORGE_BLENDER_RIG_CREATION_FACTORY_VALIDATION_PASS")
