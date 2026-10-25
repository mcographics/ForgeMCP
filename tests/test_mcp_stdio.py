import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from server.core.workflow_journal import WorkflowJournal

TOOLS = {
    "forge_status",
    "forge_list_sessions",
    "forge_ensure_connected",
    "unreal_project_info",
    "unreal_read_editor_log",
    "unreal_capture_screenshot",
    "unreal_list_actors",
    "unreal_get_selected_actors",
    "unreal_read_editor_log",
    "blender_scene_info",
}
ADDITIONAL = {
    "unreal_read_landscape_height_region",
    "unreal_landscape_edit_session_preflight", "unreal_request_landscape_edit_session",
    "unreal_landscape_edit_session_status", "unreal_revoke_landscape_edit_session",
    "unreal_landscape_adoption_preflight", "unreal_request_landscape_adoption",
    "unreal_inspect_landscape", "unreal_preview_landscape", "unreal_apply_landscape",
    "unreal_landscape_job_status", "unreal_cancel_landscape_job",
    "unreal_query_collision",
    "unreal_inspect_dirty_packages",
    "blender_list_commands", "blender_inspect_command", "blender_list_rna_types",
    "blender_inspect_rna_type", "blender_inspect_properties", "blender_preview_creative",
    "blender_apply_creative", "blender_render_job_status", "blender_cancel_render_job",
    "unreal_preview_csv_import",
    "unreal_apply_csv_import",
    "unreal_preview_struct_tooltips",
    "unreal_apply_struct_tooltips",
    "unreal_find_actors",
    "blender_inspect_animation",
    "forge_compare_mesh_binding",
    "unreal_inspect_mesh_binding",
    "blender_inspect_mesh_binding",
    "forge_preview_send_to_blender",
    "forge_apply_send_to_blender",
    "unreal_inspect_material_graph",
    "unreal_preview_material",
    "unreal_apply_material",
    "unreal_preview_material_edits",
    "unreal_apply_material_edits",
    "unreal_preview_material_compile",
    "unreal_compile_material",
    "unreal_preview_material_save",
    "unreal_save_material",
    "unreal_inspect_material_instance",
    "unreal_preview_material_instance",
    "unreal_apply_material_instance",
    "unreal_preview_material_instance_save",
    "unreal_save_material_instance",
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
    "unreal_inspect_actor_components",
    "unreal_inspect_component_properties",
    "unreal_preview_component_property_edit",
    "unreal_apply_component_property_edit",
    "unreal_inspect_actor_properties",
    "unreal_preview_actor_property_edit",
    "unreal_apply_actor_property_edit",
    "unreal_inspect_gas",
    "unreal_preview_actors",
    "unreal_apply_actors",
    "unreal_preview_actor_delete",
    "unreal_apply_actor_delete",
    "unreal_preview_current_level_save",
    "unreal_apply_current_level_save",
    "unreal_reconcile_current_level_save",
    "unreal_preview_empty_open_world",
    "unreal_apply_empty_open_world",
    "unreal_search_assets",
    "unreal_list_data_assets",
    "unreal_list_data_asset_classes",
    "unreal_inspect_data_asset_schema",
    "unreal_preview_data_asset",
    "unreal_apply_data_asset",
    "unreal_preview_data_asset_edit",
    "unreal_apply_data_asset_edit",
    "unreal_inspect_asset",
    "unreal_get_selected_assets",
    "unreal_open_asset",
    "unreal_sync_content_browser",
    "unreal_inspect_asset_properties",
    "unreal_inspect_data_table_schema",
    "unreal_list_data_table_rows",
    "unreal_inspect_data_table_row",
    "unreal_preview_asset_property_edit",
    "unreal_apply_asset_property_edit",
    "blender_inspect_material",
    "forge_search_api_docs",
    "unreal_class_info",
    "unreal_inspect_blueprint",
    "unreal_preview_blueprint",
    "unreal_apply_blueprint",
    "blender_inspect_object",
    "blender_inspect_mesh_geometry",
    "blender_inspect_mesh_edges",
    "blender_inspect_mesh_uvs",
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
        "FORGE_UNREAL_SESSION_DIR": str(tmp_path / "unreal"),
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
            dirty_tool = next(tool for tool in tools if tool.name == "unreal_inspect_dirty_packages")
            request_schema = dirty_tool.inputSchema["$defs"]["DirtyPackageInspectionRequest"]
            assert "snapshot_id" in request_schema["properties"]
            assert "snapshot_id" not in request_schema.get("required", [])
            snapshot_schema = request_schema["properties"]["snapshot_id"]
            assert {"type": "null"} in snapshot_schema["anyOf"]
            assert any(
                item.get("type") == "string" and item.get("minLength") == 32 and item.get("maxLength") == 32
                for item in snapshot_schema["anyOf"]
            )
            for tool in tools:
                assert tool.annotations.readOnlyHint == (tool.name not in {
                    "unreal_revoke_landscape_edit_session",
                    "blender_apply_creative", "blender_cancel_render_job",
                    "unreal_apply_landscape", "unreal_cancel_landscape_job",
                    "forge_apply_send_to_blender", "unreal_apply_material", "unreal_apply_material_edits",
                    "unreal_compile_material", "unreal_save_material", "unreal_apply_material_instance",
                    "unreal_save_material_instance", "unreal_apply_level_save", "unreal_apply_blueprint",
                    "unreal_apply_blueprint_edits", "unreal_apply_actors", "unreal_apply_asset_property_edit",
                    "unreal_apply_actor_property_edit", "unreal_apply_component_property_edit",
                    "unreal_apply_actor_delete", "unreal_apply_current_level_save",
                    "unreal_apply_data_asset",
                    "unreal_apply_data_asset_edit",
                    "unreal_apply_empty_open_world",
                    "unreal_apply_csv_import",
                    "unreal_apply_struct_tooltips",
                    "unreal_open_asset", "unreal_sync_content_browser", "blender_apply_scene",
                    "blender_apply_export", "forge_apply_transfer", "forge_apply_asset_recovery",
                })
            for name in TOOLS:
                result = await client.call_tool(name, {})
                assert not result.isError
                if name == "unreal_capture_screenshot":
                    assert result.structuredContent is None
                    assert "session_not_found" in result.content[0].text
                    continue
                assert result.structuredContent is not None
                if name in {"forge_status", "forge_list_sessions", "forge_ensure_connected"}:
                    if name == "forge_ensure_connected":
                        assert not result.structuredContent["ok"]
                        assert result.structuredContent["data"]["unreal"]["error"]["code"] == "session_not_found"
                        assert result.structuredContent["data"]["blender"]["error"]["code"] == "session_not_found"
                    else:
                        assert result.structuredContent["ok"]
                    if name == "forge_status":
                        assert result.structuredContent["data"]["server"] == "ForgeMCP"
                else:
                    assert result.structuredContent["error"]["code"] == "session_not_found"
            for name, arguments in (
                ("unreal_inspect_dirty_packages", {"request": {}, "session_id": "missing"}),
                ("unreal_get_selected_assets", {"session_id": "missing"}),
                ("unreal_open_asset", {"asset_path": "/Game/Test/SM_Test", "session_id": "missing"}),
                ("unreal_sync_content_browser", {"asset_path": "/JasperPrism/Materials/M_Test.M_Test", "session_id": "missing"}),
                ("unreal_inspect_data_table_schema", {"data_table_path": "/Game/Data/DT_Test", "session_id": "missing"}),
                ("unreal_list_data_table_rows", {"data_table_path": "/Game/Data/DT_Test", "session_id": "missing"}),
                ("unreal_inspect_data_table_row", {"data_table_path": "/Game/Data/DT_Test", "row_name": "RowA", "session_id": "missing"}),
                ("unreal_preview_csv_import", {"session_id": "missing", "request": {
                    "csv_path": r"C:\Project\bodies.csv", "struct_path": "/Game/Space/ST_CelestialBodyData",
                    "data_table_path": "/Game/Data/DT_CelestialBodies", "row_key_column": "id",
                }}),
                ("unreal_apply_csv_import", {"session_id": "missing", "preview_id": "c" * 32,
                                              "confirmation": "c" * 32}),
                ("unreal_preview_struct_tooltips", {"session_id": "missing", "request": {
                    "struct_path": "/Game/Space/Blueprints/ST_CelestialBodyData",
                    "tooltips": {"ra": "Right ascension in hours."},
                }}),
                ("unreal_apply_struct_tooltips", {"session_id": "missing", "preview_id": "d" * 32,
                                                   "confirmation": "d" * 32}),
                ("unreal_list_data_assets", {"session_id": "missing"}),
                ("unreal_list_data_asset_classes", {"session_id": "missing"}),
                ("unreal_inspect_data_asset_schema", {"session_id": "missing", "class_path": "/Script/Engine.PrimaryAssetLabel"}),
            ):
                result = await client.call_tool(name, arguments)
                assert result.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool("unreal_list_actors", {"limit": 1001})
            assert invalid.isError
            missing_actor_filter = await client.call_tool("unreal_find_actors", {"session_id": "missing"})
            assert missing_actor_filter.structuredContent["error"]["code"] == "invalid_arguments"
            invalid_actor_filter_limit = await client.call_tool("unreal_find_actors", {
                "session_id": "missing", "name_contains": "Cube", "limit": 1001,
            })
            assert invalid_actor_filter_limit.isError
            invalid_actor_tag = await client.call_tool("unreal_find_actors", {
                "session_id": "missing", "tag": "",
            })
            assert invalid_actor_tag.isError
            invalid_actor_transform_flag = await client.call_tool("unreal_find_actors", {
                "session_id": "missing", "tag": "ForgeProbe", "include_transform": "yes",
            })
            assert invalid_actor_transform_flag.isError
            invalid_selection_limit = await client.call_tool("unreal_get_selected_actors", {"limit": 201})
            assert invalid_selection_limit.isError
            invalid_data_table_page = await client.call_tool("unreal_list_data_table_rows", {
                "session_id": "missing", "data_table_path": "/Game/Data/DT_Test", "limit": 101,
            })
            assert invalid_data_table_page.isError
            invalid_data_table_row_name = await client.call_tool("unreal_inspect_data_table_row", {
                "session_id": "missing", "data_table_path": "/Game/Data/DT_Test", "row_name": "",
            })
            assert invalid_data_table_row_name.isError
            invalid_data_asset_limit = await client.call_tool("unreal_list_data_assets", {
                "session_id": "missing", "max_results": 201,
            })
            assert invalid_data_asset_limit.isError
            invalid_data_asset_class_limit = await client.call_tool("unreal_list_data_asset_classes", {
                "session_id": "missing", "limit": 201,
            })
            assert invalid_data_asset_class_limit.isError
            invalid_data_asset_schema_limit = await client.call_tool("unreal_inspect_data_asset_schema", {
                "session_id": "missing", "class_path": "/Script/Engine.PrimaryAssetLabel", "limit": 257,
            })
            assert invalid_data_asset_schema_limit.isError
            data_asset_preview = await client.call_tool("unreal_preview_data_asset", {
                "session_id": "missing",
                "request": {"asset_path": "/Game/Forge/DA_MCPProbe",
                            "class_path": "/Script/Engine.PrimaryAssetLabel",
                            "properties": [{"name": "bIsRuntimeLabel", "value": "true"}],
                            "save": True},
            })
            assert data_asset_preview.structuredContent["error"]["code"] == "session_not_found"
            invalid_data_asset_save_type = await client.call_tool("unreal_preview_data_asset", {
                "session_id": "missing",
                "request": {"asset_path": "/Game/Forge/DA_MCPProbe",
                            "class_path": "/Script/Engine.PrimaryAssetLabel", "save": "true"},
            })
            assert invalid_data_asset_save_type.isError
            data_asset_edit_preview = await client.call_tool("unreal_preview_data_asset_edit", {
                "session_id": "missing",
                "request": {"asset_path": "/Game/Forge/DA_MCPProbe.DA_MCPProbe",
                            "properties": [{"name": "bIsRuntimeLabel", "value": "true"}],
                            "save": True},
            })
            assert data_asset_edit_preview.structuredContent["error"]["code"] == "session_not_found"
            data_asset_edit_apply = await client.call_tool("unreal_apply_data_asset_edit", {
                "session_id": "missing", "preview_id": "c" * 32, "confirmation": "c" * 32,
            })
            assert data_asset_edit_apply.structuredContent["error"]["code"] == "session_not_found"
            invalid_data_asset_edit = await client.call_tool("unreal_preview_data_asset_edit", {
                "session_id": "missing",
                "request": {"asset_path": "/Game/Forge/DA_MCPProbe.Other",
                            "properties": [{"name": "bIsRuntimeLabel", "value": "true"}]},
            })
            assert invalid_data_asset_edit.isError
            invalid_editor_log_limit = await client.call_tool("unreal_read_editor_log", {"limit": 201})
            assert invalid_editor_log_limit.isError
            unavailable_screenshot = await client.call_tool("unreal_capture_screenshot", {})
            assert unavailable_screenshot.structuredContent is None
            assert "session_not_found" in unavailable_screenshot.content[0].text
            invalid_mesh_geometry_page = await client.call_tool("blender_inspect_mesh_geometry", {
                "name": "Cube", "session_id": "missing", "vertex_count": 257,
            })
            assert invalid_mesh_geometry_page.isError
            invalid_uv_page = await client.call_tool("blender_inspect_mesh_uvs", {
                "name": "Cube", "session_id": "missing", "loop_count": 257,
            })
            assert invalid_uv_page.isError
            invalid_edge_page = await client.call_tool("blender_inspect_mesh_edges", {
                "name": "Cube", "session_id": "missing", "edge_count": 257,
            })
            assert invalid_edge_page.isError
            graph_edit_preview = await client.call_tool("blender_preview_scene", {
                "session_id": "missing",
                "recipe": {"operations": [{
                    "op": "edit_material_graph", "name": "Existing Material",
                    "shader_nodes": [{"id": "ForgeRoughness", "type": "ShaderNodeValue"}],
                    "shader_links": [{"from_node": "ForgeRoughness", "from_socket": "Value",
                                      "to_node": "Principled BSDF", "to_socket": "Roughness"}],
                }]},
            })
            assert graph_edit_preview.structuredContent["error"]["code"] == "session_not_found"
            graph_output_replacement = await client.call_tool("blender_preview_scene", {
                "session_id": "missing",
                "recipe": {"operations": [{
                    "op": "edit_material_graph", "name": "Existing Material",
                    "shader_nodes": [{"id": "ReplacementOutput", "type": "ShaderNodeOutputMaterial"}],
                }]},
            })
            assert graph_output_replacement.isError
            missing_animation = await client.call_tool("blender_inspect_animation", {
                "name": "Cube", "session_id": "missing"})
            assert missing_animation.structuredContent["error"]["code"] == "session_not_found"
            invalid_animation_curve_page = await client.call_tool("blender_inspect_animation", {
                "name": "Cube", "session_id": "missing", "curve_count": 33})
            assert invalid_animation_curve_page.isError
            property_preview = await client.call_tool("unreal_preview_asset_property_edit", {
                "session_id": "missing",
                "request": {"asset_path": "/Game/Test/SM_Test", "property_name": "LightMapResolution", "property_value": "128"},
            })
            assert property_preview.structuredContent["error"]["code"] == "session_not_found"
            property_apply = await client.call_tool("unreal_apply_asset_property_edit", {
                "session_id": "missing", "preview_id": "a" * 32, "confirmation": "a" * 32,
            })
            assert property_apply.structuredContent["error"]["code"] == "session_not_found"
            invalid_property = await client.call_tool("unreal_preview_asset_property_edit", {
                "session_id": "missing",
                "request": {"asset_path": "/Engine/EngineMaterials/DefaultMaterial", "property_name": "b", "property_value": "true"},
            })
            assert invalid_property.isError
            actor_properties = await client.call_tool("unreal_inspect_actor_properties", {
                "session_id": "missing", "actor_path": "/Game/Map.Map:PersistentLevel.Actor"})
            assert actor_properties.structuredContent["error"]["code"] == "session_not_found"
            actor_preview = await client.call_tool("unreal_preview_actor_property_edit", {
                "session_id": "missing", "request": {
                    "actor_path": "/Game/Map.Map:PersistentLevel.Actor",
                    "property_name": "InitialLifeSpan", "property_value": "2.0"}})
            assert actor_preview.structuredContent["error"]["code"] == "session_not_found"
            actor_apply = await client.call_tool("unreal_apply_actor_property_edit", {
                "session_id": "missing", "preview_id": "b" * 32, "confirmation": "b" * 32})
            assert actor_apply.structuredContent["error"]["code"] == "session_not_found"
            bad_actor_property = await client.call_tool("unreal_preview_actor_property_edit", {
                "session_id": "missing", "request": {
                    "actor_path": "/Game/Map.Map:PersistentLevel.Actor",
                    "property_name": "../InitialLifeSpan", "property_value": "2.0"}})
            assert bad_actor_property.isError
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
            properties = await client.call_tool("unreal_inspect_asset_properties", {
                "session_id": "missing", "asset_path": "/Game/Test/SM_Test.SM_Test",
            })
            assert properties.structuredContent["error"]["code"] == "session_not_found"
            invalid = await client.call_tool("unreal_inspect_asset_properties", {
                "session_id": "missing", "asset_path": "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial",
                "limit": 201,
            })
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


async def test_stdio_startup_authenticates_registered_bridge_without_tool_call(tmp_path):
    authenticated = asyncio.Event()
    observed = []
    token = "b" * 64

    async def handle(reader, writer):
        request = json.loads(await reader.readline())
        observed.append(request)
        writer.write(json.dumps({
            "ok": True,
            "request_id": request["request_id"],
            "data": {"adapter": "ForgeMCP Unreal"},
        }).encode() + b"\n")
        await writer.drain()
        authenticated.set()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        registry = tmp_path / "sessions"
        registry.mkdir()
        (registry / "unreal-42.json").write_text(json.dumps({
            "protocol_version": 1,
            "session_id": "unreal-42",
            "kind": "unreal",
            "host": "127.0.0.1",
            "port": port,
            "pid": 42,
            "token": token,
        }))
        env = {
            **os.environ,
            "FORGE_PROJECT_ROOT": str(tmp_path),
            "FORGE_SESSION_DIR": str(registry),
        }
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "server.main"],
            cwd=str(Path(__file__).resolve().parents[1]),
            env=env,
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                await asyncio.wait_for(authenticated.wait(), timeout=5)

    assert observed
    assert observed[0]["command"] == "health"
    assert observed[0]["token"] == token
