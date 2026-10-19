# Native Landscape automation — UE 5.6.1

This extension uses the existing authenticated loopback bridge and native editor
thread dispatcher. It adds five typed MCP tools without replacing the foundation
inspection tools or introducing an execution/scripting endpoint.

## Safety and current scope

Terrain mutations are deliberately limited to new disposable maps beneath
`/Game/ForgeMCPTests/Landscape/`. Creation requires a separate untitled editor
world and an absent destination. It never opens or replaces the city map. The
build host is `Saved/LandscapeDevelopment/Host/ForgeMCPDev.uproject`; the live
acceptance host is `Saved/LandscapeDevelopment/LiveHost/ForgeMCPDev.uproject`. Its
plugin is a source copy, so validation does not replace the live engine plugin DLL.

The current implementation supports one `ForgeTerrain` Landscape Edit Layer,
1–2 components on each axis, one subsection per component, and 7, 15, 31 or 63
quads per subsection. The maximum heightfield is 127 × 127 vertices. It rejects
partitioned/streaming worlds, rotated Landscapes, hidden/locked layers, more than
one Edit Layer, and PIE/simulation. Existing production Landscapes, streaming
proxy creation, unloaded cells, external actor package saving, weight painting,
Landscape splines and nine-kilometre terrain are not supported by this milestone.
World Partition inspection is supported; World Partition mutation acceptance is
still outstanding.

`ForgeTerrain` is a real native Edit Layer. Editing that layer preserves the Edit
Layer workflow, but successive edits change its existing samples. This is not an
independent new layer per stroke. Pre-edit raw heights and per-stage editor
transactions provide additional recovery. Automated backup restoration is not
implemented. Editing the merged heightfield across arbitrary layer stacks is not
implemented.

## Architecture and native APIs

The source-authoritative plugin is currently engine-wide:
`G:/Program Files/EpicGames/UE_5.6/Engine/Plugins/Marketplace/Forge/Source/MajesticForge`.
The native implementation is `Private/ForgeLandscape.{h,cpp}`, registered in
`MajesticForgeModule.cpp`, with a `Landscape` module dependency in the Build.cs.
`server/core/landscape.py` owns the public Pydantic request, and `server/main.py`
exposes the tools. `server/core/connections.py` retains the command allowlist.

UE 5.6.1 installed headers and the engine's own Landscape creation code are the
version-specific authority. APIs used:

- `ALandscape::Import` creates a bounded Landscape with native components and
  initial height samples; `bCanHaveLayersContent` enables Edit Layers.
- `ULandscapeEditLayerBase` provides the 5.6 layer GUID, name, lock and visibility
  APIs. The deprecated FLandscapeLayer fields are not used.
- `ULandscapeInfo::GetLandscapeExtent` validates loaded dimensions.
- `FLandscapeEditDataInterface(Info, LayerGuid)` reads/writes an explicit layer;
  `SetHeightData` and `Flush` handle native height writes. Read-only inspection
  copies texture source mip data and uses `FLandscapeComponentDataInterfaceBase`
  for vertex-to-texel mapping; the editing interface read helper is avoided
  because it calls `Texture->Modify()` even on reads.
- `ALandscape::RequestLayersContentUpdate` schedules native layer recomposition.
  `IsUpToDate` gates explicit saves; `ForceUpdateLayersContent` flushes pending work
  without scheduling a fresh full regeneration.
- `FScopedTransaction` scopes each row batch; the existing game-thread ticker
  advances jobs. `RedrawLevelEditingViewports` requests visible redraws.
- `FEditorFileUtils::SaveLevel` saves only the isolated persistent map;
  `UEditorLoadingAndSavingUtils::LoadMap` reloads the same saved test map.

Epic's [Landscape edit interface documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Landscape/FLandscapeEditDataInterface?application_version=5.6)
provides API context. Locally installed UE 5.6.1 headers take precedence over web
pages describing newer engine versions.

## Typed operations

| MCP tool | Native command | Behavior |
| --- | --- | --- |
| `unreal_inspect_landscape` | `landscape_info` | Lists loaded Landscape actors or inspects one exact actor; reports topology, Edit Layers, layer height ranges/checksums, world partition and dirty state. |
| `unreal_preview_landscape` | `landscape_preview` | Validates and prepares one recipe without changing Unreal objects. |
| `unreal_apply_landscape` | `landscape_apply` | Consumes an unexpired one-use preview after exact confirmation and state recheck. |
| `unreal_landscape_job_status` | `landscape_job_status` | Reports job state, applied rows, progress, measured stage cost and backup path. |
| `unreal_cancel_landscape_job` | `landscape_job_cancel` | Stops future batches after exact job ID confirmation; already applied rows remain. |

Recipes select `create`, `raise`, `lower`, `flatten`, `smooth`, `generate`,
`apply_heightmap`, `coastline`, `frame`, `save` or `reload`. Every operation except create
requires an inspected exact `actor_path`. A new preview is required for each action.

Regions are inclusive Landscape vertex coordinates `[x1,y1,x2,y2]`, not world
coordinates. Height arguments use actor-local centimetres; native samples are
`round(height_cm * 128 / z_scale + 32768)`. Out-of-range requests are rejected
rather than clipped. Positive Z scale is required. Inspection reports layer-local
height ranges, not composite world elevation.

Raise/lower use the absolute height magnitude and a radial cosine falloff within
the rectangle. Flatten blends toward a constant `height_cm` with `strength` in
0–1. Smooth uses a 3 × 3 average from the immutable pre-edit heightfield, including
neighbors outside the selected rectangle. Only the selected rectangle is written.
`generate` computes deterministic sine terrain with `wavelength_vertices`;
`coastline` creates an X-axis ramp from negative to positive `height_cm`. It is a
terrain primitive, not hydraulic erosion, water generation or realistic coastal
simulation. `apply_heightmap` takes at most 256 explicit finite centimetre samples
in row-major order, exactly matching the selected region. Image/file heightmap
import and exporting heightmap assets are not implemented.

`frame` uses native editor viewport APIs to position a perspective camera from
the heightfield bounds and selects Unlit mode for geometry review. Creation also
frames the new test terrain. No mouse or simulated input is used.

## Progressive execution and recovery

A height edit computes a bounded target field during preview. Apply writes and
read-verifies a raw uint16 pre-edit height backup plus metadata under the host's
`Saved/ForgeLandscape/<id>/`. It returns a job ID without running all batches in
one request. Between editor ticks, the job writes 1–8 selected rows (default 4),
requests layer recomposition and redraw, then waits 0.1–2 seconds (default 0.3)
before the next stage. Native import, a row write, texture flush, save and reload
remain synchronous bounded engine calls; there is no hard real-time guarantee.
Actual stage timing is reported as `max_stage_ms`.

Before each stage, the implementation checks world identity, PIE/simulation,
actor transform, layer identity/visibility/lock, dimensions, and expected current
layer heights. It reads back each written stage and requires exact equality.
Changes detected between stages stop the job with `interrupted_partial`.
Readback failure returns `validation_failed_partial`. A successful staged edit
returns `completed` with `height_readback_validated:true`; it remains unsaved.

Cancellation returns `cancelled` or `cancelled_partial`, preserving completed
rows and the retained backup. It does not claim atomic rollback. Status calls do
not advance the job. Jobs are session-local, capped at 64 retained records;
previews expire after five minutes and are capped at 32. Process restart loses
in-memory job state but retains saved backups. Cross-restart job reconciliation
is not implemented.

Save is a separate preview/apply action and retains a map backup before calling
the native save API. Save waits for callers to observe `layers_up_to_date:true`
and rejects pending native layer updates; it also checks the saved package is
clean before reporting success. Reload requires a clean test map and verifies the same
Landscape GUID, dimensions, layer GUID and exact height samples after native
reload. This does not establish World Partition or production-map persistence.

## Acceptance

`python -m pytest -q` exercises public request rejection and the existing suite.
`scripts/verify_landscape_mcp.py` uses a fresh real MCP stdio subprocess and an
explicit isolated host session, verifies identity before mutation, then exercises
creation, hill, valley, flatten, smooth, save/reload, deterministic generation,
coastline, a bounded explicit heightmap, range rejection, one-use previews and
cancellation. It records intermediate row counts and native height checksums in
`Saved/LandscapeDevelopment/acceptance.json` and finishes with a saved/reloaded
hill-and-valley example. Do not replay a partial run without inspecting its host.

Python tests, native compilation, live MCP probes, height readback, persistence,
viewport appearance and performance are separate evidence gates. See the dated
acceptance report for actual results; this design document does not assert that
all gates passed.

Live test results: [October 16 acceptance](Landscape_Acceptance_20261016.md).
