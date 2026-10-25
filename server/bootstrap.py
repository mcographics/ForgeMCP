# SPDX-License-Identifier: MIT
"""Observable entry point for the existing ForgeMCP stdio server."""

import json
import os
import sys
import time

_START = time.monotonic_ns()


def _mark(event: str) -> None:
    stamp = time.monotonic_ns()
    record = json.dumps({
        "component": "forgemcp_bootstrap",
        "event": event,
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "utc_ns": time.time_ns(),
        "monotonic_ns": stamp,
        "elapsed_ms": (stamp - _START) // 1_000_000,
    }) + "\n"
    try:
        sys.stderr.write(record)
        sys.stderr.flush()
    except OSError:
        pass
    try:
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Saved", f"ForgeMCPBootstrap-{os.getpid()}.jsonl")
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(record)
    except OSError:
        pass


def main() -> None:
    _mark("python_entry")
    from server import main as application

    _mark("tool_registry_constructed")
    application.main()


if __name__ == "__main__":
    main()
