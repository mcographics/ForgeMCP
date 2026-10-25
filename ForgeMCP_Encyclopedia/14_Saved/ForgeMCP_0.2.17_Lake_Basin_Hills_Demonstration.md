# ForgeMCP 0.2.17 — Landscape Test 02: Lake Basin and Rolling Hills

Checked October 24, 2026. **BLOCKED — NATIVE FULL-LAYER VALIDATION FAILED AFTER THE WEST HILL.** The basin, offset basin lobe, and west hill were written to the loaded ForgeTerrain layer and remain **unsaved**. The east hill was not applied. No terrain retry, save, restoration, or Editor launch occurred after the failure.

## Baseline and recovery

Fresh ForgeMCP discovery authenticated the existing `unreal-33500` / PID 33500 Editor: UE 5.6.1, ForgeMCP 0.2.17-alpha.1, `G:/ForgeMCP/ForgeMCPDev.uproject`, `/Game/Levels/L_City_World_Master.L_City_World_Master`, PIE stopped. Landscape GUID `BD45FDD94EC2A29617B50794F2DE4E9D`, ForgeTerrain GUID `2E6FC5F94C4EF704F700299B5D08C23B`, Original Layer GUID `198824024FF8A77A01535B86021D9B34`. Both full-height layer MD5 hashes were `9f43572fbc2c06ef497da015879cdb23` and both layers were 0/0 local cm. All 16 World Partition proxies were loaded, with 64 registered Landscape and 64 collision components. The complete loaded-package inventory inspected 1,192 packages; only compiled-in `/Script/SlateCore` was dirty. No production Content was dirty.

The new physical pre-change checkpoint is `G:/ForgeMCP_Recovery_Checkpoints/LakeBasinHills_PreChange_20261024T065905Z`. Its manifest SHA-256 is `b6cf43a66ff94b152960824f65538ba530e569896eb503f5cd6cd582383bef8e`. It holds all 22 current map external-actor packages plus the map, 23 files totaling 9,841,221 bytes. Every source and backup file was hashed and matched immediately after copying. A fresh post-failure audit again found zero source and backup mismatches among all 23; the production disk files still match this pre-change checkpoint. Historical checkpoints were not changed.

## Location, authorization and previews

The chosen site is in the loaded World Partition proxy `/Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM`, away from the earlier riverbed coordinates. The Landscape actor is at `[-102000,-102000,0]` with `[100,100,100]` scale, so the basin footprint spans roughly 160 m by 160 m at 1 m vertex spacing. A native bounded read of `[1620,1620,1800,1800]` returned 32,761 zero-valued ForgeTerrain samples. The site and its 1-vertex edit halos fit the one loaded proxy. No exhaustive independent audit of non-Landscape actor overlap was made.

Read-only native preflight passed for `lower` and `raise` within inclusive region `[1550,1600,1880,1850]`. The owner entered `Forge.Landscape.ApproveEditSession 247B234B4319CCFB7EBF6684928A585C` in the existing Editor. The log shows approval at 07:00:50 UTC. A duplicate entry of the same command at 07:01:21 UTC returned `request stale or unsaved/unsafe world`; native status continued to show the original grant approved, and no new request was made. The native recovery root was `G:/ForgeMCP/Saved/ForgeLandscapeAdoption/247B234B4319CCFB7EBF6684928A585C`. Its manifest SHA-256 was `1e9610312e93a31ce043f25fe6208ba49eda7d6768097aecd5b16885289d4a09`; all 23 backup and source MD5 values matched.

The owner reviewed the operation footprints and explicitly approved the basin preview, then the offset lobe and both hill previews. All elevations below are ForgeTerrain edit-layer local centimeters, not composed-world or collision measurements.

| Sequence | Exact inclusive write region | Action and peak delta | Final preview ID | Native bounded before → after MD5 | Actual result |
|---|---|---|---|---|---|
| 1. Basin | `[1630,1640,1790,1800]` | lower, up to −600 cm | `CA42E1B04A3216A9FF43738ACFE0D902` | `694f08cdd12772788582bc052954d380` → `319274010486007a60d6ab2134298175` | Completed, 161/161 rows, validated |
| 2. Offset lobe | `[1715,1695,1790,1785]` | lower, up to another −200 cm | `2D0DD78547F7405D4C438AA8E455FAE6` | `6b387406153edd91a26b9ca45374503d` → `7ce1b61ad9b94862aeed3688097ed1a9` | Completed, 91/91 rows, validated |
| 3. West hill | `[1551,1670,1629,1780]` | raise, up to +500 cm | `B54EAE034FFD21245FD1A492C268D4F3` | `531aaac3ba80956c44d657e20a56ccbf` → `6eaf323f69925f9f16ae4ea9481a6758` | 111/111 rows written; bounded readback matched, **full-layer validation failed** |
| 4. East hill | `[1791,1690,1879,1820]` | raise, up to +700 cm | `832F66A84012925010A39D8F76F75629` | `0395b8d58c3f15dfe95774c793d6259d` → `d3a9a9b60aff62dfdea0e57259457820` | **Not applied** |

The first basin preview had expired after review; a fresh preview with the same region, parameters, and before/after MD5 values was used following the owner's approval. The second lobe and both hills were freshly previewed after the first basin operation. No further preview was used after the west-hill failure.

## Applied results and safety stop

For the main basin, native height readback matched the preview; 19,445 vertices were below zero, the minimum was −600 cm, and the 1-vertex outer guard ring remained zero. The offset lobe's bounded readback also matched its preview; the full ForgeTerrain MD5 after that step was `36b48c18d48ba1e705fee9b76aa4d3c4`, with the Original Layer still at `9f43572fbc2c06ef497da015879cdb23`.

The west-hill job returned `state=validation_failed_partial` with `rows_applied=111/111`, `height_readback_validated=true`, bounded after MD5 `6eaf323f69925f9f16ae4ea9481a6758`, and error `Full target or protected Original layer validation failed; evidence retained.` A fresh native bounded read confirmed 6,501 positive west-hill samples, 0 to +500 cm, and the same bounded MD5. A fresh full Landscape inspection returned ForgeTerrain MD5 `a67ab415e4c454826b8a971280b2da0e`, range −600 to +500 cm; Original Layer MD5 remained `9f43572fbc2c06ef497da015879cdb23`, range 0/0 cm. All 16 proxies and 64/64 registered components remained present, and layers were up to date.

Native status automatically revoked the grant on the validation failure. It records exactly three attempted operations, with the first two completed and the west hill `validation_failed_partial`. The east hill has no operation record. The native source computes a full-layer expected hash at **preview time** and compares it with the full layer when the job finishes. The west-hill preview was made before the overlapping offset-lobe operation, so an intervening full-layer change is a plausible reason its full-layer expectation differed even though its own bounded readback matched. The native error combines target and protected-layer failure conditions; the available result does not independently identify which comparison failed. Current Original Layer readback supports preservation, but does not convert the native job result to success.

Complete post-failure dirty-package inventory again inspected 1,192 loaded packages with no errors or further pages. The only dirty production Content packages are `/Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM` and `/Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT`; `/Script/SlateCore` is the separate compiled-in engine-script entry. Production disk files remain byte-identical to the pre-change checkpoint. The loaded terrain is therefore unsaved.

Native per-operation recovery evidence is retained under `G:/ForgeMCP/Saved/ForgeLandscape/` for the three applied preview IDs, including their `before.r16` files. No automatic restoration was attempted. Collision-height validation was deferred by native job status until save/reload; no close-up viewport capture or actual collision-height acceptance was performed after the failure. Independent disk-reload persistence is untested.

## Final verdict and next boundary

**BLOCKED — SPECIFIC SAFETY CONDITION: `validation_failed_partial` on the west-hill job.** Basin and lobe readbacks passed; the west hill is visibly represented in native height data but failed the editing-session full-layer safety gate. The grant is revoked, the east hill was not applied, and no save is authorized. Preserve the Editor and checkpoints while reviewing the native failure and current unsaved Landscape. Any new edit or save requires a fresh safety assessment and exact owner authorization; do not replay these operations or restore files automatically.
