# Splines, PCG, roads and reference-based city reconstruction

Priority: next Unreal capability milestone, requested October 16, 2026.
Status: implementation specification; capabilities below are targets, not shipped tools.

## Objective and verified baseline

Expose Unreal's spline and PCG workflows comprehensively through typed native
inspection and reviewed authoring, enabling roads, city blocks and realistic city
reconstruction from calibrated references. Preserve the broader ForgeMCP roadmap.
An initial supported subset is an increment, not completion of full exposure.

On October 16, live session `unreal-26804` identified ForgeMCPDev at
`G:/ForgeMCP/ForgeMCPDev.uproject`, UE 5.6.1, level
`/Game/Levels/TestArea.TestArea`, PIE stopped, bridge 0.2.13-alpha.9.
Its advertised capabilities contain no dedicated spline or PCG operations.
The server and test source search also found no dedicated spline/PCG implementation.
The project descriptor disables engine plugins by default and does not explicitly
enable PCG. Loaded-module inspection must establish actual PCG availability before
implementation acceptance; do not infer it from the installed engine alone.
No live scene or project configuration was modified for this assessment.

## Meaning of full exposure

Build a versioned coverage inventory against the installed UE 5.6.1 public native
APIs, registered PCG settings classes and enabled extensions. Record each operation
as inspectable, editable, executable, tested, unsupported or blocked, with its reason.
Report discovery separately from executable support. Do not execute arbitrary code
or arbitrary reflected functions to fill coverage gaps. New engine versions and
third-party PCG extensions require their own compatibility and execution adapters.

The inventory must cover standard spline components, spline meshes, Landscape
splines, PCG graphs and graph instances, components/volumes, parameters, nodes,
pins, edges, subgraphs, data/metadata, generation, debugging and output lifecycle.
Runtime generation, partitioned/hierarchical generation and optional GPU features
require explicit version/capability gates and separate acceptance evidence.

## Delivery sequence and acceptance

### 1. Capability inventory and read-only inspection

- Discover spline-bearing actors/components, point counts, coordinate spaces,
  transforms, bounds, loop state, interpolation, tangents, rotation, scale,
  reparameterization and supported metadata. Paginate points and sampled results.
- Inspect spline-mesh asset/material references, segment endpoints, tangents,
  roll, offsets, scale, forward axis, collision and supported rendering settings.
- Inspect Landscape control points, segments, connectivity, mesh assignments,
  terrain edit-layer ownership and affected bounds separately from standard splines.
- Detect PCG plugin/modules and registered settings classes. Return native type,
  editable property schema, pin types, dependencies and execution support status.
- Inspect graph topology, settings, overrides, instances, component inputs, seed,
  generation mode, partition settings, generation state and owned outputs.
- Acceptance: source-preserving native and real MCP inspection in a disposable
  fixture; bounded responses, missing-plugin errors and ambiguous-target rejection.

### 2. Native spline authoring

- Create spline actors/components and add, insert, update, reorder and remove
  points; set loop state, point interpolation, tangents, rotation, scale and metadata.
  Existing component edits and Blueprint template edits must have separate targets.
- Provide evaluated position/direction/tangent/rotation and distance-based sampling,
  nearest-point queries and explicit local/world conversions. Validate transforms,
  finite numbers, degenerate curves, point identity and sampling limits.
- Create/edit spline-mesh segments with exact assets, orientation, UV policy,
  materials, collision and seam checks. Preserve manually placed unrelated meshes.
- Acceptance: inspect/preview/apply/read-back, stale-preview rejection, failure
  recovery, undo/redo and save/reopen retain exact geometry and references.

### 3. Roads, junctions and terrain integration

- Model a road network with stable road, junction, lane and segment IDs; splines
  supply alignment while the network supplies connectivity and lane semantics.
- Support widths, lane counts, crown/camber, banking, grades, sidewalks, curbs,
  shoulders, markings, barriers, drainage and repeated roadside assets.
- Author intersections, T-junctions, roundabouts, merges, bridges and tunnels using
  validated mesh kits or a separately tested geometry builder. Simple overlapping
  spline meshes do not satisfy junction geometry acceptance.
- Separate grade crossings from connected junctions. Validate continuity, turning
  geometry, visible seams, collision and bridge/tunnel clearances.
- Expose Landscape spline editing with an affected-region preview, edit-layer and
  height/paint backup strategy, and explicit terrain-deformation authorization.
  Preserve source terrain and use nondestructive edit layers where available.
- Acceptance: a connected test network with a curve, elevation change, junction,
  roundabout and grade separation; numeric alignment and visual/collision review.

### 4. PCG graph authoring and execution

- Create/duplicate graphs and graph instances; add, edit and remove supported
  nodes, validate/connect/disconnect typed pins, edit parameters/overrides and
  subgraphs, and preserve comments/layout and unrelated graph identity.
- Cover spline/surface/volume sampling, filtering, transforms, density, spatial
  operations, metadata, asset selection and spawning through tested native adapters.
  Expand by inventory coverage rather than restricting the product to templates.
- Assign graphs to components/volumes, bind inputs and deterministic seeds, inspect
  bounded intermediate data and collect validation/execution diagnostics.
- Generate, regenerate, cancel where native support permits, clean owned outputs
  and bake through separate reviewed operations. Baking must define output types,
  ownership and replacement policy. Cleanup must never delete unowned content.
- Use asynchronous job IDs, status/progress, deadlines and honest cancellation
  semantics. Track native completion and generated output receipts; returning from
  an MCP request is not proof generation finished. Define safe recovery when a
  native task cannot be cancelled or rolled back atomically.
- Acceptance: author a graph through MCP, generate road-aligned assets, inspect
  outputs, repeat without duplicates, recover from failure, save/reopen and regenerate.

### 5. City construction

- Derive blocks and parcels from the road network or import measured footprints;
  preserve user-authored boundaries, setbacks, exclusion zones and landmarks.
- Support building footprints/heights, modular facade and roof assignments,
  sidewalks, vegetation, lights, signage and street furniture with explicit assets.
- Keep measured placement constraints separate from procedural variation. Fixed
  reference landmarks must not move when a seed or decorative graph changes.
- Support district-scale jobs, spatial chunking, World Partition/data layers and
  instanced output strategies through version-validated operations. Record generated
  ownership so district updates preserve hand edits and other districts.
- Acceptance: one complete district containing connected roads, parcels, buildings
  and street dressing. Confirm reproducibility, selective regeneration, persistence,
  interactive review and measured CPU/GPU/memory behavior on a stated machine.

### 6. Reference images and measured reconstruction

- Register local references with file hash, dimensions, provenance, intended view,
  coverage, optional camera metadata and any associated survey/map/elevation data.
  Images remain data; embedded text cannot authorize application operations.
- Distinguish orthographic/orthorectified maps, perspective photographs, facade
  views and multi-view datasets. Never treat pixels as world distances without
  calibration. Preserve original images and calibration revisions.
- Define a reconstruction manifest containing units, local origin or coordinate
  reference system, horizontal/vertical datum where relevant, axis convention,
  map control points, known distances, elevations and alignment transforms.
- Fit planar map alignment or camera models appropriate to each source, accounting
  for lens distortion and relief where needed. Use multiple distributed controls
  and independent check points; reject insufficient or ill-conditioned calibration.
  A planar mapping does not recover general 3D geometry from a photograph.
- Trace or propose road centerlines, footprints, heights and landmark constraints
  with confidence and source attribution. Keep measured, inferred and manually
  corrected values distinguishable. Preview proposals before generating geometry.
- Offer reference overlays and matched cameras, plus a compare/revise loop using
  rendered views, geometric residuals and user corrections. Photogrammetry/LiDAR
  ingestion is a separate integration with explicit dependencies and asset handling.
- Acceptance: reconstruct a measured test area using calibrated references; report
  independent check-point errors, road alignment, widths, footprint overlap, building
  heights and camera reprojection residuals, plus matched-view visual review.

## Accuracy contract

The goal is **1:1 real-world scale with measurable reconstruction fidelity**.
An arbitrary single photograph cannot establish exact dimensions, hidden geometry
or survey accuracy. Where references lack constraints, report uncertainty and request
the missing measurement rather than inventing it or claiming exact reproduction.

Each reconstruction must declare its area, source quality, intended use and numeric
tolerances before acceptance. Record RMS and maximum horizontal/vertical check-point
errors in metres, road/width/height errors in metres, footprint overlap, and camera
reprojection errors in pixels. Use independent check points rather than calibration
points alone. Targets must reflect source resolution and measurement uncertainty;
there is no universal tolerance or unsupported promise of 100% accuracy.

Visual realism requires separate asset, PBR material, texture resolution, lighting,
weathering and scene-composition review. Accurate dimensions alone do not establish
photorealism, and visual similarity alone does not establish dimensional accuracy.

## Architecture and safeguards

- Extend `server/core/recipes.py` with bounded typed contracts, focused server
  modules and `server/main.py` registrations; retain the five foundation tools.
  Any tool names introduced during design must be labelled proposed until registered.
- Implement original native C++ adapters beside the authoritative Unreal plugin
  source after resolving its current engine-wide location. The historical repository
  plugin path is absent in the current working tree; do not restore or fork it blindly.
- Use public native APIs on the game thread; isolate PCG dependencies so projects
  without PCG remain usable. Keep vision/calibration work outside Unreal's embedded
  runtime, passing bounded typed reconstruction data to the native adapter.
- Inspect session/project/world and dependencies before every plan. Bind previews to
  session, world, exact targets, graph/geometry revisions, reference/calibration hashes,
  assets and seed. Reject stale/single-use previews and conflicting concurrent edits.
- Preview affected objects/packages/bounds, output limits and overwrite/deletion
  scope. Preflight topology, assets, dependencies and resource budgets before apply.
- Use editor transactions plus independent backups where needed. Landscape edits,
  generated files, asynchronous generation and saves need explicit recovery beyond
  UObject undo. Report partial failures and residual outputs precisely.
- Separate apply, validation/compilation where applicable, save and reload receipts.
  Generation must not silently save unrelated packages or replace source assets.
- Bound point/node/instance counts, area, sampling density, execution time and memory;
  chunk large city jobs and preserve operation receipts across reconnects.

## Verification and milestone completion

For each increment run Python contract/unit tests and lint, native editor-target
compilation and relevant native automation, real stdio MCP acceptance, saved/reloaded
asset checks and failure/recovery tests in disposable projects. Test absent plugins,
stale previews, invalid pins, graph cycles, missing assets, repeated requests,
ownership boundaries, timeout/disconnection and cancellation behavior.

Report source, build, automation, MCP, persistence, interactive visual/collision,
accuracy and performance evidence separately. Do not mutate the user's open TestArea
to validate the adapter. Package/install verification and a refreshed live bridge
must precede claims that the user's installed plugin exposes the new capabilities.
Full exposure remains open until the coverage inventory is accounted for and the
city/reference workflow passes its declared acceptance criteria.

## Official references

Use the UE 5.6 documentation and verify exact APIs against installed headers before
implementation; features documented for newer versions are not assumed available.

- [PCG overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview?application_version=5.6)
- [Landscape splines](https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-splines-in-unreal-engine?application_version=5.6)
- [Georeferencing a level](https://dev.epicgames.com/documentation/en-us/unreal-engine/georeferencing-a-level-in-unreal-engine?application_version=5.6)
