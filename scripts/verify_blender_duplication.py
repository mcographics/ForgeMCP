"""Verify native duplication, independent geometry/Actions, staleness and rollback."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import bpy
from majestic_forge.automation import RecipeError, SceneAutomation

automation = SceneAutomation()
source = bpy.data.objects["Cube"]
source.keyframe_insert(data_path="location", frame=1)
original_mesh, original_action = source.data, source.animation_data.action
recipe = {"operations": [
    {"op": "duplicate_object", "source": "Cube", "name": "ForgeCubeCopy", "location": [3, 0, 0]},
    {"op": "keyframe", "name": "ForgeCubeCopy", "frame": 20},
]}
before = len(bpy.data.objects)
before_actions = len(bpy.data.actions)
preview = automation.preview(recipe)
assert len(bpy.data.objects) == before
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "completed", result
copied = bpy.data.objects["ForgeCubeCopy"]
assert copied.data != original_mesh and copied.animation_data.action != original_action
assert len(bpy.data.actions) == before_actions + 1, "Duplicate keyframing left an unnecessary Action copy"
assert source.data == original_mesh and source.animation_data.action == original_action
source_vertex = original_mesh.vertices[0].co.copy()
copied.data.vertices[0].co.x += 5
assert original_mesh.vertices[0].co == source_vertex
assert copied.location.x == 3
preview = automation.preview({"operations": [{"op": "duplicate_object", "source": "Cube", "name": "ForgeStaleCopy"}]})
source.data.vertices[0].co.x += 1
try:
    automation.apply(preview["preview_id"], preview["preview_id"])
    raise AssertionError("Source geometry changes failed to invalidate duplication")
except RecipeError as error:
    assert error.code == "stale_preview"
before_objects, before_meshes, before_actions = set(bpy.data.objects), set(bpy.data.meshes), set(bpy.data.actions)
result = automation.execute([
    {"op": "duplicate_object", "source": "Cube", "name": "ForgeRollbackCopy"},
    {"op": "set_transform", "name": "ForgeRollbackCopy", "location": ["bad", 0, 0]},
])
assert result["state"] == "rolled_back", result
assert set(bpy.data.objects) == before_objects
assert set(bpy.data.meshes) == before_meshes and set(bpy.data.actions) == before_actions
assert source.data == original_mesh and source.animation_data.action == original_action
assert bpy.data.filepath == ""
print("FORGE_NATIVE_BLENDER_DUPLICATE_INDEPENDENT_MESH_ACTION_STALE_ROLLBACK_PASS")
