"""Load a packaged ForgeMCP plugin in a fresh disposable Blueprint-only project."""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.core.connections import BridgeError, ConnectionManager


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    archive_path = args.archive.resolve(strict=True)
    root = repository / "Saved" / ("UnrealPackageAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    project = root / "ForgePackageTest.uproject"
    project.write_text(json.dumps({"FileVersion": 3, "EngineAssociation": "5.6",
                                  "Plugins": []}), encoding="utf-8")
    installed = await asyncio.to_thread(subprocess.run, ["powershell", "-NoProfile",
        "-ExecutionPolicy", "Bypass", "-File", str(repository / "scripts/Install-ForgeUnreal.ps1"),
        "-ProjectFile", str(project), "-PackageArchive", str(archive_path)],
        capture_output=True, text=True, timeout=60)
    (root / "install.log").write_text(installed.stdout + installed.stderr, encoding="utf-8")
    assert installed.returncode == 0, f"Installer failed; inspect {root}"
    installed_project = json.loads(project.read_text(encoding="utf-8-sig"))
    assert any(p["Name"] == "MajesticForge" and p["Enabled"] for p in installed_project["Plugins"])
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    manager = ConnectionManager([root / "Saved" / "MajesticForge"], timeout=15)
    print(f"Evidence: {root}", flush=True)
    with (root / "launch.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(args.editor.resolve(strict=True)), str(project),
            "-Unattended", "-NullRHI", "-NoSplash", "-NoSound", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'unreal.log'}"], cwd=root, stdout=log,
            stderr=subprocess.STDOUT, startupinfo=startup)
        try:
            deadline = time.monotonic() + 180
            report = None
            while process.poll() is None and time.monotonic() < deadline:
                for session in manager.discover():
                    if session.pid != process.pid:
                        continue
                    try:
                        health = await manager.request(session, "health")
                        info = await manager.request(session, "project_info")
                    except BridgeError:
                        continue
                    assert Path(info["project_file"]).resolve() == project
                    assert health["transfer_contract_version"] == 1
                    assert {"mesh_import_preview", "mesh_import_apply", "mesh_info",
                            "level_save_preview", "level_save_apply"} <= set(health["capabilities"])
                    module_query = await asyncio.to_thread(subprocess.run, [
                        "powershell", "-NoProfile", "-Command",
                        f"(Get-Process -Id {process.pid}).Modules | Where-Object {{$_.ModuleName -eq 'UnrealEditor-MajesticForge.dll'}} | Select-Object -ExpandProperty FileName"],
                        capture_output=True, text=True, timeout=20)
                    assert module_query.returncode == 0, module_query.stderr
                    module_path = Path(module_query.stdout.strip()).resolve()
                    assert module_path == root / "Plugins/MajesticForge/Binaries/Win64/UnrealEditor-MajesticForge.dll"
                    report = {"package_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                              "blueprint_only_project": True, "native_plugin_loaded": True,
                              "installer_verified": True,
                              "loaded_binary_path": str(module_path), "interactive_verified": False,
                              "health": health, "project": info}
                    break
                if report:
                    break
                await asyncio.sleep(0.2)
            assert report is not None, f"Packaged plugin did not become ready; inspect {root}"
            (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print("FORGEMCP_CLEAN_PROJECT_PACKAGED_UNREAL_PLUGIN_LOAD_PASS", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                await asyncio.to_thread(process.wait, timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
