# ForgeMCP Stage A7K46-C0B-R10 — Identity Probe Diagnostics

Date: 2026-10-22 UTC  
Engine: Unreal Engine 5.6.1 / 44394996  
Mode: bounded offline diagnostics  
Disposition: **DIAGNOSTICALLY VERIFIED** that filtered listener enumeration dominates the three completed probes and can stall beyond 30 seconds. The exact cause of the R8 timeout remains **UNPROVEN** because R8 retained no internal phase markers. Production Phase 6C remains **NO-GO**.

## Editor identity and preserved baseline

Passive OS metadata confirmed the existing disposable UnrealEditor PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, owner `ALIENWARE-PC\Kenne`, executable `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe`, and full command line with the exact C0B `A7K46C0B_ReadOnlyInspector.uproject`. A targeted `netstat` observation confirmed `127.0.0.1:59863 LISTENING` owned by PID 42880. These checks preceded the R10 measurements. PID 42880 was not launched, contacted, closed, saved, or discarded by this stage. Historical protected PID 15144 was not contacted.

The complete R8 and R9 reports were reviewed. Their hashes still match R8 `9ACB49FD64C4B03490157B237583EB135FAA9FF582042551E4E6D575AD524EA7` and R9 `1E551FE8B17A2AB0F9575A0BDC302E3EB6D6802BEC9E70E05AAF98E3613775D7` respectively. The R8 host stderr and runtime-result records retain the values recorded in R9. No C0B production source modification occurred since R9.

R8's recorded order remains: authenticated host startup, successful project_info, first dirty-package request, host-side `powershell_timeout` after 30 seconds, public `identity_preflight_failed`, host exit, incomplete disposable Editor close. No native dirty-package handler executed. R9 measured a successful whole probe at 5.163 seconds, with standalone filtered CIM at 399 ms and filtered listener query at 3,969 ms.

## Probe design and timing

R10 created only diagnostic harness/evidence under `runtime/R10`. It used the same essential production parameters: a single filtered `Win32_Process` query for PID 42880 and `Get-NetTCPConnection -State Listen -LocalPort 59863`, plus the same snapshot fields and JSON serialization. Each attempt launched one R10-owned `powershell.exe` with `-NoProfile -NonInteractive -Command`, redirected stdout/stderr, used a monotonic Python clock, and had a strict **30-second** communicate watchdog. Phase markers were written to stderr before serialization, so a timeout could retain the last completed phase. On timeout the harness kills and waits for its own direct child. No production timeout or source implementation was changed.

Three bounded full attempts completed with matching PID/start/executable/project/listener evidence. Durations in milliseconds, calculated from the retained phase markers:

| Attempt | PowerShell child PID | Initialization after first marker | Filtered CIM | Filtered listener | Serialization | Python launch-to-exit total | Launch/exit/pipe residual* |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 43020 | 11.790 | 1,050.778 | 4,656.015 | 165.848 | 6,931.703 | about 1,039.555 |
| 2 | 4204 | 16.218 | 457.902 | 2,205.313 | 46.378 | 3,184.825 | about 439.593 |
| 3 | 43792 | 17.738 | 593.232 | 2,824.300 | 107.963 | 4,533.480 | about 978.663 |

*Residual = Python total minus the PowerShell `serialized` marker time. It combines process launch/startup, scheduling, process exit and pipe collection; **PowerShell startup and Python subprocess overhead cannot be independently separated** by these completed measurements. The first `script_started` marker was only 7.717, 19.421 and 11.584 ms after each PowerShell script clock began; this excludes the external process-launch time. Snapshot serialization was small compared with listener enumeration. No full attempt reached 30 seconds, so none reproduces R8's timeout.

During initial passive identity verification, a separate filtered `Get-NetTCPConnection -State Listen -LocalPort 59863` call remained incomplete for over 40 seconds and was interrupted with Ctrl-C **only in that R10-owned diagnostic PowerShell session**. A later targeted `netstat` confirmed the loopback listener and owner. That observation demonstrates that the listener cmdlet can stall beyond the production 30-second budget on this machine. The initial check lacked the intended explicit watchdog; it was manually bounded when the delay became apparent. No Editor process was interrupted. This is stronger evidence of a volatile listener-query cost, but without R8 phase markers it does not prove the listener cmdlet caused the historical R8 timeout.

The three completed listener phases ranged **2.205–4.656 seconds**, versus R9's 3.969 seconds. CIM ranged **0.458–1.051 seconds**, versus R9's 0.399 seconds. Total full probes ranged **3.185–6.932 seconds**, versus R9's 5.163 seconds. PowerShell startup/scheduling may contribute, but the observed long standalone listener call is the only R10 component observed exceeding 30 seconds. Shader load is a plausible concurrency factor only; it was not deliberately generated or causally measured here.

## Synthetic timeout lifecycle

An initial five-second synthetic `subprocess.run` timeout occurred before the child emitted its identity marker, so that attempt could not establish child identity or cleanup. The separate longer test used an R10-owned PowerShell script that printed its own PID/creation time, then slept without spawning descendants. Python `subprocess.run(..., timeout=15)` raised `TimeoutExpired` after **15,102.978 ms**. The marker identified child PID **43112**, creation UTC **2026-10-22T14:07:07.1866871Z**. A post-timeout Windows process query found PID 43112 **absent** and zero processes with parent PID 43112. The script intentionally created no descendants. This **DIAGNOSTICALLY VERIFIES** direct-child cleanup for this synthetic timeout. It does **not** establish that `subprocess.run` terminates arbitrary descendants or prove the exact historical R8 child lifecycle.

The first full timing result's `direct_child_absent_after=false` was a **diagnostic harness mistake**: `OpenProcess` can still query an exited process object while its parent retains a handle. The corrected second and third checks used `WaitForSingleObject` on the process handle and confirmed the direct child signaled exit. The original first record remains retained, with this correction stated explicitly rather than rewritten. No unrelated process was terminated.

## Security and source preservation

The production path remains `ConnectionManager` isolated dispatch → explicit session ID/allowlist and exact registration check → `WindowsProcessIdentityProbe` → `validate_process_snapshot` → native socket exchange only on success. The snapshot validation still checks PID, seven-digit start time, executable path, Windows-parsed executable command-line token, exactly one matching project `.uproject` argument, unique listener owner and loopback-only address. Registration token authentication is still mandatory at the native bridge; no shared-session fallback or indefinite identity cache was added. Errors fail closed. No registration credentials were copied into R10 evidence.

Production source and relevant preserved artifact hashes at preflight:

| Artifact | SHA-256 |
|---|---|
| R8 report | `9ACB49FD64C4B03490157B237583EB135FAA9FF582042551E4E6D575AD524EA7` |
| R9 report | `1E551FE8B17A2AB0F9575A0BDC302E3EB6D6802BEC9E70E05AAF98E3613775D7` |
| `source/server/core/process_identity.py` | `6CA830A3C35B1A9D290EF8A3E5DE7C9005E0043523177978B42E296A5BDBA9EB` |
| `source/server/core/connections.py` | `C7FD5E6A466F847C8A2FEC9DB7CFB4593902B777B4BE2133DB773BDF2F929914` |
| `source/tests/test_host_config.py` | `6437979DADD92EE63B19257568E8651E7A07DD1816A48C8395AD169D44922115` |
| R8-changed `Config/DefaultEngine.ini` | `E6D3D12D7923838AD0724ED85AC781100C3E75FE90AFE8FA6D9E2BAF9F3BA863` |
| R7 Editor plugin DLL | `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37` |

No production implementation, test, project configuration, compiled DLL/PDB, R8 session file, registration, or prior report was edited. Existing Editor logs, caches and the historical telemetry anomaly remain as found. No host, Editor, build, authenticated request, or native inspector was launched in R10.

New R10 evidence hashes:

| `runtime/R10` file | Bytes | SHA-256 |
|---|---:|---|
| `identity_phase_probe.py` | 5,143 | `0BF7B152FC579C3EA36017ECDF8E9F0E8F4E29963B91F8B4306C47AB10A48A60` |
| `phase_results.json` | 2,232 | `1FD7D180A4948FCD450A56AC1487250FA0C1F400C7D11A60147E4F2CACBE54AA` |
| `timeout_child_probe.py` | 2,236 | `B8C6BCFAAF79DEC7C9C0A7EFC9135319B3C4B66B97600A1F6DA437BA74412151` |
| `timeout_result.json` | 312 | `7D8EAFFFAF024B71B5A1357A85B56FC1B59969AC105D713B950B42D7EB7E2FB8` |

## Findings and next stage

- **DIAGNOSTICALLY VERIFIED:** The filtered listener cmdlet dominates normal probe duration and separately stalled beyond 30 seconds once; a synthetic timeout killed and waited for its direct PowerShell child.
- **HYPOTHESIS:** R8's intermittent `powershell_timeout` arose in the same listener enumeration. R8 lacks phase markers, so the failing phase remains unknown.
- **NOT TESTED:** Native dirty-package/world/mesh inspectors, arbitrary descendant cleanup, complete separation of startup versus Python overhead, and any replacement identity-query implementation.
- **BLOCKED:** Runtime inspector acceptance and production Phase 6C.

The smallest proposed correction for a separately authorized stage is to replace only the variable listener-enumeration portion of `source/server/core/process_identity.py` with a narrowly scoped Windows API table query or another measured exact-port method, while retaining the complete snapshot predicates and 30-second fail-closed budget. First verify that it returns the same owner/address set for the pinned port, rejects wildcard and mismatched owners, handles IPv4/IPv6 and API errors, and remains bounded under load. Add synthetic identity/timeout/child-cleanup tests and compare results against the present PowerShell method. Do not implement or deploy it from R10. A later authenticated runtime retest needs separate authorization; no R11 work begins automatically.
