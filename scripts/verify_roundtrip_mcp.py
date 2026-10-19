"""Native round-trip acceptance in disposable applications, through actual MCP stdio."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_transfer_workflow_mcp import PROBE, hidden, ready
from server.core.connections import ConnectionManager
from server.core.workflows import close_vector


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    if not project.is_relative_to(repository / "Saved") or not project.parent.parent.name.startswith("RoundtripValidation-"):
        raise ValueError("Use only the generated disposable roundtrip host")
    root = project.parent / "Saved" / ("RoundtripAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    sessions = root / "sessions"
    sessions.mkdir()
    stop = root / "stop"
    env = {**os.environ, "FORGE_PROJECT_ROOT": str(root),
        "FORGE_UNREAL_SESSION_DIR": str(project.parent / "Saved/MajesticForge"),
        "FORGE_BLENDER_SESSION_DIR": str(sessions), "FORGE_ADDON_ROOT": str(repository / "blender-addon"),
        "FORGE_FIXTURE_ROOT": str(root), "FORGE_FIXTURE_VARIANT": "default", "FORGE_STOP_FILE": str(stop),
        "BLENDER_USER_CONFIG": str(root / "config"), "BLENDER_USER_SCRIPTS": str(root / "scripts")}
    manager = ConnectionManager([project.parent / "Saved/MajesticForge", sessions])
    processes = []
    logs = []
    try:
        log = (root / "unreal-launch.log").open("w")
        logs.append(log)
        unreal = subprocess.Popen([str(args.editor), str(project), "/Engine/Maps/Templates/Template_Default",
            "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'unreal.log'}"], env=env, stdout=log, stderr=log, **hidden())
        processes.append(unreal)
        source = await ready(manager, unreal, "unreal")
        probe = root / "blender-probe.py"
        probe.write_text(PROBE)
        log = (root / "blender.log").open("w")
        logs.append(log)
        blender = subprocess.Popen([str(args.blender), "--background", "--factory-startup", "--python", str(probe)],
            env=env, stdout=log, stderr=log, **hidden())
        processes.append(blender)
        target = await ready(manager, blender, "blender")
        params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"], cwd=str(repository), env=env)
        report = {"interactive_verified": False, "live_sync": False}
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                    value = result.structuredContent or json.loads(result.content[0].text)
                    assert value["ok"], value
                    return value["data"]
                asset_root = "/Game/Roundtrip/R_" + uuid.uuid4().hex
                original = asset_root + "/SM_Original"
                request = {"source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "Cube", "target_asset_path": original, "save_assets": True, "place": False}
                preview = await call("forge_preview_transfer", {"request": request})
                original_binding = preview["source"]["binding_id"]
                report["initial_transfer"] = await call("forge_apply_transfer", {"preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
                original_path = original + ".SM_Original"
                native_binding = await manager.request(source, "mesh_export_preview", {"asset_path": original_path, "format": "fbx"})
                assert native_binding.get("binding_id") == original_binding, native_binding
                initial_compare = await call("forge_compare_mesh_binding", {"request": {
                    "source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "Cube", "target_asset_path": original_path}})
                assert initial_compare["state"] == "synchronized", initial_compare
                assert initial_compare["mutated"] is False and initial_compare["saved"] is False
                report["initial_binding_comparison"] = initial_compare
                before = await call("unreal_inspect_static_mesh", {"session_id": source.session_id, "asset_path": original_path})
                properties = await call("unreal_inspect_asset_properties", {
                    "session_id": source.session_id, "asset_path": original_path, "limit": 100})
                assert properties["loads_assets"] is True
                assert properties["supported_property_count"] > 0
                assert properties["properties"] and all(item["read_only"] for item in properties["properties"])
                report["unreal_asset_properties"] = properties
                lightmap = next(item for item in properties["properties"] if item["name"] == "LightMapResolution")
                assert lightmap["editable_in_editor"] and lightmap["value"] == "64", lightmap
                stale_edit = await call("unreal_preview_asset_property_edit", {
                    "session_id": source.session_id,
                    "request": {"asset_path": original_path, "property_name": "LightMapResolution", "property_value": "256"},
                })
                property_preview = await call("unreal_preview_asset_property_edit", {
                    "session_id": source.session_id,
                    "request": {"asset_path": original_path, "property_name": "LightMapResolution", "property_value": "128"},
                })
                assert property_preview["current_value"] == "64"
                assert property_preview["proposed_value"] == "128"
                assert property_preview["will_enable_transaction_tracking"] is True
                invalid_value = await client.call_tool("unreal_preview_asset_property_edit", {
                    "session_id": source.session_id,
                    "request": {"asset_path": original_path, "property_name": "LightMapResolution", "property_value": "not-an-integer"},
                })
                assert invalid_value.structuredContent["error"]["code"] == "invalid_property_value", invalid_value.structuredContent
                invalid_float = await client.call_tool("unreal_preview_asset_property_edit", {
                    "session_id": source.session_id,
                    "request": {"asset_path": original_path, "property_name": "DistanceFieldSelfShadowBias", "property_value": "nan"},
                })
                assert invalid_float.structuredContent["error"]["code"] == "invalid_property_value", invalid_float.structuredContent
                wrong_confirmation = await client.call_tool("unreal_apply_asset_property_edit", {
                    "session_id": source.session_id, "preview_id": property_preview["preview_id"],
                    "confirmation": "0" * 32,
                })
                assert wrong_confirmation.structuredContent["error"]["code"] == "confirmation_required", wrong_confirmation.structuredContent
                edited_property = await call("unreal_apply_asset_property_edit", {
                    "session_id": source.session_id, "preview_id": property_preview["preview_id"],
                    "confirmation": property_preview["preview_id"],
                })
                assert edited_property["applied_value"] == "128" and edited_property["package_dirty"] is True
                assert edited_property["undo_transaction_recorded"] is True
                assert edited_property["transactional_flag_added"] is True
                replay = await client.call_tool("unreal_apply_asset_property_edit", {
                    "session_id": source.session_id, "preview_id": property_preview["preview_id"],
                    "confirmation": property_preview["preview_id"],
                })
                assert replay.structuredContent["error"]["code"] == "preview_not_found", replay.structuredContent
                stale_apply = await client.call_tool("unreal_apply_asset_property_edit", {
                    "session_id": source.session_id, "preview_id": stale_edit["preview_id"],
                    "confirmation": stale_edit["preview_id"],
                })
                assert stale_apply.structuredContent["error"]["code"] == "stale_preview", stale_apply.structuredContent
                verify_edited_property = await call("unreal_inspect_asset_properties", {
                    "session_id": source.session_id, "asset_path": original_path, "limit": 100})
                edited_lightmap = next(item for item in verify_edited_property["properties"] if item["name"] == "LightMapResolution")
                assert edited_lightmap["value"] == "128", edited_lightmap
                dirty_edit = await client.call_tool("unreal_preview_asset_property_edit", {
                    "session_id": source.session_id,
                    "request": {"asset_path": original_path, "property_name": "LightMapResolution", "property_value": "256"},
                })
                assert dirty_edit.structuredContent["error"]["code"] == "asset_already_dirty", dirty_edit.structuredContent
                report["asset_property_edit"] = {"preview": property_preview,
                    "apply": edited_property, "verified_property": edited_lightmap,
                    "stale_preview_rejected": True, "invalid_value_rejected": True,
                    "non_finite_value_rejected": True,
                    "dirty_package_edit_rejected": True, "replay_rejected": True,
                    "package_saved": False}
                rejected_engine_asset = await client.call_tool("unreal_inspect_asset_properties", {
                    "session_id": source.session_id,
                    "asset_path": "/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial"})
                rejected_data = rejected_engine_asset.structuredContent
                assert rejected_data["error"]["code"] == "unsupported_asset_path", rejected_data
                reverse = {"source_session_id": source.session_id, "target_session_id": target.session_id,
                    "source_asset_path": original_path, "target_object": "RoundtripEditable",
                    "format": args.reverse_format}
                preview = await call("forge_preview_send_to_blender", {"request": reverse})
                assert preview.get("binding_id") == original_binding, preview
                report["send_preview"] = preview
                assert preview["format"] == ("obj" if args.reverse_format == "obj" else "fbx_binary"), preview
                report["send_to_blender"] = await call("forge_apply_send_to_blender", {"preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
                assert report["send_to_blender"]["state"] == "completed", report["send_to_blender"]
                send_receipt = await call("forge_inspect_transfer", {"operation_id": report["send_to_blender"]["operation_id"]})
                imports = [event.get("evidence", {}) for event in send_receipt["record"]["events"]
                           if event.get("stage") == "import" and event.get("outcome") == "completed"]
                assert len(imports) == 1 and imports[0].get("format") == args.reverse_format, send_receipt
                report["send_to_blender_receipt"] = send_receipt
                request.update(source_object="RoundtripEditable", target_asset_path=asset_root + "/SM_Returned")
                preview = await call("forge_preview_transfer", {"request": request})
                report["return_to_unreal"] = await call("forge_apply_transfer", {"preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
                returned_path = asset_root + "/SM_Returned.SM_Returned"
                returned_binding = await manager.request(source, "mesh_export_preview", {"asset_path": returned_path, "format": "fbx"})
                assert returned_binding.get("binding_id") == original_binding, returned_binding
                report["stable_binding_verified"] = original_binding
                after = await call("unreal_inspect_static_mesh", {"session_id": source.session_id, "asset_path": asset_root + "/SM_Returned.SM_Returned"})
                returned_compare = await call("forge_compare_mesh_binding", {"request": {
                    "source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "RoundtripEditable", "target_asset_path": returned_path}})
                assert returned_compare["state"] == "synchronized", returned_compare
                report["returned_binding_comparison"] = returned_compare
                assert before["triangle_count"] == after["triangle_count"], (before, after)
                assert before["vertex_count"] == after["vertex_count"], (before, after)
                assert close_vector(before["bounds_min_cm"], after["bounds_min_cm"]), (before, after)
                assert close_vector(before["bounds_max_cm"], after["bounds_max_cm"]), (before, after)
                assert all(close_vector(a,b) for a,b in zip(sorted(before["vertex_positions_cm"]),sorted(after["vertex_positions_cm"]))), (before, after)
                report["roundtrip_geometry_verified"] = True
                report["reverse_format"] = args.reverse_format
                report["material_equivalence_verified"] = False
                report["original_mesh"] = before
                report["returned_mesh"] = after
                # Work on the received object through the existing typed Blender tools.
                edit = await call("blender_preview_scene", {"session_id": target.session_id,
                    "recipe": {"operations": [{"op": "set_transform", "name": "RoundtripEditable", "location": [1.0, 2.0, 3.0]}]}})
                report["blender_edit"] = await call("blender_apply_scene", {"session_id": target.session_id,
                    "preview_id": edit["preview_id"], "confirmation": edit["preview_id"]})
                changed_compare = await call("forge_compare_mesh_binding", {"request": {
                    "source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "RoundtripEditable", "target_asset_path": returned_path}})
                assert changed_compare["state"] == "blender_changed", changed_compare
                report["blender_change_detected"] = changed_compare
                replacement_before = await call("unreal_inspect_static_mesh", {
                    "session_id": source.session_id, "asset_path": returned_path})
                replacement_preview = await call("forge_preview_transfer", {"request": {
                    "source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "RoundtripEditable",
                    "target_asset_path": returned_path.rsplit(".", 1)[0],
                    "save_assets": True, "place": False, "replace_existing": True}})
                assert replacement_preview["overwrite"] is True
                assert replacement_preview["replacement"]["backup_required"] is True
                assert replacement_preview["replacement"]["preserves_material_assignments"] is True
                assert replacement_preview["changes"]["replace_existing"] is True
                replacement_result = await call("forge_apply_transfer", {
                    "preview_id": replacement_preview["preview_id"],
                    "confirmation": replacement_preview["preview_id"]})
                assert replacement_result["state"] == "completed", replacement_result
                replacement_after = await call("unreal_inspect_static_mesh", {
                    "session_id": source.session_id, "asset_path": returned_path})
                assert replacement_after["vertex_count"] == replacement_before["vertex_count"]
                assert replacement_after["triangle_count"] == replacement_before["triangle_count"]
                assert replacement_after["materials"] == replacement_before["materials"]
                backup_dir = Path(replacement_result["receipt"]["events"][-3]["evidence"]["backup_directory"])
                assert backup_dir.is_relative_to(project.parent / "Saved" / "ForgeMCP" / "Backups" / "MeshReplacement")
                backup_evidence = replacement_result["receipt"]["events"][-3]["evidence"]["verified_backup_parts"]
                for part in backup_evidence:
                    backup_file = backup_dir / part["file"]
                    assert backup_file.is_file() and backup_file.stat().st_size == part["bytes"]
                    assert hashlib.sha256(backup_file.read_bytes()).hexdigest() == part["sha256"]
                replacement_compare = await call("forge_compare_mesh_binding", {"request": {
                    "source_session_id": target.session_id, "target_session_id": source.session_id,
                    "source_object": "RoundtripEditable", "target_asset_path": returned_path}})
                assert replacement_compare["state"] == "synchronized", replacement_compare
                report["reviewed_replacement"] = {"result": replacement_result,
                    "material_assignments_preserved": replacement_after["materials"] == replacement_before["materials"],
                    "backup_files_verified": len(backup_evidence),
                    "post_replacement_binding_comparison": replacement_compare}
                # Exercise the same external worker protocol used by Unreal's Pull button.
                worker = await asyncio.create_subprocess_exec(sys.executable, "-m", "server.ui_transfer",
                    cwd=repository, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, **hidden())
                intent = {"mode": "import_from_blender", "unreal_project_file": str(project),
                    "source_session_id": "", "source_object": "", "target_session_id": source.session_id,
                    "target_asset_path": asset_root + "/SM_EditedPull", "save_assets": True, "place": False}
                worker.stdin.write(json.dumps(intent).encode()+b"\n")
                await worker.stdin.drain()
                try:
                    plan = json.loads(await asyncio.wait_for(worker.stdout.readline(), timeout=90))
                    assert plan["state"] == "preview", plan
                    assert plan["preview"]["changes"]["source_object"] == "RoundtripEditable", plan
                    worker.stdin.write(json.dumps({"confirmation": plan["preview"]["preview_id"]}).encode()+b"\n")
                    await worker.stdin.drain()
                    assert json.loads(await asyncio.wait_for(worker.stdout.readline(), timeout=90))["state"] == "applying"
                    result = json.loads(await asyncio.wait_for(worker.stdout.readline(), timeout=120))
                    assert result["state"] == "completed", result
                    report["import_from_blender_worker"] = result
                    worker.stdin.close()
                    await asyncio.wait_for(worker.wait(), timeout=10)
                finally:
                    if worker.returncode is None:
                        worker.terminate()
                        await worker.wait()
                edited = await call("unreal_inspect_static_mesh", {"session_id": source.session_id, "asset_path": asset_root + "/SM_EditedPull.SM_EditedPull"})
                delta = [-200.0, -100.0, 300.0]
                assert close_vector(edited["bounds_min_cm"], [v+d for v,d in zip(before["bounds_min_cm"],delta)]), edited
                assert close_vector(edited["bounds_max_cm"], [v+d for v,d in zip(before["bounds_max_cm"],delta)]), edited
                report["edited_pull_geometry_verified"] = True
                report["edited_mesh"] = edited
                # Reopen the disposable Editor to prove the binding survives the
                # package save/reload boundary, rather than existing only in memory.
                unreal.terminate()
                await asyncio.to_thread(unreal.wait, 30)
                reload_log = (root / "unreal-reload.log").open("w")
                logs.append(reload_log)
                unreal = subprocess.Popen([str(args.editor), str(project), "/Engine/Maps/Templates/Template_Default",
                    "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
                    f"-abslog={root / 'unreal-reload.log'}"], env=env, stdout=reload_log, stderr=reload_log, **hidden())
                processes.append(unreal)
                source = await ready(manager, unreal, "unreal")
                await call("unreal_inspect_asset_properties", {
                    "session_id": source.session_id, "asset_path": returned_path, "limit": 1})
                await call("unreal_inspect_static_mesh", {"session_id": source.session_id, "asset_path": returned_path})
                reloaded_binding = await manager.request(source, "mesh_export_preview", {
                    "asset_path": returned_path, "format": "fbx"})
                assert reloaded_binding.get("binding_id") == original_binding, reloaded_binding
                expected_source_snapshot = replacement_result["receipt"]["plan"]["replacement"]["source_snapshot_sha256"]
                replacement_import = next(event["evidence"] for event in replacement_result["receipt"]["events"]
                    if event.get("stage") == "import" and event.get("outcome") == "completed")
                assert reloaded_binding.get("source_revision_sha256") == expected_source_snapshot, reloaded_binding
                assert reloaded_binding.get("target_revision_sha256") == replacement_import.get("target_revision_sha256"), reloaded_binding
                assert reloaded_binding.get("source_snapshot_sha256") == reloaded_binding.get("target_revision_sha256"), reloaded_binding
                report["binding_survives_editor_restart"] = True
                report["revision_fingerprint_survives_editor_restart"] = True
        (root / "acceptance.json").write_text(json.dumps(report, indent=2))
        print("FORGEMCP_NATIVE_MCP_ROUNDTRIP_PASS", root)
    finally:
        stop.touch()
        for process in processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--editor", type=Path, default=Path(r"G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe"))
    parser.add_argument("--blender", type=Path, default=Path(r"E:\SteamLibrary\steamapps\common\Blender\blender.exe"))
    parser.add_argument("--reverse-format", choices=("fbx", "obj"), default="fbx",
                        help="Format for the Unreal-to-Blender leg; the return leg remains Blender FBX.")
    asyncio.run(verify(parser.parse_args()))
