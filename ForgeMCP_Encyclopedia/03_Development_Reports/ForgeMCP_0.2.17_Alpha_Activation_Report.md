# ForgeMCP 0.2.17 Alpha Activation Report

Date: October 23, 2026  
Project: G:/ForgeMCP/ForgeMCPDev.uproject  
Engine: Unreal Engine 5.6.1  
Final verdict: **BLOCKED — DEPLOYMENT REQUIREMENTS UNSATISFIED**

## Executive summary

The owner-approved deployment was completed. The original production Editor exited normally, the exact five-file native release set was installed and SHA-256 verified, and the same project was reopened once. The new Editor session authenticates as unreal-43744 / PID 43744, and the live native health response reports ForgeMCP 0.2.17-alpha.1 on UE 5.6.1.

The saved production Landscape remains intact. The Landscape GUID, both edit-layer GUIDs and height checksums, the saved ForgeTerrain riverbed minimum of −100 cm, all 16 streaming proxies, 64 Landscape components, 64 collision components, and clean production Content state were verified read-only after reopening.

Activation is not fully accepted because the current Codex tool catalog still exposes none of the five new MCP interfaces. Native health advertises the session preflight/request/status/revoke capabilities, and the staged stdio release test had discovered five schemas, but this active client session does not provide callable definitions for those new tools. No editing session was requested or created, and no Landscape edit or save occurred during activation.

## 1. Staged release verification

| Item | Verified result |
|---|---|
| Plugin descriptor | Version 31, 0.2.17-alpha.1 |
| Engine | UE 5.6.1, changelist 44394996 |
| UnrealEditor.modules BuildId | 43139311, matching the installed Editor build |
| Native release build | BuildRelease.log: Result: Succeeded |
| Native Landscape automation | 5 succeeded, 0 failed, 0 not run |
| Python regression | 562 passed |
| Python lint | ruff check server tests passed |
| Staged MCP stdio discovery | Five new tool schemas discovered |
| Runtime dependencies | Installed UE plugins GameplayAbilities and WebBrowserWidget; GameplayAbilities is enabled in this project |

The staged release report is Saved/ForgeMCP_Landscape_EditSession_Alpha_Development_Report.md; the user guide is docs/landscape_edit_sessions.md; native test results are Saved/LandscapeEditSession_Dev_20261023T200056Z/native_report_release/index.json.

## 2. Production safety before deployment

Before shutdown, the live production Editor was authenticated as unreal-22604 / PID 22604, with the expected project and production level, and PIE stopped. The Landscape identity was BD45FDD94EC2A29617B50794F2DE4E9D.

Pre-deployment Landscape readback showed:

- Original Layer GUID 198824024FF8A77A01535B86021D9B34, visible and unlocked, complete height checksum 9f43572fbc2c06ef497da015879cdb23, elevation 0/0 cm.
- ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B, visible and unlocked, checksum dd428766880ec01a848b4381fba82838, elevation −100/0 cm.
- 16 loaded and 0 unloaded streaming proxies; 64 registered Landscape components and 64 registered collision components.
- Landscape not dirty and its layers up to date.
- Complete loaded-package inspection found no dirty production Content. The only dirty entries were compiled-in engine-script packages.

## 3. Recovery checkpoint

Checkpoint root:

G:/ForgeMCP_Recovery_Checkpoints/ForgeMCP_0.2.17_Activation_20261023T210005Z

The checkpoint manifest pin remains SHA-256 3f42b6a4243a0ef197417ab4ee7d13fa01cc68621ec7bf4779875fd305e29aa0. Post-deployment audit verified all 205 production-before checkpoint files and all 7 release-candidate files against their manifest hashes and sizes, with zero mismatches. The existing Stage 1, native adoption, and Stage 2E post-adoption Landscape checkpoints were not changed by deployment.

The checkpoint’s current production-file comparison found no unexpected changes outside the four replaced DLL/PDB files. The fifth deployed file, UnrealEditor.modules, has the same hash as before. Project configuration, plugin descriptor, filter configuration, and .uproject retain their checkpoint hashes. No recovery or restore was performed.

## 4. Approved deployment execution

The shutdown was approved by the owner and performed orderly:

- CloseMainWindow() was sent only to identity-verified PID 22604.
- The process exited normally at approximately 2026-10-23 21:05:24 UTC; no force termination was used.
- Before replacement, no Unreal Editor process remained and no ForgeMCP module was loaded from the deployment directory.

The five exact release files installed to G:/ForgeMCP/Plugins/Forge/Binaries/Win64 are:

| File | Installed SHA-256 | Result |
|---|---|---|
| UnrealEditor-MajesticForge.dll | bec700265079898a48c98cb4e09942dc973d6fe2080aa238cc53080ac9fe98bb | PASS |
| UnrealEditor-MajesticForgeRuntime.dll | ae910bc9e0f711eb06fa38607b1171e487ae8934265ee8e970f45282eb04c74d | PASS |
| UnrealEditor-MajesticForge.pdb | 4e5da685c683b9a72c7eebe4fce42ca018c622c3abbe1e61defcee262a7967ed | PASS |
| UnrealEditor-MajesticForgeRuntime.pdb | f99d8ac22504f6630ca996a940d8a2661ae3e59665f7ea27e8953d97f168cb15 | PASS |
| UnrealEditor.modules | e16a1ae507bb506e7e98f0e9871eea4b1f69683d8000ffaf482987f0a7136781 | PASS |

The first atomic replacement attempt used an unsupported null backup-path argument. It failed before changing its target; the original DLL hash was confirmed unchanged. The release was then installed using staged, same-volume atomic file moves, with source, staging, and destination hashes checked. The Editor remained closed throughout deployment. No automatic rollback was attempted.

Deployment evidence is recorded in Saved/ForgeMCP_0.2.17_Deployment_Evidence.json.

## 5. Reopened Editor and live native version

The same production project was launched once with the installed UE 5.6.1 executable:

G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe G:/ForgeMCP/ForgeMCPDev.uproject /Game/Levels/L_City_World_Master

The new process identity is PID 43744, created at 2026-10-23T21:07:21.0178001Z. Its loaded module paths are the production plugin directory:

- G:/ForgeMCP/Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll
- G:/ForgeMCP/Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForgeRuntime.dll

Fresh forge_list_sessions, unreal_project_info, forge_status, and forge_ensure_connected responses identify the active session as unreal-43744 / PID 43744, project G:/ForgeMCP/ForgeMCPDev.uproject, level /Game/Levels/L_City_World_Master.L_City_World_Master, UE 5.6.1, ForgeMCP 0.2.17-alpha.1, and PIE stopped. The Editor log records bridge readiness for unreal-43744 and the target World Partition map load/initialization sequence.

forge_ensure_connected reports the Unreal endpoint connected. Its aggregate result is false only because the unrelated Blender endpoint is disconnected; this does not change the successful Unreal-specific result.

## 6. MCP interface discovery and compatibility

The five expected new client interfaces are:

1. unreal_landscape_edit_session_preflight
2. unreal_request_landscape_edit_session
3. unreal_landscape_edit_session_status
4. unreal_revoke_landscape_edit_session
5. unreal_read_landscape_height_region

Staged stdio discovery had found all five. In the current Codex session, the live ALL_TOOLS catalog contains 116 ForgeMCP tools, but 0 of these 5 interfaces. Direct callable checks for the new preflight and bounded-height-read tools are undefined in this session.

The native bridge health capability list includes landscape_edit_session_preflight, landscape_edit_session_request, landscape_edit_session_status, and landscape_edit_session_revoke. It also includes the existing landscape_read_region capability. This native capability response is evidence of the loaded adapter, not proof that the five new MCP tool definitions have been refreshed into the active Codex client.

Legacy read-only tools remain operational: session discovery, project info, Landscape inspection, dirty-package inspection, and ForgeMCP status/connection checks all returned current native responses.

No supported Codex-side MCP tool-catalog refresh control is exposed in this active tool set. The native Editor reconnect succeeded, but it did not update this conversation’s tool definitions. The exact five-interface discovery gate therefore remains open.

## 7. Post-deployment production and Landscape verification

A complete read-only dirty-package snapshot inspected 1,181 loaded packages with no inventory errors or further pages. It found one dirty package, /Script/SlateCore, classified with verified compiled-in engine-script provenance. Zero dirty production Content packages were observed.

A fresh Landscape inspection after startup settling reports:

| Gate | Result |
|---|---|
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D, unchanged |
| Current level / PIE | L_City_World_Master / PIE stopped |
| Original Layer | GUID 198824024FF8A77A01535B86021D9B34, visible, unlocked |
| Original Layer full-height checksum | 9f43572fbc2c06ef497da015879cdb23, unchanged |
| Original Layer elevation / dimensions | 0/0 cm; 2041 × 2041 |
| ForgeTerrain | GUID 2E6FC5F94C4EF704F700299B5D08C23B, visible, unlocked |
| ForgeTerrain full-height checksum | dd428766880ec01a848b4381fba82838 |
| ForgeTerrain elevation / dimensions | −100/0 cm; 2041 × 2041 |
| Streaming proxies | 16 loaded / 0 unloaded |
| Registered Landscape / collision components | 64 / 64 |
| Landscape dirty / layers up to date | false / true |

The first immediate read after map load reported layers_up_to_date=false; a later read-only inspection after startup settled reported true, with the same layer hashes, GUIDs, elevations, and proxy/component counts. The Landscape remained clean. No terrain operation, session request, save, or restore occurred during activation.

## 8. Multi-operation acceptance preparation

No landscape-edit session was requested, created, approved, or applied. No Landscape modification was performed.

The development report proposes a small test region [1116, 1116, 1132, 1132] with raise and smooth, disjoint from the saved riverbed region. It remains a proposal only: the unavailable client preflight tool prevented fresh validation of its bounds, edit-layer binding, operation halos, and World Partition ownership in this active session. Do not request approval or edit until those gates are freshly checked with the newly exposed tools and the owner approves the exact scope.

The staged native tests used a disposable non-World-Partition Landscape. Production World Partition multi-operation behavior, approval UX, revocation behavior in the live Editor, collision, and disk-reload acceptance remain separate gates.

## 9. Remaining blocker and final verdict

Native binary deployment and live plugin activation passed. Production identity, clean Content state, saved riverbed preservation, Original Layer preservation, World Partition proxy topology, and recovery checkpoint verification passed.

The unresolved requirement is the active Codex MCP catalog refresh: the current session still lacks all five new tool definitions, so the five interfaces cannot be exercised or verified from this client. No editing session was opened and no terrain content was changed.

**BLOCKED — DEPLOYMENT REQUIREMENTS UNSATISFIED**. The plugin is live at 0.2.17-alpha.1, but the user-requested activation verdict ACTIVE — 0.2.17 ALPHA VERIFIED is not justified until the current Codex client exposes and verifies all five new MCP tools.



## Post app-close/reopen recheck — 2026-10-23 21:16 UTC

The user closed and reopened the ChatGPT/Codex app and asked for tool discovery to be retried. Fresh discovery still finds **0 of the 5 new Codex MCP tool definitions** in the active `ALL_TOOLS` catalog:

- `unreal_landscape_edit_session_preflight`
- `unreal_request_landscape_edit_session`
- `unreal_landscape_edit_session_status`
- `unreal_revoke_landscape_edit_session`
- `unreal_read_landscape_height_region`

The catalog continues to expose the legacy Landscape inspection, preview/apply, job, and adoption interfaces. Native ForgeMCP discovery independently reports connected session `unreal-43744`, PID 43744, adapter 0.2.17-alpha.1, UE 5.6.1, and native capabilities `landscape_edit_session_preflight`, `landscape_edit_session_request`, `landscape_edit_session_status`, and `landscape_edit_session_revoke`, plus legacy `landscape_read_region`. Native capability advertisement does not refresh or prove Codex-side tool definitions. No supported catalog-refresh control is available in the current tool set.

Read-only identity recheck still matches project `G:/ForgeMCP/ForgeMCPDev.uproject`, level `/Game/Levels/L_City_World_Master.L_City_World_Master`, with PIE stopped. Landscape remains GUID `BD45FDD94EC2A29617B50794F2DE4E9D`; Original Layer and ForgeTerrain GUIDs remain unchanged, visible and unlocked. Their reported height checksums/elevations remain Original Layer `9f43572fbc2c06ef497da015879cdb23`, 0/0 cm; ForgeTerrain `dd428766880ec01a848b4381fba82838`, −100/0 cm. Topology remains 16 loaded / 0 unloaded proxies and 64 / 64 terrain/collision components.

**Current dirty-package state differs from the earlier activation check.** A fresh complete inventory of 1,183 loaded packages found four dirty packages: three production Content packages and compiled-in `/Script/SlateCore`. Production entries are:

| Package | State |
|---|---|
| `/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Weather` | Dirty project Content package |
| `/Game/__ExternalActors__/Levels/L_City_World_Master/9/UX/QWIT4Q5JJ8585ENBY5400I` | Dirty existing external actor package; owner resolves to an Ultra Dynamic Weather actor |
| `/Game/__ExternalActors__/Levels/L_City_World_Master/C/L1/9FKOG7WXO3MCN53CTMWDWE` | Dirty newly created external actor package; owner resolves to another Ultra Dynamic Weather actor |

No cause is inferred. No dirty flag was cleared and no save, session request, terrain operation, or restoration was performed. The prior report's “zero dirty production Content packages” finding remains historical and is superseded by this current snapshot for readiness decisions.

**Current outcome remains BLOCKED — DEPLOYMENT REQUIREMENTS UNSATISFIED.** Closing and reopening the app did not refresh the five new tool definitions, and the current dirty production packages independently prevent proceeding to an editing-session acceptance test. No Landscape or production package was modified by this recheck.

