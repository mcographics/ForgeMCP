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
import importlib
automation = importlib.import_module("majestic_forge.automation")
_apply_modifier_settings = automation.apply_modifier_settings
_modifier_fault_file = Path(os.environ["FORGE_MODIFIER_FAULT_FILE"])
_replace_mesh_geometry = automation.replace_mesh_geometry
_geometry_fault_file = Path(os.environ["FORGE_GEOMETRY_FAULT_FILE"])
_apply_uv_coordinates = automation.apply_uv_coordinates
_uv_fault_file = Path(os.environ["FORGE_UV_FAULT_FILE"])
_create_uv_layer = automation.create_uv_layer
_uv_create_fault_file = Path(os.environ["FORGE_UV_CREATE_FAULT_FILE"])
_smart_project_uvs = automation.smart_project_uvs
_uv_project_fault_file = Path(os.environ["FORGE_UV_PROJECT_FAULT_FILE"])
_apply_mesh_edge_seams = automation.apply_mesh_edge_seams
_edge_seam_fault_file = Path(os.environ["FORGE_EDGE_SEAM_FAULT_FILE"])
_unwrap_uvs = automation.unwrap_uvs
_unwrap_fault_file = Path(os.environ["FORGE_UV_UNWRAP_FAULT_FILE"])
_pack_uv_islands = automation.pack_uv_islands
_uv_pack_fault_file = Path(os.environ["FORGE_UV_PACK_FAULT_FILE"])
def _apply_modifier_settings_with_test_fault(modifier, settings):
    _apply_modifier_settings(modifier, settings)
    if _modifier_fault_file.exists() and settings.get("segments") == 6:
        _modifier_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after modifier write")
automation.apply_modifier_settings = _apply_modifier_settings_with_test_fault
def _replace_mesh_geometry_with_test_fault(mesh, vertices, faces):
    _replace_mesh_geometry(mesh, vertices, faces)
    if _geometry_fault_file.exists():
        _geometry_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after topology replacement")
automation.replace_mesh_geometry = _replace_mesh_geometry_with_test_fault
def _apply_uv_coordinates_with_test_fault(layer, loop_start, uv_values):
    _apply_uv_coordinates(layer, loop_start, uv_values)
    if _uv_fault_file.exists():
        _uv_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after UV write")
automation.apply_uv_coordinates = _apply_uv_coordinates_with_test_fault
def _create_uv_layer_with_test_fault(mesh, name, uv_values):
    layer = _create_uv_layer(mesh, name, uv_values)
    if _uv_create_fault_file.exists():
        _uv_create_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after UV layer creation")
    return layer
automation.create_uv_layer = _create_uv_layer_with_test_fault
def _smart_project_uvs_with_test_fault(obj, layer_name, angle_limit, island_margin):
    count = _smart_project_uvs(obj, layer_name, angle_limit, island_margin)
    if _uv_project_fault_file.exists():
        _uv_project_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after smart UV projection")
    return count
automation.smart_project_uvs = _smart_project_uvs_with_test_fault
def _apply_mesh_edge_seams_with_test_fault(mesh, changes):
    _apply_mesh_edge_seams(mesh, changes)
    if _edge_seam_fault_file.exists():
        _edge_seam_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after seam write")
automation.apply_mesh_edge_seams = _apply_mesh_edge_seams_with_test_fault
def _unwrap_uvs_with_test_fault(obj, layer_name, method, margin):
    count = _unwrap_uvs(obj, layer_name, method, margin)
    if _unwrap_fault_file.exists():
        _unwrap_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after seam-based UV unwrap")
    return count
automation.unwrap_uvs = _unwrap_uvs_with_test_fault
def _pack_uv_islands_with_test_fault(obj, layer_name, margin):
    count = _pack_uv_islands(obj, layer_name, margin)
    if _uv_pack_fault_file.exists():
        _uv_pack_fault_file.unlink()
        raise RuntimeError("Injected disposable validation failure after UV island packing")
    return count
automation.pack_uv_islands = _pack_uv_islands_with_test_fault
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
           "FORGE_MODIFIER_FAULT_FILE": str(root / "inject-modifier-failure-once"),
           "FORGE_GEOMETRY_FAULT_FILE": str(root / "inject-geometry-failure-once"),
           "FORGE_UV_FAULT_FILE": str(root / "inject-uv-failure-once"),
           "FORGE_UV_CREATE_FAULT_FILE": str(root / "inject-uv-create-failure-once"),
           "FORGE_UV_PROJECT_FAULT_FILE": str(root / "inject-uv-project-failure-once"),
           "FORGE_EDGE_SEAM_FAULT_FILE": str(root / "inject-edge-seam-failure-once"),
           "FORGE_UV_UNWRAP_FAULT_FILE": str(root / "inject-uv-unwrap-failure-once"),
           "FORGE_UV_PACK_FAULT_FILE": str(root / "inject-uv-pack-failure-once"),
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
                        f"-abslog={project.parent / 'Saved' / 'Logs' / (project.stem + '.log')}"], project.parent),
        ):
            log = (root / (name + "-launch.log")).open("w", encoding="utf-8")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=log,
                                               stderr=subprocess.STDOUT, **hidden()))
        source = await ready(manager, processes[0], "blender")
        target = await ready(manager, processes[1], "unreal")
        info = await manager.request(target, "project_info")
        assert Path(info["project_file"]).resolve() == project
        server_env = {**env, "PYTHONPATH": str(repository)}
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                           cwd=str(repository), env=server_env)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()

                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                    return result.structuredContent

                blueprint_path = "/Game/ForgeWorkflow/BP_FunctionEdit_" + uuid.uuid4().hex
                blueprint_create = await call("unreal_preview_blueprint", {
                    "session_id": target.session_id, "recipe": {
                        "asset_path": blueprint_path, "parent_class": "/Script/Engine.Actor",
                        "variables": [], "components": [], "functions": [],
                        "nodes": [
                            {"id": "rollback_self", "kind": "self", "name": "RollbackSelf"},
                            {"id": "rollback_print", "kind": "call_function", "name": "PrintString",
                             "owner_class": "/Script/Engine.KismetSystemLibrary",
                             "defaults": {"InString": "rollback probe"}},
                        ], "connections": [], "save": False, "place": False,
                    }})
                assert blueprint_create["ok"], blueprint_create
                create_id = blueprint_create["data"]["preview_id"]
                blueprint_apply = await call("unreal_apply_blueprint", {
                    "session_id": target.session_id, "preview_id": create_id, "confirmation": create_id})
                assert blueprint_apply["ok"] and blueprint_apply["data"]["state"] == "completed", blueprint_apply
                blueprint_before_function = await call("unreal_inspect_blueprint", {
                    "session_id": target.session_id, "asset_path": blueprint_path})
                function_edit_recipe = {"asset_path": blueprint_path, "operations": [], "variables": [],
                    "components": [], "functions": [{"name": "ReviewedScale",
                        "inputs": [{"name": "Value", "type": "float"}],
                        "outputs": [{"name": "Result", "type": "float"}], "pure": True}],
                    "nodes": [
                        {"id": "function_entry", "kind": "function_entry", "name": "Entry", "graph": "ReviewedScale"},
                        {"id": "function_return", "kind": "function_result", "name": "Return", "graph": "ReviewedScale"},
                    ], "connections": [{"graph": "ReviewedScale", "from_node": "function_entry", "from_pin": "Value",
                        "to_node": "function_return", "to_pin": "Result"}]}
                stale_function_preview = await call("unreal_preview_blueprint_edits", {
                    "session_id": target.session_id, "recipe": function_edit_recipe})
                current_function_preview = await call("unreal_preview_blueprint_edits", {
                    "session_id": target.session_id, "recipe": function_edit_recipe})
                assert stale_function_preview["ok"] and current_function_preview["ok"]
                assert blueprint_before_function == await call("unreal_inspect_blueprint", {
                    "session_id": target.session_id, "asset_path": blueprint_path}), "Function preview mutated Blueprint"
                function_id = current_function_preview["data"]["preview_id"]
                function_edit_apply = await call("unreal_apply_blueprint_edits", {
                    "session_id": target.session_id, "preview_id": function_id, "confirmation": function_id})
                assert function_edit_apply["ok"] and function_edit_apply["data"]["state"] == "completed", function_edit_apply
                assert function_edit_apply["data"]["compiler_errors"] == 0
                assert function_edit_apply["data"]["created_functions"] == ["ReviewedScale"]
                stale_function_result = await call("unreal_apply_blueprint_edits", {
                    "session_id": target.session_id,
                    "preview_id": stale_function_preview["data"]["preview_id"],
                    "confirmation": stale_function_preview["data"]["preview_id"]})
                assert not stale_function_result["ok"] and stale_function_result["error"]["code"] == "stale_preview"
                blueprint_after_function = await call("unreal_inspect_blueprint", {
                    "session_id": target.session_id, "asset_path": blueprint_path})
                function_graph = next(g for g in blueprint_after_function["data"]["graphs"] if g["name"] == "ReviewedScale")
                function_entry = next(n for n in function_graph["nodes"] if n["class"].endswith(".K2Node_FunctionEntry"))
                function_return = next(n for n in function_graph["nodes"] if n["class"].endswith(".K2Node_FunctionResult"))
                assert next(p for p in function_entry["pins"] if p["name"] == "Value")["links"]
                assert next(p for p in function_return["pins"] if p["name"] == "Result")["links"]
                event_nodes = next(g for g in blueprint_after_function["data"]["graphs"] if g["name"] == "EventGraph")["nodes"]
                self_node = next(n for n in event_nodes if n["class"].endswith(".K2Node_Self"))
                print_node = next(n for n in event_nodes if n["class"].endswith(".K2Node_CallFunction"))
                rollback_function_preview = await call("unreal_preview_blueprint_edits", {
                    "session_id": target.session_id, "recipe": {"asset_path": blueprint_path,
                        "operations": [{"op": "connect", "graph": "EventGraph", "node_id": self_node["id"],
                            "pin": "self", "to_node": print_node["id"], "to_pin": "execute"}],
                        "variables": [], "components": [], "functions": [{"name": "RollbackOnly"}],
                        "nodes": [], "connections": []}})
                rollback_id = rollback_function_preview["data"]["preview_id"]
                rollback_function_apply = await call("unreal_apply_blueprint_edits", {
                    "session_id": target.session_id, "preview_id": rollback_id, "confirmation": rollback_id})
                assert rollback_function_apply["ok"] and rollback_function_apply["data"]["state"] == "rolled_back", rollback_function_apply
                assert blueprint_after_function == await call("unreal_inspect_blueprint", {
                    "session_id": target.session_id, "asset_path": blueprint_path}), "Failed function edit was not rolled back"

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
                imported_asset_path = request["target_asset_path"]
                selected_assets_before = await call("unreal_get_selected_assets", {
                    "session_id": target.session_id, "limit": 100})
                assert selected_assets_before["ok"], selected_assets_before
                assert selected_assets_before["data"]["returned_count"] <= 100
                browser_sync = await call("unreal_sync_content_browser", {
                    "session_id": target.session_id, "asset_path": imported_asset_path})
                assert browser_sync["ok"] and browser_sync["data"]["sync_requested"], browser_sync
                browser_selection = await call("unreal_get_selected_assets", {
                    "session_id": target.session_id, "limit": 100})
                assert browser_selection["ok"], browser_selection
                assert browser_selection["data"]["returned_count"] <= 100
                replay = await call("forge_apply_transfer", arguments)
                assert replay["error"]["code"] == "preview_not_found", replay
                after = await manager.request(source, "scene_info")
                assert before == after, "Transfer changed source scene facts"
                report = {"interactive_verified": False, "rendered_materials_verified": False,
                          "fixture_variant": args.variant,
                          "native_blueprint_function_edit": {
                              "create": blueprint_apply, "preview": current_function_preview,
                              "apply": function_edit_apply, "inspection": function_graph,
                              "stale_preview": stale_function_result,
                              "rollback": rollback_function_apply,
                              "not_saved": True,
                          },
                          "source_geometry_modified_through_mcp": True,
                          "source_material_modified_through_mcp": True,
                          "source_edit": geometry_edit,
                          "level_saved": False, "source_scene_preserved": True,
                          "content_browser_acceptance": {
                              "selected_before": selected_assets_before,
                              "sync": browser_sync,
                              "selected_after_sync": browser_selection,
                              "visual_focus_verified": False,
                          },
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
                stale_modifier_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "add_modifier", "name": "Cube", "modifier_type": "SUBSURF",
                        "modifier_name": "ForgeMCPStaleSubdivision",
                        "modifier_settings": {"levels": 2, "render_levels": 2}}]}})
                assert stale_modifier_preview["ok"], stale_modifier_preview
                current_modifier_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "add_modifier", "name": "Cube", "modifier_type": "BEVEL",
                        "modifier_name": "ForgeMCPReviewedBevel",
                        "modifier_settings": {"segments": 3, "width": 0.05}}]}})
                assert current_modifier_preview["ok"], current_modifier_preview
                current_modifier_id = current_modifier_preview["data"]["preview_id"]
                current_modifier_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": current_modifier_id,
                    "confirmation": current_modifier_id})
                assert current_modifier_apply["ok"], current_modifier_apply
                stale_modifier_id = stale_modifier_preview["data"]["preview_id"]
                stale_modifier_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_modifier_id,
                    "confirmation": stale_modifier_id})
                assert stale_modifier_apply["error"]["code"] == "stale_preview", stale_modifier_apply
                modifier_inspection = await call("blender_inspect_object", {
                    "session_id": source.session_id, "name": "Cube"})
                assert modifier_inspection["ok"], modifier_inspection
                modifiers = modifier_inspection["data"]["modifiers"]
                bevel = next(item for item in modifiers if item["name"] == "ForgeMCPReviewedBevel")
                assert bevel["type"] == "BEVEL" and bevel["settings"]["segments"] == 3
                assert not any(item["name"] == "ForgeMCPStaleSubdivision" for item in modifiers)
                modifier_fault = root / "inject-modifier-failure-once"
                modifier_fault.touch()
                modifier_rollback_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_modifier_settings", "name": "Cube",
                        "modifier_name": "ForgeMCPReviewedBevel", "modifier_settings": {"segments": 6}}]}})
                modifier_rollback_id = modifier_rollback_preview["data"]["preview_id"]
                modifier_rollback_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": modifier_rollback_id,
                    "confirmation": modifier_rollback_id})
                assert modifier_rollback_apply["ok"]
                assert modifier_rollback_apply["data"]["state"] == "rolled_back"
                assert modifier_rollback_apply["data"]["rollback_errors"] == []
                after_modifier_rollback = await call("blender_inspect_object", {
                    "session_id": source.session_id, "name": "Cube"})
                assert next(item for item in after_modifier_rollback["data"]["modifiers"]
                            if item["name"] == "ForgeMCPReviewedBevel")["settings"]["segments"] == 3
                stale_modifier_edit = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_modifier_settings", "name": "Cube",
                        "modifier_name": "ForgeMCPReviewedBevel", "modifier_settings": {"segments": 4}}]}})
                current_modifier_edit = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_modifier_settings", "name": "Cube",
                        "modifier_name": "ForgeMCPReviewedBevel", "modifier_settings": {"segments": 5}}]}})
                assert stale_modifier_edit["ok"] and current_modifier_edit["ok"]
                modifier_edit_id = current_modifier_edit["data"]["preview_id"]
                modifier_edit_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": modifier_edit_id,
                    "confirmation": modifier_edit_id})
                assert modifier_edit_apply["ok"] and modifier_edit_apply["data"]["state"] == "completed"
                stale_modifier_edit_id = stale_modifier_edit["data"]["preview_id"]
                stale_modifier_edit_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_modifier_edit_id,
                    "confirmation": stale_modifier_edit_id})
                assert stale_modifier_edit_apply["error"]["code"] == "stale_preview", stale_modifier_edit_apply
                modifier_after_edit = await call("blender_inspect_object", {
                    "session_id": source.session_id, "name": "Cube"})
                edited_bevel = next(item for item in modifier_after_edit["data"]["modifiers"]
                                    if item["name"] == "ForgeMCPReviewedBevel")
                assert edited_bevel["settings"]["segments"] == 5
                report["blender_modifier_automation"] = {
                    "preview": current_modifier_preview, "apply": current_modifier_apply,
                    "inspection": modifier_inspection, "stale_preview_rejected": stale_modifier_apply,
                    "stale_modifier_absent": True, "edit_preview": current_modifier_edit,
                    "edit_apply": modifier_edit_apply, "post_edit_inspection": modifier_after_edit,
                    "stale_edit_rejected": stale_modifier_edit_apply,
                    "rollback_apply": modifier_rollback_apply,
                    "rollback_inspection": after_modifier_rollback}
                uv_before = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "loop_count": 8})
                assert uv_before["ok"] and uv_before["data"]["loop_total"] > 0, uv_before
                uv_layer = uv_before["data"]["layer"]
                uv_old = uv_before["data"]["loops"][0]["uv"]
                uv_stale_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_uv_coordinates", "name": "Cube", "uv_layer": uv_layer,
                        "uv_start": 0, "uv_values": [[uv_old[0] + 0.125, uv_old[1] + 0.125]]}]}})
                uv_current_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_uv_coordinates", "name": "Cube", "uv_layer": uv_layer,
                        "uv_start": 0, "uv_values": [[uv_old[0] + 0.25, uv_old[1] + 0.25]]}]}})
                assert uv_stale_preview["ok"] and uv_current_preview["ok"]
                uv_current_id = uv_current_preview["data"]["preview_id"]
                uv_current_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": uv_current_id,
                    "confirmation": uv_current_id})
                assert uv_current_apply["ok"]
                uv_stale_id = uv_stale_preview["data"]["preview_id"]
                uv_stale_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": uv_stale_id,
                    "confirmation": uv_stale_id})
                assert uv_stale_apply["error"]["code"] == "stale_preview", uv_stale_apply
                uv_after_apply = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": uv_layer,
                    "loop_count": 8})
                uv_expected = [uv_old[0] + 0.25, uv_old[1] + 0.25]
                assert all(abs(a - b) < 1e-6 for a, b in zip(uv_after_apply["data"]["loops"][0]["uv"], uv_expected))
                uv_fault = root / "inject-uv-failure-once"
                uv_fault.touch()
                uv_rollback_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_uv_coordinates", "name": "Cube", "uv_layer": uv_layer,
                        "uv_start": 0, "uv_values": [[uv_expected[0] + 0.5, uv_expected[1] + 0.5]]}]}})
                uv_rollback_id = uv_rollback_preview["data"]["preview_id"]
                uv_rollback_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": uv_rollback_id,
                    "confirmation": uv_rollback_id})
                assert uv_rollback_apply["ok"] and uv_rollback_apply["data"]["state"] == "rolled_back"
                assert uv_rollback_apply["data"]["rollback_errors"] == []
                uv_after_rollback = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": uv_layer,
                    "loop_count": 8})
                assert uv_after_rollback["data"]["loops"][0]["uv"] == uv_after_apply["data"]["loops"][0]["uv"]
                report["blender_uv_automation"] = {
                    "before": uv_before, "preview": uv_current_preview, "apply": uv_current_apply,
                    "after": uv_after_apply, "stale_preview_rejected": uv_stale_apply,
                    "rollback_apply": uv_rollback_apply, "after_rollback": uv_after_rollback}
                initial_topology = {
                    "op": "create_mesh", "name": "ForgeTopologyProbe",
                    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    "faces": [[0, 1, 2]],
                }
                replacement_topology = {
                    "op": "set_mesh_geometry", "name": "ForgeTopologyProbe",
                    "vertices": [[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]],
                    "faces": [[0, 1, 2], [0, 2, 3]],
                }
                topology_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id,
                    "recipe": {"operations": [initial_topology, replacement_topology]}})
                assert topology_preview["ok"], topology_preview
                topology_id = topology_preview["data"]["preview_id"]
                topology_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": topology_id,
                    "confirmation": topology_id})
                assert topology_apply["ok"] and topology_apply["data"]["state"] == "completed"
                topology_info = await call("blender_inspect_mesh_geometry", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "vertex_count": 16, "face_count": 16})
                assert topology_info["ok"], topology_info
                topology_data = topology_info["data"]
                assert topology_data["vertex_total"] == 4 and topology_data["face_total"] == 2
                assert [face["vertices"] for face in topology_data["faces"]] == [[0, 1, 2], [0, 2, 3]]
                bounded_vertices = [[float(index), 0.0, 0.0] for index in range(512)]
                bounded_faces = [[0, index, index + 1] for index in range(1, 511)]
                bounded_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [
                        {"op": "create_mesh", "name": "ForgeTopologyBoundProbe",
                         "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 2]]},
                        {"op": "set_mesh_geometry", "name": "ForgeTopologyBoundProbe",
                         "vertices": bounded_vertices, "faces": bounded_faces}]}})
                assert bounded_preview["ok"], bounded_preview
                bounded_id = bounded_preview["data"]["preview_id"]
                bounded_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": bounded_id,
                    "confirmation": bounded_id})
                assert bounded_apply["ok"], bounded_apply
                bounded_geometry = await call("blender_inspect_mesh_geometry", {
                    "session_id": source.session_id, "name": "ForgeTopologyBoundProbe",
                    "vertex_start": 510, "vertex_count": 2,
                    "face_start": 508, "face_count": 8})
                assert bounded_geometry["ok"], bounded_geometry
                bounded_data = bounded_geometry["data"]
                assert bounded_data["vertex_total"] == 512 and bounded_data["face_total"] == 510
                assert [vertex["index"] for vertex in bounded_data["vertices"]] == [510, 511]
                assert [face["index"] for face in bounded_data["faces"]] == [508, 509]
                assert bounded_data["vertices_truncated"] is False
                assert bounded_data["faces_truncated"] is False
                stale_topology = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_mesh_geometry", "name": "ForgeTopologyProbe",
                        "vertices": [[0, 0, 0], [3, 0, 0], [3, 1, 0], [0, 1, 0], [0, 0, 1]],
                        "faces": [[0, 1, 2], [0, 2, 3], [0, 3, 4]]}]}})
                current_topology = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_mesh_geometry", "name": "ForgeTopologyProbe",
                        "vertices": [[0, 0, 0], [4, 0, 0], [4, 1, 0], [0, 1, 0]],
                        "faces": [[0, 1, 2], [0, 2, 3]]}]}})
                assert stale_topology["ok"] and current_topology["ok"]
                current_topology_id = current_topology["data"]["preview_id"]
                current_topology_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": current_topology_id,
                    "confirmation": current_topology_id})
                assert current_topology_apply["ok"]
                stale_topology_id = stale_topology["data"]["preview_id"]
                stale_topology_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_topology_id,
                    "confirmation": stale_topology_id})
                assert stale_topology_apply["error"]["code"] == "stale_preview", stale_topology_apply
                geometry_before_rollback = await call("blender_inspect_mesh_geometry", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "vertex_count": 16, "face_count": 16})
                geometry_fault = root / "inject-geometry-failure-once"
                geometry_fault.touch()
                rollback_topology_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_mesh_geometry", "name": "ForgeTopologyProbe",
                        "vertices": [[0, 0, 0], [5, 0, 0], [5, 1, 0], [0, 1, 0], [0, 0, 1]],
                        "faces": [[0, 1, 2], [0, 2, 3], [0, 3, 4]]}]}})
                rollback_topology_id = rollback_topology_preview["data"]["preview_id"]
                rollback_topology_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_topology_id,
                    "confirmation": rollback_topology_id})
                assert rollback_topology_apply["ok"]
                assert rollback_topology_apply["data"]["state"] == "rolled_back"
                assert rollback_topology_apply["data"]["rollback_errors"] == []
                topology_after_rollback = await call("blender_inspect_mesh_geometry", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "vertex_count": 16, "face_count": 16})
                assert topology_after_rollback["data"]["vertex_total"] == 4
                assert topology_after_rollback["data"]["face_total"] == 2
                assert topology_after_rollback["data"]["vertices"] == geometry_before_rollback["data"]["vertices"]
                assert topology_after_rollback["data"]["faces"] == geometry_before_rollback["data"]["faces"]
                layer_values = [[0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]]
                layer_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [
                        {"op": "create_uv_layer", "name": "ForgeTopologyProbe",
                         "uv_layer": "ForgeCreatedUV", "uv_values": layer_values},
                        {"op": "set_uv_coordinates", "name": "ForgeTopologyProbe",
                         "uv_layer": "ForgeCreatedUV", "uv_start": 0,
                         "uv_values": [[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.1],[0.9,0.9],[0.1,0.9]]},
                    ]}})
                assert layer_preview["ok"], layer_preview
                layer_preview_id = layer_preview["data"]["preview_id"]
                layer_applied = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": layer_preview_id,
                    "confirmation": layer_preview_id})
                assert layer_applied["ok"] and layer_applied["data"]["state"] == "completed", layer_applied
                layer_inspection = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "layer_name": "ForgeCreatedUV", "loop_count": 8})
                assert layer_inspection["ok"] and layer_inspection["data"]["loop_total"] == 6
                assert all(abs(a-b) < 1e-6 for a,b in zip(
                    layer_inspection["data"]["loops"][0]["uv"], [0.1, 0.1]))
                layer_fault = root / "inject-uv-create-failure-once"
                layer_fault.touch()
                rollback_layer_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "create_uv_layer", "name": "ForgeTopologyProbe",
                        "uv_layer": "ForgeRollbackUV"}]}})
                rollback_layer_id = rollback_layer_preview["data"]["preview_id"]
                rollback_layer_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_layer_id,
                    "confirmation": rollback_layer_id})
                assert rollback_layer_apply["ok"]
                assert rollback_layer_apply["data"]["state"] == "rolled_back"
                assert rollback_layer_apply["data"]["rollback_errors"] == []
                absent_layer = await client.call_tool("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "layer_name": "ForgeRollbackUV", "loop_count": 1})
                absent_layer_data = absent_layer.structuredContent
                assert absent_layer_data["error"]["code"] == "uv_layer_not_found", absent_layer_data
                unwrap_args = {"op": "smart_uv_project", "name": "ForgeTopologyProbe",
                    "uv_layer": "ForgeCreatedUV", "uv_angle_limit": 1.1519173063162575,
                    "uv_island_margin": 0.02}
                unwrap_stale = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [unwrap_args]}})
                unwrap_current = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [unwrap_args]}})
                assert unwrap_stale["ok"] and unwrap_current["ok"]
                unwrap_id = unwrap_current["data"]["preview_id"]
                unwrap_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": unwrap_id,
                    "confirmation": unwrap_id})
                assert unwrap_apply["ok"] and unwrap_apply["data"]["operations"][0]["native_uv_projection_verified"]
                stale_unwrap_id = unwrap_stale["data"]["preview_id"]
                stale_unwrap = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_unwrap_id,
                    "confirmation": stale_unwrap_id})
                assert stale_unwrap["error"]["code"] == "stale_preview", stale_unwrap
                unwrap_inspection = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "layer_name": "ForgeCreatedUV", "loop_count": 8})
                assert unwrap_inspection["ok"] and unwrap_inspection["data"]["loop_total"] == 6
                assert all(0 <= axis <= 1 for item in unwrap_inspection["data"]["loops"] for axis in item["uv"])
                unwrap_before_fault = [item["uv"] for item in unwrap_inspection["data"]["loops"]]
                project_fault = root / "inject-uv-project-failure-once"
                project_fault.touch()
                rollback_unwrap_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        **unwrap_args, "uv_island_margin": 0.04}]}})
                rollback_unwrap_id = rollback_unwrap_preview["data"]["preview_id"]
                rollback_unwrap_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_unwrap_id,
                    "confirmation": rollback_unwrap_id})
                assert rollback_unwrap_apply["ok"]
                assert rollback_unwrap_apply["data"]["state"] == "rolled_back"
                assert rollback_unwrap_apply["data"]["rollback_errors"] == []
                unwrap_after_rollback = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "layer_name": "ForgeCreatedUV", "loop_count": 8})
                assert [item["uv"] for item in unwrap_after_rollback["data"]["loops"]] == unwrap_before_fault
                edge_before = await call("blender_inspect_mesh_edges", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "edge_start": 0, "edge_count": 8})
                edge_index = edge_before["data"]["edges"][0]["index"]
                seam_args = {"op": "set_mesh_edge_seams", "name": "ForgeTopologyProbe",
                    "edge_seams": [{"index": edge_index, "seam": True}]}
                stale_seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [seam_args]}})
                seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [seam_args]}})
                seam_id = seam_preview["data"]["preview_id"]
                seam_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": seam_id,
                    "confirmation": seam_id})
                assert seam_apply["data"]["operations"][0]["native_seams_verified"]
                stale_seam_id = stale_seam_preview["data"]["preview_id"]
                stale_seam = await client.call_tool("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_seam_id,
                    "confirmation": stale_seam_id})
                stale_seam_data = stale_seam.structuredContent
                assert stale_seam_data["error"]["code"] == "stale_preview", stale_seam_data
                seam_inspection = await call("blender_inspect_mesh_edges", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "edge_start": edge_index, "edge_count": 1})
                assert seam_inspection["data"]["edges"][0]["seam"] is True
                seam_fault = root / "inject-edge-seam-failure-once"
                seam_fault.touch()
                rollback_seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_mesh_edge_seams", "name": "ForgeTopologyProbe",
                        "edge_seams": [{"index": edge_index, "seam": False}]}]}})
                rollback_seam_id = rollback_seam_preview["data"]["preview_id"]
                rollback_seam_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_seam_id,
                    "confirmation": rollback_seam_id})
                assert rollback_seam_apply["data"]["state"] == "rolled_back"
                assert rollback_seam_apply["data"]["rollback_errors"] == []
                seam_after_rollback = await call("blender_inspect_mesh_edges", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "edge_start": edge_index, "edge_count": 1})
                assert seam_after_rollback["data"]["edges"][0]["seam"] is True
                cube_edges = await call("blender_inspect_mesh_edges", {
                    "session_id": source.session_id, "name": "Cube", "edge_start": 0, "edge_count": 32})
                cube_seam_recipe = {"op": "set_mesh_edge_seams", "name": "Cube",
                    "edge_seams": [{"index": edge["index"], "seam": True}
                                    for edge in cube_edges["data"]["edges"]]}
                cube_seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [cube_seam_recipe]}})
                cube_seam_id = cube_seam_preview["data"]["preview_id"]
                cube_seam_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": cube_seam_id,
                    "confirmation": cube_seam_id})
                assert cube_seam_apply["data"]["operations"][0]["native_seams_verified"]
                unwrap_recipe = {"op": "unwrap_uv", "name": "Cube", "uv_layer": "UVMap",
                    "uv_unwrap_method": "ANGLE_BASED", "uv_margin": 0.001}
                unwrap_seam_stale_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [unwrap_recipe]}})
                unwrap_seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [unwrap_recipe]}})
                unwrap_seam_id = unwrap_seam_preview["data"]["preview_id"]
                unwrap_seam_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": unwrap_seam_id,
                    "confirmation": unwrap_seam_id})
                assert unwrap_seam_apply["data"]["operations"][0]["native_seam_unwrap_verified"]
                stale_unwrap_seam_id = unwrap_seam_stale_preview["data"]["preview_id"]
                stale_unwrap_seam = await client.call_tool("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_unwrap_seam_id,
                    "confirmation": stale_unwrap_seam_id})
                stale_unwrap_seam_data = stale_unwrap_seam.structuredContent
                assert stale_unwrap_seam_data["error"]["code"] == "stale_preview", stale_unwrap_seam_data
                cube_uv_after_unwrap = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": "UVMap",
                    "loop_count": 32})
                assert cube_uv_after_unwrap["ok"] and len(cube_uv_after_unwrap["data"]["loops"]) == 24
                assert all(-1e-6 <= value <= 1.000001
                           for loop in cube_uv_after_unwrap["data"]["loops"] for value in loop["uv"])
                cube_uv_before_fault = [loop["uv"] for loop in cube_uv_after_unwrap["data"]["loops"]]
                unwrap_fault = root / "inject-uv-unwrap-failure-once"
                unwrap_fault.touch()
                rollback_unwrap_seam_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        **unwrap_recipe, "uv_margin": 0.002}]}})
                rollback_unwrap_seam_id = rollback_unwrap_seam_preview["data"]["preview_id"]
                rollback_unwrap_seam_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_unwrap_seam_id,
                    "confirmation": rollback_unwrap_seam_id})
                assert rollback_unwrap_seam_apply["data"]["state"] == "rolled_back"
                assert rollback_unwrap_seam_apply["data"]["rollback_errors"] == []
                cube_uv_after_unwrap_rollback = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": "UVMap",
                    "loop_count": 32})
                assert [loop["uv"] for loop in cube_uv_after_unwrap_rollback["data"]["loops"]] == cube_uv_before_fault
                pack_recipe = {"op": "pack_uv_islands", "name": "Cube", "uv_layer": "UVMap", "uv_margin": 0.002}
                stale_pack_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [pack_recipe]}})
                pack_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [pack_recipe]}})
                pack_id = pack_preview["data"]["preview_id"]
                pack_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": pack_id, "confirmation": pack_id})
                assert pack_apply["data"]["operations"][0]["native_uv_packing_verified"]
                stale_pack_id = stale_pack_preview["data"]["preview_id"]
                stale_pack = await client.call_tool("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": stale_pack_id, "confirmation": stale_pack_id})
                stale_pack_data = stale_pack.structuredContent
                assert stale_pack_data["error"]["code"] == "stale_preview", stale_pack_data
                packed_uvs = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": "UVMap", "loop_count": 32})
                assert packed_uvs["ok"] and len(packed_uvs["data"]["loops"]) == 24
                assert all(-1e-6 <= value <= 1.000001 for loop in packed_uvs["data"]["loops"] for value in loop["uv"])
                packed_uv_before_fault = [loop["uv"] for loop in packed_uvs["data"]["loops"]]
                _uv_pack_fault_file = root / "inject-uv-pack-failure-once"
                _uv_pack_fault_file.touch()
                rollback_pack_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{**pack_recipe, "uv_margin": 0.003}]}})
                rollback_pack_id = rollback_pack_preview["data"]["preview_id"]
                rollback_pack_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": rollback_pack_id, "confirmation": rollback_pack_id})
                assert rollback_pack_apply["data"]["state"] == "rolled_back"
                assert rollback_pack_apply["data"]["rollback_errors"] == []
                packed_uv_after_rollback = await call("blender_inspect_mesh_uvs", {
                    "session_id": source.session_id, "name": "Cube", "layer_name": "UVMap", "loop_count": 32})
                assert [loop["uv"] for loop in packed_uv_after_rollback["data"]["loops"]] == packed_uv_before_fault
                animation_recipe = {"operations": [
                    {"op": "keyframe", "name": "ForgeTopologyProbe", "data_path": "location",
                     "frame": 3, "value": [0.0, 0.0, 0.0]},
                    {"op": "keyframe", "name": "ForgeTopologyProbe", "data_path": "location",
                     "frame": 7, "value": [1.0, 0.0, 0.0]},
                ]}
                animation_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": animation_recipe})
                animation_id = animation_preview["data"]["preview_id"]
                animation_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": animation_id,
                    "confirmation": animation_id})
                assert animation_apply["ok"]
                animation_inspection = await call("blender_inspect_animation", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "curve_count": 3, "keyframe_count": 8})
                assert animation_inspection["ok"] and animation_inspection["data"]["action"]
                assert animation_inspection["data"]["curve_total"] == 3
                assert all(len(curve["keyframes"]) == 2
                           for curve in animation_inspection["data"]["curves"])
                original_action_name = animation_inspection["data"]["action"]
                occupied_key_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_keyframe", "name": "ForgeTopologyProbe",
                        "curve_index": 0, "keyframe_index": 0,
                        "key_frame": 7.0, "key_value": 2.5,
                    }]}})
                assert not occupied_key_preview["ok"]
                assert occupied_key_preview["error"]["code"] == "keyframe_collision"
                edit_key_preview = await call("blender_preview_scene", {
                    "session_id": source.session_id, "recipe": {"operations": [{
                        "op": "set_keyframe", "name": "ForgeTopologyProbe",
                        "curve_index": 0, "keyframe_index": 0,
                        "key_frame": 4.0, "key_value": 2.5,
                    }]}})
                assert edit_key_preview["ok"], edit_key_preview
                edit_key_id = edit_key_preview["data"]["preview_id"]
                edit_key_apply = await call("blender_apply_scene", {
                    "session_id": source.session_id, "preview_id": edit_key_id,
                    "confirmation": edit_key_id})
                assert edit_key_apply["ok"] and edit_key_apply["data"]["state"] == "completed"
                assert edit_key_apply["data"]["operations"][0]["native_keyframe_verified"]
                edited_animation = await call("blender_inspect_animation", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe",
                    "curve_count": 3, "keyframe_count": 8})
                assert edited_animation["ok"]
                assert edited_animation["data"]["action"] != original_action_name
                edited_x_keys = edited_animation["data"]["curves"][0]["keyframes"]
                assert [(key["frame"], key["value"]) for key in edited_x_keys] == [
                    (4.0, 2.5), (7.0, 1.0)]
                animation_second_page = await call("blender_inspect_animation", {
                    "session_id": source.session_id, "name": "ForgeTopologyProbe", "curve_start": 1,
                    "curve_count": 1, "keyframe_start": 1, "keyframe_count": 1})
                assert animation_second_page["ok"]
                assert animation_second_page["data"]["curve_start"] == 1
                assert animation_second_page["data"]["curves"][0]["keyframes"][0]["frame"] == 7.0
                report["blender_mesh_geometry"] = {
                    "replacement_preview": topology_preview, "replacement_apply": topology_apply,
                    "geometry_inspection": topology_info, "stale_preview_rejected": stale_topology_apply,
                    "bounded_512_vertex_510_face_apply": bounded_apply,
                    "bounded_geometry_tail_inspection": bounded_geometry,
                    "rollback_apply": rollback_topology_apply,
                    "post_rollback_inspection": topology_after_rollback,
                    "uv_layer_create_edit_inspection": layer_inspection,
                    "uv_layer_create_rollback": rollback_layer_apply,
                    "uv_layer_absence_verified": absent_layer_data,
                    "smart_uv_project_apply": unwrap_apply,
                    "smart_uv_stale_preview_rejected": stale_unwrap,
                    "smart_uv_inspection": unwrap_inspection,
                    "smart_uv_rollback": rollback_unwrap_apply,
                    "smart_uv_post_rollback_inspection": unwrap_after_rollback,
                    "edge_seam_inspection_before": edge_before,
                    "edge_seam_apply": seam_apply,
                    "stale_edge_seam_preview": stale_seam_data,
                    "edge_seam_inspection_after": seam_inspection,
                    "edge_seam_rollback": rollback_seam_apply,
                    "edge_seam_post_rollback_inspection": seam_after_rollback,
                    "cube_edge_seam_setup": cube_seam_apply,
                    "seam_unwrap_apply": unwrap_seam_apply,
                    "seam_unwrap_stale_preview": stale_unwrap_seam_data,
                    "seam_unwrap_uv_inspection": cube_uv_after_unwrap,
                    "seam_unwrap_rollback": rollback_unwrap_seam_apply,
                    "existing_action_key_edit": edit_key_apply,
                    "existing_action_key_edit_readback": edited_animation,
                    "occupied_action_key_frame_rejected": occupied_key_preview,
                    "seam_unwrap_post_rollback_uvs": cube_uv_after_unwrap_rollback,
                    "uv_pack_apply": pack_apply, "uv_pack_stale_preview": stale_pack_data,
                    "uv_pack_inspection": packed_uvs, "uv_pack_rollback": rollback_pack_apply,
                    "uv_pack_post_rollback_uvs": packed_uv_after_rollback,
                    "animation_preview": animation_preview, "animation_apply": animation_apply,
                    "animation_action_inspection": animation_inspection,
                    "animation_second_page": animation_second_page}
                (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
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
                selected_actors = await call("unreal_get_selected_actors", {
                    "session_id": target.session_id, "limit": 200})
                assert selected_actors["ok"], selected_actors
                assert isinstance(selected_actors["data"]["actors"], list)
                assert selected_actors["data"]["total_count"] == len(selected_actors["data"]["actors"])
                assert selected_actors["data"]["truncated"] is False
                actor_search_term = placed.get("label") or placed["name"]
                actor_search = await call("unreal_find_actors", {
                    "session_id": target.session_id, "name_contains": actor_search_term,
                    "class_path": placed["class_path"], "limit": 1})
                assert actor_search["ok"], actor_search
                assert actor_search["data"]["total_matches"] == 1
                assert actor_search["data"]["returned_count"] == 1
                assert actor_search["data"]["actors"][0]["path"] == placed["path"]
                actor_search_next_page = await call("unreal_find_actors", {
                    "session_id": target.session_id, "name_contains": actor_search_term,
                    "offset": 1, "limit": 1})
                assert actor_search_next_page["ok"]
                assert actor_search_next_page["data"]["total_matches"] == 1
                assert actor_search_next_page["data"]["actors"] == []
                actor_tag = "ForgeMCP_TagSearch_" + uuid.uuid4().hex[:12]
                tagged_actor_preview = await call("unreal_preview_actors", {
                    "session_id": target.session_id, "recipe": {"operations": [{
                        "op": "spawn", "class_path": "/Script/Engine.PointLight",
                        "label": "Forge Tag Search Probe", "tags": [actor_tag],
                        "location": [321.0, 654.0, 987.0],
                        "rotation": [10.0, 20.0, 30.0], "scale": [2.0, 3.0, 4.0],
                    }]}})
                assert tagged_actor_preview["ok"], tagged_actor_preview
                tagged_actor_preview_id = tagged_actor_preview["data"]["preview_id"]
                tagged_actor_apply = await call("unreal_apply_actors", {
                    "session_id": target.session_id, "preview_id": tagged_actor_preview_id,
                    "confirmation": tagged_actor_preview_id})
                assert tagged_actor_apply["ok"] and tagged_actor_apply["data"]["state"] == "completed", tagged_actor_apply
                tagged_actor = tagged_actor_apply["data"]["actors"][0]
                assert actor_tag in tagged_actor["tags"], tagged_actor
                tag_search = await call("unreal_find_actors", {
                    "session_id": target.session_id, "tag": actor_tag,
                    "class_path": "/Script/Engine.PointLight", "include_transform": True,
                    "limit": 1})
                assert tag_search["ok"], tag_search
                assert tag_search["data"]["total_matches"] == 1, tag_search
                found_tagged_actor = tag_search["data"]["actors"][0]
                assert found_tagged_actor["path"] == tagged_actor["path"]
                for field, expected in (("location", [321.0, 654.0, 987.0]),
                                        ("rotation", [10.0, 20.0, 30.0]),
                                        ("scale", [2.0, 3.0, 4.0])):
                    assert len(found_tagged_actor[field]) == 3
                    assert all(abs(value - wanted) < 1e-4
                               for value, wanted in zip(found_tagged_actor[field], expected))
                absent_tag_search = await call("unreal_find_actors", {
                    "session_id": target.session_id, "tag": actor_tag + "_absent"})
                assert absent_tag_search["ok"] and absent_tag_search["data"]["total_matches"] == 0
                actor_search_missing_filter = await call("unreal_find_actors", {
                    "session_id": target.session_id})
                assert actor_search_missing_filter["error"]["code"] == "invalid_arguments"
                editor_log = await call("unreal_read_editor_log", {
                    "session_id": target.session_id, "limit": 8})
                assert editor_log["ok"], editor_log
                assert isinstance(editor_log["data"]["lines"], list)
                assert len(editor_log["data"]["lines"]) <= 8
                assert editor_log["data"]["total_returned"] == len(editor_log["data"]["lines"])
                assert isinstance(editor_log["data"]["truncated"], bool)
                actor_before_failures = await manager.request(target, "actor_info", {"actor_path": placed["path"]})
                actor_components = await call("unreal_inspect_actor_components", {
                    "actor_path": placed["path"], "session_id": target.session_id})
                assert actor_components["ok"], actor_components
                assert actor_components["data"]["actor_path"] == placed["path"]
                assert actor_components["data"]["component_count"] == len(actor_components["data"]["components"])
                mesh_component = next(item for item in actor_components["data"]["components"]
                                      if item.get("static_mesh"))
                assert mesh_component["static_mesh"] == actor_before_failures["actor"]["static_mesh"]
                component_properties = await call("unreal_inspect_component_properties", {
                    "component_path": mesh_component["path"], "session_id": target.session_id,
                    "limit": 200})
                assert component_properties["ok"], component_properties
                assert component_properties["data"]["component_path"] == mesh_component["path"]
                assert component_properties["data"]["owner_actor"] == placed["path"]
                assert component_properties["data"]["properties"]
                editable_component_float = next(item for item in component_properties["data"]["properties"]
                    if item["name"] == "StreamingDistanceMultiplier" and item["editable_in_editor"])
                before_component_float = float(editable_component_float["value"])
                assert before_component_float > 0, editable_component_float
                component_edit_args = {"component_path": mesh_component["path"],
                    "property_name": editable_component_float["name"], "property_value": str(before_component_float + 0.125),
                    "session_id": target.session_id}
                stale_component_edit = await call("unreal_preview_component_property_edit", component_edit_args)
                current_component_edit = await call("unreal_preview_component_property_edit", component_edit_args)
                assert stale_component_edit["ok"] and current_component_edit["ok"]
                component_edit_id = current_component_edit["data"]["preview_id"]
                component_edit_apply = await call("unreal_apply_component_property_edit", {
                    "session_id": target.session_id, "preview_id": component_edit_id,
                    "confirmation": component_edit_id})
                assert component_edit_apply["ok"] and component_edit_apply["data"]["saved"] is False
                stale_component_id = stale_component_edit["data"]["preview_id"]
                stale_component_apply = await call("unreal_apply_component_property_edit", {
                    "session_id": target.session_id, "preview_id": stale_component_id,
                    "confirmation": stale_component_id})
                assert stale_component_apply["error"]["code"] == "stale_preview", stale_component_apply
                component_properties_after = await call("unreal_inspect_component_properties", {
                    "component_path": mesh_component["path"], "session_id": target.session_id,
                    "limit": 200})
                assert component_properties_after["ok"]
                observed_component_float = float(next(item for item in component_properties_after["data"]["properties"]
                    if item["name"] == editable_component_float["name"])["value"])
                assert abs(observed_component_float - (before_component_float + 0.125)) < 1e-6
                bitfield_bool = next(item for item in component_properties_after["data"]["properties"]
                    if item["name"] == "bRenderInMainPass")
                assert bitfield_bool["reflection_class"] == "BoolProperty", bitfield_bool
                assert bitfield_bool["value"].casefold() == "true" and bitfield_bool["editable_in_editor"]
                bool_edit_preview = await call("unreal_preview_component_property_edit", {
                    "session_id": target.session_id, "component_path": mesh_component["path"],
                    "property_name": bitfield_bool["name"], "property_value": "False"})
                assert bool_edit_preview["ok"], bool_edit_preview
                bool_edit_id = bool_edit_preview["data"]["preview_id"]
                bool_edit_apply = await call("unreal_apply_component_property_edit", {
                    "session_id": target.session_id, "preview_id": bool_edit_id,
                    "confirmation": bool_edit_id})
                assert bool_edit_apply["ok"] and bool_edit_apply["data"]["applied_value"].casefold() == "false", bool_edit_apply
                bool_properties_after = await call("unreal_inspect_component_properties", {
                    "component_path": mesh_component["path"], "session_id": target.session_id,
                    "limit": 200})
                assert next(item for item in bool_properties_after["data"]["properties"]
                    if item["name"] == bitfield_bool["name"])["value"].casefold() == "false"
                actor_properties = await call("unreal_inspect_actor_properties", {
                    "actor_path": placed["path"], "session_id": target.session_id, "limit": 200})
                assert actor_properties["ok"], actor_properties
                editable_numeric = next(item for item in actor_properties["data"]["properties"]
                    if item["editable_in_editor"] and any(token in item["type"].lower()
                        for token in ("float", "double")) and item["value"].replace(".", "", 1).replace("-", "", 1).isdigit())
                before_value = float(editable_numeric["value"])
                property_name = editable_numeric["name"]
                stale_value = str(before_value + 0.25)
                applied_value = str(before_value + 0.125)
                stale_actor_edit = await call("unreal_preview_actor_property_edit", {
                    "session_id": target.session_id, "request": {
                        "actor_path": placed["path"], "property_name": property_name, "property_value": stale_value}})
                assert stale_actor_edit["ok"], stale_actor_edit
                current_actor_edit = await call("unreal_preview_actor_property_edit", {
                    "session_id": target.session_id, "request": {
                        "actor_path": placed["path"], "property_name": property_name, "property_value": applied_value}})
                assert current_actor_edit["ok"], current_actor_edit
                current_actor_id = current_actor_edit["data"]["preview_id"]
                actor_edit_result = await call("unreal_apply_actor_property_edit", {
                    "session_id": target.session_id, "preview_id": current_actor_id,
                    "confirmation": current_actor_id})
                assert actor_edit_result["ok"] and actor_edit_result["data"]["saved"] is False, actor_edit_result
                actor_property_after = await call("unreal_inspect_actor_properties", {
                    "actor_path": placed["path"], "session_id": target.session_id, "limit": 200})
                applied_property = next(item for item in actor_property_after["data"]["properties"]
                                        if item["name"] == property_name)
                assert applied_property["value"] == actor_edit_result["data"]["applied_value"]
                stale_actor_id = stale_actor_edit["data"]["preview_id"]
                stale_actor_result = await call("unreal_apply_actor_property_edit", {
                    "session_id": target.session_id, "preview_id": stale_actor_id,
                    "confirmation": stale_actor_id})
                assert stale_actor_result["error"]["code"] == "stale_preview", stale_actor_result
                report["native_actor_property_edit"] = {
                    "inspection": actor_properties, "edit_preview": current_actor_edit,
                    "edit_apply": actor_edit_result, "post_edit_inspection": actor_property_after,
                    "stale_preview_rejected": stale_actor_result,
                    "level_saved_by_property_edit": actor_edit_result["data"]["saved"]}
                report["native_actor_components"] = actor_components
                report["native_selected_actors"] = selected_actors
                report["native_actor_search"] = {
                    "combined_name_and_class_filter": actor_search,
                    "next_page": actor_search_next_page,
                    "missing_filter_rejected": actor_search_missing_filter}
                report["native_editor_log"] = editor_log
                report["native_component_properties"] = component_properties
                report["native_component_property_edit"] = {
                    "preview": current_component_edit, "apply": component_edit_apply,
                    "stale_preview_rejected": stale_component_apply,
                    "post_edit_inspection": component_properties_after,
                    "bitfield_boolean_inspection": bitfield_bool,
                    "bitfield_boolean_edit_preview": bool_edit_preview,
                    "bitfield_boolean_edit_apply": bool_edit_apply,
                    "bitfield_boolean_post_edit_inspection": bool_properties_after}
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
                # Opening an asset is intentionally last: the headless Editor may
                # persist a Slate toolkit layout during shutdown, which requires a
                # real desktop window and can fail after this operation has returned.
                opened_asset = await call("unreal_open_asset", {
                    "session_id": target.session_id, "asset_path": imported_asset_path})
                assert not opened_asset["ok"], opened_asset
                assert opened_asset["error"]["code"] == "interactive_editor_required", opened_asset
                report["content_browser_acceptance"]["opened_asset"] = opened_asset
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
