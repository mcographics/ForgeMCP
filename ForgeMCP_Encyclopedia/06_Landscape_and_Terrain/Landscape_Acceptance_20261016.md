# Landscape acceptance — October 16, 2026

The bounded native Landscape extension passed its initial and extended real MCP
acceptance tests in UE 5.6.1. This is development acceptance for isolated test maps;
production-level editing and World Partition mutation remain unsupported.

## Verified identity and delivered state

- Live session: `unreal-3960`.
- Project: `G:/ForgeMCP/Saved/LandscapeDevelopment/LiveHost/ForgeMCPDev.uproject`.
- Saved map: `/Game/ForgeMCPTests/Landscape/L_TerrainAcceptance_20261016_v2`.
- Landscape: one component, 63 quads per section, one subsection, 64 × 64 vertices.
- XY scale: 100 cm; Z scale: 100. Footprint: 63 × 63 metres.
- Native Edit Layer: `ForgeTerrain`.
- Final state: `completed`, `persistence_validated:true`, `dirty:false`,
  `layers_up_to_date:true`.
- Final layer height MD5: `4345b7bd2cfad75367fe31b085864072`.
- Final local height range after flattening/smoothing:
  `-492.1875` to `353.90625` cm.

The separate original editor remained on
`/Game/Levels/L_City_World_Master.L_City_World_Master`, with PIE stopped.
SHA-256 comparisons verified all **851 protected city/Sky files unchanged**.
No roads, buildings or nine-kilometre city terrain were generated.

## Evidence gates

| Gate | Result |
| --- | --- |
| Python full suite | 392 passed. |
| Latest affected Python/stdio contract checks | 14 passed after the frame API addition. |
| Ruff | Passed for server, new test and acceptance runner. |
| Native compilation | Full plugin/runtime compilation and linking passed. |
| Editor target | `UnrealEditor Win64 Development` passed; final incremental target also passed. |
| Real MCP subprocess | Creation, hill, valley, flatten, smooth, generation, coastline, explicit heightmap, save/reload and cancellation passed. |
| Height validation | Every completed stage matched exact planned native height samples; completed job checksums matched previews. |
| Persistence | Native save/reload passed twice. Landscape GUID, layer GUID, dimensions and exact height samples matched. |
| Read-only inspection | Repeated inspection preserved a clean reloaded map. |
| Viewport | Intermediate and completed native viewport captures inspected; terrain framing corrected. Unlit geometry review mode is used. |
| Protection | 851 before/after protected-file hashes matched; city editor retained its original world. |
| World Partition | Inspection metadata supported; mutations and external actor/streaming package saving explicitly rejected, not validated. |

The hill reached +800 cm and the valley reached -500 cm before the flatten/smooth
passes. Flattening blended its selected rectangle to +200 cm; smoothing used the
pre-edit neighborhood data. Every edit recorded multiple observable progress
states. Generated terrain used a deterministic sine field; coastline testing used
an X-axis elevation ramp. The explicit heightmap test applied a 4 × 4 sample patch.

One-use preview replay and native height-range rejection passed. Cancellation
stopped a 64-row job after **3 rows**, preserved an actual partial height change,
and applied no more rows during the subsequent observation. It did not claim
rollback. The retained backup path is recorded in the JSON acceptance report.
The test reset its extra terrain experiments, reconstructed the hill/valley
example and required the final saved/reloaded height checksum to match the first
successful persistence check.

## Performance limits

Observed maximum native stage times across the 12 completed edit jobs ranged
from 2.527 to 8.543 ms. The default stage was four rows
with a 0.3-second interval. These measurements cover the native batch operation;
they do not establish overall frame rate, GPU cost, large-terrain performance or
production World Partition responsiveness. Import, save and reload remain bounded
synchronous native calls.

## Resolved failures and remaining scope

The first run failed at reload because Unreal's editing-interface read helper
calls `Texture->Modify()`, dirtying a package during inspection. The read path now
copies texture source mip data without the editing interface; clean-package
regression checks passed. Native bounds-based framing replaced generic actor
framing. The stricter creation guard was also corrected to ignore Unreal-created
transient debug helpers while rejecting authored actors. Earlier failure evidence
is retained under `Saved/LandscapeDevelopment/attempt1/` and `attempt2-guard/`.

This extension currently supports only bounded disposable maps, one ForgeTerrain
Edit Layer, at most 127 × 127 vertices/four components, rectangular vertex edits
and explicit heightmap patches of at most 256 samples. Multi-layer composition,
independent layers per stroke, image-file heightmap import/export, erosion,
water/coastal simulation, World Partition proxy creation/unloaded cells and
production-level mutation remain unsupported. The single-component 64 × 64 case
is the live acceptance case; other supported topology combinations have not all
received individual live tests. Large-world and physics/PIE acceptance are not
claimed.

## Source, backups and installation state

The engine-wide source-authoritative plugin contains the new native source;
its running installed DLL was **not replaced**. The validated binary is currently
loaded only by the isolated LiveHost editor. The existing city session still runs
the earlier engine binary. The existing client needs a fresh MCP server/tool
registry to discover the five new tools; the acceptance runner used a fresh real
stdio server. A future engine-wide binary installation/restart is separate from
this isolated validation and was not performed on the open city editor.

Native sources match across build host, live host and the engine source tree.
Original affected source files are backed up under
`Saved/LandscapeDevelopment/SourceBackup-20261016/`. The complete native delta is
`Saved/LandscapeDevelopment/native-landscape.patch`; native hashes and a compiled
binary receipt are beside it. No source was published or committed by this task.

Machine evidence: `Saved/LandscapeDevelopment/acceptance.json`,
`build-and-validation-receipt.json`, `protected-content-after.json`,
`editor-target-first-pass.log`, `editor-target-final.log`, and
`final-incremental-console.log`. Viewport images are in the same folder.

See [Landscape API and operation contract](LandscapeAutomation.md).
