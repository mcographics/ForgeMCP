"""Package the current source with matching isolated Win64 development binaries."""

import argparse
import hashlib
import json
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from verify_unreal_tab_ui import validate_html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--channel", choices=("development", "alpha"), default="development")
    parser.add_argument("--source", type=Path, help="Authoritative plugin source, if kept outside this checkout")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    host = args.host.resolve(strict=True)
    relative = host.relative_to(repository / "Saved")
    if len(relative.parts) != 2 or not relative.parts[0].startswith(("TransferImportValidation-", "RoundtripValidation-", "AlphaValidation-", "EngineWideAlpha")) or relative.parts[1] != "HostProject":
        raise ValueError("Only an isolated transfer, roundtrip or alpha validation build is allowed")
    source = (args.source or repository / "Plugins" / "Forge").resolve(strict=True)
    built = host / "Plugins" / "Forge"
    assert source != built.resolve(), "Validate against a separate authoritative source directory"
    payloads = {}
    for folder in ("Source", "Config", "Resources"):
        source_files = sorted(p for p in (source / folder).rglob("*") if p.is_file())
        built_files = sorted(p.relative_to(built) for p in (built / folder).rglob("*") if p.is_file())
        assert [p.relative_to(source) for p in source_files] == built_files, "Build/source file scope mismatch"
        for path in source_files:
            assert not path.is_symlink()
            data = path.read_bytes()
            assert (built / path.relative_to(source)).read_bytes() == data, path
            payloads["Forge/" + path.relative_to(source).as_posix()] = data
    descriptor = source / "MajesticForge.uplugin"
    assert descriptor.read_bytes() == (built / descriptor.name).read_bytes()
    descriptor_data = json.loads(descriptor.read_text())
    assert descriptor_data["FriendlyName"] == "ForgeMCP"
    ui_entry = source / "Resources" / "ReactUI" / "index.html"
    if ui_entry.is_file():
        validate_html(ui_entry.read_text(encoding="utf-8"))
    plugin_version = descriptor_data["VersionName"]
    assert isinstance(plugin_version, str) and all(c.isalnum() or c in ".-" for c in plugin_version)
    if args.channel == "alpha":
        assert "-alpha." in plugin_version and descriptor_data.get("EnabledByDefault") is True
    payloads["Forge/MajesticForge.uplugin"] = descriptor.read_bytes()
    payloads["Forge/LICENSE.txt"] = (source / "LICENSE.txt").read_bytes()
    modules_path = built / "Binaries" / "Win64" / "UnrealEditor.modules"
    modules = json.loads(modules_path.read_text())
    engine_version = json.loads((args.engine / "Engine/Build/Build.version").read_text())
    assert (engine_version["MajorVersion"], engine_version["MinorVersion"], engine_version["PatchVersion"]) == (5, 6, 1), "Package naming requires Unreal 5.6.1"
    engine_modules = json.loads((args.engine / "Engine/Binaries/Win64/UnrealEditor.modules").read_text())
    assert modules["BuildId"] == engine_modules["BuildId"], "Editor BuildId mismatch"
    assert set(modules["Modules"]) == {"MajesticForge", "MajesticForgeRuntime"}
    for module, filename in modules["Modules"].items():
        assert filename == f"UnrealEditor-{module}.dll"
        binary = modules_path.parent / filename
        assert binary.stat().st_mtime >= max(p.stat().st_mtime for p in (built / "Source" / module).rglob("*") if p.is_file()), "Binary predates its module source"
        payloads["Forge/Binaries/Win64/" + filename] = binary.read_bytes()
    payloads["Forge/Binaries/Win64/UnrealEditor.modules"] = modules_path.read_bytes()
    manifest = {"package_kind": "development_editor_plugin", "platform": "Win64",
                "plugin_version": plugin_version, "release_channel": args.channel,
                "installation_scopes": ["project", "engine"],
                "engine_version": "5.6.1",
                "engine_build_id": modules["BuildId"], "source_matches_isolated_build": True,
                "interactive_acceptance_complete": False,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()}}
    payloads["package-manifest.json"] = json.dumps(manifest, indent=2).encode()
    artifacts = repository / "Artifacts"
    artifacts.mkdir(exist_ok=True)
    destination = artifacts / f"ForgeMCP-Unreal-{args.channel.title()}-{plugin_version}-UE5.6.1-Win64.zip"
    temporary = artifacts / ("package-" + uuid.uuid4().hex + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payloads.items()):
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None
            assert all(archive.read(name) == data for name, data in payloads.items())
        if destination.exists() and destination.read_bytes() != temporary.read_bytes():
            backups = artifacts / "Backups"
            backups.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            shutil.copy2(destination, backups / (destination.stem + "-" + stamp + ".zip"))
        temporary.replace(destination)
        print(f"Package: {destination}")
        print(f"Files: {len(payloads)}; SHA256: {hashlib.sha256(destination.read_bytes()).hexdigest()}")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
