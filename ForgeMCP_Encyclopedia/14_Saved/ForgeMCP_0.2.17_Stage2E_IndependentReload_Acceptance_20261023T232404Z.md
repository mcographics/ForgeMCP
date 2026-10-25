# ForgeMCP 0.2.17 — Stage 2E Independent Reload Acceptance

Current verdict: **BLOCKED — CONTROLLER WORKER-IDENTITY OBSERVATION TIMED OUT BEFORE MAP ACCEPTANCE**.
Preparation and static isolation: **PASS**.
Independent disk reload: **NOT TESTED**.
Close-up visual and actual collision behavior: **NOT TESTED**.
Phase 6C release acceptance: **NOT TESTED**.

Prepared October 23, 2026, 19:27 EDT / 23:27 UTC. One explicitly approved isolated Editor was subsequently launched and safely stopped after a controller observation timeout. See the latest execution result below; the following preparation record is historical. Production source preservation passed. No retry occurred.

## Historical preparation record

## 1. Production Editor identity — PASS

Fresh discovery, native health and project_info authenticate unreal-43744 / PID 43744, UE 5.6.1-44394996+++UE5+Release-5.6, ForgeMCP 0.2.17-alpha.1, G:/ForgeMCP/ForgeMCPDev.uproject, /Game/Levels/L_City_World_Master.L_City_World_Master, PIE stopped. Final project_info after preparation confirms the same identity.

## 2. Saved-source verification — PASS within current evidence

Reviewed the [manual save verification report](ForgeMCP_0.2.17_MultiSculpt_ManualSave_Verification_20261023T231706Z.md). Fresh hashes match:
- Affected streaming proxy: 01bcd92c87e93b000811a863b88701ec845ff0e7487c868f0ccb92a46a955b61.
- Landscape root: 9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df.

That report retains the native production save evidence for both packages. Root bytes remained unchanged despite the recorded rewrite; no repeat save was attempted.

Fresh production full-height hashes match:
- ForgeTerrain: 08cbe382a59441d8148a674cf0d83851.
- Original Layer: 9f43572fbc2c06ef497da015879cdb23.

Fresh native bounded read [1042,1065,1098,1075] exactly matches the final prepared result: all 120 new modified values and all 101 original carved values retained, region MD5 3817bd2c18535a9b4529387de493f2b9, minimum -100 cm. This is current production readback, not independent disk-reload proof.

Initial and final complete loaded-package inventories each inspected 1236 packages, no errors or further pages, and found only compiled-in /Script/SlateCore dirty. Zero dirty production Content.

## 3. New disk baseline and independent copy — PASS

New test root:
G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z

Independent project:
G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z/isolated_project/ForgeMCPDev.uproject

Scope: all current Content, Config, Binaries, Plugins, Source and ForgeMCPDev.uproject. Root generated Saved/Intermediate, logs, credentials and private registrations were not copied. New independent Saved/Intermediate and user paths were created.

Source manifest: **1745 files, 5094258538 bytes**. Every ordinary copied file was hash/size verified and checked for different source/destination filesystem identities. No symlinks, junctions, reparse points or hardlinks were used. File link counts are one. Historical copies/checkpoints were not reused or overwritten.

Only two clone configuration files differ from source:
- Config/DefaultEngine.ini: private DDC/fallback graphs and editor loading setting to load the proxy set.
- Config/DefaultEditorPerProjectUserSettings.ini: autosave/tab restoration and Live Coding disabled.

All clone Content files are read-only. The clone retains native World Partition; its editor spatial-loading setting is changed only to load proxies for inspection. There is no production configuration change.

Free disk before copying: 176924241920 bytes; after preparation: 171824156672 bytes. This exceeded twice the source size plus 2 GiB. Pre-copy OS memory observation reported 20139248 KiB available physical memory. Runtime resource sufficiency remains subject to observation during the approved test.

## 4. Dependencies and private DDC — static PASS; runtime NOT TESTED

Both project and Forge module BuildIds match 43139311. Module DLLs exist, all 16 enabled project plugin descriptors and WebBrowserWidget are available, copied Forge descriptor reports 0.2.17-alpha.1, and the project has no AdditionalPluginDirectories.

Reviewed Stage 2E-R startup forensics and Stage 2E-T controlled-load result. NullRHI failed before map acceptance. RenderOffscreen also failed to establish a map load. The later ordinary rendered attempt proved private DDC selection but timed out at 900 seconds before map loading while shader compilation was observed. No successful prior independent load is claimed.

The new selected Stage2EAlphaPrivateDDC graph and BOTH fallback sections, InstalledDerivedDataBackendGraph and DerivedDataBackendGraph, have reachable topology:
Root -> EngineReadPak (read-only installed Compressed.ddp) + Stage2EAlphaLocal (new private filesystem cache).

The writable node has a literal path under this new root and no EnvPathOverride, CommandLineOverride, EditorOverrideSetting or RedirectionFileName hooks. No reachable Shared, Zen, Cloud or WritePak node is present. Thirteen applicable later/platform/plugin/user configuration candidates were scanned without graph conflicts. Private registration directory inheritance was removed and explicit full control granted to current owner and SYSTEM.

Private test paths cover user, localappdata, temp, logs, registry and DDC. Child-only environment removes inherited FORGE_* and supplies the exact override map in launch_plan.json. No global environment, registry value or Codex connection was changed.

Installed engine runtime/content and read-only cache pak remain shared dependencies. This is project/cache isolation, not a separate Windows account or complete OS filesystem sandbox. Runtime DDC graph selection and actual private cache use must be proven from the future child log before accepting map results.

## 5. Exact proposed launch — NOT EXECUTED

```text
"G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe" "G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z/isolated_project/ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -Unattended -SCCProvider=None -DDC=Stage2EAlphaPrivateDDC -UserDir="G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z/user" -abslog="G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z/logs/UnrealEditor.log"
```

Working directory: new isolated_project. Ordinary rendered startup; no NullRHI or RenderOffscreen. Installed executable SHA-256 aa27ca8afea076e7310535c8a50d9f7589a2e011175e8ae1b73dff8766f53007.

One attempt only, startup window at most 900 seconds. A retained process handle, PID/creation time/executable/exact clone project identity and owned worker parentage are required. Exclude production PID 43744. Stop on unsafe cache selection/fallback, fatal/assertion, build prompt, identity mismatch, serialization failure or timeout. No automatic retry, plugin change or repair.

The controller must target only the identity-verified disposable child and owned descendants for bounded shutdown, retaining exit status and evidence. It must never send a production close/save command.

## 6. Owner launch approval — BLOCKED

This assignment authorizes preparation, not launch. Separate explicit owner authorization is required for the single launch above. Launches so far: **0**. No approval result is assumed.

## 7. Actual independent map load — NOT TESTED

Process creation or RHI startup will not count as map acceptance. Require private authenticated child project_info for the exact independent project, target map load/World Partition initialization evidence and native Landscape inspection.

## 8. Height checksums and both extensions — NOT TESTED in clone

Expected Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D.
Original layer GUID 198824024FF8A77A01535B86021D9B34; full MD5 9f43572fbc2c06ef497da015879cdb23.
ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B; full MD5 08cbe382a59441d8148a674cf0d83851.
Verify exact bounded arrays, all 120 changed samples and 101 protected original samples from expected_reload_baseline.json. Do not use historical flat-terrain target hashes.

## 9. Original Layer preservation — production PASS; clone NOT TESTED

Fresh production checksum matches. The independent load must return the same GUID, hash, visibility and lock state, without writes.

## 10. Streaming proxy integrity — production PASS; clone NOT TESTED

Fresh production has 16 loaded / 0 unloaded proxies, 64 registered Landscape components and 64 registered collision components. Require those actual clone values after load, with correct active-world ownership.

## 11. Close-up visual inspection — NOT TESTED

After successful independent loading, capture close-up geometry of both specified extensions where a safe supported viewport method is available. Record gaps/seams honestly. No terrain changes are authorized to repair a result.

## 12. Collision behavior — NOT TESTED

Registration alone does not establish collision heights. Use bounded native read-only collision queries in the isolated loaded world where supported. No production collision query/reconfiguration, PIE or terrain modification is implied.

## 13. Production preservation — PASS through preparation

Every one of the 1745 production source hashes was rechecked after copying and matched the new source manifest. Final production identity and complete clean Content inventory passed. Production Editor remained operational. No production save, asset edit, restore, deletion, restart or new editing-session request occurred. Only new preparation/report artifacts were written under Saved and the new test root.

After any future test, reauthenticate production and compare its source membership/hashes and dirty inventory again. Historical recovery evidence remains preserved.

## 14. Evidence and manifest pins

Test-root artifacts:
- source_manifest.json — current production dependency baseline.
- clone_manifest.json — independent copy after the two documented config changes.
- preparation_result.json — isolation/source rehash results.
- private_registration_acl.json — private registry ACL evidence, no credentials.
- launch_plan.json — exact proposed arguments, child environment, deadline and stop policy.
- expected_reload_baseline.json — current production native responses and exact sample expectations.

SHA-256 pins:
- Source manifest: 6e05f0fde1dc4eabe61e0072086aa19b407949809006563cf232b9424a7062f0.
- Clone manifest: 3b70cd29f84b9d8a0581f1dd35d992de6c9d7f43db6912d09873f2159ceef316.
- Launch plan: 725650a64bccd91eac691dae421f993ca82c63738f987be9dd8636b9fdb47a43.

Preparation script: Saved/prepare_stage2e_alpha_20261023T232404Z.py. It contains no Editor launch operation. Applicable reports reviewed: ForgeMCP_Stage2ER_IsolatedEditor_Startup_Forensics.md and ForgeMCP_Stage2ET_ControlledLoad_Result.md.

## 15. Current final verdict

**BLOCKED — SEPARATE OWNER LAUNCH APPROVAL REQUIRED.**

Preparation/static isolation PASS; no independent load, runtime DDC verification, close-up visual acceptance or actual collision-height acceptance has yet occurred. No Phase 6C release GO is claimed.

## Latest approved execution — October 23, 2026, 19:36–19:42 EDT

**Final Stage 2E verdict: BLOCKED — CONTROLLER WORKER-IDENTITY OBSERVATION TIMED OUT BEFORE MAP ACCEPTANCE.**

Independent disk-backed Landscape persistence: **NOT TESTED**.
Private DDC runtime selection: **PASS**.
Production source preservation: **PASS**.

This section supersedes the historical pending-approval status above. Exactly one isolated Editor was launched. No automatic retry occurred.

### 1. Final prelaunch gates and owner approval — PASS

The owner explicitly approved ONE launch using the exact prepared launch_plan.json, with a maximum 900-second startup window and production preservation restrictions.

Immediately before launch, all 1745 production files and all 1745 clone files were rehashed and their scope memberships checked. All hashes and file counts matched; no links/reparse points or unexpected registry entries existed. Launch-plan/source/clone manifest pins matched their preparation values. The private DDC graph and fallback definitions and registration ACL were rechecked.

A first controller invocation made an invalid nested read-only native dirty-inventory request and stopped before any launch. The MCP wrapper uses flat native offset/limit fields; the corrected v2 controller used that existing contract. Original controller and correction evidence were preserved. There was no Editor process or consumed launch marker from that prelaunch invocation. This was a helper argument correction, not a repeated Editor launch.

The corrected preflight independently authenticated production unreal-43744, expected project/level/plugin, PIE stopped, clean production Content and expected Landscape checksums/topology. Full prelaunch native and disk evidence is retained.

### 2. Exact isolated launch and process identity — PASS

The exact prepared arguments and child-only environment were used; launch_plan.json was not modified.

- Isolated PID/session: **18304 / unreal-18304**.
- Executable: G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe.
- Project: G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z/isolated_project/ForgeMCPDev.uproject.
- Target level argument: /Game/Levels/L_City_World_Master.
- Retained OS creation FILETIME: 134372721750623536.
- Launch identity artifact timestamp: 2026-10-23T23:36:16.243064Z.
- Ordinary rendered startup; no NullRHI, RenderOffscreen or renderer change.
- Production PID 43744 explicitly excluded.
- Exactly ONE approved single-attempt marker and launch identity record.

The process handle, executable, creation identity, command line and parent PID were retained and checked.

### 3. Runtime DDC and startup milestones

| UTC time / elapsed | Observed evidence |
|---|---|
| 23:36:21.408 | Installed engine Compressed.ddp opened for reading (1350 MiB) |
| 23:36:21.488 | Stage2EAlphaLocal using the NEW private test-root/ddc path as Writable |
| 23:36:21.492–21.496 | Private shader working/autogen paths logged; three local shader workers announced |
| 23:36:26.013 | AssetDataGatherer cache milestone under private user/Intermediate |
| ~32 seconds | Controller confirmed private DDC at runtime and recorded three owned worker identities |
| 23:37:43.722 | Shader task submission timing message |
| 23:38:21.530 | Private DDC maintenance; zero files deleted, 153 files / approximately 2 MiB scanned |
| 23:39:52.138 | Missing cached DefaultPostProcessMaterial shadermap explicitly compiling |
| ~230.562 seconds | Worker-identity observation command hit its 12-second timeout |
| 23:40:05.836–23:40:11.707 | Identity-verified disposable process/worker shutdown recorded |

No unexpected writable DDC backend, graph fallback, old shared cache path, fatal error or assertion was observed. This is runtime graph-selection/log evidence, not a complete OS write trace.

The last logged shader compilation does not establish completion of the queue or progress into the target map.

### 4. Exact blocking condition

The controller's PowerShell/CIM query enumerating ShaderCompileWorker / CrashReportClient identities timed out after 12 seconds. The Python exception was subprocess.TimeoutExpired. The controller stopped the test because that required observation could no longer be verified.

This happened after approximately **230.562 seconds**, before the 900-second ceiling. It was **not** a 900-second Unreal startup timeout, not an observed engine crash, and not a verified Landscape serialization failure.

The cause of the Windows process-observation delay is not established. Do not attribute it to Landscape corruption, DDC failure or a specific engine deadlock. Private DDC selection passed independently.

### 5. Independent map and Landscape acceptance — NOT TESTED

No target-map load/World Partition acceptance or authenticated isolated native Landscape response was obtained. No independent_native_landscape.json artifact exists. The child did not produce an accepted private ForgeMCP session inspection.

Consequently independent clone verification of both full-height hashes, all 120 extension samples, all 101 original carved samples, layer identities, proxy topology, collision registration and serialization correctness was not completed. The expected data remains in expected_reload_baseline.json; it is not a test result.

### 6. Close-up visual and collision acceptance — NOT TESTED

No isolated viewport capture or collision query was executed because independent map loading was not established. The prior distant production screenshot remains historical and does not satisfy close-up join acceptance. No terrain repair, camera mutation, collision setting change or PIE occurred.

### 7. Bounded disposable shutdown — PASS

Immediately before shutdown, the controller verified the retained child handle's creation identity/executable and the current process command line for the exact clone project, explicitly excluding production.

PID 18304 was terminated via its retained process handle and waited for completion. Recorded exit code: **1**, as a controller termination result; it is not an engine crash diagnosis.

Two still-terminable owned shader workers, PIDs 23140 and 43724, were stopped only after their retained handle creation/executable identities matched. The third recorded worker, PID 22024, was not listed as terminated by the controller. Post-test direct Win32 queries confirmed the child was no longer running and all three recorded worker PIDs were absent. No broad process-name termination or production UI close/save command was used.

No isolated retry, rollback, checkpoint restoration, cache seeding, plugin disable/rebuild or renderer experiment followed.

### 8. Production and clone preservation — PASS

Post-test fresh native authentication confirms production unreal-43744 / PID 43744, correct project/level/plugin, PIE stopped and operational.

Complete post-test inventory inspected **1236 packages**, no errors or further pages; only compiled-in /Script/SlateCore was dirty. Zero dirty production Content.

Fresh production Landscape inspection/readback confirms:
- Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D.
- Original Layer GUID 198824024FF8A77A01535B86021D9B34, MD5 9f43572fbc2c06ef497da015879cdb23.
- ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B, MD5 08cbe382a59441d8148a674cf0d83851.
- All 627 bounded values identical to prelaunch, retaining the 120 new and 101 original carved samples.
- Minimum -100 cm; both layers visible/unlocked; Landscape clean/layers up to date.
- 16 loaded / 0 unloaded proxies, 64 registered terrain and 64 registered collision components.

Final full byte audits:
- Production source_manifest.json: **1745 files checked, zero hash mismatches, zero additions, zero deletions**.
- Clone clone_manifest.json: **1745 files checked, zero hash mismatches, zero additions, zero deletions**.
- Six historical recovery manifest SHA-256 pins, including Stage 1, native adoption, post-adoption, first riverbed, approved multi-sculpt and activation: unchanged.

Generated private cache/log/user artifacts are retained. No production asset save, terrain operation, editing-session request, restore, deletion or restart occurred. New report/controller evidence under Saved and the new test root is outside the production asset manifest and was deliberately retained.

### 9. Comprehensive acceptance status

| Gate | Result |
|---|---|
| Production identity / saved source | PASS |
| Independent project copy / no shared writable production project files | PASS |
| Static private DDC and fallback fencing | PASS |
| Runtime private DDC selection | PASS |
| Separate owner launch approval | PASS |
| One-launch limit and bounded shutdown | PASS |
| Actual independent target-map acceptance | NOT TESTED |
| Independent height hashes and both extensions | NOT TESTED |
| Independent Original layer / proxy / collision registration | NOT TESTED |
| Close-up visual connections | NOT TESTED |
| Actual collision-height behavior | NOT TESTED |
| Production and clone source preservation | PASS |
| Stage 2E independent reload verdict | BLOCKED |
| Phase 6C release acceptance | NOT TESTED |

### 10. Retained evidence and next boundary

Evidence root: G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261023T232404Z.

- launch_plan.json and approved_single_attempt_marker.json: exact plan and owner-approved attempt.
- launch_approved.json: actual process identity and command line.
- prelaunch_disk_verification_corrected.json and prelaunch_production_native.json: final passed gates.
- prelaunch_controller_correction.json, run_approved_once.py and run_approved_once_v2.py: preserved helper correction and actual controller.
- logs/UnrealEditor.log and logs/launcher_stdout.log: startup/cache/shader evidence.
- milestones.json: elapsed time, process CPU, log size, owned worker identities and startup excerpts.
- test_result.json: exact controller observation timeout.
- termination.json and post_test_processes.json: verified disposable shutdown and process absence.
- post_test_production_native.json: current production identity/height/sample/dirty results.
- post_test_disk_verification.json: full production/clone hashes and membership.
- historical_checkpoint_manifest_verification.json: six preserved manifest pins.

The approved attempt is complete and must not be relaunched automatically. A future step may diagnose or replace the blocking worker-observation path without touching production. Any further isolated Editor attempt requires a new explicit owner authorization and reviewed launch conditions. No successful disk-backed persistence or Phase 6C GO is claimed.

**Final verdict: BLOCKED — INDEPENDENT RELOAD NOT DEMONSTRATED; PRODUCTION PRESERVATION VERIFIED.**

## Later approved attempt — October 24, 2026

The owner separately approved one hardened-controller launch of the newly prepared clone. That attempt launched once and stopped on an isolated Editor startup assertion before target-map acceptance. Runtime private DDC selection and production preservation passed; independent Landscape persistence, close-up visual inspection, and actual collision-height testing remain unverified. The complete later result and retained evidence are documented in [ForgeMCP_0.2.17_Stage2E_IndependentReload_Acceptance_20261024T001332Z.md](ForgeMCP_0.2.17_Stage2E_IndependentReload_Acceptance_20261024T001332Z.md). Its approval was consumed with no retry. Stage 2E remains blocked.


