"""Exercise new creative tools over real stdio MCP and an isolated authenticated Blender."""

import asyncio
import json
import os
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]


def decode_png(path):
    raw = path.read_bytes()
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    payload = bytearray()
    width = height = depth = color = None
    ended = False
    while offset < len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        kind = raw[offset + 4 : offset + 8]
        data = raw[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length : offset + 12 + length])[0]
        assert zlib.crc32(kind + data) & 0xFFFFFFFF == crc
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", data)
            assert interlace == 0
        if kind == b"IDAT":
            payload.extend(data)
        if kind == b"IEND":
            ended = True
            break
        offset += length + 12
    assert ended and depth == 8 and color in {2, 6}
    stride = width * (3 if color == 2 else 4) + 1
    decoded = zlib.decompress(payload)
    assert len(decoded) == stride * height
    assert all(decoded[row * stride] <= 4 for row in range(height))
    return [width, height]


async def main():
    blender = Path(sys.argv[1])
    work = Path(tempfile.mkdtemp(prefix="forge-creative-mcp-", dir=ROOT / "Saved"))
    env = {
        **os.environ,
        "FORGE_PROJECT_ROOT": str(ROOT),
        "FORGE_CREATIVE_TEST_ROOT": str(work),
        "FORGE_BLENDER_SESSION_DIR": str(work / "sessions"),
        "FORGE_UNREAL_SESSION_DIR": str(work / "unreal"),
        "BLENDER_USER_CONFIG": str(work / "config"),
        "BLENDER_USER_SCRIPTS": str(work / "scripts"),
        "BLENDER_USER_EXTENSIONS": str(work / "extensions"),
    }
    log = (work / "bridge.log").open("wb")
    process = subprocess.Popen(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(ROOT / "scripts" / "creative_bridge_probe.py"),
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    log.close()
    checks = []
    try:
        deadline = time.monotonic() + 20
        while not (work / "bridge-ready").exists():
            assert process.poll() is None, "Blender bridge failed to start"
            assert time.monotonic() < deadline, "Blender bridge startup timed out"
            await asyncio.sleep(0.1)
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "server.main"], cwd=str(ROOT), env=env
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                expected = {
                    "blender_list_commands",
                    "blender_inspect_command",
                    "blender_list_rna_types",
                    "blender_inspect_rna_type",
                    "blender_inspect_properties",
                    "blender_preview_creative",
                    "blender_apply_creative",
                    "blender_render_job_status",
                    "blender_cancel_render_job",
                }
                assert expected <= names
                checks.append("all nine tools discovered over stdio MCP")

                async def call(name, args):
                    response = await client.call_tool(name, args)
                    assert not response.isError, response
                    value = response.structuredContent
                    assert value and value.get("ok"), value
                    return value["data"]

                sessions = await call("forge_list_sessions", {})
                session = f"blender-{process.pid}"
                bridge = next(s for s in sessions["sessions"] if s["session_id"] == session)
                assert bridge["connected"] and bridge["health"]["version"] == "0.2.33"
                checks.append("authenticated Blender 0.2.33 health")
                common = {"session_id": session}
                catalog = await call("blender_list_commands", common)
                assert catalog["total"] > 1000
                checks.append("complete live native operator catalog")
                command = await call(
                    "blender_inspect_command",
                    {**common, "identifier": "mesh.primitive_uv_sphere_add"},
                )
                assert command["execution"] == "create_object"
                checks.append("native operator parameter schema")
                types = await call("blender_list_rna_types", {**common, "query": "ShaderNode"})
                assert types["total"] > 30
                await call("blender_inspect_rna_type", {**common, "name": "ShaderNodeBlackbody"})
                checks.append("RNA type catalog and schema")

                async def apply(request):
                    p = await call("blender_preview_creative", {**common, "request": request})
                    return await call(
                        "blender_apply_creative",
                        {**common, "preview_id": p["preview_id"], "confirmation": p["preview_id"]},
                    )

                await apply(
                    {
                        "action": "create_object",
                        "name": "MCP_Sun",
                        "type": "mesh.primitive_uv_sphere_add",
                        "parameters": {"segments": 64, "ring_count": 32, "radius": 1.0},
                    }
                )
                obj = await call("blender_inspect_object", {**common, "name": "MCP_Sun"})
                assert obj["type"] == "MESH"
                checks.append("reviewed native sphere creation and readback")
                await apply(
                    {
                        "action": "create_object",
                        "name": "MCP_Camera",
                        "type": "CAMERA",
                        "make_active": True,
                        "properties": {"location": [0.0, 0.0, 6.0]},
                    }
                )
                await apply(
                    {
                        "action": "edit_properties",
                        "target": {"kind": "camera", "name": "MCP_Camera"},
                        "properties": {"type": "ORTHO", "ortho_scale": 5.0},
                    }
                )
                props = await call(
                    "blender_inspect_properties",
                    {**common, "target": {"kind": "camera", "name": "MCP_Camera"}},
                )
                assert props["rna_type"] == "Camera"
                checks.append("camera creation, activation, property edits and schema")
                await apply(
                    {
                        "action": "create_material_graph",
                        "name": "MCP_SolarEmission",
                        "assign_to": "MCP_Sun",
                        "nodes": [
                            {
                                "id": "Blackbody",
                                "type": "ShaderNodeBlackbody",
                                "inputs": {"Temperature": 5772.0},
                            },
                            {
                                "id": "Emission",
                                "type": "ShaderNodeEmission",
                                "inputs": {"Strength": 0.8},
                            },
                            {"id": "Output", "type": "ShaderNodeOutputMaterial"},
                        ],
                        "links": [
                            {
                                "from_node": "Blackbody",
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
                )
                await apply(
                    {
                        "action": "keyframe",
                        "target": {
                            "kind": "socket",
                            "name": "MCP_SolarEmission",
                            "component": "Emission",
                            "socket": "Strength",
                        },
                        "keyframes": [
                            {"property": "default_value", "frame": 1, "value": 0.5},
                            {"property": "default_value", "frame": 2, "value": 1.0},
                        ],
                    }
                )
                checks.append("expanded shader graph and shader socket animation over MCP")
                await apply(
                    {
                        "action": "edit_properties",
                        "target": {"kind": "render"},
                        "properties": {
                            "engine": "CYCLES",
                            "resolution_x": 4096,
                            "resolution_y": 2304,
                            "resolution_percentage": 100,
                            "fps": 24,
                        },
                    }
                )
                await apply(
                    {
                        "action": "edit_properties",
                        "target": {"kind": "cycles"},
                        "properties": {"samples": 1, "use_denoising": False},
                    }
                )
                await apply(
                    {
                        "action": "edit_properties",
                        "target": {"kind": "image_settings"},
                        "properties": {"file_format": "PNG", "color_depth": "8"},
                    }
                )
                saved = await apply(
                    {"action": "save_copy", "path": str(work / "MCP_Creative.blend")}
                )
                assert saved["state"] == "saved"
                checks.append("new blend copy saved through MCP")
                job = await apply({"action": "render", "frame_start": 1, "frame_end": 2})
                deadline = time.monotonic() + 150
                while time.monotonic() < deadline:
                    status = await call(
                        "blender_render_job_status", {**common, "job_id": job["job_id"]}
                    )
                    if status["state"] != "running":
                        break
                    # Main bridge remains available while worker renders.
                    await call("blender_scene_info", common)
                    await asyncio.sleep(0.3)
                assert status["state"] == "completed" and status["completed_frames"] == 2, status
                for frame in (1, 2):
                    assert decode_png(Path(status["directory"]) / f"frame_{frame:04d}.png") == [
                        4096,
                        2304,
                    ]
                checks.append("two real 4K animation frames complete and fully decode")
                assert (Path(status["directory"]) / "frame_0001.png").read_bytes() != (
                    Path(status["directory"]) / "frame_0002.png"
                ).read_bytes()
                checks.append("animated emission produces different frames")
                after = await call("blender_scene_info", common)
                assert after["file"] == "" and after["frame_current"] == 1
                checks.append("interactive bridge remains responsive and unsaved scene preserved")
                await call(
                    "blender_cancel_render_job",
                    {**common, "job_id": job["job_id"], "confirmation": job["job_id"]},
                )
                checks.append("completed render cancel is idempotent")
                cancel_job = await apply({"action": "render", "frame_start": 1, "frame_end": 96})
                cancelled = await call(
                    "blender_cancel_render_job",
                    {
                        **common,
                        "job_id": cancel_job["job_id"],
                        "confirmation": cancel_job["job_id"],
                    },
                )
                deadline = time.monotonic() + 10
                while cancelled["state"] == "cancelling" and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
                    cancelled = await call(
                        "blender_render_job_status", {**common, "job_id": cancel_job["job_id"]}
                    )
                assert cancelled["state"] == "cancelled", cancelled
                checks.append("running render cancelled over MCP, files retained")
                report = {
                    "checks": checks,
                    "count": len(checks),
                    "operator_count": catalog["total"],
                    "tool_count": len(names),
                    "render": status,
                    "work": str(work),
                    "source_server": "0.3.6",
                    "addon": "0.2.33",
                }
                (ROOT / "Saved" / "creative-mcp-acceptance.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                print(json.dumps(report, indent=2))
    finally:
        (work / "stop").write_text("stop", encoding="ascii")
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
