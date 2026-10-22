# SPDX-License-Identifier: MIT
# ruff: noqa: E402
"""Original ForgeMCP Blender adapter, using only bpy and stdlib."""

import atexit
import hmac
import importlib
import json
import os
import secrets
import socket
import sys
import time
from pathlib import Path

import bpy
import bpy.utils.previews

# Blender can replace an installed package while retaining its child modules.
# Reload dependencies first so updates cannot mix old helpers with new imports.
# Blender unregisters an enabled add-on before reloading its package.
for _module_name in ("security", "materials", "automation", "creative", "skinning", "rigging", "exporting", "importing", "transfer_ui"):
    _cached_module = sys.modules.get(f"{__name__}.{_module_name}")
    if _cached_module is not None:
        importlib.reload(_cached_module)

from . import creative, transfer_ui
from .automation import (
    RecipeError,
    SceneAutomation,
    animation_info,
    mesh_edge_info,
    mesh_geometry_info,
    mesh_uv_info,
    object_info,
)
from .exporting import StaticMeshExporter
from .importing import StaticMeshImporter
from .materials import material_info
from .rigging import rig_info
from .security import protect_path
from .skinning import skin_info

bl_info = {
    "name": "ForgeMCP",
    "author": "Majestic Creations",
    "version": (0, 2, 36),
    "blender": (4, 2, 0),
    "location": "3D Viewport > Sidebar > ForgeMCP; Preferences > Add-ons",
    "description": "Authenticated native inspection and reviewed scene recipes for ForgeMCP",
    "category": "Development",
}
_bridge = None
_ui_registered = False
_exit_registered = False
_next_redraw = 0.0
ADDON_VERSION = "0.2.36-alpha.1"
BRIDGE_PROTOCOL_VERSION = 1
TRANSFER_CONTRACT_VERSION = 1
_logo_previews = None


def _load_logo():
    global _logo_previews
    if _logo_previews is None:
        previews = bpy.utils.previews.new()
        try:
            previews.load("logo", str(Path(__file__).parent / "resources" / "logo.png"), "IMAGE")
        except Exception:
            bpy.utils.previews.remove(previews)
            raise
        _logo_previews = previews


def _draw_logo(layout):
    if _logo_previews is not None:
        layout.template_icon(icon_value=_logo_previews["logo"].icon_id, scale=6.0)


MAX_REQUEST_BYTES = 512 * 1024


def parse_request(raw):
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Request too large")
    depth = 0
    in_string = escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                in_string = False
        elif byte == 34:
            in_string = True
        elif byte in (123, 91):
            depth += 1
            # Native shader RGBA/vector defaults need nine containers in the
            # protocol envelope. Keep a fixed bound rather than unbounded parsing.
            if depth > 9:
                raise ValueError("Request nesting too deep")
        elif byte in (125, 93):
            depth -= 1
            if depth < 0:
                raise ValueError("Unbalanced JSON")
    if depth or in_string:
        raise ValueError("Incomplete JSON")

    def fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    return json.loads(raw, object_pairs_hook=fields, parse_constant=invalid_constant)


class Bridge:
    def __init__(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(16)
        self.listener.setblocking(False)
        self.clients = []
        self.token = secrets.token_hex(32)
        self.session_id = f"blender-{os.getpid()}"
        self.last_request = None
        self.automation = SceneAutomation()
        root = Path(
            os.environ.get(
                "FORGE_BLENDER_SESSION_DIR",
                str(
                    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MajesticForge" / "sessions"
                ),
            )
        )
        root.mkdir(parents=True, exist_ok=True)
        try:
            protect_path(root)
        except OSError:
            self.listener.close()
            raise
        self.registration = root / f"{self.session_id}.json"
        self.exporter = StaticMeshExporter(root / "transfers" / self.session_id)
        self.importer = StaticMeshImporter(root / "transfers" / self.session_id)
        self.creative = creative.CreativeAutomation(root / "renders" / self.session_id)
        data = {
            "protocol_version": BRIDGE_PROTOCOL_VERSION,
            "session_id": self.session_id,
            "kind": "blender",
            "host": "127.0.0.1",
            "port": self.listener.getsockname()[1],
            "pid": os.getpid(),
            "token": self.token,
        }
        temporary = self.registration.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(data), encoding="utf-8")
            protect_path(temporary)
            temporary.replace(self.registration)
        except Exception:
            self.listener.close()
            raise

    def reply(self, raw):
        request_id = None
        try:
            request = parse_request(raw)
            if not isinstance(request, dict):
                raise ValueError("Expected a JSON object.")
            request_id = request.get("request_id")
            if (
                type(request.get("protocol_version")) is not int
                or request.get("protocol_version") != BRIDGE_PROTOCOL_VERSION
                or not isinstance(request_id, str)
                or not 1 <= len(request_id) <= 128
            ):
                raise ValueError("Unsupported protocol or request identifier.")
            token = request.get("token")
            if not isinstance(token, str) or not hmac.compare_digest(token, self.token):
                return self.error(request_id, "unauthorized", "Session authentication failed.")
            self.last_request = time.monotonic()
            command = request.get("command")
            if not isinstance(request.get("args", {}), dict):
                return self.error(request_id, "invalid_arguments", "args must be an object.")
            if command == "health":
                data = {
                    "adapter": "ForgeMCP Blender",
                    "bridge_protocol_version": BRIDGE_PROTOCOL_VERSION,
                    "transfer_contract_version": TRANSFER_CONTRACT_VERSION,
                    "version": ADDON_VERSION,
                    "blender_version": bpy.app.version_string,
                    "read_only": False,
                    "capabilities": ["scene_info", "object_info", "animation_info", "mesh_geometry_info", "mesh_edge_info", "mesh_uv_info", "material_info", "rig_info", "skin_info", "scene_preview", "scene_apply", "export_preview", "export_apply", "binding_info", "binding_commit_preview", "binding_commit_apply", "import_preview", "import_apply", "command_catalog", "command_schema", "rna_catalog", "rna_schema", "creative_properties", "creative_preview", "creative_apply", "render_job_info", "render_job_cancel"],
                }
            elif command == "scene_info":
                scene = bpy.context.scene
                if scene is None:
                    return self.error(
                        request_id, "scene_not_ready", "No active scene is available."
                    )
                types = {}
                for obj in scene.objects:
                    types[obj.type] = types.get(obj.type, 0) + 1
                objects = [
                    {"name": obj.name, "type": obj.type} for obj in list(scene.objects)[:200]
                ]
                data = {
                    "blender_version": bpy.app.version_string,
                    "file": bpy.data.filepath,
                    "scene_name": scene.name,
                    "units": [scene.unit_settings.system, scene.unit_settings.scale_length],
                    "mode": bpy.context.mode,
                    "active_object": bpy.context.active_object.name if bpy.context.active_object else None,
                    "object_count": len(scene.objects),
                    "object_types": types,
                    "objects": objects,
                    "truncated": len(scene.objects) > len(objects),
                    "frame_start": scene.frame_start,
                    "frame_end": scene.frame_end,
                    "frame_current": scene.frame_current,
                    "fps": scene.render.fps,
                    "fps_base": scene.render.fps_base,
                    "effective_fps": scene.render.fps / scene.render.fps_base,
                    "addon_version": ADDON_VERSION,
                }
            elif command == "object_info":
                data = object_info(request.get("args", {}).get("name"))
            elif command == "animation_info":
                args = request.get("args", {})
                if set(args) - {"name", "curve_start", "curve_count", "keyframe_start", "keyframe_count"} or "name" not in args:
                    raise RecipeError("invalid_arguments", "Expected an object name and optional bounded Action curve/keyframe pages.")
                data = animation_info(args["name"], args.get("curve_start", 0),
                    args.get("curve_count", 16), args.get("keyframe_start", 0),
                    args.get("keyframe_count", 64))
            elif command == "mesh_geometry_info":
                args = request.get("args", {})
                if set(args) - {"name", "vertex_start", "vertex_count", "face_start", "face_count"} or "name" not in args:
                    raise RecipeError("invalid_arguments", "Expected a mesh name and optional bounded vertex/face pages.")
                data = mesh_geometry_info(args["name"], args.get("vertex_start", 0),
                    args.get("vertex_count", 128), args.get("face_start", 0), args.get("face_count", 128))
            elif command == "mesh_edge_info":
                args = request.get("args", {})
                if set(args) - {"name", "edge_start", "edge_count"} or "name" not in args:
                    raise RecipeError("invalid_arguments", "Expected a mesh name and optional bounded edge page.")
                data = mesh_edge_info(args["name"], args.get("edge_start", 0), args.get("edge_count", 128))
            elif command == "mesh_uv_info":
                args = request.get("args", {})
                if set(args) - {"name", "layer_name", "loop_start", "loop_count"} or "name" not in args:
                    raise RecipeError("invalid_arguments", "Expected a mesh name and optional UV layer/page.")
                data = mesh_uv_info(args["name"], args.get("layer_name", ""),
                    args.get("loop_start", 0), args.get("loop_count", 128))
            elif command == "rig_info":
                args = request.get("args", {})
                if set(args) - {"name", "include_weights", "include_evaluated"} or "name" not in args:
                    raise RecipeError("invalid_arguments", "Expected an armature name and optional include_weights.")
                data = rig_info(args["name"], args.get("include_weights", False), args.get("include_evaluated", False))
            elif command == "skin_info":
                args = request.get("args", {})
                if "name" not in args or set(args) - {"name", "vertex_start", "vertex_count"}:
                    raise RecipeError("invalid_arguments", "Expected a mesh name and bounded vertex range.")
                data = skin_info(args["name"], args.get("vertex_start", 0), args.get("vertex_count", 128))
            elif command == "material_info":
                args = request.get("args", {})
                if set(args) != {"name"}:
                    raise RecipeError("invalid_arguments", "Expected only a material name.")
                try:
                    data = material_info(args["name"])
                except ValueError as error:
                    raise RecipeError("invalid_arguments", str(error)) from error
            elif command == "scene_preview":
                data = self.automation.preview(request.get("args", {}).get("recipe"))
            elif command == "scene_apply":
                args = request.get("args", {})
                data = self.automation.apply(args.get("preview_id"), args.get("confirmation"))
            elif command in {"command_catalog", "command_schema", "rna_catalog", "rna_schema", "creative_properties", "creative_preview", "creative_apply", "render_job_info", "render_job_cancel"}:
                args = request.get("args", {})
                functions = {
                    "command_catalog": (creative.list_commands, {"query", "offset", "limit"}),
                    "command_schema": (creative.inspect_command, {"identifier"}),
                    "rna_catalog": (creative.list_types, {"query", "offset", "limit"}),
                    "rna_schema": (creative.inspect_type, {"name"}),
                    "creative_properties": (creative.inspect_properties, {"target"}),
                    "creative_preview": (self.creative.preview, {"request"}),
                    "creative_apply": (self.creative.apply, {"preview_id", "confirmation"}),
                    "render_job_info": (self.creative.job_info, {"job_id"}),
                    "render_job_cancel": (self.creative.cancel_job, {"job_id", "confirmation"}),
                }
                function, fields = functions[command]
                optional = command in {"command_catalog", "rna_catalog"}
                if set(args) - fields or (not optional and set(args) != fields):
                    raise RecipeError("invalid_arguments", "Expected exact creative command arguments.")
                data = function(**args)
            elif command == "import_preview":
                data = self.importer.preview(request.get("args", {}))
            elif command == "import_apply":
                args = request.get("args", {})
                if set(args) != {"preview_id", "confirmation"}:
                    raise RecipeError("invalid_arguments", "Expected preview ID and confirmation.")
                data = self.importer.apply(args["preview_id"], args["confirmation"])
            elif command == "export_preview":
                args = request.get("args", {})
                if set(args) != {"name"}:
                    raise RecipeError("invalid_arguments", "Expected only an exact source mesh name.")
                data = self.exporter.preview(args["name"])
            elif command == "binding_info":
                args = request.get("args", {})
                if set(args) != {"name"}:
                    raise RecipeError("invalid_arguments", "Expected only an exact source mesh name.")
                data = self.exporter.binding_info(args["name"])
            elif command == "binding_commit_preview":
                args = request.get("args", {})
                if set(args) != {"name", "binding_id", "source_revision_sha256", "expected_previous_revision_sha256"}:
                    raise RecipeError("invalid_arguments", "Expected exact object, binding and revision identities.")
                data = self.exporter.binding_commit_preview(args["name"], args["binding_id"],
                    args["source_revision_sha256"], args["expected_previous_revision_sha256"])
            elif command == "binding_commit_apply":
                args = request.get("args", {})
                if set(args) != {"preview_id", "confirmation"}:
                    raise RecipeError("invalid_arguments", "Expected binding-baseline preview ID and confirmation.")
                data = self.exporter.binding_commit_apply(args["preview_id"], args["confirmation"])
            elif command == "export_apply":
                args = request.get("args", {})
                if set(args) != {"preview_id", "confirmation"}:
                    raise RecipeError("invalid_arguments", "Expected export preview ID and confirmation.")
                data = self.exporter.apply(args["preview_id"], args["confirmation"])
            else:
                return self.error(request_id, "command_not_allowed", "Command is not allowlisted.")
            return {"ok": True, "request_id": request_id, "data": data}
        except RecipeError as error:
            return self.error(request_id, error.code, str(error))
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return self.error(
                request_id if isinstance(request_id, str) else None,
                "invalid_request",
                "Expected a valid protocol-v1 JSON request.",
            )
        except Exception:
            return self.error(request_id, "inspection_failed", "Blender scene inspection failed.")

    @staticmethod
    def error(request_id, code, message):
        return {"ok": False, "request_id": request_id, "error": {"code": code, "message": message}}

    def tick(self):
        # Invoked by bpy.app.timers on Blender's main thread. No background bpy access.
        for _ in range(max(0, 16 - len(self.clients))):
            try:
                client, _ = self.listener.accept()
                client.setblocking(False)
                self.clients.append(
                    {
                        "socket": client,
                        "input": bytearray(),
                        "output": b"",
                        "started": time.monotonic(),
                    }
                )
            except BlockingIOError:
                break
            except OSError:
                break
        for client in list(self.clients):
            close = time.monotonic() - client["started"] > 10
            try:
                if not close and not client["output"]:
                    try:
                        data = client["socket"].recv(4096)
                        if not data:
                            close = True
                        client["input"].extend(data)
                    except BlockingIOError:
                        pass
                    if len(client["input"]) > MAX_REQUEST_BYTES:
                        close = True
                    if not close and b"\n" in client["input"]:
                        raw = bytes(client["input"]).split(b"\n", 1)[0]
                        client["output"] = json.dumps(self.reply(raw)).encode() + b"\n"
                        client["started"] = time.monotonic()
                        if len(client["output"]) > 1024 * 1024:
                            client["output"] = (
                                json.dumps(
                                    self.error(
                                        None, "response_too_large", "Response exceeds limit."
                                    )
                                ).encode()
                                + b"\n"
                            )
                if not close and client["output"]:
                    try:
                        sent = client["socket"].send(client["output"])
                        client["output"] = client["output"][sent:]
                        close = not client["output"]
                    except BlockingIOError:
                        pass
            except OSError:
                close = True
            if close:
                client["socket"].close()
                self.clients.remove(client)
        return 0.02

    def close(self):
        for client in self.clients:
            client["socket"].close()
        self.clients.clear()
        self.listener.close()
        self.registration.unlink(missing_ok=True)


def _tick():
    global _next_redraw
    if not _bridge:
        return None
    interval = _bridge.tick()
    if time.monotonic() >= _next_redraw:
        _next_redraw = time.monotonic() + 1
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    return interval


def _preferences(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def start_bridge():
    global _bridge
    if _bridge is not None:
        return
    bridge = Bridge()
    try:
        bpy.app.timers.register(_tick, first_interval=0.02, persistent=True)
    except Exception:
        bridge.close()
        raise
    _bridge = bridge


def stop_bridge():
    global _bridge
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if _bridge:
        _bridge.close()
        _bridge = None


class MAJESTICFORGE_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    auto_start: bpy.props.BoolProperty(
        name="Start bridge when add-on is enabled",
        description="Automatically start the authenticated local bridge when this add-on loads",
        default=True,
    )

    def draw(self, context):
        _draw_logo(self.layout)
        self.layout.prop(self, "auto_start")
        self.layout.label(text="Open the 3D Viewport sidebar (N) > ForgeMCP.")


class MAJESTICFORGE_OT_Start(bpy.types.Operator):
    bl_idname = "majestic_forge.start_bridge"
    bl_label = "Start Bridge"
    bl_description = "Start the authenticated local ForgeMCP bridge"

    def execute(self, context):
        try:
            start_bridge()
        except OSError:
            self.report({"ERROR"}, "Could not start Forge bridge. Check local socket/file access.")
            return {"CANCELLED"}
        return {"FINISHED"}


class MAJESTICFORGE_OT_Stop(bpy.types.Operator):
    bl_idname = "majestic_forge.stop_bridge"
    bl_label = "Stop Bridge"
    bl_description = "Stop this Blender session's Forge bridge without changing the scene"

    def execute(self, context):
        if transfer_ui.busy():
            self.report({"ERROR"}, "Finish or cancel the transfer before stopping the bridge.")
            return {"CANCELLED"}
        stop_bridge()
        return {"FINISHED"}


class MAJESTICFORGE_PT_Connection(bpy.types.Panel):
    bl_label = "ForgeMCP Connection"
    bl_idname = "MAJESTICFORGE_PT_connection"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ForgeMCP"

    def draw(self, context):
        layout = self.layout
        brand = layout.box()
        banner = brand.column(align=True)
        banner.alignment = "CENTER"
        if _logo_previews is not None:
            banner.template_icon(icon_value=_logo_previews["logo"].icon_id, scale=8.0)
        title = banner.row(align=True)
        title.scale_y = 1.35
        title.label(text="ForgeMCP")
        banner.label(text=ADDON_VERSION)

        status = layout.box()
        status.label(text="Bridge Status", icon="IPO_EASE_IN_OUT")
        if _bridge:
            status.label(text="Bridge running", icon="RADIOBUT_ON")
            status.label(text=f"127.0.0.1:{_bridge.listener.getsockname()[1]}", icon="LINKED")
            status.label(text=f"Session: {_bridge.session_id}", icon="USER")
            status.label(
                text=f"Protocol {BRIDGE_PROTOCOL_VERSION} / transfer {TRANSFER_CONTRACT_VERSION}",
                icon="INFO",
            )
            if _bridge.last_request is None:
                status.label(text="Waiting for an authenticated request", icon="TIME")
            else:
                elapsed = int(time.monotonic() - _bridge.last_request)
                status.label(text=f"Last authenticated request: {elapsed}s ago", icon="TIME")
            action = status.row()
            action.scale_y = 1.25
            action.operator("majestic_forge.stop_bridge", text="Stop Bridge", icon="PAUSE")
        else:
            status.label(text="Bridge stopped", icon="RADIOBUT_OFF")
            action = status.row()
            action.scale_y = 1.25
            action.operator("majestic_forge.start_bridge", text="Start Bridge", icon="PLAY")
        preferences = _preferences(context)
        options = layout.column(align=True)
        if preferences:
            options.prop(preferences, "auto_start")
        else:
            options.label(text="Enabled for this session only", icon="INFO")
        note = options.box()
        note.label(text="Native recipes require a reviewed preview.", icon="INFO")


_CLASSES = (
    MAJESTICFORGE_Preferences,
    MAJESTICFORGE_OT_Start,
    MAJESTICFORGE_OT_Stop,
    MAJESTICFORGE_PT_Connection,
) + transfer_ui.CLASSES


def _exit_cleanup():
    # Blender tears down RNA before Python atexit; close only native resources here.
    global _bridge
    if _bridge:
        _bridge.close()
        _bridge = None


def register():
    global _ui_registered, _exit_registered
    _load_logo()
    if not _ui_registered:
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.WindowManager.forge_transfer = bpy.props.PointerProperty(
            type=transfer_ui.MAJESTICFORGE_TransferSettings
        )
        _ui_registered = True
    preferences = _preferences(bpy.context)
    if preferences is None or preferences.auto_start:
        start_bridge()
    if not _exit_registered:
        atexit.register(_exit_cleanup)
        _exit_registered = True


def unregister():
    global _ui_registered, _logo_previews
    transfer_ui.shutdown()
    stop_bridge()
    if _ui_registered:
        del bpy.types.WindowManager.forge_transfer
        for cls in reversed(_CLASSES):
            if cls.is_registered:
                bpy.utils.unregister_class(cls)
        _ui_registered = False
    if _logo_previews is not None:
        bpy.utils.previews.remove(_logo_previews)
        _logo_previews = None
