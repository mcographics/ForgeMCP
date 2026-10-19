"""Load a packaged ForgeMCP plugin in a fresh disposable Blueprint-only project."""

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import zipfile
from ctypes import wintypes
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from server.core.connections import BridgeError, ConnectionManager
from verify_unreal_tab_ui import validate_html


async def verify_live_mcp(repository, root, session_id, project):
    env = {**os.environ, "FORGE_PROJECT_ROOT": str(root)}
    env.pop("FORGE_UNREAL_SESSION_DIR", None)
    env.pop("FORGE_BLENDER_SESSION_DIR", None)
    env.pop("FORGE_SESSION_DIR", None)
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
        cwd=str(repository), env=env)
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            initialized = await client.initialize()
            assert initialized.serverInfo.name == "ForgeMCP"
            names = {tool.name for tool in (await client.list_tools()).tools}
            assert {"forge_status", "forge_list_sessions", "forge_ensure_connected",
                    "unreal_project_info"} <= names
            sessions = (await client.call_tool("forge_list_sessions", {})).structuredContent
            assert sessions["ok"]
            assert any(s["session_id"] == session_id and s["connected"]
                       for s in sessions["data"]["sessions"])
            ensure = (await client.call_tool("forge_ensure_connected", {
                "unreal_session_id": session_id,
            })).structuredContent
            unreal_connection = ensure.get("data", {}).get("unreal", {})
            assert unreal_connection.get("connected") and unreal_connection["session_id"] == session_id
            info = (await client.call_tool("unreal_project_info",
                                          {"session_id": session_id})).structuredContent
            assert info["ok"] and Path(info["data"]["project_file"]).resolve() == project
            return {"real_stdio_mcp": True, "connected_session_verified": True,
                    "project_identity_verified": True,
                    "blender_connected": ensure.get("data", {}).get("blender", {}).get("connected", False),
                    "registered_tool_count": len(names)}


def loaded_module_path(process_id: int, module_name: str) -> Path:
    """Find an exact loaded module using Win32 process APIs, without a shell subprocess."""
    if sys.platform != "win32":
        raise OSError("Packaged Unreal Editor verification requires Windows module enumeration.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    psapi.EnumProcessModulesEx.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.DWORD,
    ]
    psapi.EnumProcessModulesEx.restype = wintypes.BOOL
    psapi.GetModuleFileNameExW.argtypes = [
        wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD,
    ]
    psapi.GetModuleFileNameExW.restype = wintypes.DWORD
    process = kernel32.OpenProcess(0x0400 | 0x0010, False, process_id)
    if not process:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        capacity = 512
        while capacity <= 32768:
            modules = (wintypes.HMODULE * capacity)()
            needed = wintypes.DWORD()
            if not psapi.EnumProcessModulesEx(
                process, modules, ctypes.sizeof(modules), ctypes.byref(needed), 0x03,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            count = needed.value // ctypes.sizeof(wintypes.HMODULE)
            if count > capacity:
                capacity *= 2
                continue
            for module in modules[:count]:
                buffer = ctypes.create_unicode_buffer(32768)
                length = psapi.GetModuleFileNameExW(process, module, buffer, len(buffer))
                if not length:
                    continue
                if Path(buffer.value).name.casefold() == module_name.casefold():
                    return Path(buffer.value).resolve()
            raise FileNotFoundError(f"{module_name} is not loaded by process {process_id}.")
        raise OSError("The target process exceeded the bounded 32768-module inspection limit.")
    finally:
        kernel32.CloseHandle(process)


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    archive_path = args.archive.resolve(strict=True)
    with zipfile.ZipFile(archive_path) as archive:
        package_descriptor = json.loads(archive.read("Forge/MajesticForge.uplugin"))
        package_dll_hash = hashlib.sha256(archive.read(
            "Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll")).hexdigest()
        ui_entry = "Forge/Resources/ReactUI/index.html"
        if ui_entry in archive.namelist():
            validate_html(archive.read(ui_entry).decode("utf-8"))
    root = repository / "Saved" / ("UnrealPackageAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    project = root / "ForgePackageTest.uproject"
    project.write_text(json.dumps({
        "FileVersion": 3,
        "EngineAssociation": "5.6",
        # Keep unrelated engine Marketplace plugins (including Cargo) out of
        # the disposable ForgeMCP acceptance project unless explicitly needed.
        "DisableEnginePluginsByDefault": True,
        # Preserve Unreal's standard audio graph plugin while opting out of
        # other engine plugins that ForgeMCP does not depend on.
        "Plugins": [
            {"Name": "Cargo", "Enabled": False},
            {"Name": "Metasound", "Enabled": True},
            {"Name": "PluginBrowser", "Enabled": True},
            # This selects the engine-installed copy without creating a
            # project-local Plugins folder when engine plugins default off.
            {"Name": "MajesticForge", "Enabled": True, "TargetAllowList": ["Editor"]},
        ],
    }), encoding="utf-8")
    if not args.engine_plugin:
        installed = await asyncio.to_thread(subprocess.run, ["powershell", "-NoProfile",
            "-ExecutionPolicy", "Bypass", "-File", str(repository / "scripts/Install-ForgeUnreal.ps1"),
            "-ProjectFile", str(project), "-PackageArchive", str(archive_path)],
            capture_output=True, text=True, timeout=60)
        (root / "install.log").write_text(installed.stdout + installed.stderr, encoding="utf-8")
        assert installed.returncode == 0, f"Installer failed; inspect {root}"
    installed_project = json.loads(project.read_text(encoding="utf-8-sig"))
    explicit_plugin = any(p["Name"] == "MajesticForge" and p["Enabled"]
                          for p in installed_project.get("Plugins", []))
    if args.engine_plugin:
        assert package_descriptor.get("EnabledByDefault") is True and explicit_plugin
    else:
        assert explicit_plugin
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    manager = ConnectionManager.configured()
    print(f"Evidence: {root}", flush=True)
    with (root / "launch.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(args.editor.resolve(strict=True)), str(project),
            "-Unattended", "-NullRHI", "-NoSplash", "-NoSound", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'Saved' / 'Logs' / (project.stem + '.log')}"], cwd=root, stdout=log,
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
                    assert health["version"] == package_descriptor["VersionName"]
                    assert {"mesh_import_preview", "mesh_import_apply", "mesh_info",
                            "level_save_preview", "level_save_apply", "asset_property_info",
                            "asset_property_edit_preview", "asset_property_edit_apply", "editor_log",
                            "find_actors"} <= set(health["capabilities"])
                    editor_log = await manager.request(session, "editor_log", {"limit": 5})
                    assert isinstance(editor_log["lines"], list) and len(editor_log["lines"]) <= 5
                    module_path = await asyncio.to_thread(
                        loaded_module_path, process.pid, "UnrealEditor-MajesticForge.dll",
                    )
                    expected_plugin = (args.engine_plugin.resolve(strict=True) if args.engine_plugin
                                       else root / "Plugins/Forge")
                    assert module_path == expected_plugin / "Binaries/Win64/UnrealEditor-MajesticForge.dll"
                    assert hashlib.sha256(module_path.read_bytes()).hexdigest() == package_dll_hash
                    assert not args.engine_plugin or not (root / "Plugins").exists()
                    report = {"package_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                              "blueprint_only_project": True, "native_plugin_loaded": True,
                              "installer_verified": not bool(args.engine_plugin),
                              "installation_scope": "engine" if args.engine_plugin else "project",
                              "loaded_binary_path": str(module_path), "interactive_verified": False,
                              "health": health, "project": info, "editor_log": editor_log}
                    report["mcp"] = await verify_live_mcp(repository, root, session.session_id, project)
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
                try:
                    await asyncio.to_thread(process.wait, timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--engine-plugin", type=Path,
                        help="Verify this installed engine plugin without creating a project copy")
    asyncio.run(verify(parser.parse_args()))
