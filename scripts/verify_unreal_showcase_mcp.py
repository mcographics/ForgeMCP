"""Read-only MCP acceptance for the saved ForgeMCP Blueprint showcase.

Run from the repository venv with --session-id for the intended live editor.
This starts a fresh source MCP subprocess; connected-client proof is separate.
It never creates assets, changes the world, compiles, or saves editor content.
"""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


async def verify(args):
    root = Path(__file__).resolve().parents[1]
    expected_project = root / "ForgeMCPDev.uproject"
    asset_path = "/Game/ForgeMCP_Demos/BP_MCP_Showcase_20261011"
    package = root / "Content/ForgeMCP_Demos/BP_MCP_Showcase_20261011.uasset"
    require(package.is_file(), "Create the authorized showcase in Unreal before verification.")
    original_bytes = package.read_bytes()
    original_hash = hashlib.sha256(original_bytes).hexdigest()
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root), env=dict(os.environ)
    )
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()

            async def call(name, arguments):
                result = await client.call_tool(name, arguments)
                data = result.structuredContent
                require(not result.isError and data and data.get("ok"), f"{name} failed: {data}")
                return data["data"]

            registry = await client.list_tools()
            project = await call("unreal_project_info", {"session_id": args.session_id})
            require(Path(project["project_file"]).resolve() == expected_project.resolve(),
                    "Session does not belong to the intended ForgeMCPDev project.")
            require(not project["play_in_editor"], "Stop PIE before running editor acceptance.")
            inspection = await call("unreal_inspect_blueprint", {
                "session_id": args.session_id, "asset_path": asset_path,
            })
            require(not inspection.get("graphs_truncated"), "Graph inspection was truncated.")
            variables = {item["name"]: item for item in inspection["variables"]}
            require(variables["DemoEnabled"]["default"].lower() == "true",
                    "DemoEnabled default differs from the reviewed recipe.")
            require(variables["DemoLabel"]["default"] == "Created through ForgeMCP",
                    "DemoLabel default differs from the reviewed recipe.")
            require(any(item["name"] == "DemoMesh" and
                        item["class"] == "/Script/Engine.StaticMeshComponent"
                        for item in inspection["components"]), "DemoMesh component is missing.")
            graph = next(item for item in inspection["graphs"] if item["name"] == "EchoValue")
            require(not graph["truncated"], "EchoValue graph was truncated.")
            entry = next(item for item in graph["nodes"]
                         if item["class"].endswith(".K2Node_FunctionEntry"))
            output = next(item for item in graph["nodes"]
                          if item["class"].endswith(".K2Node_FunctionResult"))
            source_pin = next(item for item in entry["pins"] if item["name"] == "InputValue")
            target_pin = next(item for item in output["pins"] if item["name"] == "OutputValue")
            require(f"{output['id']}:OutputValue" in source_pin["links"] and
                    f"{entry['id']}:InputValue" in target_pin["links"],
                    "EchoValue input/output connection is missing or asymmetric.")
            found = await call("unreal_search_assets", {
                "session_id": args.session_id, "path": "/Game/ForgeMCP_Demos",
                "name_contains": "BP_MCP_Showcase_20261011", "limit": 10,
            })
            require(any(item["package_name"] == asset_path for item in found["assets"]),
                    "Saved showcase is missing from the native Asset Registry.")
            after = await call("unreal_project_info", {"session_id": args.session_id})
            require(after == project, "Editor project/world context changed during acceptance.")
            require(hashlib.sha256(package.read_bytes()).hexdigest() == original_hash,
                    "Showcase package bytes changed during read-only acceptance.")
            return {
                "ok": True, "transport": "fresh source MCP stdio subprocess",
                "session_id": args.session_id, "project": project,
                "registered_tool_count": len(registry.tools), "asset_path": asset_path,
                "package_bytes": len(original_bytes), "package_sha256": original_hash,
                "checks": ["project identity", "variable defaults", "component class",
                           "bidirectional function pin links", "native asset registry",
                           "unchanged project/world context", "unchanged package bytes"],
                "limits": "Does not restart the Editor or execute gameplay; no visual UI validation.",
            }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--report", type=Path, help="Optional new JSON evidence file; no overwrite.")
    args = parser.parse_args()
    if args.report and args.report.exists():
        parser.error("Report already exists; choose a new path.")
    report = asyncio.run(verify(args))
    encoded = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as output:
            output.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
