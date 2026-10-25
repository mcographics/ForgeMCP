# ForgeMCP A.7K-39 — Engine Plugin and Interactive Landscape Preflight

Date: 2026-10-21 (America/Toronto)  
Project: `G:\ForgeMCP`  
Engine target: Unreal Engine 5.6.1  
Phase 6C: **NO-GO**  
Mode: **Read-only preflight. No Editor was launched; no plugin, project, service, or asset was changed.**

## Result

The updated engine-level plugin is present in the registered Unreal Engine 5.6.1 installation at `G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge`. Its descriptor reports `0.2.16-alpha.1`; its descriptor and both module DLL hashes match the A7K-38 candidate package manifest. The engine build's compatible changelist also matches the candidate manifest. This verifies the **installed on-disk** candidate, not a loaded runtime: no `UnrealEditor.exe` process was present in the passive process snapshot.

The Third Person feature packs are present and readable in both inspected engine roots. A fresh project is still needed for interactive acceptance. The historical `BlueprintCompileProject` contains an older project-level `0.2.14-alpha.3` plugin, and the registered isolated engine clone contains `0.2.13-alpha.9`; neither should be used to test the new engine installation. The earlier A7K-38 disposable acceptance project also remains present with its accepted Landscape map, so this plan preserves it as evidence.

**Preflight recommendation:** GO only to a separately authorized creation and launch of a new disposable Third Person project using the verified `G:\Program Files\EpicGames\UE_5.6` executable. **NO-GO** for reopening the historical `BlueprintCompileProject` or for claiming interactive Landscape acceptance now. The proposed project, private session directory, dedicated host, and interactive acceptance were not created or started.

## Engine discovery and current Editor state

Passive Unreal registration and launcher catalog evidence identified two relevant engine roots:

| Engine root | Evidence | ForgeMCP on disk |
|---|---|---|
| `G:\Program Files\EpicGames\UE_5.6` | Epic Launcher `LauncherInstalled.dat` lists UE `5.6.1-44394996`; `Engine\Build\Build.version` reports 5.6.1, changelist 44394996, compatible changelist 43139311. The Editor executable exists and its file version is `++UE5+Release-5.6-CL-44394996`. | Engine Marketplace plugin is `0.2.16-alpha.1`, matching the A7K-38 package. |
| `G:\ForgeMCP-StageA7G-UE56\UE_5.6` | `HKCU\Software\Epic Games\Unreal Engine\Builds` maps the registered build ID to this root; the historical isolated Editor executable exists. | Engine Marketplace plugin is `0.2.13-alpha.9`, not the A7K-38 candidate. |

The historical project exists at `G:\ForgeMCP\Saved\LandscapeDevelopment\Phase6C-StageA7G-FinalAcceptance\BlueprintCompileProject\ForgeMCPDev.uproject`. Its descriptor has `EngineAssociation: "5.6"` and explicitly enables `MajesticForge`; that value alone does not prove which executable will open it. The exact executable argument must be pinned at launch.

At the current passive process snapshot, **no `UnrealEditor.exe` process was running**. This verifies that no Editor is currently running under that process name; there is no current loaded plugin version, session, map, or PIE state to report. No bridge request, health check, or service operation was made.

## Installed plugin versus candidate and loaded runtime

The updated installation is:

`G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge\MajesticForge.uplugin`

The descriptor reports plugin version `0.2.16-alpha.1`, descriptor `Version: 30`, `EngineVersion: 5.6.0`, `Installed: true`, `EnabledByDefault: true`, Win64 support, a Runtime module at `Default`, and an Editor module at `PostEngineInit`. The project plugin record in the A7K-38 disposable project's descriptor explicitly enabled `MajesticForge`. The candidate manifest identifies its tested engine as 5.6.1 with engine build ID 43139311; that equals the installed engine's `CompatibleChangelist`. The descriptor's 5.6.0 field is the plugin's engine-version metadata; the candidate manifest and DLL versions provide the more specific 5.6.1 build evidence.

| Installed file | Bytes | SHA-256 | Candidate manifest |
|---|---:|---|---|
| `MajesticForge.uplugin` | 926 | `55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07` | Match |
| `Binaries\Win64\UnrealEditor-MajesticForge.dll` | 2,655,232 | `297427727F3EEA60419E8CCCBD37289DE534FCE2FFA2D7CFB0D3FA6F070D20DF` | Match; file version 5.6.1 |
| `Binaries\Win64\UnrealEditor-MajesticForgeRuntime.dll` | 114,688 | `DA58F75E596F91BE0ED798185686179E89ED2C1063AE1B64D9F12D8F626F0BAB` | Match; file version 5.6.1 |
| `Binaries\Win64\UnrealEditor.modules` | 172 | `E16A1AE507BB506E7E98F0E9871EEA4B1F69683D8000FFAF482987F0A7136781` | Match; BuildId 43139311 |

The candidate archive `ForgeMCP-Unreal-Alpha-0.2.16-alpha.1-UE5.6.1-Win64.zip` has SHA-256 `FE34EFEBEEADEDD02EC8E1BA8980A42F1450F6F27105FFAAEBBB46FA800D735`. Its embedded `package-manifest.json` confirms the descriptor and module hashes above, core compatibility tested/minimum version 0.3.15, and `interactive_acceptance_complete: false`. The archive's source includes the native `Landscape` dependency in `MajesticForge.Build.cs`; A7K-38 separately built and runtime-tested this exact candidate in a disposable headless environment. This is strong binary and source provenance, but it is not a live runtime check in the currently closed Editor.

The inspected historical locations contain older copies:

| Location | Observed version | Relevant evidence |
|---|---|---|
| `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Plugins\Marketplace\Forge` | `0.2.13-alpha.9` | Editor DLL SHA-256 `2764187D2700FECE31941567830DE3658FB6C1B4088A4C8799107458280A406D`; Runtime DLL SHA-256 `8C08D41B197574020B77B6FCE670B5C28F961ECC6AFEA7172E8CB182ECF68BC0`. |
| `...\BlueprintCompileProject\Plugins\Forge` | `0.2.14-alpha.3` | Editor DLL SHA-256 `0F20FEE991F6525D7CFB5322AFF213D37F84E1A82CD7CA888E85F9212E382CCD`; Runtime DLL SHA-256 `A901FCCB64D0DA45BBADB7DDB0157206FB9729C166B74D3ECCE5E91BEB6959DF`. |

These are old, distinct paths from the A7K-38 engine-level installation. The user-confirmed installation of the updated version at engine level is consistent with the `Program Files` engine result. The legacy project and cloned engine remain unsuitable targets for this test because their plugin descriptors identify older versions. No attempt was made to remove or replace them.

## Third Person feature pack

The actual feature-pack directory in both checked UE 5.6.1 engine roots is `<EngineRoot>\FeaturePacks` (at the engine root, not under `Engine\FeaturePacks`). Both expected packages exist and are readable:

| File in `G:\Program Files\EpicGames\UE_5.6\FeaturePacks` | Bytes | Last-write UTC | SHA-256 |
|---|---:|---|---|
| `TP_ThirdPerson.upack` | 186,288 | `2025-12-15T22:16:14.3288814Z` | `E0EE04E999D0E08D9B44B99F46CEC260DD44B9333C23D8C30A002A763D4D169D` |
| `TP_ThirdPersonBP.upack` | 186,189 | `2025-12-15T22:16:14.3293814Z` | `7FDA129DAECF1A2E9F3B6C342011461471B76C6AB1AA10EAFF905D9A8B70A0C4` |

Both files also exist in the registered isolated engine clone with identical size, timestamp, and hash. Their placement in the UE 5.6.1 installation and byte-identical presence in the clone support use with that engine. No explicit engine-version field was extracted from the `.upack` payload, so package-internal compatibility metadata remains unverified. The engine contains the `EnhancedInput`, `GameplayAbilities`, and `WebBrowserWidget` plugin descriptors required by the observed template/plugin setup. No feature-pack copy or import was performed.

## Safest test project and proposed scope

The prior A7K-38 disposable project still exists at `C:\Users\Kenne\AppData\Local\ForgeMCP\IsolatedLandscapeSmoke\f045e6361e004614a7844db21d448aa2\state\ForgeMCPDev.uproject`, and its accepted World Partition map still exists. Its project descriptor enables `MajesticForge`, and A7K-38 records the successful headless run. Reusing it would change the prior acceptance fixture, so preserve it unchanged.

The historical `BlueprintCompileProject` is also unsuitable: it contains recovery evidence and the older project-local plugin. The safest target is a **new, separately authorized disposable project** created from the installed `TP_ThirdPerson` feature pack:

- Proposed project: `G:\ForgeMCP\Saved\LandscapeDevelopment\A7K39-Interactive-20261021\ForgeMCP_A7K39_Interactive.uproject` (does not exist).
- Proposed test map: `/Game/ForgeMCPTests/Landscape/L_A7K39_Interactive_WP_20261021` (does not exist).
- Proposed private registration directory: `C:\Users\Kenne\AppData\Local\ForgeMCP\A7K39-Interactive-20261021\Session` (does not exist; create later with restricted owner/SYSTEM ACL before Editor startup).
- Use the official UE 5.6.1 executable and explicitly enable `MajesticForge` plus the feature pack's required plugins in the new project descriptor. Do not point this project at either legacy plugin copy.

After the new project and private directory are created and reviewed under separate authorization, the exact VS Code integrated PowerShell launch command is:

```powershell
$env:FORGE_UNREAL_SESSION_DIR = 'C:\Users\Kenne\AppData\Local\ForgeMCP\A7K39-Interactive-20261021\Session'
& 'G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe' 'G:\ForgeMCP\Saved\LandscapeDevelopment\A7K39-Interactive-20261021\ForgeMCP_A7K39_Interactive.uproject'
```

This command was prepared only; it was not run. It deliberately pins the executable and project and contains no `-NullRHI`. Before launch, independently recheck the process list, exact executable/project paths, project plugin resolution, and session-directory ACL. If a recovery prompt appears, stop without selecting an option. After launch, verify the new PID/start time, loaded module path/hash, private registration/session, and authenticated dedicated host before any tool request.

## Interactive Landscape acceptance plan

Once separately authorized, use the new project only. First verify the private session and plugin runtime, then request a stable, complete dirty-package inventory. The A7K-38 exact disposable `/Script/SlateCore` exception may be accepted only with its documented complete ownership evidence; dirty project packages, dirty current-world packages, external actors, unknown/incomplete rows, or any other unresolved classification block the test. Do not interpret a missing dirty marker as a clean state.

Create one new World Partition map in the proposed namespace and use the A7K-38 bounded terrain recipe: 2×2 Landscape components, one section per component, 63 quads per section, 100 cm XY scale, and the engine BasicShape Landscape material. Before Apply, inspect the native preview and approve the exact map/HLOD/WorldState destinations, generated external-actor namespace, and declared recovery/backup and Editor-generated auxiliary categories. Generated actor package names are namespace predictions, not exact paths. A7K-38 demonstrated that post-operation auditing detects unapproved writes; it is not a complete prevention fence, so the project must remain fully disposable.

The authorized acceptance should then demonstrate generated height, visible raised hill and lowered valley, flattening, smoothing, save/reload persistence, height-data comparison, and collision after reload. Manually confirm the resulting terrain in the normal Editor viewport, then test Third Person movement and collision in the disposable map. Record the exact resulting file set and stop on any write outside the approved project/map scope. Do not enter production city content or alter any preserved acceptance evidence.

## Acceptance gates

| Gate | Status | Evidence / limitation |
|---|---|---|
| Disposable Editor shutdown verified | **PASS** | No `UnrealEditor.exe` process in the current passive snapshot. |
| Correct UE 5.6.1 executable verified | **PASS** | Official launcher path and engine build metadata verified. |
| Correct new disposable project verified | **UNKNOWN** | Proposed project does not exist yet; the legacy and A7K-38 projects are intentionally not reused. |
| Engine-level ForgeMCP installation found | **PASS** | Engine Marketplace path found under the official UE 5.6.1 installation. |
| Installed plugin version verified | **PASS** | On-disk descriptor is 0.2.16-alpha.1; descriptor/module hashes match candidate manifest. |
| Loaded plugin runtime version verified | **UNKNOWN** | No Editor is running, so no module is currently loaded. |
| Duplicate/legacy path review | **CONFLICT for legacy project use** | Older 0.2.13 and 0.2.14 copies exist in the inspected historical paths. New test must use a fresh project and the official UE executable. |
| UE compatibility | **PASS for the candidate engine build** | Candidate BuildId 43139311 matches UE 5.6.1 compatible changelist; no new runtime was launched. |
| Third Person feature pack found | **PASS** | Both Third Person packages exist and are readable in the engine FeaturePacks directory; payload-internal version metadata was not parsed. |
| Interactive test project identified | **PASS as a proposal** | Exact new project and map paths are reserved conceptually and absent on disk; creation needs separate authorization. |
| Safe reopening command prepared | **PASS as a plan** | Command pins the official executable and proposed project; not executed. |
| Interactive Landscape acceptance completed | **NOT RUN** | No project, map, Landscape, host, or Editor was created or launched. |

## Authorization boundary and final recommendation

This preflight authorizes no project creation, session-directory/ACL creation, Editor launch, host startup, bridge request, feature-pack import, Landscape preview/apply, save/reload, or PIE traversal. Those operations require separate authorization. Preserve A7K-29 and all later recovery/acceptance evidence unchanged. Do not change Blender, services, credentials, production city assets, `L_City_World_Master`, or Phase 6C status.

**Recommendation: GO to a separate authorization request for creation of the new disposable Third Person project and private session, followed by interactive acceptance using the exact engine-level 0.2.16-alpha.1 plugin. NO-GO for reopening the historical project or claiming interactive acceptance before that work is approved and completed. Phase 6C remains NO-GO.**

## Files and services affected

Only this report is created. Read-only checks covered Unreal engine association/launcher metadata, the two recognized engine-level plugin paths, the historical project plugin descriptor/binaries, the A7K-38 candidate archive/manifest, project descriptors, and the two Third Person feature-pack paths. One passive process snapshot found no Unreal Editor process. No Editor, host, bridge, server, credential, production project, Blender profile, plugin, project asset, configuration, backup, or recovery file was changed. No installation, file copy, compile, asset creation, save, reload, PIE, or cleanup occurred.
