"""Windows IP Helper listener snapshot. Run in a bounded child process."""

from __future__ import annotations

import ctypes
import ipaddress
import json
import os
import socket
import struct
import sys
import time
from ctypes import wintypes

ERROR_INSUFFICIENT_BUFFER = 122
TCP_TABLE_OWNER_PID_LISTENER = 3
MIB_TCP_STATE_LISTEN = 2
MAX_TABLE_BYTES = 8 * 1024 * 1024
MAX_RETRIES = 3
_STARTED = time.monotonic()


def _diagnostic_marker(phase: str) -> None:
    destination = os.environ.get("FORGE_IDENTITY_CHILD_LOG") or os.environ.get(
        "FORGE_IDENTITY_DIAGNOSTIC_LOG")
    if not destination:
        return
    record = {"component": "listener", "phase": phase,
              "pid": os.getpid(),
              "correlation_id": os.environ.get("FORGE_IDENTITY_CORRELATION", ""),
              "elapsed_ms": round((time.monotonic() - _STARTED) * 1000, 3)}
    try:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    except OSError:
        if os.environ.get("FORGE_IDENTITY_CHILD_LOG"):
            print("identity_diagnostic_write_failed", file=sys.stderr)
            raise SystemExit(3) from None


_diagnostic_marker("process_entry")
_diagnostic_marker("module_import_complete")


class ListenerTableError(RuntimeError):
    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


class IPv4Row(ctypes.Structure):
    _fields_ = [(name, wintypes.DWORD) for name in (
        "state", "local_address", "local_port", "remote_address", "remote_port", "owner_pid"
    )]


class IPv6Row(ctypes.Structure):
    _fields_ = [
        ("local_address", ctypes.c_ubyte * 16),
        ("local_scope", wintypes.DWORD),
        ("local_port", wintypes.DWORD),
        ("remote_address", ctypes.c_ubyte * 16),
        ("remote_scope", wintypes.DWORD),
        ("remote_port", wintypes.DWORD),
        ("state", wintypes.DWORD),
        ("owner_pid", wintypes.DWORD),
    ]


def parse_table(raw: bytes, family: int, port: int) -> list[tuple[int, str]]:
    row_type = IPv4Row if family == socket.AF_INET else IPv6Row
    if family not in (socket.AF_INET, socket.AF_INET6) or len(raw) < 4:
        raise ListenerTableError("listener_table_malformed")
    count = struct.unpack_from("<I", raw)[0]
    row_size = ctypes.sizeof(row_type)
    if count > (len(raw) - 4) // row_size:
        raise ListenerTableError("listener_table_malformed")
    rows: list[tuple[int, str]] = []
    for index in range(count):
        row = row_type.from_buffer_copy(raw, 4 + index * row_size)
        if row.state != MIB_TCP_STATE_LISTEN:
            raise ListenerTableError("listener_state_invalid")
        if row.local_port & 0xFFFF0000:
            raise ListenerTableError("listener_port_malformed")
        decoded_port = socket.ntohs(row.local_port & 0xFFFF)
        if decoded_port != port:
            continue
        if row.owner_pid == 0:
            raise ListenerTableError("listener_owner_invalid")
        if family == socket.AF_INET:
            address = str(ipaddress.IPv4Address(struct.pack("<I", row.local_address)))
        else:
            address = str(ipaddress.IPv6Address(bytes(row.local_address)))
            if row.local_scope:
                address += f"%{row.local_scope}"
        rows.append((row.owner_pid, address))
    return rows


def query_table(family: int, api=None) -> bytes:
    if family not in (socket.AF_INET, socket.AF_INET6):
        raise ListenerTableError("listener_family_invalid")
    if api is None:
        api = ctypes.WinDLL("iphlpapi", use_last_error=True).GetExtendedTcpTable
        api.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), wintypes.BOOL,
                        wintypes.ULONG, ctypes.c_int, wintypes.ULONG]
        api.restype = wintypes.DWORD
    size = wintypes.DWORD(0)
    try:
        result = api(None, ctypes.byref(size), False, family, TCP_TABLE_OWNER_PID_LISTENER, 0)
        if result != ERROR_INSUFFICIENT_BUFFER:
            raise ListenerTableError("listener_table_size_failed")
        for _ in range(MAX_RETRIES):
            if size.value < 4 or size.value > MAX_TABLE_BYTES:
                raise ListenerTableError("listener_table_size_invalid")
            allocated = size.value
            buffer = ctypes.create_string_buffer(allocated)
            result = api(buffer, ctypes.byref(size), False, family, TCP_TABLE_OWNER_PID_LISTENER, 0)
            if result == 0:
                if size.value < 4 or size.value > allocated:
                    raise ListenerTableError("listener_table_size_invalid")
                return buffer.raw[:size.value]
            if result != ERROR_INSUFFICIENT_BUFFER:
                raise ListenerTableError("listener_api_failed")
        raise ListenerTableError("listener_table_unstable")
    except (OSError, OverflowError, ValueError) as exc:
        raise ListenerTableError("listener_api_failed") from exc


def listener_snapshot(port: int, *, api=None) -> dict:
    if type(port) is not int or not 1 <= port <= 65535:
        raise ListenerTableError("listener_port_invalid")
    rows = []
    for family in (socket.AF_INET, socket.AF_INET6):
        label = "ipv4" if family == socket.AF_INET else "ipv6"
        _diagnostic_marker(label + "_query_start")
        rows.extend(parse_table(query_table(family, api), family, port))
        _diagnostic_marker(label + "_query_complete")
    return {"listener_pids": [owner for owner, _ in rows],
            "listener_addresses": [address for _, address in rows]}


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ListenerTableError("listener_port_invalid")
        result = listener_snapshot(int(sys.argv[1]))
        _diagnostic_marker("serialization_start")
        print(json.dumps(result, separators=(",", ":")))
        _diagnostic_marker("serialization_complete")
        _diagnostic_marker("return_success")
        return 0
    except (ListenerTableError, ValueError) as exc:
        category = exc.category if isinstance(exc, ListenerTableError) else "listener_port_invalid"
        print(category, file=sys.stderr)
        _diagnostic_marker("return_failure")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
