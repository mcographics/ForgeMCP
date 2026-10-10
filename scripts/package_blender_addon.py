"""Build a source-only Blender installer ZIP, preserving previous package bytes."""

import ast
import hashlib
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MODULES = (
    "__init__.py",
    "automation.py",
    "exporting.py",
    "materials.py",
    "rigging.py",
    "security.py",
    "transfer_ui.py",
    "skinning.py",
)


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "blender-addon" / "majestic_forge"
    payloads = {name: (source / name).read_bytes() for name in MODULES}
    tree = ast.parse(payloads["__init__.py"])
    version = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "bl_info" for target in node.targets
        ):
            version = ast.literal_eval(node.value)["version"]
    if version is None or len(version) != 3 or any(type(n) is not int for n in version):
        raise ValueError("Add-on metadata must declare a three-part numeric version")
    for name, data in payloads.items():
        ast.parse(data, filename=name)
    payloads["LICENSE.txt"] = (root / "LICENSE").read_bytes()
    artifacts = root / "Artifacts"
    artifacts.mkdir(exist_ok=True)
    destination = artifacts / f"ForgeMCP-Blender-Addon-{'.'.join(map(str, version))}.zip"
    with tempfile.NamedTemporaryFile(dir=artifacts, suffix=".zip", delete=False) as temporary:
        staging = Path(temporary.name)
    try:
        with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for name, data in sorted(payloads.items()):
                info = zipfile.ZipInfo(f"majestic_forge/{name}", date_time=(2020, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info, data, compresslevel=9)
        with zipfile.ZipFile(staging) as z:
            assert z.testzip() is None
            assert set(z.namelist()) == {f"majestic_forge/{name}" for name in payloads}
            assert all(z.read(f"majestic_forge/{name}") == data for name, data in payloads.items())
        if destination.exists() and destination.read_bytes() != staging.read_bytes():
            backups = artifacts / "Backups"
            backups.mkdir(exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = backups / f"{destination.stem}-{stamp}.zip"
            shutil.copy2(destination, backup)
            assert backup.read_bytes() == destination.read_bytes()
            print(f"Previous package preserved: {backup}")
        staging.replace(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        print(f"Package: {destination}")
        print(f"Modules: {len(MODULES)}; bytes: {destination.stat().st_size}; SHA256: {digest}")
    finally:
        if staging.exists():
            staging.unlink()


if __name__ == "__main__":
    main()
