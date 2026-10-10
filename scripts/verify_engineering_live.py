"""Milestone-2 native recipes through MCP; only explicitly isolated test sessions."""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    expected_root = (root / "Saved" / "Milestone2" / "HostProject").resolve()
    assert Path(os.environ["FORGE_PROJECT_ROOT"]).resolve() == expected_root
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root), env=dict(os.environ)
    )
    report = {}
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.isError, name
                data = result.structuredContent
                assert data and data["ok"], (name, data)
                return data["data"]

            sessions = await call("forge_list_sessions", {})
            targets = {s["kind"]: s["session_id"] for s in sessions["sessions"] if s["connected"]}
            assert set(targets) == {"unreal", "blender"}
            unreal, blender = targets["unreal"], targets["blender"]
            project = await call("unreal_project_info", {"session_id": unreal})
            assert Path(project["project_file"]).resolve().parent == expected_root
            scene = await call("blender_scene_info", {"session_id": blender})
            assert scene["file"] == "" and scene["object_count"] == 3
            report["class_info"] = await call(
                "unreal_class_info", {"class_path": "/Script/Engine.Actor", "session_id": unreal}
            )
            assert report["class_info"]["total_functions"] > 0
            suffix = uuid.uuid4().hex[:8]
            recipe = {
                "asset_path": f"/Game/ForgeValidation/BP_ForgeProof_{suffix}",
                "variables": [{"name": "Speed", "type": "float", "default": "2.0"}],
                "components": [
                    {"name": "ForgeMesh", "class_path": "/Script/Engine.StaticMeshComponent"}
                ],
                "functions": ["ForgeHelper"],
                "nodes": [
                    {"id": "begin", "kind": "event", "name": "ReceiveBeginPlay"},
                    {
                        "id": "set",
                        "kind": "variable_set",
                        "name": "Speed",
                        "x": 300,
                        "defaults": {"Speed": "6.5"},
                    },
                    {"id": "get", "kind": "variable_get", "name": "Speed", "x": 300, "y": 300},
                    {"id": "custom", "kind": "custom_event", "name": "ForgeTriggered", "y": 600},
                    {
                        "id": "print",
                        "kind": "call_function",
                        "name": "PrintString",
                        "owner_class": "/Script/Engine.KismetSystemLibrary",
                        "x": 600,
                        "defaults": {"InString": "ForgeMCP native proof"},
                    },
                ],
                "connections": [
                    {
                        "from_node": "begin",
                        "from_pin": "then",
                        "to_node": "set",
                        "to_pin": "execute",
                    }
                ],
                "place": True,
                "save": True,
                "location": [100, 0, 100],
            }
            preview = await call(
                "unreal_preview_blueprint", {"session_id": unreal, "recipe": recipe}
            )
            report["blueprint_apply"] = await call(
                "unreal_apply_blueprint",
                {
                    "session_id": unreal,
                    "preview_id": preview["preview_id"],
                    "confirmation": preview["preview_id"],
                },
            )
            result = report["blueprint_apply"]
            assert (
                result["state"] == "completed"
                and result["compiler_errors"] == 0
                and result["saved"]
                and result["placed"]
            ), result
            report["blueprint_inspection"] = await call(
                "unreal_inspect_blueprint",
                {"session_id": unreal, "asset_path": recipe["asset_path"]},
            )
            assert any(v["name"] == "Speed" for v in result["variables"])
            assert any(c["name"] == "ForgeMesh" for c in result["components"])
            bad = {
                **recipe,
                "asset_path": f"/Game/ForgeValidation/BP_InvalidPins_{suffix}",
                "save": False,
                "place": False,
                "connections": [
                    {
                        "from_node": "begin",
                        "from_pin": "missing",
                        "to_node": "set",
                        "to_pin": "execute",
                    }
                ],
            }
            preview = await call("unreal_preview_blueprint", {"session_id": unreal, "recipe": bad})
            report["blueprint_rollback"] = await call(
                "unreal_apply_blueprint",
                {
                    "session_id": unreal,
                    "preview_id": preview["preview_id"],
                    "confirmation": preview["preview_id"],
                },
            )
            assert (
                report["blueprint_rollback"]["state"] == "rolled_back"
                and not report["blueprint_rollback"]["saved"]
            )
            # Same path can be previewed again: failed scratch packages were discarded.
            await call(
                "unreal_preview_blueprint",
                {"session_id": unreal, "recipe": {**bad, "connections": []}},
            )
            replay = (
                await client.call_tool(
                    "unreal_apply_blueprint",
                    {
                        "session_id": unreal,
                        "preview_id": preview["preview_id"],
                        "confirmation": preview["preview_id"],
                    },
                )
            ).structuredContent
            assert replay["error"]["code"] == "preview_not_found"
            bpy_recipe = {
                "operations": [
                    {
                        "op": "create_material",
                        "name": "ForgeProofMaterial",
                        "color": [0.1, 0.5, 0.9, 1],
                    },
                    {
                        "op": "create_mesh",
                        "name": "ForgeProofMesh",
                        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                        "faces": [[0, 1, 2]],
                    },
                    {
                        "op": "assign_material",
                        "name": "ForgeProofMesh",
                        "material": "ForgeProofMaterial",
                    },
                    {"op": "set_transform", "name": "ForgeProofMesh", "location": [2, 0, 0]},
                    {"op": "keyframe", "name": "ForgeProofMesh", "frame": 30},
                    {"op": "scene_settings", "fps": 30},
                ]
            }
            preview = await call(
                "blender_preview_scene", {"session_id": blender, "recipe": bpy_recipe}
            )
            report["blender_apply"] = await call(
                "blender_apply_scene",
                {
                    "session_id": blender,
                    "preview_id": preview["preview_id"],
                    "confirmation": preview["preview_id"],
                },
            )
            assert report["blender_apply"]["state"] == "completed", report["blender_apply"]
            report["object_inspection"] = await call(
                "blender_inspect_object", {"session_id": blender, "name": "ForgeProofMesh"}
            )
            assert report["object_inspection"]["location"] == [2, 0, 0]
            assert report["object_inspection"]["mesh"]["faces"] == 1
            assert report["object_inspection"]["action"]
    output = root / "Saved" / "Milestone2" / "engineering-live-report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_BLUEPRINT_COMPILE_SAVE_PLACE_GRAPH_ROLLBACK_AND_BLENDER_RECIPES_PASS")
    print(f"Token-free report: {output}")


asyncio.run(main())
