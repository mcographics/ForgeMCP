"""Call all five tools through a real MCP stdio client; write a token-free report."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root), env=dict(os.environ)
    )
    report = {}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            report["available_tools"] = [t.name for t in (await client.list_tools()).tools]
            report["tools"] = [
                "forge_status",
                "forge_list_sessions",
                "unreal_project_info",
                "unreal_list_actors",
                "blender_scene_info",
            ]
            assert set(report["tools"]).issubset(report["available_tools"])
            sessions = (await client.call_tool("forge_list_sessions", {})).structuredContent
            report["forge_list_sessions"] = sessions
            live = sessions["data"]["sessions"]
            for tool, kind in [
                ("forge_status", None),
                ("unreal_project_info", "unreal"),
                ("unreal_list_actors", "unreal"),
                ("blender_scene_info", "blender"),
            ]:
                targets = [s for s in live if s["kind"] == kind and s["connected"]]
                args = {"session_id": targets[0]["session_id"]} if targets else {}
                if tool == "unreal_list_actors":
                    args["limit"] = 10
                result = await client.call_tool(tool, args)
                report[tool] = result.structuredContent
    output = root / "Saved" / "MajesticForgeValidation" / "live-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for tool in report["tools"]:
        print(f"{tool}: {'PASS' if report[tool]['ok'] else 'UNAVAILABLE'}")
    print(f"Report: {output}")
    if not all(report[t]["ok"] for t in report["tools"]):
        raise SystemExit(1)


asyncio.run(main())
