# ForgeMCP Stage 2E-T — Approved Isolated Load Result

Date: October 23, 2026  
Final verdict: **BLOCKED — SAFE ISOLATED RELOAD UNAVAILABLE**  
Production status: Saved Landscape intact; original Editor remains running.  
Independent Landscape persistence: **Not established**.

## 1. Authorized execution and isolation

After the completed preflight and the owner's explicit “fine go ahead”, exactly one disposable Unreal Editor was launched from the prepared independent clone at G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject. The historical Stage 2E test environment and all original checkpoints were preserved. No retry, plugin disable, source modification, renderer switch, registry change or rebuild followed.

The clone contains 1,743 independently copied dependency files. Content was read-only, autosave and Live Coding disabled in copied settings, and all-proxy editor loading configured only in the clone. Private Saved/user, temporary, registry, logs and DDC directories were used. Project files are independent copies without symlinks, junctions or hardlinks to production. The installed UE engine runtime/content and read-only cache pak remain shared dependencies. Windows known-folder/global user reads are not represented as a separate OS account or full machine sandbox.

## 2. Exact launch and process identity

```text
"G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe" "G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -Unattended -SCCProvider=None -DDC=Stage2ERPrivateDDC -UserDir="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/user" -abslog="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/logs/UnrealEditor.log"
```

Ordinary rendered startup, no NullRHI or RenderOffscreen. Child PID 28816, intended session unreal-28816. OS creation time Unix 1792778583.3123832, October 23 14:03:03.312 EDT. Parent PID, executable and exact argument list are recorded in launch_approved.json. The Popen handle was retained throughout. A private child environment removed inherited FORGE_* values and selected root/registry/unreal, root/registry, root/localappdata, root/temp and root/ddc as documented in the preflight. Production credentials/approvals were not copied. Native client discovery was restricted to the child's private registry. No production client calls were made during the child run.

## 3. Observed startup milestones

Times below are EDT on October 23, 2026; the child log timestamps are UTC.

| Time | Evidence |
|---|---|
| 14:03:03 | Fresh child process created for isolated .uproject |
| 14:03:11–12 | Core/config/Slate startup; private user Saved configuration path logged |
| By 14:03:19 | D3D12 renderer and shader platform initialized |
| 14:03:20.880 | Installed engine Compressed.ddp opened for reading |
| 14:03:20.936 | Stage2ERLocal reports private root/ddc as Writable |
| 14:03:20.943 | Three local shader workers announced; private shader working paths |
| 14:03:34.378 | FAssetRegistry startup logged |
| 14:03:35 onward | Default engine material imports and texture builds |
| 14:05:20.958 | Private DDC maintenance; zero files deleted |
| 14:08:03–14:09:06 | Missing cached shadermaps explicitly compiling for DefaultPostProcessMaterial, DefaultLightFunctionMaterial, DefaultDeferredDecalMaterial and WorldGridMaterial |
| 14:18:03.341 | 900-second timeout triggered; verified child termination began |
| 14:18:06.008 | Cleanup completed; child exit code 15 retained |

Periodic CPU/memory/log-size and shader-worker identity observations are retained in milestones.json. Worker CPU consumption increased while the main Editor's CPU time largely levelled off later. This is evidence of active workers and logged compilation, not proof of a completed shader queue or target-map progress. The exact remaining startup wait/call stack was not captured.

## 4. Runtime DDC result

The corrected reachable graph worked at runtime: the log reports Stage2ERLocal using G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc as Writable and the installed engine pak opened for reading. No registry override, default-graph fallback, old F:/TEMP/UnrealCache path or other writable DDC backend was observed in the startup log. Custom and both fallback graph definitions were statically fenced before launch. This is runtime selection evidence for the DDC graph; it is not a complete operating-system write trace or a claim that all global user state is isolated.

## 5. Independent disk-load and Landscape acceptance

The 900-second experiment did not obtain a target-map load milestone, target World Partition initialization, Landscape registration, private ForgeMCP registration or authenticated child project/Landscape response. No isolated_native_landscape.json was produced. No completed Teds startup, complete module initialization or completed Editor startup is claimed. No Teds assertion or fatal startup error was observed in this attempt's log.

Consequently the disk-loaded Original Layer GUID, ForgeTerrain GUID, height arrays, proxy identities and 64/64 components were not accepted. No composed-height, collision, visual or runtime validation was possible. Saved package copies and their hashes are verified, but independent Unreal deserialization remains unverified. A startup timeout before the Landscape load does not prove failed Landscape serialization or a lost layer.

## 6. Bounded termination

The controller stopped at 900.031 seconds. Immediately before termination it verified child PID, OS creation time, executable and isolated-project command line and explicitly excluded production PID 22604. psutil terminate was applied only to that disposable child; the retained Popen handle returned code 15. This is a controller termination result, not an engine crash code. Recorded owned shader workers 18208, 32408 and 19768 were terminated only after matching their recorded creation time/executable. A later process inventory confirmed those PIDs and child PID 28816 absent, with original Unreal Editor PID 22604 still present. No broad process-name kill or UI close/save command was used.

## 7. Production before/after integrity

Post-test native authentication confirms unreal-22604, original project G:/ForgeMCP/ForgeMCPDev.uproject, original production map and PIE stopped. Complete dirty inspection finds only compiled-in /Script/SlateCore and /Script/UnrealEd; zero dirty production Content packages. Original Landscape remains clean, with target_layer_ready=true. The sole prior adoption request remains consumed and expired; no additional request was made.

| Production gate after test | Result |
|---|---|
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D |
| Original Layer GUID | 198824024FF8A77A01535B86021D9B34 |
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B |
| Both layers | Visible, unlocked, 2041 × 2041 |
| Both full-height MD5 values | 9f43572fbc2c06ef497da015879cdb23 |
| Both elevation ranges | 0 cm / 0 cm |
| Loaded/unloaded proxies | 16 / 0 |
| Registered terrain/collision components | 64 / 64 |

After child termination, all 1,743 production dependency files matched current_state_baseline.json, and all 1,743 prepared clone files matched clone_final_manifest.json. Zero mismatches, production additions or deletions. This scope covers Content, Config, Binaries, Plugins, Source and .uproject, not generated user/Saved/cache files, engine directories or every repository file. The clone's generated caches/logs/user files are retained without cleanup.

All three original checkpoint manifest pins were reverified after the test. All 32 Stage 1 backups, all 23 native checkpoint backups and all 32 post-adoption backups retain their hashes. Compared with the older post-adoption sources, the only three differences remain the owner's documented Sky, Weather and PlayerStart saves; they match the current-state baseline. All 17 saved Landscape packages retain their post-adoption hashes. No restore or checkpoint modification occurred.

## 8. Evidence and limitations

Evidence root: G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01.

- approved_single_attempt_marker.json and launch_approved.json — one approved launch and process identity.
- run_one_approved_test.py — exact controller, child environment, read-only dispatch and deadline/termination logic.
- logs/UnrealEditor.log — runtime renderer/cache/material milestones; retained without overwrite.
- milestones.json — process/resource observations and log excerpts.
- test_result.json and termination.json — timeout and numeric process exit result.
- post_test_production_native.json — full post-test production identity, layers, topology, dirty inventory and adoption state.
- post_test_disk_verification.json — full dependency hash audit summary against retained per-file manifests.
- Saved/ForgeMCP_Stage2ET_PostTest_Checkpoint_Verification.json — detailed checkpoint backup/source audit.

The private cache correction is validated at the logged graph-selection gate. Shader compilation activity is directly evidenced. Whether cold compilation would eventually complete or another wait is involved is unresolved. No thread stack, complete dependency load, shader completion, independent Landscape readback, composed geometry or persistence acceptance was obtained. No further experiment is authorized by this completed attempt.

## 9. Final verdict

**BLOCKED — SAFE ISOLATED RELOAD UNAVAILABLE**

Exactly one approved isolated attempt was executed and stopped at its deadline. The target Landscape was not loaded and accepted within that budget, so PASS cannot be claimed. Production is still authenticated, clean and unchanged within the verified file/native scope. No production save, reload, restart, rebuild, adoption, sculpt, restoration or Stage 3 operation occurred. The production Editor was never restarted or reloaded. The first +2 m ForgeTerrain hill remains on hold. Stop after reporting; no automatic retry or recovery follows.
