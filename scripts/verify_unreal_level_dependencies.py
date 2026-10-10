"""Native MCP dependency guard acceptance in the generated disposable host."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.core.connections import ConnectionManager
from server.core.security import protect_path

SETUP = '''
import unreal, json, os
from pathlib import Path
root = Path(os.environ["FORGE_DEPENDENCY_ROOT"])
expected = json.loads((root / "expected.json").read_text())
source = unreal.load_asset(expected["source_material"])
clone = unreal.AssetToolsHelpers.get_asset_tools().duplicate_asset(
    "M_Dependency", expected["dependency_folder"], source)
assert isinstance(clone, unreal.Material)
actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
          if a.get_actor_label() == expected["actor_label"]]
assert len(actors) == 1 and isinstance(actors[0], unreal.StaticMeshActor)
actors[0].static_mesh_component.set_material(0, clone)
original_sidedness = clone.get_editor_property("two_sided")
(root / "ready.json").write_text(json.dumps({"material_path": clone.get_path_name(),
    "actor_path": actors[0].get_path_name()}))
def tick(delta):
    if (root / "save-request").exists() and not (root / "saved.json").exists():
        saved = unreal.EditorAssetLibrary.save_loaded_asset(clone, only_if_is_dirty=False)
        (root / "saved.json").write_text(json.dumps({"saved": bool(saved)}))
    if (root / "dirty-request").exists() and not (root / "dirtied.json").exists():
        clone.modify(True)
        clone.set_editor_property("two_sided", not original_sidedness)
        (root / "dirtied.json").write_text(json.dumps({"modified": True}))
    if (root / "resave-request").exists() and not (root / "resaved.json").exists():
        clone.modify(True)
        clone.set_editor_property("two_sided", original_sidedness)
        saved = unreal.EditorAssetLibrary.save_loaded_asset(clone, only_if_is_dirty=False)
        (root / "resaved.json").write_text(json.dumps({"saved": bool(saved)}))
        unreal.unregister_slate_post_tick_callback(callback)
callback = unreal.register_slate_post_tick_callback(tick)
'''


async def verify(args):
    repository = Path(__file__).resolve().parents[1]
    project = args.project.resolve(strict=True)
    relative = project.relative_to(repository / "Saved")
    if (not relative.parts[0].startswith("TransferImportValidation-")
            or relative.parts[1:] != ("HostProject", "ForgeMCPDev.uproject")):
        raise ValueError("Only the generated disposable transfer host is allowed")
    acceptance = args.acceptance.resolve(strict=True)
    if acceptance.parent != project.parent / "Saved" or not acceptance.name.startswith("WorkflowAcceptance-"):
        raise ValueError("Acceptance must belong to this disposable host")
    previous = json.loads((acceptance / "acceptance.json").read_text())
    receipt = previous["apply"]["data"]["receipt"]
    imported = next(e["evidence"] for e in receipt["events"] if e["stage"] == "import" and e["outcome"] == "completed")
    placed = next(e["evidence"] for e in receipt["events"] if e["stage"] == "placement" and e["outcome"] == "completed")["native_result"]["actors"][0]
    probe_id = uuid.uuid4().hex
    root = project.parent / "Saved" / ("LevelDependencyAcceptance-" + probe_id)
    root.mkdir()
    protect_path(root)
    expected = {"source_material": imported["materials"][0]["asset_path"],
        "actor_label": placed["label"], "dependency_folder": "/Game/ForgeDependency_" + probe_id}
    (root / "expected.json").write_text(json.dumps(expected))
    script = root / "setup.py"
    script.write_text(SETUP)
    originals = [project.parent / "Content" / (p.split(".", 1)[0][6:] + ".uasset") for p in imported["saved_assets"]]
    assert all(p.resolve(strict=True).is_relative_to(project.parent / "Content") for p in originals)
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    env = {**os.environ, "FORGE_PROJECT_ROOT": str(project.parent), "FORGE_DEPENDENCY_ROOT": str(root)}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    print(f"Evidence: {root}", flush=True)
    with (root / "launch.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(args.editor.resolve(strict=True)), str(project),
            previous["native_mcp_level_save"]["apply"]["data"]["asset_path"],
            "-EnablePlugins=PythonScriptPlugin", f"-ExecCmds=py {script.as_posix()}",
            "-Unattended", "-NullRHI", "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
            f"-abslog={root / 'unreal.log'}"], cwd=project.parent, env=env,
            stdout=log, stderr=subprocess.STDOUT, startupinfo=startup)
        try:
            manager = ConnectionManager([project.parent / "Saved" / "MajesticForge"], timeout=30)
            deadline = time.monotonic() + 120
            target = None
            while process.poll() is None and time.monotonic() < deadline:
                matches = [s for s in manager.discover() if s.pid == process.pid and s.kind == "unreal"]
                if matches and (root / "ready.json").exists():
                    target = matches[0]
                    break
                await asyncio.sleep(0.2)
            assert target is not None, f"Dependency setup did not become ready; inspect {root}"
            setup = json.loads((root / "ready.json").read_text())
            params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"], cwd=str(repository), env=env)
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as client:
                    await client.initialize()

                    async def call(name, arguments):
                        reply = await client.call_tool(name, arguments)
                        assert not reply.isError and reply.structuredContent is not None, reply
                        return reply.structuredContent

                    path = "/Game/ForgeDependencyMap_" + probe_id + "/World"
                    request = {"asset_path": path, "session_id": target.session_id}
                    blocked = await call("unreal_preview_level_save", request)
                    assert not blocked["ok"] and blocked["error"]["code"] == "unsaved_dependencies", blocked
                    assert blocked["data"]["preview_created"] is False and "preview_id" not in blocked["data"]
                    dependency = next(d for d in blocked["data"]["dependencies"] if d["package"] == expected["dependency_folder"] + "/M_Dependency")
                    assert dependency["requires_separate_save"] is True and dependency["disk_package_present"] is False
                    assert not (project.parent / "Content" / path[6:]).parent.exists()
                    (root / "save-request").write_text("save disposable dependency")
                    deadline = time.monotonic() + 30
                    while process.poll() is None and not (root / "saved.json").exists() and time.monotonic() < deadline:
                        await asyncio.sleep(0.1)
                    assert json.loads((root / "saved.json").read_text())["saved"] is True
                    preview = await call("unreal_preview_level_save", request)
                    assert preview["ok"], preview
                    operation = preview["data"]["preview_id"]
                    (root / "dirty-request").write_text("dirty disposable dependency")
                    deadline = time.monotonic() + 30
                    while process.poll() is None and not (root / "dirtied.json").exists() and time.monotonic() < deadline:
                        await asyncio.sleep(0.1)
                    assert json.loads((root / "dirtied.json").read_text())["modified"] is True
                    rejected = await call("unreal_apply_level_save", {"session_id": target.session_id,
                        "preview_id": operation, "confirmation": operation})
                    assert not rejected["ok"] and rejected["error"]["code"] == "unsaved_dependencies", rejected
                    assert not (project.parent / "Content" / path[6:]).parent.exists()
                    failed_receipt = await call("forge_inspect_transfer", {"operation_id": operation})
                    assert failed_receipt["ok"] and failed_receipt["data"]["record"]["state"] == "failed"
                    (root / "resave-request").write_text("restore and save disposable dependency")
                    deadline = time.monotonic() + 30
                    while process.poll() is None and not (root / "resaved.json").exists() and time.monotonic() < deadline:
                        await asyncio.sleep(0.1)
                    assert json.loads((root / "resaved.json").read_text())["saved"] is True
                    preview = await call("unreal_preview_level_save", request)
                    assert preview["ok"], preview
                    operation = preview["data"]["preview_id"]
                    saved = await call("unreal_apply_level_save", {"session_id": target.session_id,
                        "preview_id": operation, "confirmation": operation})
                    assert saved["ok"] and saved["data"]["state"] == "saved", saved
                    observed = await call("unreal_inspect_actor", {"session_id": target.session_id,
                        "actor_path": setup["actor_path"]})
                    assert observed["ok"] and setup["material_path"] in observed["data"]["actor"]["material_assets"]
                    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
                    (root / "acceptance.json").write_text(json.dumps({"blocked": blocked, "preview": preview,
                        "dirty_after_preview_rejected": rejected, "failed_receipt": failed_receipt,
                        "apply": saved, "actor": observed, "original_packages_unchanged": True,
                        "dependency_created_and_saved_by_native_fixture": True,
                        "interactive_verified": False, "saved_map_reopened": False}, indent=2))
            print("FORGEMCP_NATIVE_UNSAVED_DEPENDENCY_GUARD_PASS", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
                await asyncio.to_thread(process.wait, timeout=20)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    asyncio.run(verify(parser.parse_args()))
