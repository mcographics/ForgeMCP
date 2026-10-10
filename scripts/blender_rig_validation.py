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
try:
    rig_info("Cube")
except Exception as error:
    assert getattr(error, "code", None) == "rig_not_found"
else:
    raise AssertionError("A mesh object must not be accepted as an armature.")
assert before.issubset({obj.name for obj in bpy.context.scene.objects})

selected_before = {obj.name for obj in bpy.context.selected_objects}
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
