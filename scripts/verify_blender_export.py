"""Disposable native FBX export and reimport verification; never run in a user scene."""

import json
import os
import sys
import tempfile
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge import Bridge
from majestic_forge.automation import RecipeError
from majestic_forge.exporting import StaticMeshExporter


def reject(code, callback):
    try:
        callback()
    except RecipeError as error:
        assert error.code == code, (code, error.code)
    else:
        raise AssertionError(f"Expected rejection {code}")


cube = bpy.data.objects["Cube"]
bpy.context.scene.unit_settings.system = "NONE"
bpy.context.scene.unit_settings.scale_length = 1.0
# An asymmetric fixture makes swapped axes and selection mistakes observable.
for vertex in cube.data.vertices:
    vertex.co.x *= 2
    vertex.co.y *= 3
cube.data.vertices[0].co.x += 0.35
cube.data.vertices[0].co.z += 0.2
expected_vertices = sorted(
    tuple(round(c, 4) for c in cube.matrix_world @ v.co) for v in cube.data.vertices
)
material = bpy.data.materials.new("ForgeExportMaterial")
cube.data.materials.clear()
cube.data.materials.append(material)
bpy.ops.object.select_all(action="DESELECT")
bpy.data.objects["Camera"].select_set(True)
bpy.context.view_layer.objects.active = bpy.data.objects["Camera"]
before = (
    [o.name for o in bpy.context.selected_objects],
    bpy.context.view_layer.objects.active.name,
    len(bpy.data.objects),
    bpy.data.filepath,
)

with tempfile.TemporaryDirectory(prefix="forgemcp-export-validation-") as temp:
    exporter = StaticMeshExporter(Path(temp) / "transfers")
    plan = exporter.preview("Cube")
    assert not exporter.staging_root.exists(), "Preview must not write staging files"
    reject("confirmation_required", lambda: exporter.apply(plan["preview_id"], "wrong"))
    cube.data.vertices[0].co.x += 0.25
    reject("stale_preview", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    cube.data.vertices[0].co.x -= 0.25
    plan = exporter.preview("Cube")
    uv = cube.data.uv_layers.active.data[0].uv
    original_uv = uv.x
    uv.x += 0.1
    reject("stale_preview", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    uv.x = original_uv
    plan = exporter.preview("Cube")
    material.diffuse_color[0] += 0.1
    reject("stale_preview", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    material.diffuse_color[0] -= 0.1
    plan = exporter.preview("Cube")
    bpy.context.scene.unit_settings.system = "METRIC"
    reject("stale_preview", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    bpy.context.scene.unit_settings.system = "NONE"
    modifier = cube.modifiers.new("ExportMustRejectModifier", "BEVEL")
    reject("unsupported_source", lambda: exporter.preview("Cube"))
    cube.modifiers.remove(modifier)
    plan = exporter.preview("Cube")
    exporter.previews[plan["preview_id"]]["expires"] = 0
    reject("preview_not_found", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    plan = exporter.preview("Cube")
    exported = exporter.apply(plan["preview_id"], plan["preview_id"])
    assert exported["status"] == "exported" and exported["saved_scene"] is False
    reject("preview_not_found", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))

    # Exercise authentication and strict arguments through the native bridge route.
    previous = os.environ.get("FORGE_BLENDER_SESSION_DIR")
    os.environ["FORGE_BLENDER_SESSION_DIR"] = str(Path(temp) / "sessions")
    bridge = Bridge()
    try:

        def request(command, args, token=None):
            return bridge.reply(
                json.dumps(
                    {
                        "protocol_version": 1,
                        "request_id": "export-test",
                        "token": token or bridge.token,
                        "command": command,
                        "args": args,
                    }
                ).encode()
            )

        assert (
            request("export_preview", {"name": "Cube"}, "wrong")["error"]["code"] == "unauthorized"
        )
        assert (
            request("export_preview", {"name": "Cube", "filepath": "arbitrary"})["error"]["code"]
            == "invalid_arguments"
        )
        preview = request("export_preview", {"name": "Cube"})["data"]
        result = request(
            "export_apply",
            {"preview_id": preview["preview_id"], "confirmation": preview["preview_id"]},
        )
        assert result["ok"] and result["data"]["status"] == "exported", result
    finally:
        bridge.close()
        if previous is None:
            os.environ.pop("FORGE_BLENDER_SESSION_DIR", None)
        else:
            os.environ["FORGE_BLENDER_SESSION_DIR"] = previous
    assert before == (
        [o.name for o in bpy.context.selected_objects],
        bpy.context.view_layer.objects.active.name,
        len(bpy.data.objects),
        bpy.data.filepath,
    )
    path = exporter.staging_root / exported["transfer_id"] / exported["artifact_name"]
    assert (
        json.loads((path.parent / "export-report.json").read_text())["artifact_sha256"]
        == exported["artifact_sha256"]
    )
    objects_before = set(bpy.data.objects)
    assert bpy.ops.import_scene.fbx(filepath=str(path)) == {"FINISHED"}
    imported = list(set(bpy.data.objects) - objects_before)
    assert len(imported) == 1 and imported[0].type == "MESH", "Only the reviewed mesh may export"
    mesh = imported[0]
    assert len(mesh.data.vertices) == exported["vertex_count"]
    # Blender adds .001 when importing a material whose name already exists.
    assert [s.material.name for s in mesh.material_slots] == ["ForgeExportMaterial.001"]
    bounds = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    assert sorted(tuple(round(c, 4) for c in v) for v in bounds) == expected_vertices
    extents = [max(v[i] for v in bounds) - min(v[i] for v in bounds) for i in range(3)]
    expected_extents = [
        max(v[i] for v in expected_vertices) - min(v[i] for v in expected_vertices)
        for i in range(3)
    ]
    assert all(abs(a - b) < 1e-4 for a, b in zip(extents, expected_extents)), extents
    # Procedural recipes may have no UV layer. Export must supply valid UVs
    # without altering the source mesh, selection, or retained objects.
    for layer in list(cube.data.uv_layers):
        cube.data.uv_layers.remove(layer)
    source_mesh = cube.data
    object_count, mesh_count = len(bpy.data.objects), len(bpy.data.meshes)
    plan = exporter.preview("Cube")
    assert plan["export_settings"]["generates_uvs"] is True
    uv_export = exporter.apply(plan["preview_id"], plan["preview_id"])
    assert cube.data == source_mesh and not cube.data.uv_layers
    assert (len(bpy.data.objects), len(bpy.data.meshes)) == (object_count, mesh_count)
    before_import = set(bpy.data.objects)
    uv_path = exporter.staging_root / uv_export["transfer_id"] / "mesh.fbx"
    assert bpy.ops.import_scene.fbx(filepath=str(uv_path)) == {"FINISHED"}
    uv_mesh = next(iter(set(bpy.data.objects) - before_import)).data
    assert uv_mesh.uv_layers.active is not None
    uv_mesh.calc_tangents()
    assert all(loop.tangent.length > 0.99 and loop.bitangent.length > 0.99 for loop in uv_mesh.loops)
    # Failure inside the native exporter must also remove temporary datablocks.
    from unittest.mock import patch
    with patch.object(StaticMeshExporter, "_export_object", side_effect=RuntimeError("fixture export failure")):
        object_count, mesh_count = len(bpy.data.objects), len(bpy.data.meshes)
        try:
            StaticMeshExporter._write_fbx(cube, Path(temp) / "failure.fbx")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected native exporter failure")
        assert (len(bpy.data.objects), len(bpy.data.meshes)) == (object_count, mesh_count)
        assert cube.data == source_mesh and not cube.data.uv_layers
    plan = exporter.preview("Cube")
    exporter._write_fbx = lambda *_: {"CANCELLED"}
    reject("export_failed", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))
    record = exporter.staging_root / plan["preview_id"] / "export-report.json"
    assert json.loads(record.read_text())["status"] == "export_failed"
    reject("preview_not_found", lambda: exporter.apply(plan["preview_id"], plan["preview_id"]))

print("FORGEMCP_NATIVE_EXPORT_PREVIEW_STALE_REPLAY_CONTEXT_REIMPORT_FAILURE_REPORT_PASS")
