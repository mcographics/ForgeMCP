"""Install and activate a ZIP in an isolated Blender user profile, without saving prefs."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

PROBE = """
import os, json, hashlib, sys
from pathlib import Path
import addon_utils
import bpy

root = Path(os.environ["FORGE_PACKAGE_TEST_ROOT"]).resolve()
addons = Path(bpy.utils.user_resource("SCRIPTS", path="addons", create=True)).resolve()
assert addons.is_relative_to(root), "Installation must use the isolated profile"
before = (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.data.filepath)
archive = os.environ["FORGE_PACKAGE_ARCHIVE"]
assert bpy.ops.preferences.addon_install(filepath=archive) == {"FINISHED"}
module = addon_utils.enable("majestic_forge", default_set=False)
assert module and Path(module.__file__).resolve().is_relative_to(root)
assert module.bl_info["name"] == "ForgeMCP"
assert "MIT License" in (Path(module.__file__).parent / "LICENSE.txt").read_text()
assert module.MAJESTICFORGE_PT_Connection.is_registered
assert module.transfer_ui.MAJESTICFORGE_PT_Transfer.is_registered
assert module.transfer_ui.MAJESTICFORGE_OT_ExportToUnreal.is_registered
assert module.transfer_ui.MAJESTICFORGE_OT_ConfirmTransfer.is_registered
assert tuple(bpy.context.window_manager.forge_transfer.location) == (0.0, 0.0, 0.0)
assert not module.transfer_ui.busy()
assert module._bridge is not None
from majestic_forge import skinning
assert Path(skinning.__file__).resolve().is_relative_to(root)
def request(command, args=None, token=None):
    return module._bridge.reply(json.dumps({
        "protocol_version": 1, "request_id": "package-probe",
        "token": module._bridge.token if token is None else token,
        "command": command, "args": {} if args is None else args
    }).encode())
health = request("health")["data"]
assert health["transfer_contract_version"] == 1
assert "export_preview" in health["capabilities"]
assert request("export_preview", {"name": "Cube"}, token="incorrect")["error"]["code"] == "unauthorized"
assert request("export_preview", {"name": "Cube", "output_path": str(root / "forbidden.fbx")})["error"]["code"] == "invalid_arguments"
assert not (root / "forbidden.fbx").exists()
context_before = (bpy.context.view_layer.objects.active, tuple(bpy.context.selected_objects), bpy.context.mode)
plan = request("export_preview", {"name": "Cube"})["data"]
export_args = {"preview_id": plan["preview_id"], "confirmation": plan["preview_id"]}
exported = request("export_apply", export_args)
assert exported["ok"] and exported["data"]["status"] == "exported", exported
data = exported["data"]
artifact = root / "sessions" / "transfers" / data["source_session_id"] / data["transfer_id"] / "mesh.fbx"
assert artifact.stat().st_size == data["artifact_bytes"]
assert hashlib.sha256(artifact.read_bytes()).hexdigest() == data["artifact_sha256"]
assert data["world_vertices_truncated"] is False and len(data["source_world_vertices"]) == 8
assert request("export_apply", export_args)["error"]["code"] == "preview_not_found"
assert context_before == (bpy.context.view_layer.objects.active, tuple(bpy.context.selected_objects), bpy.context.mode)
stale = request("export_preview", {"name": "Cube"})["data"]
cube = bpy.data.objects["Cube"]
old_location = cube.location.copy()
cube.location.x += 0.25
rejected = request("export_apply", {"preview_id": stale["preview_id"], "confirmation": stale["preview_id"]})
assert rejected["error"]["code"] == "stale_preview", rejected
cube.location = old_location
bpy.context.view_layer.update()
assert not (root / "sessions" / "transfers" / data["source_session_id"] / stale["preview_id"]).exists()
assert bpy.ops.majestic_forge.stop_bridge() == {"FINISHED"}
assert module._bridge is None
assert bpy.ops.majestic_forge.start_bridge() == {"FINISHED"}
addon_utils.disable("majestic_forge")
assert module._bridge is None
# Reproduce an older cached materials module left behind by ZIP replacement.
cached_materials = sys.modules["majestic_forge.materials"]
del cached_materials.transfer_surface
sys.modules.pop("majestic_forge")
errors = []
updated = addon_utils.enable("majestic_forge", default_set=False, handle_error=errors.append)
assert updated is not None and not errors, errors
assert hasattr(sys.modules["majestic_forge.materials"], "transfer_surface")
assert updated._bridge is not None
assert updated.MAJESTICFORGE_PT_Connection.is_registered
assert updated._bridge.exporter.preview("Cube")["vertex_count"] == 8
addon_utils.disable("majestic_forge")
assert updated._bridge is None
print("FORGEMCP_CACHED_OLD_MATERIALS_UPDATE_PASS")
assert before == (len(bpy.data.objects), bpy.context.scene.frame_current, bpy.data.filepath)
print("FORGEMCP_CLEAN_ZIP_INSTALL_ENABLE_DISABLE_PASS")
print("FORGEMCP_INSTALLED_ZIP_NATIVE_EXPORT_AUTH_STALE_REPLAY_PASS")
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    blender = args.blender.resolve(strict=True)
    archive = args.archive.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="forgemcp-clean-blender-install-") as temp:
        root = Path(temp)
        for name in ("scripts", "config", "sessions"):
            (root / name).mkdir()
        script = root / "verify_install.py"
        script.write_text(PROBE, encoding="utf-8")
        env = {
            **os.environ,
            "BLENDER_USER_SCRIPTS": str(root / "scripts"),
            "BLENDER_USER_CONFIG": str(root / "config"),
            "FORGE_BLENDER_SESSION_DIR": str(root / "sessions"),
            "FORGE_PACKAGE_TEST_ROOT": str(root),
            "FORGE_PACKAGE_ARCHIVE": str(archive),
        }
        result = subprocess.run(
            [
                str(blender),
                "--background",
                "--factory-startup",
                "--python-exit-code",
                "1",
                "--python",
                str(script),
            ],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        print(result.stdout)
        print(result.stderr)
        if (
            result.returncode
            or "FORGEMCP_CLEAN_ZIP_INSTALL_ENABLE_DISABLE_PASS" not in result.stdout
        ):
            raise SystemExit("Clean-profile Blender installation validation failed")


if __name__ == "__main__":
    main()
