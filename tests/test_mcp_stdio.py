import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS = {
    "forge_status",
    "forge_list_sessions",
    "unreal_project_info",
    "unreal_list_actors",
    "blender_scene_info",
}
ADDITIONAL = {
    "unreal_preview_blueprint_edits",
    "unreal_apply_blueprint_edits",
    "unreal_inspect_actor",
    "unreal_inspect_gas",
    "unreal_preview_actors",
    "unreal_apply_actors",
    "unreal_search_assets",
    "unreal_inspect_asset",
    "blender_inspect_material",
    "forge_search_api_docs",
    "unreal_class_info",
    "unreal_inspect_blueprint",
    "unreal_preview_blueprint",
    "unreal_apply_blueprint",
    "blender_inspect_object",
    "blender_inspect_rig",
    "blender_preview_scene",
    "blender_apply_scene",
}


async def test_real_stdio_discovery_and_disconnected_tools(tmp_path):
    env = {
        **os.environ,
        "FORGE_PROJECT_ROOT": str(tmp_path),
        "FORGE_BLENDER_SESSION_DIR": str(tmp_path / "blender"),
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.main"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            initialized = await client.initialize()
            assert initialized.serverInfo.name == "ForgeMCP"
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == TOOLS | ADDITIONAL
            for tool in tools:
                assert tool.annotations.readOnlyHint == (
                    tool.name not in {"unreal_apply_blueprint", "unreal_apply_blueprint_edits", "unreal_apply_actors", "blender_apply_scene"}
                )
            for name in TOOLS:
                result = await client.call_tool(name, {})
                assert not result.isError
                assert result.structuredContent is not None
                if name in {"forge_status", "forge_list_sessions"}:
                    assert result.structuredContent["ok"]
                    if name == "forge_status":
                        assert result.structuredContent["data"]["server"] == "ForgeMCP"
                else:
                    assert result.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool("unreal_list_actors", {"limit": 1001})
            assert invalid.isError
            disconnected = await client.call_tool(
                "unreal_inspect_gas", {"session_id": "missing", "actor_path": "/Game/Test.Actor"}
            )
            assert disconnected.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool(
                "unreal_inspect_gas", {"session_id": "test", "actor_path": "x" * 513}
            )
            assert invalid.isError
            invalid = await client.call_tool(
                "unreal_preview_blueprint",
                {"session_id": "test", "recipe": {"asset_path": "/Engine/Overwrite"}},
            )
            assert invalid.isError
            missing = await client.call_tool(
                "unreal_apply_blueprint",
                {"session_id": "missing", "preview_id": "p", "confirmation": "p"},
            )
            assert missing.structuredContent["error"]["code"] == "session_not_found"
