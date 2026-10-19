import hashlib
import json
import zipfile

import pytest

from scripts.extract_unreal_package import extract


def archive(tmp_path, *, extra=None, corrupt=False, duplicate=False):
    files = {"Forge/MajesticForge.uplugin": b"{}",
             "Forge/Binaries/Win64/UnrealEditor.modules": b"{}",
             "Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll": b"editor fixture",
             "Forge/Binaries/Win64/UnrealEditor-MajesticForgeRuntime.dll": b"runtime fixture"}
    if extra:
        files[extra] = b"escape fixture"
    manifest = {"package_kind": "development_editor_plugin", "engine_version": "5.6.1",
                "platform": "Win64", "files": {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}}
    path = tmp_path / "package.zip"
    with zipfile.ZipFile(path, "w") as output:
        output.writestr("package-manifest.json", json.dumps(manifest))
        for name, data in files.items():
            output.writestr(name, data + b"corrupt" if corrupt else data)
        if duplicate:
            output.writestr("FORGE/MAJESTICFORGE.UPLUGIN", b"alias fixture")
    return path


def test_valid_package_extracts_to_new_directory_and_never_overwrites(tmp_path):
    package = archive(tmp_path)
    destination = tmp_path / "extracted"
    plugin = extract(package, destination)
    descriptor = plugin / "MajesticForge.uplugin"
    descriptor.write_text("preserved work")
    with pytest.raises(FileExistsError):
        extract(package, destination)
    assert descriptor.read_text() == "preserved work"


@pytest.mark.parametrize("extra", ["Forge/../../escape.txt", "Forge/C:/escape.txt",
                                   "Forge/Source/../escape.txt", "Forge/Source/trailing."])
def test_unsafe_paths_rejected_before_any_extraction(tmp_path, extra):
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError):
        extract(archive(tmp_path, extra=extra), destination)
    assert not destination.exists()


@pytest.mark.parametrize("options", [{"corrupt": True}, {"duplicate": True}])
def test_checksum_or_case_alias_rejected_before_any_extraction(tmp_path, options):
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError):
        extract(archive(tmp_path, **options), destination)
    assert not destination.exists()
