# ForgeMCP Landscape Stage 2B — Save and Persistence Report

Date: October 23, 2026, approximately 03:25 EDT  
Final verdict: **SAVE BLOCKED — SCOPED CAPABILITY UNAVAILABLE**

## 1. Authenticated session and project details

The existing Editor was rediscovered through forge_list_sessions and authenticated with explicit session unreal-22604 / PID 22604. It reports ForgeMCP 0.2.16-alpha.1 and UE 5.6.1. No old PID was assumed and no other Editor was launched.


```json
{
  "ok": true,
  "session_id": "unreal-22604",
  "data": {
    "project_name": "ForgeMCPDev",
    "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
    "engine_version": "5.6.1-44394996+++UE5+Release-5.6",
    "level": "/Game/Levels/L_City_World_Master.L_City_World_Master",
    "play_in_editor": false
  }
}
```

Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D matches. World Partition remains enabled and PIE is stopped. Both original Layer and ForgeTerrain match the preceding successful in-memory adoption report. No adoption request, grant or setup was repeated.

## 2. Recovery checkpoint verification

Both checkpoints were read and independently reverified without modification:

- Stage 1: G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892.
- Native: G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF.

All 32 Stage 1 backup files (23 native scope and 9 supplemental) match their recorded SHA-256 values; all 32 isolated reconstruction copies also match. All 23 native checkpoint files match native MD5 manifest entries and Stage 1 SHA-256 values. Their current 23 production originals still match. No checkpoint file was altered.

Stage 1 manifest SHA-256: d9de66d61745427b313c5ee7eb5a1f2238d8c76ca2dc5aa0cd277929bbac3388  
Native manifest SHA-256: e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f  
Free storage: 190,541,111,296 bytes (about 177.46 GiB), exceeding the checked 1 GiB minimum for this small package set. Storage is not the blocker.

## 3. Actual save mechanism and blocking contract

The advertised tools were rediscovered. unreal_preview_current_level_save successfully returned a read-only review for the active persistent level and its loaded external-object packages. The preview contains 23 observed packages but marks exactly the 17 authorized Landscape-owned external packages will_save=true, with no will_delete=true. The map and the five unrelated external actor packages are will_save=false.

Preview ID: a7c00c724823211b3ba58ea8edd01bfe  
Intended apply tool: unreal_apply_current_level_save.  
Native implementation: FForgeLevels::Handle, current_level_save_apply, invokes FEditorFileUtils::SaveCurrentLevel and audits the reviewed package scope.

**Apply was not called.** Inspection found that the current adapter automatically restores production files when save or verification fails:

- Plugins/Forge/Source/MajesticForge/Private/ForgeLevels.cpp:651-665 enters recovery on !bVerified.
- Line 658 copies checkpoint bytes back over existing production files.
- Line 663 deletes newly created files during recovery.
- The exposed apply schema accepts only session_id, preview_id and confirmation; no option disables automatic recovery.

That behavior conflicts with the user's explicit instruction: “Do not perform automatic recovery without explicit authorization.” It cannot be excluded by reviewing a successful preview. The save route is therefore unavailable under this task's constraints even though its predicted package selection is correct.

Other advertised routes do not resolve this constraint:

- unreal_preview_level_save saves a new map to a fresh folder and explicitly excludes existing World Partition/external-package destinations.
- Landscape save/reload actions do not provide a separately approved adopted-Landscape save capability; the consumed setup_layer grant cannot be reused, and another grant was explicitly prohibited. The current adopted authorization action allowlist does not include save/reload.
- No general exact-package save tool with recovery disabled is advertised.
- No unrestricted scripting, direct disk serialization, UI automation, source edit or rebuild was used to substitute for a missing supported route.

A preview creates transient review state only; it does not save production packages. Its expiration does not affect the existing in-memory adoption. No automatic retry or scope expansion occurred.

## 4. Exact packages requested, saved, failed or modified

The 17 authorized packages below were verified by native dirty inventory actor ownership and matched one-for-one to will_save=true in the preview. Every owner resolves to the existing Landscape root or one of its 16 existing streaming proxies. None is newly created, and ownership scans are complete.

**Save requests applied: 0. Packages saved: 0. Package save failures: 0.** No save was attempted, so the block must not be described as a failed save.

| Package reviewed | Owner | Production file | Save outcome |
|---|---|---|---|
| /Game/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT | Landscape root | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | Not attempted; remains dirty in memory |
| /Game/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | Not attempted; remains dirty in memory |

Explicitly excluded from saving: /Script/SlateCore, /Script/UnrealEd, editor settings/configuration, Ultra Dynamic Sky, HLOD assets, all unrelated actor/assets, and the clean map package. The complete inventory has 19 dirty loaded packages: the 17 authorized production packages plus the two compiled-in script packages. Both script packages have verified engine-script provenance and are not save targets. The inventory was complete with no errors or further pages.

## 5. Before/after file checksums

The table records the 17 intended save targets. Since apply was never called, before and after SHA-256 values are identical. All 23 native recovery-scope production files and all nine supplemental current files were compared across Stage 2B; all 32 remain unchanged during this operation. This is distinct from the previously known supplemental settings difference relative to Stage 1.

| Production file relative to project | Before SHA-256 | After SHA-256 | Result |
|---|---|---|---|
| Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | b1723d1612763c695d0e44350f09c6fc7320d70874250f33e133ec94cde42e18 | b1723d1612763c695d0e44350f09c6fc7320d70874250f33e133ec94cde42e18 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | 657a427271aec851ad11a67a803ed5878dc7d27897b0c2e80c89f4d93ce901a9 | 657a427271aec851ad11a67a803ed5878dc7d27897b0c2e80c89f4d93ce901a9 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | bb3b860c59337346e0b3652bb8cb59f43400fecc4c44978b22d54f278351a349 | bb3b860c59337346e0b3652bb8cb59f43400fecc4c44978b22d54f278351a349 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | a5e237cb4388b97bc8f2c7c45d2ef5bb12660367801a726823af94113f97fa52 | a5e237cb4388b97bc8f2c7c45d2ef5bb12660367801a726823af94113f97fa52 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | 5c03c5062b24b57484d346716e4aea2bc966b53fc4c18b8087d0722498e74370 | 5c03c5062b24b57484d346716e4aea2bc966b53fc4c18b8087d0722498e74370 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | 2c98d9cf71b8b4fd3f96601682accbf6c94d092009d8f2537cc89cb948de3196 | 2c98d9cf71b8b4fd3f96601682accbf6c94d092009d8f2537cc89cb948de3196 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | 3fd31f6720d7496fe7dea83c143f668da7578c10a8e72573577cdab5c7670a03 | 3fd31f6720d7496fe7dea83c143f668da7578c10a8e72573577cdab5c7670a03 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | e056f875f94ec1018637cb4f73902731c737a6544cc3c6a15aff1cf83389677c | e056f875f94ec1018637cb4f73902731c737a6544cc3c6a15aff1cf83389677c | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | f435931234858e22eea465630b9975cc70f12c8baa83083363c7260712100050 | f435931234858e22eea465630b9975cc70f12c8baa83083363c7260712100050 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | 8285ba3c3d98bd7db6e165e7d5f2835f771bd545dc354bb583877031924cff19 | 8285ba3c3d98bd7db6e165e7d5f2835f771bd545dc354bb583877031924cff19 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | f6085afb66af8e30804affe5e6531db7500d7a6ccefab548b2b0578b4d091a5f | f6085afb66af8e30804affe5e6531db7500d7a6ccefab548b2b0578b4d091a5f | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | fb7c9674915a6351bd8c9c9e2ffae4715431ebca231a702ef3e9e041ecf33626 | fb7c9674915a6351bd8c9c9e2ffae4715431ebca231a702ef3e9e041ecf33626 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | b0778b3a47349c4d4ff6425d4df7ae5ffd525d7757bd56f32fd2f5738ca38fb7 | b0778b3a47349c4d4ff6425d4df7ae5ffd525d7757bd56f32fd2f5738ca38fb7 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | 3d294c102d7f35d2202c37045970ca0942799a6cbc0100aeab73e915ff690139 | 3d294c102d7f35d2202c37045970ca0942799a6cbc0100aeab73e915ff690139 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | 020bc5d773d98e83dbe6c9753deb6be9aa7c4dd48497b26364483ea48edabeaa | 020bc5d773d98e83dbe6c9753deb6be9aa7c4dd48497b26364483ea48edabeaa | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | 193b0a56a14033c3e28a12a44fa64773f64ca6e39987fcaa7cf5ec3a9490fb93 | 193b0a56a14033c3e28a12a44fa64773f64ca6e39987fcaa7cf5ec3a9490fb93 | Unchanged; not saved |
| Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | 2f55b75143e371bff56d8b69c68584cf6b775b29b67c6ccc31a2fd25a103d5c9 | 2f55b75143e371bff56d8b69c68584cf6b775b29b67c6ccc31a2fd25a103d5c9 | Unchanged; not saved |

The complete 32-file before/after audit, full native save preview and full dirty inventories are retained in [evidence.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2B_Evidence_20261023/evidence.json).

## 6. Original Layer verification

Original Layer remains present, visible and unlocked, GUID 198824024FF8A77A01535B86021D9B34. Full native height readback checksum remains 9f43572fbc2c06ef497da015879cdb23 over 2041 x 2041 vertices. Its reported state is identical to the previous adoption evidence.

## 7. ForgeTerrain verification

ForgeTerrain remains present with GUID 2E6FC5F94C4EF704F700299B5D08C23B, visible and unlocked. Native readback supports heights across 2041 x 2041 vertices, with checksum 9f43572fbc2c06ef497da015879cdb23 and min/max 0 cm / 0 cm. Its reported layer record is unchanged during Stage 2B.

Complete final layer readback:

```json
[
  {
    "name": "Layer",
    "guid": "198824024FF8A77A01535B86021D9B34",
    "locked": false,
    "visible": true,
    "height_read_supported": true,
    "height_sha_md5": "9f43572fbc2c06ef497da015879cdb23",
    "min_local_cm": 0,
    "max_local_cm": 0,
    "vertices_x": 2041,
    "vertices_y": 2041
  },
  {
    "name": "ForgeTerrain",
    "guid": "2E6FC5F94C4EF704F700299B5D08C23B",
    "locked": false,
    "visible": true,
    "height_read_supported": true,
    "height_sha_md5": "9f43572fbc2c06ef497da015879cdb23",
    "min_local_cm": 0,
    "max_local_cm": 0,
    "vertices_x": 2041,
    "vertices_y": 2041
  }
]
```


## 8. Height and geometry preservation

Both full native layer-height checksums remain unchanged. Original layer elevation minimum/maximum are 0 cm / 0 cm, and ForgeTerrain remains neutral with the same full-array checksum. The prior native setup explicitly validated every new-layer sample as neutral and preservation of the original layer. No terrain edit occurred during Stage 2B.

No distinct composed-height export is exposed in the current inspection response. Native original-layer and neutral-layer data support an unchanged flat composed result; a separate full composed-array export or visual/collision acceptance test was not performed. This evidence limit is not a saved/reloaded geometry claim. Final composed persistence remains unverified because neither save nor reload occurred.

## 9. World Partition streaming-proxy integrity

The 16 proxy identity/ownership records were checked against the existing Stage 2 evidence. The current state reports:

- 16 loaded streaming proxies, zero unloaded.
- 64 registered Landscape components and 64 registered collision components.
- 17 total Landscape proxies including the root.
- Same Landscape GUID, original layer GUID and ForgeTerrain GUID.
- Active-world ownership retained; no World Partition configuration operation executed.

No proxy deletion/replacement, HLOD rebuild, Ultra Dynamic Sky edit, city-layout change, terrain generation, coastline/road/building operation, adoption replay, engine restart/recompile, or backup restore occurred.

## 10. Reload/persistence verification

**Not performed; persistence remains pending.** All 17 authorized packages remain unsaved in Editor memory. A reload now could discard those changes, so no reload was attempted.

The advertised Landscape reload path is guarded for supported isolated/authorized Landscape workflows; the consumed setup grant is not a reload authorization. Opening the same asset is not proof of a disk reload. No restart, forced reload, or workaround was used.

A future stage needs a supported exact-package save mechanism that respects the no-automatic-recovery requirement. After a verified save, safe reload must be assessed independently, with unrelated unsaved work preserved. This report makes no persisted-adoption claim.

## 11. Unrelated configuration-change audit

The previously observed Config/DefaultEditorPerProjectUserSettings.ini difference from Stage 1 is preserved and not attributed. It concerns CameraSpeed, editor-grid entries, EditorViews and PerInstanceSettings.

Stage 1 SHA-256: 69e2efc1894343b1c969d2306668202a8f120b41913e17af82842821a19ccb4d.  
Current before and after Stage 2B SHA-256: 51fb4fa5d62915034c142c4037f139e231986dd50e3bc42dde7d60bdd623bbdc.

No Stage 2B change to this file was observed. The existing settings diff/copy remain in the previous Stage 2 evidence directory. This operation did not restore, edit or save configuration. The two engine-script dirty packages were excluded without clearing their flags.

## 12. Remaining blockers or risks

The available current-level save adapter has automatic production recovery behavior that the user has not authorized. Its apply schema cannot disable it. No compliant scoped save route was established, so execution stopped before any save. No source modification/rebuild or permission expansion was attempted.

The adopted state remains unsaved. The setup grant is consumed, and no new grant was requested. Closing/reloading could discard the in-memory layer. No automatic recovery or forced persistence action should occur.

Both recovery checkpoints remain intact. The Stage 1 checkpoint is scoped operation recovery on the same G: volume, not a complete independent project archive. Native readback validation, on-disk hash checks, live reload proof and visual/runtime proof remain distinct gates.

Previous Stage 2 report evidence is preserved at [stage2_report_before_stage2b.md](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2B_Evidence_20261023/stage2_report_before_stage2b.md). Stage 2B evidence is preserved separately; neither recovery checkpoint was modified.

## 13. Final verdict

**SAVE BLOCKED — SCOPED CAPABILITY UNAVAILABLE**

Identity, geometry/layer state, package ownership, checkpoint integrity and free-space checks pass. The save preview predicts exactly the authorized 17 packages, but apply cannot meet the explicit no-automatic-recovery requirement. No save was applied; no save failed; no reload occurred. Native in-memory adoption remains verified and unsaved.

The Stage 2 report is updated with this outcome. The operation ends after reporting, without Stage 3 or any terrain work.

