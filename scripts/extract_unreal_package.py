"""Validate a bounded development archive before extracting to a new directory."""

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path


def extract(archive_path, destination):
    destination = Path(destination).absolute()
    for ancestor in (destination.parent, *destination.parent.parents):
        if ancestor.exists():
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Extraction ancestors must not be links or reparse points")
    payloads = {}
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if not 4 <= len(entries) <= 128 or len(set(n.casefold() for n in names)) != len(names):
            raise ValueError("Archive scope or duplicate entry rejected")
        if any(entry.file_size > 64 * 1024 * 1024 or entry.flag_bits & 1 or
               stat.S_ISLNK(entry.external_attr >> 16) for entry in entries):
            raise ValueError("Oversized, encrypted or linked entry rejected")
        if sum(e.file_size for e in entries) > 128 * 1024 * 1024:
            raise ValueError("Archive exceeds expanded size limit")
        manifest_entry = archive.getinfo("package-manifest.json")
        if manifest_entry.file_size > 256 * 1024:
            raise ValueError("Manifest exceeds size limit")
        manifest = json.loads(archive.read(manifest_entry))
        if (manifest.get("package_kind") != "development_editor_plugin" or
                manifest.get("engine_version") != "5.6.1" or manifest.get("platform") != "Win64"):
            raise ValueError("Unsupported package target")
        files = manifest.get("files")
        if not isinstance(files, dict) or set(names) != set(files) | {"package-manifest.json"}:
            raise ValueError("Archive does not match manifest scope")
        for name, checksum in files.items():
            if (not re.fullmatch(r"Forge/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+", name)
                    or any(part in {".", ".."} or part.endswith((".", " ")) for part in name.split("/"))
                    or not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum)):
                raise ValueError("Unsafe package path or checksum")
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("Package checksum mismatch")
            payloads[name] = data
        required = {"Forge/MajesticForge.uplugin", "Forge/Binaries/Win64/UnrealEditor.modules",
                    "Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll",
                    "Forge/Binaries/Win64/UnrealEditor-MajesticForgeRuntime.dll"}
        if not required <= payloads.keys():
            raise ValueError("Required plugin modules missing")
    # No filesystem writes until the entire archive has passed validation.
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
    (destination / "package-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination / "Forge"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(extract(args.archive.resolve(strict=True), args.destination))
