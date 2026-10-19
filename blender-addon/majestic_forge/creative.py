# SPDX-License-Identifier: MIT
"""Original RNA-driven creative workflows. No eval, arbitrary code, or arbitrary operators."""

import hashlib
import json
import math
import os
import re
import secrets
import struct
import subprocess
import time
from pathlib import Path

import bpy

from .automation import RecipeError, action_curves, fingerprint
from .materials import socket
from .security import protect_path

PRIMITIVES = {
    "mesh.primitive_plane_add",
    "mesh.primitive_cube_add",
    "mesh.primitive_circle_add",
    "mesh.primitive_uv_sphere_add",
    "mesh.primitive_ico_sphere_add",
    "mesh.primitive_cylinder_add",
    "mesh.primitive_cone_add",
    "mesh.primitive_torus_add",
    "mesh.primitive_grid_add",
    "mesh.primitive_monkey_add",
    "curve.primitive_bezier_curve_add",
    "curve.primitive_bezier_circle_add",
    "curve.primitive_nurbs_curve_add",
    "curve.primitive_nurbs_circle_add",
    "curve.primitive_nurbs_path_add",
    "surface.primitive_nurbs_surface_curve_add",
    "surface.primitive_nurbs_surface_circle_add",
    "surface.primitive_nurbs_surface_surface_add",
    "surface.primitive_nurbs_surface_cylinder_add",
    "surface.primitive_nurbs_surface_sphere_add",
    "surface.primitive_nurbs_surface_torus_add",
}
MESH_OPERATORS = {
    "mesh.subdivide",
    "mesh.unsubdivide",
    "mesh.triangulate",
    "mesh.quads_convert_to_tris",
    "mesh.tris_convert_to_quads",
    "mesh.beautify_fill",
    "mesh.remove_doubles",
    "mesh.merge",
    "mesh.dissolve_limited",
    "mesh.dissolve_degenerate",
    "mesh.dissolve_edges",
    "mesh.dissolve_verts",
    "mesh.dissolve_faces",
    "mesh.delete_loose",
    "mesh.fill",
    "mesh.fill_grid",
    "mesh.fill_holes",
    "mesh.edge_split",
    "mesh.split",
    "mesh.flip_normals",
    "mesh.normals_make_consistent",
    "mesh.vertices_smooth",
    "mesh.vertices_smooth_laplacian",
    "mesh.faces_shade_smooth",
    "mesh.faces_shade_flat",
    "mesh.mark_seam",
    "mesh.mark_sharp",
    "mesh.poke",
    "mesh.inset",
    "mesh.bevel",
    "mesh.extrude_faces_move",
    "mesh.extrude_region",
    "mesh.extrude_edges_indiv",
    "mesh.extrude_faces_indiv",
    "mesh.extrude_vertices_move",
    "mesh.solidify",
    "mesh.edge_rotate",
    "mesh.symmetrize",
    "mesh.select_all",
    "mesh.select_mode",
    "mesh.select_more",
    "mesh.select_less",
    "mesh.select_non_manifold",
    "mesh.select_interior_faces",
    "mesh.select_face_by_sides",
}
SIMPLE = {"BOOLEAN", "INT", "FLOAT", "ENUM"}
TARGET_KINDS = {
    "scene",
    "render",
    "image_settings",
    "view_settings",
    "cycles",
    "eevee",
    "world",
    "object",
    "mesh",
    "camera",
    "light",
    "material",
    "node",
    "socket",
    "modifier",
    "constraint",
}
OBJECT_PROPERTIES = {
    "location",
    "rotation_euler",
    "rotation_quaternion",
    "rotation_mode",
    "scale",
    "hide_render",
    "hide_viewport",
    "display_type",
    "color",
    "show_in_front",
}
SCENE_PROPERTIES = {"frame_start", "frame_end", "frame_step", "use_nodes"}
# Flags affecting threading/file output are controlled by render jobs, never generic setters.
BLOCKED_PROPERTIES = {
    "name",
    "name_full",
    "filepath",
    "use_lock_interface",
    "use_file_extension",
    "use_multiview",
    "use_overwrite",
    "use_placeholder",
    "is_active_output",
}
REQUEST_FIELDS = {
    "action",
    "name",
    "target",
    "type",
    "properties",
    "parameters",
    "nodes",
    "links",
    "keyframes",
    "path",
    "frame_start",
    "frame_end",
    "assign_to",
    "make_active",
}


def fail(code, message):
    raise RecipeError(code, message)


def plain(value):
    if type(value) in (bool, str, int, float) or value is None:
        return value
    if isinstance(value, set):
        return sorted(value)
    return [plain(item) for item in value]


def checked_name(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(ord(c) < 32 for c in value):
        fail("invalid_arguments", "An exact nonempty datablock name is required.")
    return value


def operator(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", identifier
    ):
        fail(
            "invalid_arguments", "Use an exact Blender operator identifier such as mesh.subdivide."
        )
    try:
        namespace, name = identifier.split(".")
        op = getattr(getattr(bpy.ops, namespace), name)
        op.get_rna_type()
        return op
    except (AttributeError, RuntimeError, KeyError):
        fail(
            "operator_not_found", "This operator is not registered in the selected Blender session."
        )


def property_schema(prop):
    result = {
        "identifier": prop.identifier,
        "name": prop.name,
        "description": prop.description[:512],
        "type": prop.type,
        "readonly": prop.is_readonly,
        "subtype": prop.subtype,
    }
    if prop.type in SIMPLE:
        result["array_length"] = getattr(prop, "array_length", 0)
        if prop.type in {"INT", "FLOAT"}:
            result["minimum"] = prop.hard_min
            result["maximum"] = prop.hard_max
        if prop.type == "ENUM":
            result["items"] = [
                {"identifier": e.identifier, "name": e.name} for e in list(prop.enum_items)[:256]
            ]
            result["enum_flag"] = prop.is_enum_flag
            if prop.identifier == "engine":
                existing = {item["identifier"] for item in result["items"]}
                for cls in bpy.types.RenderEngine.__subclasses__():
                    identifier = getattr(cls, "bl_idname", None)
                    if identifier and identifier not in existing:
                        result["items"].append({"identifier": identifier, "name": identifier})
        try:
            result["default"] = plain(
                prop.default_array if getattr(prop, "is_array", False) else prop.default
            )
        except (AttributeError, TypeError):
            pass
    return result


def list_commands(query="", offset=0, limit=100):
    if (
        not isinstance(query, str)
        or len(query) > 128
        or type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or not 1 <= limit <= 200
    ):
        fail("invalid_arguments", "Use a bounded operator catalog query/page.")
    matches = []
    for ns in sorted(dir(bpy.ops)):
        if ns.startswith("_"):
            continue
        for name in sorted(dir(getattr(bpy.ops, ns))):
            identifier = f"{ns}.{name}"
            if name.startswith("_") or query.casefold() not in identifier.casefold():
                continue
            matches.append(
                {
                    "identifier": identifier,
                    "execution": "create_object"
                    if identifier in PRIMITIVES
                    else "mesh_operator"
                    if identifier in MESH_OPERATORS
                    else "discovery_only",
                    "reason": "Reviewed typed operation"
                    if identifier in PRIMITIVES | MESH_OPERATORS
                    else "Requires a dedicated context/authorization adapter; catalog presence does not authorize execution.",
                }
            )
    return {
        "blender_version": bpy.app.version_string,
        "total": len(matches),
        "offset": offset,
        "commands": matches[offset : offset + limit],
        "truncated": offset + limit < len(matches),
    }


def inspect_command(identifier):
    op = operator(identifier)
    rna = op.get_rna_type()
    try:
        poll = bool(op.poll())
    except RuntimeError:
        poll = False
    return {
        "identifier": identifier,
        "rna_identifier": rna.identifier,
        "description": rna.description[:1024],
        "parameters": [
            property_schema(p) for p in list(rna.properties)[:128] if p.identifier != "rna_type"
        ],
        "execution": "create_object"
        if identifier in PRIMITIVES
        else "mesh_operator"
        if identifier in MESH_OPERATORS
        else "discovery_only",
        "poll_in_current_context": poll,
        "parameters_truncated": len(rna.properties) > 128,
    }


def resolve(target):
    if (
        not isinstance(target, dict)
        or set(target) - {"kind", "name", "component", "socket"}
        or target.get("kind") not in TARGET_KINDS
    ):
        fail("invalid_arguments", "Expected an explicit typed Blender property target.")
    kind = target["kind"]
    name = target.get("name", "")
    component = target.get("component", "")
    scene = bpy.context.scene
    if kind in {"scene", "render", "image_settings", "view_settings", "cycles", "eevee", "world"}:
        if name and name != scene.name:
            fail("scene_mismatch", "Scene-scoped targets must name the active scene.")
        if kind == "scene":
            return scene
        if kind == "image_settings":
            return scene.render.image_settings
        obj = getattr(scene, kind, None)
    elif kind in {"material", "node", "socket"}:
        obj = bpy.data.materials.get(name)
        if obj is None:
            fail("target_not_found", "Material was not found.")
        if kind in {"node", "socket"}:
            obj = obj.node_tree.nodes.get(component) if obj.node_tree else None
            if obj and kind == "socket":
                obj = socket(obj, "inputs", target.get("socket", ""))
    else:
        obj = scene.objects.get(name)
        if obj is not None:
            if kind in {"camera", "light", "mesh"}:
                if obj.type != kind.upper():
                    fail("target_type_mismatch", "Object data type differs from the target.")
                obj = obj.data
            elif kind in {"modifier", "constraint"}:
                obj = getattr(obj, kind + "s").get(component)
    if obj is None:
        fail("target_not_found", "Exact native target was not found in the active scene.")
    owner = getattr(obj, "id_data", obj)
    if getattr(owner, "library", None) or getattr(owner, "override_library", None):
        fail("linked_data", "Linked/overridden data cannot be edited by this workflow.")
    return obj


def editable(target, prop):
    if (
        prop.identifier in BLOCKED_PROPERTIES
        or prop.identifier.startswith("bl_")
        or prop.is_readonly
        or prop.type not in SIMPLE
    ):
        return False
    if target["kind"] == "object":
        return prop.identifier in OBJECT_PROPERTIES
    if target["kind"] == "scene":
        return prop.identifier in SCENE_PROPERTIES
    if target["kind"] == "socket":
        return prop.identifier == "default_value"
    return True


def validate_value(prop, value):
    if prop.type not in SIMPLE or prop.is_readonly:
        fail(
            "property_not_editable",
            "Only editable native numeric, boolean and enum properties are accepted.",
        )
    if getattr(prop, "is_array", False):
        if not isinstance(value, list) or len(value) != prop.array_length:
            fail("invalid_arguments", "Native property array dimensions do not match.")
        values = value
    else:
        values = [value]
    if prop.type == "ENUM":
        ids = {i.identifier for i in prop.enum_items}
        if prop.identifier == "engine":
            ids.update(
                getattr(cls, "bl_idname", "") for cls in bpy.types.RenderEngine.__subclasses__()
            )
        if prop.is_enum_flag:
            if not isinstance(value, list) or any(
                not isinstance(v, str) or v not in ids for v in value
            ):
                fail("invalid_enum", "Invalid native enum flags.")
            return set(value)
        if not isinstance(value, str) or value not in ids:
            fail("invalid_enum", "Value is not in the native enum schema.")
    elif prop.type == "BOOLEAN":
        if any(type(v) is not bool for v in values):
            fail("invalid_arguments", "Boolean properties require JSON booleans.")
    else:
        for v in values:
            if (
                type(v) not in (int, float)
                or (prop.type == "INT" and type(v) is not int)
                or not math.isfinite(v)
                or not prop.hard_min <= v <= prop.hard_max
                or abs(v) > 1e10
            ):
                fail("invalid_arguments", "Value is outside the native finite numeric range.")
    return value


def property_values(obj):
    values = {}
    for p in obj.bl_rna.properties:
        if p.type in SIMPLE:
            try:
                values[p.identifier] = plain(getattr(obj, p.identifier))
            except (AttributeError, TypeError):
                pass
    return values


def inspect_properties(target):
    obj = resolve(target)
    props = []
    for p in list(obj.bl_rna.properties)[:256]:
        info = property_schema(p)
        info["editable_by_bridge"] = editable(target, p)
        if p.type in SIMPLE:
            try:
                info["value"] = plain(getattr(obj, p.identifier))
            except (AttributeError, TypeError):
                pass
        props.append(info)
    return {
        "target": target,
        "rna_type": obj.bl_rna.identifier,
        "properties": props,
        "truncated": len(obj.bl_rna.properties) > 256,
    }


def list_types(query="", offset=0, limit=100):
    if (
        not isinstance(query, str)
        or len(query) > 128
        or type(offset) is not int
        or offset < 0
        or type(limit) is not int
        or not 1 <= limit <= 200
    ):
        fail("invalid_arguments", "Use bounded type catalog pages.")
    names = [
        n
        for n in sorted(dir(bpy.types))
        if query.casefold() in n.casefold() and hasattr(getattr(bpy.types, n), "bl_rna")
    ]
    return {
        "total": len(names),
        "types": names[offset : offset + limit],
        "offset": offset,
        "truncated": offset + limit < len(names),
    }


def inspect_type(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", name):
        fail("invalid_arguments", "Use an exact native RNA type name.")
    cls = getattr(bpy.types, name, None)
    if cls is None or not hasattr(cls, "bl_rna"):
        fail("type_not_found", "RNA type is not registered.")
    props = cls.bl_rna.properties
    return {
        "name": name,
        "properties": [property_schema(p) for p in list(props)[:256]],
        "truncated": len(props) > 256,
        "node_creation_supported": name.startswith("ShaderNode")
        and name not in {"ShaderNodeScript", "ShaderNodeGroup", "ShaderNodeCustomGroup"},
    }


def validated_properties(obj, properties, target=None):
    if not isinstance(properties, dict) or not 1 <= len(properties) <= 64:
        fail("invalid_arguments", "Use 1–64 native property values.")
    clean = {}
    for key, value in properties.items():
        prop = obj.bl_rna.properties.get(key)
        if (
            prop is None
            or (target is not None and not editable(target, prop))
            or key in BLOCKED_PROPERTIES
        ):
            fail(
                "property_not_editable", "Property is absent or outside this target's edit policy."
            )
        clean[key] = validate_value(prop, value)
    return clean


def new_file(path):
    if not isinstance(path, str) or not path or len(path) > 1024 or "\x00" in path:
        fail("invalid_path", "Use an absolute new .blend destination.")
    p = Path(path)
    if not p.is_absolute() or p.suffix.lower() != ".blend" or not p.parent.is_dir() or p.exists():
        fail(
            "invalid_path",
            "Destination must be a new .blend file in an existing absolute directory.",
        )
    for ancestor in (p.parent, *p.parents):
        if ancestor.is_symlink() or getattr(ancestor.stat(), "st_file_attributes", 0) & 0x400:
            fail("invalid_path", "Linked/reparse destinations are not supported.")
    return p


def graph_state(tree):
    if not tree:
        return None
    if len(tree.nodes) > 512 or len(tree.links) > 1024:
        fail("scene_limit", "Node tree exceeds snapshot limits.")
    nodes = []
    for n in tree.nodes:
        nodes.append(
            {
                "name": n.name,
                "type": n.bl_idname,
                "properties": property_values(n),
                "inputs": [
                    [s.identifier, plain(s.default_value)]
                    for s in n.inputs
                    if hasattr(s, "default_value")
                    and s.type in {"VALUE", "INT", "BOOLEAN", "VECTOR", "RGBA", "STRING"}
                ],
                "outputs": [
                    [s.identifier, plain(s.default_value)]
                    for s in n.outputs
                    if hasattr(s, "default_value")
                    and s.type in {"VALUE", "INT", "BOOLEAN", "VECTOR", "RGBA", "STRING"}
                ],
                "color_ramp": [[e.position, list(e.color)] for e in n.color_ramp.elements]
                if hasattr(n, "color_ramp")
                else None,
            }
        )
    return {
        "nodes": nodes,
        "action": action_curves(tree.animation_data.action if tree.animation_data else None),
        "links": [
            [
                edge.from_node.name,
                edge.from_socket.identifier,
                edge.to_node.name,
                edge.to_socket.identifier,
            ]
            for edge in tree.links
        ],
    }


def scene_revision():
    scene = bpy.context.scene
    if len(scene.objects) > 2000:
        fail("scene_limit", "Creative snapshots support at most 2000 objects.")
    state = {
        "legacy": fingerprint([]),
        "camera": scene.camera.name if scene.camera else None,
        "mode": bpy.context.mode,
        "settings": [
            property_values(o)
            for o in [scene, scene.render, scene.render.image_settings, scene.view_settings]
        ],
        "world": graph_state(scene.world.node_tree) if scene.world else None,
        "objects": [],
        "materials": [],
        "groups": [],
        "scene_action": action_curves(
            scene.animation_data.action if scene.animation_data else None
        ),
    }
    for kind in ("cycles", "eevee"):
        if hasattr(scene, kind):
            state[kind] = property_values(getattr(scene, kind))
    vertex_total = 0
    for obj in scene.objects:
        entry = {
            "name": obj.name,
            "identity": obj.as_pointer(),
            "props": property_values(obj),
            "data_id": obj.data.as_pointer() if obj.data else None,
            "modifiers": [[m.name, m.type, property_values(m)] for m in obj.modifiers],
            "constraints": [
                [
                    c.name,
                    c.type,
                    property_values(c),
                    c.target.name if hasattr(c, "target") and c.target else None,
                ]
                for c in obj.constraints
            ],
            "action": action_curves(obj.animation_data.action if obj.animation_data else None),
        }
        if obj.type == "MESH":
            vertex_total += len(obj.data.vertices)
            if vertex_total > 500000:
                fail("scene_limit", "Snapshot geometry exceeds 500000 source vertices.")
            entry["geometry"] = [
                [list(v.co) for v in obj.data.vertices],
                [list(p.vertices) for p in obj.data.polygons],
            ]
            entry["materials"] = [m.name if m else None for m in obj.data.materials]
            entry["uvs"] = [
                [layer.name, [list(loop.uv) for loop in layer.data]] for layer in obj.data.uv_layers
            ]
            entry["face_settings"] = [[p.material_index, p.use_smooth] for p in obj.data.polygons]
            entry["edge_settings"] = [[e.use_seam, e.use_edge_sharp] for e in obj.data.edges]
        elif obj.type in {"CURVE", "SURFACE"}:
            entry["data"] = property_values(obj.data)
            entry["splines"] = [
                {
                    "type": spline.type,
                    "properties": property_values(spline),
                    "points": [list(p.co) for p in spline.points],
                    "bezier": [
                        [list(p.co), list(p.handle_left), list(p.handle_right)]
                        for p in spline.bezier_points
                    ],
                }
                for spline in obj.data.splines
            ]
        elif obj.data:
            entry["data"] = property_values(obj.data)
        state["objects"].append(entry)
    for m in bpy.data.materials:
        state["materials"].append([m.name, graph_state(m.node_tree)])
    for g in bpy.data.node_groups:
        state["groups"].append([g.name, graph_state(g)])
    return hashlib.sha256(json.dumps(state, sort_keys=True, allow_nan=False).encode()).hexdigest()


class CreativeAutomation:
    def __init__(self, root):
        self.root = Path(root)
        self.previews = {}
        self.jobs = {}

    def validate(self, request):
        if not isinstance(request, dict) or set(request) - REQUEST_FIELDS:
            fail("invalid_arguments", "Unknown creative request fields.")
        action = request.get("action")
        if bpy.context.mode != "OBJECT":
            fail(
                "context_not_supported",
                "Creative operations require Object Mode; existing Edit Mode work is preserved.",
            )
        if action == "create_object":
            checked_name(request.get("name"))
            if bpy.data.objects.get(request["name"]):
                fail("name_exists", "Object name already exists.")
            kind = request.get("type")
            if kind not in PRIMITIVES | {
                "CAMERA",
                "POINT",
                "SUN",
                "SPOT",
                "AREA",
                "EMPTY",
                "WORLD",
            }:
                fail(
                    "unsupported_operation",
                    "Object creation type is outside the native creation catalog.",
                )
            if kind in PRIMITIVES:
                op = operator(kind)
                for key, value in request.get("parameters", {}).items():
                    prop = op.get_rna_type().properties.get(key)
                    if prop is None:
                        fail("invalid_arguments", "Unknown primitive parameter.")
                    validate_value(prop, value)
                    if key == "enter_editmode" and value:
                        fail("context_not_supported", "Primitive creation must preserve Object Mode.")
                    if (
                        key
                        in {
                            "segments",
                            "ring_count",
                            "vertices",
                            "major_segments",
                            "minor_segments",
                            "x_subdivisions",
                            "y_subdivisions",
                        }
                        and value > 256
                    ):
                        fail(
                            "geometry_limit",
                            "Primitive tessellation is limited to 256 segments per dimension.",
                        )
                    if key == "subdivisions" and value > 6:
                        fail("geometry_limit", "Icosphere subdivisions are limited to 6.")
            elif request.get("parameters"):
                fail(
                    "invalid_arguments",
                    "Data API creation uses properties, not operator parameters.",
                )
        elif action == "edit_properties":
            target = request.get("target")
            obj = resolve(target)
            validated_properties(obj, request.get("properties", {}), target)
        elif action == "create_material_graph":
            checked_name(request.get("name"))
            if bpy.data.materials.get(request["name"]):
                fail("name_exists", "Material name already exists.")
            nodes = request.get("nodes", [])
            links = request.get("links", [])
            if (
                not isinstance(nodes, list)
                or not 1 <= len(nodes) <= 128
                or not isinstance(links, list)
                or len(links) > 256
            ):
                fail("invalid_arguments", "Use 1–128 shader nodes and at most 256 links.")
            ids = set()
            for n in nodes:
                if not isinstance(n, dict) or set(n) - {
                    "id",
                    "type",
                    "properties",
                    "inputs",
                    "outputs",
                    "color_ramp",
                    "location",
                }:
                    fail("invalid_arguments", "Unknown shader node fields.")
                checked_name(n.get("id"))
                if n["id"] in ids:
                    fail("invalid_arguments", "Node IDs must be unique.")
                ids.add(n["id"])
                kind = n.get("type", "")
                cls = getattr(bpy.types, kind, None)
                if (
                    not kind.startswith("ShaderNode")
                    or kind in {"ShaderNodeScript", "ShaderNodeGroup", "ShaderNodeCustomGroup"}
                    or cls is None
                    or not issubclass(cls, bpy.types.Node)
                ):
                    fail(
                        "node_not_supported",
                        "Use a registered built-in shader node; script and group references require a separate adapter.",
                    )
            if sum(n.get("type") == "ShaderNodeOutputMaterial" for n in nodes) != 1:
                fail("invalid_graph", "Exactly one material output is required.")
            targets = set()
            edges = {n: [] for n in ids}
            for edge in links:
                if (
                    not isinstance(edge, dict)
                    or set(edge) != {"from_node", "from_socket", "to_node", "to_socket"}
                    or edge["from_node"] not in ids
                    or edge["to_node"] not in ids
                ):
                    fail("invalid_graph", "Links require exact node/socket endpoints.")
                target = (edge["to_node"], edge["to_socket"])
                if target in targets:
                    fail("invalid_graph", "Duplicate linked input.")
                targets.add(target)
                edges[edge["from_node"]].append(edge["to_node"])

            def visit(n, path, done):
                if n in path:
                    fail("invalid_graph", "Shader cycles are rejected.")
                if n in done:
                    return
                for child in edges[n]:
                    visit(child, path | {n}, done)
                done.add(n)

            done = set()
            for n in ids:
                visit(n, set(), done)
            if request.get("assign_to"):
                obj = bpy.context.scene.objects.get(request["assign_to"])
                if obj is None or obj.type != "MESH" or obj.data.library:
                    fail("target_not_found", "Material assignment requires a local mesh.")
        elif action in {"create_modifier", "create_constraint"}:
            obj = resolve(request.get("target"))
            if request["target"]["kind"] != "object":
                fail("invalid_arguments", "Modifier/constraint creation requires an object target.")
            checked_name(request.get("name"))
            collection = obj.modifiers if action == "create_modifier" else obj.constraints
            if collection.get(request["name"]):
                fail("name_exists", "Modifier/constraint name already exists.")
            prop = collection.bl_rna.functions["new"].parameters["type"]
            validate_value(prop, request.get("type"))
            if request.get("type") in {
                "NODES",
                "FLUID",
                "CLOTH",
                "SOFT_BODY",
                "PARTICLE_SYSTEM",
                "DYNAMIC_PAINT",
            }:
                fail(
                    "unsupported_operation",
                    "Simulation/cache and Geometry Nodes modifiers require a dedicated adapter.",
                )
        elif action == "mesh_operator":
            obj = resolve(request.get("target"))
            if (
                request["target"]["kind"] != "object"
                or obj.type != "MESH"
                or obj.data.library
                or obj.data.shape_keys
            ):
                fail(
                    "unsupported_operation",
                    "Mesh operators require a local plain mesh without shape keys.",
                )
            kind = request.get("type")
            if kind not in MESH_OPERATORS:
                fail(
                    "operator_not_allowed", "Use an audited mesh operator from the command catalog."
                )
            op = operator(kind)
            for key, value in request.get("parameters", {}).items():
                prop = op.get_rna_type().properties.get(key)
                if prop is None:
                    fail("invalid_arguments", "Unknown mesh operator parameter.")
                validate_value(prop, value)
                if key in {"number_cuts", "segments", "iterations", "repeat"} and value > 16:
                    fail(
                        "geometry_limit",
                        "Mesh iteration/tessellation parameters are limited to 16.",
                    )
            cuts = request.get("parameters", {}).get("number_cuts", 1)
            if len(obj.data.vertices) > 100000 or (
                kind == "mesh.subdivide" and len(obj.data.polygons) * (cuts + 1) ** 2 > 100000
            ):
                fail("geometry_limit", "Mesh edit exceeds bounded geometry limits.")
        elif action == "keyframe":
            target = request.get("target")
            obj = resolve(target)
            if getattr(obj, "animation_data", None) and obj.animation_data.drivers:
                fail(
                    "unsupported_operation", "Driven targets require a dedicated animation adapter."
                )
            keys = request.get("keyframes", [])
            if not isinstance(keys, list) or not 1 <= len(keys) <= 256:
                fail("invalid_arguments", "Use 1–256 explicit numeric keyframes.")
            for key in keys:
                if (
                    not isinstance(key, dict)
                    or set(key) - {"property", "frame", "value"}
                    or not {"property", "frame", "value"} <= set(key)
                ):
                    fail("invalid_arguments", "Keys require property, frame and value.")
                if type(key["frame"]) is not int or not -100000 <= key["frame"] <= 100000:
                    fail("invalid_arguments", "Invalid keyframe number.")
                prop = obj.bl_rna.properties.get(key["property"])
                if (
                    prop is None
                    or not editable(target, prop)
                    or prop.type not in {"INT", "FLOAT"}
                    or not getattr(prop, "is_animatable", False)
                ):
                    fail(
                        "property_not_animatable",
                        "Only editable native animatable numeric properties are supported.",
                    )
                validate_value(prop, key["value"])
        elif action == "save_copy":
            new_file(request.get("path"))
        elif action == "render":
            start = request.get("frame_start", 1)
            end = request.get("frame_end", start)
            if (
                type(start) is not int
                or type(end) is not int
                or not -100000 <= start <= end <= 100000
                or end - start + 1 > 1000
            ):
                fail("invalid_arguments", "Render 1–1000 frames in an explicit ascending range.")
            scene = bpy.context.scene
            if scene.camera is None:
                fail("camera_missing", "An active scene camera is required.")
            if scene.render.engine not in {"CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"}:
                fail("unsupported_renderer", "Use a supported native Cycles or Eevee engine.")
            if scene.render.resolution_x > 8192 or scene.render.resolution_y > 8192:
                fail("render_limit", "Render dimensions are limited to 8192 per axis.")
            if scene.render.image_settings.file_format != "PNG":
                fail(
                    "unsupported_output",
                    "Render jobs produce verifiable PNG frame sequences; select PNG first.",
                )
        else:
            fail("unsupported_operation", "Unknown creative operation.")
        return request

    def preview(self, request):
        request = json.loads(json.dumps(self.validate(request), allow_nan=False))
        now = time.monotonic()
        self.previews = {k: v for k, v in self.previews.items() if v["expires"] > now}
        if len(self.previews) >= 32:
            fail("preview_limit", "Too many pending creative previews.")
        pid = secrets.token_hex(16)
        self.previews[pid] = {
            "request": request,
            "revision": scene_revision(),
            "expires": now + 600,
        }
        return {
            "preview_id": pid,
            "expires_in_seconds": 600,
            "scene": bpy.context.scene.name,
            "changes": request,
            "saves_file": request["action"] in {"save_copy", "render"},
            "limitation": "One reviewed operation per transaction. Render returns a job, not completed frames. Save is a new copy; no overwrite.",
        }

    def apply(self, preview_id, confirmation):
        if not isinstance(preview_id, str) or confirmation != preview_id:
            fail("confirmation_required", "confirmation must equal the reviewed preview_id.")
        plan = self.previews.pop(preview_id, None)
        if plan is None or plan["expires"] <= time.monotonic():
            fail("preview_not_found", "Preview expired, consumed, or not owned by this session.")
        if plan["revision"] != scene_revision():
            fail("stale_preview", "Scene content changed after preview.")
        request = self.validate(plan["request"])
        if request["action"] == "save_copy":
            return self.save_copy(request)
        if request["action"] == "render":
            return self.start_render(request, preview_id)
        return self.execute(request)

    def execute(self, r):
        action = r["action"]
        scene = bpy.context.scene
        active = bpy.context.view_layer.objects.active
        selected = list(bpy.context.selected_objects)
        old_camera = scene.camera
        old_world = scene.world
        before = {
            k: set(getattr(bpy.data, k))
            for k in (
                "objects",
                "meshes",
                "curves",
                "cameras",
                "lights",
                "worlds",
                "materials",
                "actions",
            )
        }
        undo = []
        old_action = None
        old_slot = None
        animation_owner = None
        copied_action = None
        old_data = None
        old_slots = None
        obj = None
        created_component = None
        try:
            if action == "create_object":
                kind = r["type"]
                if kind in PRIMITIVES:
                    result = operator(kind)(**r.get("parameters", {}))
                    if "FINISHED" not in result:
                        fail("native_execution_failed", "Primitive operator did not finish.")
                    obj = bpy.context.object
                elif kind == "WORLD":
                    obj = bpy.data.worlds.new(r["name"])
                    if r.get("make_active"):
                        scene.world = obj
                else:
                    data = (
                        bpy.data.cameras.new(r["name"])
                        if kind == "CAMERA"
                        else None
                        if kind == "EMPTY"
                        else bpy.data.lights.new(r["name"], kind)
                    )
                    obj = bpy.data.objects.new(r["name"], data)
                    scene.collection.objects.link(obj)
                    if kind == "CAMERA" and r.get("make_active"):
                        scene.camera = obj
                obj.name = r["name"]
                if r.get("properties"):
                    for key, value in validated_properties(
                        obj, r["properties"], {"kind": "world" if kind == "WORLD" else "object"}
                    ).items():
                        setattr(obj, key, value)
                result = {"name": obj.name, "type": kind}
            elif action == "edit_properties":
                obj = resolve(r["target"])
                for key, value in validated_properties(obj, r["properties"], r["target"]).items():
                    undo.append((obj, key, plain(getattr(obj, key))))
                    setattr(obj, key, value)
                    actual = plain(getattr(obj, key))
                    expected = plain(value)
                    if isinstance(expected, (int, float)) and type(expected) is not bool:
                        if not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-7):
                            fail(
                                "native_verification_failed",
                                "Property read-back differs from requested value.",
                            )
                    elif (
                        isinstance(expected, list)
                        and len(actual) == len(expected)
                        and all(type(v) in (int, float) for v in expected)
                    ):
                        if not all(
                            math.isclose(x, y, rel_tol=1e-6, abs_tol=1e-7)
                            for x, y in zip(actual, expected)
                        ):
                            fail(
                                "native_verification_failed",
                                "Array read-back differs from requested value.",
                            )
                    elif actual != expected:
                        fail(
                            "native_verification_failed",
                            "Property read-back differs from requested value.",
                        )
                result = inspect_properties(r["target"])
            elif action == "create_material_graph":
                mat = bpy.data.materials.new(r["name"])
                mat.use_nodes = True
                tree = mat.node_tree
                tree.nodes.clear()
                nodes = {}
                for spec in r["nodes"]:
                    n = tree.nodes.new(spec["type"])
                    n.name = spec["id"]
                    nodes[n.name] = n
                    if spec.get("location"):
                        if (
                            not isinstance(spec["location"], list)
                            or len(spec["location"]) != 2
                            or any(
                                type(v) not in (int, float)
                                or not math.isfinite(v)
                                or abs(v) > 100000
                                for v in spec["location"]
                            )
                        ):
                            fail(
                                "invalid_arguments",
                                "Node location requires two bounded coordinates.",
                            )
                        n.location = spec["location"]
                    if spec.get("properties"):
                        for key, value in validated_properties(n, spec["properties"]).items():
                            setattr(n, key, value)
                    for direction in ("inputs", "outputs"):
                        defaults = spec.get(direction, {})
                        if not isinstance(defaults, dict) or len(defaults) > 32:
                            fail("invalid_arguments", "Use bounded socket defaults.")
                        for key, value in defaults.items():
                            pin = socket(n, direction, key)
                            prop = pin.bl_rna.properties.get("default_value")
                            if prop is None:
                                fail("invalid_socket", "Socket has no editable default.")
                            pin.default_value = validate_value(prop, value)
                    if spec.get("color_ramp"):
                        stops = spec["color_ramp"]
                        if (
                            not hasattr(n, "color_ramp")
                            or not isinstance(stops, list)
                            or not 2 <= len(stops) <= 32
                        ):
                            fail("invalid_arguments", "Color ramps need 2–32 explicit stops.")
                        if any(
                            not isinstance(s, dict)
                            or set(s) != {"position", "color"}
                            or type(s["position"]) not in (int, float)
                            or not 0 <= s["position"] <= 1
                            or not isinstance(s["color"], list)
                            or len(s["color"]) != 4
                            or any(
                                type(v) not in (int, float)
                                or not math.isfinite(v)
                                or not 0 <= v <= 1
                                for v in s["color"]
                            )
                            for s in stops
                        ):
                            fail("invalid_arguments", "Invalid color ramp stops.")
                        stops = sorted(stops, key=lambda s: s["position"])
                        ramp = n.color_ramp
                        ramp.elements[0].position = stops[0]["position"]
                        ramp.elements[0].color = stops[0]["color"]
                        ramp.elements[1].position = stops[-1]["position"]
                        ramp.elements[1].color = stops[-1]["color"]
                        for s in stops[1:-1]:
                            ramp.elements.new(s["position"]).color = s["color"]
                for spec in r.get("links", []):
                    out = socket(nodes[spec["from_node"]], "outputs", spec["from_socket"])
                    inp = socket(nodes[spec["to_node"]], "inputs", spec["to_socket"])
                    if inp.is_linked:
                        fail("invalid_graph", "Resolved duplicate input.")
                    tree.links.new(out, inp)
                if any(not edge.is_valid for edge in tree.links):
                    fail("invalid_graph", "Blender reports an invalid native shader link.")
                if r.get("assign_to"):
                    obj = scene.objects[r["assign_to"]]
                    old_slots = list(obj.data.materials)
                    obj.data.materials.append(mat)
                result = {"material": mat.name, "graph": graph_state(tree)}
            elif action in {"create_modifier", "create_constraint"}:
                obj = resolve(r["target"])
                collection = obj.modifiers if action == "create_modifier" else obj.constraints
                created_component = (
                    collection.new(r["name"], r["type"])
                    if action == "create_modifier"
                    else collection.new(r["type"])
                )
                created_component.name = r["name"]
                if r.get("properties"):
                    for key, value in validated_properties(
                        created_component, r["properties"]
                    ).items():
                        setattr(created_component, key, value)
                if r.get("assign_to"):
                    if action != "create_constraint" or not hasattr(created_component, "target"):
                        fail(
                            "unsupported_operation",
                            "This component has no explicit target binding.",
                        )
                    target = scene.objects.get(r["assign_to"])
                    if target is None:
                        fail("target_not_found", "Constraint target object not found.")
                    created_component.target = target
                result = {
                    "object": obj.name,
                    "component": created_component.name,
                    "type": created_component.type,
                    "properties": property_values(created_component),
                }
            elif action == "mesh_operator":
                obj = resolve(r["target"])
                old_data = obj.data
                obj.data = old_data.copy()
                for o in bpy.context.selected_objects:
                    o.select_set(False)
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                op = operator(r["type"])
                if not op.poll():
                    fail("context_not_supported", "Operator cannot run in this Blender context.")
                status = op(**r.get("parameters", {}))
                bpy.ops.object.mode_set(mode="OBJECT")
                if "FINISHED" not in status:
                    fail("native_execution_failed", "Mesh operator did not finish.")
                if len(obj.data.vertices) > 250000:
                    fail("geometry_limit", "Mesh result exceeds limits; original mesh restored.")
                result = {
                    "object": obj.name,
                    "operator": r["type"],
                    "vertices": len(obj.data.vertices),
                    "faces": len(obj.data.polygons),
                    "original_mesh_preserved": old_data.name,
                }
                old_data.use_fake_user = True
            elif action == "keyframe":
                obj = resolve(r["target"])
                animation_owner = obj.id_data
                data = animation_owner.animation_data_create()
                old_action = data.action
                old_slot = getattr(data, "action_slot", None)
                copied_action = old_action.copy() if old_action else None
                if copied_action:
                    data.action = copied_action
                    if old_slot and hasattr(data, "action_slot"):
                        data.action_slot = copied_action.slots.get(old_slot.identifier)
                for key in r["keyframes"]:
                    prop = key["property"]
                    value = validate_value(obj.bl_rna.properties[prop], key["value"])
                    undo.append((obj, prop, plain(getattr(obj, prop))))
                    setattr(obj, prop, value)
                    if not obj.keyframe_insert(data_path=prop, frame=key["frame"]):
                        fail("native_execution_failed", "Native keyframe insertion failed.")
                # Reevaluate original frame rather than leave the last inserted key's value active.
                scene.frame_set(scene.frame_current)
                if old_action:
                    old_action.use_fake_user = True
                result = {
                    "target": r["target"],
                    "keys_inserted": len(r["keyframes"]),
                    "action": data.action.name,
                    "original_action_preserved": old_action.name if old_action else None,
                }
            else:
                fail("unsupported_operation", "Unsupported creative edit.")
            return {"state": "completed", "action": action, "result": result, "blend_saved": False}
        except Exception as error:
            try:
                if bpy.context.mode != "OBJECT":
                    bpy.ops.object.mode_set(mode="OBJECT")
                for target, key, value in reversed(undo):
                    prop = target.bl_rna.properties[key]
                    setattr(
                        target,
                        key,
                        set(value) if prop.type == "ENUM" and prop.is_enum_flag else value,
                    )
                if animation_owner:
                    animation_owner.animation_data.action = old_action
                    if (
                        old_action
                        and old_slot
                        and hasattr(animation_owner.animation_data, "action_slot")
                    ):
                        animation_owner.animation_data.action_slot = old_slot
                if old_data:
                    obj.data = old_data
                if old_slots is not None:
                    obj.data.materials.clear()
                    for m in old_slots:
                        obj.data.materials.append(m)
                if created_component:
                    (obj.modifiers if action == "create_modifier" else obj.constraints).remove(
                        created_component
                    )
                scene.camera = old_camera
                scene.world = old_world
                for kind, items in before.items():
                    collection = getattr(bpy.data, kind)
                    for item in set(collection) - items:
                        collection.remove(item, do_unlink=True)
            except Exception:
                fail(
                    "rollback_failed",
                    "Native operation failed and rollback could not be verified; inspect scene before retrying.",
                )
            if isinstance(error, RecipeError):
                raise
            fail(
                "native_execution_failed",
                "Native operation failed; original data restored. Inspect the native parameter schema.",
            )
        finally:
            if bpy.context.mode == "OBJECT":
                for o in bpy.context.selected_objects:
                    o.select_set(False)
                for o in selected:
                    if o.name in scene.objects:
                        o.select_set(True)
                bpy.context.view_layer.objects.active = (
                    active if active and active.name in scene.objects else None
                )

    def save_copy(self, r):
        dest = new_file(r["path"])
        original = bpy.data.filepath
        # Exclusive reservation prevents a late competing write from being overwritten.
        with dest.open("xb"):
            pass
        try:
            status = bpy.ops.wm.save_as_mainfile(
                filepath=str(dest),
                copy=True,
                compress=False,
                check_existing=False,
                relative_remap=False,
            )
            if (
                "FINISHED" not in status
                or not dest.is_file()
                or dest.stat().st_size < 12
                or bpy.data.filepath != original
            ):
                fail("save_failed", "Native save-copy did not verify.")
            with dest.open("rb") as f:
                if f.read(7) != b"BLENDER":
                    fail("save_failed", "Native output is not an uncompressed Blender file.")
            return {
                "state": "saved",
                "path": str(dest),
                "bytes": dest.stat().st_size,
                "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                "active_file_unchanged": True,
                "reopen_verified": False,
            }
        except Exception:
            # Retain failed native output for diagnosis, never silently replay a save.
            fail(
                "save_failed",
                "Save-copy failed. Inspect the destination before retrying; any partial output is retained.",
            )

    def start_render(self, r, pid):
        if sum(job["process"].poll() is None for job in self.jobs.values()) >= 2:
            fail("render_busy", "At most two render jobs may run concurrently.")
        self.root.mkdir(parents=True, exist_ok=True)
        protect_path(self.root)
        folder = self.root / pid
        folder.mkdir()
        protect_path(folder)
        snapshot = folder / "scene.blend"
        self.save_copy({"path": str(snapshot)})
        # Frame output is private to the new job. Neither the user's scene nor preferences are changed.
        scene = bpy.context.scene
        command = [
            bpy.app.binary_path,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            str(snapshot),
            "--scene",
            scene.name,
            "--render-output",
            str(folder / "frame_"),
            "--render-format",
            "PNG",
            "--use-extension",
            "1",
            "--frame-start",
            str(r.get("frame_start", 1)),
            "--frame-end",
            str(r.get("frame_end", 1)),
            "--frame-jump",
            "1",
            "--render-anim",
        ]
        log = (folder / "render.log").open("wb")
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except OSError:
            log.close()
            fail("render_start_failed", "Background Blender could not start; snapshot retained.")
        log.close()
        self.jobs[pid] = {
            "process": process,
            "folder": folder,
            "start": r.get("frame_start", 1),
            "end": r.get("frame_end", 1),
            "width": scene.render.resolution_x * scene.render.resolution_percentage // 100,
            "height": scene.render.resolution_y * scene.render.resolution_percentage // 100,
            "cancelled": False,
        }
        receipt = {
            "job_id": pid,
            "state": "running",
            "directory": str(folder),
            "snapshot": str(snapshot),
            "frames": [self.jobs[pid]["start"], self.jobs[pid]["end"]],
            "scene": scene.name,
        }
        (folder / "job.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        return receipt

    def job_info(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch("[0-9a-f]{32}", job_id):
            fail("invalid_arguments", "Use an exact render job ID.")
        job = self.jobs.get(job_id)
        if job is None:
            fail(
                "job_not_found",
                "Render job not owned by this adapter lifetime. Retained files are not replayed.",
            )
        code = job["process"].poll()
        valid = []
        invalid = []
        for frame in range(job["start"], job["end"] + 1):
            p = job["folder"] / f"frame_{frame:04d}.png"
            if p.exists():
                with p.open("rb") as f:
                    header = f.read(24)
                if (
                    len(header) == 24
                    and header[:8] == b"\x89PNG\r\n\x1a\n"
                    and struct.unpack(">II", header[16:24]) == (job["width"], job["height"])
                ):
                    valid.append(frame)
                else:
                    invalid.append(frame)
        expected = job["end"] - job["start"] + 1
        state = (
            ("cancelling" if job["cancelled"] else "running")
            if code is None
            else "cancelled"
            if job["cancelled"]
            else "completed"
            if code == 0 and len(valid) == expected and not invalid
            else "failed"
        )
        info = {
            "job_id": job_id,
            "state": state,
            "exit_code": code,
            "completed_frames": len(valid),
            "expected_frames": expected,
            "resolution": [job["width"], job["height"]],
            "invalid_frames": invalid,
            "directory": str(job["folder"]),
            "log": str(job["folder"] / "render.log"),
            "visual_verified": False,
            "decode_verified": False,
        }
        return info

    def cancel_job(self, job_id, confirmation):
        if confirmation != job_id:
            fail("confirmation_required", "Cancel confirmation must equal the inspected job_id.")
        info = self.job_info(job_id)
        job = self.jobs[job_id]
        if info["state"] == "running":
            job["cancelled"] = True
            job["process"].terminate()
        return self.job_info(job_id)
