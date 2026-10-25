# ForgeMCP Stage A7K46-C0B-R17 — Helper Startup Repair and Live Test

Date: 2026-10-22 UTC  
Mode: bounded offline startup diagnosis  
Disposition: **STOPPED BEFORE HOST LAUNCH.** Three permitted diagnostic attempts completed without reproducing the R16 timeout. A Python venv redirector/child-PID mismatch was verified, but its causal role in the timeout remains unproven. No host, native request, functional source repair or plugin build was attempted. Production Phase 6C remains **NO-GO**.

## R16 failure and host concurrency

The complete R16 report and its `identity-markers.jsonl`, result and sanitized host stderr were reviewed. R16's background/foreground checks completed PowerShell in about 2.1 seconds, launched two listener checks with roughly 27.9 seconds left, then timed out without either listener child reaching the first module marker. Both direct children were reported reaped. No native request reached Unreal.

`source/server/core/connection_monitor.py` starts a periodic, authorized `health` dispatch every two seconds after the host lifespan's startup authentication/project checks. `source/server/core/connections.py` calls the Windows process identity probe through `asyncio.to_thread` for each native dispatch. A foreground `unreal_project_info` can therefore overlap with periodic `health`; each independently launches PowerShell and listener helper subprocesses. The R16 marker sequence is consistent with overlapping checks. **Concurrency is supported by the source and overlapping R16 markers, but is not proven to cause the startup stall.** No monitor, request freshness, allowlist or authentication behavior was changed.

## Stage-owned early bootstrap and three offline attempts

The R17 evidence root is `runtime/R17-20261022T162312Z-9d686a6247c34b7eaef062b4ff8c631c`. A minimal stage-owned `listener_bootstrap.py` writes a sanitized entry marker before importing `server.core.windows_tcp_listener`, then calls its existing `main()`. Its stdout remains the helper's JSON result. A stage-owned `offline_probe.py` launches bounded subprocess cases using the existing C0B venv interpreter, source `PYTHONPATH`, source working directory, and R17-local temp/profile paths. The harness records parent spawn monotonic times, `Popen` PID, Windows process creation time, the interpreter path, sanitized working directory/launch mode, bounded stdout/stderr, child markers, exit status and timeout cleanup. No credential or registration content is read or logged.

Exactly **three** diagnostic cases were run, each with a 30-second case watchdog:

| Case | Result | Total time | Early bootstrap evidence |
|---|---|---:|---|
| Existing `python -m server.core.windows_tcp_listener` | Exit 0; exact target owner and loopback row | 656 ms | Module code markers completed; no pre-import bootstrap in this case. |
| One bootstrap helper | Exit 0; same listener row | 359 ms | Bootstrap entry about 250 ms after parent spawn; import and both IP-family queries completed. |
| Two overlapping bootstrap helpers | Both exit 0; same listener row | 969 ms | First entries about 844 and 875 ms after their parent spawns; both imports, queries and serialization completed. |

No diagnostic case timed out. IPv4, IPv6 and serialization markers completed in the bootstrap cases. The first combined R16-style identity probe was **not** rerun in R17: the three-attempt ceiling was consumed by the one normal-helper control and the single/overlap early-bootstrap cases. This is an explicit missing Phase 3/5 gate, not an implied PASS. No Unreal bridge socket was opened and no ForgeMCP host was launched.

## Verified launch-chain defect and unresolved timeout

The stage-owned bootstrap emitted its executing PID, which differed from the PID returned by `subprocess.Popen` for the existing venv `python.exe`:

| Case | `Popen` PID | Bootstrap execution PID |
|---|---:|---:|
| Single | 42284 | 14684 |
| Overlap child 1 | 10988 | 39668 |
| Overlap child 2 | 10092 | 38648 |

`G:\ForgeMCP\.venv\pyvenv.cfg` points to the base Python at `C:\Program Files\Python\Python311\python.exe`. The observed PID split establishes that this venv launch path introduces another process before helper module execution. Consequently, the R15/R16 `listener_child_reaped` marker proves cleanup of the **direct** `subprocess.run` child, but does not alone prove the actual Python helper descendant exited. A final passive check found none of the R17 diagnostic launcher or executing PIDs still present. The PID split is a real cleanup/observability concern; it does **not** prove why R16's two launches stalled before module entry. The overlap case here succeeded, so a concurrency-triggered stall remains an unverified hypothesis.

The requested distinctions between OS creation delay, redirector/interpreter initialization, early import, diagnostic-file access and parent pipe collection remain incomplete for the failed R16 children. R16 had no bootstrap/PID correlation, and R17 did not reproduce the timeout. The controlled bootstrap demonstrated that early code can mark before the Forge import, not that it reached that point during R16. **Exact startup blocker: UNKNOWN.**

An explicit absolute helper script launched by the base interpreter could remove venv-redirector and package-resolution indirection, but R17 did not execute or validate that path within the three-attempt limit. Changing the security-critical probe to it now would be speculative. No functional C0B source change, timeout increase, cached identity shortcut, or bounded-serialization change was made. The R16 authorization was not reused.

## Files, validation and preservation

Only the two new stage-owned diagnostic scripts and their R17 output files were created. Hashes: `listener_bootstrap.py` `57AB13B25B641363884FC86AA7E480C86E1B777B78804C4BE75D6F759FD8F563`; `offline_probe.py` `EBF83729AF89E909AB6B8D3AB4EB19A7E22BBB28A20F96D7717758932CC3B151`. The three result JSON hashes are `707F14715A64C8DEA50564DD711E5EB49A0B83C8704F12CB3D0EBEB5A82EC10F`, `98CBFEF34A1F8FC0D5AA4CAF716A2423228A586C78825F9D486F2AACFC09F705`, and `D30F5FF64B71CBE9688CABD78DB2DDAE6AAA9CCBEEAB399C08A86F44CF4B89B4` in case order above.

The isolated production-path Python files remained unchanged from R15: `process_identity.py` SHA-256 `F9403E67BE247F98F2CF9A1DDA55C45BF61DB5F80856FDB9AF3D7419ED2FF693`, and `windows_tcp_listener.py` `AC704E69A7D8F45DD6BFDCB472B02522E4588CDE93382FDFB04F70C14A60E380`. Existing session, process, listener and authentication predicates remain as before. Focused host/session/security/listener tests: **89 passed in 15.63 seconds**. Ruff over `server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. These tests validate unchanged C0B source; they do not validate a repaired launch mechanism or native request. The R16 monitored five disposable Content/Config files still matched their saved SHA-256 values. Disposable Editor PID **42880** with pinned start remained present at the final passive check; no listed R17 diagnostic PID remained. No A7K41 or closed production project was contacted. No asset, package, plugin binary or Engine file was changed.

## Gate results and next boundary

| Gate | R17 result |
|---|---|
| Exact R16 timeout cause | **UNKNOWN** — no repeat failure in three permitted attempts. |
| Host health overlap | **SUPPORTED AS POSSIBLE** by source and R16 interleaving; causal contribution unproven. |
| Venv redirector/PID split | **VERIFIED**; direct-child cleanup does not establish descendant cleanup. |
| Functional repair | **NOT APPLIED**; a replacement launch path was not tested. |
| Actual corrected combined identity probe | **NOT RUN**; attempt ceiling exhausted. |
| R17 live host/native connection | **NOT RUN**; conditional authorization not exercised. |
| Dirty/world/mesh inspectors and indicator | **NOT TESTED**. |
| Preservation within monitored Content/Config | **PASS for five named files**; complete package preservation untested. |
| Official-engine deployment | **NOT READY**; no authenticated C0B native acceptance. |

The narrow next action is to design and validate one direct-child helper launch using the installed base interpreter and absolute C0B script path, then prove negative owner/malformed/timeout behavior and descendant cleanup under a fresh bounded authorization. If those gates pass, re-run the combined identity preflight in the exact host environment before a separately authorized single-host acceptance attempt. Do not deploy to the official engine, alter the native indicator, or contact A7K41 on the strength of this diagnostic result. Production Phase 6C remains **NO-GO**.
