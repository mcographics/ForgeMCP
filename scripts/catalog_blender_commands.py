"""Export registered native command coverage from an isolated Blender profile."""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "blender-addon"))
from majestic_forge.creative import list_commands, list_types

commands = []
offset = 0
while True:
    page = list_commands(offset=offset, limit=200)
    commands.extend(page["commands"])
    if not page["truncated"]:
        break
    offset += 200
root = Path(__file__).resolve().parents[1] / "Documentation" / "Reference_Audits"
report = {
    "blender_version": bpy.app.version_string,
    "profile": "factory-startup, built-in registered operators",
    "scope": "All registered bpy.ops identifiers are discoverable. Execution is separately policy-limited; bpy data/RNA workflows are additional to operators.",
    "total": len(commands),
    "execution_coverage": dict(Counter(c["execution"] for c in commands)),
    "rna_type_count": list_types()["total"],
    "commands": commands,
}
(root / "Blender_MCP_Commands.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
with (root / "Blender_MCP_Commands.csv").open("w", newline="", encoding="utf-8") as stream:
    writer = csv.DictWriter(stream, fieldnames=["identifier", "execution", "reason"])
    writer.writeheader()
    writer.writerows(commands)
print(json.dumps({k: v for k, v in report.items() if k != "commands"}))
