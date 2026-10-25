# ForgeMCP Official Engine Connection Verification — ForgeMCPDev

Date: 2026-10-22 UTC  
Scope: bounded read-only verification  
Final verdict: **BLOCKED after one authenticated metadata response.** The response identified the active level as the explicitly excluded production level `L_City_World_Master`; testing stopped immediately. No second request was sent.

## Verified Editor and session

Passive checks before the request found Editor PID **13432**, created **2026-10-22T18:52:40.8564630Z**, running the official UE executable at `G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe` with the exact project argument `G:/ForgeMCP/ForgeMCPDev.uproject`. The Engine plugin descriptor reports version **0.2.16-alpha.1**, numeric version **30**, and matches the official Engine descriptor hash `55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07`.

The private registration `unreal-13432` matched kind `unreal`, PID **13432**, host **127.0.0.1**, port **62491**, and protocol **1**. A token was present; its value was not read into the report or disclosed. The registration ACL was protected and limited to the owner and SYSTEM. A passive listener check found exactly one listener for port 62491: **127.0.0.1:62491**, owned by PID **13432**.

The running Editor had `UnrealEditor-MajesticForge.dll` and `UnrealEditor-MajesticForgeRuntime.dll` loaded from the project-local `G:\ForgeMCP\Plugins\Forge\Binaries\Win64` directory. Their on-disk hashes differ from the official Engine plugin binaries. Therefore this verifies a project-local Forge plugin copy running under the official Engine, not the Engine-installed binary copy.

## Native response and stop boundary

One explicit `unreal_project_info` call with session `unreal-13432` returned successfully and echoed that session ID. The response reported:

- Project: `ForgeMCPDev` at `G:/ForgeMCP/ForgeMCPDev.uproject`
- Engine: `5.6.1-44394996+++UE5+Release-5.6`
- Active level: `/Game/Levels/L_City_World_Master.L_City_World_Master`
- PIE: `false`

The successful response to the exact registered session is evidence of one authenticated native response. It also revealed that this Editor is currently on the production level explicitly excluded by the request. I stopped at that point. No second read-only request, health/status probe, dirty-package inspection, asset inspection, or further production-level access was performed.

The user's reported red/green indicator changes were not independently observed during this verification. No claim is made about the current rendered indicator color or idle transition. No Editor, host, bridge, package, asset, plugin, Engine configuration, or project file was changed by this verification. No Editor lifecycle action or host replacement was performed.

## Verdicts

| Gate | Result |
|---|---|
| Current Editor/project/session/endpoint identity | **PASS** for the observed PID, project argument, registration fields, and loopback listener |
| Authenticated native response | **PASS** for one `unreal_project_info` response |
| Correct ForgeMCP binary source | **PARTIAL** — project-local plugin binaries were loaded; they differ from the official Engine plugin binaries |
| Second read-only request and separate health check | **NOT RUN** — stopped after the response identified the excluded production level |
| Indicator behavior | **NOT VERIFIED** |
| Production-level access boundary | **STOPPED** after one metadata response; no package or asset inspection followed |

**Final verdict: BLOCKED.** Do not continue this verification against the current Editor while it is on `L_City_World_Master`. A follow-up requires a safe non-production project/session and an explicit instruction for that target. Production Phase 6C remains **NO-GO**.
