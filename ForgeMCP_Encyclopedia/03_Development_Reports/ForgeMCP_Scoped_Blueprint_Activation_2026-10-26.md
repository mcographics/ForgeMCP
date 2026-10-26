---
title: Scoped Blueprint journal activation - full build passed, startup blocked
created: 2026-10-26
time: "04:00:10"
timezone: America/Toronto
status: Blocked
summary: The full UE 5.6.1 Editor target passed 37 actions, but the approved single reopen hit a TedsOutliner request for unloaded LevelEditor before both queued tests could run; all 2,798 Content files remained unchanged.
evidence:
  - ../04_Testing_and_Validation/ForgeMCP_Scoped_Blueprint_Activation_2026-10-26.json
  - ForgeMCP_Scoped_Blueprint_Journal_Source_2026-10-26.md
  - ForgeMCP_Blueprint_Progress_Update_2026-10-26.md
---

# Scoped Blueprint journal activation: full build passed, startup blocked

Date: 2026-10-26 (America/Toronto)

## Authorization and preserved baseline

The owner approved one additional controlled close, binary backup, full build and reopen of the same ForgeMCPDev Editor, with only the inspection regression and new scoped-journal automation tests queued. The owner subsequently authorized continued work while unavailable. No additional Editor session or isolated engine installation was created.

Fresh authenticated identity and a complete dirty-package scan preceded the close. UE 5.6.1, ForgeMCPDev, TestArea and stopped PIE were confirmed. All 1,311 loaded packages were inspected: no dirty project Content; only compiled-in `/Script/SlateCore` was dirty. This scan does not classify unloaded packages as clean.

Ten current binary files totaling **83,225,281 bytes** were backed up, preserving relative paths, with source/destination SHA-256 verification. Eleven implementation/test source files were copied and hashed for the build receipt. Global and project Codex configuration hashes remained unchanged.

A complete **2,798-file Content SHA-256 baseline** was recorded. The normal Editor close took approximately 26.5 seconds, exceeding the helper's initial 20-second wait. The helper stopped before building. Independent process/log inspection then confirmed completed normal shutdown; the backups were reverified before continuing the already approved build. No force termination, second close or binary restoration occurred.

## Full build result

The official UE 5.6.1 toolchain compiled and linked the plugin. The final `ForgeMCPDevEditor` target completed **37 actions**, with **Result: Succeeded** and total execution time **347.76 seconds**. The journal implementation and native test are linked in the on-disk DLL. This supersedes the earlier source-only linking gate, while leaving runtime acceptance separate.

Native DLL SHA-256: `C6C71E9BF4568747AEC408E17A8FA3DC43EF66CFA15398978812400D68FCA6DA`.

## Approved reopen failed before automation

The same project was reopened exactly once on TestArea, queuing:

- `ForgeMCP.BlueprintInspection.LargeGraphPaginationAndTrace`
- `ForgeMCP.BlueprintPatches.ScopedPrimitiveJournal`

At approximately **04:00:10 EDT**, startup asserted on `ModuleManager.IsModuleLoaded(ModuleName)`: Unreal tried to obtain the unloaded `LevelEditor` module. The recorded stack includes `FModuleManager::GetModuleChecked<FLevelEditorModule>()` and `UE::Editor::Outliner::FTedsOutlinerModule::StartupModule()` at `TedsOutlinerModule.cpp:109`.

The Editor exited during startup. No authenticated session became available, no native automation report was produced, and **both queued tests were NOT RUN**. No disposable journal fixture directory/package was created. There is no remaining UnrealEditor process or connected Editor session at the post-failure check.

The startup stack identifies the failing module-access path. It does not establish that the journal implementation is correct or defective, that a saved Blueprint is corrupt, or that a historical workaround is safe to adopt. The earlier successful 1,001-node inspection test remains historical evidence for its earlier binary and session; it was not rerun here.

## Content integrity and validation correction

The complete post-failure audit found **2,798 files**, **zero added**, **zero modified**, and **zero deleted**. Every original Content file matched its baseline SHA-256 and length. The before/after manifest bytes also hash identically: `46CE5DBE1D16EB6F1BA0305041915328E76F9D0C0A3C3C3096BEE8AC962B6328`.

The first comparison helper incorrectly wrapped PowerShell 5.1's parsed JSON array and reported a baseline count of one. That comparison was invalid, rather than evidence of Content changes. Both complete hash manifests were retained unchanged and independently compared using Node, which validated all 2,798 unique file identities and exact matches. The invalid helper output is preserved separately in the local evidence directory.

## Gate disposition

| Gate | Result |
| --- | --- |
| Pre-close identity and loaded dirty-package inventory | PASS for the recorded snapshot. |
| Binary backup, source snapshot and configuration preservation | PASS. |
| Full UE 5.6.1 build/link | PASS, 37 final-target actions. |
| Approved startup and authenticated reconnection | FAILED/BLOCKED at the TedsOutliner/LevelEditor assertion. |
| Two queued native tests | NOT RUN. |
| Journal real compiler-failure, rollback/refusal and preservation assertions | NOT RUN. |
| Owning-client exposure of the two new patch tools | NOT EXPOSED in the current client namespace. |
| Complete Content file preservation | PASS, 2,798 unchanged files. |
| General save, independent reload, Niagara runtime and ViperBP readiness | Not passed; ViperBP untouched and NO-GO. |

Native changes stopped at the failed startup acceptance gate, following the original instruction to stop on a failed safety/acceptance gate and avoid unverified recovery. No additional launch, engine patch, project reconfiguration, package reload, save, restore or cleanup was attempted. The next dependency is read-only startup diagnosis and a reviewable scoped resolution; historical deferred designs are not implemented fixes.

Raw build logs, crash evidence, source copies, backups, manifests and the corrected audit remain local under the dated scoped-activation evidence folder. Public records are sanitized derivatives. [Curated activation evidence](../04_Testing_and_Validation/ForgeMCP_Scoped_Blueprint_Activation_2026-10-26.json) preserves the build/test-execution distinction and receipts without publishing runtime identities or credentials.
