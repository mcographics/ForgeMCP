# ForgeMCP Stage A7K46-C0B-R19 — Listener Startup and Concurrency Diagnostics

Date: 2026-10-22 UTC  
Mode: Existing C0B workspace, offline only  
Disposition: **R18 failure phase remains unproven. No C0B runtime source changed; no host or Unreal endpoint was contacted. Official deployment and Production Phase 6C remain NO-GO.**

## R18 baseline and event correlation

The complete R18 report, live identity-marker log, sanitized host stderr, result, and current source were reviewed. The three required R18 hashes match: `process_identity.py` `8053DA234276E2BE9915CF0CE5F0385E276D25C2BF3C57037E1ECE69F7E547B2`; `windows_tcp_listener.py` `310BC15CE49F110AC9013E2D5C3D4545A1A70813B54BDD2A5DD6929519B98B59`; `test_host_config.py` `77BB030BF39CA3D91B3D2A2B430524B99B63BCC93BD4B47789BCAF85C64E1A24`.

The R18 marker file first records three completed checks, including a successful startup/authentication sequence. Its final four `identity_start` rows include two overlapping failed checks. The final pair have this recorded sequence; the shared log lacks request IDs, so assignment of the earlier versus later sequence to health versus foreground cannot be proven from markers alone. Sanitized host stderr records one `health` and one `project_info` identity failure. Source confirms the background monitor dispatches `health` and a foreground tool dispatches `project_info` independently.

| R18 check, ordering in shared marker file | Identity start | PowerShell completion | Listener launch / remaining budget | Child entry/completion | Timeout / direct-child reap marker |
|---|---:|---:|---:|---|---:|
| First of final overlapping pair | 0 ms | 3,188 ms, exit 0 | 3,188 ms / 26,812 ms | No child marker; no recorded PID or exit | 30,078 ms / 30,078 ms |
| Second of final overlapping pair | 0 ms | 3,516 ms, exit 0 | 3,516 ms / 26,484 ms | No child marker; no recorded PID or exit | 30,141 ms / 30,141 ms |

Those elapsed values use independent probe-relative monotonic clocks and cannot be merged into one absolute process timeline. `listener_launch` is written immediately **before** `subprocess.run`; R18 did not record a `Popen` return, process handle, or child PID for either failure. A `TimeoutExpired` from `subprocess.run` means a process object was created and its communicate phase timed out under normal Python semantics, but the R18 evidence does not timestamp process creation or prove when child code began. The `listener_child_reaped` row follows Python's timeout handling; it has no independent OS PID check. Missing `process_entry` therefore does not establish Windows process-creation failure.

## Source-path analysis

`windows_tcp_listener.py` writes `process_entry` only after Python interpreter initialization, eight standard-library imports, `_STARTED` initialization, an environment lookup, JSON serialization and opening the shared diagnostic file. It is earlier than argument parsing and IP Helper calls, but not a true process-entry marker. Each marker opens the same file in append mode, writes one line and closes it; the writer suppresses `OSError`. An access failure can leave no marker, and an open/write stall can delay the child before its first marker. The implementation does not explicitly flush while the file is open, although close normally flushes; its synchronous file operation can contend with simultaneous children and parent markers. R18 had no marker-write duration or failure result. Stdout/stderr are captured with `subprocess.run(..., capture_output=True)`, whose `communicate` drains both pipes, avoiding the usual single-pipe wait deadlock; a different parent/child wait problem remains unexcluded.

`connection_monitor.py` starts a periodic health task after isolated startup checks and dispatches through the same `ConnectionManager` used by the foreground tool. `connections.py` invokes each identity probe through `asyncio.to_thread`, with a fresh 30-second deadline inside each probe. There is no shared identity lock or cached positive result in this path. The two checks can overlap in separate worker threads, and each can launch its own PowerShell and listener children. The event loop awaits these threads rather than running the blocking subprocess call itself. Cancellation of an awaiting coroutine does not by itself stop a worker thread already in `subprocess.run`; R18's two timeout rows indicate those workers reached their own timeout handlers. No evidence identifies a threadpool exhaustion, handle leak, marker-file lock, or monitor interval as the cause.

## Three bounded offline cases

The stage-only harness and bootstrap are under `runtime/R19-20261022T125704Z-0c749ed3841f472282cb1cf240c07795`. They use `C:\Program Files\Python\Python311\python.exe -I -S`, the absolute C0B listener script, source working directory and a stage-owned diagnostic path. They inspect the port's passive OS listener table; they do not open an Unreal socket or read a registration. Every subprocess had an explicit watchdog and only stage-owned child PIDs were eligible for termination. The child bootstrap marks its earliest practical Python execution before importing the listener; it still cannot measure OS process creation or interpreter initialization before Python code runs.

| Case | Observation | Verdict |
|---|---|---|
| A: one direct helper | `Popen` PID 18608, return about 0 ms; JSON valid, one matching row, exit 0, 156 ms total, empty stderr; child phase markers completed. | PASS for this offline launch. |
| B: two overlapping helpers sharing diagnostic file | `Popen` PIDs 32100 and 28884; returns at 31 and 15 ms; bootstrap PIDs match; both imported, queried IPv4/IPv6, serialized and exited 0 in 531 and 359 ms. Shared append file contains complete per-PID sequences. | No contention/stall reproduced in this bounded case. |
| C: controlled pre-marker delay | `Popen` PID 26756 returned at 16 ms. A stage-only script slept before emitting a marker; two-second watchdog fired, direct child was killed, `communicate` returned, and `poll` confirmed it reaped at 2,047 ms. | PASS for bounded direct-child timeout cleanup; no claim about arbitrary descendants. |

The JSON stdout schema in A/B parsed successfully; stderr was empty. The harness records output byte counts rather than printing listener details or credentials. `results.json` SHA-256 is `60BA40E3A70CD9A183493E459484B83A40D83777675554034F7529DFEAE5C074`; `offline_harness.py` SHA-256 is `81E25F7193F6582DB8E73670A3AB8F3DBD76EA9CEEB6BA81CE9110CADE7A3BD6`. These timing measurements have ordinary Windows scheduling resolution and are not a worst-case guarantee.

## Root-cause classification and changes

- **CONFIRMED:** R18 had two overlapping listener phases with more than 26 seconds remaining, no child `process_entry`, and host-side `listener_timeout`; source permits monitor/foreground overlap. R18 did not record failed-child PIDs or `Popen` return times.
- **REPRODUCED:** direct PID ownership and child cleanup in the R19 offline harness; not the live stall.
- **INFERRED:** both R18 identity checks were health and foreground requests, based on sanitized stderr plus source. Their exact correspondence to the two unlabelled marker sequences is unknown.
- **NOT VERIFIED:** whether R18 delayed at Windows creation, interpreter startup, early imports, marker-file access, IP Helper, pipe collection, threadpool contention, or another host-specific resource. No mechanism is assigned as root cause.

No C0B runtime or test source was changed because no specific defect reproduced. The only new files are the stage-owned harness, bootstrap, delay script, outputs and this report. Prior evidence and binaries were preserved.

## Regression and next boundary

Focused pytest (`test_host_config.py`, `test_connections.py`, `test_security.py`, `test_dirty_packages.py`, `test_native_plugin_contract.py`): **98 passed in 9.02 seconds**. Ruff `check server tests scripts`: **PASS**. `compileall -q server tests scripts`: **PASS**. These are offline checks of unchanged source. The R19 harness additionally verifies direct PIDs, listener JSON parsing, parallel completion and timeout/reap. No host, Editor, native build, plugin deployment, package save/discard or native inspector ran.

The minimum next instrumentation is a separately scoped Python-only parent `Popen` wrapper with a per-probe correlation ID and timestamps immediately before/after process creation, the direct child PID/handle and OS creation time, bounded stderr/exit status, and an independent post-timeout PID-absence check. A stage-owned early bootstrap should record entry and marker-open/write duration/failure per child before importing the listener, with separate files or correlated records to distinguish contention. Preserve each request's fresh identity check and 30-second total budget. A further live host attempt needs its own authorization; none is granted by R19.

**Final disposition:** root cause UNKNOWN; no speculative correction. Official-engine deployment **NO-GO**; Production Phase 6C **NO-GO**.
