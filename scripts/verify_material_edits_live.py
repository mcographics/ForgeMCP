"""Verify existing native material input editing through MCP in factory Blender."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    assert Path(os.environ["FORGE_BLENDER_SESSION_DIR"]).resolve().is_relative_to(root / "Saved")
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                   cwd=str(root), env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args):
                response = await client.call_tool(name, args)
                assert not response.isError, response
                result = response.structuredContent
                assert result and result["ok"], result
                return result["data"]

            sessions = await call("forge_list_sessions", {})
            targets = [s for s in sessions["sessions"] if s["kind"] == "blender" and s["connected"]]
            assert len(targets) == 1
            session = targets[0]["session_id"]
            scene = await call("blender_scene_info", {"session_id": session})
            assert scene["file"] == "" and scene["object_count"] == 3

            async def apply(recipe):
                preview = await call("blender_preview_scene", {"session_id": session, "recipe": recipe})
                result = await call("blender_apply_scene", {"session_id": session,
                    "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
                assert result["state"] == "completed" and not result["saved"], result
                return preview, result

            await apply({"operations": [
                {"op": "create_material", "name": "ForgeExistingMCPMaterial", "color": [0.2, 0.3, 0.4, 1]},
                {"op": "assign_material", "name": "Cube", "material": "ForgeExistingMCPMaterial"},
            ]})
            before = await call("blender_inspect_material", {"session_id": session, "name": "ForgeExistingMCPMaterial"})
            surface = next(n for n in before["nodes"] if n["type"] == "ShaderNodeBsdfPrincipled")
            preview, result = await apply({"operations": [
                {"op": "set_material_input", "name": before["name"], "node": surface["id"], "socket": "Roughness", "value": 0.25},
                {"op": "set_material_input", "name": before["name"], "node": surface["id"], "socket": "Base Color", "value": [0.8, 0.1, 0.2, 1]},
            ]})
            assert preview["material_edits"][0]["object_users"] == ["Cube"]
            after = await call("blender_inspect_material", {"session_id": session, "name": before["name"]})
            changed = next(n for n in after["nodes"] if n["id"] == surface["id"])
            pins = {pin["name"]: pin for pin in changed["inputs"]}
            assert abs(pins["Roughness"]["default"] - 0.25) < 1e-6
            assert all(abs(a - b) < 1e-6 for a, b in zip(pins["Base Color"]["default"], [0.8, 0.1, 0.2, 1]))
            (root / "Saved/Milestone2/material-edits-live-report.json").write_text(
                json.dumps({"before": before, "apply": result, "after": after}, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_EXISTING_MATERIAL_ROUGHNESS_RGBA_INPUT_EDITS_PASS")


if __name__ == "__main__":
    asyncio.run(main())
