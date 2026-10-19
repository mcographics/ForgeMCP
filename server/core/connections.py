# SPDX-License-Identifier: MIT
from __future__ import annotations

import asyncio
import heapq
import json
import logging
import math
import os
import stat
import uuid
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("majestic_forge")
MAX_RESPONSE = 1024 * 1024
MAX_REQUEST = 512 * 1024
MAX_SESSION_REGISTRATIONS = 64
COMMANDS = {
    "unreal": {
        "health",
        "project_info",
        "landscape_info",
        "landscape_preview",
        "landscape_apply",
        "landscape_job_status",
        "landscape_job_cancel",
        "collision_query",
        "list_actors",
        "find_actors",
        "get_selected_actors",
        "editor_log",
        "capture_screenshot",
        "blueprint_preview",
        "blueprint_apply",
        "blueprint_info",
        "class_info",
        "asset_search",
        "list_data_assets",
        "list_data_asset_classes",
        "data_asset_schema",
        "data_asset_create_preview",
        "data_asset_create_apply",
        "data_asset_edit_preview",
        "data_asset_edit_apply",
        "asset_info",
        "get_data_table_schema",
        "get_data_table_rows",
        "get_data_table_row",
        "csv_import_preview",
        "csv_import_apply",
        "struct_tooltips_preview",
        "struct_tooltips_apply",
        "get_selected_assets",
        "open_asset",
        "sync_browser",
        "asset_property_info",
        "asset_property_edit_preview",
        "asset_property_edit_apply",
        "actor_info",
        "actor_components_info",
        "component_property_info",
        "component_property_edit_preview",
        "component_property_edit_apply",
        "actor_property_info",
        "actor_property_edit_preview",
        "actor_property_edit_apply",
        "gas_info",
        "actor_preview",
        "actor_apply",
        "actor_delete_preview",
        "actor_delete_apply",
        "level_save_preview",
        "level_save_apply",
        "level_create_preview",
        "level_create_apply",
        "current_level_save_preview",
        "current_level_save_apply",
        "blueprint_edit_preview",
        "blueprint_edit_apply",
        "mesh_import_preview",
        "mesh_import_apply",
        "mesh_replace_preview",
        "mesh_replace_apply",
        "mesh_info",
        "mesh_export_preview",
        "mesh_export_apply",
        "mesh_binding_info",
        "material_graph_info",
        "material_preview",
        "material_apply",
        "material_edit_preview",
        "material_edit_apply",
        "material_instance_info",
        "material_instance_preview",
        "material_instance_apply",
        "material_instance_save_preview",
        "material_instance_save_apply",
    },
    "blender": {"command_catalog", "command_schema", "rna_catalog", "rna_schema", "creative_properties", "creative_preview", "creative_apply", "render_job_info", "render_job_cancel", "health", "scene_info", "object_info", "animation_info", "mesh_geometry_info", "mesh_edge_info", "mesh_uv_info", "material_info", "rig_info", "skin_info", "scene_preview", "scene_apply", "export_preview", "export_apply", "binding_info", "binding_commit_preview", "binding_commit_apply", "import_preview", "import_apply"},
}


class BridgeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Session:
    session_id: str
    kind: str
    port: int
    token: str = field(repr=False)
    pid: int

    def public(self) -> dict:
        return {"session_id": self.session_id, "kind": self.kind, "pid": self.pid}


class ConnectionManager:
    def __init__(self, roots: list[Path], timeout: float = 10, *, apply_timeout: float = 60):
        if not math.isfinite(apply_timeout) or not 0 < apply_timeout <= 1800:
            raise ValueError("Apply timeout must be finite and between 0 and 1800 seconds")
        self.roots = roots
        self.timeout = timeout
        self.apply_timeout = apply_timeout

    @classmethod
    def configured(cls) -> ConnectionManager:
        shared_root = Path(
            os.environ.get(
                "FORGE_SESSION_DIR",
                str(Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MajesticForge" / "sessions"),
            )
        )
        # App-specific overrides remain useful for isolated tests and deliberate
        # private deployments. Normal engine-wide installs share one user session
        # directory and never infer an Unreal project from the MCP checkout.
        unreal_root = Path(os.environ.get("FORGE_UNREAL_SESSION_DIR", str(shared_root)))
        blender_root = Path(os.environ.get("FORGE_BLENDER_SESSION_DIR", str(shared_root)))
        return cls([unreal_root, blender_root])

    def discover(self) -> list[Session]:
        sessions = {}
        for root in self.roots:
            recent = []
            for path in root.glob("*.json"):
                try:
                    info = path.lstat()
                except OSError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    recent.append((info.st_mtime_ns, path))
            candidates = heapq.nlargest(
                MAX_SESSION_REGISTRATIONS, recent, key=lambda item: (item[0], item[1].name)
            )
            for _, path in candidates:
                try:
                    if path.stat().st_size > 8192:
                        raise ValueError("registration too large")
                    if path.is_symlink() or path.resolve().parent != root.resolve():
                        raise ValueError("registration must be a direct local file")
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    if (
                        not isinstance(data, dict)
                        or type(data.get("protocol_version")) is not int
                        or data.get("protocol_version") != 1
                        or data.get("host") != "127.0.0.1"
                        or data.get("kind") not in COMMANDS
                    ):
                        raise ValueError("unsupported session")
                    if (
                        type(data.get("port")) is not int
                        or not 1 <= data["port"] <= 65535
                        or type(data.get("pid")) is not int
                        or data["pid"] <= 0
                        or not isinstance(data.get("token"), str)
                        or not 32 <= len(data["token"]) <= 128
                        or not isinstance(data.get("session_id"), str)
                        or not 1 <= len(data["session_id"]) <= 128
                    ):
                        raise ValueError("invalid registration")
                    session = Session(
                        data["session_id"], data["kind"], data["port"], data["token"], data["pid"]
                    )
                    sessions.setdefault(session.session_id, session)
                except (OSError, ValueError, KeyError, TypeError, RecursionError):
                    # Never log registration contents, tokens, or arbitrary payloads.
                    log.warning("Ignored invalid session registration")
        return list(sessions.values())

    async def request(self, session: Session, command: str, args: dict | None = None) -> dict:
        if command not in COMMANDS.get(session.kind, set()):
            raise BridgeError("command_not_allowed", "Command is not in the native allowlist.")
        request_id = uuid.uuid4().hex

        async def exchange():
            reader, writer = await asyncio.open_connection(
                "127.0.0.1", session.port, limit=MAX_RESPONSE
            )
            try:
                request = {
                    "protocol_version": 1,
                    "request_id": request_id,
                    "token": session.token,
                    "command": command,
                    "args": args or {},
                }
                encoded = json.dumps(request, allow_nan=False).encode() + b"\n"
                if len(encoded) > MAX_REQUEST:
                    raise BridgeError(
                        "invalid_arguments", "Native request exceeds the 512 KiB transport limit."
                    )
                writer.write(encoded)
                await writer.drain()
                raw = await reader.readline()
                if len(raw) > MAX_RESPONSE or not raw.endswith(b"\n"):
                    raise BridgeError(
                        "invalid_response", "Bridge closed before completing a response."
                    )
                response = json.loads(raw)
                if (
                    not isinstance(response, dict)
                    or response.get("request_id") != request_id
                    or type(response.get("ok")) is not bool
                ):
                    raise BridgeError("invalid_response", "Bridge response failed validation.")
                if not response["ok"]:
                    error = response.get("error", {})
                    if not isinstance(error, dict):
                        raise BridgeError("invalid_response", "Invalid bridge error object.")
                    native_message = error.get("message", "")
                    safe_message = " ".join(native_message.split())[:256] if isinstance(native_message, str) else ""
                    raise BridgeError(
                        str(error.get("code", "bridge_error"))[:64],
                        safe_message or "Bridge rejected the request.",
                    )
                if not isinstance(response.get("data"), dict):
                    raise BridgeError("invalid_response", "Bridge data must be an object.")
                return response["data"]
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            return await asyncio.wait_for(
                exchange(), self.apply_timeout if command.endswith("_apply") else self.timeout
            )
        except BridgeError:
            raise
        except TimeoutError:
            if command.endswith("_apply"):
                raise BridgeError(
                    "outcome_unknown",
                    "Apply response timed out. Inspect the target before retrying; the preview may already be consumed.",
                ) from None
            raise BridgeError("timeout", "Editor did not respond before the deadline.") from None
        except OSError:
            raise BridgeError(
                "disconnected", "Editor is closed or its bridge is unavailable."
            ) from None
        except (ValueError, TypeError, AttributeError, RecursionError):
            raise BridgeError(
                "invalid_response", "Bridge returned malformed or oversized JSON."
            ) from None

    async def inspect_sessions(self) -> list[dict]:
        async def inspect(session):
            result = session.public()
            try:
                result.update(connected=True, health=await self.request(session, "health"))
            except BridgeError as error:
                result.update(connected=False, error={"code": error.code, "message": str(error)})
            return result

        return await asyncio.gather(*(inspect(s) for s in self.discover()))

    async def ensure_app_sessions(
        self, requested: dict[str, str | None] | None = None
    ) -> dict[str, dict]:
        """Find and health-check one live session for Unreal and Blender.

        ForgeMCP uses short authenticated TCP requests rather than persistent
        sockets. A successful health request verifies a session for the caller;
        it does not keep an application connection open between MCP calls.
        """
        requested = requested or {}
        found = self.discover()

        async def resolve(kind: str) -> dict:
            candidates = [session for session in found if session.kind == kind]
            session_id = requested.get(kind)
            if session_id:
                candidates = [session for session in candidates if session.session_id == session_id]
                if not candidates:
                    return {
                        "connected": False,
                        "session_id": None,
                        "error": {
                            "code": "session_not_found",
                            "message": f"No registered {kind} session matches the requested ID.",
                        },
                    }

            async def probe(session: Session) -> tuple[Session, dict | None, BridgeError | None]:
                try:
                    health = await self.request(session, "health")
                    if health.get("adapter") not in {"ForgeMCP Unreal", "ForgeMCP Blender"}:
                        raise BridgeError("invalid_identity", "Bridge health identity is invalid.")
                    expected = "ForgeMCP Unreal" if kind == "unreal" else "ForgeMCP Blender"
                    if health.get("adapter") != expected:
                        raise BridgeError("invalid_identity", "Bridge application type does not match its registration.")
                    return session, health, None
                except BridgeError as error:
                    return session, None, error

            results = await asyncio.gather(*(probe(session) for session in candidates))
            live = [(session, health) for session, health, error in results if error is None]
            if len(live) == 1:
                session, health = live[0]
                return {"connected": True, "session_id": session.session_id, "health": health}
            if len(live) > 1:
                return {
                    "connected": False,
                    "session_id": None,
                    "error": {
                        "code": "ambiguous_session",
                        "message": f"Multiple live {kind} sessions responded; specify a session ID.",
                    },
                    "candidates": [session.public() for session, _ in live],
                }
            if results:
                error = results[0][2]
                return {"connected": False, "session_id": None,
                        "error": {"code": error.code, "message": str(error)}}
            return {
                "connected": False,
                "session_id": None,
                "error": {
                    "code": "session_not_found",
                    "message": f"No {kind} bridge session was found. Open the app and start its ForgeMCP bridge.",
                },
            }

        unreal, blender = await asyncio.gather(resolve("unreal"), resolve("blender"))
        return {"unreal": unreal, "blender": blender,
                "connected": unreal["connected"] and blender["connected"]}

    async def dispatch(
        self, kind: str, command: str, session_id: str | None, args: dict | None = None
    ) -> dict:
        try:
            sessions = [s for s in self.discover() if s.kind == kind]
            if session_id:
                sessions = [s for s in sessions if s.session_id == session_id]
            if not sessions:
                raise BridgeError(
                    "session_not_found",
                    f"No authorized {kind} bridge found. "
                    "Open the application and enable ForgeMCP.",
                )
            if len(sessions) > 1:
                raise BridgeError(
                    "ambiguous_session",
                    "More than one session is registered. "
                    "Use forge_list_sessions and pass an explicit session_id.",
                )
            session = sessions[0]
            data = await self.request(session, command, args)
            # Receiving a reply does not imply an apply result is completed;
            # rolled_back/partial states remain authoritative in returned data.
            log.info("Native response received: %s %s", kind, command)
            return {"ok": True, "session_id": session.session_id, "data": data}
        except BridgeError as error:
            log.warning("Native request unavailable: %s %s %s", kind, command, error.code)
            return {"ok": False, "error": {"code": error.code, "message": str(error)}}
