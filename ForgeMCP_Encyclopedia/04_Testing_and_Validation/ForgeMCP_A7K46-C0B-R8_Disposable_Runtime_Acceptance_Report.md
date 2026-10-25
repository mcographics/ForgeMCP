# ForgeMCP Stage A7K46-C0B-R8 — Disposable Runtime Acceptance

Date: 2026-10-22 (UTC)  
Engine: Unreal Engine 5.6.1 / 44394996  
Mode: Isolated runtime validation  
Disposition: **PARTIAL PASS for module loading, authenticated project identity and exact four-tool catalog. Inspector acceptance BLOCKED by powershell_timeout. Disposable Editor shutdown BLOCKED; PID 42880 remains running. Production Phase 6C remains NO-GO.**

## 1. Result and stop boundary

Exactly one disposable Editor launch and one dedicated isolated host attempt were made. The expected native Editor, Runtime and project modules loaded from the C0B project and their on-disk hashes matched R7. The host authenticated to the new private session, exposed exactly the four approved read-only tools, rejected missing and unallowlisted session IDs, and successfully returned the expected project/world information.

The first dirty-package request returned identity_preflight_failed. The existing sanitized host log records the underlying category as powershell_timeout. The passive PowerShell identity probe exceeded its existing 30-second bound before the inventory request could be sent to the native observer. The client stopped and its host context exited; no second host was launched. No world-save-scope or StaticMesh request was subsequently made.

No current dirty-package snapshot, snapshot ID, package count, or native inspector side-effect baseline was obtained. No world/mesh acceptance PASS is inferred from the successful connection.

The host processes exited. The new Editor accepted CloseMainWindow after exact identity reverification, but did not exit within 60 seconds and was still active at the final passive check. No force termination, save/discard selection, source repair, rebuild, or configuration rollback was issued.

## 2. R7 evidence and preflight

Existing development root: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1

Disposable project: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject

The full R7 report was reviewed and retained SHA-256 DE44D4290B82A0ED661DD6CD6876E21E392C2B1E35689EFEE061ED53D01F91B1. Source/configuration/descriptor/prior-report inputs selected from the R7 manifest initially matched. All three module hashes and the Engine/project/plugin BuildId 43139311 matched. Plugin descriptor version is numeric 30 / 0.2.16-alpha.1. Binary hashes still match after the attempt.

Before launch, passive OS inspection identified the existing protected Editor at PID 15144 with the official Engine executable and A7K41 project argument. It was not connected to, closed, restarted, or otherwise manipulated. Only the new C0B process was targeted for R8 operations.

Prelaunch memory query reported 20,364,068 KiB free physical memory (about 19.4 GiB) of 33,418,384 KiB visible memory. Disk checks were queried; exact final disk-space values are {'C:\\': 30475190272, 'G:\\': 99925651456}. Those numeric disk values are post-run observations, not a reconstructed prelaunch disk record.

The existing Saved\ForgeMCPDisposableProject.json marker contains a stale G:\ForgeMCP-C0B-Dev-... drive-root project/isolation path rather than this actual G:\ForgeMCP\Saved\... path. It was not modified. Exact descriptor, executable, command-line, loaded-module and private-session identity were independently verified. No fixture mutation, Landscape operation, package exception or save authorization relied on that marker.

## 3. Editor launch and loaded modules

- PID: 42880
- Process start UTC (CIM pin): 2026-10-22T06:37:06.5248750Z
- Owner: ALIENWARE-PC\Kenne
- Executable: G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe
- Session: unreal-42880
- Private native endpoint: 127.0.0.1:59863; listener uniquely owned by PID 42880
- Private root: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\runtime\R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06
- Launch count: 1

Exact recorded command line:

    "G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" "G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject" /Engine/Maps/Entry -SkipCompile -Unattended -DisablePlugins=Cargo -ddc=InstalledNoZenLocalFallback -NoSplash "-AbsLog=G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\runtime\R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06\logs\Editor.log"

Process-scoped session roots, TEMP/TMP, LocalAppData/Roaming profile paths and local DDC path were placed under this private root. Shared DDC was disabled and the installed non-Zen local fallback graph selected. No global settings were edited. Startup used the explicit Entry map override and normal graphics startup, without NullRHI.

Installed LaunchEngineLoop.cpp was reviewed before launch: SKIPCOMPILE clears forced startup compilation, and unattended mode exits on incompatible modules instead of accepting a rebuild prompt. No agent UBT build was launched. Startup nevertheless performed the Engine automatic QueryTargets metadata query described below.

Fresh identity comparison initially hit a diagnostic harness formatting issue: ConvertFrom-Json materialized the pinned ISO timestamp as System.DateTime. Both timestamps were then normalized to the same seven-digit UTC format and matched exactly; executable and full command line also matched. Identity checks were preserved.

| Mapped module | On-disk SHA-256 at loaded path |
|---|---|
| UnrealEditor-A7K46C0B_ReadOnlyInspector.dll | E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7 |
| UnrealEditor-MajesticForgeRuntime.dll | 2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F |
| UnrealEditor-MajesticForge.dll | A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37 |

All three mapped paths are beneath the exact disposable project. These are file hashes at mapped paths, not fingerprints of the in-memory image bytes. Native module loading passed; native inspector behavior did not reach acceptance.

## 4. Dedicated host, authentication and catalog

Source runtime: ForgeMCP core 0.3.15 from G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\source. The exact-session, authentication and preservation_readonly implementations were unchanged. The host used the new private registration only; no A7K41 registration/token or shared-session discovery was used.

Host ID: R8host-42880. The client observed the venv launcher PID 43024; the server log identifies actual host PID 8244. Both were absent at the final process checks. An exit code was not retained, so cleanup is reported as verified process absence rather than a claimed exit-code-zero result.

The actual MCP catalog was exactly:

1. unreal_project_info
2. unreal_inspect_dirty_packages
3. unreal_inspect_static_mesh
4. unreal_inspect_world_save_scope

All four actual annotations reported readOnlyHint=true. No mutation tool was exposed. Registration/schema presence is not treated as native handler acceptance.

| Request | Actual result |
|---|---|
| unreal_project_info with no session ID | Rejected: session_id_required |
| unreal_project_info with r8-not-allowlisted | Rejected: session_not_allowed |
| unreal_project_info with unreal-42880 | Authenticated success; exact expected project/world/engine; PIE false |
| unreal_inspect_dirty_packages, exact session, limit 50 / offset 0 | Rejected by passive identity preflight; identity_preflight_failed, underlying powershell_timeout |

No registration credential was printed or copied into evidence/report payloads. Native registration remains in the private session directory while the Editor remains running.

## 5. Confirmed project/world and inventory failure

- Project: A7K46C0B_ReadOnlyInspector
- Project file: G:/ForgeMCP/Saved/ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1/disposable/A7K46C0B_ReadOnlyInspector/A7K46C0B_ReadOnlyInspector.uproject
- Runtime Engine: 5.6.1-44394996+++UE5+Release-5.6
- Active world path: /Engine/Maps/Entry.Entry
- PIE: false
- Dirty snapshot ID/count/completeness: UNKNOWN; no snapshot returned
- Current map IsDirty, transient associations, World Partition, streaming levels, external packages and build data: NOT TESTED

The host stderr records:

    Isolated process preflight rejected a request (powershell_timeout)

The public response intentionally collapses the underlying category to identity_preflight_failed. In existing connections.py, the ProcessIdentityError handler logs error.category before raising that public error; the following socket exchange is not reached. This supports a failed host-side passive check, not a native inventory failure, authentication bypass, or a verified Editor identity mismatch.

The operational failure is confirmed: a 30-second PowerShell subprocess timeout. Why that subprocess failed to complete within its bound is not established. Startup logs show heavy shader/mesh-card work and later prolonged shader jobs, Slate draw-buffer waits and audio starvation, which make resource pressure plausible but do not prove causality. No timeout was increased and no identity predicate was relaxed.

## 6. World and StaticMesh acceptance coverage

The client stopped before either native world-save-scope or StaticMesh handler was called. Consequently:

- World/persistent-level package identity beyond project_info, dirty state, World Partition and streaming/external/build-data fields: NOT TESTED.
- Hypothetical destination/collision reporting, scan limits, unknown/incomplete fields, and runtime Save As BLOCKED output: NOT TESTED.
- Positive project-local StaticMesh fixture, object identity/material/ownership metadata and unavailable geometry/dependency results: NOT TESTED.
- Invalid/unloaded StaticMesh path handling: NOT TESTED; those calls were not reached.
- Before/after package flags/counts and mesh UObject identity: NOT TESTED.
- No fixture asset was created or saved. No forced World Partition initialization, actor load, Save As, Landscape operation, or package exception was performed.

R6/R7 source and compile evidence still says geometry is unavailable and Save As remains blocked, but those historical/source facts are not relabeled as successful R8 runtime responses.

The fixed four-tool catalog also lacks a full clean-loaded-package identity list: its dirty observer reports total inspected count plus dirty rows. Even a future successful count comparison cannot by itself establish equality of every loaded clean package identity.

## 7. Filesystem findings and timing

No complete inspection comparison baseline was established because the first inventory failed. The filesystem comparison spans prelaunch through the startup/host window. It cannot be presented as an isolated before/after native-inspector side-effect test.

Project Content: no created/changed asset file was observed. Forge source, descriptors, selected prior reports and the three R7 DLLs remained unchanged. The R7 report hash is still DE44D4290B82A0ED661DD6CD6876E21E392C2B1E35689EFEE061ED53D01F91B1.

**Unexpected disposable configuration change:**

    Config\DefaultEngine.ini

- Before launch: 1,199 bytes; SHA-256 E3D3AB62B3E3FC286010F45AB8D4146D9657F4FB1E285FAE72E378D5B5B3C7A1
- After startup: 1589 bytes; SHA-256 E6D3D12D7923838AD0724ED85AC781100C3E75FE90AFE8FA6D9E2BAF9F3BA863
- Last-write: 2026-10-22T06:41:30.0627521Z, before the host process started.
- Added section observed: /Script/AndroidFileServerEditor.AndroidFileServerRuntimeSettings.
- It includes generated security settings. Security values were not included in this report or config-change evidence.
- No configuration edit was issued by the R8 client. Timing establishes this as a startup-window write predating the host; the exact writer/call site was not instrumented.
- The file was preserved as left by the Editor; no repair or rollback was attempted.

Twenty-one project Config/Saved file additions/changes were observed relative to the prelaunch snapshot, primarily generated Editor/user configuration and project bookkeeping. The exact list, hashes and warning records are in post-audit.json. That record was captured while the Editor remained alive; later normal writes are possible and no final quiescent project snapshot is claimed.

The new private root contains expected startup DDC/profile/temp/log/session artifacts. Credential-bearing registrations were not exported. No system-wide write trace was run, and external filesystem containment is not certified by R8.

## 8. Startup warnings and incidental work

The startup log records Engine initialization taking 287.51 seconds, default shader compilation, engine editor/MediaPlate mesh builds, mesh-card work, repeated Slate draw-buffer waits and audio buffer underrun/starvation. These events occurred during startup/idle activity; no native mesh inspection ran. R8 therefore does not demonstrate a mesh-build-free inspection window.

At 06:41:31.758 UTC, the Editor automatically launched Build.bat -Mode=QueryTargets with the disposable project and output Intermediate\TargetInfo.json. This was an unexpected automatic UBT metadata query, distinct from an agent-requested native build. No C++ compile/link or plugin rebuild was observed, and all R7 DLL hashes remained unchanged. Do not state that no UBT invocation occurred.

An incidental wildcard listener owned by the disposable Editor was observed at 0.0.0.0:39320, separately from the verified Forge bridge at 127.0.0.1:59863. Its component/role was not investigated or modified. This is not evidence that ForgeMCP bound to a wildcard address.

The post-audit captured 88 warning/error log lines at its observation time. Selected samples and startup events remain in post-audit.json; the live Editor log may grow. No fatal plugin initialization failure was observed; required modules and authenticated project_info succeeded.

## 9. Connection indicator

Listener availability, authentication success and request outcome were distinct: the loopback listener was still present before the close attempt, authentication/project_info succeeded, and the later inventory was rejected by host process-preflight timeout.

Existing host connection_monitor_lifespan performs periodic health probes by design. R8 added no artificial keepalive, polling workaround or UI code change. That existing activity prevents a clean six-second idle experiment while the host is alive.

The actual UI indicator was not safely observed. After the host ended, no new requests were sent; listener presence alone does not prove the UI indicator state. Source describes the six-second authenticated-activity timeout, but its visual idle transition is NOT TESTED in R8.

## 10. Historical telemetry anomaly

The missing R7 VSApplicationInsights .trn remains an unresolved historical telemetry anomaly, as instructed. Its pre-build size was 1,531 bytes and SHA-256 B86CBA2D4E5DB305DA495128CFAB0B9A358F0056919473C86EB3EFA336860A81. It remains absent; it was not restored, recreated, deleted again or used as a new integrity baseline. This historical exception is separate from the R8 configuration startup write and identity-probe timeout.

## 11. Shutdown and current ownership

Before close, PID, executable, full project command line and seven-digit start pin were reverified. Both dedicated-host processes are absent. CloseMainWindow returned true for the new Editor, but WaitForExit(60000) returned false. No forced termination or save/discard action followed.

Final passive observation at 2026-10-22T06:57:14.441249+00:00:

- PID 42880: present and active; executable still the StageA7G UnrealEditor.exe.
- Host launcher PID 43024: absent.
- Actual dedicated host PID 8244: absent.
- New private registration: still present.
- Protected Editor: no close/restart/save/discard/connection request was issued.

**Disposable Editor cleanup is BLOCKED, not PASS.** Its close-state requires review. The Editor and private session were left isolated with evidence intact. No statement is made about preservation of arbitrary current Editor memory.

## 12. Acceptance gates

| Gate | Status |
|---|---|
| R7 binaries and matching BuildId/version | PASS |
| One disposable Editor launch | PASS |
| Native Editor/Runtime/project modules loaded | PASS |
| Dedicated isolated host and authentication | PASS for initialization/project_info; later request blocked |
| Exact four-tool read-only catalog | PASS |
| Missing/unallowlisted session fails closed | PASS |
| Runtime project/world path and PIE stopped | PASS |
| Complete dirty-package inventory | BLOCKED — powershell_timeout before native observer |
| World-save-scope acceptance | NOT TESTED |
| StaticMesh positive/negative acceptance | NOT TESTED |
| Native inspector package/filesystem side-effect acceptance | BLOCKED — no complete baseline |
| Configuration preservation across startup | FAIL / OBSERVED CHANGE — DefaultEngine.ini appended settings |
| Content/source/binary file identity at audit time | PASS for monitored files |
| Connection-indicator idle behavior | NOT TESTED |
| Dedicated-host cleanup | PASS for process absence; exit code unknown |
| Disposable Editor graceful shutdown | BLOCKED — still running |
| Overall R8 runtime acceptance | BLOCKED / PARTIAL; no full PASS |
| Production Phase 6C | NO-GO |

## 13. Evidence and smallest next action

New private evidence root: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\runtime\R8-20261022T063606Z-5cfa33bbc9f14e95805e09c8b7e80c06\evidence
.
Records include preflight.json, editor-launch.json, editor-identity.json, runtime_client.py, runtime-result.json, shutdown-request.json, post-audit.json, config-change.json and final-lifecycle.json. Host and Editor diagnostic logs are under the sibling logs directory. No authentication values are reproduced here.

| Evidence | Bytes | SHA-256 at report preparation |
|---|---:|---|
| evidence\config-change.json | 529 | 6E25BC1C5DB409A0784D7C1C1F6C64A5F6D3217CF5BD1A5B4E0678E7EDF28569 |
| evidence\editor-identity.json | 1572 | 7684F35A3DAE5B07500FF8B3208B1DFA0BACB56C9C92BEE99FD70E6F7B8D2F90 |
| evidence\editor-launch.json | 1181 | D5D83E6092A2CB2B4B0AA643F22AEBCD8EFA3DF188DD7071AEB6F303445A0E61 |
| evidence\final-lifecycle.json | 3494 | B1F863D258B1A431069F8C062FBE0D05166B0EC7A1089682A19DEABBC1C0AFA2 |
| evidence\post-audit.json | 15008 | 1CD8A8326BA614D5C3D357152EE157BCCE41890AE4E9C2DC4B29CDBC67AB31A4 |
| evidence\preflight.json | 2659 | EC39BD14F3629CD7324465D9F341AA424B9B0F9DF43F469CEC4D5FEF85CF1496 |
| evidence\runtime-result.json | 17761 | 88FD99B253C208A4EEECA8BD001BA8AFEFA5AC532E4C2445A16A19D2E88D5DEA |
| evidence\runtime_client.py | 12632 | E63A512BC4F342D131CC4E6863C248568F7B5D7CB39177A4E3D0BFB8EE9F3433 |
| evidence\shutdown-request.json | 289 | D9E8DE0D61D9B8F9FB0E7BA4F40F02EEA290532F5E174B2C843466D57DA0FA53 |
| logs\Editor.log | 158914 | 53D2AB9F0E5001DCD42CD631731EDF8043E457DD346C004BAA75444F11A848ED |
| logs\host-stderr.txt | 688 | 41466D50715A1C601F47C3D555ED17A8C2F246F87F6DA28BDED722283B37B13C |
| logs\server-8244.log | 0 | E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855 |

The Editor log remains live, so its hash is an observation at report preparation and may change. Prior reports were not edited.

The immediate next action is owner review of the still-running disposable Editor PID 42880 and its uncompleted close request; do not target protected PID 15144. Then use a narrowly scoped offline investigation of the existing PowerShell identity probe timeout under load, preserving every identity/authentication predicate. The native inspectors have not failed a runtime behavioral test because they were never reached. A plugin rebuild is not justified by the evidence from this timeout alone.

Any new host attempt or runtime acceptance run requires a new bounded authorization. Reuse the existing environment and preserved warmed-cache evidence; do not start another Editor automatically or patch the probe during R8. No new build, deployment, protected operation, package save/discard, Landscape action or cleanup is authorized by this report.

**Final disposition: module loading/authentication/catalog PARTIAL PASS; inspector acceptance and disposable Editor shutdown BLOCKED. Production Phase 6C remains NO-GO. Stop after reporting.**
