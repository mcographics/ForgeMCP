import asyncio
import json

import pytest

from server.core.connections import BridgeError, ConnectionManager


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
        with pytest.raises(BridgeError, match="native allowlist"):
            await manager.request(manager.discover()[0], "execute_python")


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
        manager = ConnectionManager([tmp_path], timeout=0.1)
        result = await manager.dispatch("unreal", "project_info", None)
        assert result["error"]["code"] == code
