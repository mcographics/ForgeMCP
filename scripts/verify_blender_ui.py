"""Run in factory-startup Blender to verify installed UI and bridge lifecycle."""

import addon_utils
import bpy

before = (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.context.scene.render.fps)
module = addon_utils.enable("majestic_forge", default_set=True)
assert module is not None, "Installed ForgeMCP add-on could not be enabled"
assert module.bl_info["name"] == "ForgeMCP"
assert module.MAJESTICFORGE_PT_Connection.is_registered
assert module.MAJESTICFORGE_PT_Connection.bl_category == "ForgeMCP"
preferences = bpy.context.preferences.addons["majestic_forge"].preferences
assert preferences.auto_start is True
assert module._bridge is not None
assert bpy.ops.majestic_forge.stop_bridge() == {"FINISHED"}
assert module._bridge is None
assert bpy.ops.majestic_forge.start_bridge() == {"FINISHED"}
assert module._bridge is not None
preferences.auto_start = False
addon_utils.disable("majestic_forge")
module = addon_utils.enable("majestic_forge")
assert module.MAJESTICFORGE_PT_Connection.is_registered
assert module._bridge is None, "Disabled auto-start should leave the bridge stopped"
assert bpy.ops.majestic_forge.start_bridge() == {"FINISHED"}
assert module._bridge is not None
addon_utils.disable("majestic_forge")
assert before == (
    len(bpy.data.objects),
    bpy.context.scene.frame_current,
    bpy.context.scene.render.fps,
)
print("FORGE_INSTALLED_UI_PREFERENCES_AND_LIFECYCLE_PASS")
