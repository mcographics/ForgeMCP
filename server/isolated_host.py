# SPDX-License-Identifier: MIT
"""Dedicated entry point that refuses to fall back to shared production config."""

from __future__ import annotations

import os


def main() -> None:
    mode = os.environ.get("FORGE_HOST_MODE", "").strip().lower()
    if mode != "isolated":
        raise SystemExit(
            "Dedicated ForgeMCP host requires FORGE_HOST_MODE=isolated; no production fallback is allowed."
        )
    # Import only after the explicit mode check: server.main initializes the
    # configured registry at module load time.
    from server.main import main as run_server

    run_server()


if __name__ == "__main__":
    main()
