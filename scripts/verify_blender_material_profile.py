"""Factory-process acceptance of native Blender material transfer classification."""

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge.materials import transfer_surface

material = bpy.data.materials.new("ForgeProfileProbe")
material.use_nodes = False
material.diffuse_color = (0.12, 0.34, 0.56, 1)
material.roughness = 0.27
material.metallic = 0.63
surface = transfer_surface(material)
assert surface["model"] == "pbr_constants"
if material.use_nodes:
    # Blender 5.2 keeps node shading active despite the deprecated False setter.
    # Viewport metadata must not replace the active shader's values.
    active = material.node_tree.nodes.get("Principled BSDF")
    assert surface["roughness"] == active.inputs["Roughness"].default_value
    assert surface["metallic"] == active.inputs["Metallic"].default_value
    material.diffuse_color = (0.12, 0.34, 0.56, 0.5)
    assert transfer_surface(material)["model"] == "pbr_constants"
    print("FORGEMCP_NATIVE_NODE_SHADING_IGNORES_VIEWPORT_METADATA_PASS")
else:
    assert abs(surface["roughness"] - 0.27) < 1e-6
    assert abs(surface["metallic"] - 0.63) < 1e-6
    material.diffuse_color = (0.12, 0.34, 0.56, 0.5)
    assert transfer_surface(material) == {"model": "unsupported", "reason": "transparency"}

material.use_nodes = True
shader = material.node_tree.nodes.get("Principled BSDF")
shader.inputs["Base Color"].default_value = (0.12, 0.34, 0.56, 1)
shader.inputs["Roughness"].default_value = 0.27
shader.inputs["Metallic"].default_value = 0.63
assert transfer_surface(material)["model"] == "pbr_constants"
material.use_backface_culling = True
assert transfer_surface(material)["two_sided"] is False
material.use_backface_culling = False
assert transfer_surface(material)["two_sided"] is True
for name, value in (("Coat Weight", 0.5), ("Transmission Weight", 0.5),
                    ("Anisotropic", 0.5), ("Diffuse Roughness", 0.5),
                    ("Emission Strength", 2.0), ("Specular IOR Level", 0.7), ("IOR", 1.7)):
    old = shader.inputs[name].default_value
    shader.inputs[name].default_value = value
    assert transfer_surface(material) == {"model": "unsupported", "reason": "non_default_bsdf"}, name
    shader.inputs[name].default_value = old
shader.inputs["Alpha"].default_value = 0.5
assert transfer_surface(material)["reason"] == "transparency"
shader.inputs["Alpha"].default_value = 1
noise = material.node_tree.nodes.new("ShaderNodeTexNoise")
material.node_tree.links.new(noise.outputs["Fac"], shader.inputs["Roughness"])
assert transfer_surface(material) == {"model": "unsupported", "reason": "shader_graph"}
shader.inputs["Roughness"].keyframe_insert(data_path="default_value", frame=1)
assert transfer_surface(material) == {"model": "unsupported", "reason": "animation"}
print("FORGEMCP_NATIVE_MATERIAL_CONSTANTS_AND_UNSUPPORTED_SURFACES_PASS")
