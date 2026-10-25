# ForgeMCP Landscape Runtime Acceptance — Phase 6C

**Target engine:** Unreal Engine 5.6.1  
**Candidate:** `Saved/LandscapeDevelopment/Phase6Fresh/ForgeMCPDev.uproject`  
**Protected level:** `L_City_World_Master`  
**Acceptance status:** **NO-GO**  
**Report date:** 2026-10-17

## Acceptance context

Phase 6C requires live Editor evidence for World Partition transitions, coastline collision, consecutive heightmap chunks, streaming-boundary edits, measured memory and responsiveness, and close-up viewport results. The user directed that Unreal remain closed. Accordingly, no Editor was launched for this acceptance pass, no Landscape operation was applied, and no runtime gate is represented as newly tested. The connected city Editor was not used. Existing isolated-run evidence from earlier phases is retained below and is distinguished from Phase 6C acceptance.

## A. Implementation summary

Phase 6C produced no C++ or Python implementation changes: the required corrective work depends on live repro and validation, and running it would require opening an Editor. The isolated Phase 6B2 candidate remains the implementation under review. It retains the five existing MCP tools: `unreal_inspect_landscape`, `unreal_preview_landscape`, `unreal_apply_landscape`, `unreal_landscape_job_status`, and `unreal_cancel_landscape_job`.

The native candidate uses `ALandscape::Import`, a native `ForgeTerrain` Edit Layer, `FLandscapeEditDataInterface` for bounded height access, the editor game-thread tick for staged edits, and native World Partition editor loader adapters for region requests. It enforces a 4,194,304-sample creation cap, a 1,048,576-sample edit-region cap, a 32,768-sample heightmap input-chunk cap, a 16 MiB before/after working-buffer budget, a 15 MiB pending-preview budget, and at most eight rows written per editor tick. Cancellation stops later batches and reports the partial result; it does not roll back rows already applied. The implementation does not provide an end-to-end large source-heightmap tiler/orchestrator.

The Phase 6B2 candidate also keeps asynchronous loader adapters alive while polling proxy descriptors and only reports an unload after observing the requested descriptor state. The test runner checks both loader status and proxy counts. These changes compiled, but the revised unload path has not passed live acceptance. The candidate permits a clean `/Engine/Maps/Entry` package as the isolated creation source under its safety checks; that gate was previously inspected live, but no Landscape was created in that session.

The candidate source, Python contract, tests, acceptance runner, and prior candidate DLL have a hash manifest at [the Phase 6B2 source backup](../Saved/LandscapeDevelopment/SourceBackup-Phase6B2-20261017-012414/manifest.jsonl). The compiled candidate DLL remains isolated at `Saved/LandscapeDevelopment/Phase6Fresh/Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll` (SHA-256 `41B2B10AE889247BFEDF671BDC639920B6127D3BC76DA4AF9E5262AEDA073018`). It was not installed into the shared plugin or city project.

## B. World Partition results

Earlier isolated tests established proxy creation and external-actor persistence, but not actual streaming transitions:

| Prior test evidence | Observed result | Acceptance status |
|---|---|---|
| 253 × 253 Landscape, 16 components, four streaming-proxy descriptors | Create/edit operations, save/reload, restart identity and height-hash checks passed. Five external package backups and seven external actor files were recorded. All four proxy descriptors remained loaded after the unload request; zero unloaded proxies were observed. | Persistence passed in that run; unload/reload transition failed. |
| 1,135 × 1,135 Landscape, 324 components, 81 streaming-proxy descriptors | Create, external-package save, and restart persistence passed. After the unload request, all 81 descriptors remained loaded and zero were unloaded. | Persistence passed in that run; unload/reload transition failed. |

Evidence: [253² World Partition run](../Saved/LandscapeDevelopment/phase6-L_Phase6_WPFreshC.json), [253² restart run](../Saved/LandscapeDevelopment/phase6-L_Phase6_WPFreshC-restart.json), [1,135² World Partition run](../Saved/LandscapeDevelopment/phase6-L_Phase6_WPGrid18B.json), and [1,135² restart run](../Saved/LandscapeDevelopment/phase6-L_Phase6_WPGrid18B-restart.json).

There is no demonstrated loaded-to-unloaded transition, reload transition, or truthful end-to-end runtime state sequence after the Phase 6B2 asynchronous change. Earlier runs do not establish whether editor references, streaming sources, pinned actors, or another World Partition condition prevented unloading. No exact engine limitation has been established, so the behavior cannot be accepted as an engine limitation with a supported alternative. Streaming-boundary edits and edits against unloaded regions remain untested.

## C. Collision validation

The earlier 1,009 × 1,009 non-partitioned test applied its full coastline operation across all 1,009 rows and passed height-data readback. It then failed collision validation: the complex collision height query returned no readable value at the final edit sample after approximately 12.065 seconds of collision waiting. The operation was not saved as a passing result. The same run recorded successful height and collision checks for raise, lower, flatten, and smooth operations. A separate 2,041² bounded 5 × 5 raise crossing four components passed height readback and a complex collision query (expected and actual world Z were both 0 cm); this does not validate full-coastline collision synchronization.

Evidence: [1,009² run](../Saved/LandscapeDevelopment/phase6-L_Phase6_1009A.json) and [2,041² bounded edit](../Saved/LandscapeDevelopment/phase6-L_Phase6_2041BoundedEdit.json).

**Root cause and correction remain unresolved.** The candidate waits for `ALandscape::IsUpToDate()` before its collision query. That is a layer-recomposition check and does not, by itself, prove that every collision component has a readable complex heightfield. Local UE 5.6.1 source inspection shows the height query can return no value when collision-component coverage or the complex heightfield reference/data is unavailable. Those are possible failure modes, not a diagnosis of this recorded failure: the test did not capture per-component collision readiness or identify the failing component. The collision sample was adjusted away from a component seam in candidate code, but that change has not been retested live. Collision acceptance therefore fails.

## D. Chunked heightmap results

The Python/native request contracts enforce the 32,768-sample input chunk limit and exact request-region dimensions. Terrain edits are bounded to 1,048,576 samples, and staged jobs are limited by the plugin-owned buffer budgets and eight-row tick batch. A previous bounded edit crossed four Landscape components successfully, which validates that specific edit path and sample, not heightmap chunk assembly.

No Phase 6C test applied multiple consecutive heightmap chunks. Chunk placement, shared-edge continuity, deterministic joins across hills/slopes/coastlines, full collision continuity, and partial-chunk cancellation/recovery have not been measured. A previously exercised small-job cancellation does not establish recovery of a multi-chunk import. ForgeMCP has no large-source tiling/orchestration path to validate. Chunked heightmap acceptance is **not demonstrated**.

## E. Performance and memory measurements

The available values below are timings captured by the earlier acceptance harness. Stage duration is not equivalent to a measured Editor frame time. No Unreal Insights trace, peak process-memory capture, temporary-allocation profiler, or responsiveness measurement was collected.

| Test size | Creation / editing evidence | Collision / persistence evidence | Memory / responsiveness |
|---|---|---|---|
| 253 × 253, World Partition | Creation apply about 994 ms. Earlier individual bounded edit stages were in the approximate 9–20 ms range. | Save about 382 ms and reload about 421 ms in the prior run; restart identity/hash passed. | Peak memory and Editor responsiveness not measured. Proxy unloading did not occur. |
| 1,009 × 1,009, 256 components | Coastline wrote 1,009/1,009 rows. Coastline maximum stage was about 105.46 ms; smoothing recorded a maximum stage of about 171.17 ms. | Height readback passed; complex collision query failed after about 12,065 ms. This run was not accepted or saved as a pass. | Peak memory and Editor responsiveness not measured. |
| 2,041 × 2,041, 16 components | Creation took about 2,129.9 ms. A 5 × 5 edit crossing four components recorded a maximum stage of about 26.94 ms. | Bounded edit collision validation took about 1,025 ms; save/reload preserved Landscape identity and height hash. Creation map was about 8,491,061 bytes; edited map about 8,496,834 bytes. | Peak memory and Editor responsiveness not measured. |

The configured raw before/after height-buffer budget is 16 MiB, but it does not measure Unreal texture source, collision, derived data, or total process memory. No claim of stable frame rate or large-terrain memory safety can be made from these timings. The proposed 4,573² topology remains outside the current sample cap: 20,912,329 vertices and 41,824,658 bytes for a single R16 height plane, before other engine allocations.

## F. Automated testing and compilation

Offline checks run for this report:

- Full Python suite: **403 passed** in 18.55 seconds.
- Scoped Ruff check for `server/core/landscape.py`, `tests/test_landscape.py`, and `scripts/verify_landscape_scalability.py`: passed.
- Python byte-compilation for those same files: passed.

The isolated UE 5.6.1 `ForgeMCPDevEditor Win64 Development` candidate build log records four of four UBT actions and `Result: Succeeded` (32.49 seconds total; 30.56 seconds in the local executor). See [the Phase 6B2 candidate build log](../Saved/LandscapeDevelopment/phase6b2-final-build.log). No new C++ change was made for this Phase 6C report, so this is prior candidate compile evidence, not a new runtime validation.

The existing suite preserves contract and resource-bound checks. It does not replace the missing live tests for proxy transitions, coastline collision synchronization, chunk continuity, streaming-boundary behavior, runtime memory, or viewport responsiveness. No Phase 6C-specific automated coverage was added. No live Unreal acceptance test or screenshot was run for this report.

## G. Remaining limitations

- **World Partition streaming:** Proxy unload and reload transitions are unproven; earlier 4- and 81-proxy tests observed all proxies still loaded.
- **Collision:** The 1,009² coastline failure has no confirmed root cause or successful retest. Collision readiness at every touched component is not verified.
- **Heightmap chunks:** Multi-chunk placement, adjacency continuity, cancellation recovery, and deterministic results are unverified; large-source tiling is unsupported.
- **Streaming boundaries:** Loaded/unloaded boundary behavior and safe rejection or queuing of edits against unloaded terrain are unverified.
- **Performance:** Peak process/engine memory, collision allocation cost, streaming transition time, and Editor responsiveness were not profiled. Recorded stage times include a roughly 171 ms maximum and must not be interpreted as a frame-time guarantee.
- **Visual acceptance:** No Phase 6C close-up viewport screenshots exist. The earlier 2,041² edit screenshot used a wide camera angle and does not clearly show the 5 × 5 modification.
- **Large-world topology:** The 4,573² proposal exceeds current ForgeMCP sample and buffer limits. Multi-Landscape tiling and shared-border continuity are not implemented or validated.

## H. Final recommendation

**NO-GO — Phase 6C acceptance requirements are not satisfied.** The exact blockers are the missing observed World Partition unload/reload transitions, unresolved coastline collision failure, unvalidated multi-chunk continuity and recovery, untested streaming-boundary edits, absent runtime memory/responsiveness profiling, and missing close-up viewport evidence. Passing unit tests and compilation do not satisfy those runtime gates.

The next Phase 6C acceptance run requires an isolated UE 5.6.1 Editor session. It should reproduce and instrument collision readiness per component, demonstrate actual proxy unload and reload, validate multi-chunk seams and cancellation, exercise loaded/unloaded edit boundaries, collect Insights/memory/responsiveness data at the three requested sizes, and capture close-up terrain views. Until an Editor session is authorized and available, the candidate should remain isolated. Do not proceed to Phase 6D, deploy to the city environment, or modify `L_City_World_Master` on the basis of this report.

## Safety and evidence boundaries

The user requested that Unreal remain closed. No Editor was launched for this report, and no terrain operation was executed in the protected city project. The existing city level, actors, World Partition configuration, Ultra Dynamic Sky, Ultra Dynamic Weather, roads, buildings, and city terrain were not modified. The candidate DLL remains isolated, and the source backup manifest remains available at the path recorded in section A. This report classifies earlier live evidence as prior-phase evidence and does not claim new runtime, visual, memory, or performance acceptance.

## Runtime acceptance and corrective validation — 2026-10-17

This later section records the single hidden isolated Editor session explicitly authorized in the attached Phase 6C instructions. It supersedes the earlier statement that no runtime session was authorized or run. The previous NO-GO evidence remains intact. The full coastline collision correction passed on the tested candidate binary, but the maximum-size heightmap preview still disconnects, and the final status remains **NO-GO** because World Partition transitions, full-size heightmap work, viewport proof, and responsiveness gates are unresolved.

The isolated project was `Saved/LandscapeDevelopment/Phase6Fresh/ForgeMCPDev.uproject`, session `unreal-14540`, PID 14540, Unreal Engine 5.6.1. It opened only the disposable `P6CCoast1009A` map. All edits ran outside PIE, and the Editor had no visible window handle. The candidate Editor was closed after the coastline save/reload check and heightmap transport probes. The separate city Editor (PID 27224) remained running and untouched. The protected-file audit checked all 860 baseline hashes: **860 unchanged, 0 changed, 0 missing**. Installed production plugin hashes remained at baseline. Runtime scripts, JSON evidence, screenshots, and a before-test map copy are in [the corrective runtime evidence folder](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/).

### A. Implementation changes and root causes

Three native defects or gaps were isolated in this run:

1. The prior 16 KiB input ceiling did not match Python's 512 KiB transport or the 32,768-sample heightmap contract. The receive ceiling had already been raised to 512 KiB in candidate source and compiled into the binary used in this run; a Python mock-bridge regression test verifies only Python-side 32,768-sample serialization.
2. The 1,009² coastline previously selected a collision probe from its final one-row batch at row 1008. With a component size of 63, this selected component row 16, beyond valid rows 0–15. Candidate source now selects probe Y from the full edited interval. The compiled correction passed the full-coastline runtime retest below.
3. The native socket reader still applied a fixed 10-second absolute deadline to each request and response. The 32,768- and 16,384-sample heightmap previews each failed at about 10 seconds even when the Python-side wait was extended. Source now has a bounded 60-second total client lifetime and a 10-second idle timeout, refreshing activity while receiving and sending. This source change was backed up but its candidate build stalled and was stopped; the tested DLL does **not** contain this latest deadline change, and the changed source remains uncompiled and unvalidated.

The five Landscape MCP tools remain unchanged. No new MCP tool was added. The candidate-only source and earlier pre-correction binary are backed up in [the Phase 6C corrective backup manifest](../Saved/LandscapeDevelopment/SourceBackup-Phase6C-Corrections-20261017/manifest.json). The current transport-deadline source backup is [here](../Saved/LandscapeDevelopment/SourceBackup-Phase6C-TransportDeadline-20261017/manifest.json).

### B. World Partition transitions

**Creation and persistence: PASS.** The isolated `P6CStream253A` map created a 253×253 Landscape with 16 components and four spatial proxy descriptors. Editor streaming and dynamic Editor loading were enabled. The map saved with five proxy external packages and seven external actor package files present.

**Unload: FAIL.** All four proxies began loaded. The load request returned `loaded`, still with four of four loaded. The unload request ended `transition_failed` with the exact report `loaded=4 total=4 spatial=4 non_spatial=0 editor_loaders=2.` Zero proxies unloaded. Follow-up region-load requests returned `loaded` while the proxies were already loaded; they do not demonstrate a reload transition. **Reload transition: BLOCKED.** The run therefore proves external actor saving, not streaming behavior or restart persistence. Evidence: [253² World Partition run](../Saved/LandscapeDevelopment/phase6-P6CStream253A.json).

### C. Coastline collision correction and retest

On the compiled candidate used for this run, the full coastline wrote **1,009/1,009 rows**, passed height readback, and passed complex-collision validation. Collision validation took **1,525.2 ms**; the largest reported terrain stage took **1,066.4 ms**. The post-operation height hash was `ec1ac35fe65665e41eeac97959a1319f`. The map then saved and reloaded with `persistence_validated=true`. This accepts the corrected collision probe for this isolated 1,009² coastline, but the >1-second maximum stage is a responsiveness concern and is not a frame-time measurement. Evidence: [corrective runtime results](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/corrective_runtime_results.json), [coastline save/reload check](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/coastline_reload_check.json), and [pre-test disposable map backup](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/P6CCoast1009A-before-retest.umap).

### D. Heightmap chunk continuity, cancellation, and recovery

On the 253² non-World-Partition map, 24 progressive heightmap chunks of 1,024 samples each applied hill, valley, slope, coastline, urban-flat, and repeated-hill patterns across component boundaries. Each completed chunk passed its planned-height readback hash and complex-collision check. The largest request body was 8,445 bytes; the largest Forge plan-plus-stage estimate was 6,048 bytes; the maximum recorded batch was 62.3 ms. Shared edge input samples were generated from the same global-coordinate function, including overlaps at chunk joins.

Two consecutive full hill passes produced the same whole-Landscape hash, `823bc8591e7a389d46ecd98b2f8ba81f`. Cancellation stopped after two rows; the row count remained stable after cancellation, and reapplying the same absolute-height data completed successfully. This confirms the documented partial-write behavior; it does not imply rollback. Save and same-session reload passed with identical before/after height hash `d6a733fcd2df81af09361c7f18dbeb15` and a clean map. The complete record is in [the small-chunk run](../Saved/LandscapeDevelopment/Phase6C-PreRuntime-20261017-073631/heightmap_small_chunk_acceptance.json), [the global-repeat and cancellation run](../Saved/LandscapeDevelopment/Phase6C-PreRuntime-20261017-073631/chunk_followup_acceptance.json), and [the persistence check](../Saved/LandscapeDevelopment/Phase6C-PreRuntime-20261017-073631/chunk_persistence_reload.json).

The first harness compared each chunk’s preview hash across different chunk orders. That comparison included a one-vertex halo that later chunks legitimately changed, so those per-chunk hashes were not comparable. The follow-up whole-Landscape hash test is the valid determinism check and passed. A later harness assertion also compared the map hash from before cancellation with the hash after an intentional recovery edit extending into new rows; the recovery changed that map region as designed. The separate save/reload check passed. These harness assertion mistakes are preserved in their raw files and are not counted as terrain failures.

**Maximum 32,768-sample live chunk: FAIL.** The 32,768-sample preview did not reach apply; the native bridge timed out/disconnected after about 10.6 seconds. A second 16,384-sample preview also failed after about 10.3 seconds. Neither request wrote terrain. Python's wait was raised to 60 seconds for the 32,768-sample retry, confirming the native listener's 10-second deadline as the limiting stage. The separate source-level fix is not present in the binary tested here and needs a successful build plus a separately authorized runtime retest. Evidence: [32,768-sample transport retest](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/heightmap_transport_retest.json), [16,384-sample probe](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/heightmap_16k_retest.json).

### E. Streaming-boundary editing

**BLOCKED.** No genuinely unloaded Landscape proxy was observed. Edits within, across, or into unloaded World Partition cells, load-before-edit, and safe rejection behavior were not tested. No completion claim is made for unloaded terrain.

### F. Performance and memory

Process-memory values below are sampled whole-process working set and private bytes. They are not plugin-only allocations. Plugin plan estimates are reported separately. Editor frame time, Unreal Insights traces, and plugin-owned allocation profiling were not collected.

| Test | Measured result | Process-memory peak (working set / private bytes) |
|---|---|---:|
| 253² World Partition create | 1.729 s create apply; 4 proxy descriptors | 1,660 / 2,604 MiB |
| 253² small-chunk acceptance | 24 chunks; up to 62.3 ms per batch; collision checks passed | Not separately sampled |
| 253² heightmap-validation process sample | Separate terrain-operation harness | 535.6 / 3,593.9 MiB |
| 1,009² coastline | 1,009 rows; up to 396.7 ms per batch; 33.753 s collision wait before failure | 1,295.3 / 3,638.8 MiB |
| 1,009² corrective coastline | 1,009 rows; 1,066.4 ms maximum stage; 1,525.2 ms collision validation; height and collision passed | No peak capture. A later whole-process snapshot after failed heightmap previews was 311 MiB working set / 3,474 MiB private bytes; this is not a peak or terrain-only allocation. |
| 2,041² create and bounded edit | 8.245 s create apply; 21×21 edit across the 510-quad component boundary; 62.5 ms maximum batch; 1.122 s collision validation | 813.3 / 3,769.4 MiB |

The 2,041² collision probe measured 57.03125 cm expected and 57.01991 cm actual, within the unchanged 8 cm tolerance. The Editor log also warned that the Edit Layer merge needed a minimum 1,531-pixel batch while the configured maximum was 1,024. A later settled inspection reported the layer up to date; the warning remains a performance/configuration risk for larger maps. The corrective runtime monitor could not import `psutil` from the project virtual environment, so no peak memory was captured for that run. `Responding=True` is only a coarse Windows process flag and is not frame-time evidence. **Responsiveness acceptance: NOT RUN.** Start/peak/end samples from earlier tests are retained in [the World Partition process CSV](../Saved/LandscapeDevelopment/p6c-stream253-memory.csv), [the coastline process CSV](../Saved/LandscapeDevelopment/p6c-coast1009-memory.csv), [the heightmap-validation process CSV](../Saved/LandscapeDevelopment/p6c-heightmap-validation-memory.csv), and [the 2,041² process CSV](../Saved/LandscapeDevelopment/Phase6C-PreRuntime-20261017-073631/large2041-process-memory.csv).

### G. Visual acceptance

**FAIL.** Earlier terrain-operation screenshots were byte-identical across hill, valley, flatten, smooth, and coastline captures (SHA-256 `3ad59942a2a2fe513198e796b0f9909df5da29f19eccb0dbafd13de7fd9853e6`). In the new hidden-session run, the mid-coastline screenshot is black, and the final screenshot shows a wide gray Landscape without a readable close-up of the coastline. See [the corrective progress frame](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/coastline-1009-progress.jpg) and [the corrective final frame](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/coastline-1009-final.jpg). Numerical validation passed for the coastline, but these captures do not satisfy viewport-visible progressive acceptance.

### H. Regression tests and compilation

- Full Python suite: **404 passed** in 42.55 seconds, including the new maximum-chunk Python transport test.
- Scoped Ruff checks: **passed**.
- Python byte-compilation: **passed**.
- UE 5.6.1 `ForgeMCPDevEditor Win64 Development` build for the receive-cap and collision-probe fixes: **passed**, five UBT actions, 92.55 seconds. Both `ForgeLandscape.cpp` and `MajesticForgeModule.cpp` compiled and the candidate DLL linked. See [the corrective build log](../Saved/LandscapeDevelopment/phase6c-corrective-build.log).
- That tested candidate DLL has SHA-256 `70D4852CB77B49C3E9DF6E97D4FE5822BBC3771549F4B596795AB754A2572FF5` and remains isolated under `Phase6Fresh`; the installed production DLL was not replaced.
- The later 60-second total / 10-second idle native deadline source change has **no completed build result**. The UBA build stalled at the module compile action; the non-UBA retry also stalled before producing the object or link. Both attempts were stopped when system CPU reached 100%. Logs: [UBA attempt](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/phase6c-transport-timeout-build.log) and [non-UBA attempt](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/phase6c-transport-timeout-build-no-uba.log). The existing DLL timestamp and hash remain those of the earlier successful build.
- Current transport-deadline source SHA-256: `9BCE10698BB6A9C7AD6A3288A75F2C39EF5916199A6E1D03CD36313A02905AE5`. Candidate DLL SHA-256 remains `70D4852CB77B49C3E9DF6E97D4FE5822BBC3771549F4B596795AB754A2572FF5`, timestamped before the source change. This source/binary mismatch is an explicit **do-not-deploy** condition.

The earlier compile and Python tests validate the receive-cap and collision-probe changes, and live runtime now confirms the full-coastline collision fix. The Python test does not cover the native 10-second deadline. The source-only deadline change is uncompiled and untested; it must not be deployed.

### I. Remaining limitations and safety

- World Partition unload/reload is not demonstrated; all unloaded-region editing remains blocked.
- Full 1,009² coastline height and collision validation now pass on the tested binary, followed by save and reload. Maximum-size heightmap preview remains unsupported at runtime: 16,384- and 32,768-sample previews both hit the native 10-second deadline before apply.
- The source-only 60-second total / 10-second idle transport deadline change has not compiled or run. The existing candidate DLL does not contain it.
- Close-up visual acceptance, frame-time measurement, Unreal Insights, and plugin-only allocation profiling remain outstanding.
- The current 4,194,304-sample creation cap rejects a 4,573² Landscape (20,912,329 samples). The proposed 18×18 components with 254 quads per component are geometrically expressible as 127 quads per section × two sections, but the ForgeMCP sample cap and large-world profiling still block readiness.
- The current run validated same-session map save/reload but did not test an Editor restart.
- No city asset, `L_City_World_Master`, city actor, road, building, World Partition setting, Ultra Dynamic Sky/Weather asset, or installed plugin binary was changed. A fresh post-run audit checked **860 protected files: 860 unchanged, 0 changed, 0 missing**, recorded in [the post-run hash audit](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/protected_hash_audit_after.json). The installed production Editor DLL hashes remain `2764187D2700FECE31941567830DE3658FB6C1B4088A4C8799107458280A406D` and `8C08D41B197574020B77B6FCE670B5C28F961ECC6AFEA7172E8CB182ECF68BC0`. The isolated candidate PID 14540 is closed; only the pre-existing city Editor PID 27224 remains.

### J. Final recommendation

**NO-GO — Phase 6C is not ready for Phase 6D or city-world deployment.** The 253² bounded operations, 1,009² coastline height/collision validation, cancellation/recovery, same-session persistence, and 2,041² creation/edit/save/reload evidence passed in their respective isolated runs. World Partition unload/reload failed; streaming-boundary editing is blocked; 16,384- and 32,768-sample heightmap previews time out before apply; the latest transport-deadline source fix is uncompiled; viewport frames do not show readable progressive terrain; and Editor responsiveness/peak memory have not been measured for this corrective run.

The next step is to compile the current source change when system load permits, then obtain authorization for a new isolated Editor session to test the rebuilt DLL. That session should repeat the 32,768-sample preview/apply and save/reload, then investigate genuine proxy unload/reload and streaming-boundary behavior, and collect close-up viewport plus frame-time/Insights evidence. One replacement session was used and closed; no second session was launched. Do not deploy either candidate binary to the city project or begin Phase 6D until those gates pass and are reviewed.

The machine-readable roll-up for this corrective run is [the Phase 6C corrective runtime summary](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/phase6c_corrective_runtime_summary.json). Earlier Phase 6C measurements remain in [the pre-runtime summary](../Saved/LandscapeDevelopment/Phase6C-PreRuntime-20261017-073631/phase6c_runtime_verified_summary.json).
## Phase 6C continuation — isolated Editor acceptance (2026-10-17)

**Acceptance status: NO-GO.** This continuation supersedes the earlier “Editor remained closed / no runtime acceptance” statement above. The user authorized isolated Editor sessions for these tests. Test Editors were launched hidden against the disposable Phase6Fresh project only, ran with PIE disabled, and were closed cleanly. The protected city Editor stayed separate.

### Implementation and MCP surface

The five existing typed operations remain in place: unreal_inspect_landscape, unreal_preview_landscape, unreal_apply_landscape, unreal_landscape_job_status, and unreal_cancel_landscape_job. This continuation added no new MCP tool names.

The isolated candidate’s ForgeLandscape.cpp received two final source changes, with a verified pre-change backup at the Phase 6C WP unload/frame backup. The frame action now accepts a bounded vertex region and uses that region for viewport framing; the original default still frames the full Landscape. The World Partition unload path now calls the native loader Unload, releases the editor loader adapter, and then observes descriptor state. The latter did not solve the observed proxy pinning: the selected proxy stayed loaded.

The candidate also contains the earlier corrective receive-cap, collision-probe, and transport-deadline changes. The 32,768-sample run completed with the rebuilt binary, confirming that request now passes through preview and apply without the earlier transport timeout. Current candidate source SHA-256: F4EF33FFF9756BC707E86BC11BF7CF57C639AACE278B5AC11680012101516F8A. Current isolated Editor DLL SHA-256: 79D90F18EBC6DBAD15338E0CE4209BF0A011E12796130F23E088438A48D56238. The pre-edit source backup is verified in the linked manifest.

### Build and automated checks

The UE 5.6.1 ForgeMCPDevEditor Win64 Development build **passed**: four UBT actions, including ForgeLandscape.cpp compile and candidate DLL link, in 25.69 seconds. See the [native build log](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/phase6c-wp-frame-build.log).

The full Python suite passed **404 tests**. Scoped Ruff checks and Python byte-compilation also passed. These results cover the Python contract and tests; the native editor build is a separate check.

### World Partition acceptance

World Partition Landscape creation and external actor persistence passed in isolated maps. A 1,009 × 1,009 Landscape created 256 components and 64 spatial streaming proxies; its World Partition editor streaming flags were enabled. Creation apply took about 20.03 seconds for that test configuration. A separate 2,041 × 2,041 test created 64 components and 64 spatial streaming proxies, with 65 external actor packages counted for the Landscape and proxies.

Saving the 2,041² WP map recorded backups for 65 external actor packages. Same-session map reload retained the Landscape GUID and height hash; the final inspection reported 64/64 proxies loaded, no dirty state, and the Edit Layer up to date. This confirms save/reload and external-package handling in that test, not persistence across an Unreal Editor process restart.

**Proxy unload/reload failed.** The earlier 1,009² regional unload left all four selected proxies loaded and zero unloaded. After the immediate adapter-release change, a fresh 2,041² test still left its selected spatial proxy loaded after the 30-second transition window. Another editor loader remained registered. Loaded-proxy edits crossing adjacent proxy boundaries passed height readback and collision checks; an edit requiring a truly unloaded proxy was blocked because no unloaded proxy could be produced. Runtime streaming behavior and unloaded-cell editing therefore remain unaccepted. We have not established whether another editor loader, streaming source, actor reference, or another World Partition condition is keeping the proxy resident.

Evidence: [World Partition after-release run](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/world_partition_after_release_fix.json), [scale and proxy benchmarks](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/benchmarks_world_partition_results.json).

### Terrain editing, continuity, cancellation, and performance

The corrected 1,009² coastline passed height readback and collision validation. A 32,768-sample heightmap request contained 131,291 JSON bytes, took 19.18 seconds to preview and 284 ms to apply, wrote 128/128 rows, and had a 125.66 ms maximum reported stage. Collision validation took 927 ms; expected and actual world Z differed by less than 0.007 cm. Saving and reloading preserved the height hash.

Two adjacent 32,768-sample chunks each wrote 128 rows across multiple Landscape components. Both passed height readback and collision checks; the shared-edge input formula predicted a 0 cm discontinuity, and repeat preview produced the same output hash. A 256 × 256 hill crossing component boundaries passed height and collision validation with a 173 ms maximum stage. Raise, lower, flatten, generated roughness, smoothing, and coastline test regions also passed their height/collision probes and same-session save/reload checks. The chosen high-relief 100 × 100 hill reported a 771 ms maximum stage. These are successful bounded-operation samples; they do not establish an Editor frame-time budget.

Cancellation stopped a 241-row operation after eight rows (3.32 percent) and returned cancelled_partial. The applied rows were not rolled back. The partial state was saved and reloaded successfully. Cancellation is therefore observable and bounded, but it is not transactional rollback.

| Isolated workload | Measured result |
|---|---|
| 253² Landscape, 16 components | 307 ms preview; 945 ms creation apply |
| 2,041² Landscape, 64 components | 358 ms preview; 2.93 s creation apply; save/reload passed |
| 1,009² WP Landscape, 256 components / 64 spatial proxies | 20.03 s creation apply |
| 32,768-sample heightmap chunk | 19.18 s preview; 284 ms apply; 125.66 ms maximum stage; 927 ms collision validation |
| 2,041² WP process monitor | 373 samples; peak sampled working set 1.984 GiB and private bytes 4.475 GiB |

All 373 rows in the memory CSV recorded the Windows Responding flag as true. That flag is coarse process health only. No Unreal Insights trace, Editor frame-time profile, or plugin-only allocation profile was collected. Memory totals include the entire Editor process, not just ForgeMCP. Performance and responsiveness acceptance remains **FAIL / NOT MEASURED** at the frame-time level.

Evidence: [32,768-sample retest](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/heightmap_transport_retest_after_timeoutbuild.json), [chunk and cancellation run](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/terrain_ops_chunks_cancel_results.json), [sculpt readback/collision run](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/closeup_sculpt_visual_results.json), [memory samples](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/test_editor_memory_after_fixes.csv).

### Viewport evidence and persistence boundary

A fresh hidden Editor session reopened the saved 1,009² disposable map. Project identity was Phase6Fresh, engine 5.6.1, PIE disabled. The region-aware frame action returned four distinct captures by SHA-256 for the initial view and hill, valley, and coastline regions. This confirms region framing and close-up inspection work after reload.

The staged 25/50/75-percent captures from the terrain jobs remained byte-identical to their pre-edit frames in the earlier sculpt run. The new captures were taken after framing, not during a live height-write batch. They do not prove that incremental terrain changes are visibly rendered while each batch runs. Progressive viewport-visible acceptance remains **FAIL**. The close-up captures are linked as [hill](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/final-frame-hill.jpg), [valley](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/final-frame-valley.jpg), and [coastline](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/final-frame-coast.jpg); the [capture metadata](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/final_visual_pass.json) records their distinct hashes.

Same-session save/reload passed for the tested 253², 1,009², and 2,041² maps. A full Editor process restart persistence test was not run, so that requirement remains **NOT RUN**.

### Readiness, safety audit, and deployment

The proposed 4,573 × 4,573 topology is geometrically consistent with 18 × 18 components at 254 quads per component (20,912,329 height samples). ForgeMCP’s current creation/readback cap is 4,194,304 samples, so that 9 km target cannot be created by the current implementation. The 2,041² benchmark does not justify extrapolating to 4,573². Large-world readiness is **NO**.

The post-test audit checked **860 protected files: 860 unchanged, zero changed, zero missing**. It includes L_City_World_Master, the protected Ultra Dynamic Sky content, and the installed Marketplace Forge plugin. The installed production DLL hashes remain Editor 2764187D2700FECE31941567830DE3658FB6C1B4088A4C8799107458280A406D and Runtime 8C08D41B197574020B77B6FCE670B5C28F961ECC6AFEA7172E8CB182ECF68BC0. See the [refreshed protected-file audit](../Saved/LandscapeDevelopment/Phase6C-CorrectiveRuntime-20261017/protected_hash_audit_after.json). The test Editor was closed cleanly; only the pre-existing city Editor PID 27224 remained. No city map, actor, World Partition setting, road, building, Ultra Dynamic Sky/Weather asset, or production plugin binary was changed.

**Do not deploy the candidate DLL.** It is validated only in Phase6Fresh and lacks passing proxy unload/reload, progressive viewport visibility, frame-time profiling, 4,573² capacity, and process-restart persistence. A future deployment should first pass those gates in a disposable staging project, then close every Editor using the installed plugin, verify a versioned backup and candidate hashes, install only during that closed-Editor window, and revalidate in staging before separately authorizing any production use. No city deployment or Phase 6D work was performed.

**Final recommendation: NO-GO for Phase 6D and city-world construction.** Keep development isolated while investigating why World Partition proxies remain loaded, then repeat visual-progress, frame-time, restart-persistence, and larger-capacity tests on a fresh isolated build.

## Corrective world-lifecycle validation — 2026-10-17

**Crash-recovery gate: BLOCKED. Phase 6C remains NO-GO.** This additive record preserves the earlier acceptance results above.

### Crash evidence and owner attribution

- **Crash detected and evidence preserved: PASS.** The isolated crash bundle is in [the preserved crash evidence](../Saved/LandscapeDevelopment/Phase6C-CorrectiveValidation-20261017-172604UTC/crash-preservation-20261017/). A rehash checked all 16 manifest entries with zero byte-count or SHA-256 mismatches. It includes both UE crash contexts and minidumps, the Editor logs and trace, the saved test-map copy, prior test JSON, relevant source/header, and the triage notes.
- The failing map was `/Game/ForgeMCPTests/Landscape/P6CFinal253B.P6CFinal253B`, a 253 × 253 Landscape with 16 components, World Partition disabled, and no registered editor loader adapters. The failure occurred during `GEditor->NewMap(false)` in `ForgeLandscape.cpp` at the reported line 720.
- The two reported leaked entries were the outgoing `UWorld` and its package. The preserved crash context shows a reference path through `GCObjectReferencer_0` to `Landscape_0.Heightmap_0`, then the Landscape, persistent level, and world. The native owner behind `GCObjectReferencer_0` was not identified; the preserved triage records that `ReferenceChainSearch` itself failed to resolve that link. The original crash therefore has **no confirmed strong-reference owner or root cause**.
- Controlled diagnostics on later disposable maps found the test `Heightmap_1` strongly referenced through `UEditorEngine::Trans` → `UTransBuffer` → transaction object record. At that time the transaction queue length was 1, undo count 0, Landscape editor mode inactive, and the Heightmap was in the transaction buffer. This is a confirmed owner for those test objects, **not proof that the original `Heightmap_0` crash had the same owner**.

### Corrective source and transition checks

- The Phase6Fresh candidate was backed up before editing. [All 54 source-backup entries](../Saved/LandscapeDevelopment/Phase6C-WorldLifecycleRecovery-20261017/candidate-source-backup-manifest.json) were rehashed successfully with zero mismatches.
- Candidate-only changes in `ForgeLandscape.cpp`, `ForgeLandscape.h`, and `MajesticForge.Build.cs` add transition preflight/guards, release Forge-owned transient job/loader state, use `UEditorEngine::CreateNewMapForEditing` for the supported editor lifecycle, and validate the requested World Partition initialization path before Landscape creation. The initialized empty map is saved before the Landscape is spawned. No installed plugin binary was replaced.
- **Supported Landscape-world transition cleanup: PASS for two repeated controlled transitions; original crash attribution: BLOCKED.** `P6CRecoveryTransitionA → B` and `B → C` each created a fresh 253 × 253, 16-component non-World-Partition Landscape through the supported API. Both records report that the outgoing weak world and package references became invalid after the transition. The second transition also succeeded with the live `UTransBuffer` reference chain described above. Evidence: [A](../Saved/LandscapeDevelopment/phase6-P6CRecoveryTransitionA.json), [B](../Saved/LandscapeDevelopment/phase6-P6CRecoveryTransitionB.json), and [C](../Saved/LandscapeDevelopment/phase6-P6CRecoveryTransitionC.json).
- This validates the corrected path twice without a crash, but does not establish that the historical `GCObjectReferencer_0` owner was removed or that the exact original crash was fixed. No global transaction/undo reset or forced-GC workaround was used.
- **Bounded edit persistence: PASS in the disposable non-World-Partition map.** A raised region read back at 125 cm maximum local layer height; after map save/reload the Landscape GUID and height hash matched the edited state and the map was clean. Evidence: [post-transition edit and reload record](../Saved/LandscapeDevelopment/Phase6C-WorldLifecycleRecovery-20261017/P6CRecoveryTransitionC-post-transition-edit-resume.json).
- The native UE 5.6.1 `ForgeMCPDevEditor Win64 Development` candidate build passed in 178.44 seconds. See [successful build log](../Saved/LandscapeDevelopment/Phase6C-WorldLifecycleRecovery-20261017/build-logs/phase6fresh-build-success-20261017.txt). Python Landscape/MCP regressions passed **26 tests**; scoped Ruff and Python byte-compilation passed. These checks do not substitute for the unresolved original-crash owner or live visual acceptance.

### World Partition, viewport, and persistence status

- The original crash test was **not** a World Partition map, so it does not implicate World Partition. Prior Phase 6C records document separate World Partition creation and external-package save/reload tests, with proxy unload/reload still failing. This corrective run did not perform a new Open World/World Partition acceptance test.
- **World Partition initialization and streaming correction: NOT RUN in this corrective runtime.** No new partitioned map, subsystem/region-loading acceptance, streaming proxy transition, unloaded-cell edit, or external actor package test was performed after the crash. Those checks remain gated on resolving the crash attribution. The repeated corrective maps were explicitly non-partitioned.
- **Viewport-visible acceptance: FAIL.** The native frame action returned `completed` and requested Lit view, but the captured [final viewport image](../Saved/LandscapeDevelopment/Phase6C-WorldLifecycleRecovery-20261017/P6CRecoveryTransitionC-post-transition-final.jpg) is black. It does not demonstrate visible terrain or a hill. UDS was not spawned, progressive visual updates were not accepted, and the image is not evidence of successful visual inspection.
- Save/reload was tested within the same Editor process only. **Editor restart persistence: NOT RUN.** The isolated candidate Editor is left running on Phase6Fresh and `P6CRecoveryTransitionC` for inspection; the production city Editor PID 27224 remains running and untouched.

### Safety and next gate

- A fresh protected-file audit compared 860 baseline files: **860 unchanged, 0 changed, 0 missing**. See [recovery audit](../Saved/LandscapeDevelopment/Phase6C-WorldLifecycleRecovery-20261017/protected-hash-audit-recovery.json). The candidate source backup and the separate crash-preservation bundle also rehashed with no mismatches.
- No city map or actor, `L_City_World_Master`, installed Forge plugin, production UDS/UW assets, road, or building was modified. No candidate binary was deployed, no Phase 6D work began, and no city terrain was generated.
- **Proposed corrective action:** keep the crash gate blocked until the original `GCObjectReferencer_0` owner can be established from suitable crash diagnostics or a faithful controlled reproduction; then repeat the original Landscape-world map transition and verify world/package cleanup. Only after that gate passes should a verified Open World test confirm World Partition subsystem/region loading, proxy creation and unload/reload, external-package persistence, and a readable Lit/UDS viewport. Do not claim the crash fixed or proceed to Phase 6D on the current evidence.

## Targeted Empty Open World creation correction — 2026-10-17

**Targeted map-creation result: PASS. World Partition: TRUE. Isolated Editor: OPEN and visible.** This addendum records the single authorized blank-map acceptance run. The broader Phase 6C Landscape acceptance and the historical crash-owner gate remain unresolved; this result does not supersede their NO-GO/BLOCKED status.

### Finding and implementation

UE 5.6.1's `GEditor->NewMap(false)` passes `false` as `bIsPartitionedWorld`, so it explicitly creates a non-partitioned map. The Empty Open World template is represented by `EmptyWorldPartition` in `NewLevelDialogModule.cpp` (line 459); the Level Editor passes its partitioned-world selection to `CreateNewMapForEditing` (`LevelEditorActions.cpp`, line 252). `UEditorEngine::CreateNewMapForEditing` forwards that flag to `NewMap` (`EditorServer.cpp`, lines 2121–2156), where it becomes `UWorldFactory::bCreateWorldPartition` (line 2188). The isolated ForgeMCP operation now invokes `GEditor->CreateNewMapForEditing(false, true)`: it suppresses the interactive save prompt only after the existing clean-world/lifecycle preflight, and explicitly requests World Partition.

The isolated native plugin exposes `level_create_preview` and `level_create_apply`; MCP exposes the typed tools `unreal_preview_empty_open_world` and `unreal_apply_empty_open_world`. Preview binds the plan to the current project/world and an unused bounded destination. Apply rechecks the clean outgoing world, uses the existing Landscape transition guard, creates the map, verifies the loaded world, initialized `UWorldPartition`, partition subsystem and streaming flag, verifies there are no Landscape actors, then saves the map. The durable operation receipt disallows automatic replay after an uncertain apply.

### Single-run acceptance

- Project: `G:/ForgeMCP/Saved/LandscapeDevelopment/Phase6Fresh/ForgeMCPDev.uproject`; UE `5.6.1-44394996+++UE5+Release-5.6`; isolated Editor PID `19380`; PIE disabled.
- Source world: `/Engine/Maps/Entry.Entry`. Destination: `/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017`.
- The preview confirmed the `Empty Open World` template, `CreateNewMapForEditing(false, true)`, a clean source world, and no Landscape spawn. One apply completed and returned `state=saved`.
- The resulting world was loaded and current; World Partition was enabled and initialized; the subsystem was available and streaming enabled. Landscape actor count was zero. The saved `.umap` exists (13,252 bytes; SHA-256 `C621B0AF943F8D9A2F4E6BAE68E31122E38FDA3129D54D55E758449271341A21`).
- The Editor log records the map package and two `/Game/__ExternalActors__/.../Phase6C_EmptyOpenWorld_20261017/` actor packages being saved. The acceptance result is [machine-readable here](../Saved/LandscapeDevelopment/Phase6C-OpenWorldCorrection-20261017/empty-open-world-acceptance.json); the [Editor log](../Saved/LandscapeDevelopment/Phase6Fresh/Saved/Logs/ForgeMCPDev.log) contains the corresponding save records.
- The candidate Editor window is visible and responding, and remains open on the new map. A read-only post-run check confirms the protected Editor PID `27224` is still on `L_City_World_Master` with PIE disabled. No production Editor mutation or candidate plugin deployment was performed.

### Build, tests, and limits

The isolated `ForgeMCPDevEditor Win64 Development` build passed in 94.14 seconds; candidate Editor DLL SHA-256 is `FA2B85A4CF7915E79AA7D1D26DB7BF187AAC3A73964E639AECBC7D6141C0384F`. The native build log is [here](../Saved/LandscapeDevelopment/Phase6C-OpenWorldCorrection-20261017/build-logs/empty-open-world-build-20261017.txt). The focused Python MCP/level suites passed **59 tests**; scoped Ruff and Python byte-compilation also passed. Test output is [preserved here](../Saved/LandscapeDevelopment/Phase6C-OpenWorldCorrection-20261017/automated-tests-20261017.txt). All eight pre-edit source backups rehashed to their manifest hashes.

No crash occurred during this one corrected map creation, but this single blank-world transition does not identify or clear the historical `GCObjectReferencer_0` owner, and does not prove repeated Landscape cleanup. The earlier crash report's two leaked entries were the outgoing world and package; the underlying reference owner remains unknown. No Landscape, UDS, streaming-cell test, Editor restart, or further map transition was performed. The candidate is not deployed, no city terrain was created, and Phase 6D remains out of scope.

The pre-addendum report is preserved at [the report backup](../Saved/LandscapeDevelopment/Phase6C-OpenWorldCorrection-20261017/report-backup/Landscape_Runtime_Acceptance_Phase6C_20261017.pre-open-world-correction.md).

## Controlled Landscape and UDS acceptance preflight — 2026-10-17

**Result: BLOCKED before mutation. Phase 6C overall remains NO-GO.** This run stayed on the existing Open World map and made no Editor or project-asset changes. The requested Landscape cannot be created in place through the current validated `landscape` create operation: its native apply path replaces the active world through `CreateNewMapForEditing`, which this task explicitly prohibits. I therefore did not call Landscape preview/apply, spawn UDS, alter the viewport, or save the map again.

### Isolated Editor and current world

- Current connected session: `unreal-19380`, UE `5.6.1-44394996+++UE5+Release-5.6`, project `G:/ForgeMCP/Saved/LandscapeDevelopment/Phase6Fresh/ForgeMCPDev.uproject`, PIE disabled. The process command line matched that isolated project; its window was visible and responding.
- The current world is `/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017.Phase6C_EmptyOpenWorld_20261017`. Its saved `.umap` SHA-256 still matches the prior Empty Open World acceptance record. Native inspection reports a valid current world, World Partition present, zero streaming sublevels, and **zero Landscapes**. The actor list contains eight actors, including `WorldSettings` and `WorldPartitionMiniMap`; no Landscape or UDS actor is present.
- The previous live creation record for this same map reports World Partition initialized, subsystem available, streaming enabled, and saved. The current session remains on the same map with no world transition since that record; editor-specific region-loading availability was not independently queried in this preflight.
- No Landscape job has been started since the current world was loaded. The native Landscape tick resets its job/loader state when the world changes, and the current-session calls since that transition were read-only. The adapter does not expose a list-all-jobs query.

### Landscape creation blocker

Live `landscape_info` reports `safe_create_source=false` for the existing saved Open World map. The native preview path rejects `create` unless its source world passes `SafeCreateSourceWorld`; its apply path then calls `PrepareForWorldTransition` and `GEditor->CreateNewMapForEditing(false, bWorldPartition)` (`ForgeLandscape.cpp`, lines 612 and 783–794). The typed create request also requires an absent disposable destination under `/Game/ForgeMCPTests/Landscape/`. There is no current in-place Landscape creation path for the required `/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017` world.

Because `CreateNewMapForEditing` would leave the required map, even a successful apply would violate this task. No preview was staged for a different destination and no apply or world transition was attempted. The requested 253 × 253 vertices, 252 × 252 quads, 4 × 4 components, and flat midpoint height were **not created**. Component registration, heightmap texture, collision, render state, actor package, and Landscape streaming proxy registration were not testable without the actor; no proxy count or identity is claimed.

### Ultra Dynamic Sky and viewport

- The isolated project has no separate `UltraDynamicSky` plugin entry enabled, but its project Content already contains `/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Sky.Ultra_Dynamic_Sky`; no content was copied. The asset registry identifies generated class `/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Sky.Ultra_Dynamic_Sky_C`, parent `/Script/Engine.Actor`, and 191 package dependencies (the returned dependency list was truncated). Blueprint inspection succeeded and reported compile status `BS_UpToDate` (native enum value 3) with 23 components, including the UDS Sun and Moon directional lights, two sky-light components, Sky Atmosphere, Volumetric Cloud, and Exponential Height Fog.
- No UDS actor was spawned or configured. Runtime light orientation, sun elevation, lighting conflicts, and sky rendering therefore remain unverified. No Lit-mode or camera change was made, and no Landscape screenshot was captured; visual acceptance is blocked.

### Save, checks, and acceptance status

No packages were modified or saved in this run. The existing map remains at `Content/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017.umap` with its prior accepted hash. No Landscape actor or UDS actor package exists for this test. No source correction was made, so no build or focused regression tests were run. The current operation blocker and read-only evidence are in [the preflight record](../Saved/LandscapeDevelopment/Phase6C-UDSControlledLandscape-20261017/acceptance_preflight.json).

The post-test protected-file audit checked **860 files: 860 unchanged, 0 changed, 0 missing**; see [the audit](../Saved/LandscapeDevelopment/Phase6C-UDSControlledLandscape-20261017/protected_hash_audit_after.json). The protected Editor PID `27224` remains on `L_City_World_Master` with PIE disabled. No production mutation or candidate-plugin deployment occurred. The pre-update report is preserved at [the report backup](../Saved/LandscapeDevelopment/Phase6C-UDSControlledLandscape-20261017/report-backup/Landscape_Runtime_Acceptance_Phase6C_20261017.pre-uds-landscape-test.md).

| Acceptance item | Result |
|---|---|
| World Partition | **PASS** — same live world remains partitioned; prior same-map acceptance recorded initialization, subsystem, and streaming as enabled. Current editor-region-loading availability was not separately queried. |
| Landscape creation | **BLOCKED** — current create apply transitions to another map; no in-place path exists. |
| Component registration | **BLOCKED** — no Landscape was created. |
| Streaming proxy inspection | **BLOCKED** — no Landscape proxy configuration exists to inspect. |
| Ultra Dynamic Sky | **BLOCKED** — asset is present and inspectable, but actor spawn/configuration was not reached. |
| Visual acceptance | **BLOCKED** — no Landscape, Lit-mode confirmation, or terrain viewport image. |
| Save | **NOT RUN** — no map or actor changes were made; the existing map remains saved at its prior hash. |
| Production safety | **PASS** — protected-file audit clean; production Editor and map remain unchanged. |
| Phase 6C overall | **NO-GO** |

The isolated Editor remains open on the existing Empty Open World map. No new level was created, no Landscape/UDS actor was added, no streaming unload/reload was run, no Editor restart occurred, and Phase 6D did not begin.

---

## Controlled in-place World Partition Landscape acceptance — 2026-10-17

This addendum records the approved isolated test after the earlier blocked preflight. It preserves the prior entries above. The isolated editor remains open on the same saved map for inspection.

### Crash evidence and correction status

- The earlier crash bundle remains preserved at [the crash evidence directory](../Saved/LandscapeDevelopment/Phase6C-CorrectiveValidation-20261017-172604UTC/crash-preservation-20261017/). Its recorded leak entries were the outgoing `UWorld` and its package. The crash context led through `GCObjectReferencer_0` to a Landscape heightmap and its owning level/world, but the native owner behind that referencer was not identified. A transaction-buffer reference found in a later test was not proof of the original crash owner.
- The crash map was `/Game/ForgeMCPTests/Landscape/P6CFinal253B`, which had World Partition disabled. It is invalid as World Partition acceptance evidence, though still valid as evidence of a crash in the non-partitioned map-transition path.
- This run used `/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017`. Live inspection confirmed World Partition, the World Partition subsystem, the Landscape subsystem, editor streaming, and editor-region loading were enabled. The map uses external actors.
- The new `create_in_place` route did not call `NewMap` or `CreateNewMapForEditing`; it created in the current approved test world. No crash occurred in this route. **The original map-transition crash has not been reproduced and its root cause is not confirmed or fixed.** This run demonstrates a scoped path that avoids that transition.

### Implementation

- Added the typed `create_in_place` Landscape action in [landscape.py](../server/core/landscape.py) and its native UE editor implementation in [ForgeLandscape.cpp](../Saved/LandscapeDevelopment/Phase6Fresh/Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp). The native path is restricted to the exact Phase6C map; it requires a saved World Partition world, initialized subsystems and editor loading, no existing Landscape actor or proxy descriptors, and no active Landscape loader. It reuses native Landscape import, the `ForgeTerrain` Edit Layer, the Landscape subsystem grid conversion, save, and height readback. The response reports `world_transition_performed: false`.
- Added a similarly exact-map allowance for `load_region` only, so saved proxies can be brought into view after an editor restart. `unload_region` remains blocked on this map. The existing new-map `create` operation remains available with its original transition guard.
- Added the bounded request contract test in [test_landscape.py](../tests/test_landscape.py) and updated the Landscape tool description in [main.py](../server/main.py).
- Source, prior report, initial map, and the previously loaded candidate DLL/PDB were backed up before changes. Hashes are in [backup-manifest.json](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/backup-manifest.json); the source checkpoint before the load-only extension is also preserved in that evidence folder.

### Runtime and persistence results

- The reviewed preview and apply created one 253×253 Landscape: 4×4 components, 63 quads per component, one section per component, 100 cm XY scale and 100 Z scale. The native apply returned `completed`, `saved: true`, `height_readback_validated: true`, and `created_in_existing_world: true`. The test remained outside PIE.
- Inspection found 16 components and 16 registered collision components, a `ForgeTerrain` Edit Layer, and a flat midpoint height field (`min_local_cm = max_local_cm = 0`). The initial full-field height hash was `936985f47d62be84987dbd0e6189ce17`.
- World Partition produced four spatial Landscape Streaming Proxy descriptors and five Landscape proxy packages including the main Landscape actor. The current-level save preview covered nine packages (the map and eight external actor packages); the UDS actor package was the new package saved by that operation. Save reconciliation recorded `completed` and matching saved-file hashes. The package details are in [disk-package-hashes.json](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/disk-package-hashes.json).
- Ultra Dynamic Sky was already present in the isolated project at `/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Sky`. Blueprint inspection reported `BS_UpToDate` and 23 asset components. One actor was spawned through the typed actor preview/apply path, labeled `Phase6C_UltraDynamicSky`, then saved as an external actor. It survived the editor restart. The UDS asset itself was not edited.
- After a graceful restart of only the isolated editor, the same Landscape GUID, the UDS actor, and all four proxy descriptors were present. World Partition had loaded one proxy and left three unloaded for the editor's initial region. A reviewed `load_region` operation for vertices 0–252 then completed at progress 1; status confirmed four loaded and zero unloaded proxies. Full height readback returned the original hash, and all 16 components and collision components were registered. The operation did not save or alter height data.
- The in-memory viewport capture after the full region load shows the complete flat Landscape under the UDS sky in Lit mode: [viewport-after-region-load.jpg](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/viewport-after-region-load.jpg). No terrain sculpting was performed.

### Build, tests, safety, and remaining scope

- The final `ForgeMCPDevEditor Win64 Development` build succeeded with UE 5.6.1. The build log and candidate DLL hash are in [build-result-final.json](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/build-result-final.json). Python verification passed: **25 Landscape tests**, Ruff, and Python byte-compilation.
- The protected-file audit checked **860 files: 860 unchanged, 0 changed, 0 missing**; see [the current audit](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/protected-safety-check/protected_hash_audit_after.json). The production editor stayed on `L_City_World_Master`; no production city, UDS, or weather assets were touched, and no production plugin binary was replaced.
- This validates small in-place WP Landscape creation, save, editor-restart persistence, proxy descriptor persistence, and native region loading. It does **not** validate the original crash fix, explicit proxy unloading/cancellation, terrain raising/lowering/flattening/smoothing/coastlines, cross-component edit seams, physics collision response, multi-kilometre memory/performance, or Phase 6D. The editor stayed connected and responsive for these small operations, but no frame-time or large-terrain benchmark was run. The startup log also contains asset-linker warnings for missing Interchange script packages referenced by existing UDS assets; the actor rendered in this test, but those references were not separately resolved.

| Acceptance item | Result |
|---|---|
| Crash evidence preserved | **PASS** — prior crash bundle retained; no new crash. |
| Original crash root cause | **UNRESOLVED** — this run avoided the NewMap transition and did not reproduce the original operation. |
| World Partition test map | **PASS** — exact saved map, initialized subsystems, editor streaming enabled. |
| In-place Landscape creation | **PASS** — 253×253, 16 components, saved with height readback. |
| Proxy persistence and region loading | **PASS for load** — four descriptors survived restart; all four loaded through the bounded region loader. Explicit unload remains untested. |
| UDS actor and viewport | **PASS for this test** — actor saved/reloaded; full flat Landscape is visible beneath the sky. |
| Save/restart persistence | **PASS** — same Landscape GUID and full height hash after restart and full-region load. |
| Collision | **PARTIAL** — 16 collision components registered; runtime physics response not tested. |
| Terrain sculpting and large-scale performance | **NOT TESTED** — outside this controlled creation run. |
| Production safety | **PASS** — 860/860 protected files unchanged; production editor untouched. |
| Phase 6C overall | **NO-GO** — the original crash root cause, unload/cancel behavior, terrain edits, and scale acceptance remain open. |

Phase 6D did not begin. The isolated editor is left open on the test map with the full Landscape region loaded.

### Resolved execution notes

The first current-level save apply returned preview_not_found because the preview and apply were run in separate short-lived MCP server processes; no write occurred. A fresh preview and apply in one persistent MCP client session completed and reconciled successfully. An earlier build attempt caught a C++ C2181 brace-scope error in the new branch split; the scope was corrected, the legacy transition guard lifetime was restored, and the final build passed.
The exact-map allowlist in this run enables create_in_place and load_region only. Raise, lower, flatten, smooth, coastline, and other terrain-edit actions remain restricted on this Open World map and were not exercised; native inspection reports mutation_supported=false there.
The final native loader poll is recorded in [region-load-job-status.json](../Saved/LandscapeDevelopment/Phase6C-InPlaceLandscape-20261017-215322UTC/region-load-job-status.json).

---

## Phase 6C lifecycle gate recheck — 2026-10-17

### Gate result

**Overall Phase 6C: NO-GO. Stage A: BLOCKED. Stages B and C: NOT RUN.** The mandatory unload/reload gate did not pass, so no terrain edit, save/reload terrain test, or editor-restart terrain test was attempted. No force-unload was used.

### Verified map and streaming state

The isolated Editor is running UE 5.6.1 on the existing disposable map `/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017`, with World Partition, editor streaming and region loading enabled, and PIE disabled. The same Landscape GUID (`8F6F1EE446FB746B38424FBC8FB933FB`), 253 × 253 height field, and pre-restart height hash (`936985f47d62be84987dbd0e6189ce17`) were observed after restart. Its 16 components and 16 registered collision components remained present, layers were up to date, and the map was clean. Four spatial Landscape Streaming Proxy descriptors were present and all four were loaded.

Two loaded user-created editor regions were restored after restart, both labeled `Last Loaded Region`: a full-map region and a point region at the origin. The point region intersects `LandscapeStreamingProxy_0_0_0` (GUID `7619638C4097AEB2B6FEFBBC0630269D`). The adapter exposes unload only for a live Forge loader created in the current session; the prior session’s loader ID returned `job_not_found`. It cannot safely release either restored region by that old ID. Because the origin region independently references a proxy, attempting to unload around it would not establish the required safe unload. Stage A therefore stopped before an unload request. Reported cell intersections are derived from the editor spatial hash, not runtime PIE streaming-cell IDs.

### Candidate implementation and checks

Only the isolated `Phase6Fresh` candidate was changed. [ForgeLandscape.cpp](../Saved/LandscapeDevelopment/Phase6Fresh/Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp) adds bounded proxy-descriptor diagnostics and permits exact-map `unload_region` preview/apply only for a live user-created Forge loader. It does not yet provide a typed way to release the restored editor-region adapters. No terrain algorithm or production source was changed. Source and candidate binary backups are preserved in [the Stage A evidence folder](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/source-backup-before-stage-a/).

The UE 5.6.1 `UnrealEditor Win64 Development` candidate build succeeded, including `ForgeLandscape.cpp` compilation and plugin link. Focused Python tests passed: **27 passed** (`tests/test_landscape.py` and `tests/test_mcp_stdio.py`). Build and test records are [build-result-stage-a.json](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/build-result-stage-a.json) and [python-test-results.json](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/python-test-results.json).

The previous isolated Editor exited normally. Its log records saves for four external Landscape proxy packages while the `.umap` hash stayed unchanged; no new crash was detected. The candidate Editor was then restarted on the same map and remains open for inspection. The historical `GCObjectReferencer_0` world-GC leak cause remains **UNRESOLVED**; this recheck did not reproduce the original `NewMap` operation.

### Safety and evidence limits

The protected-file audit checked **860 files: 860 unchanged, 0 changed, 0 missing**. The production Editor remains connected to `L_City_World_Master`, PIE disabled; no production assets or binaries were modified or deployed. The audit also lists 660 current root `Content` files outside its pre-run manifest; with no baseline inventory for those paths, they cannot be attributed to this run.

The saved post-restart viewport image shows the unchanged flat Landscape under the UDS actor; it is not a sculpting demonstration. Height integrity is verified only for the unchanged restart baseline. No unload/reload acceptance, terrain raising/lowering/flattening/smoothing, persistence of terrain edits, or large-terrain performance test is claimed. The recorded evidence and gate states are in [stage-acceptance.json](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/stage-acceptance.json), with fresh session identity in [final-session-reverification.json](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/final-session-reverification.json) and the viewport capture at [viewport-after-candidate-restart.jpg](../Saved/LandscapeDevelopment/Phase6C-Lifecycle-20261017-20261017-223254Z/viewport-after-candidate-restart.jpg).

The next required engineering change is a safe, typed way to inspect and release Forge-owned editor-region references that survive a restart, with identity and ownership checks. Until that is implemented and Stage A unload/reload passes, Stage B and Stage C remain gated off. Phase 6D and city terrain construction have not begun.
---

## Crash forensics and isolated recovery — 2026-10-18 UTC

This addendum records the RDG crash investigation and read-only recovery. The full report and evidence are in [the timestamped forensics folder](../Saved/LandscapeDevelopment/Phase6C-CrashForensics-20261018T0111Z/crash-recovery-report.md). The previous Phase 6C results remain intact.

The isolated Editor crash is confirmed at 2026-10-18 01:11:53.532 UTC (2026-10-17 21:11:53.532 local), PID 16844, on the existing World Partition Open World map. The failing assertion was FRDGTransientRenderTarget::Release() at RenderGraphResourcePool.cpp:266, on Foreground Worker #0. The call stack proceeds through RDG transient render-target release, reference-pointer destruction and task/log-scope teardown. The minidump does not distinguish whether the reference count became negative or the lifetime state left Allocated. The exact root cause is **UNRESOLVED**. No shutdown sequence, Landscape mutation, save or World Partition operation is evidenced immediately before the failure. Exact Editor activity is **UNKNOWN**. No leaked object/package names are associated with this RDG assertion; the earlier GCObjectReferencer world-GC issue remains separate and unresolved.

Crash evidence, minidump analysis, source excerpts and hashes were preserved before launching a replacement. Only the isolated Phase6Fresh project was launched, visibly, on the same map. Its session (unreal-27744, PID 27744) was verified on /Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld_20261017, PIE disabled. The read-only native baseline recorded the existing 253 × 253 Landscape, 16 components, 16 registered collision components, four loaded streaming proxies, ForgeTerrain hash 936985f47d62be84987dbd0e6189ce17, flat 0 cm height range, World Partition/editor streaming enabled, and the UDS actor present. All 1,286 isolated Content files remained hash-identical through the observation. A final native Landscape reread was unavailable because the Python host lacked the MCP SDK; connected project identity was reverified after the window.

The two restored loaded editor loaders were tied to per-world FBoxes in EditorPerProjectUserSettings.ini and the UE 5.6.1 LoadLastLoadedRegions() implementation. They are engine-restored adapters owned by the current UWorldPartition registry; the persisted identity is world path plus bounds. One is the origin point and one spans the full Landscape. Their overlap with the origin proxy and all four proxies respectively was recorded. Neither was released or unloaded.

The isolated Editor remained responsive for about 10 minutes 32 seconds and is left open on the original map. Private memory increased about 41 MiB; working set decreased. The available log had no new fatal/assert entry, but stopped updating shortly after startup, so the bounded observation does not establish a crash fix. Production remains on L_City_World_Master, PIE disabled. The protected audit found 860/860 files unchanged, 0 changed, 0 missing; 660 root Content files outside the old manifest remain un-attributed and untouched.

| Gate | Result |
|---|---|
| Crash evidence preservation | **PASS** |
| Timeline reconstruction | **PARTIAL** |
| RDG root cause | **UNRESOLVED** |
| Production isolation | **PASS** |
| Isolated Editor recovery | **PASS** |
| Landscape integrity | **PASS against native baseline and unchanged content hashes**; final native reread unavailable |
| World Partition inspection | **PASS, read-only** |
| Stability observation | **PASS for approximately 10.5 minutes** |
| Stage A | **BLOCKED** |
| Stage B / Stage C | **NOT RUN** |
| Phase 6C | **NO-GO** |

No prior successful creation/save/restart evidence was altered. No lifecycle mutation, terrain sculpting, package save, code change, engine change, production edit or deployment occurred in this recovery. The Editor remains open for inspection. Do not resume Stage A or begin Stage B/C until separately authorized and the unresolved crash/lifecycle gates are addressed.
