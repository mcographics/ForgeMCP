# ForgeMCP Landscape Adoption — Stage 1 Recovery Checkpoint

Date: October 23, 2026 02:57:33 EDT  
Project: G:/ForgeMCP/ForgeMCPDev.uproject  
Final verdict: **READY TO REQUEST ADOPTION**

## 1. Executive summary

Stage 1 passed. The current authenticated Editor and production Landscape match the requested identity. Both adoption MCP tools are exposed in this Codex session. Read-only setup_layer preflight passed before and after backup. An external checkpoint contains all 23 native backup-scope files and 9 supplemental files; all 32 source/backup/isolated-copy SHA-256 checks passed. All 16 live streaming-proxy package paths are explicitly present in the manifest. Production geometry, layers, dirty state, source bytes, and native-scope file membership are unchanged.

Authorization for this stage was limited to external backup creation, inspection, and this report. No adoption request, approval, grant, edit-layer operation, sculpting, production save, Editor restart, or rebuild occurred. Stage 2 requires new user authorization. This verdict is readiness to request adoption only; no mutation permission is implied.

Checkpoint root: G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892  
Manifest: [manifest.json](<G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/manifest.json>)  
Complete native evidence: [stage1_native_evidence.json](<G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/stage1_native_evidence.json>)  
Final source/backup/isolated verification: [final_verification.json](<G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/final_verification.json>)

## 2. Session and project identity

Fresh forge_list_sessions discovery found exactly one connected Unreal session, unreal-22604 / PID 22604. The previous PID was not assumed. Authenticated unreal_project_info before and after backup returned:


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

Adapter health reports ForgeMCP 0.2.16-alpha.1. The current level is the requested production world, PIE is stopped, and World Partition is enabled. The exact actor path is:


```json
{
  "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
  "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D"
}
```

The actor GUID and Landscape GUID are distinct identities; the Landscape GUID above is the acceptance value.

## 3. Adoption tool discovery

Both tools were discovered from the current Codex tool catalog:

- unreal_landscape_adoption_preflight: reads eligibility, preparation, and local approval state; never approves or writes.
- unreal_request_landscape_adoption: registers a pending local-approval request; available but deliberately never called.

Native session health advertises landscape_adoption_preflight and landscape_adoption_request. The actual documented schema requires session_id plus request fields actor_path, editor_pid, landscape_guid, project_file, world_path, world_partition, region, actions, and optional lifetime_seconds. The exposed region array uses strings, which the typed server converts to integer coordinates. Package world_path uses /Game/Levels/L_City_World_Master, without the object-name suffix.

## 4. Native preflight results

The exact request was:


```json
{
  "session_id": "unreal-22604",
  "request": {
    "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
    "editor_pid": 22604,
    "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D",
    "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
    "world_path": "/Game/Levels/L_City_World_Master",
    "world_partition": true,
    "region": [
      "0",
      "0",
      "2040",
      "2040"
    ],
    "actions": [
      "setup_layer"
    ],
    "lifetime_seconds": 600
  }
}
```

Complete native response before backup:


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
    "requests": []
  }
}
```

Complete native response after backup:


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
    "requests": []
  }
}
```

Both responses pass read_only=true, potentially_adoptable=true, empty readiness_blocker, checkpoint_source_clean=true, backup_scope_readable=true, and requests=[]. The missing ForgeTerrain layer is expected at Stage 1. setup_layer is the inspected eligibility scope; no layer operation was submitted.

## 5. Production Landscape baseline

| Field | Before backup | After backup |
|---|---|---|
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D | Same |
| Vertex dimensions | 2041 x 2041 | Same |
| Loaded / unloaded streaming proxies | 16 / 0 | 16 / 0 |
| Registered Landscape / collision components | 64 / 64 | 64 / 64 |
| World Partition | Enabled | Enabled |
| Dirty | false | false |
| Layers up to date | true | true |
| Original layer | Layer | Layer |
| Original layer GUID | 198824024FF8A77A01535B86021D9B34 | Same |
| Visible / locked | true / false | true / false |
| ForgeTerrain exists | No | No |
| Minimum / maximum local elevation | 0 cm / 0 cm | 0 cm / 0 cm |
| Original-layer height MD5 | 9f43572fbc2c06ef497da015879cdb23 | Same |

The full before/after Landscape responses, including every streaming-proxy descriptor, are retained in stage1_native_evidence.json. This checksum is the native original-layer height readback checksum; file integrity uses separate SHA-256 hashes.

## 6. Backup manifest and verification results

The native preflight exposes backup_source_file_count=23, but does not expose the filenames. The exact disk scope was reconstructed from the current native EnumerateExistingWorldPackageFiles implementation at Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp:927:

1. The map Content/Levels/L_City_World_Master.umap and every same-basename L_City_World_Master.* file in that map directory.
2. Every file recursively under Content/__ExternalActors__/Levels/L_City_World_Master.
3. Every file recursively under Content/__ExternalObjects__/Levels/L_City_World_Master, if present.
4. Canonical path deduplication.

The resulting set contains exactly 23 files: one map and 22 external actor packages. There are no current map sidecars or files in the external-object namespace. All 16 actor_package paths returned by live streaming-proxy descriptors resolve to files in this set. This is a source-derived exact enumeration corroborated by the live native count, rather than a claim that preflight returned a filename list.

Nine supplemental files were also backed up: ForgeMCPDev.uproject, six Config files, and the two existing L_City_World_Master_HLODLayer_* assets. They are not required writes for setup_layer; they preserve project/configuration and map-specific HLOD context. The checkpoint is scoped recovery for this operation, not a complete project/dependency archive.

Free storage before backup: **190,585,929,728 bytes** (177.50 GiB).  
Total source size: **9,832,931 bytes** (9.38 MiB).  
Conservative storage budget checked: **96,607,657 bytes**, covering three source-size copies plus 64 MiB overhead.  
Backup timestamp (UTC): **2026-10-23T06:53:47.278679+00:00**.  
All destinations were created with exclusive creation; no existing backup was overwritten.

Each source was SHA-256 hashed before copying; source size, modification time, and hash were rechecked after copying. Each backup was independently hashed. All files were copied again from backup alone into isolated_recovery_inspection with the same relative paths, rehashed, and checked for equal size. Unreal package tags were read from those isolated .umap/.uasset files; .uproject JSON was parsed and .ini files were decoded. This proves byte readability and isolated path reconstruction. No isolated Editor launch or package deserialization was performed.

The final verification rehashed all 32 production originals, backups, and isolated copies and reconfirmed unchanged source modification times. Native namespace membership was re-enumerated and matched the exact original 23-file set. Results: **32/32 PASS**, including **23/23 native-scope files**.

The table below gives the complete manifest. Every row has backup timestamp 2026-10-23T06:53:47.278679+00:00; the machine-readable manifest repeats the timestamp in every row. N = native 23-file scope; S = supplemental recovery metadata.

| Scope | Original file path | Backup file path | Size (bytes) | SHA-256 | Verification |
|---|---|---|---:|---|---|
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/1/BL/KH23FPCOUY21XYNKZ3FLE3.uasset | 597281 | b1723d1612763c695d0e44350f09c6fc7320d70874250f33e133ec94cde42e18 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/UL/OCMPORF7XIE1QQQWMA573K.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/1/UL/OCMPORF7XIE1QQQWMA573K.uasset | 2511 | b23fc8d558ca82a5bce9e429d2eb4559eac93acd86b6923f7ec626e4941aa613 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/1/X8/EKR3GIKPE95UHYYYPAKDWJ.uasset | 597397 | 657a427271aec851ad11a67a803ed5878dc7d27897b0c2e80c89f4d93ce901a9 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/2/21/FZ0HZ4K6JVBR8GPCMEBET6.uasset | 597397 | bb3b860c59337346e0b3652bb8cb59f43400fecc4c44978b22d54f278351a349 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/2/FW/NV3A49S9QWJLRZE7WI4HMM.uasset | 597397 | a5e237cb4388b97bc8f2c7c45d2ef5bb12660367801a726823af94113f97fa52 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/2/HU/Y8TEYME9MZA2A35BESDWR5.uasset | 597397 | 5c03c5062b24b57484d346716e4aea2bc966b53fc4c18b8087d0722498e74370 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/3/XU/BASWU5RY3VLZL2D2OQDMGF.uasset | 597281 | 2c98d9cf71b8b4fd3f96601682accbf6c94d092009d8f2537cc89cb948de3196 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/5/0C/LCBNMQ13VCDM21M6PIQ3UI.uasset | 597060 | 3fd31f6720d7496fe7dea83c143f668da7578c10a8e72573577cdab5c7670a03 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/5/7U/MOEZ1NFXWRBZY5OR1L0SHU.uasset | 597397 | e056f875f94ec1018637cb4f73902731c737a6544cc3c6a15aff1cf83389677c | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/5/JC/6DJTG5IP7XHZ2LQLRV19GF.uasset | 597281 | f435931234858e22eea465630b9975cc70f12c8baa83083363c7260712100050 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | 597324 | 8285ba3c3d98bd7db6e165e7d5f2835f771bd545dc354bb583877031924cff19 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/5/OP/0WSRWB0C3RJ4GXMQITJQTN.uasset | 597397 | f6085afb66af8e30804affe5e6531db7500d7a6ccefab548b2b0578b4d091a5f | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/8/4Y/DB0D58DF5MS1BQIUSLWMMX.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/8/4Y/DB0D58DF5MS1BQIUSLWMMX.uasset | 2382 | 7602e1ffac5ba1a6322f927f102b082b4207baff2fa3a234cdeeb282a386a416 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/8/D4/6BQXU1WLECGHE78Q5VHPEU.uasset | 597281 | fb7c9674915a6351bd8c9c9e2ffae4715431ebca231a702ef3e9e041ecf33626 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | 4684 | b0778b3a47349c4d4ff6425d4df7ae5ffd525d7757bd56f32fd2f5738ca38fb7 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/UX/QWIT4Q5JJ8585ENBY5400I.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/9/UX/QWIT4Q5JJ8585ENBY5400I.uasset | 38791 | 56eb7009ed2654e55259cc1e6213045f582aa9feb8f0e314801b83a9b8418844 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/9/UZ/96ULHPD3KIG1PGR2F32CHQ.uasset | 597281 | 3d294c102d7f35d2202c37045970ca0942799a6cbc0100aeab73e915ff690139 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/A/BL/DJINWNSGSZTJN5K6P1P8RO.uasset | 597281 | 020bc5d773d98e83dbe6c9753deb6be9aa7c4dd48497b26364483ea48edabeaa | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/C/58/36UIEEB8GTP0SGJ2SO61J8.uasset | 597397 | 193b0a56a14033c3e28a12a44fa64773f64ca6e39987fcaa7cf5ec3a9490fb93 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/C/AE/BK2M8Y8Y4ILGBJFC22SJCA.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/C/AE/BK2M8Y8Y4ILGBJFC22SJCA.uasset | 66345 | ac20b0491ad334c5378cf31539eb8b0e0aa5f9ded4948895e3e11e80cbff1b73 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/E/TO/6QDSBS3BHBP7VVJ6YGFP0U.uasset | 597397 | 2f55b75143e371bff56d8b69c68584cf6b775b29b67c6ccc31a2fd25a103d5c9 | PASS |
| N | G:/ForgeMCP/Content/__ExternalActors__/Levels/L_City_World_Master/F/26/359XHJOPQAURYFVANTMBAM.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/__ExternalActors__/Levels/L_City_World_Master/F/26/359XHJOPQAURYFVANTMBAM.uasset | 4172 | ef10150379d4c9d0712a9c5b93e7e3cbaded6d6074af0c7fb6afffa54e853171 | PASS |
| N | G:/ForgeMCP/Content/Levels/L_City_World_Master.umap | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/Levels/L_City_World_Master.umap | 12995 | ad4218ccbba473aaa4e3c1a18e8df396b5cce0950a3973ad1d3193b58c94b383 | PASS |
| S | G:/ForgeMCP/Config/DefaultEditor.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultEditor.ini | 55093 | d2a0a36c8fad20c9421f8c54178c9b2eabefbf463f464e3d6009686652e394ba | PASS |
| S | G:/ForgeMCP/Config/DefaultEditorPerProjectUserSettings.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultEditorPerProjectUserSettings.ini | 67217 | 69e2efc1894343b1c969d2306668202a8f120b41913e17af82842821a19ccb4d | PASS |
| S | G:/ForgeMCP/Config/DefaultEditorSettings.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultEditorSettings.ini | 1061 | 147fdcc2d1569dfb0d660e2dcf0d58b844a5925b575e558fb72eabe413a35547 | PASS |
| S | G:/ForgeMCP/Config/DefaultEngine.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultEngine.ini | 3099 | 5538e90a4d03e711367f4fad799ada656117b80b34b9f6d560b477045f155774 | PASS |
| S | G:/ForgeMCP/Config/DefaultGame.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultGame.ini | 178 | aff4df784c8136856b2219611f0d656af68a19d24b62d6b2933d867827256fdf | PASS |
| S | G:/ForgeMCP/Config/DefaultInput.ini | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Config/DefaultInput.ini | 10052 | 383de74c165eb3eeedc538d829938287c719c4be18999d5b4c2a31c47a6812b6 | PASS |
| S | G:/ForgeMCP/Content/Levels/L_City_World_Master_HLODLayer_Instanced.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/Levels/L_City_World_Master_HLODLayer_Instanced.uasset | 1841 | 72620f0057cc681f3a589b93c221813aa0ae33a2fb05b762ca99527332ad7bfa | PASS |
| S | G:/ForgeMCP/Content/Levels/L_City_World_Master_HLODLayer_Merged.uasset | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/Content/Levels/L_City_World_Master_HLODLayer_Merged.uasset | 3139 | 41b41231d13dda03318c4742c00c7e8037fc57633544d5f71afb63388e1a792d | PASS |
| S | G:/ForgeMCP/ForgeMCPDev.uproject | G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892/before/ForgeMCPDev.uproject | 2125 | 7f31c36cb98a75afbab8cdcd92c417f7977ad4578a0ad10b7666307e006bcc93 | PASS |

## 7. Adoption mutation-scope assessment

Verified by current source inspection, with recovery coverage checked against live package descriptors and disk enumeration:

- Pending adoption registration would add in-memory request state only. It does not mutate production packages.
- Local approval would create a separate native checkpoint and manifest under Saved/ForgeLandscapeAdoption/<adoption_id>, then activate an in-memory grant. It does not create ForgeTerrain or save production packages.
- A later explicitly authorized setup_layer preview/apply would add ForgeTerrain to the selected Landscape and initialize layer data across the entire selected Landscape. This scope includes all 16 streaming proxies and their 64 components. It is not a small brush operation.
- Native setup uses Target->Modify(), CreateLayer, and layer-content recomposition; it checks preservation of every original layer's heights/name/lock/visibility and checks neutral new height values. Its successful response is completed_unsaved and saved=false. Failure may attempt layer removal; retain the recovery checkpoint regardless.
- Expected serialized ownership is the Landscape root external package and the 16 streaming-proxy external packages, with the world map included conservatively. The 23-file backup additionally preserves the other five external actor packages in the same namespace.
- All current files that the native map/external-package write scope can affect are covered. Existing sidecars would be included by enumeration. A future save could create additional sidecars; these have no pre-operation bytes to back up and must be detected against the manifest and quarantined during a separately authorized recovery. This stage performs no save.
- The two map-specific HLOD-layer packages and project/configuration metadata are backed up additionally. No source evidence indicates that setup_layer needs to modify materials, layer-info assets, plugin binaries, or unrelated shared assets. Those existing dependencies remain in place; this checkpoint is not intended to recreate the entire project on another machine.

Source evidence:

- ForgeLandscapeAdoption.inl:151-251: exact identity, readiness, clean-source, readable-scope checks; preflight returns before request creation.
- ForgeLandscapeAdoption.inl:254-292: local dialog, verified native backup, grant activation, and revocation.
- ForgeLandscape.cpp:893-1080: map/external namespace enumeration, backup and write-scope validation.
- ForgeLandscape.cpp:1558-1626 and 1773-1847: scoped grant checks, setup preview, backup revalidation, actor-wide setup, original-layer preservation and unsaved result.
- UE 5.6 local source LandscapeEditLayers.cpp:13461 onward: CreateLayer owns the edit-layer object under the Landscape; OnLayerCreatedInternal invokes AddLayer for every proxy.
- UE 5.6 local source Landscape.cpp:2626 onward and LandscapeEdit.cpp:8230 onward: default layer height textures are initialized neutrally and owned by the corresponding LandscapeProxy, rather than created in arbitrary standalone asset packages.

Coverage conclusion: the complete current native recovery scope is backed up, plus supplemental metadata. Recovery coverage is established for the bounded adoption/setup workflow against the present project state. Future sculpting, saving, HLOD building, dependency changes, or other operations require their own authorization and scope review.

## 8. Local Editor confirmation requirements

The following is documentation only; none of these steps was executed.

1. With new user authorization, rediscover/revalidate the live session and rerun preflight. Invoke unreal_request_landscape_adoption with the exact PID/project/world/actor/GUID/World Partition identity, full setup_layer region, and setup_layer as the only action.
2. The native request returns adoption_id, state=pending_local_approval, and the exact local_editor_command. A pending request must be approved within 300 seconds.
3. A human in the correct Unreal Editor executes Forge.Landscape.ApproveAdoption <adoption_id> in the local Editor console.
4. The native handler verifies game thread, stopped PIE, unexpired request, exact identity, readiness, and clean source. It opens a modal Yes/No dialog describing the session, project, world, actor, GUID, actions, inclusive region, lifetime, World Partition state, entire-Landscape setup scope, backup, and absence of automatic saving.
5. Only a local Yes response proceeds. Identity/cleanliness are rechecked. The handler creates and hash-verifies its own native full-world/external-package checkpoint, writes a manifest, and then marks the grant approved. The selected lifetime begins at approval; this inspected request used 600 seconds.
6. The external Stage 1 SHA-256 checkpoint does not substitute for the native grant checkpoint. Native validation uses its own MD5 snapshot/manifest and refuses stale source bytes, changed file membership, missing backup files, wrong identity, expired/revoked/used grants, or action/region mismatch.
7. A later separately authorized Landscape preview must carry adoption_id, exact actor, setup_layer action, and full region. Apply requires the reviewed one-use preview confirmation. The grant is consumed for that operation before creation. Setup and sculpt require separate grants/checkpoints; setup does not authorize saving.
8. Forge.Landscape.RevokeAdoption <adoption_id> revokes future use/batches. It does not undo applied changes.

No current adoption request or grant exists. This report contains no usable adoption ID and grants no authorization.

## 9. Recovery/rollback procedure

This procedure is documented for a future recovery authorization; no production restore was attempted.

1. Stop further operations. Do not save the affected world/assets. Record current identity, pending jobs and dirty state. If appropriate and authorized, revoke the actual adoption ID to stop further batches; revocation alone does not roll back.
2. Revalidate the retained manifest and backup SHA-256 hashes. Preserve the failed current files/state in a separate new external incident folder before any restore; do not overwrite this checkpoint.
3. For only unsaved in-memory changes with unchanged disk bytes, an authorized controlled close without saving affected content and reopen may recover the disk baseline. Preserve unrelated user work explicitly before closing.
4. If disk bytes changed, close/unload the Editor cleanly under separate authorization before touching production packages. Never restore packages while Unreal has them loaded.
5. Enumerate the current map/external namespaces using the same scope. Compare with the manifest. Quarantine newly created scope files/sidecars absent from the manifest in an external incident directory so stale post-operation data cannot remain. Do not delete unrelated files.
6. Restore the 23 native-scope files from before/ to their recorded original paths, preserving relative paths and using the complete set together. Supplemental .uproject/Config/HLOD files should be restored only if separately diagnosed as changed and authorized; they are not routine overwrite targets.
7. Verify all restored SHA-256 hashes and exact native file membership before reopening. Reopen the existing project and production map only under the recovery authorization.
8. Rediscover the new session, authenticate, and recheck GUID, 16 loaded/0 unloaded proxies, original visible/unlocked Layer, no ForgeTerrain, 0 cm elevations, checksum 9f43572fbc2c06ef497da015879cdb23, clean production packages, and no active adoption requests. Reload required cells manually/through authorized loading if needed.

Recovery feasibility demonstrated now: all 32 files were independently read from the checkpoint, reconstructed into an isolated directory, size/hash matched, and package signatures/metadata readability checked. This is byte/path recovery verification, not a successful Unreal reopen/deserialization or visual recovery test. Such a live test was not needed to write production files and was not performed.

## 10. Outstanding risks or blockers

No Stage 1 blocker remains.

- This is a point-in-time checkpoint. Any subsequent project/session/content change requires fresh identity, preflight, file-set/hash checks, and a new checkpoint if the sources differ.
- The sole dirty loaded package before and after was /Script/SlateCore, classified by the native inventory as engine_script with verified compiled-in provenance and not associated with the current level. The inventory was complete (1,244 loaded packages); no dirty production content package or unexpected new dirty package was observed. Unloaded packages are not classified as clean by this inventory; their recovery-scope bytes were checked separately.
- An initial dirty-inventory call with limit=100 was rejected by schema validation; the tool limit is 50. A subsequent map-filtered call was also rejected because target_map_path accepts disposable test map paths only. Neither rejected call executed a mutation. The successful calls omitted that optional filter and captured the complete loaded-package inventory before and after backup.
- Native preflight exposes only the backup file count, so the filename list is source-derived using the same deterministic native enumeration, count-checked and cross-checked with all 16 live proxy package paths.
- Current ForgeMCP source and installed UE source establish the mutation-scope assessment; no setup apply, save, recovery restore, rebuild, or live viewport/runtime test was performed.
- The checkpoint is on the same physical G: storage volume as the project. It protects against operation-level content changes, not loss of that storage device.
- Referenced plugins/materials/shared assets and the engine are existing dependencies, not a complete machine-independent project archive. The proposed bounded setup does not write those dependencies.
- External backup/report files and normal Editor telemetry are distinct from production packages. All 23 native source files plus 9 supplemental originals retained identical SHA-256 hashes, sizes, and modification times. This does not claim that unrelated logs or operating-system access metadata never changed.

## 11. Final readiness verdict

**READY TO REQUEST ADOPTION**

| Stage 1 acceptance gate | Result |
|---|---|
| Correct authenticated Editor, project, level, and Landscape GUID | PASS |
| Both actual-chat adoption tools exposed | PASS |
| PIE stopped; 16 loaded and zero unloaded streaming proxies | PASS |
| Native read-only preflight passes before/after backup | PASS |
| Original geometry, height checksum/elevations and layer configuration unchanged | PASS |
| Exact 23-file native recovery scope externally backed up and SHA-256 verified | PASS |
| Additional metadata backed up; all 16 live proxy packages covered | PASS |
| Isolated byte/path recovery inspection passes | PASS |
| Same source file membership and hashes after backup; no unexpected dirty packages | PASS |
| No adoption request/grant, layer edit, sculpt, production save, restart, or rebuild | PASS |
| Stage 1 Markdown report generated | PASS |

The only production-project artifact intentionally created by this stage is this requested Markdown report under Saved. All backup, manifest, evidence and isolated recovery files are outside the production project. The operation ends here. Stage 2 has not started and requires new authorization.
