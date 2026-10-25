# ForgeMCP Stage A7K46-C0B-R20 — Correlated Child Startup Instrumentation

Date: 2026-10-22 UTC  
Mode: isolated C0B Python correction and offline verification  
Disposition: **INSTRUMENTATION IMPLEMENTED AND OFFLINE VERIFIED. R18 live timeout cause remains UNKNOWN. No host or Unreal socket connection was made. Official-engine deployment and Production Phase 6C remain NO-GO.**

## Baseline

The complete R18 and R19 reports and their referenced marker/result evidence were reviewed. The pre-edit R18 hashes matched exactly: `process_identity.py` `8053DA234276E2BE9915CF0CE5F0385E276D25C2BF3C57037E1ECE69F7E547B2`, `windows_tcp_listener.py` `310BC15CE49F110AC9013E2D5C3D4545A1A70813B54BDD2A5DD6929519B98B59`, and `test_host_config.py` `77BB030BF39CA3D91B3D2A2B430524B99B63BCC93BD4B47789BCAF85C64E1A24`. R19 `results.json` remained SHA-256 `60BA40E3A70CD9A183493E459484B83A40D83777675554034F7529DFEAE5C074` at baseline. The three R7 project/plugin DLL hashes still match `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37`, `2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F`, and `E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7` respectively. No binary was loaded, rebuilt or modified.

R19 established that R18's two failed probes overlapped, but neither failed child had a recorded PID or `Popen` return. R19's one- and two-helper offline cases succeeded. R20 therefore adds diagnostics; it does **not** claim to repair the unidentified R18 stall.

## Python changes

Only these isolated C0B source files changed:

| File | Final SHA-256 | Change |
|---|---|---|
| `source/server/core/process_identity.py` | `025BE1C16734DB4D15EBAD82F7931257E0A5F85DD6102E931660AC247ADA19CC` | Per-probe correlation/origin, direct `Popen`/`communicate` observation, Windows handle creation-time query, bounded timeout cleanup and handle-exit check, separate parent/child diagnostic paths, fail-closed marker errors. |
| `source/server/core/windows_tcp_bootstrap.py` (new) | `142C8B9FB5655F683A08E2FE3062CB2ABD8D59F3CAABF16827388DFB0BD03CE8` | Absolute-script bootstrap under the same base Python `-I -S`; records earliest Python marker, import boundaries, marker I/O and helper exit without changing listener JSON stdout. |
| `source/server/core/windows_tcp_listener.py` | `3BFCE867F3A9D59E72F14068ADD33FA8D022953371C0102C90E2538732F2FA0B` | Child markers carry the correlation ID and prefer the per-child diagnostic file; an opt-in marker write error exits with a sanitized category. IPv4/IPv6 query and JSON response contracts are unchanged. |
| `source/server/core/connections.py` | `8CC4641A55919CFE9327EFE4E234638C0B86C4753D6B94870DA31549573CA66A` | A context variable labels each fresh probe as `health`, `project_info`, or `other`; `asyncio.to_thread` receives that context. Authorization and request payloads are unchanged. |
| `source/tests/test_host_config.py` | `A53672D753D707545EC8A780D9FD94FB25AF3500ABFA8D07909BD455674B90FA` | Adapt timeout/malformed-child tests to `Popen`; add parent diagnostic failure and origin-propagation tests that stop before a socket. |

The direct listener launch remains the verified installed base interpreter, `C:\Program Files\Python\Python311\python.exe`, with `-I -S` and validated absolute bootstrap and helper paths. The correlation ID is random diagnostic metadata only. It does not select a session, authenticate a request, alter the 30-second aggregate deadline or cache an identity result.

## Event schema and Windows child identity

Each probe writes `identity-parent-<correlation>.jsonl` and its child writes `identity-child-<correlation>.jsonl` under the supplied stage-owned diagnostic directory. Parent records carry `component`, `phase`, `correlation_id`, sanitized `origin`, parent PID, monotonic nanoseconds and probe-relative elapsed milliseconds. The launch sequence includes `popen_enter`, `popen_return`, direct child PID, numeric process-local handle, `GetProcessTimes` creation FILETIME ticks, exit code, timeout and cleanup results. A `Popen` return timestamp is captured immediately after process creation, before the handle query. A missing handle creation time or unverified normal child exit fails the identity probe closed.

Bootstrap records carry correlation ID, executing PID, monotonic timestamp, `python_entry`, `listener_import_start`, `listener_import_complete`, `helper_execution_start` and `helper_exit`. Each bootstrap marker has a companion `marker_write_result` with measured open/write durations. The existing listener contributes IPv4/IPv6 start/end, serialization and return markers in the same **per-child** file. Neither child diagnostic output nor authentication data enters JSON stdout. A child marker-file error emits only `identity_diagnostic_write_failed` on stderr and exits nonzero; a parent marker-file error fails the probe before a positive result.

The Windows process handle identifies the direct child independently of a bare PID, and `GetProcessTimes` supplies its creation identity. On timeout, the wrapper terminates only its owned direct child, waits at most two seconds to reap it, then checks the same handle for signaled exit. A failed cleanup or handle check remains a sanitized failure. No arbitrary descendant-tree cleanup is claimed. The bootstrap still cannot observe OS process creation or Python interpreter initialization **before its first Python statement**. Python's local monotonic clock displayed millisecond granularity in these records; zero measured sub-operations do not prove zero duration. Synchronous local marker I/O is small and per-probe but does not have an independent hard I/O watchdog; a filesystem stall remains a limitation.

## Correlated offline evidence

Evidence root: `runtime/R20-20261022T132343Z-0e78d366dcb14aaf8bf494f33168a7b7`. The final offline run used the C0B source and venv in a fresh process. It queried only passive Windows process/listener metadata for the existing disposable PID/port; it opened no Unreal socket, host, registration or protected project. `offline-results.json` SHA-256: `3BE468BFBF96415DEC99166D1913492FA80EDFAD0F19BA3F5EDB41CDD0F435B8`.

| Case | Result | Correlation example |
|---|---|---|
| A, one direct probe | Passive snapshot, one listener row, 2,172 ms; direct child exited 0. | `other` ID `d6a0c7e50e1c4501b93f92c1953545f8`, child PID 38648; `popen_enter` 1,422 ms, return 1,453 ms, complete 2,172 ms. |
| B, two concurrent probes | Both passive snapshots; `health` 1,594 ms, `project_info` 1,593 ms. Parent/child files and executing PIDs matched independently. | Health ID `d7aa134f381d40e7ac78c3fe1732a838`, PID 43572, creation ticks 134371637297322527. Project-info ID `c517b66ce9d748bdaf643385bbc65614`, PID 20020, creation ticks 134371637298144206. |
| C, controlled pre-marker delay | Two-second watchdog expired; R20-owned PID 34180 was killed/reaped and its handle was signaled at 2,031 ms. | Stage-owned delay script; no Unreal access. |
| D, marker-file failure | Stage-owned PID 25248 exited 3 in 188 ms, no JSON stdout, sanitized `identity_diagnostic_write_failed`; handle confirmed exit. A separate unit test verifies parent marker failure stops before launch. | Fault was a directory used as the child marker file. |
| E, malformed/failed helper | Focused tests reject nonzero helper output and malformed listener JSON; positive identity is not returned. | Mocked subprocess responses; no additional OS child. |

`fault-results.json` SHA-256: `BCE59C810246C80A9C6691F4C39126960955999566E0835D93233B9CDE237C9B`. The concurrent case and R19's earlier overlapping case both completed; normal timing variation is not evidence that R18's host-only stall is fixed. Each probe maintained its own deadline; the same single 30-second budget covers its filtered CIM and listener checks.

## Regression and independent gates

Focused pytest on `test_host_config.py`, `test_connections.py`, `test_security.py`, `test_dirty_packages.py` and `test_native_plugin_contract.py`: **100 passed in 7.38 seconds** after the final source change. Ruff `check server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. Existing and updated tests cover missing/unallowlisted sessions, private registration, process PID/start/executable/project argument, unique loopback listener, timeout and malformed-output rejection, and the exact four-tool `preservation_readonly` catalog. The source retains both IPv4 and IPv6 owner-PID table queries. No native token validation was performed live; its host/native boundary was not edited.

| Required gate | R20 verdict |
|---|---|
| Parent instrumentation | **PASS offline** — correlated launch/return/PID/handle/creation/exit events observed. |
| Direct-child identity | **PASS offline** — Windows handle creation ticks and PID observed; handle exit verified. |
| Early child marker | **PASS offline** — pre-import bootstrap and marker I/O records observed. |
| Concurrent correlation | **PASS offline** — separate health/project-info IDs and files, matching child PIDs. |
| Timeout cleanup | **PASS for owned direct child** — bounded reap and handle-exit evidence; descendants not tested. |
| Identity security regression | **PASS at focused offline test/source level** — 100 tests and no changed authorization predicate; native authentication not retested. |
| Live startup failure resolved | **NOT VERIFIED** — no host launched. |
| Native inspector acceptance | **NOT TESTED**. |

The next safe action is a separately authorized **single** live diagnostic host attempt with a fresh disposable Editor identity/registration gate and a stage-owned diagnostic directory. Preserve the per-probe parent/child files on failure; their last completed phases can distinguish a returned process handle, earliest Python execution, import, marker I/O, IP Helper and pipe completion. Stop on the first failure. R20 grants no live host, native request, build, deployment or Editor action. The original R18 stall remains unexplained, and official-engine deployment and Production Phase 6C remain **NO-GO**.
