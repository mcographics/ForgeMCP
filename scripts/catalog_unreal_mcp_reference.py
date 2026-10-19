"""Statically catalog a pinned reference checkout; never import or execute its code."""

import argparse
import ast
import collections
import csv
import json
import re
from pathlib import Path

REPOSITORY = "https://github.com/aadeshrao123/Unreal-MCP"

# Conservative semantic comparisons: a recipe step is not an independent editor command.
SUPPORTED = {
    "get_selected_actors": (
        ["unreal_get_selected_actors"],
        "Read-only bounded Editor selection query returns actor identity, level and truncation metadata.",
    ),
}
RUNTIME_VERIFIED = {"get_selected_actors", "find_actors", "create_blueprint_function"}
PARTIAL = {
    "spawn_actor": "Reviewed actor recipes spawn five allowlisted native actor classes; arbitrary classes/assets are unsupported.",
    "spawn_actor_by_class": "Reviewed actor recipes spawn five allowlisted native actor classes, not arbitrary classes.",
    "set_actor_transform": "Reviewed actor recipes transform exact loaded unattached actor paths in the editor world.",
    "get_actor_properties": "unreal_inspect_actor reads identity, transform and game-hidden state, not generic properties.",
    "find_assets": "unreal_search_assets filters registry paths, exact native classes and name substrings with pagination.",
    "list_assets": "unreal_search_assets lists sorted registry metadata; filtered class matching is exact, not recursive.",
    "get_asset_info": "unreal_inspect_asset returns registry metadata/tags without loading editable UObject properties.",
    "get_data_table_schema": "unreal_inspect_data_table_schema returns bounded row-struct field metadata; nested types are described but not traversed.",
    "get_data_table_rows": "unreal_list_data_table_rows returns sorted DataTable row names with bounded pagination.",
    "get_data_table_row": "unreal_inspect_data_table_row returns bounded simple reflected values for one exact row; nested containers are omitted.",
    "list_data_asset_classes": "unreal_list_data_asset_classes discovers loaded UDataAsset-derived classes with bounded filtering and pagination; abstract classes are optional and unrelated unloaded/plugin types are not enumerated.",
    "list_data_assets": "unreal_list_data_assets queries recursive Asset Registry results derived from UDataAsset, with bounded content paths, class filtering and pagination.",
    "open_asset": "unreal_open_asset opens one exact /Game or /JasperPrism asset in its native editor; asset edits and saving are not performed.",
    "get_selected_assets": "unreal_get_selected_assets returns sorted, bounded Content Browser selection metadata.",
    "sync_browser": "unreal_sync_content_browser requests Content Browser navigation to one exact /Game or /JasperPrism asset; visual focus is not verified.",
    "find_references": "unreal_inspect_asset returns bounded registry package dependencies and referencers.",
    "get_actors_in_level": "unreal_list_actors lists the active editor world with a bounded limit.",
    "find_actors_by_name": "unreal_find_actors performs bounded case-insensitive substring matching on actor names and labels; wildcard/exact/pattern syntax is not implemented.",
    "find_actors": "unreal_find_actors searches by name/label substring, exact class path or exact actor tag with pagination and optional transforms; wildcard/exact name patterns and property predicates remain unsupported.",
    "get_world_info": "unreal_project_info plus unreal_list_actors supplies current world context.",
    "create_blueprint": "Preview/apply creates new /Game Actor Blueprints with native Actor parents only.",
    "add_component_to_blueprint": "Native ActorComponents are available in new Blueprints and reviewed existing normal Blueprint edits.",
    "create_blueprint_variable": "Seven primitive variable types/defaults are available in new Blueprints and reviewed existing normal Blueprint edits.",
    "create_blueprint_function": "New Blueprint recipes and reviewed edits to existing normal Blueprints add typed function signatures and validated entry/return pin connections; existing function signature changes remain unsupported.",
    "add_blueprint_node": "New and existing Blueprint recipes support bounded event, variable, flow-control, reroute and allowlisted native function nodes.",
    "add_event_node": "New recipes support parent override events and custom events.",
    "connect_blueprint_nodes": "Named pins connect during new Blueprint creation and reviewed existing-graph edits, including newly added nodes, within the approved native node set.",
    "set_blueprint_node_property": "Reviewed existing graph edits support node positions and validated input defaults, not generic node properties.",
    "read_blueprint_content": "unreal_inspect_blueprint reads bounded variables/components/graphs/nodes/pins.",
    "analyze_blueprint_graph": "Inspection returns graph connectivity; specialized analysis is absent.",
    "get_blueprint_variable_details": "Inspection reports variables but does not provide full property metadata.",
    "get_blueprint_function_details": "Graph inspection is available; a full function-signature inspector is absent.",
    "compile_blueprint": "Native compilation runs after new Blueprint creation and reviewed existing graph/variable/component edits; standalone compile is absent.",
    "save_asset": "Explicit save applies only to the newly created Blueprint, not arbitrary existing assets.",
    "spawn_blueprint_actor": "An optional placement step spawns the newly created Blueprint only.",
}


def extract(root: Path, commit: str) -> list[dict]:
    """Read registered tool signatures and literal RPC targets through Python AST."""
    tools_dir = root / "unrealmcp/tools"
    imports = ast.parse((tools_dir / "__init__.py").read_text(encoding="utf-8-sig"))
    registered = {
        alias.name
        for node in imports.body
        if isinstance(node, ast.ImportFrom) and node.module == "unrealmcp.tools"
        for alias in node.names
    }
    bridge = (root / "Source/UnrealMCPBridge/Private/EpicUnrealMCPBridge.cpp").read_text(
        encoding="utf-8-sig"
    )
    dispatch = set(re.findall(r'CommandType\s*==\s*TEXT\("([^"]+)"\)', bridge))
    prefixes = re.findall(r'CommandType\.StartsWith\(TEXT\("([^"]+)"\)', bridge)
    records = []
    for path in sorted(tools_dir.glob("*.py")):
        if path.stem not in registered:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8-sig")).body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == "mcp"
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            ):
                continue
            args = node.args.posonlyargs + node.args.args
            defaults = [None] * (len(args) - len(node.args.defaults)) + node.args.defaults
            params = []
            for arg, default in zip(args + node.args.kwonlyargs, defaults + node.args.kw_defaults):
                params.append({
                    "name": arg.arg,
                    "annotation": ast.unparse(arg.annotation) if arg.annotation else None,
                    "required": default is None,
                    "default_expression": ast.unparse(default) if default is not None else None,
                })
            targets = sorted({
                call.args[0].value
                for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id in {"_call", "_tcp_send_raw"}
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
            })
            if node.name == "execute_python":
                targets = ["execute_python"]  # _send forwards through _bridge.py.
            status, ours, note = "missing", [], "No corresponding typed Majestic Forge operation."
            if node.name == "health_check":
                status, ours = "equivalent-purpose", ["forge_status", "forge_list_sessions"]
                note = "Authenticated health/session checks serve the same inspection purpose."
            elif node.name in SUPPORTED:
                ours, note = SUPPORTED[node.name]
                status = "supported"
            elif node.name in PARTIAL:
                status, note = "partial", PARTIAL[node.name]
                ours = ["unreal_preview_blueprint", "unreal_apply_blueprint"]
                if node.name.startswith(("read_", "analyze_", "get_blueprint_")):
                    ours = ["unreal_inspect_blueprint"]
                elif node.name == "get_actors_in_level":
                    ours = ["unreal_list_actors"]
                elif node.name in {"find_actors_by_name", "find_actors"}:
                    ours = ["unreal_find_actors"]
                elif node.name == "get_world_info":
                    ours = ["unreal_project_info", "unreal_list_actors"]
                elif node.name in {"find_assets", "list_assets"}:
                    ours = ["unreal_search_assets"]
                elif node.name in {"get_asset_info", "find_references"}:
                    ours = ["unreal_inspect_asset"]
                elif node.name == "get_selected_assets":
                    ours = ["unreal_get_selected_assets"]
                elif node.name == "get_data_table_schema":
                    ours = ["unreal_inspect_data_table_schema"]
                elif node.name == "get_data_table_rows":
                    ours = ["unreal_list_data_table_rows"]
                elif node.name == "get_data_table_row":
                    ours = ["unreal_inspect_data_table_row"]
                elif node.name == "open_asset":
                    ours = ["unreal_open_asset"]
                elif node.name == "sync_browser":
                    ours = ["unreal_sync_content_browser"]
                elif node.name == "get_actor_properties":
                    ours = ["unreal_inspect_actor"]
                elif node.name == "create_blueprint_function":
                    ours = ["unreal_preview_blueprint", "unreal_apply_blueprint",
                            "unreal_preview_blueprint_edits", "unreal_apply_blueprint_edits"]
                elif node.name in {"spawn_actor", "spawn_actor_by_class", "set_actor_transform"}:
                    ours = ["unreal_preview_actors", "unreal_apply_actors"]
            elif node.name == "execute_python":
                status = "intentionally-excluded"
                note = "Unrestricted editor Python violates the project command allowlist requirements."
            relative = path.relative_to(root).as_posix()
            records.append({
                "name": node.name, "category": path.stem,
                "source": relative, "line": node.lineno,
                "source_url": f"{REPOSITORY}/blob/{commit}/{relative}#L{node.lineno}",
                "parameters": params,
                "return_annotation": ast.unparse(node.returns) if node.returns else None,
                "rpc_targets": targets,
                "cpp_dispatch_mentions": {
                    target: target in dispatch or any(target.startswith(p) for p in prefixes)
                    for target in targets
                },
                "coverage": status, "majestic_tools": ours, "coverage_note": note,
                "runtime_verified": node.name in RUNTIME_VERIFIED,
            })
    counts = collections.Counter(record["name"] for record in records)
    for record in records:
        record["duplicate_registration"] = counts[record["name"]] > 1
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, default=Path("Documentation/Reference_Audits"))
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("commit must be a full SHA")
    records = extract(args.reference_root, args.commit)
    args.output.mkdir(parents=True, exist_ok=True)
    categories = collections.Counter(record["category"] for record in records)
    coverage = collections.Counter(record["coverage"] for record in records)
    bridge_path = "Source/UnrealMCPBridge/Private/EpicUnrealMCPBridge.cpp"
    bridge = (args.reference_root / bridge_path).read_text(encoding="utf-8-sig")
    rpc_targets = {target for record in records for target in record["rpc_targets"]}
    transport_only = []
    for match in re.finditer(r'CommandType\s*==\s*TEXT\("([^"]+)"\)', bridge):
        name = match.group(1)
        if name not in rpc_targets:
            line = bridge[:match.start()].count("\n") + 1
            transport_only.append({"name": name, "line": line,
                                   "source_url": f"{REPOSITORY}/blob/{args.commit}/"
                                   f"{bridge_path}#L{line}", "runtime_verified": False})
    metadata = {
        "repository": REPOSITORY, "commit": args.commit, "audit_date": "2026-10-09",
        "method": "Static AST signatures from imported @mcp.tool modules; C++ dispatch text check.",
        "limitations": "Reference code never executed; dispatch mention is not runtime success. "
        "Annotations/defaults are source expressions, not validated JSON Schema. "
        "Duplicate names retained; effective registration depends on reference MCP SDK behavior.",
        "registrations": len(records), "unique_names": len({r["name"] for r in records}),
        "categories": dict(categories), "coverage": dict(coverage), "commands": records,
        "transport_only_dispatch_literals": transport_only,
        "rpc_targets_without_top_level_dispatch": sorted({
            target for record in records
            for target, mentioned in record["cpp_dispatch_mentions"].items() if not mentioned
        }),
    }
    (args.output / "Unreal_MCP_Commands.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output / "Unreal_MCP_Commands.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["category", "command", "signature", "rpc_targets", "coverage", "note",
                         "duplicate_registration", "source_url"])
        for row in records:
            signature = ", ".join(
                p["name"] + (": " + p["annotation"] if p["annotation"] else "")
                + (" = " + p["default_expression"] if not p["required"] else "")
                for p in row["parameters"]
            )
            writer.writerow([row["category"], row["name"], signature,
                             ", ".join(row["rpc_targets"]), row["coverage"], row["coverage_note"],
                             row["duplicate_registration"], row["source_url"]])
    lines = ["# Unreal-MCP public command comparison", "",
             f"Audited 2026-10-09 against [{args.commit}]({REPOSITORY}/tree/{args.commit}).", "",
             "ForgeMCP does not provide feature parity with this public repository. "
             "Its 22 MCP interfaces include Blender and API retrieval; bundled Unreal recipes "
             "are not equivalent to standalone editor commands.", "",
             f"Static source contains **{len(records)} decorated registrations**, "
             f"**{metadata['unique_names']} distinct names**, in **{len(categories)} imported modules**. "
             "The README advertises 288 community commands; its 900+ figure describes a separate "
             "commercial product whose private commands are not included in this audit. "
             "Both level.py and editor_commands.py register spawn_actor with different signatures "
             "and RPC targets. Both definitions are retained, without assuming which wins at runtime.",
             "", "## Coverage by source module", "",
             "| Module | Registrations | Equivalent purpose | Supported | Partial | Missing | Excluded |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for category, count in categories.items():
        group = collections.Counter(r["coverage"] for r in records if r["category"] == category)
        lines.append(f"| {category} | {count} | {group['equivalent-purpose']} | {group['supported']} "
                     f"| {group['partial']} | {group['missing']} | {group['intentionally-excluded']} |")
    lines += ["", "Coverage classifications compare purpose and scope, not wire compatibility. "
              "Partial means a bounded subset exists, usually only during creation of a new Actor "
              "Blueprint. Missing does not mean approved for automatic implementation. "
              "Unrestricted execute_python remains intentionally excluded.", "",
              "## Complete source-declared catalog", "",
              "Every registration is listed below. JSON and CSV companions retain all parameter "
              "names, annotations, required/default expressions, literal RPC targets, duplicate "
              "flags, and pinned source links. The reference was inspected statically and never "
              "installed or run. C++ dispatcher mentions do not establish successful execution.", "",
              "| Module | Command / source | RPC | Forge coverage | Explanation |",
              "|---|---|---|---|---|"]
    for row in records:
        lines.append(f"| {row['category']} | [{row['name']}]({row['source_url']}) "
                     f"{'(duplicate)' if row['duplicate_registration'] else ''}| "
                     f"{', '.join(row['rpc_targets']) or 'indirect/unresolved'} | "
                     f"{row['coverage']} | {row['coverage_note']} |")
    lines += ["", "## Additional transport dispatcher literals", "",
              "These dispatcher names have no extracted public MCP wrapper in this snapshot. "
              "They are recorded separately from MCP tool counts; no runtime support is assumed.", ""]
    lines.extend(f"- [{row['name']}]({row['source_url']})" for row in transport_only)
    lines += ["", "## Original implementation priorities", "",
              "1. Expand bounded asset/class/instance inspection and structured diagnostics.",
              "2. Add previews and native transactions for existing Blueprint graphs, variables, "
              "components and function signatures; expand the supported node families deliberately.",
              "3. Add reviewed actor, asset import/duplicate/save and material graph recipes.",
              "4. Implement Enhanced Input, UMG, data tables/assets and Mass configuration adapters.",
              "5. Add specialized Niagara and StateTree editors with compile diagnostics and rollback.",
              "6. Add profiling and screenshot workflows with explicit output paths and bounds.", "",
              "Deletion, rename/overwrite and saving existing work require task authorization and "
              "suitable preview/transaction/backup behavior. Custom HLSL and other code-bearing inputs "
              "need separate policy and validation; their presence in the reference does not authorize "
              "unrestricted execution here. Preserve loopback authentication, explicit session identity, "
              "main-thread native APIs, bounded requests and one-use preview/apply confirmations.", "",
              "The repository is Unreal-only. Forge's Blender adapter, exact-version local API "
              "retrieval and multi-session security are separate capabilities, not substitutions for "
              "missing Unreal operations. GAS, World Partition, PCG, animation/retargeting and other "
              "Forge roadmap requirements remain tracked separately; no private commercial feature "
              "list is treated as implemented public commands.", "",
              "## Reference source caveat", "",
              "search_statetree_nodes has a Python wrapper and a StateTree handler, but the "
              "top-level dispatcher does not include search_statetree in its accepted prefixes. "
              "It remains in the source-declared catalog; successful routing is unverified. "
              "The duplicate spawn_actor registrations also require runtime examination of the "
              "reference SDK to establish the effective exposed signature. Neither issue was "
              "tested against a running reference plugin.", "",
              "## Reproduce", "", "Use a read-only reference snapshot at the pinned commit:", "",
              "```powershell", ".venv\\Scripts\\python.exe scripts/catalog_unreal_mcp_reference.py `",
              "  --reference-root Saved/ReferenceAudits/Unreal-MCP `",
              f"  --commit {args.commit}", "```", "",
              "Only command/interface facts are extracted into documentation. Third-party source "
              "remains in ignored Saved/ReferenceAudits and is not a Forge dependency. No scenes "
              "were changed, editor sessions probed, or plugin binaries replaced for this audit."]
    (args.output / "Unreal_MCP_Comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items() if k != "commands"}, indent=2))


if __name__ == "__main__":
    main()
