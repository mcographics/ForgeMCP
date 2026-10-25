# ForgeMCP Stage 2E-R — Isolated Editor Startup Forensics

Date: October 23, 2026  
Verdict: **READY — ONE CONTROLLED ISOLATED LOAD TEST**  
Scope executed: Read-only diagnosis plus this report. No new Editor, configuration change, registry change, rebuild, asset save, reload or restore.

## 1. Executive summary

The first test has a verified immediate failure: Teds Outliner startup obtains an already-loaded LevelEditor module through GetModuleChecked, but LevelEditor was not loaded. The NullRHI attempt exited with status 3 before map acceptance. The available evidence establishes a startup dependency/order incompatibility, not failed Landscape serialization. The exact upstream reason that LevelEditor was absent is not completely established by these logs and source reads.

The second test initialized D3D12/SM6, filesystem DDC, shader worker infrastructure and the asset registry, then stopped advancing through logged main startup milestones around recursive default engine material loads. A DDC maintenance thread later logged activity. The controller timed out after approximately 240 seconds. There is no map-load or authenticated bridge result, no recorded fatal error in that attempt, and no evidence sufficient to assign the stall to DDC, shader compilation, GPU execution, or a specific plugin.

The DDC isolation defect is independently proven and has a source-supported correction. The selected InstalledNoZenLocalFallback graph allows a current-user registry value to override the environment's private local path. Its Local node has no CommandLineOverride key. A custom isolated-only graph with a literal private filesystem path and no override/redirection hooks removes that ambiguity. Both default graph fallbacks must also be fenced to the same private-only topology; otherwise an invalid named graph can silently revert to a shared default.

One ordinary rendered Editor attempt, with no NullRHI or RenderOffscreen and with the graph below, is a justified bounded diagnostic experiment. READY means the proposed safety/configuration review supports that one future test; it does not mean startup success or Landscape persistence has been proven. The unexplained stall remains a live uncertainty.

Production is still authenticated, clean and geometrically unchanged. All 32 post-adoption checkpoint/source pairs, including the 17 saved Landscape packages, match their recorded hashes. No test was executed during Stage 2E-R.

## 2. Evidence reviewed and preservation

Retained Stage 2E root:
G:/ForgeMCP_Recovery_Checkpoints/Landscape_Stage2E_20261023

Reviewed:

- Saved/ForgeMCP_Landscape_Stage2E_Persistence_Acceptance.md.
- launch.json, launch_rendered.json and both isolated error records.
- logs/UnrealEditor.log and logs/UnrealEditor_rendered.log, including RHI, DDC, shader, asset registry, plugin startup and error entries.
- launch_and_inspect.py, launch_and_inspect_rendered.py and prepare_isolated.py.
- project_copy_manifest.json, production_integrity_audit.json, final_post_save_hash_verification.json, and post_adoption_checkpoint/manifest.json.
- Prior Stage 2C saved-package evidence.
- Installed UE 5.6.1 source and BaseEngine.ini.

The retained copy manifest has **1,743 entries / 5,093,257,203 bytes**; all listed copied files remain present. No retained copy, helper, configuration, log, checkpoint or manifest was edited. The post-adoption manifest SHA-256 remains c3ec68f538425c600bc10981e0ad519d35371a3920839f2c722b1a3e1b861fc1.

Process inspection during this investigation found only the existing production UnrealEditor process, PID 22604, with the original project command line. No interrupted helper or isolated Editor was relaunched.

## 3. Attempt 1 — NullRHI timeline and exact launch

Recorded PID: 976. Intended session: unreal-976. Working directory: the retained isolated_project directory. Exact recorded Windows command line:

```text
"G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\isolated_project\ForgeMCPDev.uproject /Game/Levels/L_City_World_Master -Unattended -NullRHI -NoSplash -NoSound -NoLiveCoding -NoSourceControl -ddc=InstalledNoZenLocalFallback -UserDir=G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\user -abslog=G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\logs\UnrealEditor.log
```

| UTC timestamp, October 23 | Observation |
|---|---|
| 07:57:51.897 | launch.json artifact written after Popen returned. This is an artifact timestamp, not a separately captured OS process-creation timestamp. |
| Approximately 07:57:54 | Editor log opened; local log header says 03:57:54 EDT. |
| 07:57:57.271 | Local filesystem DDC selected F:/TEMP/UnrealCache as writable. The first attempt also had the cache-isolation defect. |
| 07:57:57.285 | Shader compiler infrastructure reported three local workers. |
| 07:57:59.844 | FAssetRegistry startup reported completion in 0.0044 seconds. |
| 07:58:03.636–03.644 | World Partition class-descriptor registry initialized. This is not initialization of the target World Partition map. |
| 07:58:04.676 | MetaSound page target initialized. |
| 07:58:05.009 | CEF3 loaded for WebBrowser. |
| 07:58:05.097 | Niagara debugger client initialized. |
| 07:58:05.689 | Assertion: module interface requested for unloaded LevelEditor. |
| 07:58:13.893 | Critical-error call stack emitted; TedsOutliner startup is on the stack. |
| 07:58:13.920 | Engine requested exit with status 3. |
| 07:58:16.186 | Controller error artifact records process exit code 3. |

No ULevel::OnLevelLoaded(L_City_World_Master) or ForgeMCP bridge-ready entry exists in this log. No independent Landscape inspection completed.

## 4. Verified Teds Outliner dependency findings

Installed source root:
G:/Program Files/EpicGames/UE_5.6/Engine

Verified trace:

- Plugins/Experimental/EditorDataStorageFeatures/EditorDataStorageFeatures.uplugin declares TedsOutliner as an Editor module, without an explicit LoadingPhase.
- Source/Runtime/Projects/Public/ModuleDescriptor.h:203 defaults the descriptor loading phase to Default.
- Source/Runtime/Launch/Private/LaunchEngineLoop.cpp:4410 onward loads enabled project/plugin modules through PreDefault, Default and PostDefault phases.
- TedsOutliner/TedsOutliner.Build.cs lists LevelEditor as a private compile/link dependency. A build dependency does not itself prove that StartupModule has already executed for the dependency.
- TedsOutliner/Private/TedsOutlinerModule.cpp:103-109 calls RegisterLevelEditorTedsOutlinerTab during StartupModule.
- The same file:194-196 uses FModuleManager::GetModuleChecked<FLevelEditorModule>("LevelEditor"), rather than LoadModuleChecked.
- Source/Runtime/Core/Public/Modules/ModuleManager.h:333-339 checks IsModuleLoaded and asserts if it is false. It does not load an absent module.
- The actual crash stack names precisely that check and TedsOutliner::StartupModule.

NullRHI is a different engine initialization mode. Source/Runtime/Core/Public/Misc/App.h:400-408 makes FApp::CanEverRender false when nullrhi is present. LaunchEngineLoop.cpp:3142 selects a different Slate renderer for NullRHI, and lines 4204-4207 omit SlateRHIRenderer loading in that mode. Rendering-dependent branches are therefore different.

**Correction to the preceding Stage 2E explanation:** the previously cited !GUsingNullRHI block at LaunchEngineLoop.cpp:4204 loads **SlateRHIRenderer**, not LevelEditor. That block cannot be cited as proof that the engine directly skips LevelEditor there. The logs prove absence at Teds startup, but the complete upstream load-order explanation has not been established. This new report corrects the overstatement without rewriting the preserved evidence.

Ordinary rendered Editor initialization is supported: the production project is currently running under the same installed executable with its normal renderer and plugin set. A proposed normal rendered, non-offscreen child avoids the known NullRHI branch. This is a source-supported test direction, not proof that the next isolated launch will pass Teds startup.

No plugin must be disabled for the first corrected attempt. A future isolated-only disable of the UI-only EditorDataStorageFeatures plugin could be investigated as a separate experiment if the same assertion repeats, after confirming no map class depends on it; it is not part of the approved one-attempt proposal. Do not disable or alter Teds in production, edit engine/plugin source, or rebuild.

## 5. Attempt 2 — Offscreen timeline, status and startup boundary

Recorded PID: 20792. Intended session: unreal-20792. Exact recorded Windows command line:

```text
"G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\isolated_project\ForgeMCPDev.uproject /Game/Levels/L_City_World_Master -Unattended -RenderOffscreen -Windowed -ResX=640 -ResY=480 -NoSplash -NoSound -NoLiveCoding -NoSourceControl -ddc=InstalledNoZenLocalFallback -UserDir=G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\user -abslog=G:\ForgeMCP_Recovery_Checkpoints\Landscape_Stage2E_20261023\logs\UnrealEditor_rendered.log
```

| UTC timestamp, October 23 | Observation |
|---|---|
| 07:58:57.935 | launch_rendered.json artifact written after process launch. |
| Approximately 07:58:58 | Log opened; object subsystem initialized. |
| 07:58:58.968 | Asset discovery cache absent at the private user/Intermediate path; an uncached scan was expected. |
| 07:58:59.674 | Default RHI selected D3D12, SM6. |
| 07:59:00.469–01.195 | RTX 3060 selected; D3D12 device/features and shader-platform metadata initialized. |
| 07:59:01.322 | Target-platform shader-format modules loaded; ray tracing shaders reported enabled. |
| 07:59:01.418–01.673 | Requested fallback graph parsed; engine read-only compressed pak opened; registry override selected shared local cache. ZenShared, named Shared and Cloud were disabled. |
| 07:59:01.674–01.676 | Shader working directories selected, three local workers announced, shader autogen file unchanged. This does not prove ongoing shader job progress. |
| 07:59:06.471 | FAssetRegistry reported startup in 0.0037 seconds. |
| 07:59:06.865 | AssetDataGatherer reported cache-load timing. This is not proof all assets finished gathering. |
| 07:59:07.123–07.158 | Recursive synchronous loads/dynamic imports of Engine default material packages logged; last visible main-startup progress boundary. |
| 08:01:09.154 | Background cache maintenance completed; scanned 4,189 files, deleted zero files. This proves a background thread progressed, not that the main startup thread or map initialization progressed. |
| 08:02:58.612 | Controller artifact records timeout. Approximately 240.677 seconds elapsed since the launch-record write. |
| After timeout | Previous Stage 2E execution verified the child executable/project command line and stopped only PID 20792. Exact termination time and numeric OS exit status were not retained. |

The second error is **a controller timeout**, not an observed engine exit code or a recorded fatal startup exception. No exit status should be invented. The prior controller's Popen object was not retained through the external Stop-Process operation, so the missing numeric exit status cannot be recovered from these artifacts.

No target-map ULevel load, completed target World Partition initialization, bridge registration/readiness or authenticated project-info result exists. Plugin mount messages prove discovery/mounting, not successful completion of every plugin's StartupModule.

Classification: **unresolved startup stall or long wait**, not a verified continuing shader compile and not an identifiable fatal error. Cold initialization, recursive load waiting, rendering/offscreen behavior, module interactions, and DDC requests are hypotheses. There is no captured thread stack/wait-chain or shader-job progress sufficient to select one as the cause. Shared-cache use is an independently proven isolation defect; it is not a proven stall cause. No Landscape serialization diagnosis follows from this attempt.

## 6. Effective DDC graph and override precedence

Authoritative code:

- Source/Developer/DerivedDataCache/Private/DerivedDataBackends.cpp:126-180 selects -DDC=<section>, reads graph definitions from GEngineIni, and falls back to InstalledDerivedDataBackendGraph for an installed build if a requested graph is unusable.
- Source/Runtime/Core/Public/Misc/ConfigHierarchy.h:9-45 defines layered Engine configuration: engine base, project default, platform/generated/custom and later user layers. Project DefaultEngine.ini can override engine graph entries, but later layers must also be inspected for conflicts.
- Source/Developer/DerivedDataCache/Private/FileSystemCacheStore.cpp:3023-3083 applies filesystem path settings in the sequence below.
- Source/Runtime/Core/Private/Windows/WindowsPlatformMisc.cpp:2709-2718 implements GetStoredValue using **HKEY_CURRENT_USER**, not HKEY_LOCAL_MACHINE.

For one filesystem node, later applicable nonempty values win:

| Order | Source | Applicability |
|---:|---|---|
| 1 | Node Path= in merged Engine config | Initial path |
| 2 | Process environment variable | Only if node declares EnvPathOverride=<name> |
| 3 | HKCU stored value | Same declared EnvPathOverride name; overrides the environment |
| 4 | Process command line | Only if node declares CommandLineOverride=<argument> |
| 5 | Editor setting in GEditorSettingsIni | Only if node declares EditorOverrideSetting=<key>; can override the command-line result |
| 6 | ?Name lookup in DerivedDataCacheSettings | Only if the resulting path begins with ?; then path normalization/length validation |

Registry location and read-only verified value:

```text
HKCU\Software\Epic Games\GlobalDataCachePath
Value name: UE-LocalDataCachePath
Value data: F:\TEMP\UnrealCache
```

No registry value was changed. Calling this merely a “machine registry setting” was imprecise; this path is a **current-user registry override**.

The actual selected node in Engine/Config/BaseEngine.ini, InstalledNoZenLocalFallback:

```ini
Local=(Type=FileSystem, UnusedFileAge=34, Path="%ENGINEVERSIONAGNOSTICUSERDIR%DerivedDataCache", EnvPathOverride=UE-LocalDataCachePath, EditorOverrideSetting=LocalDerivedDataCache)
```

It has **no CommandLineOverride=LocalDataCachePath**. Adding -LocalDataCachePath to this unmodified installed node would not be a source-supported fix. Merely setting UE-LocalDataCachePath again also fails because the HKCU value is applied afterward. Even where a node declares a command-line hook, an editor-setting hook is processed later.

The offscreen log:627-631 proves the actual resolution:

1. Environment UE-LocalDataCachePath points into the private workspace.
2. The HKCU-backed GlobalDataCachePath value changes it to F:\TEMP\UnrealCache.
3. Speed tests execute there.
4. The node logs that path as writable.

This was the **Local** node pointing at a shared location. The graph's separately named Shared node was disabled by UE-SharedDataCachePath=None; ZenShared and Cloud also logged disabled. “Shared cache” must not be misread as evidence that the named Shared backend remained enabled.

-UserDir redirects project user/saved paths (Paths.cpp:1868 onward), but it does not change the Windows HKCU hive used by GetStoredValue. LOCALAPPDATA and TEMP changes do not override that API either.

## 7. Proposed isolated-only correction — not applied

Preserve the entire old Stage 2E workspace and 1,743-file copy. For one future attempt, create an independent new working clone at:

```text
G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject
```

Stage2ER_01 did not exist at this investigation's read-only existence check. If it exists when a future stage begins, do not overwrite it; select and document a new unique run root.

The proposed clone uses ordinary byte copies only. Verify all file hashes, path containment, no reparse-point directories, destination link count 1, and source/destination file identity inequality again. Keep Content read-only and autosave disabled. Retain the copied-only editor all-proxy loading override; never change production World Partition settings.

Proposed additions/replacements in the **new clone's** Config/DefaultEngine.ini only:

```ini
[Stage2ERPrivateDDC]
Root=(Type=Hierarchical,Inner=EngineReadPak,Inner=Stage2ERLocal)
EngineReadPak=(Type=ReadPak,Filename="G:/Program Files/EpicGames/UE_5.6/Engine/DerivedDataCache/Compressed.ddp",Compressed=true)
Stage2ERLocal=(Type=FileSystem,Path="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc",ReadOnly=false,DeleteOnly=false,Clean=false,Flush=false)

[InstalledDerivedDataBackendGraph]
Root=(Type=Hierarchical,Inner=EngineReadPak,Inner=Stage2ERLocal)
EngineReadPak=(Type=ReadPak,Filename="G:/Program Files/EpicGames/UE_5.6/Engine/DerivedDataCache/Compressed.ddp",Compressed=true)
Stage2ERLocal=(Type=FileSystem,Path="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc",ReadOnly=false,DeleteOnly=false,Clean=false,Flush=false)

[DerivedDataBackendGraph]
Root=(Type=Hierarchical,Inner=EngineReadPak,Inner=Stage2ERLocal)
EngineReadPak=(Type=ReadPak,Filename="G:/Program Files/EpicGames/UE_5.6/Engine/DerivedDataCache/Compressed.ddp",Compressed=true)
Stage2ERLocal=(Type=FileSystem,Path="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc",ReadOnly=false,DeleteOnly=false,Clean=false,Flush=false)
```

Rationale and precedence proof:

- -DDC=Stage2ERPrivateDDC selects the unique custom section through the actual parser.
- DerivedDataBackends.cpp:269-320 reads each reachable node from that section. Only EngineReadPak and Stage2ERLocal are reachable.
- The filesystem node has a literal short path and **omits EnvPathOverride, CommandLineOverride, EditorOverrideSetting and RedirectionFileName**. Those source branches cannot consult the user registry/editor overrides or redirect this node.
- FileSystemCacheStore.cpp:1540 onward attempts filesystem redirection only when RedirectionFileName is nonempty; it is empty by default here.
- The sole writable store is Stage2ERLocal. ReadOnly=false and DeleteOnly=false permit normal storage; Clean=false/Flush=false avoid startup deletion requests. The directory must be created writable and checked for reparse points before launch.
- EngineReadPak is an optional shared **read-only** installed engine cache. DerivedDataBackends.cpp:319-320 and 396-410 create a ReadPak store with bWriting=false. The file exists locally. Removing this read-only acceleration node is possible but is not required for writable isolation.
- There are no reachable Shared, Zen, Cloud or WritePak nodes.
- Both possible default fallback sections are given the same safe Root and node definitions. Inherited unused Local/Shared/Cloud entries remain unreachable. This closes the silent-default-fallback hazard identified at DerivedDataBackends.cpp:152-180.
- Before any launch, inspect all later project/platform/user config layers for conflicting definitions of these Root/node keys. If the merged graph cannot be established, stop. Do not rely on an environment-only or user-directory-only guarantee.
- If private storage is unavailable, the fenced fallback has the same private-only store; it must fail rather than restore the old shared graph. Reject any fallback/other writable-store log as a failed isolation gate.

This is a source-verified path-selection design, not a runtime-tested cache result. The future process must still log exactly the expected private writable path before its load can be accepted. A runtime fallback message is a stop signal, even if a fenced private fallback would remain safe.

Test-only new-clone editor settings may explicitly set autosave off and Live Coding bEnabled=False / bAutomaticallyCompileNewClasses=False. LiveCoding/Private/LiveCodingSettings.h declares these config properties. Do not infer that the old -NoLiveCoding/-NoSourceControl strings were effective merely because they appeared in argv; the new minimal proposal below uses the verified source-control provider override instead. No plugin disable or source rebuild is proposed.

Nothing in this section was written to a configuration file during Stage 2E-R.

## 8. Exact supported launch proposal — not executed

Normal rendered Editor mode; omit NullRHI, RenderOffscreen, commandlet/game modes and executable compile/build actions. Preserve the installed plugin set. Use a private new run root and ordinary renderer/window creation, matching the class of startup already working in production.

```text
"G:/Program Files/EpicGames/UE_5.6/Engine/Binaries/Win64/UnrealEditor.exe" "G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/isolated_project/ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -Unattended -SCCProvider=None -DDC=Stage2ERPrivateDDC -UserDir="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/user" -abslog="G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/logs/UnrealEditor.log"
```

Verified relevant argument implementations:

- -DDC=: DerivedDataBackends.cpp:126.
- -UserDir=: Core/Private/Misc/Paths.cpp:1868-1891.
- -abslog=: Core/Private/GenericPlatform/GenericPlatformOutputDevices.cpp:86.
- -Unattended: Core/Private/Misc/App.cpp:280-285; this is distinct from NullRHI's CanEverRender check.
- -SCCProvider=None: SourceControl/Private/SourceControlSettings.cpp:43-65 parses SCCProvider; SourceControlModule.cpp:167-169 uses provider None for disabling/resetting revision control.
- Project/map positional arguments are the same supported style used in the production and recorded launches. Success still requires authenticated project/map identity, not trust in argv.

Use a child-only environment dictionary, never global environment changes:

```text
FORGE_UNREAL_SESSION_DIR=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/registry/unreal
FORGE_SESSION_DIR=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/registry
LOCALAPPDATA=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/localappdata
TEMP=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/temp
TMP=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/temp
UE-LocalDataCachePath=G:/ForgeMCP_Recovery_Checkpoints/Stage2ER_01/ddc
UE-SharedDataCachePath=None
```

The DDC environment lines are secondary containment/documentation; the literal graph, not these variables, establishes path precedence. Clear inherited FORGE_* host/project/grant settings before setting the private registry values. Do not copy a production registration or approval. Protect the new registry directory to the current owner/SYSTEM and never print tokens.

Run with the new isolated project directory as cwd. A Python Popen STARTUPINFO with STARTF_USESHOWWINDOW/SW_HIDE may keep the child window hidden without selecting the engine's RenderOffscreen or NullRHI modes. There must be no simulated user input or live production UI operation. Do not attempt an unattended rebuild if modules are incompatible; capture the failure.

The old launch helper cannot simply be rerun: it hardcodes an already-used root/log names, the old graph and renderer settings. A future helper must implement this proposal with exclusive creation and exact child ownership checks. No helper was modified or created now.

## 9. One-attempt milestones, timeout and termination plan

Future execution requires separate authorization. Exactly one child launch is proposed; no automatic retries, renderer switches, plugin disables, cache cleanup or repairs.

Prelaunch gates:

1. Reauthenticate production; verify clean saved layer/height/proxy state and all saved package hashes.
2. Verify all three recovery checkpoints and sufficient storage/RAM.
3. Independently clone the retained project to the new path; validate binaries/modules/engine 5.6.1, manifest identities and no links/shared writable project files.
4. Apply only the proposed new-clone configuration; inspect later config layers and confirm the private/cache/user/temp/registry directories are unique, contained, writable and free of reparse points.
5. Preserve exact argv, child environment allowlist, parent/child PID, OS process creation time, executable and project command line. Do not include credential values.
6. Capture log baseline offsets and Content/config/source file hashes.

Finite budget: **900 seconds total** from launch. Suggested milestone checks at 30, 120, 300, 600 and 900 seconds. Capture logs, CPU/memory and child-owned shader-worker/process information at each check without changing the process. Do not terminate based solely on a quiet log while measurable initialization may still be active; the total deadline remains fixed.

Required observable milestones:

- Correct executable and isolated project identity.
- Renderer initialization, with no NullRHI path.
- Private DDC node reports the expected writable path; engine pak is read-only; no F:/TEMP/UnrealCache, other writable cache, Zen/cloud/shared endpoint, registry override or graph fallback.
- Shader workers/autogen initialization followed by evidence of progress or completion, not just the initial worker announcement.
- Asset registry startup and subsequent progress.
- No Teds/LevelEditor startup assertion; private ForgeMCP bridge registration for this exact child.
- Authenticated native project_info matches the new .uproject and target map.
- Actual ULevel::OnLevelLoaded target-map and World Partition initialization evidence in this fresh process.
- All 16 spatial proxies loaded through copied test settings.
- Both layer GUIDs/settings/dimensions, full height checksum, neutral ForgeTerrain and 64/64 component counts match.
- Supported read-only collision/composed sampling, if available, is reported separately; no save or terrain apply.

Safety stop signals: wrong project/PID, unexpected writable mount/cache, source-file/hash changes, module/build prompt or fatal error, package/layer serialization error, private authentication mismatch, or timeout. No restore or repair follows a failed signal.

Termination must apply only to the owned child: retain its Popen handle; verify PID, creation time, executable and exact isolated .uproject command line immediately before stopping it; reject production PID and PID reuse. After normal successful inspection or timeout, end only that disposable process, wait for completion and record its numeric exit status plus termination method/time. Track and stop only shader/crash worker children whose parentage and executable match the recorded test process; do not terminate workers belonging to production. No project save/close command, production UI message or broad process-name kill is permitted.

Preserve logs and artifacts. After the child ends, reauthenticate production, rehash saved packages, compare Content membership and confirm no production dirty/package/identity change. The original Editor must remain running throughout.

## 10. Production safety results — verified now

Fresh authenticated project-info:

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

Landscape checks pass now:

| Gate | Verified current result |
|---|---|
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D |
| Original Layer GUID | 198824024FF8A77A01535B86021D9B34 |
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B |
| Both layers | Visible and unlocked |
| Both complete native height checksums | 9f43572fbc2c06ef497da015879cdb23 |
| Dimensions | 2041 x 2041 for both |
| Minimum/maximum | 0 cm / 0 cm for both |
| Streaming proxies | 16 loaded / 0 unloaded |
| Registered terrain/collision components | 64 / 64 |
| Unexpected dirty production packages | Zero in complete loaded-package inventory |

Only /Script/SlateCore and /Script/UnrealEd remain dirty, classified as compiled-in engine-script packages. Neither was altered or cleared.

Read-only source/checkpoint verification at 2026-10-23T08:26:52.501621+00:00: all 32 post-adoption source/backup pairs match their recorded SHA-256, including all 17 saved Landscape packages. The retained 1,743-file manifest has no missing copied file. This stage did not rehash every unrelated 5.09 GB project file; the preceding full Stage 2E audit remains historical evidence. No historical result is substituted for the freshly verified saved-package/layer gates.

No new Editor was launched or stopped during this investigation. The only filesystem write authorized and performed was creation of this report. No configuration, registry, global environment, copied test project, checkpoint, plugin or source file was modified.

## 11. Remaining uncertainties and final recommendation

Verified defects: an unsatisfied Teds startup precondition in NullRHI mode, an environment-overridden-by-HKCU DDC path, and an inadequately recorded second child exit status. Verified correction: source-defined private filesystem graph without override hooks, including fenced defaults. Supported startup direction: ordinary rendered Editor initialization, not the failed headless/offscreen variants.

Unresolved: exact upstream LevelEditor loading-order cause; the offscreen stall's main-thread wait/call stack; whether shader work was genuinely continuing; and whether the proposed ordinary rendered child will initialize successfully on this machine. A private DDC corrects isolation but is not represented as a proven startup-stall fix. A future failure must not be interpreted as bad Landscape data unless actual disk-loaded package/layer validation reaches and fails that gate.

**READY — ONE CONTROLLED ISOLATED LOAD TEST**

The report supplies one bounded, isolated-only experiment with source-verified cache precedence and explicit failure/termination rules. This verdict authorizes no action itself: Stage 2E-R ends here, and the proposed launch/configuration changes have not been executed. The saved production Landscape remains intact; independent persistence acceptance is still pending.

