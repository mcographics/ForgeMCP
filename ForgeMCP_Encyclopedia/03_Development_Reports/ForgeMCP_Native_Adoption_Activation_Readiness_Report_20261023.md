# Native adoption activation readiness

Date: October 23, 2026 (America/Toronto)

## Current live state

The actual Codex ForgeMCP namespace authenticated and executed read-only session, project and Landscape inspections. Windows independently identified one Editor and the paths of its loaded Forge DLLs.

- Session `unreal-18588`, Editor PID `18588`, freshly rediscovered during this phase.
- Project `G:/ForgeMCP/ForgeMCPDev.uproject`, Unreal Engine `5.6.1-44394996+++UE5+Release-5.6`.
- World `/Game/Levels/L_City_World_Master`, PIE stopped.
- Native Landscape GUID `BD45FDD94EC2A29617B50794F2DE4E9D`.
- Actor `/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295`.
- 2041 x 2041 vertices, 64 components, 16 loaded streaming proxies, zero unloaded proxies, World Partition enabled.
- Original `Layer` remains flat at 0 cm and its checksum remains `9f43572fbc2c06ef497da015879cdb23`, matching the October 23 implementation report.
- A read-only dirty-package snapshot inspected 1,258 loaded packages and found only `/Script/SlateCore`, classified as an engine script package and unrelated to the current level. No dirty loaded project-content packages were reported. Unloaded packages were not classified as clean. The engine script package was left untouched.

No adoption request, grant, layer setup, terrain Apply, save, map transition, host refresh, Editor restart, Live Coding or additional Editor process was performed.

## Module and build assessment

The adoption implementation changes native code only in the `MajesticForge` Editor module. It must be relinked. `MajesticForgeRuntime` source is unchanged by adoption, but the plugin's manifest describes both modules and a clean staged plugin build can regenerate both binaries.

Loaded native files are:

```text
G:/ForgeMCP/Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll
G:/ForgeMCP/Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForgeRuntime.dll
```

The existing plugin and installed engine `UnrealEditor.modules` both use BuildId `43139311`. The live Editor-module DLL SHA-256 before staging is `CB3041EFAA0D0E71F2651CB2E4F549C85107B1119A51DD89515CCE8D3337E292`.

An in-place linked build would target loaded DLLs and was not run. An out-of-place linked build is supported through Unreal's plugin build workflow. It uses generated build metadata and a copy of the plugin; it creates no terrain test world and launches no Editor. The installed UE 5.6 AutomationTool and UBT source were inspected to verify copy/output behavior and supported options.

The prior report's `-NoLink` build succeeded in 188.18 seconds. That is historical compile evidence, not a completed linked build or native runtime acceptance.

## Staging build evidence

Stage/backup root:

```text
G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z
```

`SourcePlugin` contains a snapshot of the plugin descriptor, Source, Config and Resources. `Package` was verified absent before invoking AutomationTool. Existing Binaries and Intermediate were omitted from the input snapshot so the build could not reuse or replace the live plugin binaries. The package output is a sibling of the input snapshot and is outside every loaded native-module directory. BuildPlugin's generated HostProject is retained as build evidence; it was never opened in an Editor.

Initial supported command:

```powershell
& 'G:/Program Files/EpicGames/UE_5.6/Engine/Build/BatchFiles/RunUAT.bat' BuildPlugin '-Plugin=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/SourcePlugin/MajesticForge.uplugin' '-Package=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/Package' -HostPlatforms=Win64 -NoTargetPlatforms -NoDeleteHostProject -UTF8Output
```

This failed before compilation with:

```text
Could not find definition for module 'KitBash3dUsdTools',
(referenced via default plugins -> Cargo.uplugin)
```

Evidence: `InitialBuildPlugin-RulesFailure.txt` in the stage root. Production already explicitly disables Cargo and engine plugins by default. Only the generated staging HostProject was given `DisableEnginePluginsByDefault: true`; production configuration was not edited. A generic UnrealEditor target also scans all compatible plugin modules and failed at the same missing Cargo module. Evidence: `LinkedBuild-GenericTargetRulesFailure.log`.

The resumed supported UBT invocation adds `-DisablePlugin=Cargo` only for the generated staging target. The option is declared in UE 5.6 `TargetRules.cs`; `UEBuildTarget.AddAllValidModulesToTarget` explicitly skips plugins in that target's DisablePlugins list. This is a scoped build exclusion matching production's existing setting, not a change to the working Editor or connection.

```powershell
& 'G:/Program Files/EpicGames/UE_5.6/Engine/Build/BatchFiles/Build.bat' UnrealEditor Win64 Development '-Project=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/Package/HostProject/HostProject.uproject' '-plugin=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/Package/HostProject/Plugins/MajesticForge/MajesticForge.uplugin' -noubtmakefiles '-manifest=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/Package/HostProject/Saved/Manifest-UnrealEditor-Win64-Development.xml' -nohotreload -NoEngineChanges -DisablePlugin=Cargo '-Log=G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/LinkedBuild.log'
```

Final linked-build result and artifact verification are recorded in the completion section below. The initial BuildPlugin packaging command itself must not be described as successful.

## Tests and coverage limits

Executed in this readiness phase:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_mcp_stdio.py tests/test_landscape_adoption.py tests/test_landscape.py tests/test_landscape_authorization.py tests/test_landscape_authorization_tools.py tests/test_landscape_write_scope_audit.py tests/test_native_plugin_contract.py tests/test_host_config.py tests/test_connections.py -q
```

Result: **152 passed in 39.40 seconds**. These are Python schema/wrapper tests, native source-contract checks, connection regressions and MCP subprocess tests using fake registrations. They are not native runtime tests or proof of production sculpting.

Native adoption automation executed: **none**.

- `Forge.Landscape.Adoption.Authorization`: not run; current loaded DLL predates it.
- `Forge.Landscape.Adoption.BackupIntegrity`: not run; current loaded DLL predates it.

Neither test name nor `landscape_adoption_preflight` was found in the loaded DLL's ASCII/UTF-16 strings, and its live health response advertises neither new native adoption command. The current Codex namespace also lacks the two new MCP tools. The existing native `editor_test` bridge handles only the allowlisted Blueprint compile/start-PIE/stop-PIE cases; it cannot run arbitrary automation tests. It was not invoked as a substitute.

The new native policy test covers approved scope, session/project/world/actor/GUID/partition mismatch, unapproved actions, expiration, revocation, one-operation use, region containment, component/proxy count/readiness predicates, missing/locked/invisible target layers and missing backups. The backup test checks fixture copy validity, tampering and missing checkpoint bytes. These are policy/helper tests; they do not exercise actual World Partition streaming or native layer creation on production content. Original workflow compatibility and preview/apply source boundaries are covered by the executed Python/source-contract suite. Real Edit Layer preservation, World Partition write-region behavior and actual adoption preview/apply still need runtime acceptance under separately authorized conditions.

## Backups and connection rollback readiness

`BackupManifest.json` records lengths and SHA-256 values for 134 copied files. Every entry was compared to its original source and verified; copies were not merely compared to hashes generated from themselves. The staging root's inherited permissions were replaced with current-user and SYSTEM access because configuration copies may contain private settings. No registration or token files were copied or printed.

Backed up:

- `Backup/Plugin/Binaries/Win64`: both known-working loaded DLL files, matching PDBs and `UnrealEditor.modules`.
- `Backup/Plugin/MajesticForge.uplugin`, Source, Config and Resources: current descriptor and source/resource snapshot. The source already includes adoption changes and must not be confused with the older loaded DLL implementation.
- `Backup/HostCurrent/server`: current on-disk host source, including bootstrap and adoption additions.
- `Backup/ProjectCodexConfig.toml`: `G:/ForgeMCP/.codex/config.toml`.
- `Backup/UserCodexConfig.toml`: `C:/Users/Kenne/.codex/config.toml`.
- `Backup/pyproject.toml`.

`Backup/HostPreAdoptionCandidate/server` was reconstructed from HostCurrent plus the pre-adoption copies of `server/main.py`, `server/core/connections.py` and `server/core/landscape.py` retained by the implementation task. All 33 Python source files parse successfully. An offline import/tool-registry check through the unchanged venv also succeeded: `forge_status`, `forge_list_sessions`, `unreal_project_info` and `unreal_inspect_landscape` were present, and adoption tools were absent. It did not start a stdio server or authenticate to Unreal. This is a recoverable pre-adoption source candidate, not a byte-for-byte dump of the running Python interpreter or a live-tested rollback startup. The current venv/interpreter/dependencies were not changed and are retained in place.

Connection configuration remains:

```text
command: G:/ForgeMCP/.venv/Scripts/python.exe
arguments: -B -m server.bootstrap
cwd: G:/ForgeMCP
startup timeout: 60 seconds
tool timeout: 30 seconds
session directory: C:/Users/Kenne/AppData/Local/MajesticForge/sessions
```

No shell wrapper, new Python environment, session-marker change or credential regeneration is needed. Keep the working registration architecture. After a later Editor restart, rediscover the new session/PID and use its fresh native registration; never restore an old session-registration file or reuse this report's PID by assumption.

## Exact controlled activation procedure

This procedure is prepared for a later separately authorized activation window. No restart or installation is authorized by this report.

1. Confirm final staged link/artifact checks below passed. Verify source snapshots and backup manifest. If the staged build failed or BuildIds/module lists differ, stop. Do not deploy partial output.
2. Reinspect the live project, world, Landscape GUID, loaded proxies, original layer checksum, PIE state and dirty packages. Review unsaved user work with the user. Do not use Save All or save city content merely to activate a plugin.
3. After separate restart authorization, close the existing Editor normally through **File -> Exit**. The user decides whether any unrelated unsaved work should be saved or discarded. Cancel shutdown if that decision is unresolved. Confirm the known Editor PID exited and the two Forge DLLs are no longer mapped. Never force termination.
4. Verify the original native backup hashes again while the Editor is closed. Install a complete compatible staged binary set into `G:/ForgeMCP/Plugins/Forge/Binaries/Win64`: `UnrealEditor-MajesticForge.dll`, `UnrealEditor-MajesticForgeRuntime.dll`, their matching PDBs, and the matching `UnrealEditor.modules`. If a staged file is absent or BuildId does not match installed engine `43139311`, stop. Retain rollback copies; do not install individual mismatched pieces. The descriptor/source/resources already match the recorded build snapshot; compare hashes before replacing anything else.
5. Open `G:/ForgeMCP/ForgeMCPDev.uproject` once through the existing UE 5.6.1 executable. Wait for that single Editor to open the intended production level. This loads the module through the normal Editor startup path; do not use Live Coding or a forced module reload. If a rebuild/missing-module dialog appears, stop and preserve its exact message.
6. Rediscover sessions with the existing ForgeMCP tools. Match the sole intended Editor PID, project and world before addressing a session. If the existing host discovers it and communicates correctly, keep the host running. It still needs a controlled refresh to expose the new Python tool registry if it predates adoption; refresh only the existing registered `forgemcp` entry in the owning VS Code Codex MCP settings, after separate authorization. Do not create another server entry. Preserve `-B`, bootstrap, cwd and both timeouts; allow the full 60-second startup interval. If only a full Codex extension/window refresh is available, report that disruption before taking it.
7. Require actual current-chat tool discovery of `unreal_landscape_adoption_preflight` and `unreal_request_landscape_adoption`, plus native health capability discovery of `landscape_adoption_preflight` and `landscape_adoption_request`. A tool list or startup handshake alone is insufficient. Execute `unreal_project_info` and `unreal_inspect_landscape` against the explicit newly discovered session and require authenticated success.
8. Run the two exact new native tests through the existing Editor's Output Log console, one at a time, after confirming they are registered: `Automation RunTests Forge.Landscape.Adoption.Authorization` and `Automation RunTests Forge.Landscape.Adoption.BackupIntegrity`. Review native test outcomes/logs. The policy test uses no production world; BackupIntegrity uses generated Saved fixture files and removes only its fixture tree. Do not run a broad unrelated test suite or PIE test on production.
9. Run only `unreal_landscape_adoption_preflight` using the exact request below and freshly verified current identity. Its `actions` describe the proposed preparation scope; preflight does not request or grant adoption and must remain read-only. Require the same actor/GUID, `potentially_adoptable: true`, correct checkpoint-source status, and a precise missing-layer/approval/backup explanation. Do not call `unreal_request_landscape_adoption`, any local approval command, or `unreal_apply_landscape` in this activation phase.
10. Reinspect the original layer checksum, layer list and Editor responsiveness. Stop with activation/preflight evidence. Creating `ForgeTerrain`, issuing a grant, sculpting and saving require separate future authorization.

Read-only preflight request (replace the PID/session and any identity that changed after restart):

```json
{
  "session_id": "unreal-18588",
  "request": {
    "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
    "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D",
    "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
    "world_path": "/Game/Levels/L_City_World_Master",
    "world_partition": true,
    "editor_pid": 18588,
    "region": [0, 0, 2040, 2040],
    "actions": ["setup_layer"],
    "lifetime_seconds": 600
  }
}
```

## Rollback procedure if activation fails

1. Stop further activation work. Preserve native logs, bootstrap phase markers and the exact Codex startup/tool error. Do not increase timeouts or change authentication speculatively.
2. With the user's authorization, close the affected Editor normally; preserve user work and confirm its Forge DLLs are unmapped. Close no unrelated process.
3. Restore the entire backed-up `Backup/Plugin/Binaries/Win64` set to the original plugin directory while the Editor is closed. Verify each restored hash against `BackupManifest.json`. Restore the backed-up descriptor/Config/Resources only if they were actually changed during activation; the readiness work did not change them.
4. If only native activation failed, the current host may remain unchanged. If a refreshed host also fails, stop the registered host through its normal owning-client mechanism and restore `Backup/HostPreAdoptionCandidate/server` Python source to `G:/ForgeMCP/server`, retaining the adoption implementation snapshot. Do not overwrite credentials or session registrations. The rollback source candidate is syntax-checked but startup remains to be verified.
5. Restore project/user Codex configurations only if they changed, from their exact backups. Normally they should remain untouched. Keep the existing venv and `-B -m server.bootstrap` launch. Do not reinstall dependencies or regenerate native authentication tokens manually.
6. Open the original project once, rediscover its new session, refresh the existing host only if needed and authorized, allow the configured timeout, and prove actual authenticated `unreal_project_info`/Landscape inspection from the owning Codex chat. Compare the original layer checksum and project/world identity. Do not declare rollback successful from process presence, file restoration or handshake alone.

Native rollback copies are verified. `HostPreAdoptionCandidateManifest.json` separately records SHA-256 hashes for the 33 reconstructed rollback Python sources. End-to-end rollback is prepared but intentionally unexercised; performing it now would interrupt the healthy connection.

## Completion and remaining blockers

**Full staged linked build: PASS.** The final supported UBT command exited 0 with `Result: Succeeded` after 855.46 seconds. All 34 actions completed, including explicit links for both `UnrealEditor-MajesticForgeRuntime.dll` and `UnrealEditor-MajesticForge.dll`. This is full linking, not `-NoLink`, and did not install or load either candidate DLL.

Verified candidate binary directory:

```text
G:/ForgeMCP/Saved/ForgeMCP-Adoption-ActivationReadiness-20261023T055129Z/Package/HostProject/Plugins/MajesticForge/Binaries/Win64
```

- Both DLLs have valid PE signatures and AMD64 machine headers.
- `UnrealEditor.modules` lists exactly `MajesticForge` and `MajesticForgeRuntime` and matches installed-engine BuildId `43139311`.
- Both matching PDBs are present; the five binary/metadata files have SHA-256 entries in `StagedBinaryManifest.json`.
- Candidate Editor DLL length: 2,797,056 bytes; SHA-256 `429FCD78B1D8057ACC180900092D3AC1C91A0439A72426009C297311C3E9F4DF`.
- Static inspection found both new native adoption commands, the adoption origin, the local approval console command and both adoption automation test names in the candidate Editor DLL. This confirms inclusion, not runtime execution.
- Post-build comparison of every one of the 134 original source files represented in `BackupManifest.json` found **zero changes**. This includes active plugin DLLs/PDBs/manifest, source/resources, host source and both Codex configurations. The active Editor DLL retains its original SHA-256.
- A final fresh session discovery and authenticated project/Landscape inspection succeeded against `unreal-18588` / PID `18588`, the expected project/world, the same Landscape GUID, 2041 x 2041 vertices, 64 components and 16 loaded proxies. Original `Layer` checksum remains `9f43572fbc2c06ef497da015879cdb23`. Only that Editor is running and it remains responsive.

**Activation requires a separately authorized normal Editor close/reopen.** The candidate files are ready for the controlled installation procedure above; no file may be copied over a loaded DLL. The existing host needs an authorized refresh to expose its new tool registry. Configuration changes and another Editor instance are unnecessary.

**Native runtime acceptance is pending.** Neither adoption automation test was executed; new commands are not in the currently loaded module. The existing Landscape is structurally ready to be the runtime read-only adoption-preflight target after activation. Actual native preflight eligibility remains unverified, and this phase does not authorize a grant, layer setup, sculpt or save.

**Rollback readiness: prepared and hash-verified; live restoration unexercised.** Known-working native binaries and exact configurations are copied, and the pre-adoption host candidate passed syntax/import/registry checks. Any actual rollback must be verified through the owning Codex connection after fresh session discovery.

No source implementation changes, active native binary replacements, host reloads, Editor restarts, production grants, terrain changes, saves or new Editor instances occurred during readiness work. Only reports, protected backup/build snapshots and generated staging build metadata/artifacts were written. The unrelated Cargo module problem was excluded only in staging; the installed engine and production plugin settings were not repaired or changed.
