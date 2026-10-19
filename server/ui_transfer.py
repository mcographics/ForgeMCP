# SPDX-License-Identifier: MIT
"""Bounded local Blender-panel client for the existing MCP transfer tools."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import ValidationError

from server.core.roundtrip import SendToBlenderRequest
from server.core.workflows import TransferRequest

MAX_LINE = 16384


def read_message():
    line = sys.stdin.buffer.readline(MAX_LINE + 1)
    if not line or len(line) > MAX_LINE or not line.endswith(b"\n"):
        raise ValueError("invalid_panel_request")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("invalid_panel_request")
    return value


def emit(value):
    print(json.dumps(value, allow_nan=False), flush=True)


def known_worker_error(error):
    if isinstance(error, BaseExceptionGroup):
        return all(known_worker_error(child) for child in error.exceptions)
    return isinstance(error, (ValueError, ValidationError, OSError, TimeoutError))


async def transfer(client, intent, confirm):
    """Keep preview and apply in one MCP session; never replay an uncertain apply."""
    async def call(name, arguments):
        result = await client.call_tool(name, arguments)
        if result.isError:
            raise ValueError("mcp_tool_failed")
        value = result.structuredContent
        if value is None:
            value = json.loads(result.content[0].text)
        if not isinstance(value, dict):
            raise ValueError("invalid_mcp_result")
        return value

    intent = dict(intent)
    mode = intent.pop("mode", "send_to_unreal")
    reverse = mode == "send_to_blender"
    if mode not in {"send_to_unreal", "import_from_blender", "send_to_blender"}:
        raise ValueError("invalid_panel_request")
    allowed = ({"source_session_id", "source_asset_path", "target_session_id", "target_object", "format"}
        if reverse else {"source_session_id", "source_object", "target_session_id",
                         "target_asset_path", "save_assets", "place", "location", "replace_existing"})
    if set(intent) - allowed:
        raise ValueError("invalid_panel_request")
    kind = "blender" if reverse or mode == "import_from_blender" else "unreal"
    field = "source_session_id" if mode == "import_from_blender" else "target_session_id"
    selected = intent.get(field, "")
    if not selected:
        sessions = await call("forge_list_sessions", {})
        if not sessions.get("ok"):
            emit({"state": "failed", "error": {"code": "session_discovery_failed"}})
            return
        targets = [s for s in sessions["data"]["sessions"] if s["kind"] == kind and s["connected"]]
        if len(targets) != 1:
            emit({"state": "failed", "error": {"code": kind + "_not_connected" if not targets else "ambiguous_session"},
                  "targets": [s["session_id"] for s in targets]})
            return
        selected = targets[0]["session_id"]
    intent[field] = selected
    if mode == "import_from_blender" and not intent.get("source_object"):
        scene = await call("blender_scene_info", {"session_id": selected})
        if not scene.get("ok") or not scene.get("data", {}).get("active_object"):
            emit({"state": "failed", "error": {"code": "source_not_selected"}})
            return
        intent["source_object"] = scene["data"]["active_object"]
    model = SendToBlenderRequest if reverse else TransferRequest
    try:
        request = model.model_validate(intent)
    except ValidationError as error:
        # Handle before leaving the MCP task group, which wraps exceptions and
        # otherwise masks an ordinary input rejection as panel_worker_failed.
        fields = {str(e["loc"][0]) for e in error.errors(include_input=False, include_url=False)
                  if e.get("loc")}
        field = next(iter(fields)) if len(fields) == 1 else None
        code = {"source_asset_path": "invalid_source_asset_path",
                "target_object": "invalid_target_object_name",
                "source_session_id": "invalid_source_session_id",
                "target_session_id": "invalid_target_session_id"}.get(field, "invalid_panel_request")
        emit({"state": "failed", "error": {"code": code}})
        return
    preview_tool = "forge_preview_send_to_blender" if reverse else "forge_preview_transfer"
    apply_tool = "forge_apply_send_to_blender" if reverse else "forge_apply_transfer"
    preview = await call(preview_tool, {"request": request.model_dump()})
    if not preview.get("ok"):
        emit({"state": "failed", "error": preview.get("error", {"code": "preview_failed"})})
        return
    plan = preview["data"]
    operation = plan["preview_id"]
    emit({"state": "preview", "preview": plan})
    approval = await confirm()
    if approval != {"confirmation": operation}:
        emit({"state": "cancelled"})
        return
    emit({"state": "applying", "operation_id": operation})
    applied = await call(apply_tool, {"preview_id": operation, "confirmation": operation})
    emit({"state": applied.get("data", {}).get("state", "outcome_unknown"),
          "operation_id": operation, "result": applied})


async def main():
    applying = False
    try:
        intent = read_message()
        # The panel may include this for display context. Discovery is user-wide;
        # a project path must never redirect session lookup.
        intent.pop("unreal_project_file", None)
        root = Path(__file__).resolve().parents[1]
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
            cwd=str(root), env={**os.environ, "FORGE_PROJECT_ROOT": str(root)})
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                async def confirm():
                    nonlocal applying
                    approval = await asyncio.wait_for(asyncio.to_thread(read_message), timeout=290)
                    applying = "confirmation" in approval
                    return approval
                await transfer(client, intent, confirm)
    except (ValueError, ValidationError, OSError, TimeoutError):
        emit({"state": "outcome_unknown" if applying else "failed",
              "error": {"code": "panel_transfer_unavailable"}})
    except Exception as error:
        # Do not echo arbitrary exception text, credentials, scene data or paths.
        emit({"state": "outcome_unknown" if applying else "failed",
              "error": {"code": "panel_transfer_unavailable" if known_worker_error(error)
                        else "panel_worker_failed"}})


if __name__ == "__main__":
    asyncio.run(main())
