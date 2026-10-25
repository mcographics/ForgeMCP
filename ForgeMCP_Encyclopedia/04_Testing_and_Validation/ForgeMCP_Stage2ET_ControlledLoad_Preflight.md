# ForgeMCP Stage 2E-T — Resumed Controlled Load Safety Preflight

> Subsequent execution outcome: the owner approved one launch. It timed out at 900 seconds before map acceptance and was stopped without retry. See [Controlled Load Result](ForgeMCP_Stage2ET_ControlledLoad_Result.md). The READY verdict below records the historical prelaunch review, not completed persistence acceptance. No unused launch approval remains.

Date: October 23, 2026  
Current verdict: **READY — REQUEST EXPLICIT OWNER LAUNCH APPROVAL**  
Status: Subsequent final review passed with PIE stopped. No launch authorized or performed.  
Test Editor launches: **0**.

## 1. Production identity and initial clean-state result

Fresh discovery authenticated unreal-22604 / PID 22604, project G:/ForgeMCP/ForgeMCPDev.uproject, level /Game/Levels/L_City_World_Master.L_City_World_Master, UE 5.6.1-44394996+++UE5+Release-5.6 and ForgeMCP 0.2.16-alpha.1. PIE was initially stopped. The complete initial dirty inventory inspected 1,244 loaded packages, with zero dirty production Content, no further pages and no errors. Only compiled-in /Script/SlateCore and /Script/UnrealEd were dirty.

The earlier blocked preflight and subsequent dirty-package recheck were preserved verbatim at G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/historical_blocked_preflight.md before this report was updated.

## 2. Initial Landscape verification

Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D; Original Layer GUID 198824024FF8A77A01535B86021D9B34; ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B. Both layers exist, visible and unlocked, dimensions 2041 × 2041, full-height MD5 9f43572fbc2c06ef497da015879cdb23, and min/max 0 cm / 0 cm. Loaded/unloaded streaming proxies 16/0; registered terrain/collision components 64/64. Landscape dirty=false. This establishes unchanged reported layer data and neutrality against the known neutral checksum; no separate composed-height/collision runtime test was performed.

Read-only adoption preflight reports checkpoint_source_clean=true, target_layer_ready=true, requires_layer_setup=false. The sole old approval remains used and expired. No new request or terrain operation was dispatched. These responses do not enumerate every possible terrain job; no global operation-history assertion is claimed.

## 3. Current disk audit and owner-authorized saves

The complete recorded project dependency scope was rehashed: Content, Config, Binaries, Plugins, Source and ForgeMCPDev.uproject, 1,743 files. Comparison uses the historical full-copy baseline updated with the verified post-adoption checkpoint. Exactly three files changed, no files were added or deleted. All three map to the actor ownership established by the earlier native dirty inventory and the owner's explicit confirmation of moving and saving those actors. Package identities and file paths remain the same. No claim of a property-by-property binary asset diff is made.

| Owner / package suffix under Content/__ExternalActors__/Levels/L_City_World_Master | Previous SHA-256 | Current SHA-256 |
|---|---|---|
| Ultra Dynamic Sky — C/AE/BK2M8Y8Y4ILGBJFC22SJCA.uasset | ac20b0491ad334c5378cf31539eb8b0e0aa5f9ded4948895e3e11e80cbff1b73 | 6a50ee7ebfa3dfa10d4c1095471224cfa15edd7728d2761d520d0210d1fbf77d |
| PlayerStart — F/26/359XHJOPQAURYFVANTMBAM.uasset | ef10150379d4c9d0712a9c5b93e7e3cbaded6d6074af0c7fb6afffa54e853171 | 47817d2b3c8fa498bbd861538ca489a5b1a0f401f316fcc41e27f80a8f31832f |
| Ultra Dynamic Weather — 9/UX/QWIT4Q5JJ8585ENBY5400I.uasset | 56eb7009ed2654e55259cc1e6213045f582aa9feb8f0e314801b83a9b8418844 | 2ddcb1931436e94b06fa4b668186c3ac6bf6b50aefa2e7e1a049d76a54803591 |

Separate current-state baseline: Stage2ER_01/current_state_baseline.json. No original manifest was overwritten. All 17 saved Landscape package hashes remain unchanged. The audit excludes generated Saved/Intermediate, logs and repository tooling; it is not an entire-drive audit.

## 4. Recovery checkpoint integrity

All three original manifest SHA-256 pins match: Stage 1 d9de66d61745427b313c5ee7eb5a1f2238d8c76ca2dc5aa0cd277929bbac3388; native e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f; post-adoption c3ec68f538425c600bc10981e0ad519d35371a3920839f2c722b1a3e1b861fc1.

Verified all 32 Stage 1 backups, all 23 native backups against SHA-256 and native MD5, and all 32 post-adoption backups. Current post-checkpoint sources match except the three explicitly authorized actor saves. No checkpoint was changed or restored. Verification is implemented in Saved/stage2et_prepare_current_clone.py; successful preparation evidence is retained separately.

## 5. Independent clone verification

New project: G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject.

Ordinary independent byte copies: 1,743 files, 5,093,257,926 source bytes. Free storage before copying: 185,443,176,448 bytes, exceeding twice the copy size plus 2 GiB. Approximate free physical RAM during preparation: 21.46 GiB. All copied files matched source hashes, link counts were one, and source/destination file identities differed. Source paths and clone paths were checked for reparse points. No symlinks, junctions or hardlinks were used. All original source hashes were rechecked after copying and remained unchanged during preparation.

Independent Saved, Intermediate, user, localappdata, logs, temp, private registry and DDC directories exist. Content is marked read-only; copied-only settings disable autosave and Live Coding, and disable editor spatial loading to load all proxy descriptors. Only two copied configuration files differ from the current-state source baseline. Before/after configuration clone manifests record exact hashes. Production configuration was not modified.

All project Content and dependency roots were copied. The 16 enabled project plugin descriptors and WebBrowserWidget dependency are available. Project and Forge plugin module DLLs exist, and their Build IDs match installed engine BuildId 43139311. EngineAssociation is 5.6. Shared installed engine runtime/content is required; no writable production project asset is referenced through project mount/configuration settings found in the inspected scope. Actual map dependency loading remains unverified until a fresh Editor loads it.

## 6. Private DDC static checks

The clone DefaultEngine.ini contains Stage2ERPrivateDDC, InstalledDerivedDataBackendGraph and DerivedDataBackendGraph with identical reachable topology: Root → read-only EngineReadPak plus Stage2ERLocal. The only writable node has literal path G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc and ReadOnly=false, DeleteOnly=false, Clean=false, Flush=false. It omits EnvPathOverride, CommandLineOverride, EditorOverrideSetting and RedirectionFileName. No reachable Shared, Zen, Cloud or WritePak node exists.

Installed DerivedDataBackends.cpp and FileSystemCacheStore.cpp reconfirm selection, fallback and override precedence; ConfigHierarchy.h and WindowsPlatformProcess.cpp establish later configuration candidates and known-folder behavior. Scanned clone/plugin, platform and applicable user/system configuration candidates contain no conflicting graph sections. Known-folder APIs are not assumed redirected by LOCALAPPDATA. The registry was not changed. Private registration ACL grants current owner and SYSTEM. Static graph checks pass; runtime graph selection and absence of shared writes are explicitly unverified.

## 7. Exact proposed launch command — NOT EXECUTED

```text
"G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe" "G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -Unattended -SCCProvider=None -DDC=Stage2ERPrivateDDC -UserDir="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/user" -abslog="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/logs/UnrealEditor.log"
```

This is the Stage 2E-R ordinary rendered proposal: no NullRHI or RenderOffscreen. Future child-only environment must remove inherited FORGE_* values, set FORGE_SESSION_DIR=root/registry, FORGE_UNREAL_SESSION_DIR=root/registry/unreal, LOCALAPPDATA=root/localappdata, TEMP/TMP=root/temp, UE-LocalDataCachePath=root/ddc and UE-SharedDataCachePath=None. Here root means G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01. No global environment change was made.

A later approved launch must retain its Popen handle, executable, PID, creation time, exact project command line and parentage. Maximum runtime 900 seconds, no retry. Reject unexpected writable DDC or graph fallback, build prompts, identity mismatch or fatal error. Termination must revalidate identity and target only that disposable child, explicitly excluding production; retain numeric exit status. Worker handling must use verified descendant ownership. The command is a proposal, not permission to run it.

## 8. Historical PIE blocker and outstanding limitations

Final native dirty inspection returned ok=false, code=pie_active: Dirty package inspection is unavailable while PIE is active. Fresh project_info then confirmed the same production project/map and play_in_editor=true. OS inspection still found only the original production Editor PID 22604. The test launched no Editor and did not start or stop PIE. Its cause is not attributed.

Consequently the final zero-dirty-Content check and post-preparation Landscape readback are pending. No final clean-state assertion is made. Production file hashes passed the copy-stage final rehash, but no later full disk audit after the observed PIE transition is claimed. The prior offscreen startup stall remains unresolved. Runtime DDC isolation, disk-loaded map/layers, proxy registration and composed geometry acceptance remain future gates.

## 9. Evidence and recommendation

Artifacts at G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01:

- historical_blocked_preflight.md — original report preserved.
- current_state_baseline.json — all current dependency hashes and three authorized changes.
- clone_before_config_manifest.json and clone_final_manifest.json — source-copy and prepared-clone hashes.
- preparation_result.json — successful copy/checkpoint/source verification.
- static_safety_review.json — graph, configuration candidates, plugin descriptors and link checks.
- native_preflight_evidence.json — initial production results and final PIE blocker.

Full current disk audit: G:/ForgeMCP/Saved/ForgeMCP_Stage2ET_CurrentDiskAudit.json. Audit/preparation/static-review helpers are retained under Saved. A preparation-helper path-type error was corrected before any clone creation; no Editor launch or automatic retry occurred.

The preceding blocked outcome is historical and superseded by section 10. No production asset save, reload, restart, adoption, sculpt, rebuild, registry change, restoration or Stage 3 action was executed. The first +2 m ForgeTerrain hill remains on hold.

## 10. Final resumed review — October 23, 2026

**READY — REQUEST EXPLICIT OWNER LAUNCH APPROVAL**

The previous PIE-blocked report is preserved at Stage2ER_01/preflight_before_final_resume.md. Fresh discovery and final authentication confirm the original production Editor unreal-22604 / PID 22604 remains running in the correct project/map, PIE stopped. Complete dirty-package inspection again found only the two verified compiled-in engine-script packages and zero dirty production Content packages. Final Landscape records exactly match the fresh initial records from this resumed review: both expected GUIDs/settings/full checksums, neutral 2041 × 2041 layers at 0/0 cm, 16 loaded and zero unloaded proxies, 64/64 components, Landscape clean. The read-only adoption state still contains only the old consumed/expired request. No new operation was issued; the inspection API does not provide a complete global job-history audit.

Fresh full dependency rehash completed at 2026-10-23 13:58:49 EDT: all 1,743 production files match current_state_baseline.json; all 1,743 prepared clone files match clone_final_manifest.json. Zero hash mismatches, additions or deletions. Free disk 180,325,761,024 bytes, approximately 167.94 GiB. The clone was reused without recopying or rewriting its configuration. Owner-authorized differences remain exactly the three documented actor packages; the 17 saved Landscape packages match their post-adoption hashes.

All three recovery manifest pins and all backup hashes were reverified. The raw checkpoint audit reports postadoption_pass=false because it compares current sources to the older checkpoint: the only three source mismatches are precisely the owner-authorized Sky, Weather and PlayerStart saves. Every post-adoption backup matches its original recorded hash. This is an expected baseline distinction, not checkpoint corruption; current_state_baseline.json separately records the authorized newer bytes.

Static DDC/configuration/plugin/link review was rerun successfully, retained as static_safety_review_resume.json. Runtime DDC isolation and actual fresh-process loading remain unverified and must be accepted only from the future child log/native evidence. No guarantee of startup success is made. Project dependencies are independently copied; installed engine runtime/content remains shared as documented above. Known Windows user config reads are not represented as fully isolated OS user state. The source-supported literal DDC graph removes the documented writable cache override hooks.

Additional evidence: final_resume_disk_verification.json and final_resume_native_evidence.json under Stage2ER_01, plus Saved/ForgeMCP_Stage2ET_Resume_Checkpoint_Verification.json. The old original checkpoints and historical test evidence were preserved. No test process was launched; only the original production Editor was observed.

The exact proposed command is section 7, using the prepared clone and child environment specified there. Request owner approval for ONE ordinary rendered isolated Editor launch, maximum 900 seconds, no retries, with identity-checked disposable-child termination. Do not execute until explicit approval arrives. Recheck live production/child identity immediately before any approved launch. No save, restore, terrain operation or Stage 3 action is authorized. Stop after this report.
