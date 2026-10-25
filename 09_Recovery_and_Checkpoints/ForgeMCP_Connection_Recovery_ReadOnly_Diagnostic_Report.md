# ForgeMCP connection recovery — read-only diagnostic

Date: October 22, 2026, America/Toronto  
Observation cutoff: October 23, 2026, 01:20 UTC  
**Verdict: Native connectivity PASS; Codex MCP connection BLOCKED by absent connected host/tool integration. No fixes implemented.**

## Current identity and connection

Two official UE 5.6.1 Editors are running the same `G:/ForgeMCP/ForgeMCPDev.uproject`. Read-only authenticated project-info replies confirmed **both** are currently on `/Game/Levels/L_City_World_Master.L_City_World_Master`, with PIE false:

| Editor PID | Creation UTC | Session | Verified loopback endpoint |
|---|---|---|---|
| 5028 | 2026-10-23 00:43:20.822941 | unreal-5028 | 127.0.0.1:59421 |
| 18588 | 2026-10-23 00:52:39.812163 | unreal-18588 | 127.0.0.1:64370 |

Each process uses the official `G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe` and has the project-local Forge Editor/Runtime modules mapped. Each private registration matches its PID/session/endpoint, protocol version 1, has a token, and has protected ACL inheritance. IP Helper queries of both IPv4 and IPv6 listener tables found only the expected PID and IPv4 loopback row at each port. Tokens were never emitted or copied.

No process matching the standard ForgeMCP `python -m server.main` host invocation was found. The previously observed host PIDs 4480/25964 are no longer present in that host inventory. This chat exposes **no ForgeMCP MCP tools**. Thus no currently connected MCP host can be demonstrated to have loaded any authorization code.

To distinguish a missing MCP host from a native/authentication failure, one transient Python diagnostic reused the existing ConnectionManager for explicit read-only requests. It was not an MCP server, launched no background monitor, used no mutation commands, and exited normally. Both project-info replies succeeded; PID 5028 also returned authenticated health and a complete dirty-package snapshot. This proves the native endpoints and credentials worked at inspection time, not that Codex's MCP transport has been restored.

## Red indicator

Confirmed source logic: **red** means no bridge listener or no authenticated request since that bridge's last initialization; **green** means authenticated activity within six seconds; **yellow** means older authenticated activity with a listener still present. Simply losing a host after prior authentication should produce yellow, not necessarily red.

Both listeners and authentication worked during this diagnostic. No LogMajesticForge authentication error was found in the relevant bounded log inspection; both logs record their bridge-ready messages. The reported earlier red dot is **not conclusively attributed**: waiting for a client after bridge initialization/restart, observing a different Editor, or a prior stopped-bridge state remain possible. The native internal activity timestamp and the actual rendered dot were not inspected. Diagnostic requests refresh that timestamp, so this was not a passive reproduction of the original red state. Source predicts brief green followed by yellow without continuing host activity; visual behavior is unverified.

## Updated authorization and Landscape registration

The on-disk `server/main.py` and `server/core/landscape_authorization.py` hashes still match the implementation report (`4312B6D9…078D90` and `29DC919F…28170D`). Source inspection confirms the private authorization injection and all five MCP wrapper definitions:

- unreal_inspect_landscape
- unreal_preview_landscape
- unreal_apply_landscape
- unreal_landscape_job_status
- unreal_cancel_landscape_job

Authenticated native health advertises the corresponding five native commands. **Current live MCP registration/accessibility remains unverified because no connected host/tool integration is available.** No preview, apply, cancellation or job operation was executed to test registration. The transient connection diagnostic does not establish a refreshed MCP host.

## SlateCore

For **unreal-5028**, the native scan inspected **1,164 loaded packages**, reported `inventory_complete=true`, and returned exactly one dirty package: **/Script/SlateCore**, classified as engine_script, with zero associated actors and no current-level association. The city map was not returned as dirty. Unloaded packages were not classified, and PID 18588's dirty state was not queried.

This condition persists in the city session and is separate from the connection issue. It would still block the implemented existing-world creation apply policy. Nothing was saved, discarded, marked clean or exempted.

## Smallest next actions

1. Reconnect/start the existing ForgeMCP MCP integration through its owning client so it launches the current `G:\ForgeMCP` Python source. Do not rebuild or restart Unreal to solve this demonstrated host/tool gap. Then verify the updated authorization schema and all five tools through that actual connection.
2. Choose one explicit session for future work; two city Editors are open. Neither should be closed or altered automatically.
3. Address SlateCore separately through an explicitly authorized, narrowly scoped policy review or other evidence-supported remedy. Do not clear its dirty flag or weaken package protections as a connection workaround.

Only this report was created. No host was persistently started or terminated, no Editor restarted, no source/configuration/policy changed, no grant configured, and no asset or level saved or modified by the diagnostic. No full filesystem preservation audit was run. **Production Landscape creation remains blocked; Phase 6C remains NO-GO.**
