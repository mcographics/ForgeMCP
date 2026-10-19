"""Install and activate a ZIP in an isolated Blender user profile, without saving prefs."""

import argparse
import ast
import hashlib
import json
import os
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path

PROBE = """
import os, json, hashlib, sys
from pathlib import Path
import addon_utils
import bpy

root = Path(os.environ["FORGE_PACKAGE_TEST_ROOT"]).resolve()
addons = Path(bpy.utils.user_resource("SCRIPTS", path="addons", create=True)).resolve()
assert addons.is_relative_to(root), "Installation must use the isolated profile"
before = (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.data.filepath)
archive = os.environ["FORGE_PACKAGE_ARCHIVE"]
assert bpy.ops.preferences.addon_install(filepath=archive) == {"FINISHED"}
module = addon_utils.enable("majestic_forge", default_set=False)
assert module and Path(module.__file__).resolve().is_relative_to(root)
assert module.bl_info["name"] == "ForgeMCP"
assert module.bl_info["version"] == tuple(json.loads(os.environ["FORGE_PACKAGE_EXPECTED_VERSION"]))
assert module._logo_previews is not None and "logo" in module._logo_previews
# Background Blender has no UI icon allocation; verify lifecycle and packaged bytes here.
assert (Path(module.__file__).parent / "resources" / "logo.png").is_file()
assert "MIT License" in (Path(module.__file__).parent / "LICENSE.txt").read_text()
assert module.MAJESTICFORGE_PT_Connection.is_registered
assert module.transfer_ui.MAJESTICFORGE_PT_Transfer.is_registered
assert module.transfer_ui.MAJESTICFORGE_OT_ExportToUnreal.is_registered
assert module.transfer_ui.MAJESTICFORGE_OT_ConfirmTransfer.is_registered
assert tuple(bpy.context.window_manager.forge_transfer.location) == (0.0, 0.0, 0.0)
assert bpy.context.window_manager.forge_transfer.asset_path == "/Game/Content/Returns/"
assert not module.transfer_ui.busy()
assert module._bridge is not None
from majestic_forge import skinning
assert Path(skinning.__file__).resolve().is_relative_to(root)
def request(command, args=None, token=None):
    return module._bridge.reply(json.dumps({
        "protocol_version": 1, "request_id": "package-probe",
        "token": module._bridge.token if token is None else token,
        "command": command, "args": {} if args is None else args
    }).encode())
health = request("health")["data"]
assert health["transfer_contract_version"] == 1
assert health["version"] == os.environ["FORGE_PACKAGE_EXPECTED_RELEASE"]
assert "export_preview" in health["capabilities"]
assert "animation_info" in health["capabilities"]
assert "creative_apply" in health["capabilities"]
assert request("command_catalog", {"limit": 1})["data"]["total"] > 1000
assert request("command_schema", {"identifier": "mesh.primitive_uv_sphere_add"})["data"]["execution"] == "create_object"
assert request("rna_schema", {"name": "ShaderNodeBlackbody"})["data"]["node_creation_supported"]
assert request("export_preview", {"name": "Cube"}, token="incorrect")["error"]["code"] == "unauthorized"
assert request("export_preview", {"name": "Cube", "output_path": str(root / "forbidden.fbx")})["error"]["code"] == "invalid_arguments"
assert not (root / "forbidden.fbx").exists()
context_before = (bpy.context.view_layer.objects.active, tuple(bpy.context.selected_objects), bpy.context.mode)
plan = request("export_preview", {"name": "Cube"})["data"]
export_args = {"preview_id": plan["preview_id"], "confirmation": plan["preview_id"]}
exported = request("export_apply", export_args)
assert exported["ok"] and exported["data"]["status"] == "exported", exported
data = exported["data"]
artifact = root / "sessions" / "transfers" / data["source_session_id"] / data["transfer_id"] / "mesh.fbx"
assert artifact.stat().st_size == data["artifact_bytes"]
assert hashlib.sha256(artifact.read_bytes()).hexdigest() == data["artifact_sha256"]
assert data["world_vertices_truncated"] is False and len(data["source_world_vertices"]) == 8
assert request("export_apply", export_args)["error"]["code"] == "preview_not_found"
assert context_before == (bpy.context.view_layer.objects.active, tuple(bpy.context.selected_objects), bpy.context.mode)
stale = request("export_preview", {"name": "Cube"})["data"]
cube = bpy.data.objects["Cube"]
old_location = cube.location.copy()
cube.location.x += 0.25
rejected = request("export_apply", {"preview_id": stale["preview_id"], "confirmation": stale["preview_id"]})
assert rejected["error"]["code"] == "stale_preview", rejected
cube.location = old_location
bpy.context.view_layer.update()
assert not (root / "sessions" / "transfers" / data["source_session_id"] / stale["preview_id"]).exists()
uv_page = request("mesh_uv_info", {"name": "Cube", "loop_count": 2})
assert uv_page["ok"] and uv_page["data"]["loop_total"] > 0, uv_page
uv_layer = uv_page["data"]["layer"]
uv_before = uv_page["data"]["loops"][0]["uv"]
uv_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "set_uv_coordinates", "name": "Cube", "uv_layer": uv_layer,
    "uv_start": 0, "uv_values": [[uv_before[0] + 0.01, uv_before[1] + 0.01]]}]}})["data"]
uv_applied = request("scene_apply", {"preview_id": uv_preview["preview_id"],
    "confirmation": uv_preview["preview_id"]})
assert uv_applied["ok"], uv_applied
uv_after = request("mesh_uv_info", {"name": "Cube", "layer_name": uv_layer, "loop_count": 1})["data"]["loops"][0]["uv"]
assert all(abs(a-b-0.01) < 1e-6 for a,b in zip(uv_after, uv_before))
uv_restore = request("scene_preview", {"recipe": {"operations": [{
    "op": "set_uv_coordinates", "name": "Cube", "uv_layer": uv_layer,
    "uv_start": 0, "uv_values": [uv_before]}]}})["data"]
uv_restored = request("scene_apply", {"preview_id": uv_restore["preview_id"],
    "confirmation": uv_restore["preview_id"]})
assert uv_restored["ok"]
topology = request("scene_preview", {"recipe": {"operations": [
    {"op": "create_mesh", "name": "PackageGeometryProbe",
     "vertices": [[0,0,0],[1,0,0],[0,1,0]], "faces": [[0,1,2]]},
    {"op": "set_mesh_geometry", "name": "PackageGeometryProbe",
     "vertices": [[0,0,0],[2,0,0],[2,1,0],[0,1,0]], "faces": [[0,1,2],[0,2,3]]},
]}})["data"]
topology_applied = request("scene_apply", {"preview_id": topology["preview_id"],
    "confirmation": topology["preview_id"]})
assert topology_applied["ok"], topology_applied
topology_info = request("mesh_geometry_info", {"name": "PackageGeometryProbe", "vertex_count": 8,
    "face_count": 8})
assert topology_info["ok"] and topology_info["data"]["face_total"] == 2
assert [face["vertices"] for face in topology_info["data"]["faces"]] == [[0,1,2],[0,2,3]]
uv_create = request("scene_preview", {"recipe": {"operations": [
    {"op": "create_uv_layer", "name": "PackageGeometryProbe", "uv_layer": "ForgeUV",
     "uv_values": [[0,0],[1,0],[1,1],[0,0],[1,1],[0,1]]},
    {"op": "set_uv_coordinates", "name": "PackageGeometryProbe", "uv_layer": "ForgeUV",
     "uv_start": 0, "uv_values": [[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.1],[0.9,0.9],[0.1,0.9]]},
]}})["data"]
uv_create_apply = request("scene_apply", {"preview_id": uv_create["preview_id"],
    "confirmation": uv_create["preview_id"]})
assert uv_create_apply["ok"], uv_create_apply
uv_created_info = request("mesh_uv_info", {"name": "PackageGeometryProbe", "layer_name": "ForgeUV",
    "loop_count": 8})
assert uv_created_info["ok"] and uv_created_info["data"]["loop_total"] == 6
assert all(abs(a-b) < 1e-6 for a, b in zip(uv_created_info["data"]["loops"][0]["uv"], [0.1, 0.1]))
unwrap = request("scene_preview", {"recipe": {"operations": [{
    "op": "smart_uv_project", "name": "PackageGeometryProbe", "uv_layer": "ForgeUV",
    "uv_angle_limit": 1.15, "uv_island_margin": 0.025,
}]}})["data"]
unwrap_result = request("scene_apply", {"preview_id": unwrap["preview_id"],
    "confirmation": unwrap["preview_id"]})
assert unwrap_result["ok"] and unwrap_result["data"]["operations"][0]["native_uv_projection_verified"]
unwrap_info = request("mesh_uv_info", {"name": "PackageGeometryProbe", "layer_name": "ForgeUV",
    "loop_count": 8})
assert unwrap_info["ok"] and unwrap_info["data"]["loop_total"] == 6
assert all(0 <= axis <= 1 for item in unwrap_info["data"]["loops"] for axis in item["uv"])
edge_page = request("mesh_edge_info", {"name": "PackageGeometryProbe", "edge_start": 0, "edge_count": 8})
assert edge_page["ok"] and edge_page["data"]["edge_total"] == 5
edge_index = edge_page["data"]["edges"][0]["index"]
seam_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "set_mesh_edge_seams", "name": "PackageGeometryProbe",
    "edge_seams": [{"index": edge_index, "seam": True}],
}]}})["data"]
seam_apply = request("scene_apply", {"preview_id": seam_preview["preview_id"],
    "confirmation": seam_preview["preview_id"]})
assert seam_apply["ok"] and seam_apply["data"]["operations"][0]["native_seams_verified"]
edge_after = request("mesh_edge_info", {"name": "PackageGeometryProbe", "edge_start": edge_index, "edge_count": 1})
assert edge_after["ok"] and edge_after["data"]["edges"][0]["seam"] is True
cube_edges = request("mesh_edge_info", {"name": "Cube", "edge_start": 0, "edge_count": 32})
cube_seams = request("scene_preview", {"recipe": {"operations": [{
    "op": "set_mesh_edge_seams", "name": "Cube",
    "edge_seams": [{"index": item["index"], "seam": True} for item in cube_edges["data"]["edges"]],
}]}})["data"]
cube_seams_apply = request("scene_apply", {"preview_id": cube_seams["preview_id"],
    "confirmation": cube_seams["preview_id"]})
assert cube_seams_apply["ok"]
seam_unwrap = request("scene_preview", {"recipe": {"operations": [{
    "op": "unwrap_uv", "name": "Cube", "uv_layer": "UVMap",
    "uv_unwrap_method": "ANGLE_BASED", "uv_margin": 0.001,
}]}})["data"]
seam_unwrap_apply = request("scene_apply", {"preview_id": seam_unwrap["preview_id"],
    "confirmation": seam_unwrap["preview_id"]})
assert seam_unwrap_apply["ok"] and seam_unwrap_apply["data"]["operations"][0]["native_seam_unwrap_verified"]
seam_unwrap_info = request("mesh_uv_info", {"name": "Cube", "layer_name": "UVMap", "loop_count": 32})
assert seam_unwrap_info["ok"] and seam_unwrap_info["data"]["loop_total"] == 24
assert all(-1e-6 <= axis <= 1.000001 for item in seam_unwrap_info["data"]["loops"] for axis in item["uv"])
pack_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "pack_uv_islands", "name": "Cube", "uv_layer": "UVMap", "uv_margin": 0.002,
}]}})["data"]
pack_apply = request("scene_apply", {"preview_id": pack_preview["preview_id"],
    "confirmation": pack_preview["preview_id"]})
assert pack_apply["ok"] and pack_apply["data"]["operations"][0]["native_uv_packing_verified"]
packed_uv_info = request("mesh_uv_info", {"name": "Cube", "layer_name": "UVMap", "loop_count": 32})
assert packed_uv_info["ok"] and packed_uv_info["data"]["loop_total"] == 24
assert all(-1e-6 <= axis <= 1.000001 for item in packed_uv_info["data"]["loops"] for axis in item["uv"])
animation_preview = request("scene_preview", {"recipe": {"operations": [
    {"op": "keyframe", "name": "PackageGeometryProbe", "data_path": "location", "frame": 3, "value": [0, 0, 0]},
    {"op": "keyframe", "name": "PackageGeometryProbe", "data_path": "location", "frame": 7, "value": [1, 0, 0]},
]}})["data"]
animation_apply = request("scene_apply", {"preview_id": animation_preview["preview_id"],
    "confirmation": animation_preview["preview_id"]})
assert animation_apply["ok"]
animation = request("animation_info", {"name": "PackageGeometryProbe", "curve_count": 3, "keyframe_count": 8})
assert animation["ok"] and animation["data"]["curve_total"] == 3, animation
assert all(len(curve["keyframes"]) == 2 for curve in animation["data"]["curves"])
before_edit_action = animation["data"]["action"]
edit_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "set_keyframe", "name": "PackageGeometryProbe", "curve_index": 0,
    "keyframe_index": 0, "key_frame": 4.0, "key_value": 2.5,
}]}})
assert edit_preview["ok"], edit_preview
edited = request("scene_apply", {"preview_id": edit_preview["data"]["preview_id"],
    "confirmation": edit_preview["data"]["preview_id"]})
assert edited["ok"] and edited["data"]["operations"][0]["native_keyframe_verified"], edited
animation_after_edit = request("animation_info", {"name": "PackageGeometryProbe",
    "curve_count": 3, "keyframe_count": 8})
assert animation_after_edit["ok"]
assert animation_after_edit["data"]["action"] != before_edit_action
assert [(key["frame"], key["value"]) for key in animation_after_edit["data"]["curves"][0]["keyframes"]] == [
    (4.0, 2.5), (7.0, 1.0)]
animation_page = request("animation_info", {"name": "PackageGeometryProbe", "curve_start": 1,
    "curve_count": 1, "keyframe_start": 1, "keyframe_count": 1})
assert animation_page["ok"] and animation_page["data"]["curves"][0]["keyframes"][0]["frame"] == 7.0
print("FORGEMCP_INSTALLED_ZIP_LAYERED_ACTION_EDIT_INSPECTION_AND_PAGINATION_PASS")
print("FORGEMCP_INSTALLED_ZIP_UV_PROJECT_SEAMS_AND_SEAM_AWARE_UNWRAP_PASS")
package_geometry = bpy.data.objects["PackageGeometryProbe"]
package_mesh = package_geometry.data
bpy.data.objects.remove(package_geometry, do_unlink=True)
if package_mesh.users == 0:
    bpy.data.meshes.remove(package_mesh)
print("FORGEMCP_INSTALLED_ZIP_MESH_TOPOLOGY_UV_PREVIEW_APPLY_INSPECTION_PASS")
material = bpy.data.materials.new("GraphEditProbe")
material.use_nodes = True
surface = material.node_tree.nodes.get("Principled BSDF")
assert surface is not None
before_graph = request("material_info", {"name": material.name})["data"]
graph_recipe = {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_nodes": [{"id": "ForgeRoughness", "type": "ShaderNodeValue",
                      "outputs": {"Value": 0.35}},
                     {"id": "ForgeMath", "type": "ShaderNodeMath"}],
    "shader_links": [{"from_node": "ForgeRoughness", "from_socket": "Value",
                       "to_node": surface.name, "to_socket": "Roughness"}],
}]}
graph_preview = request("scene_preview", {"recipe": graph_recipe})
assert graph_preview["ok"], graph_preview
graph_apply = request("scene_apply", {"preview_id": graph_preview["data"]["preview_id"],
    "confirmation": graph_preview["data"]["preview_id"]})
assert graph_apply["ok"] and graph_apply["data"]["state"] == "completed", graph_apply
after_graph = request("material_info", {"name": material.name})["data"]
assert len(after_graph["nodes"]) == len(before_graph["nodes"]) + 2
assert len(after_graph["links"]) == len(before_graph["links"]) + 1
assert any(link["from_node"] == "ForgeRoughness" and link["to_node"] == surface.name
           and link["to_socket"] == "Roughness" for link in after_graph["links"])
assert graph_apply["data"]["operations"][0]["native_graph_verified"]
print("FORGEMCP_INSTALLED_ZIP_EXISTING_MATERIAL_GRAPH_ADDITIVE_EDIT_PASS")

node_edit_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_node_edits": [
        {"id": surface.name, "x": 320, "y": -180,
         "inputs": {"Base Color": [0.2, 0.4, 0.6, 1.0]}},
        {"id": "ForgeMath", "operation": "SUBTRACT", "x": 640, "y": 40},
    ],
}]}})
assert node_edit_preview["ok"], node_edit_preview
node_edit_preview_data = node_edit_preview["data"]
node_edit_apply = request("scene_apply", {"preview_id": node_edit_preview_data["preview_id"],
    "confirmation": node_edit_preview_data["preview_id"]})
assert node_edit_apply["ok"] and node_edit_apply["data"]["operations"][0]["native_graph_verified"], node_edit_apply
edited_graph = request("material_info", {"name": material.name})["data"]
edited_by_id = {node["id"]: node for node in edited_graph["nodes"]}
assert edited_by_id[surface.name]["location"] == [320.0, -180.0], edited_by_id[surface.name]
base_color = next(pin["default"] for pin in edited_by_id[surface.name]["inputs"]
                  if pin["name"] == "Base Color")
assert all(abs(actual - expected) <= 1e-6
           for actual, expected in zip(base_color, [0.2, 0.4, 0.6, 1.0])), edited_by_id[surface.name]
assert edited_by_id["ForgeMath"]["operation"] == "SUBTRACT", edited_by_id["ForgeMath"]
assert edited_by_id["ForgeMath"]["location"] == [640.0, 40.0], edited_by_id["ForgeMath"]
print("FORGEMCP_INSTALLED_ZIP_EXISTING_MATERIAL_NODE_DEFAULT_POSITION_AND_OPERATION_EDIT_PASS")

linked_default = request("scene_preview", {"recipe": {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_node_edits": [{"id": surface.name, "inputs": {"Roughness": 0.4}}],
}]}})
assert linked_default["error"]["code"] == "invalid_arguments", linked_default

stale_recipe = {"operations": [{"op": "edit_material_graph", "name": material.name,
    "shader_nodes": [{"id": "StaleNode", "type": "ShaderNodeValue"}]}]}
stale_preview_result = request("scene_preview", {"recipe": stale_recipe})
assert stale_preview_result["ok"], stale_preview_result
stale_preview = stale_preview_result["data"]
intervening = request("scene_preview", {"recipe": {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_nodes": [{"id": "InterveningNode", "type": "ShaderNodeValue"}]}]}})["data"]
intervening_apply = request("scene_apply", {"preview_id": intervening["preview_id"],
    "confirmation": intervening["preview_id"]})
assert intervening_apply["ok"], intervening_apply
stale_apply = request("scene_apply", {"preview_id": stale_preview["preview_id"],
    "confirmation": stale_preview["preview_id"]})
assert stale_apply["error"]["code"] == "stale_preview", stale_apply
linked_input_edit = request("scene_preview", {"recipe": {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_nodes": [{"id": "Replacement", "type": "ShaderNodeValue"}],
    "shader_links": [{"from_node": "Replacement", "from_socket": "Value",
        "to_node": surface.name, "to_socket": "Roughness"}]}]}})
assert linked_input_edit["error"]["code"] == "invalid_arguments", linked_input_edit

from majestic_forge import automation
original_graph_edit = automation.add_existing_graph_nodes
def fail_after_graph_edit(*args):
    original_graph_edit(*args)
    raise RuntimeError("injected graph-edit failure")
automation.add_existing_graph_nodes = fail_after_graph_edit
rollback_before = request("material_info", {"name": material.name})["data"]
rollback_preview = request("scene_preview", {"recipe": {"operations": [{
    "op": "edit_material_graph", "name": material.name,
    "shader_nodes": [{"id": "RollbackNode", "type": "ShaderNodeValue"}],
    "shader_node_edits": [{"id": surface.name, "x": 999,
                            "inputs": {"Base Color": [0.9, 0.8, 0.7, 1.0]}},
                           {"id": "ForgeMath", "operation": "ADD", "x": 888}]}]}})["data"]
rollback_apply = request("scene_apply", {"preview_id": rollback_preview["preview_id"],
    "confirmation": rollback_preview["preview_id"]})
automation.add_existing_graph_nodes = original_graph_edit
rollback_after = request("material_info", {"name": material.name})["data"]
assert rollback_apply["ok"] and rollback_apply["data"]["state"] == "rolled_back", rollback_apply
assert rollback_after == rollback_before, (rollback_before, rollback_after)
print("FORGEMCP_INSTALLED_ZIP_EXISTING_MATERIAL_GRAPH_STALE_AND_ROLLBACK_PASS")
assert bpy.ops.majestic_forge.stop_bridge() == {"FINISHED"}
assert module._bridge is None
assert bpy.ops.majestic_forge.start_bridge() == {"FINISHED"}
addon_utils.disable("majestic_forge")
assert module._bridge is None
assert module._logo_previews is None
# Reproduce an older cached materials module left behind by ZIP replacement.
cached_materials = sys.modules["majestic_forge.materials"]
del cached_materials.transfer_surface
sys.modules.pop("majestic_forge")
errors = []
updated = addon_utils.enable("majestic_forge", default_set=False, handle_error=errors.append)
assert updated is not None and not errors, errors
assert hasattr(sys.modules["majestic_forge.materials"], "transfer_surface")
assert updated._bridge is not None
assert updated.MAJESTICFORGE_PT_Connection.is_registered
assert updated._bridge.exporter.preview("Cube")["vertex_count"] == 8
addon_utils.disable("majestic_forge")
assert updated._bridge is None
assert updated._logo_previews is None
print("FORGEMCP_CACHED_OLD_MATERIALS_UPDATE_PASS")
assert before == (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.data.filepath)
print("FORGEMCP_CLEAN_ZIP_INSTALL_ENABLE_DISABLE_PASS")
print("FORGEMCP_INSTALLED_ZIP_NATIVE_EXPORT_AUTH_STALE_REPLAY_PASS")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    blender = args.blender.resolve(strict=True)
    archive = args.archive.resolve(strict=True)
    with zipfile.ZipFile(archive) as package:
        tree = ast.parse(package.read("majestic_forge/__init__.py"))
    metadata = next(ast.literal_eval(item.value) for item in tree.body
                    if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "bl_info" for target in item.targets))
    repository = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="forgemcp-clean-blender-install-") as temp:
        root = Path(temp)
        for name in ("scripts", "config", "sessions"):
            (root / name).mkdir()
        script = root / "verify_install.py"
        script.write_text(PROBE, encoding="utf-8")
        env = {
            **os.environ,
            "BLENDER_USER_SCRIPTS": str(root / "scripts"),
            "BLENDER_USER_CONFIG": str(root / "config"),
            "FORGE_BLENDER_SESSION_DIR": str(root / "sessions"),
            "FORGE_PACKAGE_TEST_ROOT": str(root),
            "FORGE_PACKAGE_ARCHIVE": str(archive),
            "FORGE_PACKAGE_EXPECTED_VERSION": json.dumps(metadata["version"]),
            "FORGE_PACKAGE_EXPECTED_RELEASE": next(
                ast.literal_eval(item.value) for item in tree.body
                if isinstance(item, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "ADDON_VERSION" for target in item.targets
                )
            ),
        }
        result = subprocess.run(
            [
                str(blender),
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        print(result.stderr)
        evidence = repository / "Saved" / ("BlenderPackageAcceptance-" + uuid.uuid4().hex)
        evidence.mkdir(parents=True, exist_ok=False)
        (evidence / "acceptance.json").write_text(json.dumps({
            "archive": str(archive),
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "blender_executable": str(blender),
            "returncode": result.returncode,
            "pass_markers": [line for line in result.stdout.splitlines()
                             if line.startswith("FORGEMCP_")],
            "stdout": result.stdout,
            "stderr": result.stderr,
        }, indent=2) + "\n", encoding="utf-8")
        print(f"Acceptance evidence: {evidence}")
        if (
            result.returncode
            or "FORGEMCP_CLEAN_ZIP_INSTALL_ENABLE_DISABLE_PASS" not in result.stdout
        ):
            raise SystemExit("Clean-profile Blender installation validation failed")


if __name__ == "__main__":
    main()
