"""Export native bpy RNA reference metadata from a separate factory Blender process."""

import json
import sys
from pathlib import Path

import bpy

output = Path(sys.argv[sys.argv.index("--") + 1])
output.parent.mkdir(parents=True, exist_ok=True)
version = ".".join(str(v) for v in bpy.app.version)
count = 0
with output.open("w", encoding="utf-8") as stream:
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name, None)
        rna = getattr(cls, "bl_rna", None)
        if rna is None:
            continue
        symbol = "bpy.types." + name
        entries = [(symbol, rna.description or name)]
        for prop in rna.properties:
            entries.append(
                (
                    symbol + "." + prop.identifier,
                    f"{prop.identifier}: {prop.type}. {prop.description}. Read-only: {prop.is_readonly}",
                )
            )
        for function in rna.functions:
            parameters = ", ".join(f"{p.identifier}: {p.type}" for p in function.parameters)
            entries.append(
                (
                    symbol + "." + function.identifier,
                    f"{function.identifier}({parameters}): {function.description}",
                )
            )
        known = {entry[0] for entry in entries}
        for member_name in dir(cls):
            member_symbol = symbol + "." + member_name
            if member_name.startswith("_") or member_symbol in known:
                continue
            member = getattr(cls, member_name, None)
            if callable(member) and getattr(member, "__doc__", None):
                entries.append((member_symbol, member.__doc__[:6000]))
        for entry_symbol, text in entries:
            stream.write(
                json.dumps(
                    {
                        "version": version,
                        "symbol": entry_symbol,
                        "source": f"Blender {version} bpy reference: {entry_symbol}",
                        "text": text,
                    }
                )
                + "\n"
            )
            count += 1
print(f"Exported {count} native bpy API reference entries for Blender {version}")
