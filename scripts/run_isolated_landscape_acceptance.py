"""Launch a disposable UE host with a private registration and run the landscape suite."""

from __future__ import annotations

import argparse
import asyncio
import atexit
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
import zipfile
import zlib
from pathlib import Path

# Support both direct-script and ``python -m`` invocation from any working
# directory. The runner invokes helper scripts as files and imports core code.
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
for _import_root in (_REPOSITORY_ROOT, _REPOSITORY_ROOT / "scripts"):
    _import_root_text = str(_import_root)
    if _import_root_text not in sys.path:
        sys.path.insert(0, _import_root_text)

from server.core.connections import BridgeError, ConnectionManager  # noqa: E402
from server.core.host_config import IsolatedHostConfig  # noqa: E402
from server.core.process_identity import (  # noqa: E402
    WindowsProcessIdentityProbe,
    validate_process_snapshot,
)


def _assert_disjoint(parent: Path, candidate: Path) -> None:
    parent = parent.resolve()
    candidate = candidate.resolve()
    if parent == candidate or parent in candidate.parents or candidate in parent.parents:
        raise RuntimeError("Private validation storage overlaps the shared session root")


def _protect_root(path: Path) -> dict[str, str]:
    identity = subprocess.run(
        ["whoami"], check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    result = subprocess.run(
        [
            "icacls", str(path), "/inheritance:r", "/grant:r",
            f"{identity}:(OI)(CI)F", "SYSTEM:(OI)(CI)F",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    verification = subprocess.run(
        ["icacls", str(path)], check=True, capture_output=True, text=True, timeout=10,
    ).stdout
    folded = verification.casefold()
    if any(value in folded for value in ("everyone", "authenticated users", "builtin\\users")):
        raise RuntimeError("The private test root grants access to a broad Windows principal")
    if identity.casefold() not in folded or "system:" not in folded:
        raise RuntimeError("The private test root ACL does not show the expected owner and SYSTEM")
    return {"owner": identity, "protected_acl": "owner and SYSTEM only", "icacls_result": result.stdout.strip()}


def _extract_release(archive_path: Path, plugin_root: Path) -> tuple[dict, str]:
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        if "package-manifest.json" not in names:
            raise ValueError("The Unreal archive has no package manifest")
        manifest = json.loads(archive.read("package-manifest.json"))
        if (
            manifest.get("package_kind") != "development_editor_plugin"
            or manifest.get("engine_version") != "5.6.1"
            or manifest.get("interactive_acceptance_complete") is not False
            or manifest.get("core_compatibility", {}).get("tested_version") != "0.3.15"
            or manifest.get("landscape_write_scope_schema") != 2
            or manifest.get("plugin_version") != "0.2.16-alpha.1"
            or manifest.get("dirty_package_classification_schema") != 2
        ):
            raise ValueError("The Unreal archive manifest is outside the expected development scope")
        payload_names = names - {"package-manifest.json"}
        if payload_names != set(manifest.get("files", {})):
            raise ValueError("Archive contents do not match its declared file set")
        for name in sorted(payload_names):
            if not name.startswith("Forge/"):
                raise ValueError("Unexpected path in Unreal archive")
            relative = Path(name).relative_to("Forge")
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Unsafe path in Unreal archive")
            data = archive.read(name)
            if hashlib.sha256(data).hexdigest() != manifest["files"][name]:
                raise ValueError(f"Archive hash mismatch: {name}")
            destination = plugin_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(data)
    return manifest, hashlib.sha256(archive_path.read_bytes()).hexdigest()


def _make_project(project_file: Path) -> None:
    descriptor = {
        "FileVersion": 3,
        "EngineAssociation": "5.6",
        "DisableEnginePluginsByDefault": True,
        "Plugins": [
            {"Name": "Cargo", "Enabled": False},
            {"Name": "Metasound", "Enabled": True},
            {"Name": "PluginBrowser", "Enabled": True},
            {"Name": "GameplayAbilities", "Enabled": True},
            {"Name": "WebBrowserWidget", "Enabled": True},
            {
                "Name": "MajesticForge",
                "Enabled": True,
                "TargetAllowList": ["Editor"],
                "SupportedTargetPlatforms": ["Win64"],
            },
        ],
    }
    with project_file.open("x", encoding="utf-8") as stream:
        json.dump(descriptor, stream, indent=2)
        stream.write("\n")
    config = project_file.parent / "Config"
    config.mkdir(exist_ok=False)
    (config / "DefaultEngine.ini").write_text(
        "[/Script/EngineSettings.GameMapsSettings]\n"
        "EditorStartupMap=/Engine/Maps/Entry\n"
        "GameDefaultMap=/Engine/Maps/Entry\n",
        encoding="utf-8",
    )
    saved = project_file.parent / "Saved"
    saved.mkdir(exist_ok=False)
    marker = {
        "purpose": "forge_landscape_disposable_test",
        "test_id": uuid.uuid4().hex,
        "project_root": str(project_file.parent.resolve()),
        "project_file": str(project_file.resolve()),
    }
    with (saved / "ForgeMCPDisposableProject.json").open("x", encoding="utf-8") as stream:
        json.dump(marker, stream, indent=2)
        stream.write("\n")


def _snapshot_project_files(project_root: Path) -> dict[str, tuple[int, str]]:
    snapshot = {}
    for path in sorted(project_root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Refusing to audit a disposable project containing a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(project_root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        snapshot[relative] = (path.stat().st_size, digest)
    return snapshot


def _native_scope_paths(write_scope: dict, project_root: Path) -> tuple[set[str], set[str]]:
    root = project_root.resolve()
    exact_files: set[str] = set()
    package_sidecar_stems: set[str] = set()
    for field in ("exact_known_package_destinations", "exact_known_auxiliary_file_destinations"):
        entries = write_scope.get(field)
        if not isinstance(entries, list):
            raise RuntimeError(f"Native write-scope preview omitted {field}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
                raise RuntimeError(f"Native write-scope preview has an invalid entry in {field}")
            destination = Path(entry["filename"]).resolve(strict=False)
            try:
                relative = destination.relative_to(root).as_posix().casefold()
            except ValueError as error:
                raise RuntimeError("Native exact destination escaped the disposable project root") from error
            exact_files.add(relative)
            if destination.suffix.casefold() in {".umap", ".uasset"}:
                package_sidecar_stems.add(relative.rsplit(".", 1)[0])
    return exact_files, package_sidecar_stems


def _classify_write(relative_path: str, map_name: str,
                    exact_files: set[str] | None = None,
                    package_sidecar_stems: set[str] | None = None) -> str | None:
    path = relative_path.replace("\\", "/")
    lower = path.casefold()
    exact_files = exact_files or set()
    package_sidecar_stems = package_sidecar_stems or set()
    if lower in exact_files:
        return "exact native preview destination"
    map_parent = f"content/forgemcptests/landscape/{map_name.casefold()}/"
    actor_root = f"content/__externalactors__/forgemcptests/landscape/{map_name.casefold()}/"
    object_root = f"content/__externalobjects__/forgemcptests/landscape/{map_name.casefold()}/"
    if lower == f"content/forgemcptests/landscape/{map_name.casefold()}.umap":
        return "exact target map package"
    if lower.startswith(actor_root):
        return "target map World Partition external actor namespace"
    if lower.startswith(object_root):
        return "target map World Partition external object namespace"
    if lower.startswith("saved/forgelandscape/"):
        return "declared Forge Landscape job or map backup"
    if lower.startswith("saved/autosaves/"):
        return "Unreal autosave/recovery auxiliary data"
    if lower.startswith("saved/logs/"):
        return "Unreal diagnostic log auxiliary data"
    if lower == "saved/sourcecontrol/uncontrolledchangelists.json":
        return "Unreal source-control bookkeeping auxiliary data"
    if lower == "saved/config/windowseditor/editorperprojectusersettings.ini":
        return "Unreal per-project Editor UI settings auxiliary data"
    if lower == "saved/assetregistry.bin":
        return "Unreal project Asset Registry auxiliary data"
    if lower == f"saved/landscapedevelopment/phase6-{map_name.casefold()}.json":
        return "disposable acceptance report"
    # Unreal package sidecars are allowed only when adjacent to the exact map
    # or inside that map's generated external package namespaces.
    if lower.endswith((".uexp", ".ubulk", ".uptnl")):
        parent = lower.rsplit("/", 1)[0] + "/"
        sidecar_stem = lower.rsplit(".", 1)[0]
        if (sidecar_stem in package_sidecar_stems or
                parent == map_parent or
                parent.startswith(actor_root) or parent.startswith(object_root)):
            return "approved package sidecar"
    return None


def _audit_write_set(before: dict[str, tuple[int, str]], after: dict[str, tuple[int, str]],
                     map_name: str, write_scope: dict, project_root: Path) -> dict:
    exact_files, package_sidecar_stems = _native_scope_paths(write_scope, project_root)
    changes = []
    for relative in sorted(set(before) | set(after)):
        old = before.get(relative)
        new = after.get(relative)
        if old == new:
            continue
        classification = _classify_write(relative, map_name, exact_files, package_sidecar_stems)
        changes.append({
            "path": relative,
            "change": "added" if old is None else "removed" if new is None else "modified",
            "before_size": old[0] if old else None,
            "before_sha256": old[1] if old else None,
            "after_size": new[0] if new else None,
            "after_sha256": new[1] if new else None,
            "scope_classification": classification or "OUT_OF_SCOPE",
        })
    return {
        "change_count": len(changes),
        "out_of_scope_paths": [item["path"] for item in changes
                                if item["scope_classification"] == "OUT_OF_SCOPE"],
        "changes": changes,
        "audit_role": "post-operation detection only; not a prevention mechanism",
    }


def _registration(path: Path, process_id: int) -> tuple[str, int]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    expected_session_id = f"unreal-{process_id}"
    if (
        path.stem != expected_session_id
        or data.get("session_id") != expected_session_id
        or data.get("kind") != "unreal"
        or data.get("host") != "127.0.0.1"
        or data.get("pid") != process_id
        or type(data.get("port")) is not int
        or not 1 <= data["port"] <= 65535
        or data.get("protocol_version") != 1
    ):
        raise RuntimeError("The private Editor registration does not match the launched process")
    return expected_session_id, data["port"]


def _stop_disposable_editor(process: subprocess.Popen, registration_path: Path) -> None:
    """Stop only the child Editor created by this runner, then remove its token file."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    if process.poll() is None:
        raise RuntimeError("The disposable Editor process did not exit")
    if registration_path.exists():
        expected_parent = registration_path.parent.resolve()
        if registration_path.resolve().parent != expected_parent:
            raise RuntimeError("Refusing to remove a registration outside the private directory")
        registration_path.unlink()


def _host_environment(
    *, root: Path, project_file: Path, executable: Path, process_id: int,
    session_id: str, port: int, start_utc: str, shared_root: Path,
) -> dict[str, str]:
    registry = root / "registry"
    state = root / "state"
    temporary = root / "temp"
    logs = root / "logs"
    host_env = dict(os.environ)
    host_env.update({
        "FORGE_HOST_MODE": "isolated",
        "FORGE_HOST_ID": f"landscape-smoke-{root.name[-12:]}",
        "FORGE_AUTH_CONTEXT_ID": f"landscape-smoke-auth-{root.name[-12:]}",
        "FORGE_ISOLATED_CREDENTIAL_SOURCE": "private_session_registration",
        "FORGE_PRIVATE_ROOT": str(root),
        "FORGE_SESSION_DIR": str(registry),
        "FORGE_UNREAL_SESSION_DIR": str(registry / "unreal"),
        "FORGE_BLENDER_SESSION_DIR": str(registry / "blender"),
        "FORGE_STATE_DIR": str(state),
        "FORGE_PROJECT_ROOT": str(state),
        "FORGE_TEMP_DIR": str(temporary),
        "FORGE_LOG_DIR": str(logs),
        "FORGE_SHARED_SESSION_DIR": str(shared_root),
        "FORGE_ISOLATED_ALLOWED_SESSION_IDS": session_id,
        "FORGE_ISOLATED_DENIED_SESSION_IDS": "unreal-7556,unreal-16436",
        "FORGE_ISOLATED_EXPECTED_PID": str(process_id),
        "FORGE_ISOLATED_EXPECTED_PORT": str(port),
        "FORGE_ISOLATED_EXPECTED_START_UTC": start_utc,
        "FORGE_ISOLATED_EXPECTED_EXECUTABLE": str(executable),
        "FORGE_ISOLATED_EXPECTED_PROJECT_FILE": str(project_file),
        "FORGE_ISOLATED_EXPECTED_LEVEL": "/Engine/Maps/Entry.Entry",
        "FORGE_ISOLATED_EXPECTED_ENGINE_VERSION": "5.6.1",
        "FORGE_ISOLATED_TOOL_PROFILE": "landscape_smoke",
        "TEMP": str(temporary),
        "TMP": str(temporary),
    })
    return host_env


async def _run(args: argparse.Namespace) -> dict:
    if os.name != "nt":
        raise RuntimeError("This isolated Unreal acceptance runner requires Windows")
    repository = Path(__file__).resolve().parents[1]
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
    private_root = local_app_data / "ForgeMCP" / "IsolatedLandscapeSmoke" / test_id
    _assert_disjoint(shared_root, private_root)
    private_root.mkdir(parents=True, exist_ok=False)
    acl_result = _protect_root(private_root)

    for relative in ("registry/unreal", "registry/blender", "temp", "logs", "state"):
        (private_root / relative).mkdir(parents=True, exist_ok=False)
    state = private_root / "state"
    project_file = state / "ForgeMCPDev.uproject"
    _make_project(project_file)
    manifest, archive_sha256 = _extract_release(archive, state / "Plugins" / "Forge")
    (private_root / "Saved").mkdir(exist_ok=True)

    editor_log = private_root / "logs" / "UnrealEditor.log"
    editor_env = dict(os.environ)
    editor_env.update({
        "FORGE_UNREAL_SESSION_DIR": str(private_root / "registry" / "unreal"),
        "FORGE_SESSION_DIR": str(private_root / "registry"),
        "TEMP": str(private_root / "temp"),
        "TMP": str(private_root / "temp"),
        "FORGE_LANDSCAPE_DISPOSABLE_PROJECT_ROOT": str(state.resolve()),
    })
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    with editor_log.open("x", encoding="utf-8") as log_stream:
        process = subprocess.Popen(
            [
                str(editor), str(project_file), "-Unattended", "-NullRHI", "-NoSplash",
                "-NoSound", "-NoLiveCoding", "-NoSourceControl",
                f"-abslog={editor_log}",
            ],
            cwd=state,
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
        time.sleep(0.25)
    if process.poll() is not None:
        raise RuntimeError(f"Disposable Editor exited during startup; inspect {editor_log}")
    if not registration_path.is_file():
        raise TimeoutError(f"Disposable Editor did not publish its private registration; inspect {editor_log}")
    unexpected = [
        path for path in (private_root / "registry" / "unreal").glob("*.json")
        if path != registration_path
    ]
    if unexpected:
        raise RuntimeError("Unexpected registration appeared in the private Unreal registry")
    session_id, port = _registration(registration_path, process.pid)
    snapshot = WindowsProcessIdentityProbe()(process.pid, port)
    expected = {
        "pid": process.pid,
        "executable_path": str(editor),
        "creation_utc": snapshot.creation_utc,
    }
    env = _host_environment(
        root=private_root,
        project_file=project_file,
        executable=editor,
        process_id=process.pid,
        session_id=session_id,
        port=port,
        start_utc=snapshot.creation_utc,
        shared_root=shared_root,
    )
    config = IsolatedHostConfig.from_env(env)
    validate_process_snapshot(snapshot, config)
    direct_manager = ConnectionManager(
        [config.unreal_registry_root, config.blender_registry_root],
        isolated_config=config,
        log_root=config.log_root,
        process_identity_probe=WindowsProcessIdentityProbe(),
    )
    private_sessions = direct_manager.discover()
    if len(private_sessions) != 1 or private_sessions[0].session_id != session_id:
        raise RuntimeError("Private registry did not discover exactly the launched test Editor")
    health = await direct_manager.request(
        private_sessions[0], "health", session_id=session_id
    )
    if health.get("adapter") != "ForgeMCP Unreal":
        raise RuntimeError("The authenticated private Editor health identity is unexpected")
    if health.get("version") != manifest.get("plugin_version"):
        raise RuntimeError("The disposable Editor plugin version does not match the package manifest")
    registration_acl = subprocess.run(
        ["icacls", str(registration_path.parent)], check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout
    registration_acl_folded = registration_acl.casefold()
    if any(value in registration_acl_folded for value in (
        "everyone", "authenticated users", "builtin\\users"
    )):
        raise RuntimeError("The Editor registration directory has a broad access rule")

    # Exercise the native plugin's destination check directly. The MCP-level
    # negative test below is useful, but schema rejection alone does not prove
    # that the Editor-side boundary rejects an out-of-scope path. This request
    # is preview-only and must fail before any map transition or project write.
    native_negative_before = _snapshot_project_files(project_file.parent)
    try:
        await direct_manager.request(
            private_sessions[0],
            "landscape_preview",
            {"request": {
                "action": "create",
                "map_path": "/Game/ForgeMCPTests/Outside/L_A7K38_Rejected",
                "world_partition": True,
            }},
            session_id=session_id,
        )
    except BridgeError as error:
        native_negative_error = error.code
    else:
        raise RuntimeError("Native Landscape preview accepted an out-of-scope target path")
    native_negative_after = _snapshot_project_files(project_file.parent)
    if native_negative_error != "invalid_destination":
        raise RuntimeError(
            "Native Landscape boundary rejected the negative request for an unexpected reason: "
            + native_negative_error
        )
    if native_negative_before != native_negative_after:
        raise RuntimeError("Rejected native Landscape preview changed disposable project files")

    existing_destination_name = f"L_A7K38_Existing_{test_id[:8]}"
    existing_destination = (
        project_file.parent / "Content" / "ForgeMCPTests" / "Landscape"
        / f"{existing_destination_name}.umap"
    )
    existing_destination.parent.mkdir(parents=True, exist_ok=True)
    existing_fixture_bytes = b"FORGEMCP_A7K38_EXISTING_DESTINATION_FIXTURE\\n"
    with existing_destination.open("xb") as fixture:
        fixture.write(existing_fixture_bytes)
    existing_before = _snapshot_project_files(project_file.parent)
    try:
        await direct_manager.request(
            private_sessions[0],
            "landscape_preview",
            {"request": {
                "action": "create",
                "map_path": f"/Game/ForgeMCPTests/Landscape/{existing_destination_name}",
                "world_partition": True,
            }},
            session_id=session_id,
        )
    except BridgeError as error:
        existing_destination_error = error.code
    else:
        raise RuntimeError("Native Landscape preview accepted an existing target package")
    existing_after = _snapshot_project_files(project_file.parent)
    if existing_destination_error not in {"invalid_destination", "write_scope_rejected"}:
        raise RuntimeError(
            "Native existing-destination guard rejected for an unexpected reason: "
            + existing_destination_error
        )
    if existing_before != existing_after:
        raise RuntimeError("Rejected existing-destination preview changed disposable project files")
    existing_destination.unlink()

    def preview_request(map_package: str) -> dict:
        return {
            "request": {
                "action": "create",
                "map_path": map_package,
                "components_x": 2,
                "components_y": 2,
                "quads_per_section": 63,
                "sections_per_component": 1,
                "world_partition": True,
                "partition_grid_size_components": 2,
                "xy_scale_cm": 100,
                "z_scale": 100,
            }
        }

    # The local engine default layer is HLODLayer_Instanced. This fixture
    # targets the exact deterministic package suffix documented by the UE
    # 5.6.1 DuplicateHLODLayersSetup implementation.
    hlod_conflict_name = f"L_A7K38_HLODConflict_{test_id[:8]}"
    hlod_fixture = (project_file.parent / "Content" / "ForgeMCPTests" / "Landscape"
                    / f"{hlod_conflict_name}_HLODLayer_Instanced.uasset")
    with hlod_fixture.open("xb") as stream:
        stream.write(b"FORGEMCP_A7K38_HLOD_DESTINATION_FIXTURE\\n")
    hlod_before = _snapshot_project_files(project_file.parent)
    try:
        await direct_manager.request(
            private_sessions[0], "landscape_preview",
            preview_request(f"/Game/ForgeMCPTests/Landscape/{hlod_conflict_name}"),
            session_id=session_id,
        )
    except BridgeError as error:
        hlod_conflict_error = error.code
    else:
        raise RuntimeError("Native Landscape preview accepted an existing HLOD package destination")
    hlod_after = _snapshot_project_files(project_file.parent)
    if hlod_conflict_error != "write_scope_rejected" or hlod_before != hlod_after:
        raise RuntimeError("Existing HLOD package was not rejected before any file mutation")
    hlod_fixture.unlink()

    worldstate_conflict_name = f"L_A7K38_WorldStateConflict_{test_id[:8]}"
    worldstate_package = f"/Game/ForgeMCPTests/Landscape/{worldstate_conflict_name}"
    worldstate_crc = zlib.crc32(worldstate_package.encode("utf-16le")) & 0xFFFFFFFF
    worldstate_fixture = (project_file.parent / "Saved" / "Config" / "WorldState"
                          / f"{worldstate_crc}.json")
    worldstate_fixture.parent.mkdir(parents=True, exist_ok=True)
    with worldstate_fixture.open("xb") as stream:
        stream.write(b"FORGEMCP_A7K38_WORLDSTATE_DESTINATION_FIXTURE\\n")
    worldstate_before = _snapshot_project_files(project_file.parent)
    try:
        await direct_manager.request(
            private_sessions[0], "landscape_preview",
            preview_request(worldstate_package), session_id=session_id,
        )
    except BridgeError as error:
        worldstate_conflict_error = error.code
    else:
        raise RuntimeError("Native Landscape preview accepted an existing target WorldState destination")
    worldstate_after = _snapshot_project_files(project_file.parent)
    if worldstate_conflict_error != "write_scope_rejected" or worldstate_before != worldstate_after:
        raise RuntimeError("Existing target WorldState file was not rejected before any file mutation")
    worldstate_fixture.unlink()

    map_name = args.map_name or f"L_A7K38_WP_{test_id[:8]}"
    if not re.fullmatch(r"L_A7K38_WP_[A-Fa-f0-9]{8}", map_name):
        raise ValueError("The test map name must use the unique L_A7K38_WP_<8 hex> form")
    test_env = _host_environment(
        root=private_root,
        project_file=project_file,
        executable=editor,
        process_id=process.pid,
        session_id=session_id,
        port=port,
        start_utc=snapshot.creation_utc,
        shared_root=shared_root,
    )
    (private_root / "logs" / "acceptance.log").touch(exist_ok=False)
    project_files_before_acceptance = _snapshot_project_files(project_file.parent)
    result = subprocess.run(
        [
            sys.executable,
            str(repository / "scripts" / "verify_landscape_mcp.py"),
            "--session-id", session_id,
            "--project-file", str(project_file),
            "--map-name", map_name,
            "--world-partition",
        ],
        cwd=repository,
        env=test_env,
        capture_output=True,
        text=True,
        timeout=args.test_timeout,
    )
    acceptance = project_file.parent / "Saved" / "LandscapeDevelopment" / f"phase6-{map_name}.json"
    if acceptance.is_file():
        (private_root / "logs" / "acceptance.json").write_bytes(acceptance.read_bytes())
    (private_root / "logs" / "acceptance.log").write_text(
        result.stdout + "\n" + result.stderr, encoding="utf-8"
    )
    if result.returncode != 0 or not acceptance.is_file():
        raise RuntimeError(
            f"Landscape acceptance failed with exit code {result.returncode}; "
            f"inspect {private_root / 'logs' / 'acceptance.log'}"
        )
    acceptance_data = json.loads(acceptance.read_text(encoding="utf-8"))
    project_files_after_acceptance = _snapshot_project_files(project_file.parent)
    write_audit = _audit_write_set(
        project_files_before_acceptance, project_files_after_acceptance, map_name,
        acceptance_data.get("create_preview", {}).get("write_scope", {}), project_file.parent,
    )
    acceptance_data["actual_write_set_audit"] = write_audit
    acceptance.write_text(json.dumps(acceptance_data, indent=2) + "\n", encoding="utf-8")
    if write_audit["out_of_scope_paths"]:
        raise RuntimeError(
            "Disposable acceptance produced paths outside the approved write policy: "
            + ", ".join(write_audit["out_of_scope_paths"])
        )
    acceptance_passed = acceptance_data.get("state") == "passed"

    # This runner is invoked as a file from the repository root, where the
    # scripts directory is already on sys.path.  It uses only the passive
    # Win32 module-path helper; the generic verifier's CLI workflow is not run.
    from verify_unreal_package import loaded_module_path

    module_path = await asyncio.to_thread(
        loaded_module_path, process.pid, "UnrealEditor-MajesticForge.dll"
    )
    expected_module = project_file.parent / "Plugins" / "Forge" / "Binaries" / "Win64" / "UnrealEditor-MajesticForge.dll"
    if module_path != expected_module.resolve():
        raise RuntimeError("The disposable Editor loaded a plugin binary outside its project root")
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    package_module_hash = manifest["files"]["Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll"]
    if module_hash != package_module_hash:
        raise RuntimeError("The loaded plugin path does not contain the package-manifest binary")

    _stop_disposable_editor(process, registration_path)

    report = {
        "result": "PASS" if acceptance_passed else "BLOCKED",
        "test_scope": "fresh disposable World Partition Landscape acceptance",
        "unreal_version": "5.6.1",
        "archive": str(archive),
        "archive_sha256": archive_sha256,
        "plugin_version": manifest["plugin_version"],
        "process": expected,
        "session_id": session_id,
        "port": port,
        "private_root": str(private_root),
        "private_root_acl": acl_result,
        "registration_acl_protected": True,
        "project_file": str(project_file),
        "map_name": map_name,
        "authenticated_health_preflight": {
            "adapter": health.get("adapter"),
            "version": health.get("version"),
            "landscape_capabilities": sorted(
                capability for capability in health.get("capabilities", [])
                if capability.startswith("landscape_") or capability == "inspect_dirty_packages"
            ),
        },
        "native_out_of_scope_preview_test": {
            "request": "create preview outside approved Landscape test namespace",
            "native_error_code": native_negative_error,
            "rejected_by_editor_plugin": True,
            "project_file_set_unchanged": True,
            "apply_invoked": False,
        },
        "native_existing_destination_preview_test": {
            "fixture_path": str(existing_destination),
            "fixture_sha256": hashlib.sha256(existing_fixture_bytes).hexdigest(),
            "native_error_code": existing_destination_error,
            "rejected_by_editor_plugin": True,
            "project_file_set_unchanged_while_fixture_present": True,
            "fixture_removed_after_test": not existing_destination.exists(),
            "apply_invoked": False,
        },
        "native_existing_hlod_destination_preview_test": {
            "fixture_path": str(hlod_fixture),
            "native_error_code": hlod_conflict_error,
            "project_file_set_unchanged_while_fixture_present": True,
            "fixture_removed_after_test": not hlod_fixture.exists(),
            "apply_invoked": False,
        },
        "native_existing_worldstate_destination_preview_test": {
            "fixture_path": str(worldstate_fixture),
            "native_error_code": worldstate_conflict_error,
            "project_file_set_unchanged_while_fixture_present": True,
            "fixture_removed_after_test": not worldstate_fixture.exists(),
            "apply_invoked": False,
        },
        "loaded_module_path": str(module_path),
        "loaded_module_sha256": module_hash,
        "landscape_acceptance_report": str(acceptance),
        "landscape_acceptance_state": acceptance_data["state"],
        "actual_write_set_audit": write_audit,
        "landscape_acceptance_blocking_reason": acceptance_data.get("blocking_reason"),
        "disposable_editor_exit_confirmed": process.poll() is not None,
        "limitations": [
            "The run used -NullRHI and does not prove interactive viewport appearance.",
            "The bounded two-by-two test does not close city-scale, performance, or full coastline-collision gates.",
            "Any post-operation write audit detects out-of-scope effects but cannot prevent Unreal engine writes.",
        ],
    }
    result_path = private_root / "logs" / "release-acceptance.json"
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return report


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--editor", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--map-name")
    parser.add_argument("--startup-timeout", type=int, default=240)
    parser.add_argument("--test-timeout", type=int, default=900)
    args = parser.parse_args()
    report = await _run(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
