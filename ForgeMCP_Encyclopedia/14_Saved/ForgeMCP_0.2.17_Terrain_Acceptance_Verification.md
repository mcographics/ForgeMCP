# ForgeMCP 0.2.17 — Terrain Acceptance Verification

Checked October 24, 2026. Mode: read-only acceptance audit. **Overall verdict: BLOCKED — independent disk reload and close-up visual acceptance remain unverified.** Live Editor collision-height queries and the production package integrity audit passed. No terrain edit, preview, save, Editor launch/reload, checkpoint change, or east-hill operation occurred during this audit.

## Acceptance gates

| Gate | Verdict | Evidence boundary |
|---|---|---|
| Independent disk-backed Landscape reload | **BLOCKED** | No independently loaded current saved project was available; the production Editor was not reloaded or restarted. Disk hashes and current memory are not a reload test. |
| Close-up basin/lobe/west-hill visual inspection | **BLOCKED** | A native viewport capture succeeded, but it showed distant flat terrain rather than the target features. Safe automated close-up framing was unavailable. |
| Actual collision-height queries in the current Editor | **PASS, live session only** | Five read-only native line traces hit the expected Landscape heightfield collision component; heights matched local layer samples within 0.01 cm. The independently loaded-world collision requirement remains untested. |
| Production package and checkpoint integrity | **PASS** | All 23 protected production file hashes and sizes were unchanged throughout this audit; checkpoint backup hashes and manifest pin match. Zero dirty production Content packages. |

## Session, Landscape, and saved-file baseline

Fresh ForgeMCP discovery found one connected Unreal session: `unreal-33500`, PID 33500, UE 5.6.1, ForgeMCP 0.2.17-alpha.1. `unreal_project_info` identified `G:/ForgeMCP/ForgeMCPDev.uproject`, `/Game/Levels/L_City_World_Master.L_City_World_Master`, PIE stopped. The Landscape GUID is `BD45FDD94EC2A29617B50794F2DE4E9D`, with ForgeTerrain GUID `2E6FC5F94C4EF704F700299B5D08C23B` and Original Layer GUID `198824024FF8A77A01535B86021D9B34`.

Fresh *live-memory* full-height MD5 values were ForgeTerrain `a67ab415e4c454826b8a971280b2da0e` (−600 to +500 local cm) and Original Layer `9f43572fbc2c06ef497da015879cdb23` (0/0 cm). Both layers were visible and unlocked; the Landscape reported clean and layers up to date. All 16 World Partition proxies were loaded, with 64 registered Landscape and 64 collision components.

The protected Content baseline consists of the map plus 22 current level external-actor files. Their 23 relative paths, SHA-256 values, and sizes were captured in memory at the start of this audit and compared again at the end: **zero changed hashes or sizes**. The saved sculpt proxy remained `679,644` bytes / SHA-256 `8247516d21595bb39be3778845b6931214e0fab968cbafe69dc209a0edc36cb0`; the Landscape-root external actor remained `5,063` bytes / SHA-256 `9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df`. The level namespace still contained 22 external-actor files and the map.

## Independent disk reload — BLOCKED

Only the production Editor was connected. No current isolated Editor or independent disk-loaded Landscape response was available. The previously prepared Stage 2E clones predate the current saved basin and hills, so their files cannot establish persistence of this new terrain. Creating a current clone and launching an isolated Editor would write files, private DDC, logs, and process state; this read-only task did not authorize that work. Reloading the active production Editor would disturb its current session and was expressly excluded when unsafe.

The prior native save receipt and production package hashes support that the two scoped packages were saved, but they do **not** independently deserialize the height data. The expected ForgeTerrain and Original Layer MD5 values were therefore confirmed only from the current loaded production Editor. **No independent disk-reload PASS is claimed.** A separate reviewed authorization is required for a fresh isolated project copy and one bounded isolated Editor launch, or another demonstrated read-only UE package deserializer that can recover these edit-layer heights from the saved files without affecting production.

## Close-up visual inspection — BLOCKED

`unreal_capture_screenshot` produced one read-only, in-memory 1072 × 720 JPEG on Editor frame 380735. It showed a distant flat checkerboard Landscape and sky; the basin, offset lobe, and west hill were not in view. It cannot be used to judge their contour, bank slope, connection, surface artifacts, or visual prominence. No screenshot file was saved.

The computer-use window inventory uniquely identified the running `ForgeMCPDev - Unreal Editor` window. Its image capture timed out twice (first `FrameArrived timed out`, then `window capture timed out`). No UI input or viewport navigation was sent. Native `frame` would require a new existing-world authorization in this protected production map, so it was not invoked merely to move the viewport. No camera actor, material, lighting, Landscape component, or asset was changed.

For a later manual close-up review, representative world coordinates from the Landscape actor transform `[-102000,-102000,0]` and 100 cm XY vertex spacing are: basin center `(69000,70000,-600)` cm, offset lobe `(73200,72000,-424)` cm, and west hill `(57000,70500,500)` cm. Viewport navigation should remain temporary and nonpersistent; capture each feature and its transition to flat terrain without saving or editing.

## Native collision-height queries — PASS in the current Editor

Five bounded, read-only `Visibility` line traces ran from Z +5000 to −5000 cm with PIE stopped. Every query hit `LandscapeStreamingProxy_B7E96FCS9V6MS9RT9VEJH9KT9_510_3_3_0`, specifically `LandscapeHeightfieldCollisionComponent_54`, rather than an unrelated actor. The component reported `QueryAndPhysics`, `BlockAll`, object type `WorldStatic`, and `Visibility=Block`. No trace missed. Samples were taken at exact Landscape vertices, avoiding off-grid interpolation ambiguity; collision remains a runtime approximation at other positions and resolutions.

| Site | Vertex XY | World XY (cm) | ForgeTerrain sample Z (cm) | Collision impact Z (cm) | Absolute difference |
|---|---|---|---:|---:|---:|
| Basin floor | `(1710,1720)` | `(69000,70000)` | −600 | −600 | 0 |
| Offset lobe | `(1752,1740)` | `(73200,72000)` | −424.21875 | −424.22827497 | 0.009525 cm |
| West hill peak | `(1590,1725)` | `(57000,70500)` | +500 | +500 | 0 |
| Basin shoreline control | `(1710,1640)` | `(69000,62000)` | 0 | −0.00610361 | 0.006104 cm |
| Unchanged flat control | `(1700,1600)` | `(68000,58000)` | 0 | −0.00610361 | 0.006104 cm |

These are **actual physics traces in the production Editor's loaded world**, with the expected proxy and heightfield component. They do not prove collision data persisted to disk or behaves identically after an independent reload. No collision rebuild, physics setting change, debug drawing, or PIE run occurred.

## Final integrity and historical operation status

A final complete native dirty-package inventory inspected 1,192 loaded packages, with no errors or further pages. It found only compiled-in `/Script/SlateCore` and `/Script/UnrealEd` dirty: **zero dirty production Content packages**. Final project, level, PIE, Landscape GUID, layer hashes, and 16/64/64 topology matched the initial audit.

The original 23-file pre-change checkpoint at `G:/ForgeMCP_Recovery_Checkpoints/LakeBasinHills_PreChange_20261024T065905Z` retained manifest SHA-256 `b6cf43a66ff94b152960824f65538ba530e569896eb503f5cd6cd582383bef8e`; all 23 checkpoint backups matched their manifest hashes. This checkpoint is intentionally a *pre-sculpt* recovery baseline, so its affected proxy hash differs from the current saved sculpt file. It was not overwritten or restored.

Native editing-session status remains revoked. It still records the main basin and offset lobe as `completed`, the west hill as **`validation_failed_partial`**, and no east-hill apply. No editing session, terrain preview/apply, save, or cleanup operation was issued in this audit.

## Overall recommendation

**BLOCKED for full terrain acceptance.** The saved-file write scope and current production collision behavior are verified, but independent disk-backed Landscape deserialization and close-up visual review remain required. A later separately authorized isolated reload must start from a fresh copy of the current saved project, verify both full-layer hashes, representative feature heights, proxy/collision registration and actual collision traces, then audit production preservation. A close-up visual review can be done in the existing Editor through owner-controlled viewport navigation if its target features can be shown without asset changes. Do not apply the east hill or revise the historical west-hill result as part of this acceptance audit.
