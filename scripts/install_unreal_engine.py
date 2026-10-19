"""Install a validated ForgeMCP archive engine-wide, with reversible directory swaps."""

import argparse
import json
import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path

try:
    from scripts.extract_unreal_package import extract
except ModuleNotFoundError:
    from extract_unreal_package import extract


def reject_links(path: Path):
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Installation paths must not contain links or reparse points")


def engine_editors(engine: Path) -> list:
    """Conservatively reject updates when any editor from this engine is open."""
    if os.name != "nt":
        raise OSError("Engine-wide binary installation requires Windows")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "@(Get-CimInstance Win32_Process | Where-Object { "
         "$_.Name -in @('UnrealEditor.exe','UnrealEditor-Cmd.exe') } | "
         "Select-Object ProcessId,ExecutablePath) | ConvertTo-Json -Compress"],
        capture_output=True, text=True, check=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    entries = json.loads(result.stdout.strip() or "[]")
    if isinstance(entries, dict):
        entries = [entries]
    return [entry for entry in entries if not entry.get("ExecutablePath") or
            Path(entry["ExecutablePath"]).is_relative_to(engine)]


def install(archive: Path, engine: Path, *, update: bool = False) -> dict:
    reject_links(engine.absolute())
    engine = engine.resolve(strict=True)
    version = json.loads((engine / "Engine/Build/Build.version").read_text())
    if tuple(version[k] for k in ("MajorVersion", "MinorVersion", "PatchVersion")) != (5, 6, 1):
        raise ValueError("This alpha binary package requires Unreal Engine 5.6.1")
    destination = engine / "Engine/Plugins/Marketplace/Forge"
    legacy_destination = engine / "Engine/Plugins/Marketplace/MajesticForge"
    reject_links(destination)
    reject_links(legacy_destination)
    # The plugin descriptor/module IDs stay MajesticForge for compatibility;
    # only the installed plugin directory moves to Forge.
    if destination.exists() and legacy_destination.exists():
        raise FileExistsError("Both Forge and legacy MajesticForge engine plugin folders exist")
    previous = destination if destination.exists() else legacy_destination if legacy_destination.exists() else None
    if previous is not None and not update:
        raise FileExistsError("Engine plugin exists; use --update for a backed-up replacement")
    if previous is not None:
        existing = json.loads((previous / "MajesticForge.uplugin").read_text())
        if existing.get("FriendlyName") != "ForgeMCP":
            raise ValueError("Destination is not a recognized ForgeMCP installation")
        if engine_editors(engine):
            raise RuntimeError("Save and close editors using this engine before updating ForgeMCP")
    for descriptor in (engine / "Engine/Plugins").rglob("MajesticForge.uplugin"):
        if descriptor.parent not in {destination, legacy_destination}:
            raise ValueError(f"Another engine copy exists: {descriptor.parent}")
    identity = uuid.uuid4().hex
    staging = engine / "Engine/Saved/ForgeMCPInstallStaging" / identity
    backup = engine / "Engine/Saved/ForgeMCPInstallBackups" / identity / (previous.name if previous else "PreviousPlugin")
    reject_links(staging)
    reject_links(backup)
    moved_previous_from = None
    installed_new = False
    try:
        plugin = extract(archive.resolve(strict=True), staging)
        manifest = json.loads((staging / "package-manifest.json").read_text())
        descriptor = json.loads((plugin / "MajesticForge.uplugin").read_text())
        modules = json.loads((plugin / "Binaries/Win64/UnrealEditor.modules").read_text())
        engine_modules = json.loads((engine / "Engine/Binaries/Win64/UnrealEditor.modules").read_text())
        if (descriptor.get("FriendlyName") != "ForgeMCP" or
                descriptor.get("EnabledByDefault") is not True or
                descriptor.get("VersionName") != manifest.get("plugin_version")):
            raise ValueError("Expected an explicitly enabled ForgeMCP package with matching version")
        if (not modules.get("BuildId") or modules["BuildId"] != engine_modules.get("BuildId") or
                modules["BuildId"] != manifest.get("engine_build_id")):
            raise ValueError("Package BuildId does not match this engine; rebuild before installing")
        expected_modules = {name: f"UnrealEditor-{name}.dll"
                            for name in ("MajesticForge", "MajesticForgeRuntime")}
        if modules.get("Modules") != expected_modules:
            raise ValueError("Unexpected plugin module manifest")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if previous is not None:
            backup.parent.mkdir(parents=True, exist_ok=False)
            previous.rename(backup)
            moved_previous_from = previous
        plugin.rename(destination)
        installed_new = True
        receipt = {"installation_scope": "engine", "plugin_version": descriptor["VersionName"],
                   "engine_build_id": modules["BuildId"], "destination": str(destination),
                   "backup": str(backup) if moved_previous_from is not None else None,
                   "package_manifest": manifest, "project_files_modified": False}
        (destination / "forge-install-receipt.json").write_text(json.dumps(receipt, indent=2))
        return receipt
    except BaseException:
        if installed_new:
            destination.rename(staging / "failed-install")
        if moved_previous_from is not None:
            backup.rename(moved_previous_from)
        raise
    finally:
        # Only this invocation's unique, validated staging directory is removed.
        if staging.exists():
            shutil.rmtree(staging)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    result = install(args.archive, args.engine, update=args.update)
    print(json.dumps({k: v for k, v in result.items() if k != "package_manifest"}, indent=2))
    print("Enable ForgeMCP in Edit > Plugins, restart the project, then open Window > ForgeMCP.")
