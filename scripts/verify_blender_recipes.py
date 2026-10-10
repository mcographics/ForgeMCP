"""Native recipe validation in a factory-startup Blender, never an open user scene."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import bpy
from majestic_forge.automation import RecipeError, SceneAutomation, action_curves, object_info
from majestic_forge.rigging import rig_info

automation = SceneAutomation()
cube = bpy.data.objects["Cube"]
original_mesh = cube.data
original_vertices = [list(v.co) for v in original_mesh.vertices]
original_location = list(cube.location)
recipe = {
    "operations": [
        {"op": "create_collection", "name": "ForgeTestCollection"},
        {"op": "create_material", "name": "ForgeTestMaterial", "color": [0.2, 0.4, 0.8, 1]},
        {
            "op": "create_mesh",
            "name": "ForgeTestTriangle",
            "collection": "ForgeTestCollection",
            "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "faces": [[0, 1, 2]],
        },
        {"op": "assign_material", "name": "ForgeTestTriangle", "material": "ForgeTestMaterial"},
        {"op": "keyframe", "name": "ForgeTestTriangle", "frame": 1},
        {"op": "set_transform", "name": "ForgeTestTriangle", "location": [2, 0, 0]},
        {"op": "keyframe", "name": "ForgeTestTriangle", "frame": 30},
        {"op": "scene_settings", "fps": 30, "frame_start": 1, "frame_end": 60},
    ]
}
before = len(bpy.data.objects)
preview = automation.preview(recipe)
assert len(bpy.data.objects) == before
try:
    automation.apply(preview["preview_id"], "wrong")
    raise AssertionError("Confirmation mismatch accepted")
except RecipeError as error:
    assert error.code == "confirmation_required"
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "completed", result
assert object_info("ForgeTestTriangle")["mesh"]["faces"] == 1
assert bpy.context.scene.render.fps == 30
bpy.context.scene.frame_set(30)
assert abs(bpy.data.objects["ForgeTestTriangle"].location.x - 2) < 1e-6
bpy.context.scene.frame_set(1)
assert abs(bpy.data.objects["ForgeTestTriangle"].location.x) < 1e-6
try:
    automation.apply(preview["preview_id"], preview["preview_id"])
    raise AssertionError("Consumed preview replayed")
except RecipeError as error:
    assert error.code == "preview_not_found"

rig_preview = automation.preview({"operations": [{
    "op": "create_armature",
    "name": "ForgePoseKeyframeRig",
    "bones": [{"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]}],
}]})
rig_apply = automation.apply(rig_preview["preview_id"], rig_preview["preview_id"])
assert rig_apply["state"] == "completed", rig_apply
rig = bpy.data.objects["ForgePoseKeyframeRig"]
pose_bone = rig.pose.bones["Root"]
pose_preview = automation.preview({"operations": [
    {"op": "bone_keyframe", "name": rig.name, "bone": "Root", "data_path": "location",
     "value": [0, 0, 0], "frame": 1},
    {"op": "bone_keyframe", "name": rig.name, "bone": "Root", "data_path": "location",
     "value": [1, 0, 0], "frame": 20},
]})
assert pose_bone.location.x == 0
pose_apply = automation.apply(pose_preview["preview_id"], pose_preview["preview_id"])
assert pose_apply["state"] == "completed", pose_apply
assert len(pose_apply["operations"]) == 2
pose_action = rig.animation_data.action
assert pose_action is not None
assert any(
    'pose.bones["Root"].location' == curve[0]
    for curve in action_curves(pose_action)
)
scene = bpy.context.scene
original_frame = scene.frame_current
scene.frame_set(20)
assert abs(pose_bone.location.x - 1.0) < 1e-6
scene.frame_set(1)
assert abs(pose_bone.location.x) < 1e-6
scene.frame_set(original_frame)
assert rig_info(rig.name)["bones"][0]["pose"]["location"] == list(pose_bone.location)

pose_preview = automation.preview({"operations": [{
    "op": "bone_keyframe", "name": rig.name, "bone": "Root", "data_path": "location",
    "value": [2, 0, 0], "frame": 40,
}]})
pose_bone.location.x += 0.5
try:
    automation.apply(pose_preview["preview_id"], pose_preview["preview_id"])
    raise AssertionError("Pose-bone changes after preview were not detected")
except RecipeError as error:
    assert error.code == "stale_preview"

before_pose = list(pose_bone.location)
before_action = rig.animation_data.action
rollback = automation.execute([
    {"op": "bone_keyframe", "name": rig.name, "bone": "Root", "data_path": "location",
     "value": [3, 0, 0], "frame": 50},
    {"op": "bone_keyframe", "name": rig.name, "bone": "Root", "data_path": "missing",
     "value": [4, 0, 0], "frame": 51},
])
assert rollback["state"] == "rolled_back", rollback
assert list(pose_bone.location) == before_pose
assert rig.animation_data.action == before_action

cube.keyframe_insert(data_path="location", frame=1)
original_action = cube.animation_data.action
preview = automation.preview(
    {
        "operations": [
            {
                "op": "set_vertices",
                "name": "Cube",
                "vertices": [[v[0] * 2, v[1], v[2]] for v in original_vertices],
            },
            {"op": "set_transform", "name": "Cube", "location": [3, 0, 0]},
            {"op": "keyframe", "name": "Cube", "frame": 20},
        ]
    }
)
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "completed", result
assert cube.data != original_mesh
assert [list(v.co) for v in original_mesh.vertices] == original_vertices
assert cube.animation_data.action != original_action
preview = automation.preview(
    {"operations": [{"op": "set_transform", "name": "Cube", "location": [4, 0, 0]}]}
)
cube.location.x += 1
try:
    automation.apply(preview["preview_id"], preview["preview_id"])
    raise AssertionError("Stale preview accepted")
except RecipeError as error:
    assert error.code == "stale_preview"

before_location = list(cube.location)
before_objects, before_meshes = set(bpy.data.objects), set(bpy.data.meshes)
# Fault injection into the internal execution seam: real RNA rejects the bad vector
# after a mesh was created. The public preflight correctly rejects this input earlier.
result = automation.execute(
    [
        {"op": "create_mesh", "name": "ForgeRollbackMesh", "vertices": [[0, 0, 0]], "faces": []},
        {"op": "set_transform", "name": "Cube", "location": ["invalid", 0, 0]},
    ]
)
assert result["state"] == "rolled_back", result
assert set(bpy.data.objects) == before_objects and set(bpy.data.meshes) == before_meshes
assert list(cube.location) == before_location
assert bpy.data.filepath == ""
print("FORGE_NATIVE_BLENDER_RECIPES_PREVIEW_APPLY_OBJECT_AND_BONE_KEYFRAMES_BACKUPS_STALE_REPLAY_ROLLBACK_PASS")
