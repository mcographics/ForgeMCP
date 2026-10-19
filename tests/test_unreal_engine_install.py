import hashlib
import json
import zipfile

import pytest

from scripts import install_unreal_engine as installer


def fixture(tmp_path, build_id="engine-fixture"):
    engine = tmp_path / "UE_5.6"
    version = engine / "Engine/Build/Build.version"
    version.parent.mkdir(parents=True)
    version.write_text(json.dumps(dict(MajorVersion=5, MinorVersion=6, PatchVersion=1)))
    modules = engine / "Engine/Binaries/Win64/UnrealEditor.modules"
    modules.parent.mkdir(parents=True)
    modules.write_text(json.dumps({"BuildId": "engine-fixture"}))
    payloads = {
        "Forge/MajesticForge.uplugin": json.dumps({"FriendlyName": "ForgeMCP",
            "VersionName": "0.2.13-alpha.1", "EnabledByDefault": True}).encode(),
        "Forge/Binaries/Win64/UnrealEditor.modules": json.dumps({"BuildId": build_id,
            "Modules": {name: f"UnrealEditor-{name}.dll"
                        for name in ("MajesticForge", "MajesticForgeRuntime")}}).encode(),
        "Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll": b"fixture",
        "Forge/Binaries/Win64/UnrealEditor-MajesticForgeRuntime.dll": b"fixture",
    }
    manifest = {"package_kind": "development_editor_plugin", "engine_version": "5.6.1",
                "platform": "Win64", "plugin_version": "0.2.13-alpha.1",
                "engine_build_id": build_id,
                "files": {n: hashlib.sha256(d).hexdigest() for n, d in payloads.items()}}
    archive = tmp_path / "alpha.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("package-manifest.json", json.dumps(manifest))
        for name, data in payloads.items():
            output.writestr(name, data)
    return engine, archive


def test_install_update_preserves_prior_install_and_unrelated_files(tmp_path, monkeypatch):
    engine, archive = fixture(tmp_path)
    monkeypatch.setattr(installer, "engine_editors", lambda _: [])
    result = installer.install(archive, engine)
    destination = installer.Path(result["destination"])
    (destination / "old-only.txt").write_text("preserve me in backup")
    other = destination.parent / "Unrelated.txt"
    other.write_text("untouched")
    with pytest.raises(FileExistsError):
        installer.install(archive, engine)
    updated = installer.install(archive, engine, update=True)
    assert (installer.Path(updated["backup"]) / "old-only.txt").read_text() == "preserve me in backup"
    assert not (destination / "old-only.txt").exists()
    assert other.read_text() == "untouched"


def test_engine_folder_migration_backs_up_legacy_name(tmp_path, monkeypatch):
    engine, archive = fixture(tmp_path)
    legacy = engine / "Engine/Plugins/Marketplace/MajesticForge"
    legacy.mkdir(parents=True)
    (legacy / "MajesticForge.uplugin").write_text(json.dumps({"FriendlyName": "ForgeMCP"}))
    (legacy / "legacy-only.txt").write_text("retain in rollback")
    monkeypatch.setattr(installer, "engine_editors", lambda _: [])

    with pytest.raises(FileExistsError, match="use --update"):
        installer.install(archive, engine)

    result = installer.install(archive, engine, update=True)
    destination = installer.Path(result["destination"])
    assert destination == engine / "Engine/Plugins/Marketplace/Forge"
    assert not legacy.exists()
    assert (installer.Path(result["backup"]) / "legacy-only.txt").read_text() == "retain in rollback"


def test_wrong_build_id_never_installs(tmp_path):
    engine, archive = fixture(tmp_path, "different-engine")
    with pytest.raises(ValueError, match="BuildId"):
        installer.install(archive, engine)
    assert not (engine / "Engine/Plugins/Marketplace/Forge").exists()


def test_open_editor_prevents_update(tmp_path, monkeypatch):
    engine, archive = fixture(tmp_path)
    result = installer.install(archive, engine)
    monkeypatch.setattr(installer, "engine_editors", lambda _: [{"ProcessId": 123}])
    with pytest.raises(RuntimeError, match="close editors"):
        installer.install(archive, engine, update=True)
    assert (installer.Path(result["destination"]) / "forge-install-receipt.json").is_file()


def test_failed_receipt_restores_previous_install(tmp_path, monkeypatch):
    engine, archive = fixture(tmp_path)
    result = installer.install(archive, engine)
    destination = installer.Path(result["destination"])
    assert destination.name == "Forge"
    (destination / "previous.txt").write_text("original")
    monkeypatch.setattr(installer, "engine_editors", lambda _: [])
    original = installer.Path.write_text

    def fail_receipt(path, *args, **kwargs):
        if path.name == "forge-install-receipt.json":
            raise OSError("simulated receipt failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(installer.Path, "write_text", fail_receipt)
    with pytest.raises(OSError, match="simulated"):
        installer.install(archive, engine, update=True)
    assert (destination / "previous.txt").read_text() == "original"
