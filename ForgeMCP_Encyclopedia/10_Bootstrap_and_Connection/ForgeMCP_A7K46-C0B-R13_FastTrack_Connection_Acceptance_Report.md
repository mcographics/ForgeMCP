# ForgeMCP Stage A7K46-C0B-R13 — Fast-Track Connection Acceptance

Date: 2026-10-22 UTC  
Engine target: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **BLOCKED at the authenticated project-info request.** Exactly one isolated host was launched. It exposed the four required read-only tools and rejected missing and unauthorized session IDs, but its exact-session process preflight timed out before sending a native request. No native inspector ran. Production Phase 6C remains **NO-GO**.

## Yellow indicator meaning

The C0B plugin source `source/Plugins/Forge/Source/MajesticForge/Private/MajesticForgeModule.cpp` controls the per-Editor indicator. `IsForgeMcpConnected()` requires a live listener and a last authenticated native request no more than six seconds old (lines 128–132). `ConnectionDotColor()` is red if the listener is absent or no request has authenticated, amber/yellow if a previous authenticated request is older than six seconds, and pulsing green while that request is recent (lines 145–157). `ConnectionStatusText()` distinguishes stopped, waiting, connected, and interrupted states (lines 134–143). The timestamp is set only after token validation in native request handling (line 377). `BuildUiState()` publishes listener, connected, interrupted, endpoint and session fields (lines 242–251).

This state belongs to each plugin instance in its own Unreal Editor process. Yellow is an authenticated-activity age indicator; by itself it does not prove that the MCP host crashed, that authentication is currently failing, or that a registration is stale. This short-lived test did not visually observe the disposable Editor's dot during the active host. The R13 host never completed a native authenticated request, so R13 cannot establish that the dot became green. No UI semantics or plugin binary were changed. A permanent green state would require genuinely recent authenticated activity; the six-second rule should not be bypassed to change the display.

## R12 client repair and passive preflight

The original R12 client remains unchanged at `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R12-20261022T152009Z-7435095744d7456ca0f7429ccc3c60db/evidence/runtime_client.py`, SHA-256 `D54CA09FD045BA2B21C0C4B8EF9EC9157461A203E2DF9E39EEA7F301281C6BB6`.

A stage-owned copy was placed at `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R13-20261022T153922Z-a27704896d83405db3b7c0b3027a69dd/evidence/runtime_client.py`, SHA-256 `D51866D6C86E2D9A367653F8D88808C9484F4CF353FB28FBBB32D130AE1EFFBA`. It preserves inherited environment entries, adds the C0B source to `PYTHONPATH`, and sets the client working directory to that source before the identity probe. The latter matters because `G:\ForgeMCP` contains another top-level `server` package that won Python's import resolution when the client started there. A fresh child using `G:\ForgeMCP\.venv\Scripts\python.exe` from the isolated source resolved `server.core.windows_tcp_listener` to the exact C0B source file. The host parameters also use that interpreter, source working directory, and isolated environment. No `process_identity.py`, listener helper, authentication, or native plugin source was edited.

Fresh passive OS checks matched disposable PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, owner `ALIENWARE-PC\Kenne`, exact StageA7G `UnrealEditor.exe`, and the exact C0B disposable project command-line argument. The private registration identified `unreal-42880`, PID 42880, port 59863 and loopback host without emitting its token. A direct read-only Windows listener check returned the unique row `(42880, 127.0.0.1)` at that port. The stage-owned combined preflight then passed with that same process start and listener. The existing 30-second fail-closed process identity budget was retained. R11 source hashes matched: `process_identity.py` `E7A812F17D3B71806C21D2FA439CA8D4E2CD38F5C4AD06EE36E2528E68F7F2C6`, `windows_tcp_listener.py` `992ABD7AEB9CEA39C4DCEF399334374A4360E2F4706C21BADCAF90E941F0850B`, and `test_host_config.py` `CF4EDCDC0C7C27959186B32F395C9515B52FCF8D6D88DE53479C9808C24B250B`. The three disposable mapped project/plugin module files matched the R7/R8 SHA-256 identities. No module was rebuilt or loaded by this stage.

## One isolated host and connection result

The R13 client used the existing private registration, exact `unreal-42880` allowlist, `preservation_readonly` profile, private root, and source working directory. It launched **one** dedicated host. The actual catalog was exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh`, and `unreal_inspect_world_save_scope`; every entry reported `readOnlyHint=true`. A missing session ID returned `session_id_required` in 5.058 ms, and an unallowlisted ID returned `session_not_allowed` in 4.661 ms. No mutation tool or shared-session fallback was exposed.

The single `unreal_project_info` call for `unreal-42880` returned `identity_preflight_failed` after **30,044.634 ms**. The sanitized host stderr specifies **`listener_timeout`**; it also records that subsequent internal health handling was rejected for the same reason. The host-side repeat process preflight failed before a native socket exchange. The pre-host client probe and direct listener lookup had passed, so the cause of the host's 30-second listener-helper stall is **unknown**. This result is neither an observed Editor identity mismatch nor proof of a native handler failure. Authentication to Unreal and native `project_info` were **not verified** in R13. The R8 authenticated `project_info` remains historical evidence only.

The stage stopped at this failed gate. It did not retry `project_info`, launch another host, request the dirty-package inventory, or call either remaining native inspector. No snapshot ID, dirty rows, current-world response, World Partition/save scope, mesh response, or native timing exists for R13. Save As remains blocked from earlier source evidence; this stage did not test or authorize saving. No suitable already-loaded StaticMesh was independently identified, so its positive-case status is **NOT TESTED**.

## Preservation and lifecycle audit

The client captured five Content/Config files before host launch and after the failed host context. Their recorded SHA-256 values show **no changed Content/Config file** during that window. This comparison does not prove full loaded-package identity or exclude ordinary Editor background activity outside those paths. No native inspector executed, so inspector side-effect acceptance is **not established**. The original R11 source and compiled module hashes were checked before the attempt; no source edit, build, plugin deployment, asset load/create, save, discard, or Landscape operation was issued.

The host context exited. A post-run process check found no R13 isolated host process; its empty `server-15492.log` and sanitized `host-stderr.txt` remain under the R13 stage logs. An exit code was not retained, so cleanup is confirmed as process absence rather than exit-code-zero. Disposable Editor PID 42880 remained present with the pinned creation time and executable at the final passive check. Neither it nor protected A7K41 was closed, restarted, connected through a host, or modified. The earlier R7 telemetry anomaly and R8 configuration startup change were left untouched.

Evidence is under `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R13-20261022T153922Z-a27704896d83405db3b7c0b3027a69dd`. `evidence/result.json` contains sanitized request outcomes, timings, catalog, client preflight and bounded file snapshots. No credential was copied into this report.

## Independent acceptance gates

| Gate | R13 result |
|---|---|
| Host operational | **PARTIAL** — one host initialized and served the four-tool catalog; its repeat listener identity preflight timed out. |
| Authentication verified | **NO** — the exact-session call stopped before native authentication. |
| Native inspection operational | **NO / NOT TESTED** — no native handler response. |
| Status indicator verified | **NO** — source semantics established; live disposable color not observed. |
| Preservation acceptance | **BLOCKED** — bounded Content/Config hashes unchanged, but no inspector ran and no complete package baseline exists. |
| Production readiness | **NO-GO** — A7K41 untouched and Landscape acceptance not attempted. |

The narrow next action is an offline diagnosis of the R13 host's `listener_timeout` under the actual isolated-host child environment, retaining exact PID/start/project/listener checks and the 30-second failure boundary. Capture sanitized helper phase, exit and stderr evidence without retrying this consumed R13 host authorization. A later single-host retest requires separate authorization. Do not patch the native plugin or infer that yellow can be fixed by a cosmetic status change.
