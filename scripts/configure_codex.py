"""Create a workspace-scoped Codex MCP entry, preserving any existing settings."""

import json
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config_path = root / ".codex" / "config.toml"
python_path = root / ".venv" / "Scripts" / "python.exe"
if not python_path.is_file():
    raise SystemExit("Create .venv and install the package before configuring Codex.")
old = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
config = tomllib.loads(old)
expected = {
    "command": python_path.as_posix(),
    "args": ["-m", "server.main"],
    "cwd": root.as_posix(),
    "startup_timeout_sec": 20,
    "tool_timeout_sec": 30,
    "env": {"FORGE_PROJECT_ROOT": root.as_posix()},
}
servers = config.get("mcp_servers", {})
entry = servers.get("forgemcp")
legacy_entry = servers.get("majestic_forge")
if legacy_entry is not None:
    if entry is not None:
        raise SystemExit("Both forgemcp and legacy majestic_forge entries exist; review them manually.")
    if legacy_entry != expected:
        raise SystemExit("An existing majestic_forge configuration differs; review it manually.")
    updated = old.replace(
        "[mcp_servers.majestic_forge.env]", "[mcp_servers.forgemcp.env]"
    ).replace("[mcp_servers.majestic_forge]", "[mcp_servers.forgemcp]")
    if updated == old:
        raise SystemExit("Could not locate the legacy majestic_forge table in the config.")
    tomllib.loads(updated)
    config_path.write_text(updated, encoding="utf-8")
    print(f"Migrated the workspace MCP entry in {config_path} to forgemcp.")
elif entry is not None:
    if entry != expected:
        raise SystemExit("An existing forgemcp configuration differs; review it manually.")
    print("Workspace Codex MCP entry is already configured.")
else:
    lines = ["", "[mcp_servers.forgemcp]"]
    for key, value in expected.items():
        if key != "env":
            lines.append(f"{key} = {json.dumps(value)}")
    lines += [
        "",
        "[mcp_servers.forgemcp.env]",
        f"FORGE_PROJECT_ROOT = {json.dumps(root.as_posix())}",
        "",
    ]
    updated = old + "\n".join(lines)
    tomllib.loads(updated)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(updated, encoding="utf-8")
    print(f"Configured {config_path}. Restart the Codex extension to load the ForgeMCP tools.")
