"""Verify ForgeMCP Blender UI branding from project source in factory startup."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge

assert majestic_forge.bl_info["name"] == "ForgeMCP"
assert "Sidebar > ForgeMCP" in majestic_forge.bl_info["location"]
assert majestic_forge.MAJESTICFORGE_PT_Connection.bl_category == "ForgeMCP"
assert majestic_forge.MAJESTICFORGE_PT_Connection.bl_label == "ForgeMCP Connection"
assert majestic_forge.MAJESTICFORGE_Preferences.bl_idname == "majestic_forge"
print("FORGEMCP_BLENDER_SOURCE_UI_BRANDING_PASS")
