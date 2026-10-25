# ForgeMCP 0.2.17 — World Partition Multi-Sculpt Acceptance

Checked: October 23, 2026, 18:23 EDT (22:23 UTC).
Final verdict: **BLOCKED — SAFETY OR AUTHORIZATION GATE**

## 1. Active Editor session and plugin version

Fresh forge_list_sessions and unreal_project_info calls authenticated existing session unreal-43744, PID 43744, native ForgeMCP 0.2.17-alpha.1, UE 5.6.1-44394996+++UE5+Release-5.6, project G:/ForgeMCP/ForgeMCPDev.uproject, level /Game/Levels/L_City_World_Master.L_City_World_Master, PIE stopped. No Editor was launched or restarted.

## 2. Initial dirty-package findings and resolution

Phase 1 failed its clean production Content gate. The user's instructions explicitly require: "If production Content packages remain dirty, report the findings and STOP for my decision."

Complete native snapshot E2FE1FFA458A75BD16FE559D2113D4AB inspected 1183 loaded packages. inventory_complete=true, snapshot_limit_reached=false, returned_count=4, no further pages and inspection_errors=[].

| Exact package | Verified ownership and state |
|---|---|
| /Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Weather | Dirty existing project Blueprint package; contains Blueprint, generated class, skeleton class and class-default object. Disk .uasset exists (19,048,149 bytes). |
| /Game/__ExternalActors__/Levels/L_City_World_Master/9/UX/QWIT4Q5JJ8585ENBY5400I | Dirty existing external actor package. Inventory associates the exact weather object below, class /Engine/Transient.REINST_Ultra_Dynamic_Weather_C_1. Disk .uasset exists (38,758 bytes). |
| /Game/__ExternalActors__/Levels/L_City_World_Master/C/L1/9FKOG7WXO3MCN53CTMWDWE | Dirty newly created external actor package. Inventory and direct inspection identify the weather actor below. No corresponding .uasset exists on disk. |
| /Script/SlateCore | Dirty compiled-in engine-script package; verified engine-module provenance. This is separate from the three production Content entries. |

Existing package's associated object:
`/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Ultra_Dynamic_Weather_C_UAID_701CE7E46087C60B03_1356334297`

Direct unreal_inspect_actor on that path returned actor_not_found: "Actor is not loaded in the current editor world." The package inventory's object association and the failed direct level-actor resolution are recorded separately; neither is substituted for the other.

Newly created package's actor:
`/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Ultra_Dynamic_Weather_C_UAID_701CE7E46087F10D03_1329563975`

Direct inspection succeeded: label Ultra_Dynamic_Weather; class /Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Weather.Ultra_Dynamic_Weather_C; actor GUID EEDB97B4455CDCD3860017A2E300BFB1; location [0,0,20], rotation [0,0,0], scale [1,1,1], hidden=false, no tags. These are current values, not a proven before/after property diff.

Read-only asset-registry inspection confirmed the weather asset is an Actor Blueprint and includes the existing external actor package among its registry referencers. It reported loads_assets=false. Its dependency/referencer samples were bounded and truncated, so they are not a complete dependency audit.

Determined unsaved state: all three project packages are dirty; one actor package is newly created and absent on disk. The exact unsaved Blueprint graph/property changes and existing actor property changes were not established. The REINST class is an observed class identity, not a proven cause. No inference that any change is harmful is made.

Resolution: **pending owner decision**. Nothing was saved, discarded, reloaded, overwritten, restored, or cleared. Loaded-package inventory does not classify unloaded packages as clean.

## 3. Landscape and layer baseline

Phase 2 was not entered because Phase 1 requires a stop. Expected baseline from the user's instructions:
- Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D.
- ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B; expected full height MD5 dd428766880ec01a848b4381fba82838.
- Original layer expected full height MD5 9f43572fbc2c06ef497da015879cdb23.
- Riverbed minimum -100 cm; 16 loaded streaming proxies; 64 registered Landscape and 64 collision components.

The prior discovery-recovery report verified those values earlier. They were not revalidated as a fresh acceptance baseline in this Phase 1 run. Recovery checkpoint integrity and absence of unexpected disk changes were not audited in this run.

## 4. Editing-session authorization status

No session was requested, approved, revoked or used in this run. No approval command was generated. The previously verified availability of five tools does not authorize sculpting or resolve the dirty-package gate.

## 5. Approved operation scopes and exact regions

None. Two smoothly connected riverbed extensions have not been designed, read back or previewed in this run. No vertex region or action scope was approved.

## 6. Operation-one preview and apply results

Not performed. Zero terrain writes.

## 7. Operation-two preview and apply results

Not performed. Zero terrain writes.

## 8. Proof both operations used one approval

Unavailable: no operations and no editing-session approval occurred.

## 9. Before/after height samples and checksums

No new acceptance height samples or before/after differences were collected. Baselines above are expected/historical, not evidence of new deformation.

## 10. Original Layer integrity

No write was attempted. Fresh native checksum acceptance is deferred until the clean-state gate is resolved; no fresh checksum claim is made here.

## 11. Proxy and collision verification

Deferred at Phase 1. No fresh topology, collision behavior, or independent disk-reload acceptance is claimed.

## 12. Viewport screenshots

Not captured. No sculpt result exists to verify visually.

## 13. Changed and dirty package inventory

This recovery/acceptance run deliberately created only this Markdown report. It performed no project-asset mutation. The four dirty packages above are current observations, not changes attributed to this work.

## 14. Proposed save procedure

No save is authorized or prepared. The owner must first decide the disposition of the three weather-related packages. After the owner resolves them, capture a fresh complete dirty-package inventory and require a clean production Content gate before Phase 2.

The requested later sculpt-save boundary remains: no save between operations; after both operations and their verification, inventory all modified packages, prove ownership and intended height differences, prepare an exact native save scope, and request owner approval before saving. Do not use unrestricted Save All, automatic recovery, or a save wrapper that restores/deletes files after failed verification.

## 15. Outstanding blockers and acceptance gaps

Immediate blocker: three dirty production Content packages remain. Owner disposition is required before proceeding. The available read-only evidence does not establish an exact field-level unsaved diff or the cause of dirty state.

All subsequent gates remain pending: fresh Landscape/checkpoint integrity, extension planning, bounded readback, exact previews/halos, one owner-approved editing session, both native operations and job completion, independent height preservation checks, collision/viewport evidence, and separately authorized save.

Stage 2E independent disk-reload acceptance and Phase 6C overall release acceptance remain separate and unclaimed.

**BLOCKED — SAFETY OR AUTHORIZATION GATE**

