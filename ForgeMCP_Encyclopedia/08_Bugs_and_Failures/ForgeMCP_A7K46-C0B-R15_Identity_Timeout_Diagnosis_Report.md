# ForgeMCP Stage A7K46-C0B-R15 — Identity Timeout Diagnosis

Date: 2026-10-22 UTC  
Mode: isolated Python instrumentation and offline validation  
Disposition: **INSTRUMENTED; OFFLINE PROBES PASSED; R13/R14 ROOT CAUSE UNPROVEN.** No ForgeMCP host or Unreal Editor was launched or connected. Production Phase 6C remains **NO-GO**.

## Blocking phase and deadline

The preserved R13 and R14 host stderr logs both classify the exact-session request failure as `listener_timeout`. In `source/server/core/process_identity.py`, a single monotonic deadline is initialized at probe entry: **30 seconds total**. The filtered PowerShell `Win32_Process` child receives the current remainder. After it exits and its JSON is parsed, the listener child (`[sys.executable, '-m', 'server.core.windows_tcp_listener', port]`) receives only the remaining time. `subprocess.run` kills and waits for a direct child on timeout, then the probe fails closed. `connections.py` returns sanitized `identity_preflight_failed` before a native socket request. Thus `listener_timeout` means the budget was exhausted at or during the listener phase; it does **not** establish that `GetExtendedTcpTable` itself blocked.

R14's one offline combined probe succeeded, with its PowerShell child taking **12,875 ms**. R13 and R14 did not retain child-internal markers, so their precise blocking operation cannot be reconstructed. Their host launches each consumed one authorization; R15 did not repeat them.

## Opt-in instrumentation and offline measurements

Only two isolated C0B Python files were edited. `process_identity.py` now appends sanitized parent phase markers when `FORGE_IDENTITY_DIAGNOSTIC_LOG` is explicitly set: identity/deadline start, PowerShell launch/completion/timeout, listener launch/completion/timeout, and timeout child-reaped markers. `windows_tcp_listener.py` appends child markers for module-entry/import completion, IPv4 start/end, IPv6 start/end, serialization start/end, and return status. The normal helper stdout remains one JSON object; markers go to the separate diagnostic file. Records contain phase, elapsed milliseconds, fixed budget/remaining time or exit code. They contain no command line, executable/project path, registration, token, credential, secret, or raw stderr. The opt-in marker writer ignores logging I/O errors rather than turning an identity check into a success. Identity predicates, native authentication, session restrictions, both IP families and the **30-second limit** were unchanged.

Source hashes:

| File | Before SHA-256 | After SHA-256 |
|---|---|---|
| `source/server/core/process_identity.py` | `E7A812F17D3B71806C21D2FA439CA8D4E2CD38F5C4AD06EE36E2528E68F7F2C6` | `F9403E67BE247F98F2CF9A1DDA55C45BF61DB5F80856FDB9AF3D7419ED2FF693` |
| `source/server/core/windows_tcp_listener.py` | `992ABD7AEB9CEA39C4DCEF399334374A4360E2F4706C21BADCAF90E941F0850B` | `AC704E69A7D8F45DD6BFDCB472B02522E4588CDE93382FDFB04F70C14A60E380` |

The disposable Editor still matched PID **42880**, start UTC **2026-10-22T06:37:06.5248750Z**, exact StageA7G executable and disposable project command line before the probes. Two fresh, bounded combined probes used the existing `G:\ForgeMCP\.venv\Scripts\python.exe` from the C0B source working directory. Both returned the pinned start, owner PID 42880 and `127.0.0.1` on port 59863. Probe 2 redirected local temporary/profile paths inside the R15 evidence root to approximate the host environment. Neither probe opened the Unreal bridge socket.

| Phase | Probe 1 | Probe 2 |
|---|---:|---:|
| PowerShell child completion | 625 ms | 688 ms |
| Listener launch / remaining deadline | 625 ms / 29,375 ms | 688 ms / 29,312 ms |
| Listener child completion | 875 ms total | 985 ms total |
| IPv4 query | completed within logged millisecond resolution | completed within logged millisecond resolution |
| IPv6 query | 15 ms | completed within logged millisecond resolution |
| Serialization and return | completed | completed |

The parent timer begins at probe entry. The child's timer begins after Python has started importing the module; these markers **do not measure interpreter startup or the earliest module-import work**. The parent launch-to-completion interval includes child startup, execution and pipe collection but does not partition them. Markers persisted in `runtime/R15-20261022T160452Z-3ccb7c6035df40e3b61f54f328b7f9f1/probe1.jsonl` and `probe2.jsonl`, respectively. Their SHA-256 values are `E748A1D91D25AF1FE4BA7269F9C87C70ADA6AFB26F78559F6A90DF714ED62272` and `AB720161142F440D10D558CF8AD2C2B7F0701B6A9F3A1C8E9E4EE8A60AEE3A67`. A marker scan found no sensitive-field terms.

The two fast probes do not reproduce the host-only timeout. A slow or stalled PowerShell query remains possible, as R14's 12.875-second measurement shows, but it is not proven to be the R13/R14 failure cause. The listener child could also stall before its first marker, in either IP-family call, or at output/collection under different host conditions. **No targeted functional repair was justified or applied.** The instrumentation is retained to identify the last completed phase in a future authorized host attempt.

## Validation and preservation

Focused existing regressions plus R11's listener-specific synthetic tests: **111 passed in 10.79 seconds**. After the final marker-label adjustment, the affected host-config and listener tests: **55 passed in 5.94 seconds**. Ruff: **PASS**. Python `compileall`: **PASS**. Existing tests cover wrong owner, missing/wildcard listener, IPv4/IPv6 parsing, malformed output, timeout fail-closed handling, exact process identity, session rejection and catalog restrictions. A separate stage-owned two-second hanging Python child test timed out and its recorded PID was absent afterward; this checks direct-child cleanup without contacting Unreal. No claim is made that R15 reproduced a hung real listener child.

The five disposable Content/Config files in the R14 post-host baseline still matched their recorded SHA-256 values. No Content, Config, native plugin binary or original repository source was intentionally edited. R15 changed only the two isolated Python files above and created its own diagnostic/evidence files. Prior reports, registration, telemetry anomaly and R8 startup configuration state were retained. No package was loaded, saved, discarded or inspected through MCP. A7K41 and production city assets were not contacted.

## Next live acceptance boundary

A subsequent separately authorized single-host run should use the exact C0B source working directory and `PYTHONPATH`, the existing private `unreal-42880` registration and credentials, the `preservation_readonly` four-tool profile, and a new stage-owned `FORGE_IDENTITY_DIAGNOSTIC_LOG` path. Reverify PID, seven-digit UTC start, executable, exact project argument, registration and unique loopback listener first. Keep the 30-second aggregate deadline and stop on the first failed exact-session request. If timeout recurs, preserve the marker file and identify the last completed phase before changing code.

That later acceptance must separately prove host identity, exact catalog, authenticated native `unreal_project_info`, a complete dirty-package inventory, truthful Editor connection status and package/filesystem preservation. **R15 authorizes no host launch and establishes none of those live gates.** Production Phase 6C remains **NO-GO**.
