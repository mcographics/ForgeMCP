# ForgeMCP Landscape Stage 2E — Independent Persistence Acceptance

Date: October 23, 2026  
Final verdict: **BLOCKED — SAFE ISOLATED RELOAD UNAVAILABLE**  
Production status: Saved adoption preserved; production Editor remains running.  
Independent disk-load acceptance: Not established. Neither isolated attempt completed the map load.

## 1. Isolation method and safety verification

Production was freshly rediscovered and authenticated as unreal-22604 / PID 22604, ForgeMCP 0.2.16-alpha.1, UE 5.6.1, G:/ForgeMCP/ForgeMCPDev.uproject, /Game/Levels/L_City_World_Master. PIE was stopped, production content packages were clean, and both layers matched Stage 2C. Production was not closed, restarted, reloaded or saved.

Separate retained workspace:
G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023

Separate test project:
G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/isolated_project/ForgeMCPDev.uproject

1,743 project files totaling **5,093,257,203 bytes** were copied with ordinary independent file creation, not links. Content, Config, Binaries, Plugins, Source and the .uproject were copied. All sources and destinations were hash-checked; each destination had link count 1 and a file identity different from its source. Source-tree file/directory reparse points were rejected. No symlink, junction or hardlink to production assets was used.

Storage was estimated before copying. Approximately 190.56 billion bytes were free, exceeding the budget of twice the copy size plus 2 GiB. RAM inspection showed approximately 19 GiB free before launch. No production Intermediate, Saved, old registration, autosave, adoption grant or user-state tree was copied into the test project.

Each launch used a private ACL-protected registration directory, independent process environment, user directory, LOCALAPPDATA, temp directory, log files and intended DDC directory. The private client was constructed with only that registry root and an explicit child PID/session; no isolated client request could discover production registrations. No credentials/registration tokens are included in the report.

The shared installation is UE 5.6.1 at G:/Program Files/EpicGames/UE_5.6, including installed engine plugins and engine runtime/content. Project-owned files were independent copies. Sharing the engine installation is not sharing writable production project packages.

Test-only configuration adjustments:

- bEnableLoadingInEditor=False in the copied WorldPartitionEditor settings. Official UE source WorldPartition.cpp:741 and 1501-1528 shows this creates a ForceLoadedActors adapter and adds all actor descriptor GUIDs. This was intended to load all spatial proxies without changing map assets or production streaming settings.
- bAutoSaveEnable=False in copied editor settings.
- Copied Content files were marked read-only after copying to prevent test asset saves.
- No native save/apply/adoption/terrain operation was invoked against the test.

Important limitation discovered at runtime: despite UE-LocalDataCachePath pointing into the isolated workspace, the machine registry GlobalDataCachePath overrode it with **F:/TEMP/UnrealCache**, logged as writable. The test therefore did not achieve the claimed private DDC context. The log records cache speed tests/maintenance, including zero files deleted by maintenance. No attempt was made to restore or modify that machine cache setting. It is outside the production project but remains a shared writable cache and a blocker to a fully isolated acceptance claim.

## 2. Test project dependencies and recovery checkpoints

The copy retained the exact project descriptor, project module binaries/metadata, ForgeMCP plugin binaries/content/configuration/source, all 1,530 project Content files, and the six project Config files. Source files were copied as context; no compilation/build ran.

Project descriptor dependencies include MajesticForge, LevelSequenceEditor, GameplayAbilities, Metasound, PluginBrowser, ModelingToolsEditorMode, BlueprintGraphScreenshot, ElectronicNodes, EnhancedInput, ControlRig, AnimationData, FullBodyIK, EngineAssetDefinitions, WorldPartitionHLODUtilities, IKRig and Fab. MajesticForge additionally declares WebBrowserWidget/GameplayAbilities. Installed engine dependencies are provided by the same UE installation that production uses. The map's actor/object namespaces, HLOD assets and project-owned dependencies were included by copying all Content rather than selecting only Landscape packages.

Both original pre-adoption checkpoints were preserved and independently verified before testing:

- G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage1_20261023T065347Z_94ff8892: all 32 backup files match SHA-256.
- G:/ForgeMCP/Saved/ForgeLandscapeAdoption/6025F70A4D50AAA3EE2CCBB7ADD0C0EF: all 23 backup files match native MD5 and Stage 1 SHA-256.

Their original manifest SHA-256 pins remain:
- Stage 1: d9de66d61745427b313c5ee7eb5a1f2238d8c76ca2dc5aa0cd277929bbac3388.
- Native: e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f.

A new independent **post-adoption** recovery checkpoint was created before launching:

G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/post_adoption_checkpoint

It contains the 23 current saved map/external-namespace source files plus nine supplemental project/configuration/HLOD files, with project-relative paths and per-file SHA-256 in manifest.json. The 17 changed saved Landscape packages matched Stage 2C recorded saved hashes before copying. All 32 new checkpoint copies matched their sources.

Post-adoption manifest SHA-256:
c3ec68f538425c600bc10981e0ad519d35371a3920839f2c722b1a3e1b861fc1

Final verification after testing rehashed every one of those 32 sources and checkpoint copies; all match the recorded post-adoption hashes. No original recovery checkpoint was overwritten.

Full runtime dependency resolution was not proven because neither attempt reached a completed map load. The isolated logs contain ACL compression-default asset warnings also present in production startup; these must not be reported as a new Landscape serialization failure.

## 3. Independent disk-load evidence

Two genuinely fresh isolated processes were launched using the copied project, not an in-process opening of the already-loaded production map. All launch command lines and PIDs were recorded before waiting for native inspection.

### Attempt 1: null renderer

- PID 976 / intended session unreal-976.
- Executable: installed UE 5.6.1 UnrealEditor.exe.
- Project argument: isolated project path above.
- Map argument: /Game/Levels/L_City_World_Master.
- Flags included Unattended, NullRHI, NoSplash, NoSound, NoLiveCoding, NoSourceControl, a private UserDir and absolute log.
- Outcome: process exited with code 3 before the map loaded or bridge registered.

At 07:58:05 UTC the engine asserted: Tried to get module interface for unloaded module 'LevelEditor'. The stack identifies UnrealEditor-TedsOutliner.dll, FTedsOutlinerModule::StartupModule. The installed LaunchEngineLoop.cpp guards LevelEditor startup with !GUsingNullRHI, while the enabled Teds Outliner startup requires it. This is a startup-mode incompatibility, not evidence that the saved Landscape failed deserialization.

Evidence: [UnrealEditor.log](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/logs/UnrealEditor.log), [launch.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/launch.json), [isolated_error.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/isolated_error.json).

### Attempt 2: normal renderer, offscreen

- PID 20792 / intended session unreal-20792.
- Same copied project and map argument, unchanged asset bytes/plugin set.
- RenderOffscreen/Windowed 640x480 replaced NullRHI to allow LevelEditor startup.
- No production process restart, plugin disable, rebuild or asset modification was attempted.
- Outcome: the 240-second bounded startup check timed out without a private bridge registration, authenticated project-info response, or completed map initialization.
- Last relevant startup activity included recursive engine default-material package-load messages. The log does not establish a Landscape package load. The precise cause of the stall is unproven.
- The DDC registry override described above was discovered in this attempt; no fully isolated cache result is claimed.

Evidence: [UnrealEditor_rendered.log](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/logs/UnrealEditor_rendered.log), [launch_rendered.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/launch_rendered.json), [isolated_rendered_error.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/isolated_rendered_error.json).

After timeout, only PID 20792 was stopped. Before stopping it, Win32_Process executable and command line were checked against the recorded isolated .uproject path and UE executable; PID 22604 was explicitly excluded. The first test process had exited itself. No production shutdown was requested. Test evidence and copied assets are retained without cleanup.

**No authenticated isolated Landscape inspection result exists.** No composed-height/collision query executed because those were gated on successful isolated identity and all 16 proxies loading. There is no valid claim that saved package bytes were reloaded and accepted by Unreal.

## 4. Original Layer preservation

Production before and after testing shows Original Layer GUID **198824024FF8A77A01535B86021D9B34**, visible=true, locked=false, dimensions 2041 x 2041, full-height checksum **9f43572fbc2c06ef497da015879cdb23**. The complete reported original layer record is unchanged.

This is live production integrity evidence. Independent disk-loaded original-layer acceptance is **unverified** because the isolated map did not finish loading.

## 5. ForgeTerrain persistence

Production before and after testing shows ForgeTerrain GUID **2E6FC5F94C4EF704F700299B5D08C23B**, visible=true, locked=false, dimensions 2041 x 2041 and full-height checksum **9f43572fbc2c06ef497da015879cdb23**, with zero elevation extrema. The current production layer record remains identical to the saved adoption baseline.

The saved package hashes and copied file hashes are verified. Independent deserialization/persistence of ForgeTerrain remains **unverified**. A failed startup is not a lost-layer result and must not be reported as such.

## 6. Height validation

Production original layer and ForgeTerrain both retain minimum/maximum **0 cm / 0 cm** and the expected complete layer-height checksum. The original setup's prior neutral-all-samples validation and Stage 2C save verification remain historical evidence; this stage adds a fresh production readback and disk-hash preservation check.

No isolated layer height array, composed terrain readback, collision sample, visual test or performance result was obtained. The isolated test cannot satisfy the independent height gate.

Final production layer response:

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


## 7. Streaming-proxy integrity

Fresh final production inspection confirms:

- Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D.
- 16 loaded streaming proxies / zero unloaded.
- 17 total proxies including root.
- 64 registered Landscape components.
- 64 registered collision components.
- Same original and ForgeTerrain layer GUIDs.
- World Partition streaming/editor-loading production settings unchanged.

The isolated all-proxy load was intended through test-only ForceLoadedActors configuration, but it was never reached. No isolated proxy identity comparison or World Partition map-initialization acceptance is claimed.

## 8. Production before/after integrity

The production Editor remains running and authenticated as unreal-22604 / PID 22604 in the correct project/map with PIE stopped. Native before/after responses are retained separately:

- [production_before.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/production_before.json).
- [production_after.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/production_after.json).

The 1,743 production files used for the copy were rehashed during the test audit: **zero source changes**. The complete Content namespace had **no new or deleted files**. Every copied Content file still matched its copied source hash; **zero test asset changes**.

After stopping the disposable test process, all 32 post-adoption checkpoint/source files were independently rehashed again and matched exactly, including all 17 saved Landscape packages. This final check is retained in [final_post_save_hash_verification.json](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/final_post_save_hash_verification.json).

Final dirty-package inventory is complete and reports only /Script/SlateCore and /Script/UnrealEd with compiled-in engine-script provenance. **No production content package is dirty.** The map reports dirty=false, layers up to date=true, target_layer_ready=true.

Read-only adoption preflight confirms the same sole existing request/grant ID 6025F70A4D50AAA3EE2CCBB7ADD0C0EF, used=true and now expired=true, with checkpoint_files_present=true. No additional adoption request occurred. Its consumed/expired state was not changed or renewed.

The production Editor was inspected only before and after the isolated attempts. It was not connected through the isolated client or targeted with any mutation. No production save, reload, restart, rebuild, terrain change, layer creation, World Partition change, HLOD operation, Ultra Dynamic Sky edit or automatic restoration occurred.

## 9. Limitations, errors and retained evidence

The file-copy and recovery-checkpoint gates passed. The independent load gate did not:

1. NullRHI is incompatible with the enabled Teds Outliner startup dependency on LevelEditor.
2. The normal offscreen attempt stalled before authenticated map load and timed out.
3. The requested private filesystem DDC path was overridden by a machine registry cache setting. A future test needs a verified cache graph without registry/global overrides before launch, not a production registry/configuration change.
4. Existing ACL compression-default warnings are also present in production; they are logged without assigning them as the cause of the startup stall.
5. No Landscape serialization or layer-loading error was established because no isolated Landscape load was completed. Absence of a completed load is not successful validation.
6. No automated recovery or saved-data repair was attempted. The working production adoption is preserved.

Retained artifacts include:

- [Storage/dependency estimate](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/storage_estimate.json).
- [New post-adoption checkpoint manifest](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/post_adoption_checkpoint/manifest.json).
- [Complete independent-copy file manifest](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/project_copy_manifest.json).
- [Production/test asset audit](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/production_integrity_audit.json).
- [Final saved-source/checkpoint audit](G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023/final_post_save_hash_verification.json).
- Both launch records, startup logs, error records and external helper scripts.

The copied test project is retained for review. It is not represented as a complete successful acceptance environment. Neither failed attempt modified the saved production Landscape or its package bytes.

## 10. Final acceptance verdict

**BLOCKED — SAFE ISOLATED RELOAD UNAVAILABLE**

The successful saved adoption remains intact. A new post-adoption checkpoint is SHA-256 verified. All required production layer/height/proxy and clean-package checks still pass, and saved source hashes remain unchanged.

Independent fresh-process Landscape loading was attempted but not established, so **PASS — LANDSCAPE PERSISTENCE VERIFIED cannot be claimed**. The result is a blocked test environment, not proof of bad Landscape serialization and not a recovery trigger.

The production Editor was never restarted or reloaded. Only disposable isolated processes were started/stopped. The operation ends after this report, with no Stage 3 or further terrain work.

