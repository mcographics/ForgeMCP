import asyncio
import json
import os

import pytest

from server.core.connections import MAX_REQUEST, BridgeError, ConnectionManager


@pytest.mark.parametrize("value", [0, -1, float('inf'), float('nan'), 1801])
def test_apply_timeout_rejects_unbounded_values(tmp_path, value):
    with pytest.raises(ValueError):
        ConnectionManager([tmp_path], apply_timeout=value)


async def test_apply_timeout_is_separate_and_retains_uncertain_outcome(tmp_path):
    async def handle(reader, writer):
        try:
            await reader.readline()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        registration(tmp_path, port=listener.sockets[0].getsockname()[1])
        manager = ConnectionManager([tmp_path], timeout=2, apply_timeout=.05)
        result = await manager.dispatch('unreal', 'actor_apply', None, {})
        assert result['error']['code'] == 'outcome_unknown'
        assert manager.timeout == 2


def test_configured_sessions_default_to_shared_user_root(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setenv("FORGE_PROJECT_ROOT", str(tmp_path / "some-checkout"))
    monkeypatch.delenv("FORGE_SESSION_DIR", raising=False)
    monkeypatch.delenv("FORGE_UNREAL_SESSION_DIR", raising=False)
    monkeypatch.delenv("FORGE_BLENDER_SESSION_DIR", raising=False)

    manager = ConnectionManager.configured()

    assert manager.roots == [tmp_path / "user" / "MajesticForge" / "sessions"] * 2


def test_configured_sessions_support_shared_root_override(monkeypatch, tmp_path):
    root = tmp_path / "sessions"
    monkeypatch.setenv("FORGE_SESSION_DIR", str(root))
    monkeypatch.delenv("FORGE_UNREAL_SESSION_DIR", raising=False)
    monkeypatch.delenv("FORGE_BLENDER_SESSION_DIR", raising=False)

    assert ConnectionManager.configured().roots == [root, root]


def registration(root, port=12345, **changes):
    data = {
        "protocol_version": 1,
        "session_id": "test-unreal",
        "kind": "unreal",
        "host": "127.0.0.1",
        "port": port,
        "pid": 1,
        "token": "a" * 64,
    }
    data.update(changes)
    (root / f"{data['session_id']}.json").write_text(json.dumps(data))
    return data


@pytest.mark.parametrize(
    "changes",
    [
        {"host": "0.0.0.0"},
        {"host": "example.com"},
        {"port": True},
        {"port": 65536},
        {"token": "short"},
        {"protocol_version": 2},
        {"kind": "unknown"},
        {"protocol_version": True},
    ],
)
def test_untrusted_registration_is_rejected(tmp_path, changes):
    registration(tmp_path, **changes)
    assert ConnectionManager([tmp_path]).discover() == []


@pytest.mark.parametrize("payload", ["[]", "null", '"string"', "[" * 2000 + "]" * 2000])
def test_malformed_registration_cannot_crash_discovery(tmp_path, payload):
    (tmp_path / "malformed.json").write_text(payload)
    assert ConnectionManager([tmp_path]).discover() == []


def test_session_repr_redacts_secret(tmp_path):
    registration(tmp_path)
    assert "a" * 64 not in repr(ConnectionManager([tmp_path]).discover()[0])


def test_discovery_prioritizes_recent_sessions_when_registry_is_large(tmp_path):
    for index in range(70):
        session_id = f"aaa-stale-{index:03}"
        registration(tmp_path, session_id=session_id)
        old_timestamp = 1_700_000_000 + index
        os.utime(tmp_path / f"{session_id}.json", (old_timestamp, old_timestamp))
    registration(tmp_path, session_id="zzz-current")

    sessions = ConnectionManager([tmp_path]).discover()

    assert len(sessions) == 64
    assert "zzz-current" in {session.session_id for session in sessions}
    assert "aaa-stale-000" not in {session.session_id for session in sessions}


async def test_missing_and_ambiguous_sessions(tmp_path):
    manager = ConnectionManager([tmp_path])
    assert (await manager.dispatch("unreal", "project_info", None))["error"][
        "code"
    ] == "session_not_found"
    registration(tmp_path)
    registration(tmp_path, session_id="second")
    assert (await manager.dispatch("unreal", "project_info", None))["error"][
        "code"
    ] == "ambiguous_session"


async def test_tcp_authentication_correlation_and_redaction(tmp_path):
    async def handle(reader, writer):
        request = json.loads(await reader.readline())
        assert request["token"] == "a" * 64
        writer.write(
            json.dumps(
                {"ok": True, "request_id": request["request_id"], "data": {"read_only": True}}
            ).encode()
            + b"\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        registration(tmp_path, port=listener.sockets[0].getsockname()[1])
        manager = ConnectionManager([tmp_path])
        sessions = await manager.inspect_sessions()
        assert sessions[0]["connected"]
        assert "token" not in json.dumps(sessions)
        assert (await manager.dispatch("unreal", "project_info", None))["ok"]
        assert (await manager.dispatch(
            "unreal", "gas_info", "test-unreal", {"actor_path": "/Game/Test.Actor"}
        ))["ok"]
        assert (await manager.dispatch(
            "unreal", "struct_tooltips_preview", "test-unreal",
            {"struct_path": "/Game/TestStruct", "tooltips": {"name": "A name."}},
        ))["ok"]
        with pytest.raises(BridgeError, match="native allowlist"):
            await manager.request(manager.discover()[0], "execute_python")


async def test_maximum_landscape_heightmap_chunk_fits_python_bridge_transport(tmp_path):
    observed = {}

    async def handle(reader, writer):
        try:
            raw = await reader.readline()
            request = json.loads(raw)
            observed["bytes"] = len(raw)
            observed["sample_count"] = len(request["args"]["request"]["samples_cm"])
            response = {
                "ok": True,
                "request_id": request["request_id"],
                "data": {"accepted_samples": observed["sample_count"]},
            }
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async with await asyncio.start_server(
        handle, "127.0.0.1", 0, limit=MAX_REQUEST
    ) as listener:
        registration(tmp_path, port=listener.sockets[0].getsockname()[1])
        manager = ConnectionManager([tmp_path])
        result = await manager.dispatch(
            "unreal",
            "landscape_preview",
            "test-unreal",
            {"request": {"action": "apply_heightmap", "samples_cm": [100_000] * 32_768}},
        )

    assert result["ok"]
    assert result["data"]["accepted_samples"] == 32_768
    assert observed["sample_count"] == 32_768
    assert 16_384 < observed["bytes"] <= MAX_REQUEST


async def test_ensure_app_sessions_selects_one_authenticated_bridge_per_kind(tmp_path):
    async def serve(adapter):
        async def handle(reader, writer):
            request = json.loads(await reader.readline())
            response = {"ok": True, "request_id": request["request_id"],
                        "data": {"adapter": adapter}}
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        return await asyncio.start_server(handle, "127.0.0.1", 0)

    unreal = await serve("ForgeMCP Unreal")
    blender = await serve("ForgeMCP Blender")
    try:
        registration(tmp_path, session_id="unreal-11", kind="unreal",
                     port=unreal.sockets[0].getsockname()[1], pid=11)
        registration(tmp_path, session_id="blender-22", kind="blender",
                     port=blender.sockets[0].getsockname()[1], pid=22)
        result = await ConnectionManager([tmp_path]).ensure_app_sessions()
        assert result["connected"]
        assert result["unreal"]["session_id"] == "unreal-11"
        assert result["blender"]["session_id"] == "blender-22"
    finally:
        unreal.close()
        blender.close()
        await unreal.wait_closed()
        await blender.wait_closed()


async def test_ensure_app_sessions_reports_ambiguity_and_missing_bridge(tmp_path):
    async def handle(reader, writer):
        request = json.loads(await reader.readline())
        writer.write(json.dumps({"ok": True, "request_id": request["request_id"],
                                 "data": {"adapter": "ForgeMCP Blender"}}).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        port = listener.sockets[0].getsockname()[1]
        registration(tmp_path, session_id="blender-22", kind="blender", port=port, pid=22)
        registration(tmp_path, session_id="blender-23", kind="blender", port=port, pid=23)
        manager = ConnectionManager([tmp_path])
        result = await manager.ensure_app_sessions()
        assert not result["connected"]
        assert result["unreal"]["error"]["code"] == "session_not_found"
        assert result["blender"]["error"]["code"] == "ambiguous_session"
        selected = await manager.ensure_app_sessions(
            {"unreal": None, "blender": "blender-22"}
        )
        assert selected["blender"]["connected"]


@pytest.mark.parametrize(
    "mode,code",
    [
        ("wrong_id", "invalid_response"),
        ("bad_json", "invalid_response"),
        ("unauthorized", "unauthorized"),
        ("timeout", "timeout"),
    ],
)
async def test_bridge_failures(tmp_path, mode, code):
    async def handle(reader, writer):
        try:
            request = json.loads(await reader.readline())
            if mode == "timeout":
                await reader.read()
                return
            response = {"ok": True, "request_id": request["request_id"], "data": {}}
            if mode == "wrong_id":
                response["request_id"] = "wrong"
            if mode == "unauthorized":
                response.update(ok=False, error={"code": "unauthorized", "message": "Rejected"})
            writer.write(b"{bad\n" if mode == "bad_json" else json.dumps(response).encode() + b"\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        registration(tmp_path, port=listener.sockets[0].getsockname()[1])
        # Parsing/correlation cases need scheduling headroom on shared CI runners.
        # The dedicated timeout case still exercises the short deadline.
        manager = ConnectionManager([tmp_path], timeout=0.1 if mode == "timeout" else 2.0)
        result = await manager.dispatch("unreal", "project_info", None)
        assert result["error"]["code"] == code


async def test_bridge_native_error_detail_is_bounded_and_single_line(tmp_path):
    async def handle(reader, writer):
        request = json.loads(await reader.readline())
        response = {"ok": False, "request_id": request["request_id"],
            "error": {"code": "invalid_property_value", "message": "Bad value\r\ntry false\tthen retry"}}
        writer.write(json.dumps(response).encode() + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async with await asyncio.start_server(handle, "127.0.0.1", 0) as listener:
        registration(tmp_path, port=listener.sockets[0].getsockname()[1])
        result = await ConnectionManager([tmp_path]).dispatch("unreal", "project_info", None)
    assert result["error"] == {
        "code": "invalid_property_value", "message": "Bad value try false then retry"}
