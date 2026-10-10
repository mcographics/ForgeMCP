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
            constraints = data["bones"][1]["pose"]["constraints"]
            assert constraints["count"] == 1 and not constraints["truncated"]
            ik = constraints["items"][0]
            assert ik["type"] == "IK" and ik["muted"]
            assert ik["target"] == {"name":"ForgeRigIKTarget","type":"EMPTY"}
            assert ik["ik"]["chain_count"] == 2 and ik["ik"]["iterations"] == 64
            assert data["bones"][1]["pose"]["ik_locks"] == [True,False,False]
            evaluated = await call("blender_inspect_rig", {**args, "include_evaluated": True})
            assert evaluated["ok"], evaluated
            evaluated_mesh = evaluated["data"]["related_meshes"][0]["evaluated_mesh"]
            assert evaluated["data"]["evaluated_meshes_included"] is True
            assert evaluated_mesh["vertex_count"] == 3 and not evaluated_mesh["vertices_truncated"]
            assert evaluated_mesh["world_vertices"] == [[0, 0, 0], [1, 0, 0], [0, 1, 0]]
            assert evaluated_mesh["includes_modifier_stack"] is True
            assert evaluated["ok"], evaluated
            assert evaluated["data"]["evaluated_pose_included"] is True
            assert all(len(bone["evaluated_pose"]["matrix_world"]) == 4 for bone in evaluated["data"]["bones"])

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
                    {"name": "Root", "head": [0, 0, 0], "tail": [0.2, 0, 1]},
                    {"name": "Spine", "head": [0.2, 0, 1], "tail": [0, 0, 2],
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
            skin_preview = await call("blender_preview_scene", {"session_id": session_id,
                "recipe": {"operations": [{"op": "bind_mesh", "name": "ForgeMCPSkinnedCube",
                    "source": "Cube", "armature": "ForgeRigProbe",
                    "weights": [{"vertex":index,"bone":"Root","weight":1.0} for index in range(8)]}]}})
            assert skin_preview["ok"], skin_preview
            skin_id = skin_preview["data"]["preview_id"]
            skin_applied = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":skin_id,"confirmation":skin_id})
            assert skin_applied["ok"] and skin_applied["data"]["state"] == "completed", skin_applied
            skin_inspected = await call("blender_inspect_rig", {"session_id":session_id,"name":"ForgeRigProbe",
                "include_weights":True,"include_evaluated":True})
            assert skin_inspected["ok"], skin_inspected
            bound = next(item for item in skin_inspected["data"]["related_meshes"] if item["name"] == "ForgeMCPSkinnedCube")
            assert bound["skin_weights"]["Root"]["weighted_vertices"] == 8
            assert bound["skin_weights"]["Root"]["weight_sum"] == 8
            assert bound["evaluated_mesh"]["vertex_count"] == 8
            reweight_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"reweight_mesh","source":"ForgeMCPSkinnedCube",
                    "name":"ForgeMCPReweightedCube","armature":"ForgeRigProbe",
                    "weights":[{"vertex":index,"bone":"Child","weight":1.0} for index in range(8)]}]}})
            assert reweight_preview["ok"], reweight_preview
            reweight_id = reweight_preview["data"]["preview_id"]
            reweight_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":reweight_id,"confirmation":reweight_id})
            assert reweight_apply["ok"] and reweight_apply["data"]["state"] == "completed", reweight_apply
            reweight_inspection = await call("blender_inspect_rig", {"session_id":session_id,"name":"ForgeRigProbe",
                "include_weights":True,"include_evaluated":True})
            assert reweight_inspection["ok"], reweight_inspection
            related = reweight_inspection["data"]["related_meshes"]
            new_skin = next(item for item in related if item["name"] == "ForgeMCPReweightedCube")
            original_skin = next(item for item in related if item["name"] == "ForgeMCPSkinnedCube")
            assert new_skin["skin_weights"]["Child"]["weight_sum"] == 8
            assert original_skin["skin_weights"]["Root"]["weight_sum"] == 8
            assert not new_skin["vertex_weight_samples_truncated"]
            assert new_skin["vertex_weight_samples"] == [{"vertex":index,"weights":[{"bone":"Child","weight":1.0}]} for index in range(8)]
            automatic_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"auto_bind_mesh","source":"Cube","name":"ForgeMCPAutoCube",
                    "armature":"ForgeRigProbe","weight_method":"blender_heat_top4"}]}})
            assert automatic_preview["ok"], automatic_preview
            automatic_id = automatic_preview["data"]["preview_id"]
            automatic_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":automatic_id,"confirmation":automatic_id})
            assert automatic_apply["ok"] and automatic_apply["data"]["state"] == "completed", automatic_apply
            automatic_inspection = await call("blender_inspect_rig", {"session_id":session_id,
                "name":"ForgeRigProbe","include_weights":True,"include_evaluated":True})
            assert automatic_inspection["ok"], automatic_inspection
            auto_skin = next(item for item in automatic_inspection["data"]["related_meshes"] if item["name"] == "ForgeMCPAutoCube")
            assert auto_skin["evaluated_mesh"]["vertex_count"] == 8
            for vertex in auto_skin["vertex_weight_samples"]:
                assert 1 <= len(vertex["weights"]) <= 4
                assert abs(sum(item["weight"] for item in vertex["weights"]) - 1) < 1e-5
            skin_page = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPAutoCube","vertex_start":2,"vertex_count":2})
            assert skin_page["ok"] and skin_page["data"]["next_vertex_start"] == 4, skin_page
            assert [v["vertex"] for v in skin_page["data"]["vertices"]] == [2,3]
            original_page = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPAutoCube","vertex_count":8})
            patch_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"patch_skin_weights","source":"ForgeMCPAutoCube",
                    "name":"ForgeMCPPatchedCube","armature":"ForgeRigProbe",
                    "weights":[{"vertex":2,"bone":"Root","weight":1.0}]}]}})
            assert patch_preview["ok"], patch_preview
            patch_id = patch_preview["data"]["preview_id"]
            patch_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":patch_id,"confirmation":patch_id})
            assert patch_apply["ok"] and patch_apply["data"]["state"] == "completed", patch_apply
            patched_page = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPPatchedCube","vertex_count":8})
            preserved_page = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPAutoCube","vertex_count":8})
            assert patched_page["ok"] and preserved_page["ok"]
            assert preserved_page["data"] == original_page["data"]
            patched_vertices = patched_page["data"]["vertices"]
            for original,corrected in zip(original_page["data"]["vertices"],patched_vertices):
                if original["vertex"] == 2:
                    assert corrected["weights"] == [{"bone":"Root","weight":1.0,"locked":False}]
                else:
                    assert corrected == original
            large_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"auto_bind_mesh","source":"ForgeMCPLargeSkinSource",
                    "name":"ForgeMCPLargeSkin","armature":"ForgeRigProbe",
                    "weight_method":"blender_heat_top4"}]}})
            assert large_preview["ok"], large_preview
            large_id = large_preview["data"]["preview_id"]
            large_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":large_id,"confirmation":large_id})
            assert large_apply["ok"] and large_apply["data"]["state"] == "completed", large_apply
            large_before = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPLargeSkin","vertex_start":300,"vertex_count":2})
            assert large_before["ok"] and large_before["data"]["vertex_count"] > 300, large_before
            large_patch_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"patch_skin_weights","source":"ForgeMCPLargeSkin",
                    "name":"ForgeMCPLargePatchedSkin","armature":"ForgeRigProbe",
                    "weights":[{"vertex":300,"bone":"Root","weight":1.0}]}]}})
            assert large_patch_preview["ok"], large_patch_preview
            large_patch_id = large_patch_preview["data"]["preview_id"]
            large_patch_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":large_patch_id,"confirmation":large_patch_id})
            assert large_patch_apply["ok"] and large_patch_apply["data"]["state"] == "completed", large_patch_apply
            large_after = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPLargePatchedSkin","vertex_start":300,"vertex_count":2})
            large_preserved = await call("blender_inspect_skin", {"session_id":session_id,
                "name":"ForgeMCPLargeSkin","vertex_start":300,"vertex_count":2})
            assert large_after["ok"] and large_preserved["ok"]
            assert large_preserved["data"] == large_before["data"]
            assert large_after["data"]["vertices"][0]["weights"] == [{"bone":"Root","weight":1.0,"locked":False}]
            assert large_after["data"]["vertices"][1] == large_before["data"]["vertices"][1]
            target_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"create_empty","name":"ForgeMCPControlTarget",
                    "location":[0.7,0,1.5]},
                    {"op":"create_empty","name":"ForgeMCPPoleTarget","location":[0,2,1]}]}})
            assert target_preview["ok"], target_preview
            target_id = target_preview["data"]["preview_id"]
            target_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":target_id,"confirmation":target_id})
            assert target_apply["ok"] and target_apply["data"]["state"] == "completed", target_apply
            ik_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"create_ik_constraint","name":"ForgeMCPGeneratedRig",
                    "ik":{"bone":"Spine","constraint":"ForgeControlIK","target":"ForgeMCPControlTarget",
                          "chain_count":2,"iterations":128,"pole_target":"ForgeMCPPoleTarget",
                          "pole_angle":0.0}}]}})
            assert ik_preview["ok"], ik_preview
            ik_id = ik_preview["data"]["preview_id"]
            ik_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":ik_id,"confirmation":ik_id})
            assert ik_apply["ok"] and ik_apply["data"]["state"] == "completed", ik_apply
            assert ik_apply["data"]["operations"][0]["target_reached"], ik_apply
            ik_inspected = await call("blender_inspect_rig", {"session_id":session_id,
                "name":"ForgeMCPGeneratedRig","include_evaluated":True})
            assert ik_inspected["ok"], ik_inspected
            tail = ik_inspected["data"]["bones"][1]["evaluated_pose"]["tail_world"]
            assert sum((a-b)**2 for a,b in zip(tail,[0.7,0,1.5])) < 1e-5, tail
            target_move = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"set_transform","name":"ForgeMCPControlTarget",
                    "location":[-0.6,0,1.4]}]}})
            assert target_move["ok"], target_move
            move_id = target_move["data"]["preview_id"]
            moved_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":move_id,"confirmation":move_id})
            assert moved_apply["ok"] and moved_apply["data"]["state"] == "completed", moved_apply
            ik_moved = await call("blender_inspect_rig", {"session_id":session_id,
                "name":"ForgeMCPGeneratedRig","include_evaluated":True})
            assert ik_moved["ok"], ik_moved
            moved_tail = ik_moved["data"]["bones"][1]["evaluated_pose"]["tail_world"]
            assert sum((a-b)**2 for a,b in zip(moved_tail,[-0.6,0,1.4])) < 1e-5, moved_tail
            pole_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[{"op":"set_transform","name":"ForgeMCPPoleTarget",
                    "location":[0,-2,1]}]}})
            assert pole_preview["ok"], pole_preview
            pole_id = pole_preview["data"]["preview_id"]
            pole_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":pole_id,"confirmation":pole_id})
            assert pole_apply["ok"] and pole_apply["data"]["state"] == "completed", pole_apply
            pole_inspected = await call("blender_inspect_rig", {"session_id":session_id,
                "name":"ForgeMCPGeneratedRig","include_evaluated":True})
            assert pole_inspected["ok"], pole_inspected
            joint_before = ik_moved["data"]["bones"][0]["evaluated_pose"]["tail_world"]
            joint_after = pole_inspected["data"]["bones"][0]["evaluated_pose"]["tail_world"]
            assert sum((a-b)**2 for a,b in zip(joint_before,joint_after)) > 0.01
            pole_tail = pole_inspected["data"]["bones"][1]["evaluated_pose"]["tail_world"]
            assert sum((a-b)**2 for a,b in zip(pole_tail,[-0.6,0,1.4])) < 1e-5, pole_tail
            animated_preview = await call("blender_preview_scene", {"session_id":session_id,
                "recipe":{"operations":[
                    {"op":"keyframe","name":"ForgeMCPControlTarget","data_path":"location",
                     "frame":1,"value":[0.7,0,1.5]},
                    {"op":"keyframe","name":"ForgeMCPControlTarget","data_path":"location",
                     "frame":20,"value":[-0.6,0,1.4]}]}})
            assert animated_preview["ok"], animated_preview
            animated_id = animated_preview["data"]["preview_id"]
            animated_apply = await call("blender_apply_scene", {"session_id":session_id,
                "preview_id":animated_id,"confirmation":animated_id})
            assert animated_apply["ok"] and animated_apply["data"]["state"] == "completed", animated_apply
            animation_samples = []
            for frame in (1,10,20):
                frame_preview = await call("blender_preview_scene", {"session_id":session_id,
                    "recipe":{"operations":[{"op":"set_frame","frame":frame}]}})
                assert frame_preview["ok"], frame_preview
                frame_id = frame_preview["data"]["preview_id"]
                frame_apply = await call("blender_apply_scene", {"session_id":session_id,
                    "preview_id":frame_id,"confirmation":frame_id})
                assert frame_apply["ok"] and frame_apply["data"]["state"] == "completed", frame_apply
                assert frame_apply["data"]["operations"][0]["frame"] == frame
                frame_rig = await call("blender_inspect_rig", {"session_id":session_id,
                    "name":"ForgeMCPGeneratedRig","include_evaluated":True})
                frame_target = await call("blender_inspect_object", {"session_id":session_id,
                    "name":"ForgeMCPControlTarget"})
                assert frame_rig["ok"] and frame_target["ok"]
                frame_tail = frame_rig["data"]["bones"][1]["evaluated_pose"]["tail_world"]
                assert sum((a-b)**2 for a,b in zip(frame_tail,frame_target["data"]["location"])) < 1e-5
                animation_samples.append({"frame":frame,"rig":frame_rig["data"],"target":frame_target["data"]})
            assert animation_samples[0]["target"]["location"] != animation_samples[-1]["target"]["location"]
            report = {
                "animated_ik_apply":animated_apply,
                "animated_ik_samples":animation_samples,
                "ik_pole_move_apply":pole_apply,
                "ik_pole_move_inspected":pole_inspected,
                "ik_setup_apply":ik_apply,
                "ik_setup_inspected":ik_inspected,
                "ik_target_move_apply":moved_apply,
                "ik_target_move_inspected":ik_moved,
                "large_automatic_apply":large_apply,
                "large_partial_patch_apply":large_patch_apply,
                "large_partial_patch_inspection":large_after,
                "large_partial_patch_source_preserved":True,
                "partial_patch_preview":patch_preview,
                "partial_patch_apply":patch_apply,
                "partial_patch_inspection":patched_page,
                "partial_patch_original_preserved":True,
                "exact_skin_page":skin_page["data"],
                "structure": data,
                "weights": weighted["data"],
                "evaluated_pose": evaluated["data"],
                "invalid_mesh_query_rejected": True,
                "created_rig": generated["data"],
                "rig_apply": applied["data"],
                "preview_was_read_only": True,
                "session_id": session_id,
                "skin_binding_preview":skin_preview,
                "skin_binding_apply":skin_applied,
                "skin_binding_inspection":skin_inspected,
                "reweight_preview":reweight_preview,
                "reweight_apply":reweight_apply,
                "reweight_inspection":reweight_inspection,
                "automatic_preview":automatic_preview,
                "automatic_apply":automatic_apply,
                "automatic_inspection":automatic_inspection,
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
