import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from server.core.workflow_journal import WorkflowJournal

TOOLS = {
    "forge_status",
    "forge_list_sessions",
    "unreal_project_info",
    "unreal_list_actors",
    "blender_scene_info",
}
ADDITIONAL = {
    "blender_inspect_skin",
    "unreal_reconcile_level_save",
    "unreal_preview_level_save",
    "unreal_apply_level_save",
    "forge_preview_asset_recovery",
    "forge_apply_asset_recovery",
    "forge_reconcile_transfer",
    "unreal_inspect_static_mesh",
    "forge_preview_transfer",
    "forge_apply_transfer",
    "forge_inspect_transfer",
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
    "blender_preview_export",
    "blender_apply_export",
}


async def test_real_stdio_discovery_and_disconnected_tools(tmp_path):
    receipt_id = "a" * 32
    WorkflowJournal(tmp_path / "Saved" / "ForgeWorkflows").create(
        receipt_id, {"source_session_id": "blender-123"}
    )
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
                    tool.name not in {"unreal_apply_level_save", "unreal_apply_blueprint", "unreal_apply_blueprint_edits", "unreal_apply_actors", "blender_apply_scene", "blender_apply_export", "forge_apply_transfer", "forge_apply_asset_recovery"}
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
            receipt = await client.call_tool("forge_inspect_transfer", {"operation_id": receipt_id})
            assert receipt.structuredContent["ok"]
            assert receipt.structuredContent["data"]["effective_state"] == "prepared"
            assert receipt.structuredContent["data"]["runtime_state_verified"] is False
            missing_receipt = await client.call_tool("forge_inspect_transfer", {"operation_id": "0" * 32})
            assert missing_receipt.structuredContent["error"]["code"] == "operation_not_found"
            invalid_receipt = await client.call_tool("forge_inspect_transfer", {"operation_id": "../outside"})
            assert invalid_receipt.isError
            unavailable_transfer = await client.call_tool("forge_preview_transfer", {"request": {
                "source_session_id": "blender-123", "target_session_id": "unreal-456",
                "source_object": "Cube", "target_asset_path": "/Game/ForgeTransfer/SM_Cube",
            }})
            assert unavailable_transfer.structuredContent["error"]["code"] == "session_not_found"
            invalid_transfer = await client.call_tool("forge_apply_transfer", {
                "preview_id": "../bad", "confirmation": "../bad",
            })
            assert invalid_transfer.isError
            placement = {
                "op": "spawn", "class_path": "/Script/Engine.StaticMeshActor",
                "mesh_path": "/Game/ForgeTransfer/SM_Cube.SM_Cube",
            }
            disconnected = await client.call_tool("unreal_preview_actors", {
                "session_id": "missing", "recipe": {"operations": [placement]},
            })
            assert disconnected.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool("unreal_preview_actors", {
                "session_id": "missing", "recipe": {"operations": [{
                    **placement, "class_path": "/Script/Engine.PointLight",
                }]},
            })
            assert invalid.isError
            export = await client.call_tool("blender_preview_export", {"name": "Cube", "session_id": "missing"})
            assert export.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool("blender_preview_export", {"name": "x" * 129, "session_id": "missing"})
            assert invalid.isError
            invalid = await client.call_tool("blender_apply_export", {"preview_id": "../bad", "confirmation": "../bad", "session_id": "missing"})
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
