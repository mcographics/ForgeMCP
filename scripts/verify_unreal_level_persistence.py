"""Check native map save/reopen semantics in the disposable transfer host.

This is a native API acceptance fixture, not an implemented MCP level-save tool.
It creates one new map and closes only its own commandlet processes.
"""

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

PROBE = '''
import json, os, math
from pathlib import Path
import unreal
root = Path(os.environ["FORGE_LEVEL_PROBE_ROOT"])
expected = json.loads((root / "expected.json").read_text())
stage = os.environ["FORGE_LEVEL_PROBE_STAGE"]
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
if stage == "save":
    assert not unreal.EditorAssetLibrary.does_asset_exist(expected["map_path"])
    world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    assert world is not None
    mesh = unreal.load_asset(expected["mesh_path"])
    assert isinstance(mesh, unreal.StaticMesh)
    actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor,
        unreal.Vector(*expected["location"]), unreal.Rotator(
            pitch=expected["rotation"][0], yaw=expected["rotation"][1], roll=expected["rotation"][2]))
    assert actor is not None
    actor.set_actor_label(expected["actor_label"])
    actor.set_actor_scale3d(unreal.Vector(*expected["scale"]))
    assert actor.static_mesh_component.set_static_mesh(mesh)
    assert unreal.EditorLoadingAndSavingUtils.save_map(world, expected["map_path"])
else:
    world = unreal.EditorLoadingAndSavingUtils.load_map(expected["map_file"])
    assert world is not None
matches = [actor for actor in subsystem.get_all_level_actors()
           if isinstance(actor, unreal.StaticMeshActor)
           and actor.get_actor_label() == expected["actor_label"]]
assert len(matches) == 1
actor = matches[0]
if "actor_name" in expected:
    assert actor.get_name() == expected["actor_name"]
component = actor.static_mesh_component
assert component.static_mesh.get_path_name() == expected["mesh_path"]
materials = [component.get_material(i).get_path_name()
             for i in range(component.get_num_materials())]
assert materials == expected["material_paths"]
location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
observed = {"location": [location.x, location.y, location.z],
            "rotation": [rotation.pitch, rotation.yaw, rotation.roll],
            "scale": [scale.x, scale.y, scale.z]}
for key, values in observed.items():
    assert all(math.isclose(a, b, abs_tol=1e-4) for a, b in zip(values, expected[key])), (key, values)
assert world.get_path_name() == expected["map_path"] + "." + expected["map_path"].rsplit("/", 1)[1]
report = {"stage": stage, "world_path": world.get_path_name(),
          "actor_path": actor.get_path_name(), "mesh_path": component.static_mesh.get_path_name(),
          "material_paths": materials, "transforms": observed,
          "interactive_verified": False, "mcp_level_save_verified": False,
          "rendered_materials_verified": False}
(root / (stage + ".json")).write_text(json.dumps(report, indent=2))
print("FORGEMCP_NATIVE_LEVEL_" + stage.upper() + "_PASS")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--mcp-level", action="store_true", help="Reopen the map saved through MCP, without spawning another actor")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if (not relative.parts[0].startswith("TransferImportValidation-")
            or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject")):
        raise ValueError("Only the generated disposable transfer host is allowed")
    acceptance = args.acceptance.resolve(strict=True)
    if acceptance.parent != project.parent / "Saved" or not acceptance.name.startswith("WorkflowAcceptance-"):
        raise ValueError("Acceptance must belong to this disposable host")
    report = json.loads((acceptance / "acceptance.json").read_text())
    receipt = (report["apply"] if args.mcp_level else report["native_retained_export_recovery"]["apply"])["data"]["receipt"]
    imported = next(e["evidence"] for e in receipt["events"]
                    if e["stage"] == "import" and e["outcome"] == "completed")
    probe_id = uuid.uuid4().hex
    root = acceptance / ("LevelPersistence-" + probe_id)
    root.mkdir()
    map_path = "/Game/ForgeLevelAcceptance/Map_" + probe_id
    map_file = project.parent / "Content" / "ForgeLevelAcceptance" / ("Map_" + probe_id + ".umap")
    if args.mcp_level:
        saved = report["native_mcp_level_save"]["apply"]["data"]
        assert saved["state"] == "saved"
        map_path = saved["asset_path"]
        assert map_path.startswith("/Game/ForgeSavedLevel_")
        map_file = project.parent / "Content" / (map_path.removeprefix("/Game/") + ".umap")
        assert map_file.resolve(strict=True).is_relative_to(project.parent / "Content")
        assert map_file.resolve() == Path(saved["map_file"]).resolve(strict=True)
    else:
        assert not map_file.exists()
    expected = {"map_path": map_path, "map_file": str(map_file), "mesh_path": imported["asset_path"],
                "material_paths": [m["asset_path"] for m in imported["materials"]],
                "actor_label": "ForgePersistence_" + probe_id,
                "location": [150.0, 250.0, 350.0], "rotation": [0.0, 90.0, 0.0],
                "scale": [1.5, 0.5, 2.0]}
    if args.mcp_level:
        placement = next(e["evidence"] for e in receipt["events"]
                         if e["stage"] == "placement" and e["outcome"] == "completed")
        actor = placement["native_result"]["actors"][0]
        expected.update(actor_label=actor["label"], actor_name=actor["path"].rsplit(".", 1)[1],
                        location=actor["location"], rotation=actor["rotation"], scale=actor["scale"])
    (root / "expected.json").write_text(json.dumps(expected, indent=2))
    probe = root / "probe.py"
    probe.write_text(PROBE)
    assets = [project.parent / "Content" / (path.split(".", 1)[0].removeprefix("/Game/") + ".uasset")
              for path in imported["saved_assets"]]
    assert all(path.resolve(strict=True).is_relative_to(project.parent / "Content") for path in assets)
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in assets}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    print(f"Evidence: {root}", flush=True)
    map_checksum = hashlib.sha256(map_file.read_bytes()).hexdigest() if args.mcp_level else None
    for stage in (("reopen",) if args.mcp_level else ("save", "reopen")):
        with (root / (stage + "-launch.log")).open("w", encoding="utf-8") as log:
            process = subprocess.Popen([str(args.editor.resolve(strict=True)), str(project),
                "-run=pythonscript", f"-script={probe}", "-EnablePlugins=PythonScriptPlugin",
                "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
                f"-abslog={root / (stage + '-unreal.log')}"], cwd=project.parent,
                env={**os.environ, "FORGE_LEVEL_PROBE_ROOT": str(root), "FORGE_LEVEL_PROBE_STAGE": stage},
                stdout=log, stderr=subprocess.STDOUT, startupinfo=startup)
            try:
                process.wait(timeout=180)
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=20)
        assert process.returncode == 0 and (root / (stage + ".json")).is_file(), root
        assert map_file.is_file() and map_file.stat().st_size > 0
        checksum = hashlib.sha256(map_file.read_bytes()).hexdigest()
        if map_checksum is not None:
            assert checksum == map_checksum
        map_checksum = checksum
        assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in assets}
    (root / "acceptance.json").write_text(json.dumps({"saved_map": str(map_file),
        "map_sha256": map_checksum, "saved_actor_reopened": True, "existing_assets_unchanged": True,
        "mcp_level_save_verified": args.mcp_level, "original_mcp_actor_verified": args.mcp_level,
        "interactive_verified": False}, indent=2))
    print("FORGEMCP_NATIVE_LEVEL_SAVE_REOPEN_AND_REFERENCES_PASS", flush=True)


if __name__ == "__main__":
    main()
