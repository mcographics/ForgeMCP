"""Exercise typed shader output defaults through MCP in a factory Blender session."""

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
            recipe = {"operations": [{"op": "create_material", "name": "ForgeMCPConstants", "color": [0.2, 0.3, 0.4, 1],
                "shader_nodes": [
                    {"id": "color", "type": "ShaderNodeRGB", "outputs": {"Color": [0.8, 0.2, 0.1, 1]}},
                    {"id": "amount", "type": "ShaderNodeValue", "outputs": {"Value": 0.4}},
                    {"id": "surface", "type": "ShaderNodeBsdfPrincipled"},
                    {"id": "output", "type": "ShaderNodeOutputMaterial"},
                ], "shader_links": [
                    {"from_node": "color", "from_socket": "Color", "to_node": "surface", "to_socket": "Base Color"},
                    {"from_node": "amount", "from_socket": "Value", "to_node": "surface", "to_socket": "Roughness"},
                    {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "Surface"},
                ]}]}
            preview = await call("blender_preview_scene", {"session_id": session, "recipe": recipe})
            result = await call("blender_apply_scene", {"session_id": session,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert result["state"] == "completed" and not result["saved"]
            info = await call("blender_inspect_material", {"session_id": session, "name": "ForgeMCPConstants"})
            assert info["total_nodes"] == 4 and info["total_links"] == 3
            assert all(link["valid"] for link in info["links"])
            nodes = {node["id"]: node for node in info["nodes"]}
            assert abs(nodes["amount"]["outputs"][0]["default"] - 0.4) < 1e-6
            assert all(abs(a - b) < 1e-6 for a, b in zip(nodes["color"]["outputs"][0]["default"], [0.8, 0.2, 0.1, 1]))
            (root / "Saved/Milestone2/shader-constants-live-report.json").write_text(
                json.dumps({"scene": scene, "apply": result, "material": info}, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_SHADER_RGB_VALUE_OUTPUT_DEFAULTS_VALID_LINKS_PASS")


if __name__ == "__main__":
    asyncio.run(main())
