# ForgeMCP Stage A7K46-C0B-R9 — Identity Preflight and Editor Lifecycle Review

Date: 2026-10-22 UTC  
Mode: bounded offline diagnosis  
Disposition: **SOURCE NOT CHANGED; OFFLINE CHECKS PASSED; LIVE REQUEST NOT RETESTED.** R8's timeout cause remains unknown. The disposable Editor remains running. Production Phase 6C remains **NO-GO**.

## Result

R8's dedicated host authenticated and answered `unreal_project_info`, then the first `unreal_inspect_dirty_packages` request failed before a native socket exchange. Its host stderr recorded `powershell_timeout`; the public response was `identity_preflight_failed`. A fresh, standalone invocation of the same existing passive identity probe completed in **5.163 seconds** and returned the pinned PID, seven-digit UTC start time, and exact loopback listener owner. The one R8 timeout is therefore not reproducible under the current conditions. Neither the R8 evidence nor today's successful measurement identifies whether CIM, `Get-NetTCPConnection`, PowerShell startup, or scheduling stalled during R8. Shader activity overlapped but is not established as the cause. Under the R9 rule against an invented fix, no source or test was edited.

The R8 disposable Editor is **still running**. The prior `CloseMainWindow` returning true did not terminate it. No further close, UI, or endpoint request was sent.

## Evidence identity and timeline

The R7 report is still 17,284 bytes with SHA-256 `DE44D4290B82A0ED661DD6CD6876E21E392C2B1E35689EFEE061ED53D01F91B1`. The complete R8 report is 20,588 bytes with SHA-256 `9ACB49FD64C4B03490157B237583EB135FAA9FF582042551E4E6D575AD524EA7`. R8 `host-stderr.txt` remains 688 bytes, SHA-256 `41466D50715A1C601F47C3D555ED17A8C2F246F87F6DA28BDED722283B37B13C`; `runtime-result.json` remains 17,761 bytes, SHA-256 `88FD99B253C208A4EEECA8BD001BA8AFEFA5AC532E4C2445A16A19D2E88D5DEA`. The live Editor log is allowed to grow and was not treated as an immutable hash baseline.

The R8 order established by those records is: dedicated host initialization; successful authenticated `project_info` for the disposable project; one dirty-package request; 30-second host-side PowerShell timeout; sanitized public `identity_preflight_failed`; host process absence; one accepted but incomplete Editor close request. No dirty-package snapshot was obtained. No R9 host or Editor was started.

## Current disposable Editor lifecycle

At 2026-10-22T07:13:22.6745658Z, passive OS metadata found PID **42880**, created **2026-10-22T06:37:06.5248750Z**, executable `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe`, and the exact R8 command line containing only the C0B disposable `.uproject`. The earlier owner observation was `ALIENWARE-PC\Kenne`; the current process identity, command and start pin matched. `Get-Process.Responding` was true, its main window was `A7K46C0B_ReadOnlyInspector - Unreal Editor`, and the private Forge listener `127.0.0.1:59863` was still owned by 42880. The main window was visible and enabled. Passive top-level window enumeration found no visible save, discard, confirmation, or crash dialog owned by this PID. Hidden untitled windows do not establish the absence of every modal state.

The Editor log continued beyond R8, including slow shader jobs, Slate draw-buffer waits, and a shader compilation summary at 07:02:59 UTC. No observed log line established a completed exit or crash. Process responsiveness and continued CPU use argue against an already exited process; they do not explain why the earlier close request did not finish. **Shutdown blocker: UNKNOWN.** No second close request, WM_CLOSE, forced termination, save/discard action, or window activation was issued. The protected A7K41 Editor was not contacted.

The existing R8 private registration remains live while this Editor remains running; no registration, log, cache, or project configuration was removed. The historical R7 telemetry-file loss remains unresolved. The R8 `DefaultEngine.ini` startup change remains 1,589 bytes, SHA-256 `E6D3D12D7923838AD0724ED85AC781100C3E75FE90AFE8FA6D9E2BAF9F3BA863`, and was not rewritten. The Editor plugin DLL still matches R7 SHA-256 `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37`.

## Identity probe code path and measured behavior

The isolated dispatch path in `source/server/core/connections.py` validates the explicit session ID and exact registration, then calls `WindowsProcessIdentityProbe` through `asyncio.to_thread` **before every native request**. `validate_process_snapshot` compares PID, exact executable, exact seven-digit process start, Windows-parsed executable and sole exact `.uproject` argument, unique listener owner, and loopback-only address. A `ProcessIdentityError` is logged by category and returned to the client as `identity_preflight_failed`; no socket exchange follows. `project_info` succeeded because its own check completed; the later inventory request performed a fresh check and timed out. There is no evidence of a cached identity bypass.

`source/server/core/process_identity.py` starts `powershell.exe -NoProfile -NonInteractive -Command <fixed snapshot script>` using `subprocess.run`, `capture_output=True`, a 30-second timeout, inherited environment plus only the target PID/port variables, and `CREATE_NO_WINDOW`. The script requests one `Win32_Process` row filtered by PID and listeners filtered by the pinned local port; it emits PID, executable, full command line, UTC creation time, listener PIDs and addresses. It does not broadly enumerate Unreal sessions. Python validates response types and rejects nonzero exit, malformed data, launch failure, and timeout. The standard `subprocess.run` timeout path kills and waits for its direct child before raising, although R8 did not retain the timed-out PowerShell PID or independently prove its post-timeout absence.

Bounded standalone measurements on the still-pinned disposable process: `Get-CimInstance` took **399 ms**; `Get-NetTCPConnection -State Listen -LocalPort 59863` took **3,969 ms**; the complete production `WindowsProcessIdentityProbe()(42880, 59863)` took **5.163 seconds** and returned PID 42880, `2026-10-22T06:37:06.5248750Z`, owner 42880 and `127.0.0.1`. These current timings do not reconstruct the R8 30-second stall. A synthetic short-timeout subprocess exercise produced a timeout, but its child PID was not captured before startup and its post-timeout process absence was **not independently verified**. No claim of a passing child-cleanup acceptance test is made from it.

The stale `Saved/ForgeMCPDisposableProject.json` points to the old drive-root workspace. Neither `process_identity.py` nor this `connections.py` preflight path reads that marker. It is not supported as the timeout cause and was not edited.

## Source preservation and offline validation

No C0B source file was changed. Current pre/post-equivalent hashes are:

| File | SHA-256 |
|---|---|
| `source/server/core/process_identity.py` | `6CA830A3C35B1A9D290EF8A3E5DE7C9005E0043523177978B42E296A5BDBA9EB` |
| `source/server/core/connections.py` | `C7FD5E6A466F847C8A2FEC9DB7CFB4593902B777B4BE2133DB773BDF2F929914` |
| `source/server/main.py` | `62EEB3340ABA53712E4F81DA7BBF13AB84386B5418D67C37BD0CF639075D4934` |
| `source/tests/test_host_config.py` | `6437979DADD92EE63B19257568E8651E7A07DD1816A48C8395AD169D44922115` |

Focused pytest: **96 passed in 11.08 seconds** across `test_host_config.py`, `test_connections.py`, `test_security.py`, `test_dirty_packages.py`, and `test_native_plugin_contract.py`. Existing tests cover accepted identity; wrong PID, start, executable, project argument and listener rejection; missing/unallowlisted session rejection; timeout categorization; private roots without shared fallback; and the exact four-tool `preservation_readonly` catalog. Ruff `check server tests scripts`: **PASS**. `compileall -q server tests scripts`: **PASS**. These are offline results, not a live native request or proof that a timeout's child process was observed exiting. Python validation may create ordinary local cache files inside C0B; no cleanup was performed.

No authentication, allowlist, process-identity predicate, timeout, shared-session fallback, or catalog setting was changed. A source fix would require evidence that distinguishes a slow or wedged OS query from transient load. Simply raising the timeout or skipping repeat checks would leave the cause unknown or weaken freshness.

## Disposition and next authorization

| Gate | Result |
|---|---|
| R7/R8 immutable evidence checked | PASS |
| Current disposable process identity | PASS; PID 42880 still present |
| Graceful shutdown completed | **NO**; blocker UNKNOWN |
| R8 timeout category and host path identified | PASS |
| R8 underlying stall cause established | **UNKNOWN** |
| Source fixed | **NO CHANGE — no justified correction yet** |
| Offline tested | **PASS for 96 focused tests, Ruff, compileall; child cleanup observation incomplete** |
| Live authenticated native request retested | **NO** |
| Production Phase 6C | **NO-GO** |

The next bounded action is a separately authorized diagnostic run that times **PowerShell startup, the filtered CIM query, and the filtered listener query individually** under the same process load, records sanitized phase/time/error categories and the diagnostic child lifecycle, and leaves every identity/authentication predicate intact. If a reproducible specific bottleneck is found, make the smallest source/test correction and retest offline. A later authenticated host/native-inspector retest needs its own authorization. The still-running disposable Editor requires an owner decision for lifecycle handling; this report authorizes no close or save/discard action. No additional build, host launch, Editor launch, protected-project operation, or Landscape action occurred in R9.
