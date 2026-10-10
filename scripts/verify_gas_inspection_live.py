"""Probe native GAS inspection in a disposable Unreal validation project."""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    source_root = Path(__file__).resolve().parents[1]
    project_root = Path(os.environ["FORGE_GAS_VALIDATION_ROOT"]).resolve()
    expected_pid = int(os.environ["FORGE_GAS_VALIDATION_UNREAL_PID"])
    if not project_root.is_relative_to(source_root / "Saved"):
        raise RuntimeError("The GAS probe requires an isolated project under Saved.")

    environment = dict(os.environ)
    environment["FORGE_PROJECT_ROOT"] = str(project_root)
    environment["FORGE_BLENDER_SESSION_DIR"] = str(project_root / "Saved" / "BlenderSessions")
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.main"],
        cwd=str(source_root),
        env=environment,
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            tools = {tool.name for tool in (await client.list_tools()).tools}
            assert len(tools) == 23 and "unreal_inspect_gas" in tools, tools

            async def call(name, arguments):
                response = await client.call_tool(name, arguments)
                assert not response.isError, response
                return response.structuredContent

            sessions = await call("forge_list_sessions", {})
            matches = [
                session
                for session in sessions["data"]["sessions"]
                if session["kind"] == "unreal"
                and session["pid"] == expected_pid
                and session["connected"]
            ]
            assert len(matches) == 1, sessions
            session_id = matches[0]["session_id"]

            project = await call("unreal_project_info", {"session_id": session_id})
            assert project["ok"], project
            actual_project = os.path.normcase(os.path.abspath(project["data"]["project_file"]))
            expected_project = os.path.normcase(os.path.abspath(project_root / "ForgeMCPDev.uproject"))
            assert actual_project == expected_project, project

            suffix = uuid.uuid4().hex[:10]
            asset_path = f"/Game/ForgeMCPValidation/BP_GASInspect_{suffix}"
            recipe = {
                "asset_path": asset_path,
                "components": [
                    {
                        "name": "AbilitySystemComponent",
                        "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                        "replication_mode": "mixed",
                    },
                    {
                        "name": "GASSetup",
                        "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
                        "gas_setup": {
                            "ability_system_component": "AbilitySystemComponent",
                            "initialize_owner_as_avatar": True,
                            "attribute_sets": [],
                            "startup_abilities": [],
                            "startup_effects": [],
                        },
                    },
                ],
                "place": True,
                "save": False,
            }
            preview = await call("unreal_preview_blueprint", {
                "session_id": session_id,
                "recipe": recipe,
            })
            assert preview["ok"], preview
            applied = await call("unreal_apply_blueprint", {
                "session_id": session_id,
                "preview_id": preview["data"]["preview_id"],
                "confirmation": preview["data"]["preview_id"],
            })
            assert applied["ok"] and applied["data"]["state"] == "completed", applied
            assert applied["data"]["placed"] and not applied["data"]["saved"], applied
            blueprint_components = applied["data"]["components"]
            blueprint_asc = next(
                component for component in blueprint_components
                if component["name"] == "AbilitySystemComponent"
            )
            blueprint_setup = next(
                component for component in blueprint_components if component["name"] == "GASSetup"
            )
            assert blueprint_asc["replication_mode"] == "mixed", blueprint_asc
            assert blueprint_asc["replication_mode_configured"], blueprint_asc
            assert blueprint_asc["component_template_replication_mode"] == "full", blueprint_asc
            assert blueprint_setup["gas_configures_replication_mode"], blueprint_setup
            assert blueprint_setup["gas_replication_mode"] == "mixed", blueprint_setup

            inspected = await call("unreal_inspect_gas", {
                "session_id": session_id,
                "actor_path": applied["data"]["actor_path"],
            })
            assert inspected["ok"], inspected
            gas = inspected["data"]
            assert gas["ability_system_component_count"] == 1, gas
            component = gas["ability_system_components"][0]
            assert component["name"] == "AbilitySystemComponent", component
            assert component["replication_mode"] == "mixed", component
            assert component["replicated"], component
            assert component["ability_count"] == 0 and component["active_effect_count"] == 0, component
            assert component["owned_tag_count"] == 0 and component["attribute_count"] == 0, component
            assert not component["abilities_truncated"] and not component["active_effects_truncated"], component

            report = {
                "project": str(project_root / "ForgeMCPDev.uproject"),
                "session_id": session_id,
                "tool_count": len(tools),
                "asset_path": asset_path,
                "blueprint_apply": applied["data"],
                "blueprint_component_configuration": blueprint_components,
                "gas_inspection": gas,
                "asset_saved": False,
                "level_saved": False,
            }
            report_path = project_root / "Saved" / "gas-inspection-live-report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("FORGE_LIVE_MCP_UNREAL_GAS_COMPONENT_ATTRIBUTES_TAGS_ABILITIES_EFFECTS_INSPECTION_PASS")


if __name__ == "__main__":
    asyncio.run(main())
