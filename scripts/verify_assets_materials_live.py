"""Probe new asset/graph interfaces through MCP in explicitly isolated application sessions."""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from server.core.connections import BridgeError, ConnectionManager


async def main():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "Saved/Milestone2/HostProject").resolve()
    assert Path(os.environ["FORGE_PROJECT_ROOT"]).resolve() == expected
    assert Path(os.environ["FORGE_BLENDER_SESSION_DIR"]).resolve().is_relative_to(root / "Saved")
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                   cwd=str(root), env=dict(os.environ))
    report = {}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.isError, (name, result)
                result = result.structuredContent
                assert result and result["ok"], (name, result)
                return result["data"]

            sessions = await call("forge_list_sessions", {})
            targets = {s["kind"]: s["session_id"] for s in sessions["sessions"] if s["connected"]}
            assert set(targets) == {"unreal", "blender"}
            unreal, blender = targets["unreal"], targets["blender"]
            project = await call("unreal_project_info", {"session_id": unreal})
            assert Path(project["project_file"]).resolve().parent == expected
            scene = await call("blender_scene_info", {"session_id": blender})
            assert scene["file"] == "" and scene["object_count"] == 3
            assets = await call("unreal_search_assets", {
                "session_id": unreal, "path": "/Game/ForgeValidation",
                "class_path": "/Script/Engine.Blueprint", "limit": 1,
            })
            assert assets["total_count"] >= 1 and len(assets["assets"]) == 1, assets
            assert not assets["loads_assets"] and not assets["registry_loading"]
            assert assets["truncated"] == (assets["total_count"] > 1)
            info = await call("unreal_inspect_asset", {
                "session_id": unreal, "asset_path": assets["assets"][0]["asset_path"], "limit": 1,
            })
            assert info["asset"]["class_path"] == "/Script/Engine.Blueprint" and not info["loads_assets"]
            package_info = await call("unreal_inspect_asset", {
                "session_id": unreal, "asset_path": info["asset"]["package_name"],
            })
            assert package_info["asset"]["asset_path"] == info["asset"]["asset_path"]
            engine_references = await call("unreal_inspect_asset", {
                "session_id": unreal, "asset_path": "/Engine/EngineMaterials/WorldGridMaterial",
                "limit": 1,
            })
            assert engine_references["dependencies_total"] > 1
            assert engine_references["referencers_total"] > 1
            assert engine_references["dependencies_truncated"] and engine_references["referencers_truncated"]
            assert len(engine_references["dependencies"]) == len(engine_references["referencers"]) == 1
            page = await call("unreal_search_assets", {
                "session_id": unreal, "path": "/Game/ForgeValidation", "offset": 1,
                "class_path": "/Script/Engine.Blueprint", "limit": 1,
            })
            assert page["total_count"] == assets["total_count"]
            assert not page["assets"] or page["assets"][0]["asset_path"] != info["asset"]["asset_path"]
            empty = await call("unreal_search_assets", {
                "session_id": unreal, "name_contains": "NoSuchForgeAsset_" + uuid.uuid4().hex[:8],
            })
            assert empty["total_count"] == 0
            manager = ConnectionManager.configured()
            native_session = next(s for s in manager.discover() if s.session_id == unreal)
            for args in ({"path": "/Game/../Bad"}, {"limit": 201}, {"offset": 0.5},
                         {"path": "/Game", "python": "bad"}, {"recursive": "true"}):
                try:
                    await manager.request(native_session, "asset_search", args)
                    raise AssertionError(f"Native malformed asset query accepted: {args}")
                except BridgeError as error:
                    assert error.code == "invalid_arguments", error.code
            name = "ForgeMCPShader_" + uuid.uuid4().hex[:8]
            recipe = {"operations": [{"op": "create_material", "name": name, "color": [0.2, 0.3, 0.4, 1],
                "shader_nodes": [
                    {"id": "noise", "type": "ShaderNodeTexNoise", "inputs": {"Scale": 2}},
                    {"id": "surface", "type": "ShaderNodeBsdfPrincipled",
                     "inputs": {"Metallic": 0.4, "Roughness": 0.3}},
                    {"id": "output", "type": "ShaderNodeOutputMaterial"},
                ], "shader_links": [
                    {"from_node": "noise", "from_socket": "Color", "to_node": "surface", "to_socket": "Base Color"},
                    {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "Surface"},
                ]}]}
            preview = await call("blender_preview_scene", {"session_id": blender, "recipe": recipe})
            apply = await call("blender_apply_scene", {"session_id": blender,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert apply["state"] == "completed" and not apply["saved"], apply
            material = await call("blender_inspect_material", {"session_id": blender, "name": name})
            assert material["total_nodes"] == 3 and material["total_links"] == 2
            assert all(link["valid"] for link in material["links"])
            assert len((await client.list_tools()).tools) == 19
            report.update(project=project, assets=assets, asset_info=info, next_page=page,
                          engine_references=engine_references, material=material,
                          native_invalid_argument_cases=5, tool_count=19)
    output = root / "Saved/Milestone2/assets-materials-live-report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_ASSET_SEARCH_METADATA_REFERENCES_PAGINATION_MATERIAL_GRAPH_PASS")


if __name__ == "__main__":
    asyncio.run(main())
