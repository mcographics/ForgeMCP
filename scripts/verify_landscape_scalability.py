"""Scale and World Partition acceptance in a verified disposable UE host."""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run(args):
    repository = Path(__file__).resolve().parents[1]
    project_file = args.project_file.resolve()
    map_name = args.map_name
    suffix = "-restart" if args.verify_existing else ""
    output = repository / "Saved" / "LandscapeDevelopment" / f"phase6-{map_name}{suffix}.json"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite acceptance report: {output}")
    report = {
        "project_file": str(project_file),
        "session_id": args.session_id,
        "topology": {
            "components_x": args.components_x,
            "components_y": args.components_y,
            "quads_per_section": args.quads_per_section,
            "sections_per_component": args.sections_per_component,
            "world_partition": args.world_partition,
            "partition_grid_size_components": args.partition_grid_size_components,
        },
        "steps": [],
    }

    def checkpoint():
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.main"],
        cwd=str(repository),
        env={**os.environ, "FORGE_PROJECT_ROOT": str(repository)},
    )
    try:
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()

                async def call(name, payload, ok=True):
                    started = time.perf_counter()
                    response = await client.call_tool(name, {"session_id": args.session_id, **payload})
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    value = response.structuredContent
                    assert not response.isError and value, str(response)
                    assert value["ok"] is ok, str(response)
                    return (value["data"] if ok else value["error"]), elapsed_ms, response

                identity, _, _ = await call("unreal_project_info", {})
                assert Path(identity["project_file"]).resolve() == project_file, identity
                assert not identity["play_in_editor"], identity
                level = identity["level"]
                assert (level.startswith("/Temp/Untitled")
                        or level == "/Engine/Maps/Entry.Entry"
                        or level.startswith("/Game/ForgeMCPTests/Landscape/")), identity
                report["identity_before"] = identity
                initial_world, _, _ = await call("unreal_inspect_landscape", {})
                report["initial_landscape_world_state"] = initial_world
                checkpoint()

                if args.verify_existing:
                    prior_path = repository / "Saved" / "LandscapeDevelopment" / f"phase6-{map_name}.json"
                    prior = json.loads(prior_path.read_text(encoding="utf-8"))
                    assert prior["state"] in {"passed", "partial"}, prior
                    expected_level = f"/Game/ForgeMCPTests/Landscape/{map_name}"
                    assert level.startswith(expected_level), identity
                    current, elapsed, _ = await call("unreal_inspect_landscape", {})
                    expected = prior["persistence"]["final_inspection"]
                    restored = next((item for item in current["landscapes"]
                                     if item["guid"] == expected["guid"]), None)
                    assert restored is not None, current
                    assert restored["layers"][0]["height_sha_md5"] == expected["layers"][0]["height_sha_md5"], restored
                    assert restored["world_partition"] == expected["world_partition"], restored
                    assert (restored["landscape_proxy_descriptor_count"]
                            == restored["loaded_landscape_proxy_count"]
                            + restored["unloaded_landscape_proxy_count"]), restored
                    prior_external = prior["persistence"]["external_actor_files"]
                    assert all(Path(file).exists() for file in prior_external), prior_external
                    report["restart_verification"] = {
                        "level": level,
                        "prior_acceptance_state": prior["state"],
                        "prior_limitations": prior.get("limitations", []),
                        "expected_guid": expected["guid"],
                        "expected_height_sha_md5": expected["layers"][0]["height_sha_md5"],
                        "restored_inspection": restored,
                        "inspection_ms": elapsed,
                        "external_actor_files_persisted": prior_external,
                    }
                    report["state"] = "passed"
                    checkpoint()
                    print(output)
                    return

                async def capture(name):
                    response = await client.call_tool("unreal_capture_screenshot", {"session_id": args.session_id})
                    for block in response.content:
                        if block.type == "image":
                            image_path = repository / "Saved" / "LandscapeDevelopment" / f"{map_name}-{name}.jpg"
                            image_path.write_bytes(base64.b64decode(block.data, validate=True))
                            return str(image_path)
                    return None

                create_request = {
                    "action": "create",
                    "map_path": f"/Game/ForgeMCPTests/Landscape/{map_name}",
                    "components_x": args.components_x,
                    "components_y": args.components_y,
                    "quads_per_section": args.quads_per_section,
                    "sections_per_component": args.sections_per_component,
                    "xy_scale_cm": args.xy_scale_cm,
                    "z_scale": 100,
                    "world_partition": args.world_partition,
                    "partition_grid_size_components": args.partition_grid_size_components,
                }
                preview, preview_ms, _ = await call("unreal_preview_landscape", {"request": create_request})
                created, create_ms, _ = await call("unreal_apply_landscape", {
                    "preview_id": preview["preview_id"],
                    "confirmation": preview["preview_id"],
                })
                assert created["state"] == "completed" and created["saved"], created
                assert created["height_readback_validated"], created
                landscape = created["landscape"]
                actor_path = landscape["actor_path"]
                report["steps"].append({
                    "create_preview_ms": preview_ms,
                    "create_apply_ms": create_ms,
                    "preview": preview,
                    "result": created,
                    "viewport": await capture("created"),
                })
                checkpoint()

                component_quads = args.quads_per_section * args.sections_per_component
                width = args.components_x * component_quads + 1
                height = args.components_y * component_quads + 1

                async def inspect():
                    value, elapsed, _ = await call("unreal_inspect_landscape", {"actor_path": actor_path})
                    assert value["total_count"] == 1, value
                    item = value["landscapes"][0]
                    item["inspection_ms"] = elapsed
                    return item

                async def inspect_all():
                    value, elapsed, _ = await call("unreal_inspect_landscape", {})
                    value["inspection_ms"] = elapsed
                    return value

                async def wait_for_loader_state(loader_id, target_state, timeout=35):
                    deadline = time.monotonic() + timeout
                    status = None
                    while time.monotonic() < deadline:
                        status, _, _ = await call(
                            "unreal_landscape_job_status", {"job_id": loader_id})
                        if status["state"] == target_state or status["state"] in {
                            "transition_failed", "no_region_proxies",
                        }:
                            return status
                        await asyncio.sleep(0.1)
                    raise TimeoutError(
                        f"World Partition loader {loader_id} did not reach {target_state}: {status}")

                if args.create_only:
                    final_world = await inspect_all()
                    final = next((item for item in final_world["landscapes"]
                                  if item["guid"] == landscape["guid"]), None)
                    assert final is not None, final_world
                    map_file = project_file.parent / "Content" / "ForgeMCPTests" / "Landscape" / f"{map_name}.umap"
                    assert map_file.exists(), map_file
                    report["persistence"] = {
                        "map_file_exists": True,
                        "final_inspection": final,
                        "external_actor_files": [],
                    }
                    report["state"] = "passed"
                    checkpoint()
                    print(output)
                    return

                async def load_region(region):
                    request = {"action": "load_region", "actor_path": actor_path,
                               "region": region}
                    preview, preview_elapsed, _ = await call(
                        "unreal_preview_landscape", {"request": request})
                    accepted, apply_elapsed, _ = await call("unreal_apply_landscape", {
                        "preview_id": preview["preview_id"],
                        "confirmation": preview["preview_id"],
                    })
                    loader_id = accepted["loader_id"]
                    status = accepted if accepted["state"] == "loaded" else await wait_for_loader_state(
                        loader_id, "loaded")
                    assert status["state"] == "loaded", status
                    return {"preview": preview, "accepted": accepted, "status": status,
                            "preview_ms": preview_elapsed, "apply_ms": apply_elapsed}

                if args.streaming_only:
                    assert args.world_partition, "--streaming-only requires --world-partition"
                    before_loader = await inspect_all()
                    cell_edge = component_quads * args.partition_grid_size_components
                    cell = [0, 0, min(width - 1, cell_edge), min(height - 1, cell_edge)]
                    loaded_probe = await load_region(cell)
                    await asyncio.sleep(1)
                    after_load = await inspect_all()
                    loader_id = loaded_probe["accepted"]["loader_id"]
                    unload_request = {"action": "unload_region", "actor_path": actor_path,
                                      "partition_loader_id": loader_id}
                    unload_preview, unload_preview_ms, _ = await call(
                        "unreal_preview_landscape", {"request": unload_request})
                    unloaded, unload_ms, _ = await call("unreal_apply_landscape", {
                        "preview_id": unload_preview["preview_id"],
                        "confirmation": unload_preview["preview_id"],
                    })
                    unload_status = (unloaded if unloaded["state"] == "unloaded" else
                                     await wait_for_loader_state(loader_id, "unloaded"))
                    after_unload = await inspect_all()
                    loaded_before = before_loader.get("loaded_landscape_proxy_count", 0)
                    loaded_after = after_load.get("loaded_landscape_proxy_count", 0)
                    loaded_released = after_unload.get("loaded_landscape_proxy_count", 0)
                    unloaded_after = after_unload.get("unloaded_landscape_proxy_count", 0)
                    transition_observed = (
                        loaded_after > loaded_before
                        and unload_status.get("state") == "unloaded"
                        and unload_status.get("region_proxy_descriptor_count", 0) > 0
                        and unload_status.get("region_loaded_proxy_count", 0) == 0
                        and loaded_released < loaded_after
                        and unloaded_after > before_loader.get("unloaded_landscape_proxy_count", 0)
                    )
                    split_x = width // 2
                    split_y = height // 2
                    full_region = []
                    for region in (
                        [0, 0, split_x, split_y],
                        [split_x, 0, width - 1, split_y],
                        [0, split_y, split_x, height - 1],
                        [split_x, split_y, width - 1, height - 1],
                    ):
                        full_region.append(await load_region(region))
                    await asyncio.sleep(1)
                    final_world = await inspect_all()
                    final = next((item for item in final_world["landscapes"]
                                  if item["guid"] == landscape["guid"]), None)
                    assert final is not None, final_world
                    map_file = project_file.parent / "Content" / "ForgeMCPTests" / "Landscape" / f"{map_name}.umap"
                    external_root = project_file.parent / "Content" / "__ExternalActors__" / "ForgeMCPTests" / "Landscape" / map_name
                    external_files = sorted(str(path) for path in external_root.rglob("*.uasset")) if external_root.exists() else []
                    assert map_file.exists(), map_file
                    assert external_files, external_root
                    report["world_partition_streaming_probe"] = {
                        "before": before_loader,
                        "cell_region": cell,
                        "load": loaded_probe,
                        "after_load": after_load,
                        "unload_preview": unload_preview,
                        "unload_result": unloaded,
                        "unload_status": unload_status,
                        "unload_preview_ms": unload_preview_ms,
                        "unload_apply_ms": unload_ms,
                        "after_unload": after_unload,
                        "loaded_to_unloaded_transition_observed": transition_observed,
                        "full_region_reload": full_region,
                    }
                    report["persistence"] = {
                        "map_file_exists": True,
                        "external_actor_root": str(external_root),
                        "external_actor_files": external_files,
                        "final_inspection": final,
                        "final_viewport": await capture("final"),
                    }
                    report["limitations"] = [] if transition_observed else [
                        "The native loader request completed, but releasing it did not produce an observed loaded-to-unloaded proxy transition in the Editor world."
                    ]
                    report["state"] = "passed" if transition_observed else "partial"
                    checkpoint()
                    print(output)
                    return

                async def edit(action, region, *, height_cm=250, strength=0.8, rows=2):
                    nonlocal actor_path
                    request = {
                        "action": action,
                        "actor_path": actor_path,
                        "region": region,
                        "height_cm": height_cm,
                        "strength": strength,
                        "rows_per_stage": rows,
                        "stage_interval_seconds": 0.1,
                    }
                    before = await inspect()
                    edit_preview, preview_elapsed, _ = await call("unreal_preview_landscape", {"request": request})
                    start = time.perf_counter()
                    accepted, apply_elapsed, _ = await call("unreal_apply_landscape", {
                        "preview_id": edit_preview["preview_id"],
                        "confirmation": edit_preview["preview_id"],
                    })
                    progress = []
                    intermediate = None
                    if accepted["state"] == "running":
                        for _ in range(2000):
                            status, _, _ = await call("unreal_landscape_job_status", {"job_id": accepted["job_id"]})
                            if not progress or status["rows_applied"] != progress[-1]["rows_applied"]:
                                progress.append(status)
                                if intermediate is None and status["progress"] >= 0.5 and status["state"] == "running":
                                    intermediate = await capture(f"{action}-intermediate")
                            if status["state"] != "running":
                                break
                            await asyncio.sleep(0.05)
                        else:
                            raise TimeoutError(f"{action} terrain job did not finish")
                    else:
                        status = accepted
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    assert (status["state"] == "completed" and status["height_readback_validated"]
                            and status["collision_height_validated"]), status
                    after = await inspect()
                    assert status["validated_after_height_md5"] == edit_preview["after_height_md5"], status
                    record = {
                        "action": action,
                        "region": region,
                        "preview_ms": preview_elapsed,
                        "apply_call_ms": apply_elapsed,
                        "job_wall_ms": elapsed_ms,
                        "preview": edit_preview,
                        "status": status,
                        "collision_component_count": after["collision_component_count"],
                        "registered_collision_component_count": after["registered_collision_component_count"],
                        "progress": progress,
                        "intermediate_viewport": intermediate,
                        "before": before,
                        "after": after,
                    }
                    report["steps"].append(record)
                    checkpoint()
                    return after, status

                crossing = [max(0, component_quads - 2), max(0, component_quads - 2),
                            min(width - 1, component_quads + 2), min(height - 1, component_quads + 2)]
                lowered = [max(0, 2 * component_quads - 2), max(0, 2 * component_quads - 2),
                           min(width - 1, 2 * component_quads + 2), min(height - 1, 2 * component_quads + 2)]
                raised, _ = await edit("raise", crossing, height_cm=400, strength=1, rows=2)
                assert raised["layers"][0]["max_local_cm"] >= 399, raised
                lowered_state, _ = await edit("lower", lowered, height_cm=350, strength=1, rows=2)
                assert lowered_state["layers"][0]["min_local_cm"] <= -349, lowered_state
                await edit("flatten", crossing, height_cm=125, strength=1, rows=2)
                await edit("smooth", crossing, strength=0.75, rows=1)

                if args.world_partition:
                    grid_edge = args.partition_grid_size_components * component_quads
                    boundary = [max(0, grid_edge - 2), max(0, grid_edge - 2),
                                min(width - 1, grid_edge + 2), min(height - 1, grid_edge + 2)]
                    before_loader = await inspect_all()
                    loaded_probe = await load_region([0, 0, width - 1, height - 1])
                    await asyncio.sleep(0.5)
                    after_load = await inspect_all()
                    loader_id = loaded_probe["accepted"]["loader_id"]
                    unload_request = {"action": "unload_region", "actor_path": actor_path,
                                      "partition_loader_id": loader_id}
                    unload_preview, unload_preview_ms, _ = await call(
                        "unreal_preview_landscape", {"request": unload_request})
                    unloaded, unload_ms, _ = await call("unreal_apply_landscape", {
                        "preview_id": unload_preview["preview_id"],
                        "confirmation": unload_preview["preview_id"],
                    })
                    unload_status = (unloaded if unloaded["state"] == "unloaded" else
                                     await wait_for_loader_state(loader_id, "unloaded"))
                    after_unload = await inspect_all()
                    loaded_count = after_load.get("loaded_landscape_proxy_count", 0)
                    unloaded_count = after_unload.get("unloaded_landscape_proxy_count", 0)
                    transition_observed = (
                        unload_status.get("state") == "unloaded"
                        and unload_status.get("region_proxy_descriptor_count", 0) > 0
                        and unload_status.get("region_loaded_proxy_count", 0) == 0
                        and after_unload.get("loaded_landscape_proxy_count", 0) < loaded_count
                        and unloaded_count > before_loader.get("unloaded_landscape_proxy_count", 0)
                    )
                    report["world_partition_streaming_probe"] = {
                        "before": before_loader,
                        "load": loaded_probe,
                        "after_load": after_load,
                        "unload_preview": unload_preview,
                        "unload_result": unloaded,
                        "unload_status": unload_status,
                        "unload_preview_ms": unload_preview_ms,
                        "unload_apply_ms": unload_ms,
                        "after_unload": after_unload,
                        "loaded_to_unloaded_transition_observed": transition_observed,
                    }
                    checkpoint()
                    # Re-establish a full region load before crossing-component edits and save.
                    loaded_again = await load_region([0, 0, width - 1, height - 1])
                    report["world_partition_streaming_probe"]["reload_region"] = loaded_again
                    checkpoint()
                    await edit("coastline", [0, 0, width - 1, height - 1], height_cm=300, rows=8)
                    # The component/grid edge probe must remain exactly addressable after a full-region edit.
                    await edit("raise", boundary, height_cm=75, strength=0.8, rows=2)
                else:
                    await edit("coastline", [0, 0, width - 1, height - 1], height_cm=300, rows=8)

                before_cancel = await inspect()
                cancel_preview, _, _ = await call("unreal_preview_landscape", {"request": {
                    "action": "raise", "actor_path": actor_path,
                    "region": [0, 0, min(width - 1, 15), min(height - 1, 15)],
                    "height_cm": 25, "strength": 1, "rows_per_stage": 1,
                    "stage_interval_seconds": 0.5,
                }})
                cancel_apply, _, _ = await call("unreal_apply_landscape", {
                    "preview_id": cancel_preview["preview_id"],
                    "confirmation": cancel_preview["preview_id"],
                })
                for _ in range(200):
                    cancel_state, _, _ = await call("unreal_landscape_job_status", {"job_id": cancel_apply["job_id"]})
                    if cancel_state["rows_applied"] >= 3:
                        break
                    await asyncio.sleep(0.05)
                cancelled, _, _ = await call("unreal_cancel_landscape_job", {
                    "job_id": cancel_apply["job_id"], "confirmation": cancel_apply["job_id"],
                })
                assert cancelled["state"] == "cancelled_partial", cancelled
                await asyncio.sleep(0.75)
                stable, _, _ = await call("unreal_landscape_job_status", {"job_id": cancel_apply["job_id"]})
                assert stable["rows_applied"] == cancelled["rows_applied"], stable
                after_cancel = await inspect()
                assert after_cancel["layers"][0]["height_sha_md5"] != before_cancel["layers"][0]["height_sha_md5"]
                report["cancellation"] = {"cancelled": cancelled, "stable": stable, "after": after_cancel}
                checkpoint()

                for _ in range(120):
                    current = await inspect()
                    if current["layers_up_to_date"]:
                        break
                    await asyncio.sleep(0.25)
                save_preview, save_preview_ms, _ = await call("unreal_preview_landscape", {"request": {"action": "save", "actor_path": actor_path}})
                saved, save_ms, _ = await call("unreal_apply_landscape", {
                    "preview_id": save_preview["preview_id"], "confirmation": save_preview["preview_id"],
                })
                assert saved["saved"] and saved["state"] == "completed", saved
                reload_preview, reload_preview_ms, _ = await call("unreal_preview_landscape", {"request": {"action": "reload", "actor_path": actor_path}})
                reloaded, reload_ms, _ = await call("unreal_apply_landscape", {
                    "preview_id": reload_preview["preview_id"], "confirmation": reload_preview["preview_id"],
                })
                assert reloaded["persistence_validated"], reloaded
                actor_path = reloaded["landscape"]["actor_path"]
                final = await inspect()
                map_file = project_file.parent / "Content" / "ForgeMCPTests" / "Landscape" / f"{map_name}.umap"
                external_root = project_file.parent / "Content" / "__ExternalActors__" / "ForgeMCPTests" / "Landscape" / map_name
                external_files = sorted(str(path) for path in external_root.rglob("*.uasset")) if external_root.exists() else []
                report["persistence"] = {
                    "saved": saved,
                    "reloaded": reloaded,
                    "save_preview_ms": save_preview_ms,
                    "save_apply_ms": save_ms,
                    "reload_preview_ms": reload_preview_ms,
                    "reload_apply_ms": reload_ms,
                    "map_file_exists": map_file.exists(),
                    "external_actor_root": str(external_root),
                    "external_actor_files": external_files,
                    "final_inspection": final,
                    "final_viewport": await capture("final"),
                }
                assert map_file.exists(), map_file
                if args.world_partition:
                    assert final["world_partition"] and final["world_partition_streaming"], final
                    assert final["streaming_proxy_count"] > 0, final
                    assert external_files, report["persistence"]
                    assert (final["landscape_proxy_descriptor_count"]
                            == final["loaded_landscape_proxy_count"]
                            + final["unloaded_landscape_proxy_count"]), final
                report["state"] = "passed"
                checkpoint()
    except BaseException as exc:
        report["state"] = "failed"
        report["error"] = repr(exc)
        checkpoint()
        raise
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--project-file", type=Path, required=True)
    parser.add_argument("--map-name", required=True)
    parser.add_argument("--components-x", type=int, default=4)
    parser.add_argument("--components-y", type=int, default=4)
    parser.add_argument("--quads-per-section", type=int, choices=(7, 15, 31, 63, 127, 255), default=63)
    parser.add_argument("--sections-per-component", type=int, choices=(1, 2), default=1)
    parser.add_argument("--xy-scale-cm", type=float, default=100)
    parser.add_argument("--world-partition", action="store_true")
    parser.add_argument("--partition-grid-size-components", type=int, default=2)
    parser.add_argument("--create-only", action="store_true",
                        help="Create, inspect and save one Landscape without terrain edits")
    parser.add_argument("--streaming-only", action="store_true",
                        help="Create a World Partition Landscape and probe native region load/unload without terrain edits")
    parser.add_argument("--verify-existing", action="store_true",
                        help="After an editor restart, verify an existing Phase 6 map without modifying it")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
