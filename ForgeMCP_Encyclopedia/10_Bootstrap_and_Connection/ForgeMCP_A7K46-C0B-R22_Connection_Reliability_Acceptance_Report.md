# ForgeMCP Stage A7K46-C0B-R22 — Connection Reliability Acceptance

Date: 2026-10-22 UTC  
Engine: Unreal Engine 5.6.1 / 44394996  
Disposition: **FAIL for reliable explicit native connection.** One isolated host launch was consumed. No alpha candidate was staged or official Engine file changed. Production Phase 6C remains **NO-GO**.

## Finding and correction

R20/R21 source and correlated evidence were reviewed. R21 authenticated native startup `health` and `project_info`, then a foreground `unreal_project_info` and periodic `health` overlapped; both listener subprocesses were created but timed out before their first Python marker. The exact reason those children did not reach that marker remains **unproven**. A persistent identity worker was evaluated but not introduced: bounded IPC, worker-crash supervision and shutdown ownership would enlarge this security-critical change without evidence that the worker would eliminate the stall.

The R22 correction serializes isolated-host identity probes in `ConnectionManager`, lets periodic health skip a cycle while one is active, and applies the original **30-second aggregate deadline** from the start of queueing through the process/listener probe. Every accepted request still runs a fresh PID, creation-time, executable, exact project argument, IPv4/IPv6 listener-owner and loopback check. Cancellation retains the lock until its existing probe thread ends. Queue expiry fails closed; no positive identity cache, token bypass, timeout increase or new worker was added. This removes observed competing helper launches but was not claimed as a proven fix for the R21 stall.

| Isolated source file | Before SHA-256 | R22 SHA-256 |
|---|---|---|
| `server/core/connections.py` | `8CC4641A55919CFE9327EFE4E234638C0B86C4753D6B94870DA31549573CA66A` | `4182A97910B4449A4ACD011E7400A4A0886405E23D27D9EEF25835FD8AD382CF` |
| `server/core/process_identity.py` | `025BE1C16734DB4D15EBAD82F7931257E0A5F85DD6102E931660AC247ADA19CC` | `EF55D9179BB05A8F83A09F0777ECF78ACEA83EFD80D9446AA32ECE6BFAEDE383` |
| `server/core/connection_monitor.py` | `559A1515487D47D97DD0469925178E8B585B8609BA245C8` | `33BBF9455975893EB7A2D7B0C0D3AC069182EB805184B7FB2518DEC8A181963F` |
| `tests/test_host_config.py` | Existing R20 test source | Two new serialization/queue-expiry tests; `FD22BA298B44A266FBED65E0BF34997F3DA3C4621E8203F5C28555C5D2AF7221` |

The R20 listener and bootstrap files were not edited. Project-local native Editor, Runtime and project DLLs retained their previously verified R7 hashes (`A79131D3…C5EC37`, `2DB7050D…102FFC62F`, `E618A09C…52DD21A7`). No native build or plugin load/reload was initiated by R22.

## Offline gate

Focused host, connection, security, dirty-package and native-contract tests: **102 passed in 8.96 s**. The new tests show that simultaneous requests run fresh checks sequentially and that a queued request expires without starting another probe. Existing helper failure/malformed-output tests still fail closed. Ruff `check server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. A persistent worker was not implemented, so worker-crash behavior is not claimed. These checks established readiness for the one authorized host attempt, not live reliability.

## One live attempt

Immediately before launch, passive OS metadata still identified disposable PID **42880**, creation **2026-10-22T06:37:06.5248750Z**, exact StageA7G `UnrealEditor.exe`, exact C0B disposable `.uproject` argument, and unique `127.0.0.1:59863` listener owned by that PID. The private `unreal-42880` registration and the fresh combined identity preflight passed; the client preflight took **2,167.417 ms**. No other Editor was substituted or contacted.

One R22 isolated host launched using C0B source, private registration, stage-owned correlation logs and `preservation_readonly`. MCP initialization took **5,834.026 ms**. Host stderr records real authenticated native startup `health` and `project_info`. The actual catalog had exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh` and `unreal_inspect_world_save_scope`, all with `readOnlyHint=true`. Missing and unallowlisted IDs failed as `session_id_required` (**4.783 ms**) and `session_not_allowed` (**5.063 ms**) before native contact.

The explicit `unreal_project_info` returned `identity_preflight_failed` after **30,016.128 ms**. Sanitized host stderr identifies `listener_timeout`; this request never reached Unreal token validation or its native socket. No foreground request retry or second host launch occurred. The live client exited its host context. Its reported `ExceptionGroup` on context exit does not change the captured tool failure category.

The correlated R22 logs distinguish this run from R21: startup health and project-info probes completed with child markers. The later periodic-health probe and foreground project-info probe timed out **sequentially**, not in overlapping listener execution. Both parent records reached `popen_return` and then `listener_timeout`/`listener_child_reaped`; neither has a child marker file. The health child PID was **18256**, with **28,625 ms** remaining at listener launch; the foreground child PID was **40224**, with **28,734 ms** remaining. Thus removing overlapping probes was insufficient. Process creation returned; the remaining boundary is between child creation and first observable Python/marker execution, which can include interpreter initialization or marker-file access. The precise blocker remains **UNKNOWN**. No IP Helper query start was recorded for either failed child.

## Preservation and release gate

No dirty-package inspector ran because explicit project-info acceptance failed. There is no package snapshot or inspector side-effect baseline. The five monitored disposable Content/Config file hashes were identical before and after the host context. This bounded filesystem result does not prove full in-memory preservation. The actual connection indicator was not safely observed and is **NOT VERIFIED**. No asset, package, Landscape, source binary, Editor lifecycle, A7K41 or production-city operation was performed.

The host context exited. The disposable Editor remained running at the final passive PID/start check. No alpha candidate was staged because explicit native communication reliability, dirty inspection and indicator acceptance did not pass. Official-engine migration is **NOT AUTHORIZED**.

| Gate | R22 result |
|---|---|
| Host correction | **FAIL as a reliability fix**; serialization and bounded queueing passed offline, but live failure persisted. |
| Live authentication | **PASS only for startup health/project-info**; explicit tool request did not authenticate. |
| Explicit `unreal_project_info` | **FAIL** — listener identity timeout before native socket. |
| Repeated request reliability | **FAIL** — no successful explicit foreground request. |
| Dirty inspector | **NOT TESTED**. |
| Green indicator | **NOT VERIFIED**. |
| Alpha candidate | **NOT STAGED**. |
| Production migration | **NOT AUTHORIZED**. |

Evidence is preserved under `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R22-20261022T181115Z-ebe09329fcad49a3a048d166df0ea8dd`. `evidence/result.json` SHA-256 is `6D90B817F054F8AD64529BDED291E569BE26931C4CD53E214939147442F5D7E8`. Parent/child logs and sanitized host stderr remain in `logs`; no prior evidence was deleted.

**Architecture-level blocker:** repeated creation of a Python listener helper remains on the request-critical path, and two serial live launches still failed before their first child marker. A future correction should remove that startup boundary through a supervised long-lived worker or an in-process bounded IP Helper query, but only with explicit per-request fresh-query IPC/timeout, worker crash invalidation, strict owner cleanup and security regressions. R22 does not start that next stage automatically. **Final verdict: FAIL.** Production Phase 6C remains **NO-GO**.