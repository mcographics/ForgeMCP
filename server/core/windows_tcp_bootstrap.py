"""Early, correlated launcher for the passive Windows listener helper."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path


def _mark(phase: str) -> None:
    destination = os.environ.get("FORGE_IDENTITY_CHILD_LOG")
    if not destination:
        return
    started = time.monotonic_ns()
    record = {"component": "bootstrap", "phase": phase,
              "correlation_id": os.environ.get("FORGE_IDENTITY_CORRELATION", ""),
              "origin": os.environ.get("FORGE_IDENTITY_ORIGIN", "other"),
              "pid": os.getpid(), "monotonic_ns": started}
    try:
        with open(destination, "a", encoding="utf-8") as stream:
            opened = time.monotonic_ns()
            record["open_ns"] = opened - started
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            stream.flush()
            written = time.monotonic_ns()
            stream.write(json.dumps({"component": "bootstrap", "phase": "marker_write_result",
                                     "correlation_id": record["correlation_id"],
                                     "pid": record["pid"], "for_phase": phase,
                                     "open_ns": record["open_ns"],
                                     "write_ns": written - opened,
                                     "monotonic_ns": written}, separators=(",", ":")) + "\n")
            stream.flush()
    except OSError:
        print("identity_diagnostic_write_failed", file=sys.stderr)
        raise SystemExit(3) from None


def main() -> None:
    _mark("python_entry")
    if len(sys.argv) != 3:
        print("listener_port_invalid", file=sys.stderr)
        raise SystemExit(2)
    script = Path(sys.argv[1])
    if not script.is_absolute() or not script.is_file() or script.parent != Path(__file__).parent:
        print("listener_launch_failed", file=sys.stderr)
        raise SystemExit(2)
    _mark("listener_import_start")
    port = sys.argv[2]
    try:
        spec = importlib.util.spec_from_file_location("forge_windows_tcp_listener", script)
        if spec is None or spec.loader is None:
            print("listener_launch_failed", file=sys.stderr)
            raise SystemExit(2)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _mark("listener_import_complete")
        sys.argv = [str(script), port]
        _mark("helper_execution_start")
        result = module.main()
        _mark("helper_exit")
        raise SystemExit(result)
    except SystemExit:
        raise
    except Exception:
        print("listener_launch_failed", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
