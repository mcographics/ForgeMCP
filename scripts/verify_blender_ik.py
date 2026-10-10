"""Native reviewed IK creation, target movement, stale rejection and rollback."""

import sys
from pathlib import Path
from unittest.mock import patch

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"blender-addon"))
from majestic_forge import automation as automation_module
from majestic_forge import rigging
from majestic_forge.automation import SceneAutomation

automation = SceneAutomation()
initial = automation.preview({"operations":[
    {"op":"create_armature","name":"IKRig","bones":[
        {"name":"Root","head":[0,0,0],"tail":[0.2,0,1]},
        {"name":"Tip","head":[0.2,0,1],"tail":[0,0,2],"parent":"Root","connected":True}]},
    {"op":"create_empty","name":"IKTarget","location":[0.7,0,1.5]},
    {"op":"create_empty","name":"IKPole","location":[0,2,1]},
    {"op":"create_mesh","name":"IKSkinSource","vertices":[[0,0,2],[0.1,0,2],[0,0.1,2]],
     "faces":[[0,1,2]]}]})
assert automation.apply(initial["preview_id"],initial["preview_id"])["state"] == "completed"
rig,target = bpy.data.objects["IKRig"],bpy.data.objects["IKTarget"]
binding = automation.preview({"operations":[{"op":"bind_mesh","name":"IKSkinCopy",
    "source":"IKSkinSource","armature":rig.name,
    "weights":[{"vertex":index,"bone":"Tip","weight":1.0} for index in range(3)]}]})
assert automation.apply(binding["preview_id"],binding["preview_id"])["state"] == "completed"
op = {"op":"create_ik_constraint","name":rig.name,"ik":{
    "bone":"Tip","constraint":"ForgeIK","target":target.name,"chain_count":2,"iterations":128,
    "pole_target":"IKPole","pole_angle":0.0}}
before = (tuple(bpy.context.selected_objects),bpy.context.view_layer.objects.active,bpy.context.scene.frame_current)
plan = automation.preview({"operations":[op]})
assert not rig.pose.bones["Tip"].constraints
target.location.x = 0.8
bpy.context.view_layer.update()
try:
    automation.apply(plan["preview_id"],plan["preview_id"])
except Exception as error:
    assert getattr(error,"code",None) == "stale_preview", error
else:
    raise AssertionError("Changed IK target accepted")
target.location.x = 0.7
plan = automation.preview({"operations":[op]})
rig.pose.bones["Tip"].ik_stiffness_x = 0.2
try:
    automation.apply(plan["preview_id"],plan["preview_id"])
except Exception as error:
    assert getattr(error,"code",None) == "stale_preview", error
else:
    raise AssertionError("Changed IK stiffness accepted")
rig.pose.bones["Tip"].ik_stiffness_x = 0
plan = automation.preview({"operations":[op]})
pole = bpy.data.objects["IKPole"]
pole.location.x = 0.2
try:
    automation.apply(plan["preview_id"],plan["preview_id"])
except Exception as error:
    assert getattr(error,"code",None) == "stale_preview", error
else:
    raise AssertionError("Changed pole control accepted")
pole.location.x = 0
saved_pole = pole.location.copy()
pole.location = target.location*2
try:
    automation.preview({"operations":[op]})
except Exception as error:
    assert getattr(error,"code",None) == "invalid_arguments", error
else:
    raise AssertionError("Collinear pole plane accepted")
pole.location = saved_pole
plan = automation.preview({"operations":[op]})
native = rigging.create_ik_setup


def fail_after_native(*args):
    native(*args)
    raise RuntimeError("Injected native IK failure")


with patch.object(rigging,"create_ik_setup",side_effect=fail_after_native):
    failed = automation.apply(plan["preview_id"],plan["preview_id"])
assert failed["state"] == "rolled_back", failed
assert not rig.pose.bones["Tip"].constraints
plan = automation.preview({"operations":[op]})
applied = automation.apply(plan["preview_id"],plan["preview_id"])
assert applied["state"] == "completed", applied
assert applied["operations"][0]["target_reached"], applied
constraint = rig.pose.bones["Tip"].constraints["ForgeIK"]
assert constraint.target == target and constraint.chain_count == 2 and not constraint.use_stretch
info = rigging.rig_info(rig.name,include_evaluated=True)
tail = info["bones"][1]["evaluated_pose"]["tail_world"]
assert sum((tail[i]-target.location[i])**2 for i in range(3)) < 1e-5, tail
skin_tip = info["related_meshes"][0]["evaluated_mesh"]["world_vertices"][0]
assert sum((skin_tip[i]-target.location[i])**2 for i in range(3)) < 1e-5, skin_tip
target.location = (-0.6,0,1.4)
bpy.context.view_layer.update()
moved = rigging.rig_info(rig.name,include_evaluated=True)["bones"][1]["evaluated_pose"]["tail_world"]
assert sum((moved[i]-target.location[i])**2 for i in range(3)) < 1e-5, moved
assert moved != tail
joint = rigging.rig_info(rig.name,include_evaluated=True)["bones"][0]["evaluated_pose"]["tail_world"]
pole.location.y = -2
bpy.context.view_layer.update()
pole_moved = rigging.rig_info(rig.name,include_evaluated=True)
new_joint = pole_moved["bones"][0]["evaluated_pose"]["tail_world"]
assert sum((a-b)**2 for a,b in zip(joint,new_joint)) > 0.01, (joint,new_joint)
pole_tail = pole_moved["bones"][1]["evaluated_pose"]["tail_world"]
assert sum((pole_tail[i]-target.location[i])**2 for i in range(3)) < 1e-5, pole_tail
assert constraint.pole_target == pole and abs(constraint.pole_angle) < 1e-6
assert before == (tuple(bpy.context.selected_objects),bpy.context.view_layer.objects.active,bpy.context.scene.frame_current)
flat = automation.preview({"operations":[{"op":"create_armature","name":"FlatIKRig","bones":[
    {"name":"Root","head":[0,0,0],"tail":[0,0,1]},
    {"name":"Tip","head":[0,0,1],"tail":[0,0,2],"parent":"Root","connected":True}]}]})
assert automation.apply(flat["preview_id"],flat["preview_id"])["state"] == "completed"
flat_plan = automation.preview({"operations":[{**op,"name":"FlatIKRig"}]})
flat_result = automation.apply(flat_plan["preview_id"],flat_plan["preview_id"])
assert flat_result["state"] == "completed", flat_result
assert not flat_result["operations"][0]["target_reached"], flat_result
assert flat_result["operations"][0]["target_distance_world"] > 0.01, flat_result
assert flat_result["operations"][0]["warnings"][0]["code"] == "ik_target_not_reached", flat_result
nopole = automation.preview({"operations":[{"op":"create_armature","name":"NoPoleRig","bones":[
    {"name":"Root","head":[0,0,0],"tail":[0,0,1]},
    {"name":"Tip","head":[0,0,1],"tail":[0,0,2],"parent":"Root","connected":True}]}]})
assert automation.apply(nopole["preview_id"],nopole["preview_id"])["state"] == "completed"
nopole_plan = automation.preview({"operations":[{**op,"name":"NoPoleRig",
    "ik":{**op["ik"],"pole_target":None,"pole_angle":0.0}}]})
nopole_result = automation.apply(nopole_plan["preview_id"],nopole_plan["preview_id"])
assert nopole_result["state"] == "completed", nopole_result
assert nopole_result["operations"][0]["target_distance_world"] < 1e-3, nopole_result
assert bpy.data.objects["NoPoleRig"].pose.bones["Tip"].constraints["ForgeIK"].pole_target is None
animation = automation.preview({"operations":[
    {"op":"keyframe","name":target.name,"data_path":"location","frame":1,"value":[0.7,0,1.5]},
    {"op":"keyframe","name":target.name,"data_path":"location","frame":20,"value":[-0.6,0,1.4]}]})
assert automation.apply(animation["preview_id"],animation["preview_id"])["state"] == "completed"
action = target.animation_data.action
sampled = []
for frame in (1,10,20):
    original_frame = bpy.context.scene.frame_current
    timeline = automation.preview({"operations":[{"op":"set_frame","frame":frame}]})
    assert bpy.context.scene.frame_current == original_frame
    changed = automation.apply(timeline["preview_id"],timeline["preview_id"])
    assert changed["state"] == "completed" and changed["operations"][0]["frame"] == frame, changed
    evaluated = rigging.rig_info(rig.name,include_evaluated=True)
    point = evaluated["bones"][1]["evaluated_pose"]["tail_world"]
    mesh_point = evaluated["related_meshes"][0]["evaluated_mesh"]["world_vertices"][0]
    assert sum((point[i]-target.location[i])**2 for i in range(3)) < 1e-5, point
    assert sum((mesh_point[i]-target.location[i])**2 for i in range(3)) < 1e-5, mesh_point
    sampled.append(point)
assert sampled[0] != sampled[1] != sampled[2]
bpy.context.scene.frame_set(20,subframe=0.25)
failed_frame = automation.preview({"operations":[
    {"op":"keyframe","name":target.name,"data_path":"location","frame":25,"value":[0.2,0,1.2]},
    {"op":"set_frame","frame":5}]})
native_set_frame = automation_module._set_frame


def fail_after_frame(scene,frame):
    native_set_frame(scene,frame)
    raise RuntimeError("Injected failure after timeline evaluation")


with patch.object(automation_module,"_set_frame",side_effect=fail_after_frame):
    failure = automation.apply(failed_frame["preview_id"],failed_frame["preview_id"])
assert failure["state"] == "rolled_back" and bpy.context.scene.frame_current == 20, failure
assert abs(bpy.context.scene.frame_subframe-0.25) < 1e-8
assert target.animation_data.action == action
restored_tip = rigging.rig_info(rig.name,include_evaluated=True)["bones"][1]["evaluated_pose"]["tail_world"]
assert sum((a-b)**2 for a,b in zip(restored_tip,sampled[2])) < 1e-8, restored_tip
stale_frame = automation.preview({"operations":[{"op":"set_frame","frame":3}]})
bpy.context.scene.frame_set(7)
try:
    automation.apply(stale_frame["preview_id"],stale_frame["preview_id"])
except Exception as error:
    assert getattr(error,"code",None) == "stale_preview", error
else:
    raise AssertionError("Externally changed timeline accepted stale preview")
assert before[:2] == (tuple(bpy.context.selected_objects),bpy.context.view_layer.objects.active)
print("FORGEMCP_NATIVE_IK_POLE_ANIMATION_TIMELINE_SKIN_ROLLBACK_PASS")
