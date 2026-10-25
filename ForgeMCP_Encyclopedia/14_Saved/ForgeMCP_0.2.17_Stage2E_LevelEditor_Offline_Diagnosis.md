# ForgeMCP 0.2.17 — Stage 2E LevelEditor Offline Diagnosis

Checked October 24, 2026. **Diagnosis verdict: ROOT CAUSE PROBABLE.** The strongest evidence points to Unreal Engine's experimental `TedsOutliner` Editor module accessing `LevelEditor` during module startup, before `LevelEditor` was loaded. The crash context identifies `UnrealEditor-TedsOutliner` immediately under the failing Core module-access frame, and installed UE 5.6.1 source shows an unchecked startup path to `GetModuleChecked<FLevelEditorModule>("LevelEditor")`. The retained stack is address-only, so the precise TedsOutliner function cannot be conclusively symbolized from this evidence. Stage 2E independent disk reload remains **BLOCKED / NOT TESTED**; Phase 6C is not approved.

This is an offline forensic result. No Unreal Editor, commandlet, or real-process termination was run. No project asset, installed engine file, plugin source/binary, controller, configuration, plan, or checkpoint was changed.

## Failure record and startup timeline

The single approved isolated launch used `G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/revised_launch_plan.json` and clone `isolated_project/ForgeMCPDev.uproject`. `launch_approved.json` records PID 6236, creation FILETIME `134372765634936253`, the exact clone command line, and exclusion of production PID 43744. `approved_single_attempt_marker.json` records the consumed approval. The controller stopped the attempt at approximately 851.407 seconds, below the 900-second ceiling. No new launch is authorized.

| UTC | Evidence | Meaning |
|---|---|---|
| 00:49:24 | `launch_approved.json` | Isolated Editor process created. |
| 00:49:29 | `logs/UnrealEditor.log` lines 102, 113–130 | Project plugin mounted; UE 5.6.1 Development Editor startup and approved arguments recorded. Engine plugin `EditorDataStorageFeatures` was mounted at log line 67. |
| 00:49:36 | log DDC lines | Engine `Compressed.ddp` opened for reading; `Stage2EAlphaLocal` selected as writable under the new private root. |
| 00:53–00:54 | `milestones.json` / log | Several missing cached editor shadermaps compiled; the last sampled milestone was `WorldGridMaterial`. |
| 01:03:31.132–.142 | log lines 826–827 | World Partition **class descriptor registry** initialized. This is not evidence that the target world or Landscape loaded. |
| 01:03:33.421 | log lines 847–848; crash context | Assertion on access to unloaded `LevelEditor` module. |
| 01:03:34–35 | `test_result.json`, `termination.json` | Controller detected assertion, terminated the identity-verified isolated root, and recorded incomplete worker shutdown verification. |

The assertion is `ModuleManager.IsModuleLoaded(ModuleName)` at installed-engine source path `D:\build\++UE5\Sync\Engine\Source\Runtime\Core\Public\Modules\ModuleManager.h`, line 338, followed by `Tried to get module interface for unloaded module: 'LevelEditor'`. The first and only recorded occurrence is at log line 847. `CrashContext.runtime-xml` classifies it as `Assert`. The crash context's `PCallStack` begins with `UnrealEditor-Core + 0x424028`, then `UnrealEditor-TedsOutliner + 0x136f5` and `+ 0x731cd`, followed by Core, Projects, and UnrealEditor startup frames. Its ordinary `CallStack` is unsymbolized addresses. `UEMinidump.dmp` is retained; no symbol resolution or debugger analysis was performed, so a full source-function stack is unavailable.

The preceding log also contains missing ACL compression-settings warnings and engine asset-building messages. None has an evidenced causal link to this assertion. The assertion happened during Editor/module initialization after global engine initialization had progressed, **before verified target-map load, private ForgeMCP bridge authentication, Landscape loading, or Landscape serialization**. World Partition registry initialization alone does not move the acceptance boundary.

## Module dependency and call-path analysis

Installed UE source `Engine/Plugins/Experimental/EditorDataStorageFeatures/Source/TedsOutliner/Private/TedsOutlinerModule.cpp` shows:

- `FTedsOutlinerModule::StartupModule()` at line 104 calls `RegisterLevelEditorTedsOutlinerTab()` at line 109.
- `RegisterLevelEditorTedsOutlinerTab()` at line 194 calls `FModuleManager::GetModuleChecked<FLevelEditorModule>("LevelEditor")` at line 196, before registering `OnTabManagerChanged`.
- Other TedsOutliner paths also call `GetModuleChecked<...>("LevelEditor")`; the address-only crash stack cannot exclude them individually.
- `EditorDataStorageFeatures.uplugin` declares `TedsOutliner` as an Editor module without an explicit `LoadingPhase`; the plugin is experimental. `TedsOutliner.Build.cs` lists `LevelEditor`, but a build dependency does not prove runtime load ordering. The failed log confirms this engine plugin mounted.

**Probable trigger:** the TedsOutliner startup registration path ran when `LevelEditor` was not yet loaded. The crashing frame's module identity and the direct source path align closely. A symbolized minidump or matching PDB symbol resolution would be needed to mark that exact function call confirmed. The reason this module was scheduled before `LevelEditor` in this isolated run is not yet established.

Static inspection of `Plugins/Forge/MajesticForge.uplugin` shows the Forge editor module at `PostEngineInit`; `MajesticForge.Build.cs` includes `LevelEditor` as a private dependency. `MajesticForgeModule.cpp` startup registers its own tab/menu and starts its bridge; it does **not** call `GetModuleChecked<LevelEditor>` in that startup body. Other Forge LevelEditor subsystem/viewport references are in operational paths. The retained assertion stack has no `UnrealEditor-MajesticForge` frame, and no private ForgeMCP bridge response was obtained before the crash. This does not prove ForgeMCP could never influence module ordering indirectly, but it provides no direct evidence that ForgeMCP triggered the assertion.

## Isolated launch and configuration factors

The exact plan uses ordinary rendered `UnrealEditor.exe`, target-map argument `/Game/Levels/L_City_World_Master`, `-Unattended`, `-SCCProvider=None`, `-DDC=Stage2EAlphaPrivateDDC`, private `-UserDir`, and private log path. Child-only environment redirects Forge registration, `LOCALAPPDATA`, `TEMP`/`TMP`, and UE local cache paths. Runtime log confirms private writable DDC; no contrary cache evidence was found.

Read-only source/clone comparison found only two intentional project configuration additions: `DefaultEngine.ini` adds the private DDC graph/fallbacks and disables World Partition loading-in-editor for clone inspection; `DefaultEditorPerProjectUserSettings.ini` disables autosave, restored tabs, and Live Coding. The clone shares all other source configuration. None of these additions directly references `TedsOutliner`, `LevelEditor` module loading phase, or the assertion path. `-Unattended` and private user state may affect startup ordering or UI initialization, but that is **possible**, not demonstrated. No evidence ties the previously observed renderer/shader delay to this module assertion. The long shader preparation delayed progress but is not an established trigger.

The presence of the experimental `EditorDataStorageFeatures` plugin in the mounted set is confirmed. Its effective enablement source and whether it is required by any project dependency need a targeted static dependency audit before proposing a clone-only opt-out. Disabling it is not assumed safe or applied here.

## Controller shutdown investigation

`termination.json` names worker PIDs **38892** and **38252**, each with `PermissionError: [WinError 31] A device attached to the system is not functioning.` They were retained `ShaderCompileWorker.exe` children of PID 6236; the last `milestones.json` entry records their PIDs, parent, creation FILETIMEs, executable paths, and CPU time. The controller's pre-shutdown bounded snapshot passed with no observation failure. Root PID 6236 was stopped through its identity-verified retained handle. Three other workers, PIDs 11756, 8248, and 37232, have successful recorded termination calls.

The code at `Saved/stage2e_controller_hardening/run_revised_once.py` lines 276–283 first calls `handle_identity()`, `process_is_live()`, and identity comparisons, and only then calls `TerminateProcess`. A `TerminateProcess` false return is recorded in a separate `else` branch without the `PermissionError:` prefix. The two observed `PermissionError:` strings came from the caught `OSError` path; **the record does not prove that `TerminateProcess` was called for either PID**. The exact failing Win32 call within `GetProcessTimes`, `QueryFullProcessImageNameW`, or `GetExitCodeProcess` was not logged. The processes may have been exiting as the root crashed/stopped, but this is not established. The retained handles' validity at the error instant and the Windows device-error cause are unknown.

The controller's final bounded snapshot found no remaining worker candidates, but its policy requires both no remaining candidates and no worker termination failures, so it correctly marked `shutdown_verification=INCOMPLETE`. A separate post-run read-only process query found PID 6236 and all five recorded worker PIDs absent, with production PID 43744 still running. That later observation supports eventual absence, **not** successful controller-time shutdown verification or proof that the two problematic workers were terminated by the controller.

**Controller classification: CONFIRMED incomplete verification caused by two pre-termination worker-check exceptions; UNKNOWN underlying Win32 error cause and exact process-exit timing.** The root/process ownership controls were maintained; no evidence shows an unrelated process was targeted.

## Classified findings and minimal proposed corrections

| Finding | Classification | Basis |
|---|---|---|
| Primary startup failure was an assertion accessing unloaded `LevelEditor` | **CONFIRMED** | Child log lines 847–848 and crash context. |
| Assertion was in `TedsOutliner` module execution | **CONFIRMED** at module level | Crash context module-address stack. |
| `FTedsOutlinerModule::StartupModule` → tab registration line 196 was the exact trigger | **PROBABLE** | Installed source has the direct unchecked call; stack lacks function symbols. |
| Clone DDC selected private writable cache | **CONFIRMED** | Child log and milestones. |
| Clone configuration or `-Unattended` caused the ordering | **POSSIBLE** | Different startup context, no direct causal evidence. |
| ForgeMCP startup directly called the failing LevelEditor access | **UNSUPPORTED / UNKNOWN** | No Forge frame; inspected Forge startup has no checked LevelEditor access. |
| Landscape serialization caused the assertion | **UNSUPPORTED** | No authenticated target-map or Landscape load. |
| Two worker `TerminateProcess` calls failed | **NOT ESTABLISHED** | Exceptions were logged by the pre-call check path. |
| No recorded isolated process remained after the run | **CONFIRMED at later observation** | Separate post-run process query. |

No code change is authorized by this investigation. A **minimal UE-side correction** is justified for a future reviewed change: in `Engine/Plugins/Experimental/EditorDataStorageFeatures/Source/TedsOutliner/Private/TedsOutlinerModule.cpp`, defer tab registration until `LevelEditor` is loaded, or guard/check its availability and register on a later safe module-load callback; avoid silently skipping required registration forever. Apply the same lifecycle reasoning to shutdown and callback paths so they do not assume `LevelEditor` remains loaded. This addresses the direct unchecked access without modifying ForgeMCP. An alternative clone-only disablement of the experimental plugin may avoid this startup path, but requires proof that no project/engine feature needed for acceptance depends on it; it is not a proven equivalent fix. Do not patch the installed engine or clone during this task.

A **separate controller proposal**, for `Saved/stage2e_controller_hardening/run_revised_once.py`, is to record the failing identity substep and Win32 code per worker, then distinguish already-exited from identity-unverifiable workers using the retained handle/exit state where safely possible. Keep the exact creation/executable/parent checks before any termination. After a bounded post-shutdown snapshot, record whether a problematic PID is absent with its retained creation identity; preserve an indeterminate result when identity cannot be proven. This can improve diagnostics and completeness without weakening protections or interpreting `WinError 31` as successful termination. `worker_observer.py` need not change unless synthetic tests identify an observer gap.

Before any future runtime attempt, a reviewed correction would need offline source/dependency review, Python AST and focused synthetic controller tests, a UE compile if engine/plugin source is changed, and a fresh private-clone/config audit. An eventual **separately authorized** isolated Editor launch is still necessary to validate startup order and independently loaded disk-backed Landscape data. No such launch was made or requested here.

## Evidence and remaining uncertainty

Primary evidence: [Stage 2E execution report](ForgeMCP_0.2.17_Stage2E_IndependentReload_Acceptance_20261024T001332Z.md); `G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/` files `logs/UnrealEditor.log`, `user/Saved/Crashes/UECC-Windows-2EC36EC34E5BCC68D8B1B6879BCBA151_0000/CrashContext.runtime-xml` and `UEMinidump.dmp`, `launch_approved.json`, `milestones.json`, `test_result.json`, and `termination.json`; [preparation report](ForgeMCP_0.2.17_Stage2E_IndependentReload_Preparation_20261024T001332Z.md); installed UE 5.6.1 TedsOutliner source; Forge module source and descriptor. Both controller Python files passed read-only AST parsing. No synthetic test spawned or terminated a real Unreal process.

The specific TedsOutliner function offset, effective plugin-enable chain, and precise Windows failure call remain unconfirmed. Symbolize the retained dump with matching UE symbols and audit plugin enablement before applying any fix. Stage 2E remains **BLOCKED** until a later independent, authenticated disk reload actually verifies the Landscape. No Phase 6C GO follows from this diagnosis.
