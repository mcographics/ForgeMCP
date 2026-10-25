# ForgeMCP — Post-R23 Final Connection Verification and Development Environment Cleanup

Date: 2026-10-22 UTC  
Observation cutoff: 2026-10-22 19:00:19 UTC  
Scope: bounded read-only verification  
Final disposition: **BLOCKED before regular-engine connection acceptance.** The StageA7G Engine target is absent, R23 source and evidence remain preserved, and the regular safe Editor lacks a verified private registration and loopback endpoint. No acceptance host was launched. Production Phase 6C remains **NO-GO**.

## R23 result and preserved recovery material

R23's recorded C0B session authenticated native startup health, completed two explicit project-info requests, and completed two dirty-package inspections. Both inventories reported 930 inspected loaded packages and the same three dirty package rows. Five monitored Content/Config hashes were unchanged. The rendered green and idle-yellow indicator states were not observed, and R23 did not establish official-engine readiness.

The R23 evidence files were present and retained their reported hashes:

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| result.json | 42,633 | BB6AE1AFF5ADDDF44EDF50AF35C76B143CF44D3F1DE48416F181371E94449D6D |
| sanitized host-stderr.txt | 893 | C1FE21F80633AFD612C4738F93F9B6AFFD89903F176297BEB2FA8F32A8FD521D |

The main ForgeMCP source and the C0B source copy matched byte-for-byte for all eight R23 connection files checked:

| File | SHA-256 in both source trees |
|---|---|
| server/core/persistent_listener_worker.py | 166A524DF014E5524D275F903FAF7ED6E80747BC93E81DD940F1338DE689C35C |
| server/core/windows_tcp_worker.py | FD9A127857FC049F683F15ACF3EB96FDD9554E33093F81024BF8DC5BDDDAC67E |
| server/core/process_identity.py | 8E150EBAB7792367985466F07CC096A64B99D850220CCE2DA8176F0C1AB5B98E |
| server/core/connections.py | B6D2100CDA849DEE68E562BA94CFC793A2233463F59E13BB5413C3AD0B27A39E |
| server/core/connection_monitor.py | 0A25D2E2AC69D0A54C0B1E2BC5E4EA4419A411CDB5B2EA6753605771575EAA29 |
| server/core/windows_tcp_listener.py | 3BFCE867F3A9D59E72F14068ADD33FA8D022953371C0102C90E2538732F2FA0B |
| server/core/windows_tcp_bootstrap.py | 142C8B9FB5655F683A08E2FE3062CB2ABD8D59F3CAABF16827388DFB0BD03CE8 |
| tests/test_persistent_listener_worker.py | 35BAA174BE74512FE3B6D7FBDC8AD67B144B8B057C8206A1B2170841C5E1A991 |

The earlier consolidated-tree run passed 490 tests, Ruff, and compileall. Those recorded checks were not rerun here. The current C0B disposable Editor, Runtime, and project DLLs also remain present at their R7 hashes. No Python or native source was changed during this verification.

## Development Engine deletion

G:\ForgeMCP-StageA7G-UE56\UE_5.6 was absent at the observation cutoff. The owner-initiated deletion appears complete at that target path; this pass did not restore files or delete anything further.

Because the tree was already absent, this pass could not inventory any remaining files inside it or compare every former source, SDK dependency, Intermediate file, and the historically reported 25 UBT run markers. Earlier reports noted distinct Engine plugin files and build outputs there, but differing hashes alone do not establish that those files were needed by the official installation. The C0B source correction copies, R7 disposable DLLs, R23 reports, and R23 acceptance evidence were independently found in their existing locations.

No missing dependency has been demonstrated. A complete pre-deletion uniqueness comparison is unavailable, so this report cannot establish that every item removed with the tree was unnecessary. No further deletion is recommended or was performed.

## Current regular-Engine Editor and registration

The official Engine reports Unreal Engine 5.6.1, changelist 44394996. The existing package-acceptance Editor remained present:

| Field | Current observation |
|---|---|
| PID | 43340 |
| Creation time | 2026-10-22 18:36:25 UTC |
| Executable | G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe |
| Project | G:\ForgeMCP\Saved\UnrealPackageAcceptance-d2fa565a7fb24586982fdd697cbf826f\ForgePackageTest.uproject |
| Startup map argument | /Engine/Maps/Entry |
| Project-local Forge plugin directory | Absent |

The Editor log's last write was 18:45:33 UTC. The relevant Forge entry says the Engine plugin MajesticForge was mounting. The inspected log has no later Forge module-load or registration confirmation and no explicit Forge startup error. Process module enumeration returned no MajesticForge module. The Editor was still present and responsive, but startup completion was not established.

No registration named for PID 43340 was found in the safe project, the recovery stage roots, or the checked per-user Unreal registration directory. The filenames found in those locations referred to PIDs 32168, 10376, and 34636; they were not used. No token value was displayed or saved in this report.

PID 43340 owned one TCP listener, 0.0.0.0:35402. That listener is not a verified ForgeMCP endpoint and is not loopback-only. No 127.0.0.1 listener was owned by this Editor. The observed boundary is between Engine plugin mounting and creation of a verified private session registration with a loopback endpoint. The evidence does not distinguish delayed startup from bridge initialization failure.

A pre-existing ForgeMCP host invocation was also present: PID 4480 runs G:\ForgeMCP\.venv\Scripts\python.exe -m server.main, with child PID 25964 running the same module through the base Python interpreter. This invocation started before the R23 consolidation. Neither process owned a TCP listener, and its loaded code version and session configuration were not established. It was not used for acceptance; no host was launched during this verification.

## Host and native compatibility

The installed Engine Forge plugin descriptor is version 0.2.16-alpha.1, numeric version 30. Its plugin module manifest BuildId is 43139311, matching the official Engine BuildId.

| Official plugin module | Bytes | SHA-256 |
|---|---:|---|
| UnrealEditor-MajesticForge.dll | 2,655,232 | 297427727F3EEA60419E8CCCBD37289DE534FCE2FFA2D7CFB0D3FA6F070D20DF |
| UnrealEditor-MajesticForgeRuntime.dll | 114,688 | DA58F75E596F91BE0ED798185686179E89ED2C1063AE1B64D9F12D8F626F0BAB |

The experimental alpha candidate contains those exact same native DLLs. The consolidated R23 changes are in Python identity verification and worker supervision. The checked Python request framing uses protocol version 1 and request IDs; the plugin source accepts protocol version 1 and echoes request IDs. This establishes structural protocol compatibility and gives no evidence that a native rebuild is required. It does not prove that the installed binary completed module loading or authenticated a request in this Editor.

The active main-tree host predates the R23 consolidation, and no valid registration for PID 43340 was available. The consolidated host therefore was not connected to the regular Engine in this pass.

## Bounded acceptance result

The conditional acceptance did not start because its preconditions failed: no registration matching PID 43340 and no verified loopback ForgeMCP endpoint were available. No host initialization, fresh host identity probe, native authentication, health request, project-info request, second request, or dirty-package inspection was performed. The indicator was not observed. No retry occurred.

There is no current dirty-package snapshot for PID 43340. R23's C0B dirty rows are historical and do not establish the current safe Editor's state. This verification did not modify or save any asset or package.

## Experimental alpha candidate

The existing 0.2.16-alpha.2 candidate remains explicitly experimental and non-deployable. The staged package was rechecked:

| Check | Result |
|---|---|
| Manifest entries | 94 |
| Candidate size/hash mismatches | 0 |
| ZIP entries and manifest coverage | 94; no mismatch |
| ZIP CRC check | Passed |
| ZIP SHA-256 | 44A3273F1F3D4039B01A13D0611F9F251AAB24F3BF82570072B42EB1EC7A9687 |
| Metadata | Plugin 0.2.16-alpha.2 / numeric 31; host 0.3.16; UE 5.6.1-44394996 |
| Rollback material | Present; 66 files, including the prior plugin tree and main-source rollback archive |

The candidate's file integrity and rollback materials are present. Installability and upgrade behavior have not been exercised. Before the candidate can be considered installable, the regular Editor must produce a valid private loopback registration, accept authenticated requests from the consolidated host, and pass the requested read-only checks. The rendered indicator also remains unverified. No deployment or official Engine modification occurred.

## Editor preservation and shutdown

At the observation cutoff, historical PID 15144 (A7K41) and PID 42880 (C0B disposable Editor) were absent. Their current dirty state cannot be queried, so their final saved/unsaved state is unknown. No lifecycle action was taken.

PID 43340, the safe regular test Editor, remained open; its dirty state could not be queried without an accepted session. Another Editor, PID 13432 with G:\ForgeMCP\ForgeMCPDev.uproject on its command line, was also present. Its project role and dirty state were not investigated. No Editor was closed, saved, discarded, restarted, or terminated. The production city project and L_City_World_Master were not accessed.

**Shutdown recommendation:** leave current Editors open until each relevant project's dirty state is verified through an authorized read-only path and the owner explicitly directs shutdown.

## Final gates and remaining blocker

| Gate | Result |
|---|---|
| R23 bounded C0B native acceptance | **PASS as recorded; indicator not verified** |
| R23 source and recovery evidence preserved | **PASS** |
| StageA7G Engine target directory | **Absent; deletion already occurred** |
| Official Engine version and plugin BuildId compatibility | **PASS for version/build metadata** |
| Candidate package consistency and rollback presence | **PASS** |
| Regular safe Editor identity | **PASS for current process/project fields** |
| Forge plugin module load completion | **NOT VERIFIED** |
| Private registration for PID 43340 | **NOT FOUND** |
| Loopback listener for PID 43340 | **NOT FOUND** |
| Authenticated regular-Engine acceptance | **NOT TESTED** |
| Connection indicator behavior | **NOT VERIFIED** |
| Native rebuild required | **NO EVIDENCE OF NEED** |
| Alpha installability | **NOT ESTABLISHED; candidate remains experimental** |
| Production readiness | **NO-GO** |

The exact blocker is the absence of a verified private registration and loopback ForgeMCP endpoint for the running safe Editor. No host acceptance was attempted. This verification does not authorize another Editor launch, restart, recovery cycle, deployment, shutdown, or further deletion.

**Final verdict: BLOCKED before regular-engine connection acceptance. Production Phase 6C remains NO-GO.**