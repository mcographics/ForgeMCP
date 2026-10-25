"""Private line-delimited listener worker; no network endpoint or session credentials."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

MAX_LINE = 256


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    script = Path(sys.argv[1])
    if not script.is_absolute() or script.parent != Path(__file__).parent or not script.is_file():
        return 2
    spec = importlib.util.spec_from_file_location("forge_tcp_worker_listener", script)
    if spec is None or spec.loader is None:
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = sys.stdout.buffer
    output.write(json.dumps({"ready": True, "pid": os.getpid()}).encode() + b"\n")
    output.flush()
    while True:
        line = sys.stdin.buffer.readline(MAX_LINE + 1)
        if not line:
            return 0
        if len(line) > MAX_LINE or not line.endswith(b"\n"):
            return 3
        try:
            request = json.loads(line)
            if (not isinstance(request, dict) or set(request) != {"id", "port"}
                    or not isinstance(request["id"], str) or len(request["id"]) != 32
                    or any(c not in "0123456789abcdef" for c in request["id"])
                    or type(request["port"]) is not int):
                return 3
            result = module.listener_snapshot(request["port"])
            response = {"id": request["id"], "result": result}
        except (ValueError, module.ListenerTableError):
            return 3
        encoded = json.dumps(response, separators=(",", ":")).encode() + b"\n"
        if len(encoded) > 65536:
            return 3
        output.write(encoded)
        output.flush()


if __name__ == "__main__":
    raise SystemExit(main())
