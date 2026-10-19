"""Verify existing Blueprint/GAS edits and recovery only in an isolated project."""

import asyncio
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    root = Path(__file__).resolve().parents[1]
    expected = Path(os.environ.get(
        "FORGE_BLUEPRINT_EDIT_VALIDATION_ROOT", root / "Saved/Milestone2/HostProject"
    )).resolve()
    if not expected.is_relative_to((root / "Saved").resolve()):
        raise RuntimeError("Blueprint edit validation must use a disposable project under Saved.")
    expected_pid = os.environ.get("FORGE_BLUEPRINT_EDIT_VALIDATION_UNREAL_PID")
    expected_pid = int(expected_pid) if expected_pid else None
    assert Path(os.environ["FORGE_PROJECT_ROOT"]).resolve() == expected
    params = StdioServerParameters(command=sys.executable, args=["-m", "server.main"],
                                   cwd=str(root), env=dict(os.environ))
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, args, error=None):
                response = await client.call_tool(name, args)
                assert not response.isError, response
                result = response.structuredContent
                assert result
                if error:
                    assert not result["ok"] and result["error"]["code"] == error, result
                    return result
                assert result["ok"], result
                return result["data"]

            sessions = await call("forge_list_sessions", {})
            targets = [
                s for s in sessions["sessions"]
                if s["kind"] == "unreal" and s["connected"]
                and (expected_pid is None or s["pid"] == expected_pid)
            ]
            assert len(targets) == 1
            session = targets[0]["session_id"]
            project = await call("unreal_project_info", {"session_id": session})
            assert Path(project["project_file"]).resolve().parent == expected
            path = "/Game/ForgeValidation/BP_ExistingEdits_" + uuid.uuid4().hex[:8]
            recipe = {"asset_path": path, "save": True, "nodes": [
                {"id": "begin", "kind": "event", "name": "ReceiveBeginPlay"},
                {"id": "branch", "kind": "branch", "name": "Gate", "defaults": {"Condition": "true"}},
                {"id": "print", "kind": "call_function", "name": "PrintString",
                 "owner_class": "/Script/Engine.KismetSystemLibrary", "defaults": {"InString": "Original"}},
                {"id": "self", "kind": "self", "name": "ActorReference"},
                {"id": "math", "kind": "call_function", "name": "Add_DoubleDouble",
                 "owner_class": "/Script/Engine.KismetMathLibrary"},
            ], "connections": [
                {"from_node": "begin", "from_pin": "then", "to_node": "branch", "to_pin": "execute"},
                {"from_node": "branch", "from_pin": "then", "to_node": "print", "to_pin": "execute"},
            ]}
            preview = await call("unreal_preview_blueprint", {"session_id": session, "recipe": recipe})
            created = await call("unreal_apply_blueprint", {"session_id": session,
                "preview_id": preview["preview_id"], "confirmation": preview["preview_id"]})
            assert created["state"] == "completed" and created["saved"]
            asset_file = expected / "Content" / (path.removeprefix("/Game/") + ".uasset")
            original_hash = hashlib.sha256(asset_file.read_bytes()).hexdigest()

            async def inspect():
                return await call("unreal_inspect_blueprint", {"session_id": session, "asset_path": path})

            before = await inspect()
            nodes = [n for graph in before["graphs"] if graph["name"] == "EventGraph" for n in graph["nodes"]]
            branch = next(n for n in nodes if n["class"].endswith(".K2Node_IfThenElse"))
            printer = next(n for n in nodes if n["class"].endswith(".K2Node_CallFunction")
                           and any(p["name"] == "InString" for p in n["pins"]))
            math = next(n for n in nodes if n["class"].endswith(".K2Node_CallFunction")
                        and any(p["name"] == "A" for p in n["pins"]))
            actor = next(n for n in nodes if n["class"].endswith(".K2Node_Self"))

            async def preview_edit(operations):
                return await call("unreal_preview_blueprint_edits", {"session_id": session,
                    "recipe": {"asset_path": path, "operations": operations}})

            async def apply(plan, error=None):
                return await call("unreal_apply_blueprint_edits", {"session_id": session,
                    "preview_id": plan["preview_id"], "confirmation": plan["preview_id"]}, error)

            edits = [
                {"op": "move", "graph": "EventGraph", "node_id": branch["id"], "x": 333, "y": 222},
                {"op": "default", "graph": "EventGraph", "node_id": printer["id"], "pin": "InString", "value": "Updated"},
                {"op": "disconnect", "graph": "EventGraph", "node_id": branch["id"], "pin": "then", "to_node": printer["id"], "to_pin": "execute"},
                {"op": "connect", "graph": "EventGraph", "node_id": branch["id"], "pin": "else", "to_node": printer["id"], "to_pin": "execute"},
            ]
            stale = await preview_edit(edits)
            plan = await preview_edit(edits)
            assert await inspect() == before, "Preview mutated the graph"
            result = await apply(plan)
            assert result["state"] == "completed" and result["compiler_errors"] == 0 and not result["saved"], result
            journal = Path(result["recovery_journal"])
            assert journal.resolve().is_relative_to(expected / "Saved/MajesticForge/Recovery") and journal.is_file()
            journal_data = json.loads(journal.read_text(encoding="utf-8-sig"))
            assert journal_data["asset_path"].startswith(path)
            await apply(plan, "preview_not_found")
            await apply(stale, "stale_preview")
            after = await inspect()
            current = [n for g in after["graphs"] if g["name"] == "EventGraph" for n in g["nodes"]]
            changed = next(n for n in current if n["id"] == branch["id"])
            assert changed["x"] == 333 and changed["y"] == 222
            assert not next(p for p in changed["pins"] if p["name"] == "then")["links"]
            assert next(p for p in changed["pins"] if p["name"] == "else")["links"]
            changed_print = next(n for n in current if n["id"] == printer["id"])
            assert next(p for p in changed_print["pins"] if p["name"] == "InString")["default"] == "Updated"
            add_sequence = await call("unreal_preview_blueprint_edits", {"session_id": session,
                "recipe": {"asset_path": path, "operations": [], "nodes": [
                    {"id": "new_sequence", "kind": "sequence", "name": "ReviewedSequence",
                     "graph": "EventGraph", "x": 555, "y": 333, "execution_outputs": 3},
                    {"id": "speed_get", "kind": "variable_get", "name": "Speed"},
                    {"id": "speed_set", "kind": "variable_set", "name": "Speed"}],
                    "variables": [{"name": "Speed", "type": "float", "default": "2.5"}],
                    "components": [
                        {"name": "Mesh", "class_path": "/Script/Engine.StaticMeshComponent"},
                        {
                            "name": "AbilitySystemComponent",
                            "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                            "replication_mode": "mixed",
                        },
                        {
                            "name": "GASSetup",
                            "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
                            "gas_setup": {"ability_system_component": "AbilitySystemComponent"},
                        },
                    ],
                    "connections": [
                        {"graph": "EventGraph", "from_node": branch["id"], "from_pin": "then",
                         "to_node": "new_sequence", "to_pin": "execute"},
                        {"graph": "EventGraph", "from_node": "new_sequence", "from_pin": "then_0",
                         "to_node": printer["id"], "to_pin": "execute"}]}})
            assert await inspect() == after, "Node creation preview mutated the graph"
            added = await apply(add_sequence)
            assert added["state"] == "completed" and added["compiler_errors"] == 0, added
            assert len(added["created_nodes"]) == 3 and len(added["created_variables"]) == 1
            assert len(added["created_components"]) == 3
            assert added["created_variables"] == ["Speed"] and len(added["created_components"]) == 3
            assert {node["id"] for node in added["created_nodes"]} == {"new_sequence", "speed_get", "speed_set"}
            after = await inspect()
            speed = next(v for v in after["variables"] if v["name"] == "Speed")
            assert abs(float(speed["default"]) - 2.5) < 1e-6
            assert any(c["name"] == "Mesh" and c["class"].endswith("StaticMeshComponent") for c in after["components"])
            asc = next(c for c in after["components"] if c["name"] == "AbilitySystemComponent")
            assert asc["replication_mode"] == "mixed" and asc["replication_mode_configured"], asc
            assert asc["component_template_replication_mode"] == "full", asc
            gas_setup = next(c for c in after["components"] if c["name"] == "GASSetup")
            assert gas_setup["gas_configures_replication_mode"]
            assert gas_setup["gas_replication_mode"] == "mixed"
            current = [n for g in after["graphs"] if g["name"] == "EventGraph" for n in g["nodes"]]
            sequence_guid = next(n["node_id"] for n in added["created_nodes"] if n["id"] == "new_sequence")
            sequence = next(n for n in current if n["id"] == sequence_guid)
            assert sequence["class"].endswith(".K2Node_ExecutionSequence")
            assert len(next(p for p in sequence["pins"] if p["direction"] == "output" and p["name"] == "then_2")["links"]) == 0
            assert next(p for p in sequence["pins"] if p["direction"] == "output" and p["name"] == "then_0")["links"]
            function_recipe = {"asset_path": path, "operations": [], "variables": [], "components": [],
                "functions": [{"name": "ReviewedScale", "inputs": [{"name": "Value", "type": "float"}],
                    "outputs": [{"name": "Result", "type": "float"}], "pure": True}],
                "nodes": [{"id": "scale_entry", "kind": "function_entry", "name": "Entry", "graph": "ReviewedScale"},
                    {"id": "scale_return", "kind": "function_result", "name": "Return", "graph": "ReviewedScale"}],
                "connections": [{"graph": "ReviewedScale", "from_node": "scale_entry", "from_pin": "Value",
                    "to_node": "scale_return", "to_pin": "Result"}]}
            function_preview = await call("unreal_preview_blueprint_edits", {
                "session_id": session, "recipe": function_recipe})
            assert await inspect() == after, "Function preview mutated the graph"
            function_apply = await call("unreal_apply_blueprint_edits", {
                "session_id": session, "preview_id": function_preview["preview_id"],
                "confirmation": function_preview["preview_id"]})
            assert function_apply["state"] == "completed" and function_apply["compiler_errors"] == 0, function_apply
            assert function_apply["created_functions"] == ["ReviewedScale"] and not function_apply["saved"]
            after_function = await inspect()
            scale_graph = next(g for g in after_function["graphs"] if g["name"] == "ReviewedScale")
            scale_entry = next(n for n in scale_graph["nodes"] if n["class"].endswith(".K2Node_FunctionEntry"))
            scale_return = next(n for n in scale_graph["nodes"] if n["class"].endswith(".K2Node_FunctionResult"))
            assert next(p for p in scale_entry["pins"] if p["name"] == "Value")["links"]
            assert next(p for p in scale_return["pins"] if p["name"] == "Result")["links"]
            # Structurally valid endpoints with incompatible object -> exec types:
            # the preceding move must be restored when native connection fails.
            bad = await preview_edit([
                {"op": "move", "graph": "EventGraph", "node_id": branch["id"], "x": 999, "y": 999},
                {"op": "connect", "graph": "EventGraph", "node_id": math["id"], "pin": "ReturnValue", "to_node": printer["id"], "to_pin": "InString"},
                {"op": "connect", "graph": "EventGraph", "node_id": actor["id"], "pin": "self", "to_node": printer["id"], "to_pin": "execute"},
            ])
            rollback = await apply(bad)
            assert rollback["state"] == "rolled_back", rollback
            assert await inspect() == after, "Rollback failed to restore exact inspected graph state"
            rollback_function_preview = await call("unreal_preview_blueprint_edits", {"session_id": session,
                "recipe": {"asset_path": path, "operations": [
                    {"op": "connect", "graph": "EventGraph", "node_id": actor["id"], "pin": "self",
                     "to_node": printer["id"], "to_pin": "execute"}],
                    "functions": [{"name": "RollbackFunction", "inputs": [], "outputs": []}],
                    "nodes": [], "connections": []}})
            rollback_function = await call("unreal_apply_blueprint_edits", {"session_id": session,
                "preview_id": rollback_function_preview["preview_id"],
                "confirmation": rollback_function_preview["preview_id"]})
            assert rollback_function["state"] == "rolled_back", rollback_function
            assert await inspect() == after_function, "Function graph rollback did not restore exact Blueprint state"
            assert hashlib.sha256(asset_file.read_bytes()).hexdigest() == original_hash, "Edit overwrote the saved asset"
            registered_tools = {tool.name for tool in (await client.list_tools()).tools}
            assert {"unreal_preview_blueprint_edits", "unreal_apply_blueprint_edits"} <= registered_tools
            (expected / "Saved/blueprint-edits-live-report.json").write_text(
                json.dumps({"project": project, "asset_path": path, "before": before,
                            "apply": result, "add_nodes_apply": added, "after": after,
                            "function_preview": function_preview, "function_apply": function_apply,
                            "function_inspection": scale_graph, "function_rollback": rollback_function,
                            "rollback": rollback,
                            "saved_asset_hash_unchanged": True}, indent=2), encoding="utf-8")
    print("FORGE_LIVE_MCP_EXISTING_BLUEPRINT_NODE_CREATE_WIRE_EDIT_JOURNAL_STALE_REPLAY_ROLLBACK_PASS")


if __name__ == "__main__":
    asyncio.run(main())
