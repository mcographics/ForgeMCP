# ForgeMCP — Controlled Plugin Activation and Runtime Connection Verification

Task date: 2026-10-22 local  
Observation: 2026-10-23 UTC  
Project: `G:/ForgeMCP/ForgeMCPDev.uproject`  
**Final verdict: C. ACTIVATION BLOCKED — USER ACTION REQUIRED. Native activation and authenticated inspection PASS; updated connected Python-host activation remains incomplete.**

## Editor and native module activation

Preflight found no Unreal Editor. The official Engine reports **5.6.1 / changelist 44394996**. The project-local MajesticForge Editor DLL matched the compiled SHA-256 `CB3041EFAA0D0E71F2651CB2E4F549C85107B1119A51DD89515CCE8D3337E292`; the plugin and Engine module manifests both use **BuildId 43139311**. Available disk space was approximately 26.9 GiB on C: and 180.6 GiB on G:.

One Editor was launched from the official installation, opening the existing project and exact requested world. No new project, rebuild or hot reload occurred. Launch arguments were:

```text
"G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" "G:\ForgeMCP\ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -SkipCompile -Unattended -NoSplash "-AbsLog=G:\ForgeMCP\Saved\ForgeMCP-PluginActivation-20261023T004256Z\Editor.log"
```

The new Editor is **PID 5028**, created **2026-10-23T00:43:20.8229410Z**. Engine initialization completed in **35.29 seconds**. Process module enumeration confirmed both project-local DLLs loaded:

| Module | Loaded path / SHA-256 at mapped file |
|---|---|
| MajesticForge Editor | `G:\ForgeMCP\Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.dll` — `CB3041EFAA0D0E71F2651CB2E4F549C85107B1119A51DD89515CCE8D3337E292` |
| MajesticForgeRuntime | `G:\ForgeMCP\Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.dll` — `A672F5FF98B60825C56AEFD5B057FBF91C2B72D9F31F90260E26BAF2344EB11A` |

These are disk identities at the mapped paths, not in-memory image hashes. No module compatibility failure or Landscape initialization error was observed. Native Landscape creation initialization was not exercised.

## Session and authenticated communication

The private registration matched **unreal-5028**, PID 5028, protocol version 1 and **127.0.0.1:59421**. A token was present and never printed or exported. Passive TCP inspection found exactly the expected loopback listener owned by PID 5028. The native log reported the local bridge ready.

Through the existing Codex ForgeMCP connector, explicit `unreal_project_info` succeeded and returned:

- Project: **ForgeMCPDev**.
- Project file: **G:/ForgeMCP/ForgeMCPDev.uproject**.
- Engine: **5.6.1-44394996+++UE5+Release-5.6**.
- Active world: **/Game/Levels/L_City_World_Master.L_City_World_Master**.
- PIE: **false**.

`unreal_inspect_landscape` then succeeded: **0 Landscapes**, World Partition enabled, **0 streaming sublevels**, persistent level external actors enabled. `safe_create_source=false` remains the legacy disposable-source indicator; it does not itself evaluate the new host grant. No grant was configured and no preview/apply was requested.

The session discovery/health tool returned `connected=true` and an authenticated **ForgeMCP Unreal** health response for unreal-5028, with all five native Landscape commands advertised. The old connected host enumerated historical registrations despite the explicit session argument; those records were disconnected. They were preserved without cleanup. Health advertisement is registration proof, not execution acceptance for mutation commands.

## Python host status and precise blocker

The existing host is a stdio process chain: venv launcher **PID 4480**, actual Python host **PID 25964**, owned by **Codex PID 29192**. The chain started on October 21, before the new authorization source was written on October 22. The connected Landscape tool description still contains the old approved-test-world restriction, corroborating that this connector has not refreshed its imported tool schema.

A fresh, non-host Python import check successfully imported `server.main` and `server.core.landscape_authorization`, enumerated **114 tools**, confirmed project_info and all five Landscape tools, and verified authorization defaults to deny. This proves current source imports and registration in a fresh interpreter; it does **not** prove that the existing connected host loaded the updated code.

**No host restart was performed.** Replacing a live stdio MCP host requires its owning connector to reconnect the transport. This task has no safe host-supervisor restart/reconnect operation; terminating the identified Python processes would sever the active connection without establishing its replacement. No process was killed, no replacement host was launched, and no unrelated service was interrupted. An owner-controlled ForgeMCP MCP reconnection/restart is required before the updated authorization workflow can be considered active end to end.

## Dirty state and protected assets

The read-only native dirty-package snapshot completed: **1,164 loaded packages inspected**, inventory complete, and **one dirty package: /Script/SlateCore**. The city map was not reported dirty. This is a current loaded-package observation, not proof about unloaded package state or equality of every in-memory object before/after startup.

All **1,522 Content/Config files** had identical prelaunch and post-verification SHA-256 hashes, with no additions or deletions. This includes on-disk city, Ultra Dynamic Sky and configuration files. Ordinary Saved/Intermediate/cache/log startup artifacts are outside that bounded comparison. No asset modification, package save/discard, World Partition setting change, terrain creation/sculpting, authorization configuration, source edit or Trello action was performed. The Editor remains open.

The current existing-world creation implementation requires a complete clean dirty-package preflight. The observed /Script/SlateCore dirtiness is therefore an additional blocker to a future creation apply under the present policy; no exception, cleanup, save/discard or policy change was attempted.

## Warnings and evidence

Startup warnings include a duplicate DDC path being ignored, missing VisionOS Slate icons, missing TextureFormatOodle, and missing ACL animation compression settings assets. No correction or configuration repair was attempted. The successful module mapping, project-info, Landscape inspection and health responses establish native communication despite those warnings. No claim is made about visual indicator color, which was not independently observed.

Evidence is under `G:\ForgeMCP\Saved\ForgeMCP-PluginActivation-20261023T004256Z`: launch.json, Editor.log, verified-identity.json, read-only-results.json, prelaunch-files.json, postcheck-files.json and file-diff.json. Credentials and raw registrations were not copied into the evidence. The Editor log remains live; filesystem hashes are observations at the audit time.

## Independent gates and next action

| Gate | Result |
|---|---|
| Official Engine/project startup | PASS |
| Compiled Editor and Runtime module loading | PASS |
| Exact session/endpoint and authenticated native responses | PASS |
| Native and MCP Landscape tool registration | PASS; mutation handlers not executed |
| Current Python source imports/catalog | PASS in fresh non-host interpreter |
| Updated connected Python-host activation | BLOCKED; owner connector restart/reconnection required |
| Protected Content/Config disk identity | PASS for 1,522 monitored files |
| Existing-world creation dirty-package gate | BLOCKED by current /Script/SlateCore dirtiness |
| Readiness for controlled Landscape preview | INCOMPLETE until host refresh and current-state review |
| Production creation/save acceptance | NOT TESTED / NOT AUTHORIZED by this task |

The narrow next action is an owner-controlled refresh of the existing ForgeMCP MCP connection, followed by read-only confirmation that the connected host exposes the new authorization contract. Do not close or restart the newly launched Editor solely to refresh Python. Any subsequent grant, preview, creation, dirty-package policy decision or save requires its own explicit scope.

**C. ACTIVATION BLOCKED — USER ACTION REQUIRED. Native plugin activation and read-only connection succeeded; full updated-host activation is incomplete. Phase 6C remains NO-GO.**
