"""Verify export through real MCP stdio and a separate factory-startup Blender."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROBE = """
import os, sys, time
from pathlib import Path
sys.path.insert(0, os.environ["FORGE_EXPORT_ADDON_ROOT"])
import majestic_forge
majestic_forge.register()
deadline = time.monotonic() + 90
try:
    while time.monotonic() < deadline and not Path(os.environ["FORGE_EXPORT_STOP_FILE"]).exists():
        majestic_forge._bridge.tick()
        time.sleep(0.01)
finally:
    majestic_forge.unregister()
"""


async def verify(blender):
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="forgemcp-export-mcp-") as temp:
        root = Path(temp)
        sessions = root / "sessions"
        sessions.mkdir()
        stop = root / "stop"
        probe = root / "probe.py"
        probe.write_text(PROBE, encoding="utf-8")
        env = {
            **os.environ,
            "FORGE_PROJECT_ROOT": str(root),
            "FORGE_BLENDER_SESSION_DIR": str(sessions),
            "FORGE_EXPORT_ADDON_ROOT": str(project / "blender-addon"),
            "FORGE_EXPORT_STOP_FILE": str(stop),
        }
        with (root / "blender.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    str(blender),
                    "--background",
                    "--factory-startup",
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(probe),
                ],
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 30
                while not list(sessions.glob("blender-*.json")):
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError("Disposable Blender did not register a live bridge")
                    await asyncio.sleep(0.05)
                params = StdioServerParameters(
                    command=sys.executable,
                    args=["-m", "server.main"],
                    cwd=str(project),
                    env=env,
                )
                async with stdio_client(params) as (reader, writer):
                    async with ClientSession(reader, writer) as client:
                        await client.initialize()
                        tools = {t.name for t in (await client.list_tools()).tools}
                        assert {"blender_preview_export", "blender_apply_export"} <= tools
                        registered = (
                            await client.call_tool("forge_list_sessions", {})
                        ).structuredContent
                        live = registered["data"]["sessions"]
                        assert (
                            len(live) == 1 and live[0]["connected"] and live[0]["kind"] == "blender"
                        )
                        sid = live[0]["session_id"]
                        before = (
                            await client.call_tool("blender_scene_info", {"session_id": sid})
                        ).structuredContent
                        preview = (
                            await client.call_tool(
                                "blender_preview_export", {"name": "Cube", "session_id": sid}
                            )
                        ).structuredContent
                        assert preview["ok"], preview
                        pid = preview["data"]["preview_id"]
                        args = {"preview_id": pid, "confirmation": pid, "session_id": sid}
                        exported = (
                            await client.call_tool("blender_apply_export", args)
                        ).structuredContent
                        assert exported["ok"] and exported["data"]["status"] == "exported", exported
                        data = exported["data"]
                        artifact = sessions / "transfers" / sid / pid / data["artifact_name"]
                        assert (
                            hashlib.sha256(artifact.read_bytes()).hexdigest()
                            == data["artifact_sha256"]
                        )
                        record = json.loads((artifact.parent / "export-report.json").read_text())
                        assert record["status"] == "exported" and record["source_session_id"] == sid
                        replay = (
                            await client.call_tool("blender_apply_export", args)
                        ).structuredContent
                        assert replay["error"]["code"] == "preview_not_found"
                        after = (
                            await client.call_tool("blender_scene_info", {"session_id": sid})
                        ).structuredContent
                        assert before["data"] == after["data"], (
                            "Export must preserve factory scene facts"
                        )
            finally:
                stop.write_text("stop", encoding="utf-8")
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
            if process.returncode:
                raise RuntimeError("Disposable Blender export process failed")
        print("FORGEMCP_REAL_STDIO_NATIVE_EXPORT_CHECKSUM_REPLAY_SCENE_PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(verify(args.blender.resolve(strict=True)))


if __name__ == "__main__":
    main()
