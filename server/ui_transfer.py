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

    if set(intent) - {"source_session_id", "source_object", "target_session_id",
                      "target_asset_path", "save_assets", "place", "location"}:
        raise ValueError("invalid_panel_request")
    selected = intent.get("target_session_id", "")
    if not selected:
        sessions = await call("forge_list_sessions", {})
        if not sessions.get("ok"):
            emit({"state": "failed", "error": {"code": "session_discovery_failed"}})
            return
        targets = [s for s in sessions["data"]["sessions"]
                   if s["kind"] == "unreal" and s["connected"]]
        if len(targets) != 1:
            emit({"state": "failed", "error": {"code": "unreal_not_connected" if not targets else "ambiguous_session"},
                  "targets": [s["session_id"] for s in targets]})
            return
        selected = targets[0]["session_id"]
    request = TransferRequest.model_validate({**intent, "target_session_id": selected})
    preview = await call("forge_preview_transfer", {"request": request.model_dump()})
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
    applied = await call("forge_apply_transfer", {"preview_id": operation, "confirmation": operation})
    emit({"state": applied.get("data", {}).get("state", "outcome_unknown"),
          "operation_id": operation, "result": applied})


async def main():
    applying = False
    try:
        intent = read_message()
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
    except Exception:
        # Do not echo arbitrary exception text, credentials, scene data or paths.
        emit({"state": "outcome_unknown" if applying else "failed",
              "error": {"code": "panel_worker_failed"}})


if __name__ == "__main__":
    asyncio.run(main())
