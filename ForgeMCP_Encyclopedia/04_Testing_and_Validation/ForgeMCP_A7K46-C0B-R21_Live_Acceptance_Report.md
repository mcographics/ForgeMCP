# ForgeMCP Stage A7K46-C0B-R21 — Live Connection Acceptance and Alpha Gate

Date: 2026-10-22 UTC  
Engine: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **FAIL for the explicit authenticated connection request.** Exactly one isolated host was launched. Its startup authenticated native `health` and `project_info`, but the later tool request failed in the host-side listener identity preflight. No retry, native inspector, alpha staging or deployment followed. Production Phase 6C remains **NO-GO**.

## Current identity and preflight

The existing C0B workspace and R20 source were reused. The five R20 Python/test hashes matched the R20 report before the attempt. The protected A7K41 process was observed only as a distinct OS process; no request or action targeted it. The closed production city project was not accessed.

The R21 client independently checked the disposable Editor process and private registration before host creation. Its passive `WindowsProcessIdentityProbe` completed in **2,032.368 ms** and `validate_process_snapshot` accepted PID **42880**, exact creation UTC **2026-10-22T06:37:06.5248750Z**, the StageA7G `UnrealEditor.exe`, its exact C0B disposable `.uproject` argument, and one loopback listener on `127.0.0.1:59863` owned by that PID. The private `unreal-42880` registration reported kind `unreal`, PID 42880, host `127.0.0.1`, port 59863 and protocol 1, with a present token. The token was not emitted. The isolated configuration allowed only that session and denied the historical protected session ID.

Two initial client invocations stopped **before host launch** while checking the stage-owned host configuration. First, state/log/temp paths were outside the required private root; second, `TEMP`/`TMP` differed from its private temp path. Those client-path errors were corrected inside the new R21 harness without changing C0B runtime source, host security rules, or an Editor. Neither invocation entered `stdio_client` or sent a native request. The subsequent preflight passed and consumed the **one** authorized host launch.

## One isolated host and request result

The host used the existing C0B Python source, private registration, `preservation_readonly` profile and R20 correlated diagnostics. Initialization took **8,788.474 ms**. Its sanitized stderr records successful native `health` and `project_info` responses during isolated-host lifespan startup. This demonstrates a real authenticated native exchange at startup, but does not satisfy the later explicit tool-request gate.

The actual MCP catalog contained exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh`, and `unreal_inspect_world_save_scope`; each had `readOnlyHint=true`. A missing session ID returned `session_id_required` in **5.594 ms** and an unallowlisted ID returned `session_not_allowed` in **5.033 ms**. Those negative calls did not reach Unreal.

The single explicit `unreal_project_info` call for `unreal-42880` returned public `identity_preflight_failed` after **30,070.154 ms**. The host's sanitized category was **`listener_timeout`**. No socket request for that tool call reached Unreal and no second call or host was attempted. The client reported `BLOCKED_OR_FAILED` and `ExceptionGroup` on context exit; the captured tool response and host log identify the meaningful failure category. The host context exited, and a targeted post-run process query found no matching isolated-host process. An exit code for the host was not retained.

## Correlated failure boundary

R20 created separate per-probe parent and child files. The startup `health`/`project_info` checks and the client's passive check have complete child phase records. The two later overlapping checks have complete parent launch/timeout records but **no child file or `python_entry` marker**:

| Origin / correlation | Filtered PowerShell | Listener launch budget | `Popen` result | Last recorded phase |
|---|---:|---:|---|---|
| Foreground `project_info` / `b98e9c868b39408ea33b0c00d35faf01` | exit 0 at 1,812 ms | 28,188 ms remaining | Returned at 1,812 ms; PID **37784**, handle **1004**, Windows creation ticks **134371656735508143** | `listener_timeout` at 30,015 ms; `listener_child_reaped` at 30,031 ms, handle exit true. |
| Background `health` / `d52e1786072a43d5aa96f622a007a588` | exit 0 at 1,985 ms | 28,015 ms remaining | Returned at 2,016 ms; PID **43232**, handle **800**, Windows creation ticks **134371656735795082** | `listener_timeout` at 30,016 ms; `listener_child_reaped` at 30,031 ms, handle exit true. |

Targeted OS checks after shutdown found both failed-child PIDs absent. The process creation boundary is now **confirmed passed** for each child. The last completed observable step is the parent `popen_return`; neither child reached an observable earliest Python marker. This does **not** distinguish delayed interpreter initialization from a block/failure at the bootstrap's first marker-file operation. No IP Helper start marker exists for either failed child, so an IP Helper stall is not supported by this evidence. The concurrent health/request timing is observed, but its causal role is still unproven. No source fix is justified by this result alone.

## Inspector, indicator, preservation and release gate

The explicit project-info gate failed, so **no dirty-package inventory** was requested. There is no native package baseline or before/after dirty-state comparison. The world and StaticMesh inspectors were not called. The five monitored disposable Content/Config files have identical before/after names and SHA-256 hashes, but this bounded filesystem result does not prove complete in-memory package preservation. No save, discard, asset modification, Landscape operation, plugin rebuild or Editor lifecycle action was issued.

The actual disposable connection indicator was not safely observed during the startup responses or the failed request. Its green/yellow behavior is **NOT VERIFIED**. The existing six-second native activity rule remains a source-level observation only; no UI correction was made.

No alpha release candidate or staging area was created. The conditional release gate did not pass: the explicit authenticated tool request failed, dirty-package safety was not tested, the indicator was not verified, and native inspector acceptance remains open. The official Engine installation and plugins were left untouched.

| Gate | R21 verdict |
|---|---|
| Fresh disposable process, registration and listener identity | **PASS before host launch** |
| Exactly one isolated host launch | **PASS — authorization consumed** |
| Four-tool read-only catalog | **PASS** |
| Missing/unallowlisted session rejection | **PASS** |
| Authenticated native startup exchange | **PASS for host lifespan `health`/`project_info`** |
| Explicit authenticated `unreal_project_info` tool request | **FAIL — `listener_timeout` before native socket** |
| Dirty-package inspector and package-state comparison | **NOT TESTED** |
| Actual connection indicator | **NOT VERIFIED** |
| Five named Content/Config file hashes | **PASS for this bounded comparison** |
| Complete preservation and native inspector safety | **INCOMPLETE** |
| Alpha release/deployment readiness | **BLOCKED / NO-GO** |

## Evidence and next action

R21 evidence is under `runtime/R21-20261022T135909Z-820eaeabd0fb48bcbe38fa6547e1515a`. `evidence/result.json` SHA-256 is `3D322B37BFAFA374FA5DFBD1C699D38B9A2EB622374FD720E93A1CFDD5B6A6EA`; the stage-owned client is `6D07D41876D15D36FC83EC8D29DB96957838A2E2A426F6E97280D755DE8801C7`. Sanitized `logs/host-stderr.txt` is `A7450D1ED57C81B45912CB06E2DB1A22A179C7991075FA33EAFEC5764A6BB6E0`. The two failing parent logs are `75279046DECE7E911959669C9812993D794C828A0F21F6A135A9E1B041DE6384` and `DC817C47DA6BEB892ECA1DF4B6FEEFF4C94E43A2F9594E103F052187F36B9CC1` in table order. No child log was created for either failed correlation ID. Historical evidence was not deleted or rewritten.

The narrow next investigation is **offline**: use the preserved child creation times and handles to determine why two base-Python processes failed to reach the first bootstrap marker under concurrent host activity, while assessing whether diagnostic-file open itself can stall. Do not increase the identity deadline, bypass the fresh check, disable health checks, or infer an IP Helper defect from missing child markers. Any new live host attempt requires separate authorization and a fresh Editor identity gate.

**Final verdict: FAIL for R21 explicit live connection acceptance.** Startup native exchange was real but insufficient for the requested gate. Official-engine alpha migration and Production Phase 6C remain **NO-GO**.
