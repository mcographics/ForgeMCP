"""Compile and inspect a typed Blueprint function in the isolated validation editor."""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "Saved/FunctionSignatureValidation/ForgeMCPDev").resolve()
    assert Path(os.environ["FORGE_PROJECT_ROOT"]).resolve() == expected
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root), env=dict(os.environ)
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.isError, result
                data = result.structuredContent
                assert data and data["ok"], data
                return data["data"]

            sessions = await call("forge_list_sessions", {})
            targets = [
                session for session in sessions["sessions"]
                if session["kind"] == "unreal" and session["connected"]
            ]
            assert len(targets) == 1, "Expected only the isolated validation editor session"
            session = targets[0]["session_id"]
            project = await call("unreal_project_info", {"session_id": session})
            assert Path(project["project_file"]).resolve().parent == expected
            asset_path = f"/Game/ForgeValidation/BP_FunctionSignature_{uuid.uuid4().hex[:8]}"
            recipe = {
                "asset_path": asset_path,
                "components": [{
                    "name": "AbilitySystemComponent",
                    "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                    "replication_mode": "mixed",
                }],
                "functions": [{
                    "name": "ComputeDamage",
                    "inputs": [
                        {"name": "BaseDamage", "type": "float"},
                        {"name": "Multiplier", "type": "float"},
                    ],
                    "outputs": [{"name": "Damage", "type": "float"}],
                    "pure": True,
                }],
                "nodes": [
                    {"id": "entry", "kind": "function_entry", "name": "Entry",
                     "graph": "ComputeDamage"},
                    {"id": "return", "kind": "function_result", "name": "Return",
                     "graph": "ComputeDamage"},
                ],
                "connections": [
                    {"graph": "ComputeDamage", "from_node": "entry", "from_pin": "BaseDamage",
                     "to_node": "return", "to_pin": "Damage"},
                ],
                "save": False,
                "place": False,
            }
            preview = await call(
                "unreal_preview_blueprint", {"session_id": session, "recipe": recipe}
            )
            applied = await call("unreal_apply_blueprint", {
                "session_id": session,
                "preview_id": preview["preview_id"],
                "confirmation": preview["preview_id"],
            })
            assert applied["state"] == "completed" and applied["compiler_errors"] == 0, applied
            assert not applied["saved"] and not applied["placed"], applied

            inspection = await call("unreal_inspect_blueprint", {
                "session_id": session, "asset_path": asset_path,
            })
            graph = next(graph for graph in inspection["graphs"]
                         if graph["name"] == "ComputeDamage")
            ability_system = next(component for component in inspection["components"]
                                  if component["name"] == "AbilitySystemComponent")
            entry = next(node for node in graph["nodes"]
                         if node["class"].endswith(".K2Node_FunctionEntry"))
            result = next(node for node in graph["nodes"]
                          if node["class"].endswith(".K2Node_FunctionResult"))
            assert all(any(pin["name"] == name for pin in entry["pins"])
                       for name in ("BaseDamage", "Multiplier"))
            assert any(pin["name"] == "Damage" for pin in result["pins"])
            assert any(pin["name"] == "BaseDamage" and pin["links"] for pin in entry["pins"])
            assert any(pin["name"] == "Damage" and pin["links"] for pin in result["pins"])
            assert ability_system["class"] == "/Script/GameplayAbilities.AbilitySystemComponent"
            assert ability_system["replicated"] and ability_system["replication_mode"] == "mixed"
            report = {
                "project_file": project["project_file"],
                "asset_path": asset_path,
                "recipe": recipe,
                "apply": applied,
                "function_graph": graph,
            }
    output = root / "Saved/FunctionSignatureValidation/blueprint-functions-live-report.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Typed Blueprint function compile and pin inspection passed: {output}")


if __name__ == "__main__":
    asyncio.run(main())
