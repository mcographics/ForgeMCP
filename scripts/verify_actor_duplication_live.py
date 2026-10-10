"""Real MCP actor editing and Blender duplication in guarded isolated sessions only."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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

            async def call(name, args, error=None):
                result = await client.call_tool(name, args)
                assert not result.isError, name
                result = result.structuredContent
                assert result
                if error:
                    assert not result["ok"] and result["error"]["code"] == error, result
                    return result
                assert result["ok"], result
                return result["data"]

            sessions = await call("forge_list_sessions", {})
            targets = {s["kind"]: s["session_id"] for s in sessions["sessions"] if s["connected"]}
            assert set(targets) == {"unreal", "blender"}
            unreal, blender = targets["unreal"], targets["blender"]
            project = await call("unreal_project_info", {"session_id": unreal})
            assert Path(project["project_file"]).resolve().parent == expected
            scene = await call("blender_scene_info", {"session_id": blender})
            assert scene["file"] == "" and scene["object_count"] == 3
            before = await call("unreal_list_actors", {"session_id": unreal})
            preview = await call("unreal_preview_actors", {"session_id": unreal, "recipe": {
                "operations": [{"op": "spawn", "class_path": "/Script/Engine.CameraActor",
                                "label": "ForgeNativeCamera", "location": [100, 200, 300]}]
            }})
            assert (await call("unreal_list_actors", {"session_id": unreal}))["total_count"] == before["total_count"]
            await call("unreal_apply_actors", {"session_id": unreal, "preview_id": preview["preview_id"],
                                              "confirmation": "wrong"}, "confirmation_required")
            created = await call("unreal_apply_actors", {"session_id": unreal,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert created["state"] == "completed" and not created["saved"]
            path = created["actors"][0]["path"]
            assert (await call("unreal_list_actors", {"session_id": unreal}))["total_count"] == before["total_count"] + 1
            await call("unreal_apply_actors", {"session_id": unreal, "preview_id": preview["preview_id"],
                "confirmation": preview["preview_id"]}, "preview_not_found")
            actor = await call("unreal_inspect_actor", {"session_id": unreal, "actor_path": path})
            assert actor["actor"]["location"] == [100, 200, 300]
            recipe = {"operations": [
                {"op": "transform", "actor_path": path, "location": [400, 500, 600],
                 "rotation": [10, 20, 30], "scale": [2, 2, 2]},
                {"op": "visibility", "actor_path": path, "hidden": True},
            ]}
            stale = await call("unreal_preview_actors", {"session_id": unreal, "recipe": recipe})
            fresh = await call("unreal_preview_actors", {"session_id": unreal, "recipe": recipe})
            applied = await call("unreal_apply_actors", {"session_id": unreal,
                "preview_id": fresh["preview_id"], "confirmation": fresh["preview_id"]})
            assert applied["state"] == "completed", applied
            await call("unreal_apply_actors", {"session_id": unreal,
                "preview_id": stale["preview_id"], "confirmation": stale["preview_id"]}, "stale_preview")
            final = await call("unreal_inspect_actor", {"session_id": unreal, "actor_path": path})
            assert final["actor"]["location"] == [400, 500, 600]
            assert final["actor"]["scale"] == [2, 2, 2] and final["actor"]["hidden"]
            assert all(abs(a - b) < 1e-3 for a, b in zip(final["actor"]["rotation"], [10, 20, 30]))
            await call("unreal_preview_actors", {"session_id": unreal, "recipe": {
                "operations": [{"op": "spawn", "class_path": "/Script/Engine.LevelScriptActor"}]
            }}, "command_not_allowed")
            await call("unreal_preview_actors", {"session_id": unreal, "recipe": {
                "operations": [{"op": "transform", "actor_path": path, "scale": [0, 1, 1]}]
            }}, "invalid_arguments")
            source = await call("blender_inspect_object", {"session_id": blender, "name": "Cube"})
            preview = await call("blender_preview_scene", {"session_id": blender, "recipe": {
                "operations": [{"op": "duplicate_object", "source": "Cube", "name": "ForgeMCPDuplicate",
                                "location": [3, 4, 5]}]
            }})
            result = await call("blender_apply_scene", {"session_id": blender,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert result["state"] == "completed" and not result["saved"]
            duplicate = await call("blender_inspect_object", {"session_id": blender, "name": "ForgeMCPDuplicate"})
            assert duplicate["location"] == [3, 4, 5] and duplicate["mesh"] == source["mesh"]
            assert await call("blender_inspect_object", {"session_id": blender, "name": "Cube"}) == source
            report.update(project=project, actor=final, duplicate=duplicate, preserved_source=source,
                          tool_count=len((await client.list_tools()).tools))
            assert report["tool_count"] == 19
    (root / "Saved/Milestone2/actors-duplication-live-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_ACTOR_SPAWN_TRANSFORM_VISIBILITY_STALE_REPLAY_BLENDER_DUPLICATION_PASS")


if __name__ == "__main__":
    asyncio.run(main())
