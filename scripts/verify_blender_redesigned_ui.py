"""Draw ForgeMCP sidebar panels in headless Blender without changing scene data."""

import sys
from pathlib import Path
from types import SimpleNamespace

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import majestic_forge
from majestic_forge import transfer_ui


class LayoutProbe:
    def __init__(self, events=None):
        self.events = events if events is not None else []
        self.enabled = True

    def box(self):
        self.events.append(("box",))
        return LayoutProbe(self.events)

    def row(self, **kwargs):
        self.events.append(("row", kwargs))
        return LayoutProbe(self.events)

    def column(self, **kwargs):
        self.events.append(("column", kwargs))
        return LayoutProbe(self.events)

    def label(self, **kwargs):
        self.events.append(("label", kwargs))

    def prop(self, owner, name, **kwargs):
        self.events.append(("prop", name, kwargs))

    def operator(self, identifier, **kwargs):
        self.events.append(("operator", identifier, kwargs))

    def template_icon(self, **kwargs):
        self.events.append(("template_icon", kwargs))


before = (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.context.scene.render.fps)
try:
    majestic_forge.register()
    assert majestic_forge.ADDON_VERSION == "0.2.35-alpha.6"
    assert majestic_forge.MAJESTICFORGE_PT_Connection.is_registered
    assert transfer_ui.MAJESTICFORGE_PT_Transfer.is_registered

    connection_layout = LayoutProbe()
    majestic_forge.MAJESTICFORGE_PT_Connection.draw(
        SimpleNamespace(layout=connection_layout), bpy.context
    )
    connection_text = [event[1].get("text", "") for event in connection_layout.events if event[0] == "label"]
    assert "ForgeMCP" in connection_text
    assert "Bridge Status" in connection_text
    assert any(text.startswith("Bridge running") for text in connection_text)
    assert any(
        event[0] == "template_icon" and event[1].get("scale") == 8.0
        for event in connection_layout.events
    )

    transfer_layout = LayoutProbe()
    transfer_ui.MAJESTICFORGE_PT_Transfer.draw(
        SimpleNamespace(layout=transfer_layout), bpy.context
    )
    transfer_text = [event[1].get("text", "") for event in transfer_layout.events if event[0] == "label"]
    transfer_props = {event[1] for event in transfer_layout.events if event[0] == "prop"}
    transfer_ops = {event[1] for event in transfer_layout.events if event[0] == "operator"}
    assert "Transfer Status" in transfer_text
    assert any(
        event[1] == "majestic_forge.export_to_unreal"
        and event[2].get("text") == "Send to Unreal"
        for event in transfer_layout.events
        if event[0] == "operator"
    )
    assert {"project_root", "target_session", "asset_path", "save_assets", "place", "location"} <= transfer_props
    assert "majestic_forge.export_to_unreal" in transfer_ops
    assert bpy.context.window_manager.forge_transfer.asset_path == "/Game/Content/Returns/"
    print("FORGEMCP_BLENDER_ALPHA6_REFERENCE_LAYOUT_HEADLESS_PASS")
finally:
    majestic_forge.unregister()

assert before == (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.context.scene.render.fps)
