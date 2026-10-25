# ForgeMCP 0.2.17 — Manual Post-Save Verification

Checked: October 23, 2026, 19:17 EDT / 23:17 UTC.
Final verdict: **INCOMPLETE**.

Native manual-save output is verified for both affected packages. The current terrain, loaded actor state and clean-package inventory match the expected two-sculpt result. The Landscape root file was rewritten with identical bytes, so the owner's explicit unchanged-file condition prevents a PASS. Independent serialized height correctness has not been established by a disk reload.

This is a read-only follow-up to [the complete multi-sculpt execution report](ForgeMCP_0.2.17_WorldPartition_MultiSculpt_Execution_20261023T230054Z.md). It supersedes that report's unsaved-state finding as a current save-status observation; it does not erase historical evidence.

## 1. Current Editor identity — PASS

Fresh forge_list_sessions and unreal_project_info confirm unreal-43744 / PID 43744, UE 5.6.1-44394996+++UE5+Release-5.6, native ForgeMCP 0.2.17-alpha.1, G:/ForgeMCP/ForgeMCPDev.uproject, /Game/Levels/L_City_World_Master.L_City_World_Master, PIE stopped.

Current Landscape GUID: BD45FDD94EC2A29617B50794F2DE4E9D. Dimensions 2041 x 2041. Root and affected LandscapeStreamingProxy_2_2_0 both resolve through native actor inspection in the current world. Their exact paths and actor GUIDs are retained in the evidence JSON.

## 2. Fresh terrain verification — PASS for current loaded data

| Check | Actual value |
|---|---|
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B |
| ForgeTerrain full-height MD5 | 08cbe382a59441d8148a674cf0d83851 |
| Original layer GUID | 198824024FF8A77A01535B86021D9B34 |
| Original layer full-height MD5 | 9f43572fbc2c06ef497da015879cdb23 |
| Original layer elevation | 0 / 0 cm |
| ForgeTerrain elevation | -100 / 0 cm |
| Layer state | Both visible and unlocked; layers_up_to_date=true |
| Landscape dirty summary | false |
| Streaming proxies | 16 loaded / 0 unloaded |
| Registered Landscape / collision components | 64 / 64 |

Native bounded readback of [1042,1065,1098,1075] returned 627 samples, MD5 3817bd2c18535a9b4529387de493f2b9. Every sample matches the independently prepared final two-operation array. All 120 modified vertices retain their exact expected values. All 101 original nonzero carved vertices remain unchanged.

Left extension write rectangle [1043,1068,1057,1074] and right extension [1083,1066,1097,1072] remain present in height data. Each has 60 changed samples, with new minimum -35.15625 cm. No sculpt or preview/apply was repeated.

## 3. Complete dirty-package inventory — PASS

Snapshot B8315F5C4E06C8CFFBB27EA6A3D85C57 inspected 1183 loaded packages: inventory_complete=true, snapshot_limit_reached=false, no inspection errors, no further pages.

Only /Script/SlateCore is dirty, with verified compiled-in engine-script provenance. Zero dirty production Content packages were reported. Both affected actors remain loaded and resolved, and their previously established external package names are absent from the complete dirty inventory. This combination supports loaded/clean actor-package state; dirty-list absence alone is not used as proof of disk content.

## 4. Exact affected-file comparison

All hashes below are SHA-256. Timestamps are filesystem LastWriteTime in UTC.

### Landscape streaming proxy

Package: /Game/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2

- Production file exists.
- Before: 608675 bytes; 90e4cdcb0e922f6551def953212beecd268b6d0383f0452df012d81dc7311aa9.
- After: 609966 bytes; 01bcd92c87e93b000811a863b88701ec845ff0e7487c868f0ccb92a46a955b61.
- Last write: 2026-10-23T23:12:10.174677Z.
- Result: file bytes changed; native log independently records writing this exact production package.

### Landscape root

Package: /Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT

- Production file exists.
- Before and after: 5063 bytes.
- Before and after SHA-256: 9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df.
- Last write: 2026-10-23T23:12:10.143678Z.
- Result: native log records rewriting the exact production package, and its timestamp advanced to that save event, but serialized bytes remain identical.

An unchanged root hash is not, by itself, evidence that Unreal failed to save it. However the owner's instructions explicitly require INCOMPLETE or BLOCKED if either affected package is unchanged on disk. This report follows that criterion rather than asserting PASS.

## 5. Native save-log evidence — PASS for production output

Current Editor log:
- 23:12:09.828 UTC: InternalPromptForCheckoutAndSave started.
- 23:12:10.143 UTC: production root package output moved into Content.
- 23:12:10.174 UTC: production streaming-proxy package output moved into Content.
- 23:12:10.219 UTC: save prompt operation completed.
- 23:12:10.264 UTC: validation of two assets started.

These correspond to 19:12:09–10 EDT on October 23. The relevant log excerpt is retained in the evidence JSON and remains in Saved/Logs/ForgeMCPDev.log, lines 1172–1190 at inspection time.

Earlier 23:08:49 UTC autosave entries target Saved/Autosaves. They are distinct from this later production Content save and are not used as proof of the owner's production save.

## 6. Unrelated-file comparison

All 23 current world/map/external-package source files were compared against the exact pre-sculpt SHA-256 inventory. Only the affected streaming proxy has changed bytes. The other 22 files, including the root, match that inventory.

A full current Content audit covers 1530 files. Relative to the older recorded post-first-riverbed baseline, the differences are exactly:
- Changed: Weather Blueprint, plus the intended Landscape streaming proxy.
- Added: previously reviewed new Weather actor package.
- Absent: previously reviewed older Weather actor package.

The weather differences already existed in the pre-sculpt audit. No additional Content difference was found. This comparison is a Content and world-scope byte audit, not a claim about every file on the drive or property-by-property asset semantics. The pre-sculpt artifact pins all 23 world source files; it does not pin a fresh full-Content hash for every unrelated asset.

No historical checkpoint or production file was overwritten by this verification.

## 7. Save status and limitations

**Manual save output: VERIFIED** by native production save log, file presence/timestamps, changed proxy bytes, loaded actors and clean native package state.

**Requested final verdict: INCOMPLETE**, because:
1. The Landscape root file is byte-identical to its pre-sculpt baseline, triggering the owner's stated unchanged-file condition.
2. No genuine independent disk reload or equivalent independent deserialization has established that the saved proxy contains the correct serialized two-extension heights.

The current live height hashes and samples remain correct. Clean flags and a changed proxy hash are not substituted for disk-reload proof. No repeat save is recommended or attempted merely to force a different root hash.

## 8. Outstanding close-up and collision acceptance

Close-up visual assessment of both joins remains incomplete; the retained post-sculpt screenshot is too distant for that claim. No new viewport/camera action was performed in this verification.

All collision components remain registered. Actual collision-height behavior remains NOT TESTED; native operation results deferred collision-height validation until save/reload. This post-save verification did not perform collision queries, PIE or a reload.

## 9. Stage 2E recommendation — prepare separately; no launch authorized

Use this current saved proxy hash, the unchanged root hash, and expected native ForgeTerrain MD5 08cbe382a59441d8148a674cf0d83851 as the next disk-reload baseline. Do not reuse historical flat-terrain hashes.

The next bounded test should prepare a new independent test-only project copy, with no shared writable production files, verified private DDC/cache/log/session paths, the correct UE 5.6.1 executable, and a pinned source/copy manifest. Do not reuse or overwrite an older isolated copy without review.

Before launching, obtain separate owner approval for ONE bounded isolated Editor load. Then inspect disk-loaded Landscape/layer GUIDs, full height hashes, all 120 extension samples and 101 protected samples, 16 proxies, 64 terrain/collision components, serialization diagnostics and safely supported collision behavior. The production Editor must remain untouched.

This verification neither prepares the isolated copy nor launches it. Close-up visual acceptance, Stage 2E reload acceptance and Phase 6C release acceptance remain separate.

## 10. Evidence

[Post-save native responses, exact readback, file comparisons and save-log excerpt](WorldPartitionMultiSculpt_20261023T230054Z/manual_save_verification_20261023T231706Z.json).

No terrain edit, new session request, additional save, actor deletion, restore, restart, isolated launch or automatic cleanup occurred.

**INCOMPLETE — manual save output verified; root bytes unchanged; independent disk-reload height correctness not yet tested.**

