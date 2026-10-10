"""Verify real MCP retrieval against the installed exact-version reference index."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "FORGE_PROJECT_ROOT": str(root)}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root), env=environment
    )
    report = {}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            for application, version, query, symbol in [
                ("unreal", "5.6.1", "set_actor_location", "unreal.Actor.set_actor_location"),
                ("blender", "5.2.2", "from_pydata", "bpy.types.Mesh.from_pydata"),
            ]:
                result = await client.call_tool(
                    "forge_search_api_docs",
                    {"application": application, "version": version, "query": query, "limit": 20},
                )
                assert not result.isError
                content = result.structuredContent
                assert content["ok"] and content["data"]["indexed"], content
                assert any(r["symbol"] == symbol for r in content["data"]["results"]), content
                report[application] = content["data"]
            result = await client.call_tool(
                "forge_search_api_docs",
                {"application": "blender", "version": "4.0.0", "query": "mesh"},
            )
            assert result.structuredContent["data"]["results"] == []
            assert not result.structuredContent["data"]["indexed"]
    output = root / "Saved/Milestone2/api-retrieval-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FORGE_MCP_VERSION_SCOPED_UNREAL_PYTHON_AND_BLENDER_BPY_RETRIEVAL_PASS")


asyncio.run(main())
