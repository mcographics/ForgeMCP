"""Verify armature hierarchy and bounded skin-weight inspection through real MCP."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    session_dir = Path(os.environ["FORGE_BLENDER_SESSION_DIR"]).resolve()
    assert session_dir.is_relative_to(root / "Saved")
    pid_file = Path(os.environ.get(
        "FORGE_VALIDATION_PID_FILE", str(root / "Saved/Milestone2/blender-rig-probe.pid")
    ))
    process_id = pid_file.read_text(encoding="ascii")
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                   cwd=str(root), env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = {tool.name for tool in (await client.list_tools()).tools}
            required_tools = {
                "blender_inspect_rig",
                "blender_scene_info",
                "blender_preview_scene",
                "blender_apply_scene",
            }
            assert required_tools <= tools, sorted(required_tools - tools)

            async def call(name, args):
                response = await client.call_tool(name, args)
                assert not response.isError, response
                return response.structuredContent

            sessions = await call("forge_list_sessions", {})
            target = f"blender-{process_id}"
            entries = [session for session in sessions["data"]["sessions"]
                       if session["session_id"] == target and session["connected"]]
            assert len(entries) == 1
            session_id = entries[0]["session_id"]
            args = {"session_id": session_id, "name": "ForgeRigProbe"}
            structure = await call("blender_inspect_rig", args)
            assert structure["ok"], structure
            data = structure["data"]
            assert data["bone_count"] == 2 and data["related_meshes"][0]["name"] == "ForgeWeightedMesh"
            assert not data["weights_included"]

            weighted = await call("blender_inspect_rig", {**args, "include_weights": True})
            assert weighted["ok"], weighted
            skin = weighted["data"]["related_meshes"][0]["skin_weights"]
            assert skin["Root"]["weighted_vertices"] == 2
            assert abs(skin["Root"]["weight_sum"] - 1.5) < 1e-6
            assert skin["Child"]["weighted_vertices"] == 2
            assert abs(skin["Child"]["weight_sum"] - 0.5) < 1e-6
            invalid = await call("blender_inspect_rig", {**args, "name": "Cube"})
            assert not invalid["ok"] and invalid["error"]["code"] == "rig_not_found"
            scene_before = await call("blender_scene_info", {"session_id": session_id})
            rig_recipe = {"operations": [{
                "op": "create_armature",
                "name": "ForgeMCPGeneratedRig",
                "bones": [
                    {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
                    {"name": "Spine", "head": [0, 0, 1], "tail": [0, 0, 2],
                     "parent": "Root", "connected": True},
                    {"name": "Hand", "head": [0, 0, 2], "tail": [1, 0, 2],
                     "parent": "Spine"},
                ],
            }]}
            preview = await call("blender_preview_scene", {
                "session_id": session_id, "recipe": rig_recipe,
            })
            assert preview["ok"], preview
            scene_after_preview = await call("blender_scene_info", {"session_id": session_id})
            assert scene_after_preview["data"]["object_count"] == scene_before["data"]["object_count"]
            applied = await call("blender_apply_scene", {
                "session_id": session_id,
                "preview_id": preview["data"]["preview_id"],
                "confirmation": preview["data"]["preview_id"],
            })
            assert applied["ok"] and applied["data"]["state"] == "completed", applied
            assert not applied["data"]["saved"]
            generated = await call("blender_inspect_rig", {
                "session_id": session_id, "name": "ForgeMCPGeneratedRig",
            })
            assert generated["ok"] and generated["data"]["bone_count"] == 3, generated
            assert generated["data"]["bones"][1]["parent"] == "Root"
            assert generated["data"]["bones"][1]["connected"]
            report = {
                "structure": data,
                "weights": weighted["data"],
                "invalid_mesh_query_rejected": True,
                "created_rig": generated["data"],
                "rig_apply": applied["data"],
                "preview_was_read_only": True,
                "session_id": session_id,
            }
            report_path = Path(os.environ.get(
                "FORGE_VALIDATION_REPORT_FILE",
                str(root / "Saved/Milestone2/blender-rig-live-report.json"),
            ))
            assert report_path.resolve().is_relative_to(root / "Saved")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_BLENDER_RIG_HIERARCHY_SKIN_WEIGHT_INSPECTION_PASS")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        stop_file = os.environ.get("FORGE_VALIDATION_STOP_FILE")
        if stop_file:
            Path(stop_file).touch()
