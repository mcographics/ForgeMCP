"""Exercise actual Blender operators against a disposable native Unreal host."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.verify_transfer_workflow_mcp import hidden, ready
from server.core.connections import ConnectionManager

PROBE = '''
import json, os, sys, time
from pathlib import Path
import bpy
sys.path.insert(0, os.environ["FORGE_ADDON_ROOT"])
import majestic_forge
from majestic_forge import transfer_ui
root = Path(os.environ["FORGE_PANEL_TEST_ROOT"])
majestic_forge.register()
assert transfer_ui.MAJESTICFORGE_PT_Transfer.is_registered
assert transfer_ui.MAJESTICFORGE_OT_ExportToUnreal.bl_label == "Send to Unreal"
assert transfer_ui.MAJESTICFORGE_OT_ConfirmTransfer.bl_label == "Confirm Send to Unreal"
settings = bpy.context.window_manager.forge_transfer
settings.project_root = os.environ["FORGE_REPOSITORY"]
settings.target_session = os.environ["FORGE_PANEL_TARGET"]
settings.asset_path = "/Game/PanelAcceptance_" + root.name.split("-")[-1] + "/SM_Cube"
settings.location = (0,0,0)
before = (bpy.data.objects["Cube"].data.as_pointer(),len(bpy.data.objects),bpy.data.filepath)
def wait_preview():
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        majestic_forge._bridge.tick()
        transfer_ui._poll()
        if transfer_ui._job and transfer_ui._job["state"] == "preview":
            return transfer_ui._job["preview"]
        if not transfer_ui.busy():
            raise AssertionError(transfer_ui._status)
        time.sleep(0.02)
    raise AssertionError("Preview timed out")
try:
    assert bpy.ops.majestic_forge.export_to_unreal() == {"FINISHED"}
    cancelled = wait_preview()
    assert bpy.ops.majestic_forge.cancel_transfer() == {"FINISHED"}
    assert not transfer_ui.busy()
    assert bpy.ops.majestic_forge.export_to_unreal() == {"FINISHED"}
    plan = wait_preview()
    assert plan["target"]["project_file"].replace("\\\\","/") == os.environ["FORGE_PANEL_PROJECT"].replace("\\\\","/")
    assert bpy.ops.majestic_forge.confirm_transfer() == {"FINISHED"}
    assert transfer_ui.applying()
    try:
        transfer_ui.shutdown()
    except RuntimeError:
        pass
    else:
        raise AssertionError("Disable must protect an active apply")
    deadline = time.monotonic() + 120
    while transfer_ui.busy() and time.monotonic() < deadline:
        majestic_forge._bridge.tick()
        transfer_ui._poll()
        time.sleep(0.02)
    assert not transfer_ui.busy(), "Apply timed out"
    assert transfer_ui._status.startswith("Transferred."), transfer_ui._status
    assert before == (bpy.data.objects["Cube"].data.as_pointer(),len(bpy.data.objects),bpy.data.filepath)
    (root / "panel-result.json").write_text(json.dumps({"preview":plan,"cancelled_preview":cancelled,
        "operation_id":transfer_ui._last_operation,"status":transfer_ui._status,"interactive_verified":False}))
    print("FORGEMCP_NATIVE_PANEL_OPERATOR_PREVIEW_CANCEL_APPLY_PASS")
finally:
    majestic_forge.unregister()
'''


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if not relative.parts[0].startswith(("TransferImportValidation-", "RoundtripValidation-")) or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject"):
        raise ValueError("Only the generated disposable host is allowed")
    root = project.parent / "Saved" / ("PanelAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    sessions = root / "sessions"
    sessions.mkdir()
    env = {**os.environ, "FORGE_BLENDER_SESSION_DIR": str(sessions),
           "FORGE_UNREAL_SESSION_DIR": str(project.parent / "Saved/MajesticForge"),
           "FORGE_ADDON_ROOT": str(repository / "blender-addon"), "FORGE_REPOSITORY": str(repository),
           "FORGE_PANEL_TEST_ROOT": str(root), "FORGE_PANEL_PROJECT": str(project),
           "BLENDER_USER_CONFIG": str(root / "config"), "BLENDER_USER_SCRIPTS": str(root / "scripts")}
    manager = ConnectionManager([project.parent / "Saved/MajesticForge"])
    with (root / "editor-launch.log").open("w") as log:
        editor = subprocess.Popen([str(args.editor), str(project), "/Engine/Maps/Templates/Template_Default",
            "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'unreal.log'}"], cwd=project.parent, env=env, stdout=log, stderr=log, **hidden())
        try:
            target = await ready(manager, editor, "unreal")
            env["FORGE_PANEL_TARGET"] = target.session_id
            probe = root / "probe.py"
            probe.write_text(PROBE)
            with (root / "blender.log").open("w") as blender_log:
                blender = subprocess.Popen([str(args.blender), "--background", "--factory-startup",
                    "--python-exit-code", "1", "--python", str(probe)], cwd=repository, env=env,
                    stdout=blender_log, stderr=blender_log, **hidden())
                try:
                    code = await asyncio.to_thread(blender.wait, 240)
                    assert code == 0, f"Panel fixture failed: {root / 'blender.log'}"
                finally:
                    if blender.poll() is None:
                        blender.terminate()
                        await asyncio.to_thread(blender.wait, 20)
            result = json.loads((root / "panel-result.json").read_text())
            from server.core.workflow_journal import WorkflowJournal
            journal = WorkflowJournal(repository / "Saved/ForgeWorkflows")
            receipt = journal.read(result["operation_id"])
            assert receipt["state"] == "completed"
            evidence = next(e["evidence"] for e in receipt["events"] if e["stage"] == "placement" and e["outcome"] == "completed")
            actor = evidence["native_result"]["actors"][0]
            inspected = await manager.request(target, "actor_info", {"actor_path": actor["path"]})
            assert inspected["actor"]["location"] == [0,0,0]
            assert inspected["actor"]["static_mesh"] == result["preview"]["changes"]["target_asset_path"] + ".SM_Cube"
            try:
                journal.inspect(result["cancelled_preview"]["operation_id"])
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("Cancelled preview must not create a receipt")
            (root / "acceptance.json").write_text(json.dumps({"panel":result,"receipt":receipt,"actor":inspected},indent=2))
            print(f"FORGEMCP_NATIVE_PANEL_TO_UNREAL_PASS: {root}")
        finally:
            if editor.poll() is None:
                editor.terminate()
                await asyncio.to_thread(editor.wait, 20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
