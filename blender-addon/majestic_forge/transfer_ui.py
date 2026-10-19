# SPDX-License-Identifier: MIT
"""Main-thread Blender UI and a bounded subprocess client; no bpy in reader threads."""

import json
import os
import queue
import subprocess
import threading
from pathlib import Path

import bpy

_job = None
_status = "Select a static mesh to transfer."
_last_operation = ""
_errors = {
    "unsupported_material_surface": "Material unsupported: use an opaque constant Principled material.",
    "unsupported_source": "Use a static mesh without modifiers, parenting or animation.",
    "unsupported_context": "Switch to Object mode before sending.",
    "unreal_not_connected": "Open Unreal and start its ForgeMCP bridge.",
    "ambiguous_session": "Multiple Unreal sessions: enter the target session ID.",
    "destination_exists": "Destination exists. Choose a new asset path.",
    "invalid_context": "Stop Play in Editor before transferring.",
}


def busy():
    return _job is not None


def applying():
    return bool(_job and _job["state"] == "applying")


def _read_output(process, messages):
    try:
        while True:
            line = process.stdout.readline(1024 * 1024 + 1)
            if not line:
                break
            if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                raise ValueError("invalid_worker_response")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("invalid_worker_response")
            messages.put(value, timeout=1)
    except (ValueError, OSError, queue.Full):
        pass
    finally:
        try:
            messages.put({"eof": True}, timeout=1)
        except queue.Full:
            pass


def _close_job():
    global _job
    if _job:
        process = _job["process"]
        if process.stdin:
            try:
                if process.poll() is None and _job["state"] not in {"applying", "finished"}:
                    process.stdin.write(b"{}\n")
                    process.stdin.flush()
                process.stdin.close()
            except OSError:
                pass
        _job = None


def _poll():
    global _status, _last_operation
    if not _job:
        return None
    messages = _job["messages"]
    while True:
        try:
            message = messages.get_nowait()
        except queue.Empty:
            break
        if message.get("eof"):
            _status = "Outcome uncertain: inspect the receipt before retrying." if applying() else "Transfer worker stopped."
            _close_job()
            break
        state = message.get("state")
        if state == "preview":
            _job["preview"] = message["preview"]
            _job["state"] = "preview"
            _last_operation = message["preview"]["operation_id"]
            _status = "Review the destination below, then confirm."
        elif state == "applying":
            _job["state"] = "applying"
            _status = "Transferring — keep Blender and Unreal open."
        else:
            error = message.get("error", {}).get("code")
            result = message.get("result", {})
            error = error or result.get("data", {}).get("diagnostic_code") or result.get("error", {}).get("code")
            if state == "completed":
                _status = "Transferred. The Unreal level and Blender scene are unsaved."
            else:
                _status = _errors.get(error, f"Transfer {state or 'failed'} ({error or 'inspect receipt'}).")
            _job["state"] = "finished"
            _close_job()
            break
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    return 0.1 if _job else None


def shutdown():
    if applying():
        raise RuntimeError("ForgeMCP transfer is applying. Wait for its result before disabling the add-on.")
    _close_job()
    if bpy.app.timers.is_registered(_poll):
        bpy.app.timers.unregister(_poll)


class MAJESTICFORGE_TransferSettings(bpy.types.PropertyGroup):
    project_root: bpy.props.StringProperty(name="ForgeMCP folder", subtype="DIR_PATH", default="G:\\ForgeMCP")
    target_session: bpy.props.StringProperty(name="Unreal session", description="Leave empty if exactly one Unreal bridge is connected")
    asset_path: bpy.props.StringProperty(name="Asset path", default="/Game/Content/Returns/")
    save_assets: bpy.props.BoolProperty(name="Save new assets", default=True)
    place: bpy.props.BoolProperty(name="Place in current Unreal level", default=True)
    location: bpy.props.FloatVectorProperty(name="Location (cm)", size=3, default=(0, 0, 0), min=-1e8, max=1e8)


class MAJESTICFORGE_OT_ExportToUnreal(bpy.types.Operator):
    bl_idname = "majestic_forge.export_to_unreal"
    bl_label = "Send to Unreal"
    bl_description = "Preview transfer of the active mesh to the connected Unreal project"

    @classmethod
    def poll(cls, context):
        return not busy() and context.mode == "OBJECT" and context.active_object is not None and context.active_object.type == "MESH"

    def execute(self, context):
        global _job, _status
        from . import _bridge
        if not _bridge:
            self.report({"ERROR"}, "Start the ForgeMCP bridge first.")
            return {"CANCELLED"}
        settings = context.window_manager.forge_transfer
        root = Path(bpy.path.abspath(settings.project_root)).resolve()
        executable = root / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
        if not executable.is_file() or not (root / "server/ui_transfer.py").is_file():
            self.report({"ERROR"}, "Choose the ForgeMCP development folder with its Python environment.")
            return {"CANCELLED"}
        intent = {"source_session_id": _bridge.session_id, "source_object": context.active_object.name,
                  "target_session_id": settings.target_session, "target_asset_path": settings.asset_path,
                  "save_assets": settings.save_assets, "place": settings.place, "location": list(settings.location)}
        process = None
        try:
            process = subprocess.Popen([str(executable), "-m", "server.ui_transfer"], cwd=str(root),
                env={**os.environ, "FORGE_PROJECT_ROOT": str(root)}, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            process.stdin.write(json.dumps(intent, allow_nan=False).encode() + b"\n")
            process.stdin.flush()
            _job = {"process": process, "messages": queue.Queue(maxsize=8), "state": "preparing"}
            threading.Thread(target=_read_output, args=(process, _job["messages"]), daemon=True).start()
            if not bpy.app.timers.is_registered(_poll):
                bpy.app.timers.register(_poll, first_interval=0.1)
            _status = "Checking the selected mesh and Unreal destination..."
        except (OSError, ValueError):
            if process and process.poll() is None:
                process.terminate()
            _job = None
            self.report({"ERROR"}, "Could not start the local transfer worker.")
            return {"CANCELLED"}
        return {"FINISHED"}


class MAJESTICFORGE_OT_ConfirmTransfer(bpy.types.Operator):
    bl_idname = "majestic_forge.confirm_transfer"
    bl_label = "Confirm Send to Unreal"

    @classmethod
    def poll(cls, context):
        return bool(_job and _job["state"] == "preview")

    def execute(self, context):
        global _status
        operation = _job["preview"]["preview_id"]
        _job["state"] = "applying"
        _status = "Transferring — keep Blender and Unreal open."
        try:
            _job["process"].stdin.write(json.dumps({"confirmation": operation}).encode() + b"\n")
            _job["process"].stdin.flush()
        except OSError:
            _status = "Outcome uncertain: inspect the receipt before retrying."
            _close_job()
        return {"FINISHED"}


class MAJESTICFORGE_OT_CancelTransfer(bpy.types.Operator):
    bl_idname = "majestic_forge.cancel_transfer"
    bl_label = "Cancel Preview"

    @classmethod
    def poll(cls, context):
        return busy() and not applying()

    def execute(self, context):
        global _status
        shutdown()
        _status = "Preview cancelled; no transfer applied."
        return {"FINISHED"}


class MAJESTICFORGE_PT_Transfer(bpy.types.Panel):
    bl_label = "Send to Unreal"
    bl_idname = "MAJESTICFORGE_PT_transfer"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ForgeMCP"

    def draw(self, context):
        layout = self.layout
        settings = context.window_manager.forge_transfer
        card = layout.box()
        controls = card.column(align=True)
        controls.enabled = not busy()

        controls.prop(settings, "project_root", text="ForgeMCP Path")
        controls.prop(settings, "target_session", text="Unreal Session ID")
        controls.prop(settings, "asset_path", text="Asset Path")
        toggles = controls.column(align=True)
        toggles.prop(settings, "save_assets")
        toggles.prop(settings, "place")
        if settings.place:
            position = controls.column(align=True)
            position.label(text="Location (cm)")
            for axis, index in (("X", 0), ("Y", 1), ("Z", 2)):
                coordinate = position.row(align=True)
                coordinate.label(text=axis)
                coordinate.prop(settings, "location", index=index, text="")

        obj = context.active_object
        ready = bool(obj and obj.type == "MESH" and context.mode == "OBJECT")
        controls.label(
            text=f"Source: {obj.name}" if ready else "Select a mesh in Object mode",
            icon="MESH_DATA" if ready else "INFO",
        )
        action = controls.row()
        action.scale_y = 1.4
        action.operator("majestic_forge.export_to_unreal", text="Send to Unreal", icon="EXPORT")

        status = layout.box()
        is_error = _status.startswith(("Transfer failed", "Outcome uncertain", "Transfer worker stopped"))
        status.label(text="Transfer Status", icon="ERROR" if is_error else "INFO")
        for line in _status.splitlines() or [""]:
            status.label(text=line)
        if _job and _job["state"] == "preview":
            plan = _job["preview"]
            box = status.box()
            box.label(text="Review Transfer Preview", icon="PREVIEW_RANGE")
            box.label(text=f"Unreal Session: {plan['changes']['target_session_id']}")
            box.label(text="Project:", icon="FILE_FOLDER")
            import textwrap
            for line in textwrap.wrap(plan["target"]["project_file"], width=38):
                box.label(text=line)
            for line in textwrap.wrap(plan["changes"]["target_asset_path"], width=38):
                box.label(text=line)
            box.label(text=f"Place: {plan['changes']['place']} — {plan['changes']['location']}")
            box.label(text=f"Save assets: {plan['changes']['save_assets']}")
            box.label(text="No overwrite; level stays unsaved")
            box.operator("majestic_forge.confirm_transfer", text="Confirm Transfer", icon="CHECKMARK")
        if busy() and not applying():
            status.operator("majestic_forge.cancel_transfer", text="Cancel Preview", icon="CANCEL")
        if _last_operation:
            status.label(text=f"Receipt: {_last_operation}", icon="TEXT")


CLASSES = (MAJESTICFORGE_TransferSettings, MAJESTICFORGE_OT_ExportToUnreal,
           MAJESTICFORGE_OT_ConfirmTransfer, MAJESTICFORGE_OT_CancelTransfer, MAJESTICFORGE_PT_Transfer)
