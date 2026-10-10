"""Native staged-FBX import acceptance in a disposable compiled Unreal host.

This starts and closes its own factory Blender and unattended Unreal processes.
It never discovers or mutates the user's existing application sessions.
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
from server.core.transfer import (
    FBX_BINARY_HEADER,
    StaticMeshTransferManifest,
    stage_unreal_artifact,
)

BLENDER_PROBE = '''
import json, os, sys
from pathlib import Path
import bpy
sys.path.insert(0, os.environ["FORGE_IMPORT_ADDON_ROOT"])
from majestic_forge.exporting import StaticMeshExporter
root = Path(os.environ["FORGE_IMPORT_FIXTURE_ROOT"])
cube = bpy.data.objects["Cube"]
bpy.context.scene.unit_settings.system = "NONE"
bpy.context.scene.unit_settings.scale_length = 1.0
for vertex in cube.data.vertices:
    vertex.co.x *= 2
    vertex.co.y *= 3
cube.data.vertices[0].co.x += 0.35
cube.data.vertices[0].co.z += 0.2
material = bpy.data.materials.new("ForgeTransferMaterial")
material.use_nodes = True
shader = material.node_tree.nodes.get("Principled BSDF")
shader.inputs["Base Color"].default_value = (0.12, 0.34, 0.56, 1)
shader.inputs["Roughness"].default_value = 0.27
shader.inputs["Metallic"].default_value = 0.63
cube.data.materials.clear()
cube.data.materials.append(material)
exporter = StaticMeshExporter(root / "exports")
preview = exporter.preview("Cube")
report = exporter.apply(preview["preview_id"], preview["preview_id"])
fixture = {"export": report, "vertices": [list(v.co) for v in cube.data.vertices],
           "blender_version": bpy.app.version_string}
(root / "fixture.json").write_text(json.dumps(fixture), encoding="utf-8")
print("FORGEMCP_TRANSFER_NATIVE_BLENDER_FIXTURE_EXPORTED")
'''


def hidden_process_options():
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startup}


async def rejection(manager, session, code, command, args):
    try:
        await manager.request(session, command, args)
    except BridgeError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError(f"Expected native rejection {code}")


async def place_via_mcp(repository, project, session, manager, before, recipe):
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(repository),
        env={**os.environ, "FORGE_PROJECT_ROOT": str(project.parent),
             "FORGE_BLENDER_SESSION_DIR": str(project.parent / "Saved" / "NoBlenderSessions")},
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            initialized = await client.initialize()
            assert initialized.serverInfo.name == "ForgeMCP"
            preview = await client.call_tool("unreal_preview_actors", {
                "session_id": session.session_id, "recipe": recipe,
            })
            assert not preview.isError and preview.structuredContent["ok"], preview
            plan = preview.structuredContent["data"]
            assert (await manager.request(session, "list_actors", {"limit": 200})) == before
            arguments = {
                "preview_id": plan["preview_id"], "confirmation": plan["preview_id"],
                "session_id": session.session_id,
            }
            applied = await client.call_tool("unreal_apply_actors", arguments)
            assert not applied.isError and applied.structuredContent["ok"], applied
            placement = applied.structuredContent["data"]
            assert placement["state"] == "completed" and len(placement["actors"]) == 1, placement
            inspected = await client.call_tool("unreal_inspect_actor", {
                "session_id": session.session_id, "actor_path": placement["actors"][0]["path"],
            })
            assert not inspected.isError and inspected.structuredContent["ok"], inspected
            assert inspected.structuredContent["data"]["actor"] == placement["actors"][0]
            replay = await client.call_tool("unreal_apply_actors", arguments)
            assert replay.structuredContent["error"]["code"] == "preview_not_found"
            return plan, placement


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if (
        not relative.parts[0].startswith("TransferImportValidation-")
        or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject")
    ):
        raise ValueError("Only a generated disposable TransferImportValidation host is allowed")
    root = project.parent / "Saved" / ("MeshImportAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    probe = root / "blender-probe.py"
    probe.write_text(BLENDER_PROBE, encoding="utf-8")
    env = {
        **os.environ,
        "FORGE_IMPORT_ADDON_ROOT": str(repository / "blender-addon"),
        "FORGE_IMPORT_FIXTURE_ROOT": str(root),
    }
    with (root / "blender.log").open("w", encoding="utf-8") as log:
        native = subprocess.Popen(
            [str(args.blender), "--background", "--factory-startup", "--python-exit-code", "1",
             "--python", str(probe)],
            cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
            **hidden_process_options(),
        )
        deadline = time.monotonic() + 120
        while native.poll() is None:
            if time.monotonic() > deadline:
                native.terminate()
                native.wait(timeout=20)
                raise RuntimeError(f"Factory Blender fixture timed out; inspect {root}")
            await asyncio.sleep(0.2)
        if native.returncode:
            raise RuntimeError(f"Factory Blender export failed; inspect {root}")
    fixture = json.loads((root / "fixture.json").read_text(encoding="utf-8"))
    export = fixture["export"]
    manager = ConnectionManager([project.parent / "Saved" / "MajesticForge"], timeout=15)
    with (root / "unreal-launch.log").open("w", encoding="utf-8") as log:
        editor = subprocess.Popen(
            [str(args.editor), str(project), "-Unattended", "-NullRHI", "-NoSound", "-NoSplash",
             "-NoLiveCoding", "-NoSourceControl", f"-abslog={root / 'unreal.log'}"],
            cwd=project.parent, stdout=log, stderr=subprocess.STDOUT,
            **hidden_process_options(),
        )
        try:
            deadline = time.monotonic() + 180
            session = None
            while session is None:
                if editor.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"Disposable Unreal bridge did not become ready; inspect {root}")
                for candidate in manager.discover():
                    if candidate.pid != editor.pid:
                        continue
                    try:
                        info = await manager.request(candidate, "project_info")
                        assert Path(info["project_file"]).resolve() == project
                        health = await manager.request(candidate, "health")
                        assert "mesh_import_preview" in health["capabilities"]
                        session = candidate
                    except BridgeError:
                        pass
                if session is None:
                    await asyncio.sleep(0.2)
            before = await manager.request(session, "list_actors", {"limit": 200})
            values = {key: export[key] for key in (
                "transfer_id", "source_session_id", "source_object", "source_snapshot_sha256",
                "artifact_name", "artifact_sha256", "artifact_bytes", "meters_per_source_unit",
                "source_bounds_min", "source_bounds_max", "vertex_count", "triangle_count", "materials",
            )}
            values.update(
                target_session_id=session.session_id,
                target_project_file=str(project),
                target_asset_path="/Game/ForgeTransfer/SM_Fixture_" + uuid.uuid4().hex,
            )
            manifest = StaticMeshTransferManifest.model_validate(values)
            source = root / "exports" / manifest.transfer_id
            recipe = stage_unreal_artifact(source, manifest, save=True, transfer_materials=True)
            await rejection(manager, session, "import_rejected", "mesh_import_preview", {
                "recipe": {**recipe, "target_session_id": "unreal-1"},
            })
            await rejection(manager, session, "import_rejected", "mesh_import_preview", {
                "recipe": {**recipe, "script": "unsupported"},
            })
            invalid_definition = {**recipe["material_definitions"][0], "asset_path": "/Game/Unapproved/Material"}
            await rejection(manager, session, "import_rejected", "mesh_import_preview", {
                "recipe": {**recipe, "material_definitions": [invalid_definition]},
            })
            preview = await manager.request(session, "mesh_import_preview", {"recipe": recipe})
            package_file = project.parent / "Content" / (manifest.target_asset_path[6:] + ".uasset")
            assert not package_file.exists(), "Preview must not create an Unreal asset"
            await rejection(manager, session, "confirmation_required", "mesh_import_apply", {
                "preview_id": preview["preview_id"], "confirmation": "wrong",
            })
            result = await manager.request(session, "mesh_import_apply", {
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"],
            })
            (root / "native-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            assert result["state"] == "imported", result
            assert result["saved"] is True
            assert package_file.is_file()
            assert result["class_path"] == "/Script/Engine.StaticMesh"
            assert result["asset_path"] == (
                manifest.target_asset_path + "." + manifest.target_asset_path.rsplit("/", 1)[1]
            )
            assert isinstance(result["native_diagnostics"], list)
            assert not any("smoothing group" in item["message"].lower()
                           for item in result["native_diagnostics"])
            assert result["vertex_count"] == export["vertex_count"]
            assert result["triangle_count"] == export["triangle_count"]
            assert result["vertices_truncated"] is False
            assert [slot["imported_slot_name"] for slot in result["material_slots"]] == [
                slot["name"] for slot in export["materials"]
            ]
            assert result["material_assets_imported"] is True
            assert result["material_assets_saved"] is True
            assert len(result["materials"]) == len(export["materials"])
            for source_slot, native_material in zip(export["materials"], result["materials"]):
                surface = source_slot["surface"]
                assert surface["model"] == "pbr_constants"
                assert native_material["native_graph_verified"] is True
                assert native_material["shader_compile_verified"] is False
                assert native_material["saved"] is True
                assert native_material["color_space"] == "scene_linear"
                assert native_material["two_sided"] == surface["two_sided"]
                assert all(abs(a - b) < 1e-6 for a, b in zip(surface["base_color"], native_material["base_color"]))
                assert abs(surface["roughness"] - native_material["roughness"]) < 1e-6
                assert abs(surface["metallic"] - native_material["metallic"]) < 1e-6
                package = recipe["material_definitions"][source_slot["index"]]["asset_path"]
                assert native_material["asset_path"] == package + "." + package.rsplit("/", 1)[1]
                assert (project.parent / "Content" / (package[6:] + ".uasset")).is_file()
            # A new mesh destination must not permit reuse of existing material packages.
            material_file = project.parent / "Content" / (recipe["material_definitions"][0]["asset_path"][6:] + ".uasset")
            material_checksum = hashlib.sha256(material_file.read_bytes()).hexdigest()
            overwrite_recipe = {**recipe, "asset_path": "/Game/ForgeTransfer/SM_Overwrite_" + uuid.uuid4().hex}
            await rejection(manager, session, "import_rejected", "mesh_import_preview", {"recipe": overwrite_recipe})
            assert hashlib.sha256(material_file.read_bytes()).hexdigest() == material_checksum
            assert result["placed"] is False
            await rejection(manager, session, "preview_not_found", "mesh_import_apply", {
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"],
            })
            await rejection(manager, session, "import_rejected", "mesh_import_preview", {"recipe": recipe})
            after = await manager.request(session, "list_actors", {"limit": 200})
            assert before == after, "Import must not place or edit actors"
            record = project.parent / "Saved" / "ForgeTransfers" / manifest.transfer_id / "import-report.json"
            assert json.loads(record.read_text(encoding="utf-8"))["state"] == "imported"
            # Check explicit coordinate conversion against signed, asymmetric vertices.
            # FBX -Y forward / Z up plus Unreal's forced +X front and Y-handedness flip:
            # (x, y, z) in Blender maps to (-y, -x, z) in Unreal centimeters.
            expected = sorted((round(-y * 100, 3), round(-x * 100, 3), round(z * 100, 3))
                              for x, y, z in fixture["vertices"])
            actual = sorted(tuple(round(v, 3) for v in p) for p in result["vertex_positions_cm"])
            assert actual == expected, {"expected_vertices_cm": expected, "actual_vertices_cm": actual}
            for index, field in enumerate(("bounds_min_cm", "bounds_max_cm")):
                bound = tuple((min if index == 0 else max)(p[axis] for p in expected) for axis in range(3))
                assert tuple(round(v, 3) for v in result[field]) == bound

            # A checksum change after preview must reject apply before native mutation.
            stale = manifest.model_copy(update={
                "transfer_id": uuid.uuid4().hex,
                "target_asset_path": "/Game/ForgeTransfer/SM_Stale_" + uuid.uuid4().hex,
            })
            stale_recipe = stage_unreal_artifact(source, stale)
            stale_plan = await manager.request(session, "mesh_import_preview", {"recipe": stale_recipe})
            stale_root = project.parent / "Saved" / "ForgeTransfers" / stale.transfer_id
            artifact = stale_root / "mesh.fbx"
            original = artifact.read_bytes()
            artifact.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
            await rejection(manager, session, "stale_preview", "mesh_import_apply", {
                "preview_id": stale_plan["preview_id"], "confirmation": stale_plan["preview_id"],
            })
            assert not (stale_root / "import-report.json").exists()

            # Header/hash integrity is insufficient: the native parser must reject invalid FBX.
            invalid_source = root / "invalid-fbx"
            invalid_source.mkdir()
            invalid_bytes = FBX_BINARY_HEADER + b"invalid native FBX contents"
            (invalid_source / "mesh.fbx").write_bytes(invalid_bytes)
            invalid = manifest.model_copy(update={
                "transfer_id": uuid.uuid4().hex,
                "target_asset_path": "/Game/ForgeTransfer/SM_Invalid_" + uuid.uuid4().hex,
                "artifact_bytes": len(invalid_bytes),
                "artifact_sha256": hashlib.sha256(invalid_bytes).hexdigest(),
            })
            invalid_recipe = stage_unreal_artifact(invalid_source, invalid, save=True)
            invalid_plan = await manager.request(session, "mesh_import_preview", {"recipe": invalid_recipe})
            invalid_result = await manager.request(session, "mesh_import_apply", {
                "preview_id": invalid_plan["preview_id"], "confirmation": invalid_plan["preview_id"],
            })
            assert invalid_result["state"] == "rolled_back", invalid_result
            assert invalid_result["saved"] is False
            assert any(item["severity"] == "error" for item in invalid_result["native_diagnostics"])
            invalid_record = project.parent / "Saved" / "ForgeTransfers" / invalid.transfer_id / "import-report.json"
            assert json.loads(invalid_record.read_text(encoding="utf-8"))["state"] == "rolled_back"
            assert not (project.parent / "Content" / (invalid.target_asset_path[6:] + ".uasset")).exists()
            assert (await manager.request(session, "list_actors", {"limit": 200})) == before

            # Placement uses the existing actor tools and a reviewed exact mesh reference.
            placement_recipe = {"operations": [{
                "op": "spawn", "class_path": "/Script/Engine.StaticMeshActor",
                "mesh_path": result["asset_path"], "label": "ForgePlacement_" + uuid.uuid4().hex,
                "location": [150, 250, 350], "rotation": [0, 90, 0], "scale": [1.5, 0.5, 2],
            }]}
            await rejection(manager, session, "invalid_arguments", "actor_preview", {"recipe": {
                "operations": [{"op": "spawn", "class_path": "/Script/Engine.PointLight",
                                "mesh_path": result["asset_path"]}],
            }})
            await rejection(manager, session, "asset_not_found", "actor_preview", {"recipe": {
                "operations": [{"op": "spawn", "class_path": "/Script/Engine.StaticMeshActor",
                                "mesh_path": "/Game/ForgeTransfer/Missing.Missing"}],
            }})
            placement_plan, placement = await place_via_mcp(
                repository, project, session, manager, before, placement_recipe
            )
            assert placement["state"] == "completed", placement
            assert placement["saved"] is False
            assert len(placement["actors"]) == 1
            actor = placement["actors"][0]
            assert actor["static_mesh"] == result["asset_path"]
            assert actor["class_path"] == "/Script/Engine.StaticMeshActor"
            assert actor["location"] == [150, 250, 350]
            assert all(abs(a - b) < 1e-4 for a, b in zip(actor["rotation"], [0, 90, 0]))
            assert actor["scale"] == [1.5, 0.5, 2]
            assert actor["material_assets_truncated"] is False
            assert len(actor["material_assets"]) == len(export["materials"])
            assert actor["material_assets"] == [item["asset_path"] for item in result["materials"]]
            center = [(a + b) / 2 for a, b in zip(result["bounds_min_cm"], result["bounds_max_cm"])]
            extent = [(b - a) / 2 for a, b in zip(result["bounds_min_cm"], result["bounds_max_cm"])]
            expected_origin = [150 - center[1] * 0.5, 250 + center[0] * 1.5, 350 + center[2] * 2]
            expected_extent = [extent[1] * 0.5, extent[0] * 1.5, extent[2] * 2]
            assert all(abs(a - b) < 1e-3 for a, b in zip(actor["bounds_origin"], expected_origin)), actor
            assert all(abs(a - b) < 1e-3 for a, b in zip(actor["bounds_extent"], expected_extent)), actor
            inspected = await manager.request(session, "actor_info", {"actor_path": actor["path"]})
            assert inspected["actor"] == actor
            await rejection(manager, session, "preview_not_found", "actor_apply", {
                "preview_id": placement_plan["preview_id"], "confirmation": placement_plan["preview_id"],
            })
            (root / "placement-result.json").write_text(json.dumps(placement, indent=2), encoding="utf-8")
            acceptance = {
                "status": "passed", "interactive": False,
                "blender_version": fixture["blender_version"], "engine_version": info["engine_version"],
                "project_file": str(project), "transfer_id": manifest.transfer_id,
                "artifact_sha256": manifest.artifact_sha256, "asset_path": result["asset_path"],
                "actor_path": actor["path"], "level_saved": False, "material_assets_transferred": True,
                "material_shader_compile_verified": False, "material_visual_equivalence_verified": False,
                "checks": ["signed_vertices", "units", "bounds", "material_slots", "asset_save",
                           "wrong_session", "replay", "stale_checksum", "invalid_fbx_rollback",
                           "placement_preview", "actor_transform", "actor_world_bounds", "mesh_reference",
                           "real_mcp_stdio_placement_inspection_replay", "constant_pbr_material_parameters",
                           "material_package_save", "actor_material_references", "material_overwrite_rejection"],
            }
            (root / "acceptance.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")
            print("FORGEMCP_NATIVE_IMPORT_PBR_MATERIALS_AND_REAL_MCP_PLACEMENT_REFERENCE_PASS")
            print(f"Acceptance records: {root}")
        finally:
            if editor.poll() is None:
                editor.terminate()
                try:
                    editor.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    editor.kill()
                    editor.wait(timeout=20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--blender", required=True, type=Path)
    parser.add_argument("--editor", required=True, type=Path)
    asyncio.run(verify(parser.parse_args()))
