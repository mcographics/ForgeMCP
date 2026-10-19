# Reference city: nine regions

The user's numbered image is interpreted as a three-by-three grid. The active
target is the user's replacement `/Game/Levels/NewMap.NewMap` in ForgeMCPDev.
The deleted troubleshooting maps are preserved only as recovery copies and are
not restored by this workflow.

## Geometry and ownership

| Region | District |
| --- | --- |
| 1 | Northwest islands and park |
| 2 | Northern districts |
| 3 | Northeast district |
| 4 | Western mainland |
| 5 | Central island and tower district |
| 6 | Eastern crossings |
| 7 | Southwest interchange |
| 8 | Southern street grid |
| 9 | Southeast waterfront |

The current source contains 7,200 building masses and 80 spatial chunks, with a
512-metre target chunk size. Region boundaries follow the image's numbered grid.
Land triangles are clipped to chunk bounds. Buildings are assigned once by their
centres; their footprints can extend slightly beyond a chunk boundary. Roads are
segmented and major road corridors exclude building footprints. Bridges are split
between chunks rather than held by one city-wide heavy actor.

Scale is provisionally three metres per image pixel: the full area is 3.762 km
square and each numbered region is 1.254 km square. This is a deterministic manual
interpretation of the drawing, not a surveyed 1:1 reconstruction. Building forms,
street grids, shorelines and bridge details require further reference matching.
The scene is a blockout, not completed photorealistic content or native PCG/spline
graph exposure.

## Streaming design

Each numbered region has an editor-only native `LocationVolume` controller with
a `BoxComponent` describing its bounds. Unreal's LocationVolume loader uses the
actor's component bounds. Native Load/Unload controls are intended for selecting
regions in the World Partition editor. Heavy static-mesh actors use
`bIsSpatiallyLoaded=true`; a single inexpensive water plane uses false.

World Partition runtime streaming is controlled by streaming sources and runtime
grid settings. A numbered editor loading volume does not itself implement a
runtime region-toggle API. Interactive Load/Unload, persisted reload behavior,
runtime streaming and memory/frame-time measurements are separate acceptance
checks. Region ownership alone cannot guarantee that the engine will not crash.

## Source and recovery

The final version is `Saved/ReferenceCityRegions_v2/Chunks512_Final/`:

- `manifest.json`: coordinates, region ownership and build order.
- `ReferenceCityRegions_v2.blend`: export-space source with local chunk origins.
- `ReferenceCityRegions_v2_Layout.blend`: separate assembled review copy.
- `Nine_Region_City_Overview.png`: rendered review of the assembled source.
- `geometry_report.json`: per-chunk geometry and material counts.
- `*_transfer_result.json`: individual transfer receipts.
- `asset_preparation_progress.json`: completed asset preparation.

Earlier city versions remain preserved in their original directories. Imported
meshes are placed under `/Game/ReferenceCityRegions_v2/R01` through `R09`;
controllers and water use separate `Controllers` and `Background` folders.

`prepare_city_region_assets.py` prepares and saves assets without level placement.
It resumes only completed receipts and stops on partial or uncertain operations.
Create `pause_asset_preparation` in its source directory to stop after the current
atomic import finishes.

`install_city_regions.py` verifies the explicit live project, level and PIE state,
then uses typed native previews and applies. It checkpoints each placement and
reloads only after a verified checkpoint. A failed checkpoint stops installation
without discarding the active level.
`--reload-once` retains per-placement checkpoints but defers the level-open step
until all nine regions have been saved. This avoids interrupting a paused-editor
construction pass with repeated world reloads.

## Verified and pending evidence

The final Blender source was assembled, saved separately and rendered. Regional
geometry and level-workflow tests passed: 33 tests. The full Python suite then
passed all 380 tests. Ruff passed for the five city
scripts. The first test command used system Python, which lacks pytest and ruff;
the successful validation used the repository's `.venv` interpreter.

Unreal mesh import and material saves are recorded individually. Native import
currently triggers repeated static-mesh/distance-field work while material slots
are assigned, which can delay Editor interaction. No global renderer setting has
been disabled to conceal this cost.

Current-level checkpoint attempts previously failed the native stale-state guard.
Two actor-property samples showed a changing Ultra Dynamic Weather
`Current Lightning Angle`; the sampled sky actor values remained unchanged. The
user disabled viewport Realtime, after which the guarded checkpoint succeeded
with native backups and independent package-file verification. The guard remains
enabled. Evidence: `realtime_off_checkpoint.json`, operation
`1e504ee84c041ef6e066ff8b0fcf5449`. This establishes a successful checkpoint under
the paused editor condition, without proving that this single weather field was
the only changing value. Complete region placement, saved/reloaded controls,
interactive loading, PIE and performance remain separate checks.

All 81 mesh assets (80 chunks and one water surface) have completed saved transfer
receipts. Nine controller placements were checkpointed during the first placement
pass. Regions 5, 4, 6 and 2 were placed, checkpointed and inspected after the native
level-open request. Their actors remained loaded after those requests, so these
observations do not prove regional unloading. The pass stopped on another stale
checkpoint during region 8; the installer retained the active level. Remaining
placements and final persistence verification are still in progress.
