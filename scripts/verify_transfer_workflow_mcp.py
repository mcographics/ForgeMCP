"""Exercise the transfer coordinator through MCP in disposable native applications.

Retains evidence and closes only the processes it starts. This is headless native
acceptance, not interactive or rendered-material acceptance.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.core.connections import BridgeError, ConnectionManager

PROBE = '''
import json, os, sys, time
from pathlib import Path
import bpy
sys.path.insert(0, os.environ["FORGE_ADDON_ROOT"])
import majestic_forge
cube = bpy.data.objects["Cube"]
for vertex in cube.data.vertices:
    vertex.co.x *= 2
    vertex.co.y *= 3
cube.data.vertices[0].co.x += 0.35
cube.data.vertices[0].co.z += 0.2
if os.environ["FORGE_FIXTURE_VARIANT"] == "transformed_metric":
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.01
    cube.location = (7.0, -11.0, 5.0)
    cube.rotation_euler = (0.23, -0.41, 0.67)
    cube.scale = (1.7, 0.6, 2.3)
bpy.context.view_layer.update()
Path(os.environ["FORGE_FIXTURE_ROOT"]).joinpath("source-vertices.json").write_text(
    json.dumps([list(vertex.co) for vertex in cube.data.vertices]))
majestic_forge.register()
try:
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline and not Path(os.environ["FORGE_STOP_FILE"]).exists():
        majestic_forge._bridge.tick()
        time.sleep(0.01)
finally:
    majestic_forge.unregister()
'''


def hidden():
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startup}


async def ready(manager, process, kind):
    deadline = time.monotonic() + 180
    while process.poll() is None and time.monotonic() < deadline:
        for candidate in manager.discover():
            if candidate.pid == process.pid and candidate.kind == kind:
                try:
                    health = await manager.request(candidate, "health")
                    if health.get("transfer_contract_version") != 1:
                        raise RuntimeError("Disposable adapter requires a current build")
                    return candidate
                except BridgeError:
                    pass
        await asyncio.sleep(0.2)
    raise RuntimeError(f"Disposable {kind} did not become ready")


def audit_saved_evidence(report, project, sessions):
    """Check persisted stage evidence and artifact bytes, not current native state."""
    record = report["apply"]["data"]["receipt"]
    stages = ["export", "staging", "import", "verification", "placement"]
    assert record["state"] == "completed" and record["active_stage"] is None
    assert record["completed_stages"] == stages and record["revision"] == 10
    assert [(e["stage"], e["outcome"]) for e in record["events"]] == [
        (stage, outcome) for stage in stages for outcome in ("started", "completed")]
    evidence = {e["stage"]: e["evidence"] for e in record["events"] if e["outcome"] == "completed"}
    checks = evidence["verification"]
    assert checks["complete_vertex_positions_verified"] is True
    assert checks["geometry_bounds_and_counts_verified"] is True
    assert checks["material_constant_graphs_verified"] is True
    assert checks["shader_compile_verified"] is False and checks["visual_equivalence_verified"] is False
    imported = evidence["import"]
    assert imported["saved"] is True and imported["materials"]
    assert all(m["saved"] is True for m in imported["materials"])
    saved = []
    for asset in imported["saved_assets"]:
        package = asset.split(".", 1)[0]
        assert package.startswith("/Game/ForgeWorkflow/")
        path = project.parent / "Content" / (package.removeprefix("/Game/") + ".uasset")
        assert path.is_file() and path.stat().st_size > 0, path
        saved.append({"asset_path": asset, "bytes": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    exported = evidence["export"]
    artifact = sessions / "transfers" / exported["source_session_id"] / exported["transfer_id"] / "mesh.fbx"
    assert artifact.stat().st_size == exported["artifact_bytes"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == exported["artifact_sha256"]
    disk_record = json.loads((project.parent / "Saved" / "ForgeWorkflows" /
                             record["operation_id"] / "record.json").read_text())
    assert disk_record == record
    assert report["inspection"]["data"]["record"] == record
    assert report["inspection"]["data"]["runtime_state_verified"] is False
    return {"saved_asset_files": saved, "source_export_checksum_verified": True,
            "durable_receipt_matches_reply": True, "native_runtime_rechecked": False}


async def inspect_after_restart(repository, project, root, report):
    parameters = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
        cwd=str(repository), env={**os.environ, "FORGE_PROJECT_ROOT": str(project.parent),
                                 "FORGE_BLENDER_SESSION_DIR": str(root / "sessions")})
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            result = await client.call_tool("forge_inspect_transfer", {
                "operation_id": report["apply"]["data"]["operation_id"]})
            assert not result.isError and result.structuredContent["ok"], result
            data = result.structuredContent["data"]
            assert data["record"] == report["apply"]["data"]["receipt"]
            assert data["runtime_state_verified"] is False
            assert data["automatic_native_replay_allowed"] is False
            recovered = report.get("native_retained_export_recovery")
            if recovered and recovered.get("restored_from_failed_recovery"):
                chain = [report["native_save_failure_acceptance"]["apply"],
                         report["native_recovery_save_failure"]["apply"], recovered["apply"]]
                inspected = []
                for applied in chain:
                    expected = applied["data"]["receipt"]
                    reply = await client.call_tool("forge_inspect_transfer", {
                        "operation_id": expected["operation_id"]})
                    assert not reply.isError and reply.structuredContent["ok"], reply
                    observed = reply.structuredContent["data"]
                    assert observed["record"] == expected
                    assert observed["runtime_state_verified"] is False
                    assert observed["automatic_native_replay_allowed"] is False
                    exports = [e["evidence"] for e in expected["events"]
                               if e["stage"] == "export" and e["outcome"] == "completed"]
                    retained = exports[-1] if exports else expected["plan"]["retained_export"]
                    artifact = project.parent / "Saved" / "ForgeTransfers" / retained["transfer_id"] / "mesh.fbx"
                    assert artifact.stat().st_size == retained["artifact_bytes"]
                    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == retained["artifact_sha256"]
                    inspected.append(expected["operation_id"])
                assert chain[1]["data"]["receipt"]["plan"]["original_operation_id"] == inspected[0]
                assert chain[2]["data"]["receipt"]["plan"]["original_operation_id"] == inspected[1]
                data["recovery_chain_audit"] = {"operation_ids": inspected,
                    "receipts_unchanged": True, "retained_checksums_verified": True,
                    "native_runtime_rechecked": False}
            level_save = report.get("native_mcp_level_save")
            if level_save and "receipt" in level_save["apply"]["data"]:
                expected = level_save["apply"]["data"]["receipt"]
                reply = await client.call_tool("forge_inspect_transfer", {"operation_id": expected["operation_id"]})
                assert not reply.isError and reply.structuredContent["ok"], reply
                observed = reply.structuredContent["data"]
                assert observed["record"] == expected
                assert observed["runtime_state_verified"] is False
                assert observed["automatic_native_replay_allowed"] is False
                assert expected["completed_stages"] == ["level_save"]
                data["level_save_receipt_audit"] = observed
            failure_ids = []
            for failure in report.get("native_level_save_failures", []):
                expected = failure["inspection"]["data"]["record"]
                reply = await client.call_tool("forge_inspect_transfer", {"operation_id": expected["operation_id"]})
                assert not reply.isError and reply.structuredContent["ok"], reply
                observed = reply.structuredContent["data"]
                assert observed["record"] == expected and observed["effective_state"] == "failed"
                assert observed["runtime_state_verified"] is False
                assert observed["automatic_native_replay_allowed"] is False
                failure_ids.append(expected["operation_id"])
            if failure_ids:
                data["failed_level_receipt_audit"] = {"operation_ids": failure_ids, "receipts_unchanged": True}
            return data


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if (not relative.parts[0].startswith("TransferImportValidation-")
            or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject")):
        raise ValueError("Only a generated disposable transfer host is allowed")
    if args.audit_existing:
        root = args.audit_existing.resolve(strict=True)
        if root.parent != project.parent / "Saved" or not root.name.startswith("WorkflowAcceptance-"):
            raise ValueError("Audit must target this disposable host's acceptance directory")
        report = json.loads((root / "acceptance.json").read_text())
        audit = audit_saved_evidence(report, project, root / "sessions")
        audit["fresh_mcp_inspection"] = await inspect_after_restart(repository, project, root, report)
        (root / "persistence-audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print("FORGEMCP_PERSISTENCE_AND_FRESH_MCP_INSPECTION_PASS", flush=True)
        return
    root = project.parent / "Saved" / ("WorkflowAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    sessions = root / "sessions"
    sessions.mkdir()
    stop = root / "stop"
    probe = root / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    env = {**os.environ, "FORGE_PROJECT_ROOT": str(project.parent),
           "FORGE_BLENDER_SESSION_DIR": str(sessions),
           "FORGE_ADDON_ROOT": str(repository / "blender-addon"),
           "FORGE_STOP_FILE": str(stop),
           "FORGE_FIXTURE_VARIANT": args.variant,
           "FORGE_FIXTURE_ROOT": str(root),
           "BLENDER_USER_CONFIG": str(root / "blender-config"),
           "BLENDER_USER_SCRIPTS": str(root / "blender-scripts")}
    manager = ConnectionManager([sessions, project.parent / "Saved" / "MajesticForge"], timeout=30)
    processes = []
    logs = []
    print(f"Evidence: {root}", flush=True)
    try:
        for name, command, cwd in (
            ("blender", [str(args.blender.resolve(strict=True)), "--background", "--factory-startup",
                         "--python-exit-code", "1", "--python", str(probe)], root),
            ("unreal", [str(args.editor.resolve(strict=True)), str(project), "/Engine/Maps/Templates/Template_Default", "-Unattended", "-NullRHI",
                        "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
                        f"-abslog={root / 'unreal.log'}"], project.parent),
        ):
            log = (root / (name + "-launch.log")).open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, **hidden()))
        source = await ready(manager, processes[0], "blender")
        target = await ready(manager, processes[1], "unreal")
        info = await manager.request(target, "project_info")
        assert Path(info["project_file"]).resolve() == project
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                           cwd=str(repository), env=env)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()

                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                    return result.structuredContent

                vertices = json.loads((root / "source-vertices.json").read_text())
                for point in vertices:
                    point[0] *= 1.1
                    point[1] *= 0.9
                vertices[-1][2] += 0.17
                geometry_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [
                        {"op": "set_vertices", "name": "Cube", "vertices": vertices},
                        {"op": "set_material_input", "name": "Material", "node": "Principled BSDF",
                         "socket": "Base Color", "value": [0.12, 0.34, 0.56, 1.0]},
                        {"op": "set_material_input", "name": "Material", "node": "Principled BSDF",
                         "socket": "Roughness", "value": 0.27},
                        {"op": "set_material_input", "name": "Material", "node": "Principled BSDF",
                         "socket": "Metallic", "value": 0.63}]}})
                assert geometry_preview["ok"], geometry_preview
                geometry_id = geometry_preview["data"]["preview_id"]
                geometry_edit = await call("blender_apply_scene", {"session_id": source.session_id,
                    "preview_id": geometry_id, "confirmation": geometry_id})
                assert geometry_edit["ok"] and geometry_edit["data"]["state"] == "completed", geometry_edit
                assert geometry_edit["data"]["preserved_datablocks"], geometry_edit
                before = await manager.request(source, "scene_info")

                request = {"source_session_id": source.session_id, "target_session_id": target.session_id,
                           "source_object": "Cube", "target_asset_path": "/Game/ForgeWorkflow/SM_" + uuid.uuid4().hex,
                           "save_assets": True, "place": True, "location": [150.0, 250.0, 350.0],
                           "rotation": [0.0, 90.0, 0.0], "scale": [1.5, 0.5, 2.0]}
                preview = await call("forge_preview_transfer", {"request": request})
                assert preview["ok"], preview
                plan = preview["data"]
                operation = plan["preview_id"]
                assert not (project.parent / "Saved" / "ForgeWorkflows" / operation).exists()
                arguments = {"preview_id": operation, "confirmation": operation}
                applied = await call("forge_apply_transfer", arguments)
                (root / "apply.json").write_text(json.dumps(applied, indent=2), encoding="utf-8")
                assert applied["ok"] and applied["data"]["state"] == "completed", applied
                inspected = await call("forge_inspect_transfer", {"operation_id": operation})
                assert inspected["ok"], inspected
                replay = await call("forge_apply_transfer", arguments)
                assert replay["error"]["code"] == "preview_not_found", replay
                after = await manager.request(source, "scene_info")
                assert before == after, "Transfer changed source scene facts"
                report = {"interactive_verified": False, "rendered_materials_verified": False,
                          "fixture_variant": args.variant,
                          "source_geometry_modified_through_mcp": True,
                          "source_material_modified_through_mcp": True,
                          "source_edit": geometry_edit,
                          "level_saved": False, "source_scene_preserved": True,
                          "replay_rejected": True, "preview": preview, "apply": applied,
                          "inspection": inspected}
                report["persistence_audit"] = audit_saved_evidence(report, project, sessions)
                actors_before = await manager.request(target, "list_actors", {"limit": 200})
                saved_before = report["persistence_audit"]["saved_asset_files"]
                existing = await call("forge_preview_transfer", {"request": request})
                assert not existing["ok"] and existing["error"]["code"] == "destination_exists", existing
                assert audit_saved_evidence(report, project, sessions)["saved_asset_files"] == saved_before
                assert await manager.request(target, "list_actors", {"limit": 200}) == actors_before
                stale_request = {**request, "target_asset_path": "/Game/ForgeWorkflow/SM_" + uuid.uuid4().hex}
                stale_preview = await call("forge_preview_transfer", {"request": stale_request})
                assert stale_preview["ok"], stale_preview
                stale_plan = stale_preview["data"]
                edit_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id,
                    "recipe": {"operations": [{"op": "set_transform", "name": "Cube",
                                                "location": [19.0, -13.0, 23.0]}]}})
                assert edit_preview["ok"], edit_preview
                edit_id = edit_preview["data"]["preview_id"]
                edited = await call("blender_apply_scene", {"session_id": source.session_id,
                    "preview_id": edit_id, "confirmation": edit_id})
                assert edited["ok"], edited
                failed = await call("forge_apply_transfer", {
                    "preview_id": stale_plan["preview_id"], "confirmation": stale_plan["preview_id"]})
                assert not failed["ok"] and failed["data"]["state"] == "failed", failed
                assert failed["data"]["diagnostic_code"] == "stale_preview", failed
                failed_receipt = await call("forge_inspect_transfer", {
                    "operation_id": stale_plan["operation_id"]})
                assert failed_receipt["ok"], failed_receipt
                assert failed_receipt["data"]["record"]["state"] == "failed"
                assert failed_receipt["data"]["record"]["completed_stages"] == []
                assert not (project.parent / "Saved" / "ForgeTransfers" /
                            stale_plan["source"]["transfer_id"]).exists()
                assert await manager.request(target, "list_actors", {"limit": 200}) == actors_before
                assert audit_saved_evidence(report, project, sessions)["saved_asset_files"] == saved_before
                report["native_failure_acceptance"] = {
                    "existing_destination_rejected": True, "existing_packages_unchanged": True,
                    "stale_source_rejected_before_staging": True, "target_actors_unchanged": True,
                    "source_edit": edited, "failed_apply": failed, "failed_receipt": failed_receipt}
                (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                blocked_name = "ForgeSaveFailure_" + uuid.uuid4().hex
                blocker = project.parent / "Content" / blocked_name
                # An exclusive file at the would-be directory prevents package saves
                # without changing ACLs or touching existing destinations.
                with blocker.open("x", encoding="utf-8") as handle:
                    handle.write("Disposable native save-failure fixture")
                try:
                    save_request = {**request, "target_asset_path": f"/Game/{blocked_name}/SM_SaveFailure"}
                    save_preview = await call("forge_preview_transfer", {"request": save_request})
                    assert save_preview["ok"], save_preview
                    save_id = save_preview["data"]["preview_id"]
                    save_result = await call("forge_apply_transfer", {
                        "preview_id": save_id, "confirmation": save_id})
                    (root / "save-failure-apply.json").write_text(json.dumps(save_result, indent=2))
                    assert not save_result["ok"] and save_result["data"]["state"] == "partial", save_result
                    save_record = save_result["data"]["receipt"]
                    assert save_record["completed_stages"] == ["export", "staging"]
                    assert save_record["events"][-1]["stage"] == "import"
                    assert save_record["events"][-1]["outcome"] == "partial"
                    native = save_record["events"][-1]["evidence"]
                    assert native["saved"] is False and native["saved_assets"] == []
                    assert native["materials"] and all(m["saved"] is False for m in native["materials"])
                    current = await call("unreal_inspect_static_mesh", {
                        "session_id": target.session_id, "asset_path": native["asset_path"]})
                    assert current["ok"], current
                    assert current["data"]["runtime_state_verified"] is True
                    assert current["data"]["package_dirty"] is True
                    assert current["data"]["disk_package_present"] is False
                    assert current["data"]["vertex_count"] == 8
                    assert current["data"]["triangle_count"] == 12
                    assert all(m["disk_package_present"] is False for m in current["data"]["materials"])
                    reconciled = await call("forge_reconcile_transfer", {
                        "operation_id": save_id, "target_session_id": target.session_id})
                    assert reconciled["ok"], reconciled
                    assert reconciled["data"]["recorded_state"] == "partial"
                    assert reconciled["data"]["geometry_and_materials_verified"] is True
                    assert reconciled["data"]["receipt_modified"] is False
                    assert reconciled["data"]["recovery_completed"] is False
                    assert await manager.request(target, "list_actors", {"limit": 200}) == actors_before
                    assert audit_saved_evidence(report, project, sessions)["saved_asset_files"] == saved_before
                    report["native_save_failure_acceptance"] = {
                        "partial_import_retained": True, "placement_not_attempted": True,
                        "existing_packages_unchanged": True, "apply": save_result,
                        "native_current_state": current,
                        "reconciliation": reconciled,
                        "recovery_completed": False}
                    (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                finally:
                    blocker.unlink()
                stop.write_text("stop", encoding="utf-8")
                await asyncio.to_thread(processes[0].wait, timeout=10)
                assert processes[0].returncode == 0
                original_receipt = await call("forge_inspect_transfer", {"operation_id": save_id})
                recovery_blocker = project.parent / "Content" / ("ForgeRecoveryFailure_" + uuid.uuid4().hex)
                with recovery_blocker.open("x", encoding="utf-8") as handle:
                    handle.write("Disposable recovery save-failure fixture")
                try:
                    failed_preview = await call("forge_preview_asset_recovery", {
                        "operation_id": save_id, "target_session_id": target.session_id,
                        "new_asset_path": f"/Game/{recovery_blocker.name}/SM_FailedRecovery"})
                    assert failed_preview["ok"], failed_preview
                    failed_recovery_id = failed_preview["data"]["preview_id"]
                    failed_recovery = await call("forge_apply_asset_recovery", {
                        "preview_id": failed_recovery_id, "confirmation": failed_recovery_id})
                    assert not failed_recovery["ok"] and failed_recovery["data"]["state"] == "partial", failed_recovery
                    failed_record = failed_recovery["data"]["receipt"]
                    assert failed_record["completed_stages"] == ["staging"]
                    assert failed_record["events"][-1]["evidence"]["saved_assets"] == []
                    failed_receipt = await call("forge_inspect_transfer", {"operation_id": failed_recovery_id})
                    report["native_recovery_save_failure"] = {
                        "preview": failed_preview, "apply": failed_recovery,
                        "blender_closed": True, "saved_assets": []}
                    (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                finally:
                    recovery_blocker.unlink()
                restore_preview = await call("forge_preview_asset_recovery", {
                    "operation_id": failed_recovery_id, "target_session_id": target.session_id,
                    "new_asset_path": "/Game/ForgeRecovery/SM_" + uuid.uuid4().hex})
                assert restore_preview["ok"], restore_preview
                restore_id = restore_preview["data"]["preview_id"]
                restore_args = {"preview_id": restore_id, "confirmation": restore_id}
                restored = await call("forge_apply_asset_recovery", restore_args)
                assert restored["ok"] and restored["data"]["state"] == "completed", restored
                assert restored["data"]["receipt"]["completed_stages"] == ["staging", "import", "verification"]
                recovered_state = await call("forge_reconcile_transfer", {
                    "operation_id": restore_id, "target_session_id": target.session_id})
                assert recovered_state["ok"] and recovered_state["data"]["geometry_and_materials_verified"]
                assert (await call("forge_inspect_transfer", {"operation_id": save_id})) == original_receipt
                assert (await call("forge_inspect_transfer", {"operation_id": failed_recovery_id})) == failed_receipt
                assert (await call("forge_apply_asset_recovery", restore_args))["error"]["code"] == "preview_not_found"
                assert await manager.request(target, "list_actors", {"limit": 200}) == actors_before
                assert audit_saved_evidence(report, project, sessions)["saved_asset_files"] == saved_before
                report["native_retained_export_recovery"] = {
                    "blender_closed_before_recovery": True, "original_receipt_unchanged": True,
                    "failed_recovery_receipt_unchanged": True, "restored_from_failed_recovery": True,
                    "new_assets_restored": True, "actor_placement_performed": False,
                    "preview": restore_preview, "apply": restored, "reconciliation": recovered_state}
                map_path = "/Game/ForgeSavedLevel_" + uuid.uuid4().hex + "/TransferLevel"
                stale_map_path = "/Game/ForgeStaleLevel_" + uuid.uuid4().hex + "/TransferLevel"
                stale_level = await call("unreal_preview_level_save", {
                    "asset_path": stale_map_path, "session_id": target.session_id})
                assert stale_level["ok"], stale_level
                placed = next(e["evidence"] for e in applied["data"]["receipt"]["events"]
                              if e["stage"] == "placement" and e["outcome"] == "completed")["native_result"]["actors"][0]
                actor_before_failures = await manager.request(target, "actor_info", {"actor_path": placed["path"]})
                level_failures = []
                for failure_kind in ("destination_changed", "native_intent_unavailable"):
                    failure_folder = "ForgeLevelFailure_" + uuid.uuid4().hex
                    failure_path = f"/Game/{failure_folder}/TransferLevel"
                    failure_preview = await call("unreal_preview_level_save", {
                        "asset_path": failure_path, "session_id": target.session_id})
                    assert failure_preview["ok"], failure_preview
                    failure_id = failure_preview["data"]["preview_id"]
                    if failure_kind == "destination_changed":
                        blocker = project.parent / "Content" / failure_folder
                        expected_error = "destination_unavailable"
                    else:
                        blocker = project.parent / "Saved" / "ForgeLevelSaves" / failure_id.upper()
                        expected_error = "report_failed"
                    blocker.parent.mkdir(parents=True, exist_ok=True)
                    with blocker.open("x", encoding="utf-8") as handle:
                        handle.write("Disposable level-save failure fixture")
                    try:
                        failure_args = {"preview_id": failure_id, "confirmation": failure_id,
                                        "session_id": target.session_id}
                        failure_result = await call("unreal_apply_level_save", failure_args)
                        assert not failure_result["ok"] and failure_result["error"]["code"] == expected_error, failure_result
                        failure_receipt = await call("forge_inspect_transfer", {"operation_id": failure_id})
                        assert failure_receipt["ok"] and failure_receipt["data"]["record"]["state"] == "failed"
                        assert failure_receipt["data"]["record"]["completed_stages"] == []
                        assert not (project.parent / "Content" / failure_folder / "TransferLevel.umap").exists()
                        assert (await call("unreal_apply_level_save", failure_args))["error"]["code"] == "preview_not_found"
                        assert await manager.request(target, "actor_info", {"actor_path": placed["path"]}) == actor_before_failures
                        assert audit_saved_evidence(report, project, sessions)["saved_asset_files"] == saved_before
                        level_failures.append({"kind": failure_kind, "apply": failure_result,
                            "inspection": failure_receipt, "map_saved": False,
                            "empty_reserved_folder_retained": failure_kind == "native_intent_unavailable",
                            "placed_actor_unchanged": True, "existing_packages_unchanged": True})
                    finally:
                        blocker.unlink()
                report["native_level_save_failures"] = level_failures
                (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                for changed_location in ([151, 250, 350], placed["location"]):
                    edit = await call("unreal_preview_actors", {"session_id": target.session_id,
                        "recipe": {"operations": [{"op": "transform", "actor_path": placed["path"],
                                                   "location": changed_location}]}})
                    assert edit["ok"], edit
                    edit_id = edit["data"]["preview_id"]
                    result = await call("unreal_apply_actors", {"session_id": target.session_id,
                        "preview_id": edit_id, "confirmation": edit_id})
                    assert result["ok"] and result["data"]["state"] == "completed", result
                    if changed_location != placed["location"]:
                        stale_id = stale_level["data"]["preview_id"]
                        rejected = await call("unreal_apply_level_save", {"session_id": target.session_id,
                            "preview_id": stale_id, "confirmation": stale_id})
                        assert rejected["error"]["code"] == "stale_preview", rejected
                        assert not (project.parent / "Content" / stale_map_path.removeprefix("/Game/")).parent.exists()
                level_preview = await call("unreal_preview_level_save", {
                    "asset_path": map_path, "session_id": target.session_id})
                assert level_preview["ok"], level_preview
                level_id = level_preview["data"]["preview_id"]
                level_args = {"preview_id": level_id, "confirmation": level_id, "session_id": target.session_id}
                level_saved = await call("unreal_apply_level_save", level_args)
                assert level_saved["ok"] and level_saved["data"]["state"] == "saved", level_saved
                saved_receipt = level_saved["data"]["receipt"]
                assert saved_receipt["completed_stages"] == ["level_save"]
                assert [(e["stage"], e["outcome"]) for e in saved_receipt["events"]] == [
                    ("level_save", "started"), ("level_save", "completed")]
                current_receipt = await call("forge_inspect_transfer", {"operation_id": level_id})
                assert current_receipt["ok"] and current_receipt["data"]["record"] == saved_receipt
                level_reconciliation = await call("unreal_reconcile_level_save", {
                    "operation_id": level_id, "session_id": target.session_id})
                assert level_reconciliation["ok"], level_reconciliation
                level_observed = level_reconciliation["data"]
                # SaveMap can save a copy of an already loaded map without
                # switching the editor world to that destination.
                assert level_observed["current_world"] == level_saved["data"]["world"]
                assert level_observed["matching_world_loaded"] is False
                assert level_observed["matches_recorded_saved_checksum"] is True
                assert level_observed["native_map_contents_verified"] is False
                assert level_observed["receipt_modified"] is False
                assert (await call("forge_inspect_transfer", {"operation_id": level_id}))["data"]["record"] == saved_receipt
                assert (await call("unreal_apply_level_save", level_args))["error"]["code"] == "preview_not_found"
                assert not (await call("unreal_preview_level_save", {
                    "asset_path": map_path, "session_id": target.session_id}))["ok"]
                report["native_mcp_level_save"] = {"preview": level_preview, "apply": level_saved,
                    "reconciliation": level_reconciliation,
                    "stale_actor_change_rejected": True,
                    "replay_rejected": True, "existing_destination_rejected": True,
                    "reopened_verified": False}
                (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("FORGEMCP_NATIVE_COORDINATOR_STDIO_ACCEPTANCE_PASS", flush=True)
    finally:
        stop.write_text("stop", encoding="utf-8")
        for process in processes:
            if process.poll() is None:
                try:
                    await asyncio.to_thread(process.wait, timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    await asyncio.to_thread(process.wait, timeout=20)
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--blender", type=Path)
    parser.add_argument("--editor", type=Path)
    parser.add_argument("--audit-existing", type=Path)
    parser.add_argument("--variant", choices=("identity", "transformed_metric"), default="identity")
    arguments = parser.parse_args()
    if not arguments.audit_existing and (not arguments.blender or not arguments.editor):
        parser.error("Native acceptance requires --blender and --editor")
    asyncio.run(verify(arguments))
