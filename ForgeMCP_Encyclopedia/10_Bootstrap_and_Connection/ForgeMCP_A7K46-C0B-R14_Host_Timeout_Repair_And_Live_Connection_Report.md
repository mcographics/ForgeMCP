# ForgeMCP Stage A7K46-C0B-R14 — Host Timeout and Live Connection Verification

Date: 2026-10-22 UTC  
Engine: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **BLOCKED. One authorized host launch was consumed; the repeat host identity preflight returned `listener_timeout`. No native request reached Unreal. No source repair was made because the blocking phase and cause remain unproven.** Production Phase 6C remains **NO-GO**.

## R13 failure and targeted diagnosis

R13's preserved `evidence/result.json` and `logs/host-stderr.txt` show that the dedicated host initialized, exposed the four-tool catalog, rejected missing/unallowlisted sessions, and returned public `identity_preflight_failed` for the exact-session `unreal_project_info`. The sanitized host log identifies the internal category `listener_timeout` after about 30 seconds. In `source/server/core/process_identity.py`, the host checks a filtered `Win32_Process` row through PowerShell, then starts `[sys.executable, '-m', 'server.core.windows_tcp_listener', port]` with the remaining portion of one 30-second deadline. The listener child receives a copy of the host environment. The R13 client passed the C0B source working directory and `PYTHONPATH` to the host; its own pre-host combined identity probe succeeded. The listener module is the isolated `source/server/core/windows_tcp_listener.py`; its intended path queries both IPv4 and IPv6 `GetExtendedTcpTable` owner-PID tables, serializes one JSON result, and fails closed on malformed/failing family data.

R13 did **not** retain timestamps inside the listener child. Its log therefore cannot distinguish child launch/import, IPv4 query, IPv6 query, JSON output, or pipe collection as the stalled phase. A timeout category alone is not evidence that the IP Helper API stalled. `connections.py` records the sanitized identity category and returns `identity_preflight_failed` before opening the native socket. The 30-second limit, exact session/registration checks, and authentication requirements remain intact.

A stage-owned offline diagnostic used the same C0B Python executable, source working directory, source `PYTHONPATH`, and private temporary/profile location to run the actual `WindowsProcessIdentityProbe` on the disposable PID and port. It succeeded in about 15 seconds; its filtered PowerShell process-query child alone took **12,875 ms** and exited 0. It returned PID **42880**, start **2026-10-22T06:37:06.5248750Z**, listener owner **42880**, and `127.0.0.1`. This proves the combined predicate can pass in a fresh host-equivalent process, but does not reproduce or explain R13's timeout. The diagnostic wrapper did not preserve trustworthy per-phase markers inside the helper, so no deeper phase attribution is claimed. No diagnostic child was deliberately left running.

**Root cause: UNKNOWN.** No change was made to `process_identity.py`, `windows_tcp_listener.py`, `connections.py`, timeout accounting, or the native plugin. A guessed API, timeout, or authentication patch would weaken the evidence boundary. Future diagnostics need timestamped markers written by an R14-style stage-owned helper at import, IPv4 start/end, IPv6 start/end and serialization, plus parent child-start/exit/timeout data and bounded sanitized stderr. The present stage did not obtain that full marker record.

## Offline checks and identity gate

Focused pytest on `test_host_config.py`, `test_connections.py`, `test_security.py`, `test_dirty_packages.py`, and `test_native_plugin_contract.py`: **98 passed in 8.14 seconds**. Ruff `check server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. These are offline checks; the separate R11 synthetic listener table suite was not rerun here. No source file was edited to satisfy tests.

Before the host launch, the R14 stage-owned copy of the runtime client used the isolated source `PYTHONPATH` and source working directory. Its fresh combined `WindowsProcessIdentityProbe` passed. Passive OS data also matched the historical disposable Editor PID 42880, exact start time, owner `ALIENWARE-PC\Kenne`, StageA7G executable, exact disposable `.uproject` argument, private `unreal-42880` registration and unique `127.0.0.1:59863` listener. The R11 process/listener source hashes and R7/R8 mapped module identities were unchanged from the R13 baselines. No token value was emitted. The protected A7K41 session was not contacted.

## One live host attempt

The one dedicated R14 host started with the existing private registration, exact `unreal-42880` allowlist and `preservation_readonly` profile. Its actual catalog contained exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh`, and `unreal_inspect_world_save_scope`, each with `readOnlyHint=true`. A missing session ID returned `session_id_required` in **4.476 ms**; an unallowlisted ID returned `session_not_allowed` in **4.877 ms**. No mutating tool or shared-session fallback was exposed.

The single exact-session `unreal_project_info` call returned `identity_preflight_failed` after **30,180.448 ms**. The sanitized host stderr again recorded **`listener_timeout`**. The client stopped there. There was no native health/project-info response, authenticated Unreal exchange, dirty-package inventory, world-save-scope call, or StaticMesh call. No request was retried and no second host was launched. The R8 authenticated project-info response remains historical evidence, not an R14 result.

The client captured five disposable Content/Config files before and after the host context; their SHA-256 values did not change. Since no native inspector ran, this does not establish package-state or inspector side-effect acceptance. The host context exited, and a post-run process check found no R14 host process. No exit code was retained. Disposable Editor PID 42880 remained open with the pinned start/executable at the final passive check. Neither Editor was closed, saved, discarded or restarted.

## Connection indicator and official engine

The native plugin's status source reports green only when its listener exists and its last authenticated native request is at most six seconds old; yellow means a prior authenticated request is older than six seconds. A failed host-side identity preflight never reaches native token validation, so it cannot refresh that native timestamp. R14 did not observe the disposable Editor's dot during the host run and cannot verify its live color. A potential semantics issue remains: an idle listener with stale authenticated activity is labeled "Connection interrupted" even if no actual transport failure has been established. The narrow future UI proposal is to distinguish listener availability, authenticated activity age, and last request outcome; no UI source or binary was changed.

The official `G:\Program Files\EpicGames\UE_5.6` installation exists and reports 5.6.1 / changelist 44394996. Its installed `Engine\Plugins\Marketplace\Forge\MajesticForge.uplugin` is descriptor version **30 / 0.2.16-alpha.1**, SHA-256 `55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07`, matching the disposable project's descriptor. Descriptor equality does not prove binary or behavior equality. The tested C0B Python host still has no successful R14 native response and the preservation inspectors remain unaccepted; **official-engine deployment is not ready**. No official or live plugin file was changed.

## Independent gate verdicts

| Gate | R14 verdict |
|---|---|
| Host operational | **PARTIAL** — initialization/catalog/session rejection passed; exact-session identity preflight timed out. |
| Native request verified | **NO** — no authenticated native response in R14. |
| Status indicator verified | **NO** — source semantics verified, live color not observed. |
| Inspector safety verified | **NO** — no inspector ran or complete package baseline was captured. |
| Official engine deployment ready | **NO-GO** — runtime acceptance and binary comparison are incomplete. |

Evidence is retained under `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R14-20261022T155316Z-4aba243c5f2d41b8aa2921b4cc6264bb`. The stage-owned diagnostic and runtime client, sanitized host stderr, and runtime result remain there. Earlier R7–R13 evidence was not rewritten or removed.

The next bounded step is **offline** instrumentation of a stage-owned listener helper and parent watchdog to persist sanitized phase markers even on timeout, using the exact host environment. Once a specific phase is reproduced, repair only that proven defect in C0B and obtain a new single-host authorization. Do not raise the timeout, bypass identity, rebuild the plugin, or contact A7K41 to work around the failure.
