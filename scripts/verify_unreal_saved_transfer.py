"""Reopen saved transfer assets in a separate native Unreal Python commandlet."""

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
root = Path(os.environ["FORGE_REOPEN_ROOT"])
expected = json.loads((root / "expected.json").read_text())
mesh = unreal.load_asset(expected["asset_path"])
assert isinstance(mesh, unreal.StaticMesh), "Saved mesh failed native load"
materials = list(mesh.get_editor_property("static_materials"))
actual = [slot.get_editor_property("material_interface").get_path_name() for slot in materials]
assert actual == [m["asset_path"] for m in expected["materials"]], actual
for entry in expected["materials"]:
    material = unreal.load_asset(entry["asset_path"])
    assert isinstance(material, unreal.Material), "Saved material failed native load"
    assert material.get_editor_property("two_sided") == entry["two_sided"]
    assert material.get_editor_property("blend_mode") == unreal.BlendMode.BLEND_OPAQUE
    color_node = unreal.MaterialEditingLibrary.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_BASE_COLOR)
    roughness_node = unreal.MaterialEditingLibrary.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_ROUGHNESS)
    metallic_node = unreal.MaterialEditingLibrary.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_METALLIC)
    assert isinstance(color_node, unreal.MaterialExpressionConstant3Vector)
    assert isinstance(roughness_node, unreal.MaterialExpressionConstant)
    assert isinstance(metallic_node, unreal.MaterialExpressionConstant)
    color = color_node.get_editor_property("constant")
    assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(
        [color.r, color.g, color.b], entry["base_color"]))
    assert math.isclose(roughness_node.get_editor_property("r"), entry["roughness"], abs_tol=1e-6)
    assert math.isclose(metallic_node.get_editor_property("r"), entry["metallic"], abs_tol=1e-6)
report = {"native_mesh_loaded": True, "native_materials_loaded": True,
          "saved_constant_graphs_verified": True,
          "material_references": actual, "interactive_verified": False,
          "rendered_materials_verified": False, "level_reopened": False}
(root / "reopen.json").write_text(json.dumps(report, indent=2))
print("FORGEMCP_NATIVE_SAVED_TRANSFER_REOPEN_PASS")
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--recovery", action="store_true", help="Reopen assets from retained-export recovery")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if (not relative.parts[0].startswith("TransferImportValidation-")
            or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject")):
        raise ValueError("Only a disposable generated transfer host is allowed")
    acceptance = args.acceptance.resolve(strict=True)
    if acceptance.parent != project.parent / "Saved" or not acceptance.name.startswith("WorkflowAcceptance-"):
        raise ValueError("Acceptance must belong to the disposable host")
    report = json.loads((acceptance / "acceptance.json").read_text())
    applied = report["native_retained_export_recovery"]["apply"] if args.recovery else report["apply"]
    imported = next(e["evidence"] for e in applied["data"]["receipt"]["events"]
                    if e["stage"] == "import" and e["outcome"] == "completed")
    root = acceptance / ("Reopen-" + uuid.uuid4().hex)
    root.mkdir()
    (root / "expected.json").write_text(json.dumps(imported), encoding="utf-8")
    probe = root / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    files = [project.parent / "Content" / (asset.split(".", 1)[0].removeprefix("/Game/") + ".uasset")
             for asset in imported["saved_assets"]]
    assert all(path.resolve().is_relative_to(project.parent / "Content") for path in files)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    print(f"Evidence: {root}", flush=True)
    with (root / "launch.log").open("w", encoding="utf-8") as log:
        process = subprocess.run([str(args.editor.resolve(strict=True)), str(project),
            "-run=pythonscript", f"-script={probe}", "-EnablePlugins=PythonScriptPlugin",
            "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'unreal.log'}"], cwd=project.parent,
            env={**os.environ, "FORGE_REOPEN_ROOT": str(root)}, stdout=log,
            stderr=subprocess.STDOUT, startupinfo=startup, timeout=180)
    assert process.returncode == 0, f"Native reopen failed; inspect {root}"
    assert (root / "reopen.json").is_file(), f"Native probe did not complete; inspect {root}"
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    print("FORGEMCP_NATIVE_REOPEN_AND_UNCHANGED_PACKAGES_PASS", flush=True)


if __name__ == "__main__":
    main()
