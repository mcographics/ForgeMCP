# ForgeMCP 0.2.17 — Lake and Hills Validation Reconciliation

Checked October 24, 2026. **The loaded terrain was independently reconciled against the exact three approved operations; the owner then approved a two-package native save, which completed.** The west-hill native job remains `validation_failed_partial`; this report does not relabel it as a successful job. No terrain edit, undo, restore, or Editor launch occurred during reconciliation or saving. Independent disk reload remains untested.

## Current Editor and unsaved state

Fresh ForgeMCP discovery found one connected Unreal session, `unreal-33500` / PID 33500, UE 5.6.1, ForgeMCP 0.2.17-alpha.1. `unreal_project_info` confirmed `G:/ForgeMCP/ForgeMCPDev.uproject`, `/Game/Levels/L_City_World_Master.L_City_World_Master`, PIE stopped. Landscape GUID `BD45FDD94EC2A29617B50794F2DE4E9D`; ForgeTerrain GUID `2E6FC5F94C4EF704F700299B5D08C23B`; Original Layer GUID `198824024FF8A77A01535B86021D9B34`. All 16 streaming proxies are loaded, with 64 registered Landscape and 64 collision components. Layers are up to date.

Fresh full-height native MD5: ForgeTerrain `a67ab415e4c454826b8a971280b2da0e`, range −600 to +500 local cm; Original Layer `9f43572fbc2c06ef497da015879cdb23`, range 0/0 cm. Both layers remain visible and unlocked. A complete loaded-package scan inspected 1,192 packages, with no inventory errors or further pages. Dirty production packages are exactly:

1. `/Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM` — active-world Landscape streaming proxy containing the sculpted region.
2. `/Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT` — Landscape root external actor.

`/Script/SlateCore` and `/Script/UnrealEd` are separate compiled-in engine-script dirty entries, not production Content. The previously approved editing session `247B234B4319CCFB7EBF6684928A585C` is revoked and has no active operation. Its operation list contains main basin completed, offset lobe completed, west hill `validation_failed_partial`, and no east-hill apply.

## Checkpoint and disk preservation

The new pre-change checkpoint is `G:/ForgeMCP_Recovery_Checkpoints/LakeBasinHills_PreChange_20261024T065905Z`, manifest SHA-256 `b6cf43a66ff94b152960824f65538ba530e569896eb503f5cd6cd582383bef8e`. All **23** backup files still match their manifest SHA-256 hashes. All **23** current production disk files still match the same pre-change hashes. None of the in-memory lake/hill changes has been saved to production disk. No checkpoint was overwritten or restored.

The west-hill per-operation recovery directory, `G:/ForgeMCP/Saved/ForgeLandscape/B54EAE034FFD21245FD1A492C268D4F3`, contains its 81 × 113 `before.r16`, request metadata, session checkpoint, result, and complete 2041 × 2041 snapshots of both layers from immediately before that operation. The ForgeTerrain snapshot MD5 is `36b48c18d48ba1e705fee9b76aa4d3c4`; Original Layer snapshot MD5 is `9f43572fbc2c06ef497da015879cdb23`. The offset-lobe recovery snapshot supplies the after-basin, before-lobe ForgeTerrain MD5 `69762ef991a1407eecdc0b564120f850`.

## Native failure and the outdated full-layer expectation

Installed ForgeMCP source computes `SessionExpectedFullAfter` at **preview time**: it reads the entire target layer, replaces the preview patch in that copy, and hashes the resulting 16-bit height array (`ForgeLandscapeEditSession.inl`). At job completion, `FinishEditSessionJob` compares the current full target hash with that stored preview expectation, and also compares protected-layer hashes. It reports the combined error if either comparison fails (`ForgeLandscape.cpp`). The west-hill preview was generated after the main basin but before the offset lobe. The offset lobe subsequently changed the full ForgeTerrain layer outside the west-hill write rectangle.

Using the retained **after-basin / before-lobe** full snapshot and the west-hill preview's native falloff formula, a read-only reconstruction gives preview-time expected full MD5 `1637a2bbffcd537b704df4808c427754`. Using the retained **after-lobe / before-west** full snapshot and the same west-hill operation gives `a67ab415e4c454826b8a971280b2da0e`, exactly the current live full-layer MD5. Both reconstructions give the approved west-hill bounded after MD5 `6eaf323f69925f9f16ae4ea9481a6758`. Thus the preview's old global expectation and the intervening lobe provide a demonstrated target-hash mismatch sufficient to trigger `validation_failed_partial`. The native receipt does not identify the individual failing branch. Independent current Original Layer full hash equals the protected snapshot and baseline, so no Original Layer change is observed.

The native west-hill job wrote 111/111 rows and reported `height_readback_validated=true`, but ended `validation_failed_partial` and revoked the grant. Its receipt's `protected_layers_verified=false` reflects the combined native check; it is not an independent claim that the Original Layer changed.

## Exact combined terrain verification

An offline reconstruction started from 2041 × 2041 encoded flat heights (`uint16` value 32768), whose MD5 is the verified baseline `9f43572fbc2c06ef497da015879cdb23`. It applied the three approved rectangular cosine-falloff native formulas in the actual order, with the actor's Z scale 100 and native-style 16-bit rounding. The reconstruction changed only those approved write rectangles. Its successive full-layer MD5 values match the native history and live readback:

| Stage | Changed vertices in stage | Reconstructed full MD5 | Native full MD5 |
|---|---:|---|---|
| Flat baseline | 0 | `9f43572fbc2c06ef497da015879cdb23` | Same before Test 02 |
| Main basin, `[1630,1640,1790,1800]`, −600 cm peak | 19,445 | `69762ef991a1407eecdc0b564120f850` | Same completed job |
| Offset lobe, `[1715,1695,1790,1785]`, −200 cm additional peak | 5,000 | `36b48c18d48ba1e705fee9b76aa4d3c4` | Same completed job and west pre-operation snapshot |
| West hill, `[1551,1670,1629,1780]`, +500 cm peak | 6,501 | `a67ab415e4c454826b8a971280b2da0e` | Same fresh live layer |

Fresh native bounded readbacks also confirm:

| Region | Samples | MD5 | Range / finding |
|---|---:|---|---|
| Main basin plus 1-vertex halo `[1629,1639,1791,1801]` | 26,569 | `7b5a670572702460bd46d88e8712b7bc` | −600 to 0 cm; includes intended offset-lobe change |
| Offset lobe plus halo `[1714,1694,1791,1786]` | 7,254 | `7ce1b61ad9b94862aeed3688097ed1a9` | −596.09375 to 0 cm; matches its applied preview |
| West hill plus halo `[1550,1669,1630,1781]` | 9,153 | `6eaf323f69925f9f16ae4ea9481a6758` | 0 to +500 cm; 6,501 positive values; matches applied preview |
| Unapplied east-hill region `[1791,1690,1879,1820]` | 11,659 | `d43253f9c12b07c3c6b05c4ebaeede71` | All zero; no east-hill write |
| Earlier riverbed test region `[1042,1065,1098,1075]` | 627 | `16146c02a58a89bdd7968848bbd0b8d6` | All zero; prior reset retained |

The matching full-layer reconstruction is evidence that the loaded ForgeTerrain array equals the exact three intended operations, including unchanged values outside their write footprints, subject to the ordinary MD5 comparison limit. It is not independent disk-reload proof, composed-height proof, viewport acceptance, or actual collision-height verification.

## Save preparation and next boundary

**Classification A — verified intended terrain in the loaded Editor.** The stale preview-time *full-layer expectation* explains the west-hill native validation failure. The west-hill job itself still failed, but its current bounded values and the complete combined full-layer result match the approved operation sequence. The Original Layer is preserved. Production disk remains at the flat checkpoint baseline.

A fresh native current-level save preview `55ede95145c072a5d97b50bf15000630` reviewed all 23 current-level packages. It marked **only** the two dirty Landscape packages listed above `will_save=true`, all other 21 `will_save=false`, and every package `will_delete=false`. It advertised verified binary backups on apply. The owner separately approved this exact preview and two-package scope. See the save result below.

Independent disk-reload, close-up visual, and collision-height acceptance remain separate.

The east-hill preview from the earlier demonstration is stale. Do not apply it in this task. A future east-hill step needs fresh preflight, a new local owner-approved grant, a fresh preview based on the saved combined terrain, separate operation approval, sequential bounded/full-layer verification, and separate save approval.

## Owner-approved native save and post-save audit

The owner explicitly approved saving only the two listed Landscape external-actor packages under preview `55ede95145c072a5d97b50bf15000630`. Exactly one `unreal_apply_current_level_save` call used that same preview ID and confirmation. It returned `state=saved`, `saved=true`, `native_save_returned_success=true`, `disk_restored=false`, and `rollback_performed=false`. The receipt marks exactly the proxy and Landscape-root packages saved; all other 21 were excluded and none deleted. Read-only reconciliation reports `recorded_state=completed`, `matching_saved_packages=true`, and both saved files present with the recorded SHA-1 values and sizes. It reports `native_package_contents_verified=false`: this receipt and hash check do not constitute an independent Editor reload of serialized heights.

The Editor log records production output moves for the Landscape-root package at 07:17:37.459–.460 UTC and the affected proxy at 07:17:37.505–.506 UTC. The exact disk comparison against the pre-change 23-file manifest is:

| Package | Before SHA-256 / bytes | After SHA-256 / bytes | Result |
|---|---|---|---|
| `/Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM` | `c4d976aa9638a875e0401b82381428183fb6da6e03a775d4c4f968aeb4811bde` / 606,716 | `8247516d21595bb39be3778845b6931214e0fab968cbafe69dc209a0edc36cb0` / 679,644 | Changed, as expected for the sculpted proxy |
| `/Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT` | `9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df` / 5,063 | Same SHA-256 / 5,063 | Editor rewrote the file; bytes remained identical |

All other **21** production files in the checkpoint scope retained their pre-change SHA-256 values; the level still has 22 external-actor files and its map, with no external-object files in that level namespace. Both native save backups under `Saved/ForgeLevelSaves/55ede95145c072a5d97b50bf15000630/Backups` match the two pre-save checkpoint hashes. All 23 historical pre-change checkpoint backup hashes and the manifest pin remain intact.

Fresh native loaded-package inventory after save inspected 1,192 packages with no errors or further pages and found **zero dirty production Content**. Only compiled-in `/Script/SlateCore` and `/Script/UnrealEd` were dirty. Fresh Landscape inspection retained GUID `BD45FDD94EC2A29617B50794F2DE4E9D`, ForgeTerrain MD5 `a67ab415e4c454826b8a971280b2da0e` and range −600/+500 cm, Original Layer MD5 `9f43572fbc2c06ef497da015879cdb23` and range 0/0 cm, 16 loaded / 0 unloaded proxies, and 64/64 registered Landscape/collision components. The Landscape reports clean and its layers up to date.

**Final verdict: VERIFIED INTENDED TERRAIN — OWNER-APPROVED TWO-PACKAGE SAVE COMPLETED.** This establishes the native save receipt, exact file writes, clean current Editor state, and live terrain preservation. Independent disk-backed reload, actual collision-height behavior, close-up visual acceptance, and the east-hill operation remain open. No east-hill apply or new editing grant was made.
