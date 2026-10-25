# ForgeMCP Stage A7K46-C0B-R23 — Persistent Worker Acceptance

Date: 2026-10-22 UTC  
Engine: Unreal Engine 5.6.1 / changelist 44394996  
Disposition: **Authenticated native request reliability PASS in the one bounded disposable session. Green indicator NOT VERIFIED; alpha release NOT STAGED.** Official Engine and Production Phase 6C remain **NO-GO**.

## Baseline and implementation

The R20–R22 reports, correlated evidence and current isolated source were reviewed. R21/R22 authenticated native startup `health` and `project_info`, while later explicit requests timed out after listener child creation and before the first child marker. R22 showed that serializing probes removed overlap but did not resolve the repeated child-startup failure. The exact reason those earlier children stalled remains unproven; R23 removes repeated listener-interpreter startup from the isolated request path rather than assigning an unsupported OS root cause.

The isolated host now starts one private `C:\Program Files\Python\Python311\python.exe -I -S` worker from an absolute C0B script path during its lifespan initialization. A bounded, line-delimited stdin/stdout protocol carries a 32-character request ID and exact port. The worker calls the existing `GetExtendedTcpTable` implementation for **both IPv4 and IPv6 on every request** and returns all matching owner/address rows. It has no network listener, registration access, token or session-selection role. The host still performs fresh filtered CIM PID/start/executable/command-line checks, validates the private registration, applies the existing unique loopback-owner validator, and authenticates each native socket request. R22's serialized checks and 30-second aggregate queue/CIM/listener deadline remain in force; no positive identity result is cached.

The supervisor checks the direct process handle's creation FILETIME, executable path, ready PID and response request ID. It rejects malformed, stale, oversize, missing or timed-out responses, invalidates the worker and terminates/reaps only that owned process. A failed worker is not automatically restarted. Worker diagnostic-file environment variables are removed before launch so synchronous marker writes are outside its request path. Worker lifecycle events log sanitized PID/creation/exit details. The IPC payload is under 256 bytes and one query is in flight; the pipe-write operation itself has no independent OS-level write watchdog, a remaining engineering limit for broader production hardening.

Only isolated C0B Python source/tests changed. Relevant final SHA-256 values:

| File under `source` | SHA-256 |
|---|---|
| `server/core/persistent_listener_worker.py` | `166A524DF014E5524D275F903FAF7ED6E80747BC93E81DD940F1338DE689C35C` |
| `server/core/windows_tcp_worker.py` | `FD9A127857FC049F683F15ACF3EB96FDD9554E33093F81024BF8DC5BDDDAC67E` |
| `server/core/process_identity.py` | `8E150EBAB7792367985466F07CC096A64B99D850220CCE2DA8176F0C1AB5B98E` |
| `server/core/connections.py` | `B6D2100CDA849DEE68E562BA94CFC793A2233463F59E13BB5413C3AD0B27A39E` |
| `server/core/connection_monitor.py` | `0A25D2E2AC69D0A54C0B1E2BC5E4EA4419A411CDB5B2EA6753605771575EAA29` |
| `tests/test_persistent_listener_worker.py` | `35BAA174BE74512FE3B6D7FBDC8AD67B144B8B057C8206A1B2170841C5E1A991` |

The existing native Editor, Runtime and project DLL hashes remained `A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37`, `2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F`, and `E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7`. No C++ build, hot reload or official installation edit occurred.

## Offline verification

**107 focused tests passed in 8.68 seconds**, including host/session/security/dirty-package/native-contract tests and new worker tests for fresh repeated listener queries, concurrent calls, worker exit, stale response and timeout cleanup. Existing tests cover IPv4/IPv6 table decoding, wrong/wildcard owners, malformed results and identity/session rejection. Ruff `check server tests scripts`: **PASS**. Python `compileall -q server tests scripts`: **PASS**. A host-equivalent combined probe used the worker to return PID 42880, pinned seven-digit start, owner 42880 and `127.0.0.1`; the worker exited after that offline probe. These checks do not prove arbitrary descendant-tree cleanup or a hard bound on Windows pipe writes.

## One authorized live session

A fresh passive preflight before the host found the original disposable Editor PID **42880**, creation UTC **2026-10-22T06:37:06.5248750Z**, exact StageA7G executable, exact C0B disposable project argument, private `unreal-42880` registration and unique `127.0.0.1:59863` listener owned by that PID. The client combined check took **1,394.979 ms**. No replacement Editor was launched.

Exactly one isolated host started with the `preservation_readonly` profile. MCP initialization took **5,116.921 ms**. Its catalog contained exactly `unreal_project_info`, `unreal_inspect_dirty_packages`, `unreal_inspect_static_mesh` and `unreal_inspect_world_save_scope`, each `readOnlyHint=true`. Missing and unallowlisted session IDs returned `session_id_required` in **5.950 ms** and `session_not_allowed` in **3.901 ms**, before native contact. Host startup logs record authenticated native `health` and `project_info`.

The first explicit `unreal_project_info` returned an authenticated native success in **4,515.209 ms**, with the expected disposable project, `/Engine/Maps/Entry.Entry`, UE 5.6.1 and PIE false. A second explicit foreground `unreal_project_info` succeeded in **947.830 ms** after a fresh identity check. A periodic authenticated `health` response occurred among the foreground calls; no listener child-startup timeout recurred. Two bounded dirty-package calls succeeded in **1,046.415 ms** and **955.035 ms**. This is a bounded live reliability PASS for the requests observed, not a claim of indefinite uptime.

The initial and final native inventories each reported `inventory_complete=true`, **930** inspected loaded packages and the same **three dirty package rows** (`/Engine/Maps/Entry`, `/Script/MediaPlate`, `/Script/SlateCore`) with matching path, dirty flag and package flags. The two snapshots have distinct IDs, as expected. The five monitored disposable Content/Config files had identical hashes before/after inspection and before/after the host context. This supports no attributable change in the observed dirty-package and file state. The tool does not enumerate the identity of every clean loaded package, so complete in-memory package preservation is not established. No world-save-scope or StaticMesh handler was run in R23.

The host log identifies its owned worker as PID **38416**, creation FILETIME ticks **134371672353630973**, and reports its stopped exit status **1** during host shutdown. A targeted post-run OS check found that worker PID absent. The one host context exited. Disposable Editor PID 42880 remained running; no Editor close/restart, save/discard, asset mutation, Landscape action, A7K41 contact or production project access was performed.

## Indicator and release disposition

The disposable Editor's **actual green indicator was not safely observed during the short host session**. Native authenticated activity was proven by replies and host logs, but source-level six-second indicator logic and listener presence do not prove the rendered dot's color. The subsequent idle-yellow transition was also not observed. This visual gate is **NOT VERIFIED**, without implying a connection failure.

No next-version alpha package was staged. The required release gate remains incomplete because the indicator was not observed, full native inspector/preservation acceptance remains bounded to dirty inventory, and independently installable package integrity has not been established. The appropriate next deployment action is a separately scoped, non-deploying release-preparation pass after visual indicator acceptance and package validation; do not overwrite a loaded or official Engine plugin. This R23 session authorizes no additional host launch or Editor action.

| Gate | R23 result |
|---|---|
| Persistent worker implementation | **PASS for isolated host live operation**, with pipe-write watchdog limit recorded. |
| Authenticated native startup and explicit `project_info` | **PASS**. |
| Repeated fresh foreground requests | **PASS for two observed project-info calls and two dirty inspections**. |
| Periodic health coexistence | **PASS in this bounded session**. |
| Dirty-package preservation | **PASS for complete dirty rows/counts and five monitored files; broader package identity INCOMPLETE**. |
| Actual green/idle indicator | **NOT VERIFIED**. |
| Alpha release candidate | **NOT STAGED**. |
| Official Engine migration | **NOT AUTHORIZED**. |

Evidence is preserved under `runtime/R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06/R23-20261022T182607Z-1e2ee1211e7f4b9580ec66db13f0556c`. `evidence/result.json` SHA-256 is `BB6AE1AFF5ADDDF44EDF50AF35C76B143CF44D3F1DE48416F181371E94449D6D`; sanitized `logs/host-stderr.txt` SHA-256 is `C1FE21F80633AFD612C4738F93F9B6AFFD89903F176297BEB2FA8F32A8FD521D`. Prior reports/evidence were retained.

**Final disposition: native communication and bounded dirty inspection PASS; indicator NOT VERIFIED; alpha NOT STAGED; Production Phase 6C NO-GO. Stop after reporting.**