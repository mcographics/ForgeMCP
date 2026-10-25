# ForgeMCP 0.2.17 — TedsOutliner Startup Fix Design and Isolation Feasibility

Checked October 24, 2026. **Final verdict: MORE EVIDENCE REQUIRED.** A minimal source correction is designed and captured as a standalone, unapplied patch. Static patch validation passed against the installed UE 5.6.1 source. A supported isolated build-and-load route for the changed Engine plugin has **not** been demonstrated, so no new clone, build, deployment, launch plan, or Editor run is claimed. Stage 2E independent reload remains blocked; Phase 6C remains unapproved.

## Root-cause confidence and exact source

The retained crash context reports `ModuleManager.h:338` asserting on the unloaded `LevelEditor` module; its portable stack contains `UnrealEditor-TedsOutliner` immediately after Core. Installed source `Engine/Plugins/Experimental/EditorDataStorageFeatures/Source/TedsOutliner/Private/TedsOutlinerModule.cpp` has `FTedsOutlinerModule::StartupModule()` calling `RegisterLevelEditorTedsOutlinerTab()`, which immediately calls `GetModuleChecked<FLevelEditorModule>("LevelEditor")`. The precise function address has not been symbolized, so this exact startup call remains **probable**, while the unloaded-module assertion and TedsOutliner module-level involvement are confirmed. No target map, Landscape, or ForgeMCP private session had been authenticated before the assertion. The private writable DDC selection from the failed attempt remains verified.

`TedsOutliner` belongs to the experimental Engine plugin `EditorDataStorageFeatures`. The production project enables Fab, and Fab's installed descriptor requires that plugin. Fab source uses Editor Data Storage. The proposed fix therefore retains Fab, EditorDataStorageFeatures, TedsOutliner, LevelEditor, Landscape, World Partition, and ForgeMCP; it does not disable or remove any of them. It changes only TedsOutliner's LevelEditor registration timing.

## Proposed startup and shutdown correction

Review-only patch: [ForgeMCP_0.2.17_TedsOutliner_StartupFix_Proposed.diff](ForgeMCP_0.2.17_TedsOutliner_StartupFix_Proposed.diff). Target files are the installed Engine plugin's `Public/TedsOutlinerModule.h` and `Private/TedsOutlinerModule.cpp`. The patch was **not applied** to them or to any clone.

- Startup subscribes to `FModuleManager::OnModulesChanged()`. If `LevelEditor` is already loaded, it registers immediately; otherwise it registers on `EModuleChangeReason::ModuleLoaded` for `LevelEditor`.
- Registration uses `GetModulePtr` and records whether it attached `OnTabManagerChanged`, preventing duplicate delegate attachment. It registers the tab spawner when a valid tab manager exists and `HasTabSpawner` is false, so an already-created tab manager is not silently skipped.
- Shutdown first removes the module-load callback, then removes its LevelEditor callback and tab spawner only while LevelEditor is still available. A module-unloaded notification clears retained registration state without dereferencing an unloaded module.

Installed UE 5.6.1 source verifies the API types and signatures: `FModuleManager::IsModuleLoaded`, `GetModulePtr`, `OnModulesChanged`, `EModuleChangeReason::ModuleLoaded/ModuleUnloaded`, `FLevelEditorModule::OnTabManagerChanged`, `FTabManager::HasTabSpawner` and `UnregisterTabSpawner`, and `FDelegateHandle::Reset`. The installed `MessageLog` module itself uses `OnModulesChanged` to defer a LevelEditor-dependent registration. The patch preserves the tab's label, category, icon, and menu behavior.

This is a design artifact, not a compiled or runtime-validated fix. The `ModuleUnloaded`/shutdown ordering and repeated LevelEditor reload path require focused compile and lifecycle tests. Other TedsOutliner `GetModuleChecked<LevelEditor>` calls remain in user-invoked paths; the patch targets the evidenced startup assertion and does not claim to eliminate every possible LevelEditor lifecycle hazard.

## Offline patch validation

`git apply --check` against the installed UE 5.6.1 root succeeded without applying the diff. The two patch targets exist; the Engine is an installed build. The TedsOutliner module's existing `UnrealEditor.modules` BuildId is **43139311**, matching the installed Editor's BuildId. This checks the current binary baseline; a future changed binary must be built and checked separately. No C++ compilation, binary compatibility test, module-load test, or Editor startup test was performed. The source diff's review utility does not prove its C++ compiles.

## Dependency, build, and isolated deployment feasibility

The corrected code is confined to an Engine plugin module. A project-local fork with the same plugin/module names would create duplicate discovery/selection ambiguity; no supported override precedence was verified, so that approach is **not approved**. Renaming the plugin/module would change Fab's declared dependency and potentially Engine references, defeating the minimal correction. Copying a replacement DLL into the installed Engine would violate isolation and is excluded.

A physically independent UE installation/copy, with the patch applied only inside that copy and its plugin module built against matching UE 5.6.1 headers/binaries, is the plausible isolation route. Its feasibility is not proven here. The installed Engine occupies approximately **90.55 GB**; the observed free space was approximately **166.38 GB**. A full independent Engine copy plus the approximately 5.09 GB project scope would consume roughly 95.6 GB before build intermediates, shader/DDC data, logs, and safety margin. The exact additional build size and wall time are unknown. Existing `Build.bat`, `RunUAT.bat`, and UnrealBuildTool are present, but this installed build has not been shown to rebuild an Engine plugin module in-place within a copied installation or produce a loadable, correctly registered `TedsOutliner` DLL. An offline build-procedure proof and resource budget are required before creating an isolated deployment. Hardlinks, junctions, or shared writable Engine plugin files would not satisfy independence.

Any eventual build must preserve compatible BuildId/module metadata, plugin dependencies, editor target ABI, and private project/DDC/session registration. A new clone and launch plan should be prepared only after the separate Engine-copy/build route passes. The prior launch approval is consumed; any new isolated Editor launch requires a new explicit owner authorization. A compile/deployment operation would also require a separate owner-approved scope because this task authorizes design only.

## Controller shutdown issue

The two `PermissionError: [WinError 31]` entries for worker PIDs 38892 and 38252 came from the identity/liveness-check exception path in `Saved/stage2e_controller_hardening/run_revised_once.py`; the evidence does **not** prove that `TerminateProcess` was called for either. The controller kept exact root/worker creation and executable checks, excluded production PID 43744, used a bounded observer, and reported shutdown verification `INCOMPLETE`. A later read-only process check found the isolated root and all recorded workers absent, but did not retroactively make controller-time verification pass. The smallest future diagnostic improvement is to log which retained-handle Win32 identity call failed and whether the worker had independently exited, while never terminating a process whose identity cannot be proven. No controller change or execution occurred here.

## Regression tests and next stage

Before applying the patch in any disposable Engine copy: review callback ordering, delegate removal, tab-manager replacement and duplicate-spawner behavior; validate a reproducible BuildPlugin/UBT procedure and disk budget; then compile and run focused module lifecycle checks in that isolated installation. Verify Fab features and the required plugin set remain enabled, and confirm source/clone hashes and private cache/registration boundaries. Only a separately approved isolated Editor run can prove the assertion is gone and that the target map and saved Landscape load independently. That run would still need the Stage 2E height hashes, both extensions, Original Layer, proxies, visual joins, and collision checks.

The immediate decision is **not** whether to launch: the isolated Engine-plugin build path needs further offline evidence. This report and patch do not modify production or the installed Engine. No Phase 6C GO follows from static validation.
