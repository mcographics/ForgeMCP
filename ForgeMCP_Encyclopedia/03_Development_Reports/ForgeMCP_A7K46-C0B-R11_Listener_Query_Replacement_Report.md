# ForgeMCP Stage A7K46-C0B-R11 — Listener Query Replacement

Date: 2026-10-22 UTC  
Engine target: Unreal Engine 5.6.1 / 44394996  
Mode: isolated C0B Python source repair and offline validation  
Disposition: **IMPLEMENTED; OFFLINE VERIFIED; LIVE NATIVE INSPECTOR NOT RETESTED.** Production Phase 6C remains **NO-GO**.

## Result

The intermittently slow `Get-NetTCPConnection` call was removed from the C0B host identity probe. Filtered CIM still supplies the exact process PID, creation time, executable and full command line. A separate, strictly watched Python child now queries Windows IP Helper `GetExtendedTcpTable` for both IPv4 and IPv6 owner-PID listener tables and returns **all** rows matching only the pinned port. The existing snapshot validator then rejects missing, conflicting-owner, wildcard or non-loopback rows. Both child operations share the original **30-second overall identity-preflight budget**. A timed-out subprocess fails closed; no result is cached as a bypass.

This is a Python host change in the isolated development copy. No ForgeMCP host was started; no authenticated request or native inspector was made. The R7 plugin binaries were not rebuilt or deployed. A7K41 and production Phase 6C remain outside scope.

## Baseline and disposable identity

The complete R8, R9 and R10 reports and `process_identity.py`, `connections.py` and the identity tests were reviewed. Before editing, `process_identity.py` matched R9 SHA-256 `6CA830A3C35B1A9D290EF8A3E5DE7C9005E0043523177978B42E296A5BDBA9EB`; `connections.py` matched `C7FD5E6A466F847C8A2FEC9DB7CFB4593902B777B4BE2133DB773BDF2F929914`; `test_host_config.py` matched `6437979DADD92EE63B19257568E8651E7A07DD1816A48C8395AD169D44922115`. The R10 report remains SHA-256 `B6556396096162DBE46B977CB41266B9BDA986862C97D303C308F6970EDA38DB`.

Passive OS metadata before comparison confirmed the R8 disposable Editor PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, exact StageA7G UnrealEditor executable, and exact C0B disposable project argument. A later passive check at 2026-10-22T14:59:30.7692499Z found that same process and start pin still present. The new query and a targeted existing OS observation both returned the private listener `127.0.0.1:59863` owned by PID 42880. No endpoint connection was made. Historical protected PID 15144 was not contacted.

R10 measured the prior filtered listener cmdlet at **2.205–4.656 seconds** within three completed probes; another standalone invocation stalled beyond 40 seconds before only its own diagnostic shell was interrupted. R8's 30-second historical timeout lacked internal phase markers, so the exact R8 blocking operation remains unproven. The replacement addresses the independently observed volatile listener-query cost without changing CIM or identity acceptance rules.

## Windows API and decoding

The installed Windows SDK 10.0.22621 headers define `GetExtendedTcpTable(PVOID, PDWORD, BOOL, ULONG, TCP_TABLE_CLASS, ULONG)` with Windows calling convention, `TCP_TABLE_OWNER_PID_LISTENER` enum value **3**, and owner-PID table/row layouts in `iphlpapi.h`, `Iprtrmib.h` and `tcpmib.h`. The C0B implementation uses `ctypes.WinDLL("iphlpapi")`, DWORD/ULONG arguments, and the SDK's IPv4 `MIB_TCPROW_OWNER_PID` and IPv6 `MIB_TCP6ROW_OWNER_PID` field order. It requests **both** `AF_INET` and `AF_INET6`; failure of either family aborts the whole snapshot. The API returns a table of all listeners for that family, so the child filters the decoded rows by the exact requested port afterward.

Port DWORDs are decoded from their network-order low 16 bits with `socket.ntohs`; unexpected upper bits fail closed. IPv4 addresses are reconstructed from the DWORD's in-memory bytes. IPv6 uses all 16 address bytes and appends a nonzero numeric scope ID. The SDK listener state must be `MIB_TCP_STATE_LISTEN` (2). For a matching port, owner PID zero is rejected. No matching rows produces an empty snapshot, which the unchanged validator rejects.

The first size query must return `ERROR_INSUFFICIENT_BUFFER` (122). The child caps any table at **8 MiB**, allows at most **three** allocation attempts per family, rejects invalid/truncated counts or sizes, and fails on unexpected API return codes. An unsupported or malformed family is not silently ignored. Native API calls execute in the dedicated Python child; the host waits only within the remaining 30-second identity budget and `subprocess.run` stops and reaps that direct child on timeout. Arbitrary descendant cleanup is not claimed; the helper does not intentionally spawn descendants.

## Parity, timing, and security checks

The standalone Windows API prototype returned exactly `(42880, 127.0.0.1)` for the live disposable port; its first invocation took **511 ms** including PowerShell wrapper measurement overhead. The comparison harness attempted three old/new pairs. Pair 1 completed both queries but a diagnostic parser error occurred before the result was recorded; that harness error was corrected, and the remaining two pairs were recorded without exceeding the three-pair cap:

| Pair | Existing PowerShell listener query | Windows API child | Returned rows | Parity |
|---:|---:|---:|---|---|
| 2 | 2,579.060 ms | 254.828 ms | `(42880, 127.0.0.1)` | PASS |
| 3 | 3,586.522 ms | 357.982 ms | `(42880, 127.0.0.1)` | PASS |

Both completed recorded comparisons used 30-second child watchdogs. One passive full **new** identity-probe invocation, outside an MCP host, completed in **2,727.686 ms** and returned the exact pinned PID/start/listener. This includes unchanged filtered CIM and the new listener child. These timings demonstrate current parity and lower observed listener-query latency; they do not prove that Windows API performance can never vary or that the native Unreal inspector works.

Synthetic tests verified IPv4 and IPv6 loopback decoding, IPv6 scope preservation, exact port filtering while retaining duplicate/conflicting rows, wrong owner, absent listener, conflicting owners, wildcard IPv4/IPv6, non-loopback addresses, truncated/malformed tables, buffer resizing and retry exhaustion, oversized buffers, API failure, and rejection when the IPv6 family fails after IPv4 succeeds. Existing process-validator tests still reject wrong PID, start time, executable, project argument and listener ownership. New host tests verify listener-child timeout and malformed/failed child output fail closed. R10's controlled `subprocess.run` timeout separately observed an R10-owned PowerShell child absent after timeout; R11 did not run a new live helper-hang experiment. The 30-second timeout is unchanged and is shared across CIM plus listener phases.

Exact session ID, allowlist, private registration, native token authentication, full command-line/project parsing, unique owner, loopback-only binding, and no shared-session fallback remain unchanged. The host still logs only sanitized failure categories. The helper returns no registration data or credentials.

## Modified files and validation

Only the isolated C0B source and directly related tests changed:

| File | Before SHA-256 | After SHA-256 |
|---|---|---|
| `source/server/core/process_identity.py` | `6CA830A3C35B1A9D290EF8A3E5DE7C9005E0043523177978B42E296A5BDBA9EB` | `E7A812F17D3B71806C21D2FA439CA8D4E2CD38F5C4AD06EE36E2528E68F7F2C6` |
| `source/server/core/windows_tcp_listener.py` | absent | `992ABD7AEB9CEA39C4DCEF399334374A4360E2F4706C21BADCAF90E941F0850B` |
| `source/tests/test_host_config.py` | `6437979DADD92EE63B19257568E8651E7A07DD1816A48C8395AD169D44922115` | `CF4EDCDC0C7C27959186B32F395C9515B52FCF8D6D88DE53479C9808C24B250B` |

New R11 prototype, comparison and synthetic test evidence is under `runtime/R11`; `comparison_results.json` is 860 bytes, SHA-256 `A9D430CCA7D7DA2CC7C96BC5F47DF43AA558D72447DE76ED2D61667E27637E17`. The final R11 synthetic test file is SHA-256 `B5CDD76444A1FE91D7DCF3CD3F1BF69DBCCC394F02961CFFC2FA7366D48A2163`.

Focused pytest covering existing security/connection/dirty-package/native-plugin contracts and the new table tests: **111 passed in 8.72 seconds**. The final 13 R11 synthetic table tests separately passed in **0.22 seconds** after test import formatting. Ruff on `server tests scripts` and the R11 test file: **PASS**. Python `compileall -q server tests scripts`: **PASS**. No native compilation, plugin load, MCP host launch, or native inspector response is claimed.

The project-local R7 Editor DLL remains 2,728,960 bytes, SHA-256 `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37`. R8's `DefaultEngine.ini` change, logs, private registration and the historical telemetry anomaly were left as found. No prior report was rewritten.

## Remaining limits and next action

**IMPLEMENTED:** bounded, exact-port Windows API listener snapshot in the isolated C0B Python host path. **OFFLINE VERIFIED:** synthetic IPv4/IPv6 and negative security cases, two recorded real-port parity comparisons, one passive full-probe result, and the focused regression suite. **LIVE NATIVE INSPECTOR NOT RETESTED:** no authenticated host or Unreal handler was called.

The disposable Editor still runs; its R8 close attempt remains unresolved. R8's exact stalled phase remains unknown. Real IPv6 loopback was verified synthetically and its live family table queried successfully, but no live IPv6 listener on the pinned port existed to compare. The earlier comparison harness parser error explains the missing first pair record; it is not an API failure. A system-wide trace or all-load performance guarantee was not established.

The smallest next separately authorized stage is one dedicated, exact-session runtime retest against the existing verified disposable Editor, with a fresh identity gate and a bounded read-only dirty-package request before any world/mesh inspection. If the Editor identity or listener differs, stop. This R11 report does not authorize that host launch, any Editor lifecycle action, saving, build, protected A7K41 contact, or Landscape work. Production Phase 6C remains **NO-GO**.
