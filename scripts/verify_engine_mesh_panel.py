"""Verify Engine sphere export and the panel worker in disposable Unreal/Blender processes."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_transfer_workflow_mcp import hidden, ready
from server.core.connections import BridgeError, ConnectionManager

PROBE = '''
import os, sys, time
from pathlib import Path
sys.path.insert(0, os.environ['FORGE_ADDON_ROOT'])
import majestic_forge
majestic_forge.register()
try:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline and not Path(os.environ['FORGE_STOP_FILE']).exists():
        majestic_forge._bridge.tick()
        time.sleep(0.01)
finally:
    majestic_forge.unregister()
'''


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if not relative.parts[0].startswith("AlphaValidation-"):
        raise ValueError("Use an isolated alpha validation host")
    root = project.parent / "Saved" / ("EnginePanelAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    stop = root / "stop"
    probe = root / "probe.py"
    probe.write_text(PROBE)
    isolated_local_app_data = root / "LocalAppData"
    sessions = isolated_local_app_data / "MajesticForge" / "sessions"
    sessions.mkdir(parents=True)
    env = {**os.environ, "LOCALAPPDATA": str(isolated_local_app_data),
           "FORGE_UNREAL_SESSION_DIR": str(sessions),
           "FORGE_BLENDER_SESSION_DIR": str(sessions), "FORGE_STOP_FILE": str(stop),
           "FORGE_ADDON_ROOT": str(repository / "blender-addon"),
           "BLENDER_USER_CONFIG": str(root / "blender-config"),
           "BLENDER_USER_SCRIPTS": str(root / "blender-scripts")}
    manager = ConnectionManager([Path(env["FORGE_UNREAL_SESSION_DIR"]), sessions], timeout=30)
    processes, logs = [], []
    print(f"Evidence: {root}", flush=True)
    try:
        for name, command in (
            ("blender", [str(args.blender.resolve(strict=True)), "--background", "--factory-startup",
                         "--python-exit-code", "1", "--python", str(probe)]),
            ("unreal", [str(args.editor.resolve(strict=True)), str(project),
                        "/Engine/Maps/Templates/Template_Default", "-Unattended", "-NullRHI",
                        "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
                        "-ExecCmds=Automation RunTests ForgeMCP.Transfer.EngineSource",
                        f"-abslog={root / 'unreal.log'}"]),
        ):
            log = (root / f"{name}-launch.log").open("w")
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=root, env=env, stdout=log,
                                              stderr=subprocess.STDOUT, **hidden()))
        blender = await ready(manager, processes[0], "blender")
        unreal = await ready(manager, processes[1], "unreal")
        info = await manager.request(unreal, "project_info")
        assert Path(info["project_file"]).resolve() == project
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                await manager.request(unreal, "mesh_export_preview", {
                    "asset_path": "/Engine/BasicShapes/Sphere.Sphere", "format": "fbx"})
                break
            except BridgeError as error:
                if error.code != "unsupported_source":
                    raise
            await asyncio.sleep(0.2)
        else:
            raise AssertionError("Native automation did not load the engine sphere")
        report = {"project": info, "user_scenes_modified": False, "interactive_verified": False}
        for format_ in ("fbx", "obj"):
            name = "EngineSphere_" + format_
            worker_log = (root / f"worker-{format_}.log").open("w")
            logs.append(worker_log)
            worker = await asyncio.create_subprocess_exec(sys.executable, "-m", "server.ui_transfer",
                cwd=repository, env=env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=worker_log, **hidden())
            try:
                intent = {"mode": "send_to_blender", "unreal_project_file": str(project),
                          "source_session_id": unreal.session_id, "target_session_id": blender.session_id,
                          "source_asset_path": "/Engine/BasicShapes/Sphere.Sphere",
                          "target_object": name, "format": format_}
                worker.stdin.write((json.dumps(intent) + "\n").encode())
                await worker.stdin.drain()
                preview = json.loads(await asyncio.wait_for(worker.stdout.readline(), 60))
                assert preview["state"] == "preview", preview
                operation = preview["preview"]["preview_id"]
                worker.stdin.write((json.dumps({"confirmation": operation}) + "\n").encode())
                await worker.stdin.drain()
                applying = json.loads(await asyncio.wait_for(worker.stdout.readline(), 60))
                assert applying["state"] == "applying", applying
                result = json.loads(await asyncio.wait_for(worker.stdout.readline(), 120))
                assert result["state"] == "completed", result
                await asyncio.wait_for(worker.wait(), 30)
                mesh = await manager.request(blender, "object_info", {"name": name})
                assert mesh["name"] == name and mesh["type"] == "MESH"
                report[format_] = {"preview": preview, "result": result, "object": mesh}
            finally:
                if worker.returncode is None:
                    # Cancellation requests never replay an uncertain apply.
                    worker.stdin.close()
                    await asyncio.wait_for(worker.wait(), 30)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            native_log = (root / "unreal.log").read_text(errors="replace")
            if "Result={Success}" in native_log and "EngineSource" in native_log:
                break
            assert "Result={Fail}" not in native_log, "Native engine export automation failed"
            await asyncio.sleep(0.2)
        else:
            raise AssertionError("Native engine export automation did not complete")
        report["native_engine_export_automation_passed"] = True
        (root / "acceptance.json").write_text(json.dumps(report, indent=2))
        print("FORGEMCP_ENGINE_SPHERE_PANEL_FBX_OBJ_PASS", flush=True)
    finally:
        stop.touch()
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, timeout=10)
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
