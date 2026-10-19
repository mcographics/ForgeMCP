"""Disposable native acceptance for creative workflows; never run in a user scene."""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge.automation import RecipeError
from majestic_forge.creative import (
    CreativeAutomation,
    inspect_command,
    inspect_properties,
    inspect_type,
    list_commands,
    list_types,
)

root = Path(tempfile.mkdtemp(prefix="forge-creative-"))
a = CreativeAutomation(root / "renders")
checks = []


def check(label, value):
    assert value, label
    checks.append(label)


def apply(r):
    p = a.preview(r)
    return a.apply(p["preview_id"], p["preview_id"])


def reject(label, callback, code):
    try:
        callback()
    except RecipeError as e:
        check(label, e.code == code)
    else:
        raise AssertionError(label)


check("operator catalog exposes every registered namespace", list_commands()["total"] > 1000)
check("catalog pagination", len(list_commands(limit=2)["commands"]) == 2)
check(
    "schema discovered",
    any(
        p["identifier"] == "segments"
        for p in inspect_command("mesh.primitive_uv_sphere_add")["parameters"]
    ),
)
check(
    "unsafe command discovery only",
    inspect_command("wm.open_mainfile")["execution"] == "discovery_only",
)
check("native type catalog", list_types(query="ShaderNode")["total"] > 30)
check("native blackbody schema", inspect_type("ShaderNodeBlackbody")["node_creation_supported"])
reject(
    "no arbitrary commands",
    lambda: apply({"action": "create_object", "name": "Bad", "type": "wm.open_mainfile"}),
    "unsupported_operation",
)
reject("no python injection", lambda: inspect_command("__import__.os"), "invalid_arguments")

before = len(bpy.data.objects)
p = a.preview(
    {
        "action": "create_object",
        "name": "TestSun",
        "type": "mesh.primitive_uv_sphere_add",
        "parameters": {"segments": 128, "ring_count": 64, "radius": 1.0},
    }
)
check("preview is read only", len(bpy.data.objects) == before)
reject("wrong confirmation", lambda: a.apply(p["preview_id"], "wrong"), "confirmation_required")
check("native sphere", a.apply(p["preview_id"], p["preview_id"])["state"] == "completed")
check("sphere tessellation", len(bpy.data.objects["TestSun"].data.vertices) > 7000)
reject("single use preview", lambda: a.apply(p["preview_id"], p["preview_id"]), "preview_not_found")

apply(
    {
        "action": "create_object",
        "name": "ReviewCamera",
        "type": "CAMERA",
        "make_active": True,
        "properties": {"location": [0.0, 0.0, 6.0]},
    }
)
cam = {"kind": "camera", "name": "ReviewCamera"}
apply(
    {
        "action": "edit_properties",
        "target": cam,
        "properties": {"type": "ORTHO", "ortho_scale": 5.0},
    }
)
check("camera active", bpy.context.scene.camera.name == "ReviewCamera")
check(
    "camera schema and value",
    any(
        p.get("value") == 5
        for p in inspect_properties(cam)["properties"]
        if p["identifier"] == "ortho_scale"
    ),
)
apply({"action": "create_object", "name": "ReviewLight", "type": "AREA"})
apply(
    {
        "action": "edit_properties",
        "target": {"kind": "light", "name": "ReviewLight"},
        "properties": {"energy": 500.0, "size": 3.0},
    }
)
apply(
    {
        "action": "edit_properties",
        "target": {"kind": "object", "name": "ReviewLight"},
        "properties": {"rotation_euler": [0.1, 0.2, 0.3]},
    }
)
check("native light", bpy.data.objects["ReviewLight"].data.energy == 500)

p = a.preview({"action": "edit_properties", "target": cam, "properties": {"ortho_scale": 4.5}})
bpy.data.objects["ReviewCamera"].data.lens += 1
reject("stale camera preview", lambda: a.apply(p["preview_id"], p["preview_id"]), "stale_preview")
reject(
    "block file path setter",
    lambda: a.preview(
        {"action": "edit_properties", "target": {"kind": "render"}, "properties": {"filepath": "x"}}
    ),
    "property_not_editable",
)

graph = {
    "action": "create_material_graph",
    "name": "PhysicalEmission",
    "assign_to": "TestSun",
    "nodes": [
        {"id": "Spectrum", "type": "ShaderNodeBlackbody", "inputs": {"Temperature": 5772.0}},
        {
            "id": "Noise",
            "type": "ShaderNodeTexNoise",
            "properties": {"noise_dimensions": "4D"},
            "inputs": {"Scale": 20.0, "W": 0.0},
        },
        {
            "id": "Ramp",
            "type": "ShaderNodeValToRGB",
            "color_ramp": [
                {"position": 0.0, "color": [0.1, 0.1, 0.1, 1.0]},
                {"position": 0.5, "color": [0.5, 0.5, 0.5, 1.0]},
                {"position": 1.0, "color": [1.0, 1.0, 1.0, 1.0]},
            ],
        },
        {"id": "Emission", "type": "ShaderNodeEmission", "inputs": {"Strength": 0.7}},
        {"id": "Output", "type": "ShaderNodeOutputMaterial"},
    ],
    "links": [
        {"from_node": "Noise", "from_socket": "Fac", "to_node": "Ramp", "to_socket": "Fac"},
        {
            "from_node": "Spectrum",
            "from_socket": "Color",
            "to_node": "Emission",
            "to_socket": "Color",
        },
        {
            "from_node": "Emission",
            "from_socket": "Emission",
            "to_node": "Output",
            "to_socket": "Surface",
        },
    ],
}
check("native expanded shader graph", apply(graph)["state"] == "completed")
check(
    "color ramp read back",
    len(bpy.data.materials["PhysicalEmission"].node_tree.nodes["Ramp"].color_ramp.elements) == 3,
)
bad = {
    **graph,
    "name": "RollbackMaterial",
    "nodes": graph["nodes"]
    + [{"id": "Bad", "type": "ShaderNodeMath", "properties": {"operation": "NOT_AN_ENUM"}}],
}
reject("graph failure rolls back", lambda: apply(bad), "invalid_enum")
check("failed material removed", bpy.data.materials.get("RollbackMaterial") is None)
check(
    "original material assignment preserved", len(bpy.data.objects["TestSun"].data.materials) == 1
)

target = {"kind": "socket", "name": "PhysicalEmission", "component": "Noise", "socket": "W"}
apply(
    {
        "action": "keyframe",
        "target": target,
        "keyframes": [
            {"property": "default_value", "frame": 1, "value": 0.0},
            {"property": "default_value", "frame": 2, "value": 1.0},
        ],
    }
)
tree = bpy.data.materials["PhysicalEmission"].node_tree
old_action = tree.animation_data.action
apply(
    {
        "action": "keyframe",
        "target": target,
        "keyframes": [{"property": "default_value", "frame": 2, "value": 2.0}],
    }
)
check("shader socket animation copies Action", tree.animation_data.action != old_action)
check("original Action retained", old_action.name in bpy.data.actions)
apply(
    {
        "action": "keyframe",
        "target": {"kind": "object", "name": "TestSun"},
        "keyframes": [
            {"property": "rotation_euler", "frame": 1, "value": [0.0, 0.0, 0.0]},
            {"property": "rotation_euler", "frame": 2, "value": [0.0, 0.0, 0.01]},
        ],
    }
)
check("object keyframes", bpy.data.objects["TestSun"].animation_data.action is not None)

apply(
    {
        "action": "create_modifier",
        "name": "Smooth",
        "type": "SUBSURF",
        "target": {"kind": "object", "name": "Cube"},
        "properties": {"levels": 1, "render_levels": 1},
    }
)
check("native modifier", bpy.data.objects["Cube"].modifiers.get("Smooth") is not None)
apply(
    {
        "action": "create_constraint",
        "name": "Follow",
        "type": "COPY_LOCATION",
        "target": {"kind": "object", "name": "ReviewLight"},
        "assign_to": "TestSun",
        "properties": {"influence": 0.25},
    }
)
check(
    "native constraint binding",
    bpy.data.objects["ReviewLight"].constraints["Follow"].target.name == "TestSun",
)
mesh = bpy.data.objects["Cube"].data
apply(
    {
        "action": "mesh_operator",
        "target": {"kind": "object", "name": "Cube"},
        "type": "mesh.subdivide",
        "parameters": {"number_cuts": 1},
    }
)
check(
    "mesh operator creates preserved copy",
    bpy.data.objects["Cube"].data != mesh and len(mesh.vertices) == 8,
)
reject(
    "reject unreviewed mesh operator",
    lambda: a.preview(
        {
            "action": "mesh_operator",
            "target": {"kind": "object", "name": "Cube"},
            "type": "wm.quit_blender",
        }
    ),
    "operator_not_allowed",
)

apply(
    {
        "action": "edit_properties",
        "target": {"kind": "render"},
        "properties": {
            "engine": "CYCLES",
            "resolution_x": 4096,
            "resolution_y": 2304,
            "resolution_percentage": 100,
        },
    }
)
apply(
    {
        "action": "edit_properties",
        "target": {"kind": "cycles"},
        "properties": {"samples": 1, "use_denoising": False},
    }
)
apply(
    {
        "action": "edit_properties",
        "target": {"kind": "image_settings"},
        "properties": {"file_format": "PNG", "color_depth": "8"},
    }
)
filepath = bpy.data.filepath
saved = apply({"action": "save_copy", "path": str(root / "CreativeTest.blend")})
check("new .blend saved", saved["state"] == "saved" and saved["bytes"] > 1000)
check("save copy preserves active path", bpy.data.filepath == filepath)
reject(
    "no existing file overwrite",
    lambda: a.preview({"action": "save_copy", "path": str(root / "CreativeTest.blend")}),
    "invalid_path",
)
reopened = subprocess.run(
    [
        bpy.app.binary_path,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        str(root / "CreativeTest.blend"),
        "--python-expr",
        "import bpy; assert bpy.context.scene.render.resolution_x==4096; assert bpy.data.objects.get('TestSun'); print('REOPEN_VERIFIED')",
    ],
    capture_output=True,
    text=True,
    timeout=120,
)
check("saved copy reopens", reopened.returncode == 0 and "REOPEN_VERIFIED" in reopened.stdout)
job = apply({"action": "render", "frame_start": 1, "frame_end": 1})
check("render is asynchronous job", job["state"] == "running")
deadline = time.monotonic() + 150
while time.monotonic() < deadline:
    info = a.job_info(job["job_id"])
    if info["state"] != "running":
        break
    time.sleep(0.25)
check(
    "real 4K render completion",
    info["state"] == "completed"
    and info["resolution"] == [4096, 2304]
    and info["completed_frames"] == 1,
)
check("render leaves scene filepath unchanged", bpy.data.filepath == filepath)
reject("cancel confirmation", lambda: a.cancel_job(job["job_id"], "wrong"), "confirmation_required")
check(
    "finished render cancellation does not replay",
    a.cancel_job(job["job_id"], job["job_id"])["state"] == "completed",
)

report = {
    "checks": checks,
    "count": len(checks),
    "root": str(root),
    "render": info,
    "blender": bpy.app.version_string,
}
output = Path(__file__).resolve().parents[1] / "Saved" / "creative-acceptance.json"
output.write_text(json.dumps(report, indent=2), encoding="utf-8")
print("CREATIVE_ACCEPTANCE_PASSED", json.dumps(report), flush=True)
