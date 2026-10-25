# ForgeMCP Landscape Stage 2C — Native Manual Save Resolution

Date: October 23, 2026  
Verdict: **SAVED — RELOAD VERIFICATION PENDING**  
Status: User-performed native save verified through clean production package flags, exact on-disk changes, log records and native Landscape readback. No reload performed.

## 1. Existing Landscape state

Fresh discovery and authentication confirm the same running Editor, unreal-22604 / PID 22604, ForgeMCP 0.2.16-alpha.1, UE 5.6.1, project G:/ForgeMCP/ForgeMCPDev.uproject and production level /Game/Levels/L_City_World_Master. PIE is stopped. The Editor was neither closed nor restarted.


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

The original Layer and ForgeTerrain are both visible and unlocked. Their full reported layer records exactly match the pre-save evidence. All 16 native streaming-proxy records match by GUID, path, package ownership, loading state and component/collision counts. The Landscape GUID remains BD45FDD94EC2A29617B50794F2DE4E9D.

## 2. Checkpoint verification

Before the manual save, both checkpoints were independently verified without modification:

- External Stage 1: G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892 — all 32 recorded backup files and all 32 isolated reconstruction copies match SHA-256.
- Native adoption: G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF — all 23 files match native manifest MD5 values and Stage 1 SHA-256 values.
- All 23 original production scope files matched the original baseline before saving; current native namespace membership was identical.
- All 17 intended destination files were writable; available space exceeded 177 GiB.

After the manual save, both manifest SHA-256 pins were reconfirmed unchanged:

- Stage 1 manifest: d9de66d61745427b313c5ee7eb5a1f2238d8c76ca2dc5aa0cd277929bbac3388.
- Native manifest: e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f.

The pre-save per-file checkpoint verification remains retained in pre_save_evidence.json. Checkpoints were not restored, overwritten or updated to the new source hashes. The 17 changed production files now differ as expected from pre-adoption recovery data.

## 3. Native Editor save mechanism analysis

The exact source analysis and numbered excerpts are preserved in [native_save_source_evidence.txt](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/native_save_source_evidence.txt), and the complete pre-save report is preserved in [stage2c_report_before_manual_save.md](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/stage2c_report_before_manual_save.md).

Installed official UE 5.6 source establishes:

1. LevelEditorMenu.cpp:45-71 inserts the command in the File menu; LevelEditorActions.cpp:4071 names it Save Current Level with default Ctrl+S.
2. LevelEditor.cpp:679 maps it to FLevelEditorActionCallbacks::Save.
3. LevelEditorActions.cpp:464-476 calls FEditorFileUtils::SaveCurrentLevel for this existing non-temporary world.
4. FileHelpers.cpp:4151-4198 selects only a dirty/new map and dirty/new/empty loaded external-object packages of the active level, then guards bSkipExternalObjectSave=true.
5. InternalSavePackages / PromptForCheckoutAndSave / InternalPromptForCheckoutAndSave route the selected list through native per-package saving. Existing filenames are retained.
6. Existing non-new packages respect the external-save skip guard. Clean unrelated external packages and non-level dirty script/content packages are excluded.
7. Empty packages can be deleted by native handling, but the fresh reviewed state contained none scheduled for deletion.

The ordinary menu route bypasses ForgeMCP's current-level-save apply wrapper. ForgeLevels.cpp:651-665 contains the automatic backup-copy restoration/deletion loop; that adapter was not called.

The inspected ordinary failure path provides Cancel/Retry/Continue and may leave partially saved files; it does not invoke the ForgeMCP recovery checkpoint. Separate source-control revert/reload branches were documented. The session log reports revision control disabled, with no observed provider enable/change. No source-control configuration was changed by Codex.

No plugin source/configuration changes, new grant, rebuild or Editor restart were required.

## 4. Comparison with the approved package scope

Historical preview a7c00c724823211b3ba58ea8edd01bfe was used only as retained evidence, never applied.

The fresh pre-save read-only preview 749ff1b34189f04cdf5140b14a4dc819 confirmed 23 observed packages, exactly 17 will_save=true, zero will_delete=true, the clean map will_save=false and five unrelated external actor packages will_save=false. Its selected set exactly matched the historical preview and native dirty production ownership.

Post-save findings confirm the expected scope:

- Exactly 17 Content files changed, matching the authorized Landscape root and 16 streaming proxies.
- The clean map file remained unchanged.
- The five unrelated external actor packages remained unchanged.
- Across all 1,530 project Content files, there were **no additions, deletions or unauthorized changed files**.
- The nine supplemental files audited before/after manual save are unchanged, including configuration and the two map-specific HLOD assets.
- No production package remains dirty in the complete loaded-package inventory.

This disk audit covers the complete project Content directory and the recorded supplemental files; it does not claim a full filesystem hash audit of engine/plugin directories or logs.

## 5. Whether a safe manual-save route was established

Yes. The reviewed supported interaction was File → Save Current Level in the existing main Level Editor, performed by the user. Codex did not simulate input, invoke the blocked apply adapter, serialize assets directly, issue Save All, rerun adoption, or create another layer.

Native log records show one save batch covering exactly the 17 authorized package names, at approximately **October 23, 2026, 03:42:56 EDT**. InternalPromptForCheckoutAndSave began at 07:42:53.863 UTC and completed at 07:42:56.859 UTC. The log then reports validation of 17 assets. Earlier /Temp/Autosaves entries were not counted as production saves.

The native menu's successful completion alone is not used as proof: dirty flags, exact changed file set, new hashes and unchanged geometry were checked separately.

## 6. User save confirmation

The user reported: “ok i saved”.

Independent verification completed at approximately 07:44:37 UTC / 03:44:37 EDT. The same Editor/session remains authenticated. All 17 formerly dirty production packages are absent from the complete dirty snapshot. Only /Script/SlateCore and /Script/UnrealEd remain dirty, both with verified compiled-in engine-script provenance. No save/retry/recovery was executed by Codex.

The saved state is verified. A disk reload is a separate pending gate.

## 7. Files saved and their new hashes

The exact 17 authorized source files below changed. All remain existing files at their original package paths. The complete 1,530-file Content comparison is recorded in [post_manual_save_file_audit.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/post_manual_save_file_audit.json). The manual save log excerpt is retained in [manual_save_log_excerpt.txt](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/manual_save_log_excerpt.txt).

| Production file relative to project | Before SHA-256 | Saved SHA-256 | Saved bytes |
|---|---|---|---:|
| Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | b1723d1612763c695d0e44350f09c6fc7320d70874250f33e133ec94cde42e18 | d20bbabd9348f33da4cde8ea191441e056a6ab61ad87f7dc20c5cba2f8c09648 | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | 657a427271aec851ad11a67a803ed5878dc7d27897b0c2e80c89f4d93ce901a9 | da77c755966f750cbe01066bb91006e2733404b3b2885dd60704d723630f7e40 | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | bb3b860c59337346e0b3652bb8cb59f43400fecc4c44978b22d54f278351a349 | 8a2aa140b59129b18a7d2d1965e3e0bc6a33c8087721664c1925ff7c9f8b5085 | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | a5e237cb4388b97bc8f2c7c45d2ef5bb12660367801a726823af94113f97fa52 | c4d976aa9638a875e0401b82381428183fb6da6e03a775d4c4f968aeb4811bde | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | 5c03c5062b24b57484d346716e4aea2bc966b53fc4c18b8087d0722498e74370 | 27c4bffd7f2b591e2d7d17057f22d7c3e66367f09f335d142b763a6114a4a8e3 | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | 2c98d9cf71b8b4fd3f96601682accbf6c94d092009d8f2537cc89cb948de3196 | 63e27e7f4dcae619b75167b7cff3b9502244bfc0e8f34e95482630ee391d9dd5 | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | 3fd31f6720d7496fe7dea83c143f668da7578c10a8e72573577cdab5c7670a03 | c9d384eaf542843f58d47be61e7eaad5441def9c393b3d36ef171dcca5812aa6 | 606396 |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | e056f875f94ec1018637cb4f73902731c737a6544cc3c6a15aff1cf83389677c | eb5d5640126d4fc446968460e9a868eeb2b76e358e4c0af81191f583a6b6d302 | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | f435931234858e22eea465630b9975cc70f12c8baa83083363c7260712100050 | f9334c293ab70285e9a3d2388bc201badf5666e421b9d11d220a30c2cc707d74 | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | 8285ba3c3d98bd7db6e165e7d5f2835f771bd545dc354bb583877031924cff19 | 3250d0d5fea2d9c8bba0c85f9450102a1043328ce176d1d26cc210287076a0ea | 606643 |
| Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | f6085afb66af8e30804affe5e6531db7500d7a6ccefab548b2b0578b4d091a5f | d3db141665a4c53d681f8f680498bd9a8847f88d46696d14c80214ee87f2d667 | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | fb7c9674915a6351bd8c9c9e2ffae4715431ebca231a702ef3e9e041ecf33626 | eb15fba135162b01b7c9cf8a6aade0d08ea6d386ccdb5d813a239033f5dba7da | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | b0778b3a47349c4d4ff6425d4df7ae5ffd525d7757bd56f32fd2f5738ca38fb7 | 9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df | 5063 |
| Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | 3d294c102d7f35d2202c37045970ca0942799a6cbc0100aeab73e915ff690139 | 28f33026e840869101fbf2ed685dfe9abac79ab2d954346a07b3ce8d6ea6ec40 | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | 020bc5d773d98e83dbe6c9753deb6be9aa7c4dd48497b26364483ea48edabeaa | 72f10193d9464cd42a753c89cf2025c3814546dfab2ec8bea514ed58b80a8bc8 | 606600 |
| Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | 193b0a56a14033c3e28a12a44fa64773f64ca6e39987fcaa7cf5ec3a9490fb93 | d8c8e5a8a37fdea12f84fdd9c376ff47ef41df78d82184aca3972c419d4113fc | 606716 |
| Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | 2f55b75143e371bff56d8b69c68584cf6b775b29b67c6ccc31a2fd25a103d5c9 | d83fe4569343373a8e1dac33b3176d650bbcfe422e6d7fd601273569e607a8a3 | 606716 |

All 17 new SHA-256 values were read from production disk files after the user's save. Exactly those 17 names appear in the log's production package output records. No unexpected file additions/deletions or unauthorized Content changes were observed.

## 8. Landscape integrity after saving

Native after-save inspection confirms:

| Gate | Result |
|---|---|
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D, unchanged |
| Original layer GUID | 198824024FF8A77A01535B86021D9B34, unchanged |
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B, unchanged |
| Both layers | Visible and unlocked |
| Original full-height checksum | 9f43572fbc2c06ef497da015879cdb23, unchanged |
| ForgeTerrain full-height checksum | 9f43572fbc2c06ef497da015879cdb23, unchanged |
| Both layer dimensions | 2041 x 2041 |
| Both layer minimum/maximum elevations | 0 cm / 0 cm |
| Loaded / unloaded streaming proxies | 16 / 0 |
| Registered terrain / collision components | 64 / 64 |
| Layers up to date | true |
| Dirty production packages in complete snapshot | Zero |

Full after-save layer records:

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

The original layer and all 16 proxy identity/component records are exactly equal to the pre-save records. Native full layer checksums and the preceding setup's all-samples neutral validation establish no observed terrain-height changes.

No distinct full composed-height export or independent visual/PIE/collision-performance test was performed. Unchanged original layer plus neutral ForgeTerrain supports unchanged flat composition; this is separate from the still-pending disk-reload proof.

## 9. Reload verification

**Not performed. Verdict remains SAVED — RELOAD VERIFICATION PENDING.**

The required production packages are saved and clean. However, no supported exposed route was established that both forces an actual disk reread of this adopted production World Partition level and meets the task's safeguards.

- unreal_open_asset uses Asset.GetAsset followed by UAssetEditorSubsystem::OpenEditorForAsset. Opening an already-loaded map does not establish a disk reread.
- Landscape reload is guarded for supported test/authorized worlds. The existing setup_layer grant is consumed and does not permit reload; no new grant or bypass is allowed.
- No general package/production-level reload tool is advertised.
- The native Editor has map loading APIs, but raw API availability is not proof that a specific exposed operation safely reloads the current World Partition map while protecting unrelated work. No unrestricted script or forced unload/load was substituted.

The two dirty compiled-in script packages were not cleared or altered. The Editor remains open. No reload, level close, engine restart or restore was attempted. A later safely supported disk reload and repeat layer/height/proxy checks are required before using PASS — ADOPTION SAVED AND PERSISTENCE VERIFIED.

## 10. Remaining risks and evidence

The requested save is independently verified; reload persistence is the remaining acceptance gate. This report does not equate saved bytes plus current in-memory readback with a successful reopen.

The previously recorded Config/DefaultEditorPerProjectUserSettings.ini drift relative to Stage 1 was preserved. It and all other recorded supplemental current files retained identical hashes across the manual-save audit. Codex did not edit, restore or attribute that drift.

Both recovery checkpoints remain intact. No automatic restore occurred. They remain scoped recovery on the same G: storage volume, not a full independent project archive.

Evidence:

- [Pre-save native evidence and checkpoint audit](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/pre_save_evidence.json).
- [Full Content pre-save hash baseline](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/production_content_before_manual_save.json).
- [After-save file/hash audit](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/post_manual_save_file_audit.json).
- [After-save native Landscape and dirty-package responses](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/post_manual_save_native_evidence.json).
- [Manual-save log excerpt](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/manual_save_log_excerpt.txt).
- [Preserved pre-save Stage 2C report](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/stage2c_report_before_manual_save.md).
- [Numbered native source trace](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2C_Evidence_20261023T0739/native_save_source_evidence.txt).

No adoption repeat, duplicate ForgeTerrain, sculpting, heightmap generation, coastline/road/building generation, World Partition reconfiguration, HLOD build, Ultra Dynamic Sky edit, plugin rebuild, engine restart, backup restoration or Stage 3 work occurred.

## 11. Final verdict

**SAVED — RELOAD VERIFICATION PENDING**

The user's native save persisted exactly the 17 authorized Landscape package files, all 17 production dirty flags cleared, and every new SHA-256 is recorded. Across the complete project Content baseline, no unrelated file changed and no file was added/deleted. Original and ForgeTerrain layer records, full height checksum, Landscape identity and all 16 proxy/component records remain unchanged.

The Editor is left running. The blocked save adapter was never executed. No reload proof is claimed, and no automatic recovery or further terrain operation will follow this report.

