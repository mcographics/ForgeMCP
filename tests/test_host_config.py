import asyncio
import json
import os
import subprocess

import pytest
from mcp.server.fastmcp import FastMCP

from server.core.connection_monitor import connection_monitor_lifespan
from server.core.connections import BridgeError, ConnectionManager, Session
from server.core.host_config import HostConfigurationError, IsolatedHostConfig
from server.core.process_identity import (
    IDENTITY_PROBE_TIMEOUT_SECONDS,
    ProcessIdentityError,
    ProcessSnapshot,
    WindowsProcessIdentityProbe,
    validate_process_snapshot,
)
from server.isolated_host import main as isolated_host_main
from server.main import (
    ISOLATED_LANDSCAPE_TOOL_ALLOWLIST,
    ISOLATED_TOOL_ALLOWLIST,
    restrict_isolated_tool_catalog,
)


def isolated_env(tmp_path, **overrides):
    private = tmp_path / "dedicated-host"
    env = {
        "FORGE_HOST_MODE": "isolated",
        "FORGE_HOST_ID": "phase6c-a7j",
        "FORGE_AUTH_CONTEXT_ID": "phase6c-isolated-auth",
        "FORGE_ISOLATED_CREDENTIAL_SOURCE": "private_session_registration",
        "FORGE_PRIVATE_ROOT": str(private),
        "FORGE_SESSION_DIR": str(private / "registry"),
        "FORGE_UNREAL_SESSION_DIR": str(private / "registry" / "unreal"),
        "FORGE_BLENDER_SESSION_DIR": str(private / "registry" / "blender"),
        "FORGE_STATE_DIR": str(private / "state"),
        "FORGE_PROJECT_ROOT": str(private / "state"),
        "FORGE_TEMP_DIR": str(private / "temp"),
        "FORGE_LOG_DIR": str(private / "logs"),
        "TEMP": str(private / "temp"),
        "TMP": str(private / "temp"),
        "LOCALAPPDATA": str(tmp_path / "user" / "AppData" / "Local"),
        "FORGE_SHARED_SESSION_DIR": str(tmp_path / "user" / "AppData" / "Local" / "MajesticForge" / "sessions"),
        "FORGE_ISOLATED_ALLOWED_SESSION_IDS": "unreal-16436",
        "FORGE_ISOLATED_DENIED_SESSION_IDS": "unreal-7556",
        "FORGE_ISOLATED_EXPECTED_PID": "16436",
        "FORGE_ISOLATED_EXPECTED_PORT": "64763",
        "FORGE_ISOLATED_EXPECTED_START_UTC": "2026-10-19T07:17:30.8972790Z",
        "FORGE_ISOLATED_EXPECTED_EXECUTABLE": str(tmp_path / "UE_5.6" / "UnrealEditor.exe"),
        "FORGE_ISOLATED_EXPECTED_PROJECT_FILE": str(tmp_path / "isolated-project" / "ForgeMCPDev.uproject"),
        "FORGE_ISOLATED_EXPECTED_LEVEL": "/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017.Phase6C_EmptyOpenWorld_20261017",
        "FORGE_ISOLATED_EXPECTED_ENGINE_VERSION": "5.6.1",
    }
    env.update(overrides)
    return env


def create_manager(env):
    config = IsolatedHostConfig.from_env(env)
    config.prepare_private_directories()

    def identity_probe(pid, _port):
        command_line = subprocess.list2cmdline(
            [str(config.expected_executable_path), str(config.expected_project_file)]
        )
        return ProcessSnapshot(
            pid=pid,
            executable_path=str(config.expected_executable_path),
            command_line=command_line,
            creation_utc=config.expected_process_start_utc,
            listener_pids=(pid,),
            listener_addresses=("127.0.0.1",),
        )

    return ConnectionManager(
        [config.unreal_registry_root, config.blender_registry_root],
        isolated_config=config,
        log_root=config.log_root,
        process_identity_probe=identity_probe,
    )


def expected_process_snapshot(config, **changes):
    snapshot = {
        "pid": config.expected_pid,
        "executable_path": str(config.expected_executable_path),
        "command_line": subprocess.list2cmdline(
            [str(config.expected_executable_path), str(config.expected_project_file)]
        ),
        "creation_utc": config.expected_process_start_utc,
        "listener_pids": (config.expected_pid,),
        "listener_addresses": ("127.0.0.1",),
    }
    snapshot.update(changes)
    return ProcessSnapshot(**snapshot)


def write_registration(root, *, session_id="unreal-16436", kind="unreal", pid=16436,
                       port=64763, token="isolated-token-" + "x" * 48):
    root.mkdir(parents=True, exist_ok=True)
    registration = {
        "protocol_version": 1,
        "session_id": session_id,
        "kind": kind,
        "host": "127.0.0.1",
        "port": port,
        "pid": pid,
        "token": token,
    }
    (root / f"{session_id}.json").write_text(json.dumps(registration), encoding="utf-8")
    return registration


def test_isolated_config_requires_explicit_private_roots_and_auth_context(tmp_path):
    env = isolated_env(tmp_path)
    env.pop("FORGE_UNREAL_SESSION_DIR")
    with pytest.raises(HostConfigurationError, match="FORGE_UNREAL_SESSION_DIR"):
        IsolatedHostConfig.from_env(env)

    env = isolated_env(tmp_path)
    env.pop("FORGE_SHARED_SESSION_DIR")
    with pytest.raises(HostConfigurationError, match="FORGE_SHARED_SESSION_DIR"):
        IsolatedHostConfig.from_env(env)

    env = isolated_env(tmp_path, FORGE_ISOLATED_CREDENTIAL_SOURCE="")
    with pytest.raises(HostConfigurationError, match="FORGE_ISOLATED_CREDENTIAL_SOURCE"):
        IsolatedHostConfig.from_env(env)


def test_private_directory_preparation_creates_no_registry_or_credentials(tmp_path):
    config = IsolatedHostConfig.from_env(isolated_env(tmp_path))
    config.prepare_private_directories()

    assert config.unreal_registry_root.is_dir()
    assert config.blender_registry_root.is_dir()
    assert config.state_root.is_dir()
    assert config.temp_root.is_dir()
    assert config.log_root.is_dir()
    assert list(config.unreal_registry_root.iterdir()) == []
    assert list(config.blender_registry_root.iterdir()) == []


def test_isolated_config_rejects_shared_storage_overlap(tmp_path):
    shared = tmp_path / "user" / "AppData" / "Local" / "MajesticForge" / "sessions"
    env = isolated_env(tmp_path, FORGE_PRIVATE_ROOT=str(shared.parent.parent))
    private = shared.parent.parent
    env.update({
        "FORGE_SESSION_DIR": str(private / "registry"),
        "FORGE_UNREAL_SESSION_DIR": str(private / "registry" / "unreal"),
        "FORGE_BLENDER_SESSION_DIR": str(private / "registry" / "blender"),
        "FORGE_STATE_DIR": str(private / "state"),
        "FORGE_PROJECT_ROOT": str(private / "state"),
        "FORGE_TEMP_DIR": str(private / "temp"),
        "FORGE_LOG_DIR": str(private / "logs"),
        "TEMP": str(private / "temp"),
        "TMP": str(private / "temp"),
        "LOCALAPPDATA": str(tmp_path / "user" / "AppData" / "Local"),
        "FORGE_SHARED_SESSION_DIR": str(shared),
    })
    with pytest.raises(HostConfigurationError, match="overlap shared session storage"):
        IsolatedHostConfig.from_env(env)


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"FORGE_UNREAL_SESSION_DIR": "C:/shared/sessions"}, "children of FORGE_PRIVATE_ROOT"),
        ({"TMP": "C:/shared/temp"}, "TMP must point"),
        ({"FORGE_ISOLATED_ALLOWED_SESSION_IDS": "unreal-16436,unreal-7556"}, "Exactly one"),
        ({"FORGE_ISOLATED_DENIED_SESSION_IDS": "unreal-16436"}, "both allowed and denied"),
        ({"FORGE_ISOLATED_EXPECTED_PORT": "70000"}, "outside valid bounds"),
        ({"FORGE_ISOLATED_EXPECTED_START_UTC": "yesterday"}, "UTC timestamp"),
    ],
)
def test_isolated_config_rejects_unsafe_or_conflicting_values(tmp_path, changes, message):
    with pytest.raises(HostConfigurationError, match=message):
        IsolatedHostConfig.from_env(isolated_env(tmp_path, **changes))


def test_isolated_config_accepts_only_the_approved_engine_entry_source(tmp_path):
    config = IsolatedHostConfig.from_env(
        isolated_env(tmp_path, FORGE_ISOLATED_EXPECTED_LEVEL="/Engine/Maps/Entry.Entry")
    )
    assert config.expected_level == "/Engine/Maps/Entry.Entry"

    with pytest.raises(HostConfigurationError, match="approved /Engine/Maps/Entry"):
        IsolatedHostConfig.from_env(
            isolated_env(tmp_path, FORGE_ISOLATED_EXPECTED_LEVEL="/Engine/Maps/Other.Other")
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows command-line parsing uses CommandLineToArgvW")
def test_isolated_process_snapshot_requires_exact_executable_start_project_and_listener(tmp_path):
    config = IsolatedHostConfig.from_env(isolated_env(tmp_path))
    validate_process_snapshot(expected_process_snapshot(config), config)

    invalid_snapshots = [
        (expected_process_snapshot(config, pid=config.expected_pid + 1), "pid_mismatch"),
        (expected_process_snapshot(config, executable_path=str(tmp_path / "other.exe")), "executable_mismatch"),
        (expected_process_snapshot(config, creation_utc="2026-10-19T07:17:30.0000000Z"), "process_start_mismatch"),
        (expected_process_snapshot(config, listener_pids=(config.expected_pid + 1,)), "listener_owner_mismatch"),
        (expected_process_snapshot(config, listener_addresses=("0.0.0.0",)), "listener_not_loopback"),
        (
            expected_process_snapshot(
                config,
                command_line=subprocess.list2cmdline([
                    str(config.expected_executable_path), str(tmp_path / "Production.uproject")
                ]),
            ),
            "project_argument_mismatch",
        ),
        (
            expected_process_snapshot(
                config,
                command_line=subprocess.list2cmdline([
                    str(config.expected_executable_path),
                    str(config.expected_project_file),
                    str(tmp_path / "Production.uproject"),
                ]),
            ),
            "project_argument_mismatch",
        ),
    ]
    for snapshot, category in invalid_snapshots:
        with pytest.raises(ProcessIdentityError) as error:
            validate_process_snapshot(snapshot, config)
        assert error.value.category == category


@pytest.mark.skipif(os.name != "nt", reason="The production probe invokes Windows PowerShell")
def test_windows_identity_probe_timeout_is_bounded_and_classified(monkeypatch):
    calls = []

    def timeout_run(*args, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout_run)
    with pytest.raises(ProcessIdentityError) as error:
        WindowsProcessIdentityProbe()(15144, 60688)

    assert error.value.category == "powershell_timeout"
    assert calls[0]["timeout"] == IDENTITY_PROBE_TIMEOUT_SECONDS == 30


@pytest.mark.skipif(os.name != "nt", reason="The production probe invokes Windows PowerShell")
def test_windows_identity_probe_classifies_powershell_and_metadata_failures(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "safe failure"),
    )
    with pytest.raises(ProcessIdentityError) as powershell_error:
        WindowsProcessIdentityProbe()(15144, 60688)
    assert powershell_error.value.category == "powershell_execution_failed"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "{not-json", ""),
    )
    with pytest.raises(ProcessIdentityError) as parse_error:
        WindowsProcessIdentityProbe()(15144, 60688)
    assert parse_error.value.category == "metadata_parse_failed"


def test_configured_isolated_host_uses_private_roots_without_shared_fallback(monkeypatch, tmp_path):
    env = isolated_env(tmp_path)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    manager = ConnectionManager.configured()

    assert manager.isolated_config.allowed_session_id == "unreal-16436"
    assert manager.isolated_config.denied_session_ids == {"unreal-7556"}
    assert manager.roots == [
        tmp_path / "dedicated-host" / "registry" / "unreal",
        tmp_path / "dedicated-host" / "registry" / "blender",
    ]
    assert all("MajesticForge" not in str(root) for root in manager.roots)


def test_isolated_discovery_ignores_shared_registry_contents(tmp_path):
    env = isolated_env(tmp_path)
    manager = create_manager(env)
    write_registration(manager.isolated_config.unreal_registry_root)
    shared_root = manager.isolated_config.private_root.parent / "user" / "AppData" / "Local" / "MajesticForge" / "sessions"
    write_registration(shared_root, session_id="unreal-7556", pid=7556, port=64846)

    sessions = manager.discover()

    assert [session.session_id for session in sessions] == ["unreal-16436"]
    assert all(session.port != 64846 for session in sessions)


def test_production_log_root_preserves_unreal_registry_override(monkeypatch, tmp_path):
    unreal_root = tmp_path / "user-registry" / "unreal"
    monkeypatch.delenv("FORGE_HOST_MODE", raising=False)
    monkeypatch.delenv("FORGE_SESSION_DIR", raising=False)
    monkeypatch.delenv("FORGE_BLENDER_SESSION_DIR", raising=False)
    monkeypatch.setenv("FORGE_UNREAL_SESSION_DIR", str(unreal_root))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))

    manager = ConnectionManager.configured()

    assert manager.log_root == unreal_root.parent / "MajesticForgeLogs"


def test_dedicated_entrypoint_refuses_to_fall_back_to_production(monkeypatch):
    monkeypatch.delenv("FORGE_HOST_MODE", raising=False)
    with pytest.raises(SystemExit, match="no production fallback"):
        isolated_host_main()


@pytest.mark.parametrize(
    "change",
    [
        {"project_file": "C:/Production/ForgeMCPDev.uproject"},
        {"level": "/Game/Levels/L_City_World_Master.L_City_World_Master"},
        {"engine_version": "5.5.4-123456"},
        {"play_in_editor": True},
    ],
)
def test_isolated_editor_project_identity_is_pinned(tmp_path, change):
    config = IsolatedHostConfig.from_env(isolated_env(tmp_path))
    info = {
        "project_file": str(config.expected_project_file),
        "level": config.expected_level,
        "engine_version": "5.6.1-43139311",
        "play_in_editor": False,
    }
    info.update(change)

    with pytest.raises(ValueError, match="does not match"):
        config.validate_project_info(info)


@pytest.mark.parametrize(
    "session_id, expected_code",
    [
        (None, "session_id_required"),
        ("", "session_id_required"),
        ("unreal-7556", "production_session_denied"),
        ("unreal-99999", "session_not_allowed"),
        ("unreal-16436/../7556", "invalid_session_id"),
    ],
)
async def test_isolated_router_rejects_before_any_socket(monkeypatch, tmp_path, session_id, expected_code):
    manager = create_manager(isolated_env(tmp_path))
    calls = []

    async def unexpected_socket(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("unauthorized route attempted a socket")

    monkeypatch.setattr(asyncio, "open_connection", unexpected_socket)
    result = await manager.dispatch("unreal", "project_info", session_id)

    assert not result["ok"]
    assert result["error"]["code"] == expected_code
    assert calls == []


async def test_dirty_inventory_session_mismatch_fails_before_socket_or_fallback(monkeypatch, tmp_path):
    manager = create_manager(isolated_env(tmp_path))
    calls = []

    async def unexpected_socket(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("a mismatched dirty-inventory session must not reach any bridge")

    monkeypatch.setattr(asyncio, "open_connection", unexpected_socket)
    result = await manager.dispatch(
        "unreal", "inspect_dirty_packages", "unreal-99999",
        {"offset": 1, "limit": 1, "snapshot_id": "d" * 32},
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "session_not_allowed"
    assert calls == []


async def test_isolated_identity_mismatch_stops_before_bridge_socket(monkeypatch, tmp_path):
    manager = create_manager(isolated_env(tmp_path))
    config = manager.isolated_config
    registration = write_registration(config.unreal_registry_root)
    manager.process_identity_probe = lambda _pid, _port: ProcessSnapshot(
        pid=registration["pid"],
        executable_path=str(tmp_path / "Production" / "UnrealEditor.exe"),
        command_line=subprocess.list2cmdline([
            str(config.expected_executable_path), str(config.expected_project_file)
        ]),
        creation_utc=config.expected_process_start_utc,
        listener_pids=(registration["pid"],),
        listener_addresses=("127.0.0.1",),
    )
    calls = []

    async def unexpected_socket(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("identity mismatch must stop before a bridge socket")

    monkeypatch.setattr(asyncio, "open_connection", unexpected_socket)
    result = await manager.dispatch("unreal", "health", "unreal-16436")

    assert result["error"]["code"] == "identity_preflight_failed"
    assert calls == []


def test_isolated_registry_rejects_unexpected_and_wrong_identity_entries(tmp_path):
    manager = create_manager(isolated_env(tmp_path))
    config = manager.isolated_config
    write_registration(config.unreal_registry_root, session_id="unreal-99999", pid=16436)
    with pytest.raises(BridgeError) as unexpected:
        manager.discover()
    assert unexpected.value.code == "invalid_registry_entry"

    for path in config.unreal_registry_root.glob("*.json"):
        path.unlink()
    write_registration(config.unreal_registry_root, pid=16437)
    with pytest.raises(BridgeError) as wrong_pid:
        manager.discover()
    assert wrong_pid.value.code == "invalid_registry_entry"


def test_isolated_registration_conflict_fails_closed(tmp_path):
    manager = create_manager(isolated_env(tmp_path))
    config = manager.isolated_config
    write_registration(config.unreal_registry_root)
    # A second registration under the separate Blender root is unexpected and
    # must stop discovery instead of being ignored or selected as a fallback.
    write_registration(config.blender_registry_root, session_id="unreal-7556", kind="blender")

    with pytest.raises(BridgeError):
        manager.discover()


async def test_isolated_registry_authentication_failure_fails_closed_without_secret_leak(tmp_path, caplog):
    token = "do-not-log-this-isolated-test-token-1234567890"

    async def unauthorized(reader, writer):
        request = json.loads(await reader.readline())
        assert request["token"] == token
        writer.write(json.dumps({
            "ok": False,
            "request_id": request["request_id"],
            "error": {"code": "unauthorized", "message": "Rejected"},
        }).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(unauthorized, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        env = isolated_env(tmp_path, FORGE_ISOLATED_EXPECTED_PORT=str(port))
        manager = create_manager(env)
        write_registration(manager.isolated_config.unreal_registry_root, port=port, token=token)
        result = await manager.dispatch("unreal", "health", "unreal-16436")

    assert result["error"]["code"] == "unauthorized"
    assert token not in caplog.text
    assert token not in json.dumps(result)


async def test_isolated_request_requires_explicit_session_id_even_with_session_object(tmp_path):
    manager = create_manager(isolated_env(tmp_path))
    session = Session("unreal-16436", "unreal", 64763, "x" * 64, 16436)

    with pytest.raises(BridgeError) as error:
        await manager.request(session, "health")

    assert error.value.code == "session_id_required"


async def test_isolated_status_does_not_probe_without_explicit_session_id(tmp_path, monkeypatch):
    manager = create_manager(isolated_env(tmp_path))
    calls = []

    async def unexpected_socket(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("status without an explicit ID must not probe")

    monkeypatch.setattr(asyncio, "open_connection", unexpected_socket)
    status = await manager.inspect_sessions()
    assert status[0]["error"]["code"] == "session_id_required"
    assert calls == []


async def test_isolated_host_lifespan_refuses_to_serve_after_authentication_failure(monkeypatch, tmp_path):
    async def unauthorized(reader, writer):
        request = json.loads(await reader.readline())
        writer.write(json.dumps({
            "ok": False,
            "request_id": request["request_id"],
            "error": {"code": "unauthorized", "message": "Rejected"},
        }).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(unauthorized, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        manager = create_manager(isolated_env(tmp_path, FORGE_ISOLATED_EXPECTED_PORT=str(port)))
        write_registration(manager.isolated_config.unreal_registry_root, port=port)
        monkeypatch.setattr(ConnectionManager, "configured", classmethod(lambda cls: manager))
        with pytest.raises(RuntimeError, match="authentication failed"):
            async with connection_monitor_lifespan(None):
                pytest.fail("Isolated host must not enter serving state")


async def test_isolated_host_lifespan_rejects_wrong_project_or_map(monkeypatch, tmp_path):
    async def responder(reader, writer):
        request = json.loads(await reader.readline())
        if request["command"] == "health":
            data = {"adapter": "ForgeMCP Unreal", "engine_version": "5.6.1-43139311"}
        else:
            data = {
                "project_file": str(tmp_path / "Production.uproject"),
                "level": "/Game/Levels/L_City_World_Master.L_City_World_Master",
                "engine_version": "5.6.1-43139311",
                "play_in_editor": False,
            }
        writer.write(json.dumps({"ok": True, "request_id": request["request_id"], "data": data}).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(responder, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        manager = create_manager(isolated_env(tmp_path, FORGE_ISOLATED_EXPECTED_PORT=str(port)))
        write_registration(manager.isolated_config.unreal_registry_root, port=port)
        monkeypatch.setattr(ConnectionManager, "configured", classmethod(lambda cls: manager))
        with pytest.raises(RuntimeError, match="project identity preflight failed"):
            async with connection_monitor_lifespan(None):
                pytest.fail("A mismatched Editor must not enter serving state")


async def test_isolated_mcp_catalog_defaults_to_read_only_validation_tools():
    server = FastMCP("isolated-catalog-test")

    async def placeholder():
        return {"ok": True}

    for name in (*ISOLATED_TOOL_ALLOWLIST, "unreal_apply_landscape", "unreal_apply_actors"):
        server.add_tool(placeholder, name=name, description="offline test")

    await restrict_isolated_tool_catalog(server)
    names = {tool.name for tool in await server.list_tools()}

    assert names == ISOLATED_TOOL_ALLOWLIST
    assert "unreal_query_collision" in names
    assert "unreal_inspect_dirty_packages" in names
    assert "unreal_apply_landscape" not in names


@pytest.mark.asyncio
async def test_landscape_smoke_profile_adds_only_five_typed_landscape_tools():
    server = FastMCP("isolated-landscape-smoke-catalog-test")

    async def placeholder():
        return {"ok": True}

    for name in (
        *(ISOLATED_TOOL_ALLOWLIST | ISOLATED_LANDSCAPE_TOOL_ALLOWLIST),
        "unreal_apply_actors",
        "unreal_apply_blueprint",
    ):
        server.add_tool(placeholder, name=name, description="offline test")

    await restrict_isolated_tool_catalog(server, profile="landscape_smoke")
    names = {tool.name for tool in await server.list_tools()}

    assert names == ISOLATED_TOOL_ALLOWLIST | ISOLATED_LANDSCAPE_TOOL_ALLOWLIST
    assert "unreal_apply_actors" not in names
    assert "unreal_apply_blueprint" not in names


def test_isolated_tool_profile_is_validated(tmp_path):
    with pytest.raises(HostConfigurationError, match="FORGE_ISOLATED_TOOL_PROFILE"):
        IsolatedHostConfig.from_env(
            isolated_env(tmp_path, FORGE_ISOLATED_TOOL_PROFILE="all_tools")
        )
