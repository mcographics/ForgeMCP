"""Check native shader creation/links, rejection and batch rollback in factory Blender."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
import bpy
from majestic_forge import Bridge
from majestic_forge.automation import RecipeError, SceneAutomation
from majestic_forge.materials import material_info

automation = SceneAutomation()
graph = {
    "op": "create_material", "name": "ForgeProceduralMaterial", "color": [0.1, 0.2, 0.3, 1],
    "shader_nodes": [
        {"id": "noise", "type": "ShaderNodeTexNoise", "inputs": {"Scale": 3.0}},
        {"id": "surface", "type": "ShaderNodeBsdfPrincipled",
         "inputs": {"Roughness": 0.25, "Metallic": 0.5}, "x": 300},
        {"id": "output", "type": "ShaderNodeOutputMaterial", "x": 600},
    ],
    "shader_links": [
        {"from_node": "noise", "from_socket": "Color", "to_node": "surface", "to_socket": "Base Color"},
        {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "Surface"},
    ],
}
before = set(bpy.data.materials)
preview = automation.preview({"operations": [graph]})
assert set(bpy.data.materials) == before, "Preview mutated materials"
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "completed", result
info = material_info(graph["name"])
assert info["total_nodes"] == 3 and info["total_links"] == 2
assert all(link["valid"] for link in info["links"]), info
assert bpy.data.materials[graph["name"]].node_tree.nodes["surface"].inputs["Metallic"].default_value == 0.5
assert result["materials"][0]["name"] == graph["name"]
try:
    automation.apply(preview["preview_id"], preview["preview_id"])
    raise AssertionError("Consumed graph preview replayed")
except RecipeError as error:
    assert error.code == "preview_not_found"
for node_type in ("ShaderNodeScript", "GeometryNodeInputSceneTime", "execute_python"):
    try:
        automation.preview({"operations": [{**graph, "name": "ForgeRejected",
                           "shader_nodes": [{"id": "bad", "type": node_type}]}]})
        raise AssertionError("Nonallowlisted node accepted")
    except RecipeError as error:
        assert error.code == "invalid_arguments"
for bad_links in (
    [graph["shader_links"][0], graph["shader_links"][0]],
    [{"from_node": "noise", "from_socket": "Color", "to_node": "surface", "to_socket": "Base Color"},
     {"from_node": "surface", "from_socket": "BSDF", "to_node": "noise", "to_socket": "Vector"}],
):
    try:
        automation.preview({"operations": [{**graph, "name": "ForgeInvalidLinks",
                                             "shader_links": bad_links}]})
        raise AssertionError("Duplicate input or cyclic graph accepted")
    except RecipeError as error:
        assert error.code == "invalid_arguments"
# A valid shape with a nonexistent socket passes structural preflight but must
# roll back the material and preceding mesh when native socket resolution fails.
bad_graph = {**graph, "name": "ForgeBadSocket", "shader_links": [
    {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "NoSuchSocket"}
]}
before_materials, before_objects, before_meshes = (
    set(bpy.data.materials), set(bpy.data.objects), set(bpy.data.meshes)
)
preview = automation.preview({"operations": [
    {"op": "create_mesh", "name": "ForgeGraphRollback", "vertices": [[0, 0, 0]], "faces": []},
    bad_graph,
]})
result = automation.apply(preview["preview_id"], preview["preview_id"])
assert result["state"] == "rolled_back", result
assert set(bpy.data.materials) == before_materials
assert set(bpy.data.objects) == before_objects and set(bpy.data.meshes) == before_meshes
assert material_info(graph["name"]) == info
# Exercise the actual authenticated protocol parser, including vector socket
# defaults at the maximum supported depth. No registration/token is printed.
os.environ["FORGE_BLENDER_SESSION_DIR"] = str(
    Path(__file__).resolve().parents[1] / "Saved/Milestone2/MaterialParserSessions"
)
bridge = Bridge()
try:
    rgba_graph = {**graph, "name": "ForgeRGBASocketMaterial", "shader_nodes": [
        {"id": "surface", "type": "ShaderNodeBsdfPrincipled",
         "inputs": {"Base Color": [0.1, 0.2, 0.3, 1]}},
        {"id": "output", "type": "ShaderNodeOutputMaterial"},
    ], "shader_links": [
        {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "Surface"}
    ]}
    request = {"protocol_version": 1, "request_id": "material-parser-probe",
               "token": bridge.token, "command": "scene_preview",
               "args": {"recipe": {"operations": [rgba_graph]}}}
    response = bridge.reply(json.dumps(request).encode())
    assert response["ok"], response
    preview_id = response["data"]["preview_id"]
    request.update(command="scene_apply", args={"preview_id": preview_id, "confirmation": preview_id})
    response = bridge.reply(json.dumps(request).encode())
    assert response["ok"] and response["data"]["state"] == "completed", response
    color = bpy.data.materials[rgba_graph["name"]].node_tree.nodes["surface"].inputs["Base Color"].default_value
    assert all(abs(a - b) < 1e-6 for a, b in zip(color, [0.1, 0.2, 0.3, 1]))
    constants = {**rgba_graph, "name": "ForgeShaderConstants", "shader_nodes": [
        {"id": "color", "type": "ShaderNodeRGB", "outputs": {"Color": [0.8, 0.2, 0.1, 1]}},
        {"id": "amount", "type": "ShaderNodeValue", "outputs": {"Value": 0.4}},
        {"id": "surface", "type": "ShaderNodeBsdfPrincipled"},
        {"id": "output", "type": "ShaderNodeOutputMaterial"},
    ], "shader_links": [
        {"from_node": "color", "from_socket": "Color", "to_node": "surface", "to_socket": "Base Color"},
        {"from_node": "amount", "from_socket": "Value", "to_node": "surface", "to_socket": "Roughness"},
        {"from_node": "surface", "from_socket": "BSDF", "to_node": "output", "to_socket": "Surface"},
    ]}
    request.update(command="scene_preview", args={"recipe": {"operations": [constants]}})
    response = bridge.reply(json.dumps(request).encode())
    assert response["ok"], response
    preview_id = response["data"]["preview_id"]
    request.update(command="scene_apply", args={"preview_id": preview_id, "confirmation": preview_id})
    response = bridge.reply(json.dumps(request).encode())
    assert response["ok"] and response["data"]["state"] == "completed", response
    info = material_info(constants["name"])
    assert info["total_nodes"] == 4 and info["total_links"] == 3
    assert all(link["valid"] for link in info["links"])
    assert abs(bpy.data.materials[constants["name"]].node_tree.nodes["amount"].outputs[0].default_value - 0.4) < 1e-6
    response = bridge.reply(b"[" * 10 + b"0" + b"]" * 10)
    assert not response["ok"] and response["error"]["code"] == "invalid_request"
finally:
    bridge.close()
assert bpy.data.filepath == "", "Factory verification must not load/save user scenes"
print("FORGE_NATIVE_MATERIAL_GRAPH_LINK_DEFAULT_RGBA_PROTOCOL_REJECTION_REPLAY_BATCH_ROLLBACK_PASS")
