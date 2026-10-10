"""Test existing material input edits, shared users, staleness and batch rollback."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import bpy
from majestic_forge.automation import RecipeError, SceneAutomation
from majestic_forge.materials import material_info

automation = SceneAutomation()
mat = bpy.data.materials.new("ForgeExistingMaterial")
mat.use_nodes = True
bpy.data.objects["Cube"].data.materials.append(mat)
node = mat.node_tree.nodes.get("Principled BSDF")
old = node.inputs["Roughness"].default_value
recipe = {"operations": [{"op": "set_material_input", "name": mat.name,
                           "node": node.name, "socket": "Roughness", "value": 0.25}]}
preview = automation.preview(recipe)
assert node.inputs["Roughness"].default_value == old
assert preview["material_edits"][0]["object_users"] == ["Cube"]
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "completed" and not result["saved"], result
assert node.inputs["Roughness"].default_value == 0.25
assert result["materials"][0]["name"] == mat.name
preview = automation.preview(recipe)
node.inputs["Roughness"].default_value = 0.5
try:
    automation.apply(preview["preview_id"], preview["preview_id"])
    raise AssertionError("Changed shader input failed to invalidate preview")
except RecipeError as error:
    assert error.code == "stale_preview"
before = material_info(mat.name)
result = automation.execute([
    recipe["operations"][0],
    {"op": "set_transform", "name": "Cube", "location": ["invalid", 0, 0]},
])
assert result["state"] == "rolled_back", result
assert material_info(mat.name) == before
for value in (float("nan"), 2.0, [1, 2, 3]):
    try:
        automation.preview({"operations": [{**recipe["operations"][0], "value": value}]})
        raise AssertionError("Invalid native input default accepted")
    except RecipeError as error:
        assert error.code == "invalid_arguments"
assert bpy.data.filepath == ""
print("FORGE_NATIVE_EXISTING_MATERIAL_INPUT_PREVIEW_USERS_STALE_ROLLBACK_BOUNDS_PASS")
