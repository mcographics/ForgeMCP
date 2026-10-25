# ForgeMCP Landscape Adoption — Stage 2 Report

Date: October 23, 2026  
Status: Native setup completed and verified in memory; saving is explicitly deferred.  
Verdict: **ADOPTION VERIFIED — SAVE PENDING**

## 1. Executive summary

The existing human-approved setup_layer grant 6025F70A4D50AAA3EE2CCBB7ADD0C0EF was verified live as approved, unused, unrevoked and unexpired. Before mutation, ForgeTerrain was absent and all production Landscape packages were clean, demonstrating that setup had not already executed. The native approval-generated 23-file world/external-package checkpoint was independently hash-verified against both its MD5 manifest and the Stage 1 SHA-256 baseline.

One reviewed native setup preview was applied exactly once. It returned completed_unsaved, original_layer_heights_unchanged=true, new_layer_neutral_verified=true and saved=false. ForgeTerrain now exists, is visible and unlocked. Original Layer readback and all 16 streaming-proxy identities/components remain unchanged.

The operation stops before saving, as required by the latest instruction. No sculpting, terrain generation, additional adoption request, automatic recovery, production save, reload, restart or rebuild occurred. The grant is now used=true and must not be replayed.

Full evidence: [native_evidence.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2_Evidence_20261023T0712/native_evidence.json). The prior interim report is preserved at [previous_stage2_report.md](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2_Evidence_20261023T0712/previous_stage2_report.md).

## 2. Authenticated Editor/session identity

Fresh session discovery confirmed one connected Unreal Editor: unreal-22604 / PID 22604, ForgeMCP 0.2.16-alpha.1, UE 5.6.1. Authenticated project identity:

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

Landscape actor: /Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295  
Landscape GUID: BD45FDD94EC2A29617B50794F2DE4E9D  
World Partition enabled; PIE stopped. Production map and identity matched before planning and mutation.

## 3. Native preflight result

Full pre-mutation response:

```json
{
  "ok": true,
  "session_id": "unreal-22604",
  "data": {
    "authorization_origin": "adopted_existing_landscape",
    "session_id": "unreal-22604",
    "editor_pid": 22604,
    "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
    "world_path": "/Game/Levels/L_City_World_Master",
    "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
    "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D",
    "world_partition": true,
    "potentially_adoptable": true,
    "readiness_blocker": "",
    "checkpoint_source_clean": true,
    "target_layer_exists": false,
    "target_layer_ready": false,
    "target_layer_locked": false,
    "target_layer_visible": false,
    "requires_layer_setup": true,
    "local_editor_confirmation_required": true,
    "backup_required": true,
    "backup_scope_readable": true,
    "backup_scope_blocker": "",
    "backup_source_file_count": 23,
    "setup_affects_entire_selected_landscape": true,
    "read_only": true,
    "requests": [
      {
        "adoption_id": "6025F70A4D50AAA3EE2CCBB7ADD0C0EF",
        "approved": true,
        "revoked": false,
        "used": false,
        "expires_at_unix": 1792739841,
        "expired": false,
        "backup_root": "G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF",
        "actions": [
          "setup_layer"
        ],
        "region": [
          0,
          0,
          2040,
          2040
        ],
        "checkpoint_files_present": true
      }
    ]
  }
}
```

The same existing adoption ID was approved=true, revoked=false, used=false, expired=false, checkpoint_files_present=true, actions=[setup_layer], region=[0,0,2040,2040]. No new adoption request was issued.

Post-setup native response:

```json
{
  "ok": true,
  "session_id": "unreal-22604",
  "data": {
    "authorization_origin": "adopted_existing_landscape",
    "session_id": "unreal-22604",
    "editor_pid": 22604,
    "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
    "world_path": "/Game/Levels/L_City_World_Master",
    "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
    "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D",
    "world_partition": true,
    "potentially_adoptable": true,
    "readiness_blocker": "",
    "checkpoint_source_clean": false,
    "target_layer_exists": true,
    "target_layer_ready": true,
    "target_layer_locked": false,
    "target_layer_visible": true,
    "requires_layer_setup": false,
    "local_editor_confirmation_required": true,
    "backup_required": true,
    "backup_scope_readable": true,
    "backup_scope_blocker": "",
    "backup_source_file_count": 23,
    "setup_affects_entire_selected_landscape": true,
    "read_only": true,
    "requests": [
      {
        "adoption_id": "6025F70A4D50AAA3EE2CCBB7ADD0C0EF",
        "approved": true,
        "revoked": false,
        "used": true,
        "expires_at_unix": 1792739841,
        "expired": false,
        "backup_root": "G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF",
        "actions": [
          "setup_layer"
        ],
        "region": [
          0,
          0,
          2040,
          2040
        ],
        "checkpoint_files_present": true
      }
    ]
  }
}
```

target_layer_ready=true confirms usable layer preparation. checkpoint_source_clean=false is expected after unsaved production package edits; it is not a missing checkpoint. The native checkpoint still exists and the grant is consumed. Generic inspection's mutation_supported=false is not a promise of unrestricted editing: future editing still requires a fresh bounded authorization and appropriate clean/saved state.

## 4. Adoption request ID and confirmation outcome

Existing approval ID: 6025F70A4D50AAA3EE2CCBB7ADD0C0EF. No replacement request or approval was created by Codex.

Current project log records:

- 07:07:17.864 UTC: local command Forge.Landscape.ApproveAdoption 6025F70A4D50AAA3EE2CCBB7ADD0C0EF.
- 07:07:21.697 UTC: native 'Landscape adoption approved for one operation' log.
- Native preflight independently confirms the approved state and checkpoint.

Grant expiry: Unix 1792739841, October 23, 2026 07:17:21 UTC / 03:17:21 EDT. It was active when preview/apply occurred. After application used=true; it cannot authorize another operation.

The first preview invocation was rejected before dispatch because the typed MCP schema accepts lowercase hexadecimal adoption_id while native returned uppercase. The same ID was normalized to lowercase for the subsequent valid preview. This was not a new grant. Native lookup accepted it. No failed mutation or duplicate apply occurred.

## 5. Exact adoption operation executed

Setup preview request:

```json
{
  "session_id": "unreal-22604",
  "request": {
    "action": "setup_layer",
    "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
    "adoption_id": "6025f70a4d50aaa3ee2ccbb7add0c0ef",
    "region": [
      "0",
      "0",
      "2040",
      "2040"
    ]
  }
}
```

Reviewed preview:

```json
{
  "ok": true,
  "session_id": "unreal-22604",
  "data": {
    "preview_id": "FE7C70884D5C200096C482B293F0FDBA",
    "apply_allowed": true,
    "preview_read_only": true,
    "effect": "Add dedicated ForgeTerrain; preserve every existing layer. No save."
  }
}
```

The returned preview ID was supplied identically as preview_id and confirmation to unreal_apply_landscape. Full actual apply result:

```json
{
  "ok": true,
  "session_id": "unreal-22604",
  "data": {
    "backup_root": "G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF",
    "original_layer_heights_unchanged": true,
    "new_layer_neutral_verified": true,
    "state": "completed_unsaved",
    "layer_guid": "2E6FC5F94C4EF704F700299B5D08C23B",
    "saved": false
  }
}
```

The operation adds a neutral edit layer actor-wide over the selected 2041 x 2041 Landscape and all its proxies. No heights were sculpted/generated. This was a synchronous completed_unsaved response, not a terrain job requiring replay or polling. Only one apply was executed.

## 6. ForgeTerrain layer state

ForgeTerrain GUID: 2E6FC5F94C4EF704F700299B5D08C23B. Native readback reports visible=true, locked=false, height_read_supported=true, dimensions 2041 x 2041, min/max 0 cm and height checksum 9f43572fbc2c06ef497da015879cdb23. Post-preflight reports target_layer_exists=true, target_layer_ready=true and requires_layer_setup=false.

## 7. Original layer preservation results

The original Layer remains available with GUID 198824024FF8A77A01535B86021D9B34, visible=true and locked=false. Its complete reported layer record is identical before and after setup, including checksum, dimensions and elevation range. Native apply also independently returned original_layer_heights_unchanged=true.

Before:

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
  }
]
```

After:

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


## 8. Height checksum and geometry comparison

Original complete layer-height checksum before/after: **9f43572fbc2c06ef497da015879cdb23**, unchanged from Stage 1. The new ForgeTerrain full-height checksum is also identical because it is neutral across the same 2041 x 2041 extent. Native apply checked all new layer values for neutral encoded height 32768 and returned new_layer_neutral_verified=true.

Both layers have minimum/maximum 0 cm / 0 cm. Verification uses full native height-array hashes and native neutral-value validation, not extrema alone. There was no checksum representation change or unexplained height delta. These results establish preservation of original layer geometry and neutral setup at the native data gate. A separate visual/PIE/collision-performance acceptance test was not performed; no such result is claimed.

## 9. Streaming proxy verification

All 16 before/after streaming-proxy records were compared by actor GUID, actor soft path, Landscape GUID, actor package, component count, collision component count, loaded state and active-world ownership. All compared values match.

- Streaming proxies: 16 loaded / zero unloaded before and after.
- Registered Landscape components: 64 before and after.
- Registered collision components: 64 before and after.
- Total proxy count including root: 17.
- Landscape GUID unchanged.
- World Partition configuration unchanged by the operation.
- Native file namespace membership unchanged; no new map/external package file created.

There is no evidence of a new unrelated production actor or asset: the dirty content set resolves exactly to the existing Landscape root and its 16 existing streaming proxies, and none is classified newly created. No general before/after inventory of every actor or unrelated asset was captured; the verified claim is bounded to the inspected Landscape topology, exact dirty package ownership and production recovery namespace.

## 10. Production files modified and saved

**In-memory production modifications:** exactly 17 existing external actor packages: the Landscape root plus all 16 streaming proxies. The complete dirty inventory was collected in one page (19 records), with inventory_complete=true, no truncation and no inspection errors. Every dirty production package has resolved active-level actor ownership and is included in the 23-file recovery checkpoint.

**On-disk production package writes:** none observed. All 23 native recovery-scope files retain their Stage 1 SHA-256 hashes. Native namespace file membership remains unchanged (23 files, no added/missing files). No save tool was invoked. The world package itself reports dirty=false because the edited actors are externally packaged; this must not be confused with a fully clean production state.

| Dirty production package | Owner | Disk source file | State |
|---|---|---|---|
| /Game/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT | Landscape root | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8 | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | Dirty in memory; original disk SHA-256 unchanged |
| /Game/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U | Landscape streaming proxy | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | Dirty in memory; original disk SHA-256 unchanged |

Additional dirty loaded packages: /Script/SlateCore (pre-existing) and /Script/UnrealEd (newly observed after setup). Native inspection classifies both as compiled-in engine_script with engine_script_provenance_verified=true, not production content; neither is a production save target. The inventory does not determine the exact cause of UnrealEd's dirty flag.

Supplemental metadata drift was detected during the final audit: Config/DefaultEditorPerProjectUserSettings.ini differs from its Stage 1 copy. The changed settings are CameraSpeed (8 to 7), +DecimalGridIntervals, EditorViews and +PerInstanceSettings. This is editor preference/view state, not Landscape geometry or a production asset package. Its timing/cause relative to local user activity or the native setup is not established by the available evidence. Codex did not write or restore it. Eight of nine supplemental files still match Stage 1.

Settings file Stage 1 SHA-256: 69e2efc1894343b1c969d2306668202a8f120b41913e17af82842821a19ccb4d  
Current SHA-256: 51fb4fa5d62915034c142c4037f139e231986dd50e3bc42dde7d60bdd623bbdc

Evidence retains the [complete source hash audit](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2_Evidence_20261023T0712/source_hash_audit.json), [settings diff](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2_Evidence_20261023T0712/editor_settings_diff.txt), and a copy of the current settings file. The Stage 1 checkpoint was not changed. No claim is made that every unrelated project file remained byte-identical.

## 11. Persistence/reload verification

**SAVE PENDING.** No production save or reload was executed. The current adopted state exists only in Editor memory; disk packages still contain the pre-setup state. No persistence or reopen success is claimed.

Remaining requirements, subject to new save authorization:

1. Reauthenticate the current project/level and revalidate layers, heights, proxy identity and exact dirty package ownership.
2. Retain both recovery checkpoints and recheck original source bytes. Do not treat the consumed setup_layer grant as a save grant.
3. Establish a supported scoped save route that targets only the 17 verified Landscape-owned external packages and any world-package write demonstrably required by that route. Exclude engine script packages, editor settings and unrelated actors/assets. Do not invoke Save All.
4. Audit exact package file writes, sidecar creation, unchanged unrelated recovery files, heights and layer readiness after saving.
5. Use a safe supported reopen/reload only after ensuring no unrelated unsaved work can be discarded. Do not force reload or restart the Editor. If unavailable, explicitly retain persistence verification as incomplete.
6. Revalidate both layer identities/visibility/locks, original-height checksum, neutral ForgeTerrain, proxy identity/component counts and clean saved package state after reload.

This report identifies the actual current dirty package set; it does not claim a save route has been executed or proven available for adopted Landscape state.

## 12. Recovery checkpoint reference

External Stage 1 checkpoint, unchanged:
G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892

Native approval-generated checkpoint:
G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF

Before accepting mutation, all 23 native checkpoint files were read and verified against the native manifest MD5 values, current source MD5 values and external Stage 1 SHA-256 values. The exact native file set matches the Stage 1 scope (map plus all external actor/object namespace files). Checkpoint identity matches project world, actor and Landscape GUID. The manifest exists and native preflight reports checkpoint_files_present=true.

Native manifest SHA-256: e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f  
Native manifest MD5: 0193109f3cacfb2df7816fe99be834c8

Per-file checkpoint hash evidence is preserved in native_evidence.json. Native apply also enforces its own manifest integrity, file membership and source hash checks before creating the layer.

Recovery mapping: native checkpoint before/<project-relative path> to G:/ForgeMCP/<project-relative path>. No automatic restore occurred or is authorized. Preserve failed state and request recovery review if later validation fails. Never restore over loaded production packages. The Stage 1 documented isolated copy reconstruction provides byte/path recovery evidence, not a previously proven live Unreal restore/reopen.

## 13. Outstanding risks or blockers

- Saving and reload persistence are pending by explicit instruction.
- The setup grant is consumed. No further operation may reuse it.
- Generic mutation_supported=false remains in Landscape inspection; target_layer_ready=true and successful scoped setup do not authorize arbitrary operations.
- Current production modifications are unsaved in-memory external actor packages. Do not discard or save them inadvertently.
- Supplemental editor-settings drift is documented and retained without alteration; its causal attribution is unknown.
- No standalone composed-height export, interactive visual test, PIE run or performance test was performed. Native complete original-layer hash preservation, full new-layer neutral validation and proxy topology/readiness checks passed.
- The external recovery checkpoint is on the same G: storage volume and is not a complete project/dependency archive.
- No plugin source/configuration change, rebuild or connection repair was attempted for the uppercase/lowercase schema mismatch; normalization used the existing grant successfully.

## 14. Final verdict

**ADOPTION VERIFIED — SAVE PENDING**

The existing approval was valid and unused; the promised full native recovery checkpoint was independently verified before mutation. Exactly one authorized native setup completed unsaved. ForgeTerrain is ready, visible and unlocked. The original Layer and full height checksum are preserved. All 16 streaming proxies and 64 registered terrain/collision components remain intact. Dirty production package ownership is limited to the expected 17 Landscape-owned external packages, whose disk bytes remain unchanged.

The operation stops here before saving, reload or further adoption/terrain work. This is native in-memory adoption verification; saved persistence remains unverified.

## Stage 2B follow-up — October 23, 2026, approximately 03:25 EDT

**SAVE BLOCKED — SCOPED CAPABILITY UNAVAILABLE**

Fresh Stage 2B authentication and readback confirm that the adopted in-memory layer state above is unchanged. Both checkpoints were independently reverified; the current dirty production scope remains exactly the Landscape root and its 16 proxies. A supported current-level save preview identifies exactly those 17 will_save=true targets and no deletions.

Apply was deliberately not invoked: ForgeLevels.cpp:651-665 automatically restores/deletes production files when save or verification fails, and the exposed apply schema cannot disable recovery. That conflicts with the user's explicit no-automatic-recovery instruction. No compliant save route was established. No production package save, reload, adoption repeat or restore occurred. All 32 audited current files retained identical hashes across Stage 2B; the previously documented settings drift relative to Stage 1 was preserved without attribution or alteration.

The overall adopted state remains **ADOPTION VERIFIED — SAVE PENDING**; persisted adoption is not claimed. Full Stage 2B findings and before/after checksums are in [ForgeMCP_Landscape_Stage2B_SavePersistence_Report.md](G:/ForgeMCP/Saved/ForgeMCP_Landscape_Stage2B_SavePersistence_Report.md). The prior Stage 2 report is preserved at [stage2_report_before_stage2b.md](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2B_Evidence_20261023/stage2_report_before_stage2b.md). Full Stage 2B native evidence is in [evidence.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2B_Evidence_20261023/evidence.json).


