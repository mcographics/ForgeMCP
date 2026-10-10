"""Probe authentication, framing, and rejected commands against live adapters."""

import argparse
import asyncio
import json

from server.core.connections import ConnectionManager


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=["unreal", "blender"])
    options = parser.parse_args()
    manager = ConnectionManager.configured()
    sessions = manager.discover()
    if options.kind:
        sessions = [s for s in sessions if s.kind == options.kind]
    assert {s.kind for s in sessions} == (
        {options.kind} if options.kind else {"unreal", "blender"}
    ), "Required adapters are not registered; no partial verification is accepted."
    assert sessions, "No adapters discovered; rejection tests were not exercised."
    for session in sessions:
        for mode, expected in [
            ("bad_token", "unauthorized"),
            ("mutation", "command_not_allowed"),
            ("bad_protocol", "invalid_request"),
            ("bad_args", "invalid_arguments"),
            ("deep_json", "invalid_request"),
        ]:
            reader, writer = await asyncio.open_connection("127.0.0.1", session.port)
            request = {
                "protocol_version": 2 if mode == "bad_protocol" else 1,
                "request_id": "safety-probe",
                "command": "execute_python" if mode == "mutation" else "health",
                "args": [] if mode == "bad_args" else {},
                "token": "wrong" if mode == "bad_token" else session.token,
            }
            try:
                data = json.dumps(request).encode() + b"\n"
                if mode == "deep_json":
                    data = b"[" * 100 + b"0" + b"]" * 100 + b"\n"
                # Split framing deliberately: both bridges must handle partial TCP reads.
                writer.write(data[:12])
                await writer.drain()
                await asyncio.sleep(0.05)
                writer.write(data[12:])
                await writer.drain()
                response = json.loads(await asyncio.wait_for(reader.readline(), 15))
                assert response["ok"] is False
                assert response["error"]["code"] == expected
                print(f"{session.kind}: {mode} correctly rejected")
            finally:
                writer.close()
                await writer.wait_closed()
        reader, writer = await asyncio.open_connection("127.0.0.1", session.port)
        try:
            writer.write(b"x" * 16385)
            await writer.drain()
            assert await asyncio.wait_for(reader.read(1), 15) == b""
            print(f"{session.kind}: oversized request connection closed")
        finally:
            writer.close()
            await writer.wait_closed()
        health = await manager.request(session, "health")
        assert health["version"] in {"0.1.2", "0.2.0"}, health
        print(f"{session.kind}: {health['version']} remains responsive after rejected requests")


asyncio.run(main())
