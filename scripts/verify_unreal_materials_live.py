"""After editor/plugin rebuild, verify ONLY the authorized JasperPrism test material.

Never rerun blindly after a timeout/partial result. Existing destinations are refused.
This script starts a fresh stdio server; it does not restart the user's editor/client.
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

PROJECT = Path("G:/Unreal Engine Projects/JasperPrismDev")
TEST_PATH = "/JasperPrism/Materials/M_ForgeMCP_Test"
ORIGINAL = "/JasperPrism/Materials/M_JasperPrism_PP"
MATERIAL_TOOLS = {
    "unreal_inspect_material_graph", "unreal_preview_material", "unreal_apply_material",
    "unreal_preview_material_edits", "unreal_apply_material_edits",
    "unreal_preview_material_compile", "unreal_compile_material",
    "unreal_preview_material_save", "unreal_save_material",
}


def recipe():
    return {
        "asset_path": TEST_PATH,
        "nodes": [
            {"id": "scene", "type": "SceneTexture", "x": -600,
             "parameters": {"scene_texture_id": "PostProcessInput0", "filtered": False}},
            {"id": "subtract", "type": "Subtract", "x": -350,
             "parameters": {"const_b": 0.5}},
            {"id": "multiply", "type": "Multiply", "x": -100,
             "parameters": {"const_b": 1.08}},
            {"id": "add", "type": "Add", "x": 150,
             "parameters": {"const_b": 0.5}},
        ],
        "connections": [
            {"from_node": "scene", "from_output": "Color", "to_node": "subtract", "to_input": "A"},
            {"from_node": "subtract", "to_node": "multiply", "to_input": "A"},
            {"from_node": "multiply", "to_node": "add", "to_input": "A"},
        ],
        "properties": [{"from_node": "add", "property": "EmissiveColor"}],
    }


def content_hashes():
    # Read-only verification of all existing content, including Sky/Weather assets.
    roots = [PROJECT / "Content", PROJECT / "Plugins/JasperPrism/Content"]
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for root in roots for p in root.rglob("*") if p.is_file()
            and p.name != "M_ForgeMCP_Test.uasset"}


async def run(session_id):
    root = Path(__file__).resolve().parents[1]
    report_path = root / "Saved/MaterialAutomation/live-verification.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"session_id": session_id, "asset_path": TEST_PATH, "state": "started"}

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    hashes = content_hashes()
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "server.main"], cwd=str(root),
        env={**os.environ, "FORGE_PROJECT_ROOT": str(root),
             "FORGE_UNREAL_SESSION_DIR": str(PROJECT / "Saved/MajesticForge")},
    )
    try:
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {t.name for t in (await client.list_tools()).tools}
                assert MATERIAL_TOOLS <= names, "New server tools are not discoverable"
                report["discovered_tools"] = sorted(MATERIAL_TOOLS)

                async def call(name, arguments):
                    response = await client.call_tool(name, {"session_id": session_id, **arguments})
                    assert not response.isError, f"{name}: tool validation/transport error"
                    result = response.structuredContent
                    assert result and result["ok"], f"{name}: {result}"
                    return result["data"]

                info = await call("unreal_project_info", {})
                assert info["project_name"] == "JasperPrismDev" and not info["play_in_editor"]
                assert Path(info["project_file"]).resolve() == (PROJECT / "JasperPrismDev.uproject").resolve()
                report["project_info"] = info
                original = await call("unreal_inspect_material_graph", {"asset_path": ORIGINAL})
                search = await call("unreal_search_assets", {
                    "path": "/JasperPrism/Materials", "name_contains": "M_ForgeMCP_Test",
                    "recursive": True, "limit": 100,
                })
                assert not search["registry_loading"] and not search["truncated"]
                assert not search["assets"], "Existing test assets must be inspected, never overwritten"
                preview = await call("unreal_preview_material", {"recipe": recipe()})
                report["creation_preview"] = preview
                assert not preview["saves_asset"]
                after_preview = await call("unreal_search_assets", {
                    "path": "/JasperPrism/Materials", "name_contains": "M_ForgeMCP_Test", "limit": 100,
                })
                assert not after_preview["assets"], "Preview mutated the Asset Registry"
                assert await call("unreal_inspect_material_graph", {"asset_path": ORIGINAL}) == original
                checkpoint()
                applied = await call("unreal_apply_material", {
                    "preview_id": preview["preview_id"], "confirmation": preview["preview_id"],
                })
                report["creation_apply"] = applied
                checkpoint()
                assert applied["state"] == "completed" and applied["compiled"] and not applied["saved"]
                assert applied["compiler_errors"] == []
                graph = await call("unreal_inspect_material_graph", {"asset_path": TEST_PATH})
                assert graph["domain"] == "PostProcess"
                assert graph["blendable_location"] == "SceneColorAfterTonemapping"
                assert not graph["truncated"] and len(graph["nodes"]) == 4
                ids = {n["id"]: n["node_id"] for n in applied["created_nodes"]}
                nodes = {n["node_id"]: n for n in graph["nodes"]}
                for source, target in (("scene", "subtract"), ("subtract", "multiply"), ("multiply", "add")):
                    pin = next(p for p in nodes[ids[target]]["inputs"] if p["name"] == "A")
                    assert pin["connected"] and pin["from_node"] == ids[source] and pin["output_index"] == 0
                for name, value in (("subtract", 0.5), ("multiply", 1.08), ("add", 0.5)):
                    assert abs(nodes[ids[name]]["parameters"]["const_b"] - value) < 1e-5
                    assert not next(p for p in nodes[ids[name]]["inputs"] if p["name"] == "B")["connected"]
                emissive = next(p for p in graph["property_inputs"] if p["property"] == "MP_EmissiveColor")
                assert emissive["connected"] and emissive["from_node"] == ids["add"] and emissive["output_index"] == 0
                assert nodes[ids["scene"]]["parameters"]["scene_texture_id"] == "PostProcessInput0"
                report["verified_graph"] = graph
                # Prove typed parameter edits; restore the requested final contrast before save.
                for value in (1.09, 1.08):
                    edit = {"asset_path": TEST_PATH, "updates": [{
                        "node_id": ids["multiply"], "type": "Multiply", "parameters": {"const_b": value},
                    }]}
                    p = await call("unreal_preview_material_edits", {"recipe": edit})
                    r = await call("unreal_apply_material_edits", {
                        "preview_id": p["preview_id"], "confirmation": p["preview_id"],
                    })
                    assert r["state"] == "completed" and r["compiled"] and not r["saved"]
                    changed = next(n for n in r["graph"]["nodes"] if n["node_id"] == ids["multiply"])
                    assert abs(changed["parameters"]["const_b"] - value) < 1e-5
                p = await call("unreal_preview_material_compile", {"asset_path": TEST_PATH})
                r = await call("unreal_compile_material", {
                    "preview_id": p["preview_id"], "confirmation": p["preview_id"],
                })
                report["compile"] = r
                checkpoint()
                assert r["state"] == "completed" and r["compiled"] and not r["compiler_errors"]
                p = await call("unreal_preview_material_save", {"asset_path": TEST_PATH})
                checkpoint()
                saved = await call("unreal_save_material", {
                    "preview_id": p["preview_id"], "confirmation": p["preview_id"],
                })
                report["save"] = saved
                checkpoint()
                assert saved["state"] == "saved" and saved["saved"]
                expected = PROJECT / "Plugins/JasperPrism/Content/Materials/M_ForgeMCP_Test.uasset"
                assert Path(saved["filename"]).resolve() == expected.resolve()
                assert expected.is_file() and expected.stat().st_size > 0
                assert await call("unreal_inspect_material_graph", {"asset_path": ORIGINAL}) == original
                assert content_hashes() == hashes, "An existing content asset changed"
                report["existing_content_unchanged"] = True
                report["saved_asset_sha256"] = hashlib.sha256(expected.read_bytes()).hexdigest()
                report["state"] = "verified"
                checkpoint()
    except Exception:
        report["state"] = "stopped_inspection_required"
        checkpoint()
        raise
    print(f"FORGE_UNREAL_MATERIAL_LIVE_PASS: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    asyncio.run(run(parser.parse_args().session_id))
