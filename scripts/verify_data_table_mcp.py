"""Verify bounded DataTable inspection through MCP and a disposable UE Editor."""

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
from server.core.connections import BridgeError, ConnectionManager


def prepare_python_enabled_project(project: Path) -> None:
    data = json.loads(project.read_text(encoding="utf-8-sig"))
    plugins = data.setdefault("Plugins", [])
    if not any(item.get("Name") == "PythonScriptPlugin" for item in plugins):
        plugins.append({"Name": "PythonScriptPlugin", "Enabled": True})
        project.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def fixture_script(asset_name: str, marker: Path) -> str:
    marker_literal = json.dumps(str(marker))
    return f'''import json, unreal
row_struct = unreal.GameplayTagTableRow.static_struct()
factory = unreal.DataTableFactory()
factory.set_editor_property("struct", row_struct)
tools = unreal.AssetToolsHelpers.get_asset_tools()
table = tools.create_asset({asset_name!r}, "/Game/ForgeMCPValidation", unreal.DataTable, factory)
if not table:
    raise RuntimeError("DataTable fixture creation failed")
rows = [
    {{"Name": "RowAlpha", "Tag": "ForgeMCP.Acceptance.Alpha", "DevComment": "alpha note"}},
    {{"Name": "RowBeta", "Tag": "ForgeMCP.Acceptance.Beta", "DevComment": "beta note"}},
]
if not table.fill_from_json_string(json.dumps(rows), row_struct):
    raise RuntimeError("DataTable fixture row import failed")
if not unreal.EditorAssetLibrary.save_loaded_asset(table):
    raise RuntimeError("DataTable fixture save failed")
data_asset_factory = unreal.DataAssetFactory()
data_asset_factory.set_editor_property("data_asset_class", unreal.PrimaryAssetLabel)
data_asset = tools.create_asset({(asset_name + "_DataAsset")!r}, "/Game/ForgeMCPValidation", unreal.PrimaryAssetLabel, data_asset_factory)
if not data_asset or not unreal.EditorAssetLibrary.save_loaded_asset(data_asset):
    raise RuntimeError("PrimaryDataAsset fixture creation/save failed")
with open({marker_literal}, "w", encoding="utf-8") as output:
    json.dump({{"table": table.get_path_name(), "data_asset": data_asset.get_path_name()}}, output)
'''


async def wait_for_session(manager: ConnectionManager, process: subprocess.Popen, timeout: float = 360):
    deadline = time.monotonic() + timeout
    while process.poll() is None and time.monotonic() < deadline:
        for session in manager.discover():
            if session.kind != "unreal" or session.pid != process.pid:
                continue
            try:
                await manager.request(session, "health")
                return session
            except BridgeError:
                pass
        await asyncio.sleep(0.2)
    raise RuntimeError("Disposable Unreal Editor bridge did not become ready.")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def verify(project: Path, editor: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    project = project.resolve(strict=True)
    saved_root = repository / "Saved"
    if project.parent.parent.parent != saved_root or not project.parent.parent.name.startswith("TransferImportValidation-"):
        raise ValueError("Only the generated disposable TransferImportValidation host is allowed.")

    root = project.parent / "Saved" / ("DataTableAcceptance-" + uuid.uuid4().hex)
    root.mkdir(parents=True)
    session_root = project.parent / "Saved" / "MajesticForge"
    session_root.mkdir(parents=True, exist_ok=True)
    fixture_name = "DT_ForgeMCP_" + uuid.uuid4().hex[:12]
    asset_path = f"/Game/ForgeMCPValidation/{fixture_name}/{fixture_name}.{fixture_name}"
    marker = root / "fixture-created.txt"
    script = project.parent / "Content" / "Python" / "init_unreal.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(fixture_script(fixture_name, marker).replace(
        '"/Game/ForgeMCPValidation"', f'"/Game/ForgeMCPValidation/{fixture_name}"'
    ), encoding="utf-8")
    prepare_python_enabled_project(project)

    log_path = root / "unreal.log"
    command = [
        str(editor.resolve(strict=True)), str(project),
        "/Engine/Maps/Templates/Template_Default", "-Unattended", "-NullRHI",
        "-NoSound", "-NoSplash", "-NoLiveCoding", "-NoSourceControl",
        f"-abslog={log_path}",
    ]
    env = {
        **os.environ,
        "FORGE_PROJECT_ROOT": str(repository),
        "FORGE_UNREAL_SESSION_DIR": str(session_root),
    }
    process = subprocess.Popen(command, cwd=project.parent, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        manager = ConnectionManager([session_root], timeout=30)
        session = await wait_for_session(manager, process)
        deadline = time.monotonic() + 60
        while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        if not marker.exists():
            raise RuntimeError("The disposable DataTable fixture script did not finish; inspect its retained UE log.")
        if process.poll() is not None:
            raise RuntimeError("The disposable Unreal Editor exited after preparing the DataTable fixture.")
        fixture = json.loads(marker.read_text(encoding="utf-8"))
        table_path = fixture["table"]
        data_asset_path = fixture["data_asset"]
        if table_path != asset_path:
            raise AssertionError(f"Fixture created at an unexpected path: {table_path}")
        expected_data_asset_path = f"/Game/ForgeMCPValidation/{fixture_name}/{fixture_name}_DataAsset.{fixture_name}_DataAsset"
        if data_asset_path != expected_data_asset_path:
            raise AssertionError(f"DataAsset fixture created at an unexpected path: {data_asset_path}")
        package_file = project.parent / "Content" / "ForgeMCPValidation" / fixture_name / f"{fixture_name}.uasset"
        data_asset_file = project.parent / "Content" / "ForgeMCPValidation" / fixture_name / f"{fixture_name}_DataAsset.uasset"
        disk_hash_before = sha256(package_file)
        data_asset_hash_before = sha256(data_asset_file)

        server_env = {**env, "PYTHONPATH": str(repository)}
        parameters = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                           cwd=str(repository), env=server_env)
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()

                async def call(name: str, arguments: dict) -> dict:
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                    return result.structuredContent

                schema = await call("unreal_inspect_data_table_schema", {
                    "session_id": session.session_id, "data_table_path": table_path,
                })
                assert schema["ok"], schema
                fields = {field["name"].lower().replace("_", ""): field for field in schema["data"]["fields"]}
                assert fields["tag"]["supported_value_type"] is True, fields
                assert fields["devcomment"]["supported_value_type"] is True, fields

                first_page = await call("unreal_list_data_table_rows", {
                    "session_id": session.session_id, "data_table_path": table_path,
                    "limit": 1, "offset": 0,
                })
                second_page = await call("unreal_list_data_table_rows", {
                    "session_id": session.session_id, "data_table_path": table_path,
                    "limit": 1, "offset": 1,
                })
                assert first_page["ok"] and first_page["data"]["row_count"] == 2, first_page
                assert first_page["data"]["row_names"] == ["RowAlpha"], first_page
                assert second_page["data"]["row_names"] == ["RowBeta"], second_page

                row = await call("unreal_inspect_data_table_row", {
                    "session_id": session.session_id, "data_table_path": table_path,
                    "row_name": "RowBeta",
                })
                assert row["ok"], row
                values = {field["name"].lower().replace("_", ""): field for field in row["data"]["fields"]}
                assert values["tag"]["value"] == "ForgeMCP.Acceptance.Beta", values
                assert values["devcomment"]["value"] == "beta note", values

                missing_row = await call("unreal_inspect_data_table_row", {
                    "session_id": session.session_id, "data_table_path": table_path,
                    "row_name": "AbsentRow",
                })
                assert not missing_row["ok"] and missing_row["error"]["code"] == "row_not_found", missing_row
                denied_path = await call("unreal_inspect_data_table_schema", {
                    "session_id": session.session_id,
                    "data_table_path": "/Engine/EngineMaterials/DefaultMaterial",
                })
                assert not denied_path["ok"] and denied_path["error"]["code"] == "unsupported_asset_path", denied_path

                listed_data_assets = await call("unreal_list_data_assets", {
                    "session_id": session.session_id, "path": f"/Game/ForgeMCPValidation/{fixture_name}",
                    "class_filter": "PrimaryAssetLabel", "max_results": 10,
                })
                assert listed_data_assets["ok"], listed_data_assets
                assert [asset["asset_path"] for asset in listed_data_assets["data"]["assets"]] == [data_asset_path], listed_data_assets
                classes = await call("unreal_list_data_asset_classes", {
                    "session_id": session.session_id, "filter": "PrimaryAssetLabel", "limit": 10,
                })
                assert classes["ok"], classes
                assert any(item["class_path"] == "/Script/Engine.PrimaryAssetLabel" for item in classes["data"]["classes"]), classes
                abstract_classes = await call("unreal_list_data_asset_classes", {
                    "session_id": session.session_id, "filter": "PrimaryDataAsset",
                    "include_abstract": True, "limit": 10,
                })
                assert abstract_classes["ok"], abstract_classes
                assert any(item["class_path"] == "/Script/Engine.PrimaryDataAsset" and item["abstract"]
                           for item in abstract_classes["data"]["classes"]), abstract_classes
                data_asset_schema = await call("unreal_inspect_data_asset_schema", {
                    "session_id": session.session_id,
                    "class_path": "/Script/Engine.PrimaryAssetLabel",
                    "include_inherited": True, "limit": 64,
                })
                assert data_asset_schema["ok"], data_asset_schema
                asset_properties = {item["name"]: item for item in data_asset_schema["data"]["properties"]}
                assert asset_properties["bIsRuntimeLabel"]["value_kind"] == "boolean", asset_properties
                assert asset_properties["ExplicitAssets"]["value_kind"] == "array", asset_properties
                assert asset_properties["ExplicitAssets"]["element_type"], asset_properties
                assert data_asset_schema["data"]["loads_assets"] is False, data_asset_schema
                create_name = "DA_CreateProbe_" + uuid.uuid4().hex[:12]
                create_package = f"/Game/ForgeMCPValidation/{fixture_name}/{create_name}"
                create_preview = await call("unreal_preview_data_asset", {
                    "session_id": session.session_id,
                    "request": {
                        "asset_path": create_package,
                        "class_path": "/Script/Engine.PrimaryAssetLabel",
                        "properties": [{"name": "bIsRuntimeLabel", "value": "true"}],
                        "save": True,
                    },
                })
                assert create_preview["ok"], create_preview
                create_plan = create_preview["data"]
                assert create_plan["overwrites_existing_asset"] is False, create_preview
                assert create_plan["save"] is True, create_preview
                wrong_confirmation = await call("unreal_apply_data_asset", {
                    "session_id": session.session_id,
                    "preview_id": create_plan["preview_id"],
                    "confirmation": "0" * 32,
                })
                assert not wrong_confirmation["ok"] and wrong_confirmation["error"]["code"] == "confirmation_required", wrong_confirmation
                created_asset = await call("unreal_apply_data_asset", {
                    "session_id": session.session_id,
                    "preview_id": create_plan["preview_id"],
                    "confirmation": create_plan["preview_id"],
                })
                assert created_asset["ok"] and created_asset["data"]["saved"] is True, created_asset
                created_object_path = create_package + "." + create_name
                created_properties = await call("unreal_inspect_asset_properties", {
                    "session_id": session.session_id, "asset_path": created_object_path,
                })
                assert created_properties["ok"], created_properties
                runtime_label = next(item for item in created_properties["data"]["properties"]
                                     if item["name"] == "bIsRuntimeLabel")
                assert runtime_label["value"] is True, created_properties
                created_file = project.parent / "Content" / "ForgeMCPValidation" / fixture_name / f"{create_name}.uasset"
                created_hash_before_edit = sha256(created_file)
                edit_request = {
                    "session_id": session.session_id,
                    "request": {
                        "asset_path": created_object_path,
                        "properties": [
                            {"name": "bIsRuntimeLabel", "value": "false"},
                            {"name": "bIncludeRedirectors", "value": "false"},
                        ],
                        "save": True,
                    },
                }
                edit_preview = await call("unreal_preview_data_asset_edit", edit_request)
                assert edit_preview["ok"], edit_preview
                edit_plan = edit_preview["data"]
                assert len(edit_plan["properties"]) == 2 and edit_plan["save"] is True, edit_preview
                backup_path = Path(edit_plan["backup_path"])
                assert backup_path.is_absolute() and not backup_path.exists(), edit_preview
                stale_edit_preview = await call("unreal_preview_data_asset_edit", edit_request)
                assert stale_edit_preview["ok"], stale_edit_preview
                wrong_edit_confirmation = await call("unreal_apply_data_asset_edit", {
                    "session_id": session.session_id,
                    "preview_id": edit_plan["preview_id"],
                    "confirmation": "0" * 32,
                })
                assert not wrong_edit_confirmation["ok"] and wrong_edit_confirmation["error"]["code"] == "confirmation_required", wrong_edit_confirmation
                edited_asset = await call("unreal_apply_data_asset_edit", {
                    "session_id": session.session_id,
                    "preview_id": edit_plan["preview_id"],
                    "confirmation": edit_plan["preview_id"],
                })
                assert edited_asset["ok"] and edited_asset["data"]["saved"] is True, edited_asset
                assert edited_asset["data"]["backup_preserved"] is True, edited_asset
                assert backup_path.is_file() and sha256(backup_path) == created_hash_before_edit, backup_path
                edited_properties = await call("unreal_inspect_asset_properties", {
                    "session_id": session.session_id, "asset_path": created_object_path,
                })
                assert edited_properties["ok"], edited_properties
                edited_values = {item["name"]: item["value"] for item in edited_properties["data"]["properties"]}
                assert edited_values["bIsRuntimeLabel"] is False and edited_values["bIncludeRedirectors"] is False, edited_properties
                stale_edit = await call("unreal_apply_data_asset_edit", {
                    "session_id": session.session_id,
                    "preview_id": stale_edit_preview["data"]["preview_id"],
                    "confirmation": stale_edit_preview["data"]["preview_id"],
                })
                assert not stale_edit["ok"] and stale_edit["error"]["code"] == "stale_preview", stale_edit
                created_list = await call("unreal_list_data_assets", {
                    "session_id": session.session_id,
                    "path": f"/Game/ForgeMCPValidation/{fixture_name}",
                    "class_filter": "PrimaryAssetLabel", "max_results": 20,
                })
                assert created_list["ok"] and any(item["asset_path"] == created_object_path
                                                   for item in created_list["data"]["assets"]), created_list
                duplicate_preview = await call("unreal_preview_data_asset", {
                    "session_id": session.session_id,
                    "request": {"asset_path": create_package,
                                "class_path": "/Script/Engine.PrimaryAssetLabel"},
                })
                assert not duplicate_preview["ok"] and duplicate_preview["error"]["code"] == "asset_exists", duplicate_preview
                assert created_file.is_file(), f"Saved DataAsset package missing: {created_file}"
                created_hash = sha256(created_file)
                own_properties = await call("unreal_inspect_data_asset_schema", {
                    "session_id": session.session_id,
                    "class_path": "/Script/Engine.PrimaryAssetLabel",
                    "include_inherited": False, "limit": 1,
                })
                assert own_properties["ok"] and own_properties["data"]["truncated"], own_properties
                assert all(not item["inherited"] for item in own_properties["data"]["properties"]), own_properties
                wrong_schema_class = await call("unreal_inspect_data_asset_schema", {
                    "session_id": session.session_id, "class_path": "/Script/Engine.Actor",
                })
                assert not wrong_schema_class["ok"] and wrong_schema_class["error"]["code"] == "unsupported_data_asset_class", wrong_schema_class

                disk_hash_after = sha256(package_file)
                assert disk_hash_after == disk_hash_before, "Read-only inspections changed the saved DataTable package."
                assert sha256(data_asset_file) == data_asset_hash_before, "Read-only inspections changed the saved DataAsset package."
                report = {
                    "interactive_verified": False,
                    "project_file": str(project),
                    "session_id": session.session_id,
                    "asset_path": table_path,
                    "schema": schema,
                    "rows_page_1": first_page,
                    "rows_page_2": second_page,
                    "row_inspection": row,
                    "missing_row_rejected": missing_row,
                    "engine_path_rejected": denied_path,
                    "data_assets": listed_data_assets,
                    "data_asset_classes": classes,
                    "abstract_data_asset_classes": abstract_classes,
                    "data_asset_schema": data_asset_schema,
                    "data_asset_create_preview": create_preview,
                    "data_asset_wrong_confirmation_rejected": wrong_confirmation,
                    "data_asset_create_apply": created_asset,
                    "data_asset_property_readback": created_properties,
                    "data_asset_edit_preview": edit_preview,
                    "data_asset_edit_wrong_confirmation_rejected": wrong_edit_confirmation,
                    "data_asset_edit_apply": edited_asset,
                    "data_asset_edit_property_readback": edited_properties,
                    "data_asset_edit_stale_preview_rejected": stale_edit,
                    "data_asset_edit_backup_sha256": sha256(backup_path),
                    "data_asset_asset_registry_query": created_list,
                    "data_asset_duplicate_creation_rejected": duplicate_preview,
                    "created_data_asset_sha256": created_hash,
                    "data_asset_schema_without_inherited": own_properties,
                    "wrong_data_asset_schema_class_rejected": wrong_schema_class,
                    "disk_package_unchanged": True,
                    "package_sha256": disk_hash_after,
                    "data_asset_package_sha256": data_asset_hash_before,
                }
                if process.poll() is None:
                    process.terminate()
                    try:
                        await asyncio.to_thread(process.wait, timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        await asyncio.to_thread(process.wait, timeout=10)
                reopen_marker = root / "data-asset-reopened.json"
                script.write_text(
                    f'''import json, unreal\nasset = unreal.load_asset({created_object_path!r})\nif not asset:\n    raise RuntimeError("Saved DataAsset could not be loaded in the fresh editor process")\nvalues = {{"bIsRuntimeLabel": asset.get_editor_property("bIsRuntimeLabel"), "bIncludeRedirectors": asset.get_editor_property("bIncludeRedirectors")}}\nwith open({json.dumps(str(reopen_marker))}, "w", encoding="utf-8") as output:\n    json.dump(values, output)\n''',
                    encoding="utf-8",
                )
                reopen_log = root / "reopen.log"
                process = subprocess.Popen(command[:-1] + [f"-abslog={reopen_log}"], cwd=project.parent, env=env,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                reopen_deadline = time.monotonic() + 360
                while not reopen_marker.exists() and process.poll() is None and time.monotonic() < reopen_deadline:
                    await asyncio.sleep(0.2)
                if not reopen_marker.exists():
                    raise RuntimeError("Fresh Editor process did not reopen and inspect the saved DataAsset.")
                reopened_values = json.loads(reopen_marker.read_text(encoding="utf-8"))
                assert reopened_values == {"bIsRuntimeLabel": False, "bIncludeRedirectors": False}, reopened_values
                report["data_asset_fresh_process_reopen"] = reopened_values
                (root / "acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Evidence: {root}", flush=True)
        print("FORGEMCP_DATA_TABLE_MCP_INSPECTION_PASS", flush=True)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--editor", type=Path, required=True)
    arguments = parser.parse_args()
    asyncio.run(verify(arguments.project, arguments.editor))
