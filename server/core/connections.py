# SPDX-License-Identifier: MIT
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("majestic_forge")
MAX_RESPONSE = 1024 * 1024
COMMANDS = {
    "unreal": {
        "health",
        "project_info",
        "list_actors",
        "blueprint_preview",
        "blueprint_apply",
        "blueprint_info",
        "class_info",
        "asset_search",
        "asset_info",
        "actor_info",
        "gas_info",
        "actor_preview",
        "actor_apply",
        "level_save_preview",
        "level_save_apply",
        "blueprint_edit_preview",
        "blueprint_edit_apply",
        "mesh_import_preview",
        "mesh_import_apply",
        "mesh_info",
    },
    "blender": {"health", "scene_info", "object_info", "material_info", "rig_info", "skin_info", "scene_preview", "scene_apply", "export_preview", "export_apply"},
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
    def __init__(self, roots: list[Path], timeout: float = 10):
        self.roots = roots
        self.timeout = timeout

    @classmethod
    def configured(cls) -> ConnectionManager:
        project = Path(os.environ.get("FORGE_PROJECT_ROOT", Path(__file__).resolve().parents[2]))
        blender_root = Path(
            os.environ.get(
                "FORGE_BLENDER_SESSION_DIR",
                str(
                    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "MajesticForge" / "sessions"
                ),
            )
        )
        unreal_root = Path(os.environ.get("FORGE_UNREAL_SESSION_DIR", str(project / "Saved" / "MajesticForge")))
        return cls([unreal_root, blender_root])

    def discover(self) -> list[Session]:
        sessions = {}
        for root in self.roots:
            for path in sorted(root.glob("*.json"))[:64]:
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
                if len(encoded) > 16384:
                    raise BridgeError(
                        "invalid_arguments", "Recipe exceeds the 16 KiB request limit."
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
                    raise BridgeError(
                        str(error.get("code", "bridge_error"))[:64],
                        "Bridge rejected the request.",
                    )
                if not isinstance(response.get("data"), dict):
                    raise BridgeError("invalid_response", "Bridge data must be an object.")
                return response["data"]
            finally:
                writer.close()
                await writer.wait_closed()

        try:
            return await asyncio.wait_for(
                exchange(), 60 if command.endswith("_apply") else self.timeout
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
