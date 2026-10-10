"""Build native control/data flow through MCP only in the guarded isolated project."""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from server.core.connections import BridgeError, ConnectionManager


async def main():
    root = Path(__file__).resolve().parents[1]
    expected = (root / "Saved/Milestone2/HostProject").resolve()
    assert Path(os.environ["FORGE_PROJECT_ROOT"]).resolve() == expected
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                   cwd=str(root), env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.isError, result
                result = result.structuredContent
                assert result and result["ok"], result
                return result["data"]

            sessions = await call("forge_list_sessions", {})
            targets = [s for s in sessions["sessions"] if s["kind"] == "unreal" and s["connected"]]
            assert len(targets) == 1
            session = targets[0]["session_id"]
            project = await call("unreal_project_info", {"session_id": session})
            assert Path(project["project_file"]).resolve().parent == expected
            recipe = {
                "asset_path": "/Game/ForgeValidation/BP_ControlFlow_" + uuid.uuid4().hex[:8],
                "variables": [{"name": "Enabled", "type": "bool", "default": "true"}],
                "nodes": [
                    {"id": "begin", "kind": "event", "name": "ReceiveBeginPlay"},
                    {"id": "flag", "kind": "variable_get", "name": "Enabled"},
                    {"id": "wire", "kind": "reroute", "name": "FlagWire"},
                    {"id": "branch", "kind": "branch", "name": "Gate"},
                    {"id": "order", "kind": "sequence", "name": "Order", "execution_outputs": 3},
                    {"id": "actor", "kind": "self", "name": "ActorReference"},
                    {"id": "first", "kind": "call_function", "name": "PrintString",
                     "owner_class": "/Script/Engine.KismetSystemLibrary", "defaults": {"InString": "First"}},
                    {"id": "second", "kind": "call_function", "name": "PrintString",
                     "owner_class": "/Script/Engine.KismetSystemLibrary", "defaults": {"InString": "Second"}},
                    {"id": "visible", "kind": "call_function", "name": "SetActorHiddenInGame",
                     "defaults": {"bNewHidden": "false"}},
                ],
                "connections": [], "save": False, "place": False,
            }
            links = [
                ("begin", "then", "branch", "execute"),
                ("flag", "Enabled", "wire", "InputPin"),
                ("wire", "OutputPin", "branch", "Condition"),
                ("branch", "then", "order", "execute"),
                ("order", "then_0", "first", "execute"),
                ("order", "then_1", "second", "execute"),
                ("order", "then_2", "visible", "execute"),
                ("actor", "self", "visible", "self"),
            ]
            recipe["connections"] = [{"from_node": a, "from_pin": b, "to_node": c, "to_pin": d}
                                     for a, b, c, d in links]
            preview = await call("unreal_preview_blueprint", {"session_id": session, "recipe": recipe})
            result = await call("unreal_apply_blueprint", {"session_id": session,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert result["state"] == "completed" and result["compiler_errors"] == 0, result
            assert not result["saved"] and not result["placed"]
            inspected = await call("unreal_inspect_blueprint", {"session_id": session,
                                   "asset_path": recipe["asset_path"]})
            nodes = [node for graph in inspected["graphs"] for node in graph["nodes"]]
            for kind in ("K2Node_IfThenElse", "K2Node_ExecutionSequence", "K2Node_Self", "K2Node_Knot"):
                assert any(node["class"].endswith("." + kind) for node in nodes), kind
            sequence = next(node for node in nodes if node["class"].endswith(".K2Node_ExecutionSequence"))
            assert all(any(pin["name"] == name and pin["links"] for pin in sequence["pins"])
                       for name in ("then_0", "then_1", "then_2"))
            wire = next(node for node in nodes if node["class"].endswith(".K2Node_Knot"))
            assert all(pin["type"] == "bool" for pin in wire["pins"])
            bad_recipe = {"asset_path": recipe["asset_path"] + "_Invalid", "nodes": [
                {"id": "branch", "kind": "branch", "name": "Gate",
                 "defaults": {"Condition": "not_a_boolean"}}
            ]}
            bad_preview = await call("unreal_preview_blueprint", {"session_id": session, "recipe": bad_recipe})
            bad_result = await call("unreal_apply_blueprint", {"session_id": session,
                "preview_id": bad_preview["preview_id"], "confirmation": bad_preview["preview_id"]})
            assert bad_result["state"] == "rolled_back" and not bad_result["saved"], bad_result
            bad_recipe["nodes"][0]["defaults"]["Condition"] = "true"
            await call("unreal_preview_blueprint", {"session_id": session, "recipe": bad_recipe})
            manager = ConnectionManager.configured()
            native_session = next(s for s in manager.discover() if s.session_id == session)
            for value in (17, 1, 2.5, "3"):
                try:
                    await manager.request(native_session, "blueprint_preview", {"recipe": {
                        "asset_path": recipe["asset_path"] + "_Sequence",
                        "nodes": [{"id": "order", "kind": "sequence", "name": "Order",
                                   "execution_outputs": value}]
                    }})
                    raise AssertionError("Native sequence bound/type check failed")
                except BridgeError as error:
                    assert error.code == "invalid_recipe"
            output = root / "Saved/Milestone2/blueprint-flow-live-report.json"
            output.write_text(json.dumps({"project": project, "recipe": recipe,
                                         "apply": result, "inspection": inspected,
                                         "invalid_default_rollback": bad_result,
                                         "native_sequence_rejection_cases": 4}, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_BLUEPRINT_BRANCH_SEQUENCE_SELF_REROUTE_NATIVE_COMPILE_PASS")


if __name__ == "__main__":
    asyncio.run(main())
