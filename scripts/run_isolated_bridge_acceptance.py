"""Read-only isolated bridge acceptance for a disposable UE 5.6.1 project.

This runner launches a fresh disposable Editor and a dedicated isolated MCP host.
It checks authentication, process/session pins, dirty-package snapshot paging, and
Landscape inspection/preview contracts. It never applies a Landscape preview.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

# Prefer the checked-out 0.3.14 source and editable metadata over stale wheels
# that may also exist in the virtualenv's site-packages directory.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) in sys.path:
    sys.path.remove(str(REPOSITORY_ROOT))
sys.path.insert(0, str(REPOSITORY_ROOT))

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from run_isolated_landscape_acceptance import (  # noqa: E402
    _assert_disjoint,
    _extract_release,
    _host_environment,
    _make_project,
    _protect_root,
    _registration,
    _stop_disposable_editor,
)

from server.core.host_config import IsolatedHostConfig  # noqa: E402
from server.core.process_identity import (  # noqa: E402
    WindowsProcessIdentityProbe,
    validate_process_snapshot,
)


def _ok_data(result: dict, operation: str) -> dict:
    if not result.get("ok") or not isinstance(result.get("data"), dict):
        error = result.get("error", {})
        raise RuntimeError(f"{operation} failed: {error.get('code', 'invalid_response')}")
    return result["data"]


async def _call(client: ClientSession, name: str, arguments: dict) -> dict:
    result = await client.call_tool(name, arguments)
    if result.isError or result.structuredContent is None:
        raise RuntimeError(f"MCP tool {name} returned an invalid or error result")
    return result.structuredContent


async def _exercise_dedicated_host(
    *, repository: Path, environment: dict[str, str], session_id: str,
    process_id: int, project_file: Path,
) -> dict:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.isolated_host"],
        cwd=str(repository),
        env=environment,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            initialized = await client.initialize()
            if initialized.serverInfo.name != "ForgeMCP":
                raise RuntimeError("Dedicated host identified itself as an unexpected server")
            tools = (await client.list_tools()).tools
            by_name = {tool.name: tool for tool in tools}
            required = {
                "forge_status",
                "unreal_inspect_dirty_packages",
                "unreal_inspect_landscape",
                "unreal_preview_landscape",
                "unreal_apply_landscape",
            }
            if not required.issubset(by_name):
                raise RuntimeError("Dedicated isolated tool catalog is missing required acceptance tools")

            input_schema = by_name["unreal_inspect_dirty_packages"].inputSchema
            request_property = input_schema["properties"]["request"]
            request_ref = request_property.get("$ref")
            if not isinstance(request_ref, str) or not request_ref.startswith("#/$defs/"):
                raise RuntimeError("MCP dirty-package request schema has an unsupported reference")
            request_schema_name = request_ref.rsplit("/", 1)[-1]
            request_schema = input_schema["$defs"][request_schema_name]
            if "snapshot_id" not in request_schema.get("properties", {}):
                raise RuntimeError("MCP dirty-package request schema omits snapshot_id")
            if "snapshot_id" in request_schema.get("required", []):
                raise RuntimeError("MCP dirty-package snapshot_id must remain optional for first-page callers")

            status = await _call(client, "forge_status", {"session_id": session_id})
            status_data = _ok_data(status, "isolated host status")
            sessions = status_data.get("sessions", [])
            if len(sessions) != 1 or sessions[0].get("session_id") != session_id:
                raise RuntimeError("Host status did not resolve exactly the allowlisted disposable Editor")
            if not sessions[0].get("connected"):
                raise RuntimeError("Dedicated host could not authenticate to the disposable Editor")

            first_result = await _call(client, "unreal_inspect_dirty_packages", {
                "session_id": session_id,
                "request": {"limit": 1, "offset": 0},
            })
            first = _ok_data(first_result, "dirty-package first page")
            if first.get("read_only") is not True:
                raise RuntimeError("Dirty-package observer did not mark its result read-only")
            snapshot_id = first.get("snapshot_id")
            if not isinstance(snapshot_id, str) or not re.fullmatch(r"[A-Fa-f0-9]{32}", snapshot_id):
                raise RuntimeError("First dirty-package page did not return a valid snapshot_id")
            if first.get("inventory_id") != snapshot_id:
                raise RuntimeError("Legacy inventory_id compatibility alias does not match snapshot_id")

            pages = [first]
            while pages[-1].get("has_more_observed_results"):
                next_offset = pages[-1].get("next_offset")
                if type(next_offset) is not int:
                    raise RuntimeError("Dirty-package page announced more results without next_offset")
                result = await _call(client, "unreal_inspect_dirty_packages", {
                    "session_id": session_id,
                    "request": {
                        "limit": 1,
                        "offset": next_offset,
                        "snapshot_id": snapshot_id,
                    },
                })
                page = _ok_data(result, "dirty-package continuation page")
                if page.get("snapshot_id") != snapshot_id or page.get("inventory_id") != snapshot_id:
                    raise RuntimeError("Dirty-package continuation left its immutable snapshot")
                pages.append(page)

            # Always exercise a same-snapshot continuation, even when the disposable
            # Editor has fewer than two dirty rows. This does not claim multiple rows.
            if len(pages) > 1:
                continuation = pages[1]
            else:
                continuation_result = await _call(client, "unreal_inspect_dirty_packages", {
                    "session_id": session_id,
                    "request": {"limit": 1, "offset": 1, "snapshot_id": snapshot_id},
                })
                continuation = _ok_data(continuation_result, "same-snapshot continuation check")
            if continuation.get("snapshot_id") != snapshot_id:
                raise RuntimeError("Same-snapshot continuation returned a different snapshot ID")

            malformed = await client.call_tool("unreal_inspect_dirty_packages", {
                "session_id": session_id,
                "request": {"limit": 1, "offset": 1, "snapshot_id": "bad"},
            })
            if not malformed.isError:
                raise RuntimeError("Malformed snapshot ID was not rejected by the MCP request schema")

            unknown_id = uuid.uuid4().hex
            while unknown_id == snapshot_id:
                unknown_id = uuid.uuid4().hex
            unknown_result = await _call(client, "unreal_inspect_dirty_packages", {
                "session_id": session_id,
                "request": {"limit": 1, "offset": 1, "snapshot_id": unknown_id},
            })
            if unknown_result.get("ok") is not False or unknown_result.get("error", {}).get("code") != "snapshot_expired":
                raise RuntimeError("Unknown dirty-package snapshot ID was not rejected")

            wrong_session = await _call(client, "unreal_inspect_dirty_packages", {
                "session_id": f"unreal-{process_id + 1}",
                "request": {"limit": 1, "offset": 1, "snapshot_id": snapshot_id},
            })
            if wrong_session.get("ok") is not False or wrong_session.get("error", {}).get("code") != "session_not_allowed":
                raise RuntimeError("Mismatched session was not rejected by isolated-host policy")

            lifetime = first.get("snapshot_lifetime_seconds")
            if type(lifetime) not in (int, float) or lifetime <= 0 or lifetime > 60:
                raise RuntimeError("Native dirty-package snapshot lifetime is outside the bounded policy")
            await asyncio.sleep(float(lifetime) + 1.0)
            expired = await _call(client, "unreal_inspect_dirty_packages", {
                "session_id": session_id,
                "request": {"limit": 1, "offset": 1, "snapshot_id": snapshot_id},
            })
            if expired.get("ok") is not False or expired.get("error", {}).get("code") != "snapshot_expired":
                raise RuntimeError("Expired dirty-package snapshot was not rejected")

            dirty_rows = [row for page in pages for row in page.get("packages", [])]
            unresolved_rows = [
                row for row in dirty_rows
                if row.get("classification_complete") is False
                or row.get("ownership_scan_complete") is False
            ]
            complete = all(page.get("inventory_complete") is True for page in pages)
            if not complete:
                raise RuntimeError("Native dirty-package inventory reported an incomplete scan")

            landscape_result = await _call(client, "unreal_inspect_landscape", {
                "session_id": session_id,
                "actor_path": "",
            })
            landscape = _ok_data(landscape_result, "Landscape inspection")

            map_name = f"L_A7K35_ReadOnly_{uuid.uuid4().hex[:8]}"
            map_path = f"/Game/ForgeMCPTests/Landscape/{map_name}"
            preview_result = await _call(client, "unreal_preview_landscape", {
                "session_id": session_id,
                "request": {
                    "action": "create",
                    "map_path": map_path,
                    "components_x": 1,
                    "components_y": 1,
                    "quads_per_section": 7,
                    "sections_per_component": 1,
                    "world_partition": False,
                    "use_engine_basic_landscape_material": False,
                },
            })
            preview = _ok_data(preview_result, "Landscape create preview")
            preview_id = preview.get("preview_id")
            if not isinstance(preview_id, str) or not re.fullmatch(r"[0-9A-Fa-f]{32}", preview_id):
                raise RuntimeError(
                    f"Landscape preview did not return a 32-hex preview_id; returned fields: {sorted(preview)}"
                )
            incorrect_confirmation = "f" * 32
            if incorrect_confirmation == preview_id:
                incorrect_confirmation = "e" * 32
            rejected_apply = await _call(client, "unreal_apply_landscape", {
                "session_id": session_id,
                "preview_id": preview_id,
                "confirmation": incorrect_confirmation,
            })
            if rejected_apply.get("ok") is not False or rejected_apply.get("error", {}).get("code") != "confirmation_required":
                raise RuntimeError("Landscape apply contract did not reject mismatched confirmation")

            map_file = project_file.parent / "Content" / "ForgeMCPTests" / "Landscape" / f"{map_name}.umap"
            if map_file.exists():
                raise RuntimeError("Landscape preview unexpectedly created a map asset")

            report = {
                "host": "dedicated server.isolated_host over MCP stdio",
                "core_version": importlib.metadata.version("majestic-forge-mcp"),
                "session_id": session_id,
                "process_id": process_id,
                "authenticated_status": "PASS",
                "private_allowlist": "one exact disposable Unreal session",
                "dirty_inventory": {
                    "first_page": "PASS",
                    "snapshot_id_exposed": True,
                    "legacy_inventory_id_preserved": True,
                    "continuation_same_snapshot": "PASS",
                    "pages_with_results": len(pages),
                    "observed_rows": len(dirty_rows),
                    "inventory_complete": complete,
                    "unresolved_rows": len(unresolved_rows),
                    "malformed_snapshot_rejected": True,
                    "unknown_snapshot_rejected": True,
                    "mismatched_session_rejected": True,
                    "expired_snapshot_rejected": True,
                    "unresolved_rows_retained_in_returned_pages": len(unresolved_rows),
                },
                "landscape": {
                    "inspection": "PASS",
                    "current_world_landscape_count": landscape.get("total_count"),
                    "preview": "PASS",
                    "apply_wrong_confirmation_rejected": True,
                    "apply_executed": False,
                    "test_map_path": map_path,
                    "map_file_created": False,
                },
                "limitations": [
                    "No Landscape apply, asset creation, save, or reload was executed.",
                    "The disposable Editor may contain fewer than two dirty rows; synthetic multi-page behavior is covered by automated unit tests.",
                    "An incomplete inventory stops acceptance; unresolved classification rows are preserved and reported, not treated as clean.",
                ],
            }
            return report


async def _run(args: argparse.Namespace) -> dict:
    if os.name != "nt":
        raise RuntimeError("This isolated Unreal acceptance runner requires Windows")
    core_version = importlib.metadata.version("majestic-forge-mcp")
    if core_version != "0.3.14":
        raise RuntimeError(f"Expected ForgeMCP core 0.3.14, found {core_version}")

    repository = REPOSITORY_ROOT
    editor = args.editor.resolve(strict=True)
    archive = args.archive.resolve(strict=True)
    engine_root = editor.parents[3]
    build_version = json.loads((engine_root / "Engine/Build/Build.version").read_text())
    if (build_version.get("MajorVersion"), build_version.get("MinorVersion"),
            build_version.get("PatchVersion")) != (5, 6, 1):
        raise RuntimeError("The selected Editor executable is not Unreal Engine 5.6.1")

    local_app_data = Path(os.environ["LOCALAPPDATA"]).resolve(strict=True)
    shared_root = Path(os.environ.get(
        "FORGE_SHARED_SESSION_DIR", local_app_data / "MajesticForge" / "sessions"
    )).resolve(strict=False)
    test_id = uuid.uuid4().hex
    private_root = local_app_data / "ForgeMCP" / "IsolatedBridgeAcceptance" / test_id
    _assert_disjoint(shared_root, private_root)
    private_root.mkdir(parents=True, exist_ok=False)
    acl_result = _protect_root(private_root)
    for relative in ("registry/unreal", "registry/blender", "temp", "logs", "state"):
        (private_root / relative).mkdir(parents=True, exist_ok=False)

    project_file = private_root / "state" / "ForgeMCPDev.uproject"
    _make_project(project_file)
    plugin_root = project_file.parent / "Plugins" / "Forge"
    manifest, archive_sha256 = _extract_release(archive, plugin_root)
    if manifest.get("plugin_version") != "0.2.14-alpha.3":
        raise RuntimeError("Unreal plugin archive version does not match the requested candidate")

    editor_log = private_root / "logs" / "UnrealEditor.log"
    editor_env = dict(os.environ)
    editor_env.update({
        "FORGE_UNREAL_SESSION_DIR": str(private_root / "registry" / "unreal"),
        "FORGE_SESSION_DIR": str(private_root / "registry"),
        "TEMP": str(private_root / "temp"),
        "TMP": str(private_root / "temp"),
    })
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    registration_path = private_root / "registry" / "unreal" / "pending-registration.json"
    process: subprocess.Popen | None = None
    try:
        with editor_log.open("x", encoding="utf-8") as log_stream:
            process = subprocess.Popen(
                [
                    str(editor), str(project_file), "-Unattended", "-NullRHI", "-NoSplash",
                    "-NoSound", "-NoLiveCoding", "-NoSourceControl", f"-abslog={editor_log}",
                ],
                cwd=project_file.parent,
                env=editor_env,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
                startupinfo=startup,
            )

        session_id = f"unreal-{process.pid}"
        registration_path = private_root / "registry" / "unreal" / f"{session_id}.json"
        atexit.register(_stop_disposable_editor, process, registration_path)
        deadline = time.monotonic() + args.startup_timeout
        while time.monotonic() < deadline and process.poll() is None:
            if registration_path.is_file():
                break
            await asyncio.sleep(0.25)
        if process.poll() is not None:
            raise RuntimeError(f"Disposable Editor exited during startup; inspect {editor_log}")
        if not registration_path.is_file():
            raise TimeoutError(f"Disposable Editor did not publish its private registration; inspect {editor_log}")
        unexpected = [
            path for path in (private_root / "registry" / "unreal").glob("*.json")
            if path != registration_path
        ]
        if unexpected:
            raise RuntimeError("Unexpected registration appeared in the disposable private registry")

        session_id, port = _registration(registration_path, process.pid)
        process_snapshot = WindowsProcessIdentityProbe()(process.pid, port)
        environment = _host_environment(
            root=private_root,
            project_file=project_file,
            executable=editor,
            process_id=process.pid,
            session_id=session_id,
            port=port,
            start_utc=process_snapshot.creation_utc,
            shared_root=shared_root,
        )
        config = IsolatedHostConfig.from_env(environment)
        validate_process_snapshot(process_snapshot, config)
        discovered = [
            path for path in config.unreal_registry_root.glob("*.json")
            if path.name == registration_path.name
        ]
        if len(discovered) != 1:
            raise RuntimeError("Private registry did not contain exactly the pinned disposable session")
        acl = subprocess.run(
            ["icacls", str(config.unreal_registry_root)],
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout.casefold()
        if any(value in acl for value in ("everyone", "authenticated users", "builtin\\users")):
            raise RuntimeError("Disposable private registration ACL grants access to a broad principal")

        report = await _exercise_dedicated_host(
            repository=repository,
            environment=environment,
            session_id=session_id,
            process_id=process.pid,
            project_file=project_file,
        )
        from verify_unreal_package import loaded_module_path

        module_path = await asyncio.to_thread(
            loaded_module_path, process.pid, "UnrealEditor-MajesticForge.dll"
        )
        expected_module = plugin_root / "Binaries" / "Win64" / "UnrealEditor-MajesticForge.dll"
        if module_path != expected_module.resolve():
            raise RuntimeError("Disposable Editor loaded the plugin binary from an unexpected path")
        module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
        expected_hash = manifest["files"]["Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll"]
        if module_hash != expected_hash:
            raise RuntimeError("Disposable Editor plugin binary does not match the archive manifest")
        report.update({
            "result": "PASS",
            "unreal_version": "5.6.1",
            "plugin_version": manifest["plugin_version"],
            "plugin_archive_sha256": archive_sha256,
            "loaded_plugin_module_path": str(module_path),
            "loaded_plugin_module_sha256": module_hash,
            "private_root": str(private_root),
            "private_root_acl": acl_result["protected_acl"],
            "registration_acl_checked": True,
            "project_file": str(project_file),
            "process_identity": {
                "pid": process_snapshot.pid,
                "executable_path": process_snapshot.executable_path,
                "project_argument": str(project_file),
                "creation_utc": process_snapshot.creation_utc,
                "listener_pids": list(process_snapshot.listener_pids),
                "listener_addresses": list(process_snapshot.listener_addresses),
            },
        })
        result_path = private_root / "logs" / "isolated-bridge-acceptance.json"
        with result_path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        return report
    finally:
        if process is not None:
            _stop_disposable_editor(process, registration_path)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--startup-timeout", type=int, default=240)
    args = parser.parse_args()
    report = await _run(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
