# SPDX-License-Identifier: MIT
"""Native shader graph facts and construction; no scripts, files or existing graph edits."""

import math
import re

import bpy

NODE_TYPES = {
    "ShaderNodeOutputMaterial", "ShaderNodeBsdfPrincipled", "ShaderNodeRGB",
    "ShaderNodeValue", "ShaderNodeMath", "ShaderNodeMixRGB", "ShaderNodeTexNoise",
    "ShaderNodeTexCoord", "ShaderNodeMapping", "ShaderNodeBump", "ShaderNodeVectorMath",
    "ShaderNodeSeparateXYZ", "ShaderNodeCombineXYZ",
}
MATH_OPERATIONS = {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "MINIMUM", "MAXIMUM", "POWER"}
VECTOR_OPERATIONS = {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "CROSS_PRODUCT", "DOT_PRODUCT",
                     "NORMALIZE", "LENGTH", "SCALE"}
BLEND_OPERATIONS = {"MIX", "ADD", "MULTIPLY", "SUBTRACT", "SCREEN", "OVERLAY"}


def socket(tree_node, collection, key):
    # Identifiers distinguish repeated labels, e.g. Math's Value and Value_001.
    sockets = getattr(tree_node, collection)
    by_identifier = [s for s in sockets if s.identifier == key]
    if len(by_identifier) == 1:
        return by_identifier[0]
    by_name = [s for s in sockets if s.name == key]
    if len(by_name) != 1:
        raise ValueError("Socket was not found or its label is ambiguous; use an identifier.")
    return by_name[0]


def graph_validate(nodes, links):
    if not isinstance(nodes, list) or len(nodes) > 32 or not isinstance(links, list) or len(links) > 64:
        raise ValueError("Use at most 32 shader nodes and 64 links.")
    if not nodes:
        if links:
            raise ValueError("Shader links require explicit nodes.")
        return
    ids = set()
    for node in nodes:
        if not isinstance(node, dict) or set(node) - {"id", "type", "inputs", "outputs", "operation", "x", "y"}:
            raise ValueError("Unknown shader node fields.")
        name, kind = node.get("id"), node.get("type")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name):
            raise ValueError("Invalid shader node ID.")
        if name in ids or kind not in NODE_TYPES:
            raise ValueError("Duplicate ID or shader node type outside the allowlist.")
        ids.add(name)
        for coordinate in ("x", "y"):
            value = node.get(coordinate, 0)
            if type(value) is not int or not -100000 <= value <= 100000:
                raise ValueError("Invalid shader node position.")
        operation = node.get("operation", "")
        permitted = {"ShaderNodeMath": MATH_OPERATIONS, "ShaderNodeVectorMath": VECTOR_OPERATIONS,
                     "ShaderNodeMixRGB": BLEND_OPERATIONS}.get(kind, set())
        if operation and (not isinstance(operation, str) or operation not in permitted):
            raise ValueError("Shader operation is outside the allowlist.")
        inputs, outputs = node.get("inputs", {}), node.get("outputs", {})
        if not isinstance(inputs, dict) or len(inputs) > 16 or not isinstance(outputs, dict) or len(outputs) > 16:
            raise ValueError("Use at most 16 defaults in each socket direction per node.")
        if outputs and kind not in {"ShaderNodeRGB", "ShaderNodeValue"}:
            raise ValueError("Output defaults are supported only on RGB and Value constants.")
        for key, value in list(inputs.items()) + list(outputs.items()):
            if not isinstance(key, str) or not 1 <= len(key) <= 64:
                raise ValueError("Invalid socket key.")
            values = value if isinstance(value, list) else [value]
            if isinstance(value, list) and len(value) not in (3, 4):
                raise ValueError("Socket vectors require three or four components.")
            if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e8 for v in values):
                raise ValueError("Socket defaults must be bounded finite numbers or vectors.")
    if sum(n["type"] == "ShaderNodeOutputMaterial" for n in nodes) != 1:
        raise ValueError("Custom shader graphs require exactly one material output node.")
    targets = set()
    for link in links:
        if not isinstance(link, dict) or set(link) != {"from_node", "from_socket", "to_node", "to_socket"}:
            raise ValueError("Expected explicit shader link endpoints.")
        if link["from_node"] not in ids or link["to_node"] not in ids:
            raise ValueError("Shader link references an unknown node.")
        for key in ("from_socket", "to_socket"):
            if not isinstance(link[key], str) or not 1 <= len(link[key]) <= 64:
                raise ValueError("Invalid shader socket key.")
        target = (link["to_node"], link["to_socket"])
        if target in targets:
            raise ValueError("An input can have only one recipe link.")
        targets.add(target)
    # Prevent cyclic shader evaluation using the proposed node dependency graph.
    edges = {name: [] for name in ids}
    for link in links:
        edges[link["from_node"]].append(link["to_node"])
    visiting, visited = set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError("Shader graph cycles are not allowed.")
        if name in visited:
            return
        visiting.add(name)
        for child in edges[name]:
            visit(child)
        visiting.remove(name)
        visited.add(name)

    for name in ids:
        visit(name)


def construct_graph(material, nodes, links):
    # Called only on a newly created material already registered with batch rollback.
    tree = material.node_tree
    tree.nodes.clear()
    instances = {}
    for spec in nodes:
        node = tree.nodes.new(spec["type"])
        node.name = spec["id"]
        node.location = (spec.get("x", 0), spec.get("y", 0))
        instances[spec["id"]] = node
        if spec.get("operation"):
            setattr(node, "blend_type" if node.bl_idname == "ShaderNodeMixRGB" else "operation",
                    spec["operation"])
        for key, value in spec.get("inputs", {}).items():
            pin = socket(node, "inputs", key)
            if not hasattr(pin, "default_value") or pin.type not in {"VALUE", "RGBA", "VECTOR"}:
                raise ValueError("This socket does not support recipe defaults.")
            if pin.type == "VALUE" and type(value) not in (int, float):
                raise ValueError("Scalar input requires a scalar default.")
            if pin.type in {"VECTOR", "RGBA"} and (
                not isinstance(value, list) or len(value) != (4 if pin.type == "RGBA" else 3)
            ):
                raise ValueError("Socket default dimensions do not match.")
            if pin.type == "RGBA" and any(not 0 <= v <= 1 for v in value):
                raise ValueError("Color components must be in 0..1.")
            if pin.type == "VALUE":
                prop = pin.bl_rna.properties.get("default_value")
                if prop and not prop.hard_min <= value <= prop.hard_max:
                    raise ValueError("Scalar default is outside the native socket range.")
            pin.default_value = value
        for key, value in spec.get("outputs", {}).items():
            pin = socket(node, "outputs", key)
            if node.bl_idname == "ShaderNodeRGB":
                if not isinstance(value, list) or len(value) != 4 or any(not 0 <= v <= 1 for v in value):
                    raise ValueError("RGB constant requires RGBA in 0..1.")
            elif node.bl_idname == "ShaderNodeValue":
                if type(value) not in (int, float):
                    raise ValueError("Value constant requires a scalar.")
            else:
                raise ValueError("Output default is outside the node allowlist.")
            pin.default_value = value
    for spec in links:
        output = socket(instances[spec["from_node"]], "outputs", spec["from_socket"])
        input_pin = socket(instances[spec["to_node"]], "inputs", spec["to_socket"])
        if input_pin.is_linked:
            raise ValueError("Multiple links resolve to the same input socket.")
        compatible = output.type == input_pin.type or {
            output.type, input_pin.type
        } <= {"VALUE", "RGBA", "VECTOR"}
        if not compatible:
            raise ValueError("Shader socket types are incompatible.")
        tree.links.new(output, input_pin)
    tree.update_tag()


def editable_input(material_name, node_name, socket_name, value):
    material = bpy.data.materials.get(material_name)
    if not material or material.library or not material.use_nodes:
        raise ValueError("Expected a local material with a native node tree.")
    if len(material.node_tree.nodes) > 64 or len(material.node_tree.links) > 128:
        raise ValueError("Material exceeds bounded edit inspection limits.")
    node = material.node_tree.nodes.get(node_name)
    if not node or node.bl_idname not in NODE_TYPES:
        raise ValueError("Expected an existing allowlisted native shader node.")
    pin = socket(node, "inputs", socket_name)
    if pin.type == "VALUE":
        if type(value) not in (float, int) or not math.isfinite(value) or abs(value) > 1e8:
            raise ValueError("Expected a bounded finite scalar default.")
        prop = pin.bl_rna.properties.get("default_value")
        if prop and not prop.hard_min <= value <= prop.hard_max:
            raise ValueError("Default is outside the native socket range.")
    elif pin.type in {"RGBA", "VECTOR"}:
        if not isinstance(value, list) or len(value) != (4 if pin.type == "RGBA" else 3):
            raise ValueError("Socket default dimensions do not match.")
        if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1e8 for v in value):
            raise ValueError("Expected bounded finite vector components.")
        if pin.type == "RGBA" and any(not 0 <= v <= 1 for v in value):
            raise ValueError("Color defaults must be in 0..1.")
    else:
        raise ValueError("This socket does not support primitive default editing.")
    return pin


def material_info(name):
    if not isinstance(name, str) or not 1 <= len(name) <= 64:
        raise ValueError("Expected a bounded material name.")
    material = bpy.data.materials.get(name)
    if material is None:
        raise ValueError("Material was not found.")
    tree = material.node_tree if material.use_nodes else None
    result = {"name": material.name, "library": material.library.filepath if material.library else None,
              "users": material.users, "diffuse_color": list(material.diffuse_color),
              "use_nodes": material.use_nodes, "nodes": [], "links": []}
    users = sorted(obj.name for obj in bpy.data.objects
                   if material in list(getattr(obj.data, "materials", [])))
    result["object_users"] = users[:200]
    result["total_object_users"] = len(users)
    result["object_users_truncated"] = len(users) > 200
    if tree:
        for node in list(tree.nodes)[:64]:
            def describe_socket(pin):
                info = {"name": pin.name, "identifier": pin.identifier, "type": pin.type,
                        "linked": pin.is_linked}
                value = getattr(pin, "default_value", None)
                if type(value) in (int, float, bool, str):
                    info["default"] = value[:256] if isinstance(value, str) else value
                elif pin.type in {"RGBA", "VECTOR"} and value is not None:
                    info["default"] = list(value)
                return info
            result["nodes"].append({"id": node.name, "type": node.bl_idname,
                                    "operation": getattr(node, "operation", None),
                                    "blend_type": getattr(node, "blend_type", None),
                                    "location": list(node.location),
                                    "inputs": [describe_socket(p) for p in list(node.inputs)[:32]],
                                    "outputs": [describe_socket(p) for p in list(node.outputs)[:32]],
                                    "sockets_truncated": len(node.inputs) > 32 or len(node.outputs) > 32})
        result["links"] = [{"from_node": link.from_node.name,
                            "from_socket": link.from_socket.identifier,
                            "to_node": link.to_node.name,
                            "to_socket": link.to_socket.identifier,
                            "valid": link.is_valid} for link in list(tree.links)[:128]]
    result["total_nodes"] = len(tree.nodes) if tree else 0
    result["total_links"] = len(tree.links) if tree else 0
    result["truncated"] = result["total_nodes"] > 64 or result["total_links"] > 128
    return result


def transfer_surface(material):
    """Describe the explicit constant-PBR transfer profile without changing data.

    Unsupported surfaces stay identifiable in standalone geometry exports. A
    material-transfer workflow must reject them rather than approximate a graph.
    This maps parameters, not an assertion of identical renderer appearance.
    """
    def unsupported(reason):
        return {"model": "unsupported", "reason": reason}

    if material.animation_data or (material.node_tree and material.node_tree.animation_data):
        return unsupported("animation")
    if material.use_nodes:
        tree = material.node_tree
        if tree is None or len(tree.nodes) != 2 or len(tree.links) != 1:
            return unsupported("shader_graph")
        shaders = [n for n in tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled"]
        outputs = [n for n in tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output]
        if len(shaders) != 1 or len(outputs) != 1:
            return unsupported("shader_graph")
        shader, output = shaders[0], outputs[0]
        link = tree.links[0]
        if (
            not link.is_valid or link.from_node != shader or link.to_node != output
            or link.from_socket.name != "BSDF" or link.to_socket.name != "Surface"
            or any(pin.is_linked for pin in shader.inputs)
        ):
            return unsupported("shader_graph")
        if output.target != "ALL":
            return unsupported("shader_graph")
        # Features that this opaque Default Lit mapping cannot reproduce.
        neutral = {
            "IOR": 1.5, "Specular IOR Level": 0.5, "Subsurface Weight": 0.0,
            "Transmission Weight": 0.0, "Coat Weight": 0.0, "Sheen Weight": 0.0,
            "Emission Strength": 0.0, "Anisotropic IOR Level": 0.0,
            "Anisotropic": 0.0, "Diffuse Roughness": 0.0,
            "Weight": 0.0,
            "Thin Film Thickness": 0.0,
        }
        for name, expected in neutral.items():
            pin = shader.inputs.get(name)
            if pin is not None and abs(float(pin.default_value) - expected) > 1e-6:
                return unsupported("non_default_bsdf")
        tint = shader.inputs.get("Specular Tint")
        if tint is not None and any(abs(float(v) - 1.0) > 1e-6 for v in tint.default_value):
            return unsupported("non_default_bsdf")
        normal = shader.inputs.get("Normal")
        if normal is not None and any(abs(float(v)) > 1e-6 for v in normal.default_value):
            return unsupported("non_default_bsdf")
        color = list(shader.inputs["Base Color"].default_value)
        alpha = float(shader.inputs["Alpha"].default_value)
        roughness = float(shader.inputs["Roughness"].default_value)
        metallic = float(shader.inputs["Metallic"].default_value)
    else:
        color = list(material.diffuse_color)
        alpha = color[3]
        roughness, metallic = float(material.roughness), float(material.metallic)
    if abs(alpha - 1.0) > 1e-6 or abs(color[3] - 1.0) > 1e-6:
        return unsupported("transparency")
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in color + [roughness, metallic]):
        return unsupported("out_of_range")
    return {"model": "pbr_constants", "color_space": "scene_linear",
            "base_color": color[:3], "roughness": roughness, "metallic": metallic,
            "two_sided": not material.use_backface_culling}
