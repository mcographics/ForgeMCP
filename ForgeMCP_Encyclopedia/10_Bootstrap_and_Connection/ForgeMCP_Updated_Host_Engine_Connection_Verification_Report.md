# ForgeMCP updated-host engine connection verification

Date: October 22, 2026 (America/Toronto)  
**Result: Updated MCP host-to-engine communication PASS in one bounded session. Persistent Codex-owned tool attachment remains unresolved.**

The preferred Editor was reidentified as PID **18588**, created **2026-10-23T00:52:39.8121630Z**, using the official UE executable and `G:/ForgeMCP/ForgeMCPDev.uproject`. Its private registration matched **unreal-18588 / 127.0.0.1:64370**. Both IPv4 and IPv6 listener tables were queried; the only matching listener row was IPv4 loopback owned by PID 18588. No credential was displayed.

One real MCP client session launched the existing updated host using the installed MCP SDK stdio transport, the configured venv interpreter, source working directory **G:\ForgeMCP**, `-B -m server.main`, and `FORGE_PROJECT_ROOT=G:\ForgeMCP`. No source/configuration file or Python environment was changed. No production grant was supplied.

| Gate | Observed result |
|---|---|
| MCP initialize handshake | PASS — 3,500 ms, within the 20-second client bound |
| Actual tools/list | PASS — 114 registered tools |
| Updated authorization contract | PASS — actual preview-tool description contains the new host-configured exact session/project/world grant contract |
| Five Landscape tools | All present: inspect, preview, apply, job status and cancel |
| Explicit project_info | PASS — authenticated native response |
| Repeated project_info | PASS — second authenticated response |
| Project | ForgeMCPDev, G:/ForgeMCP/ForgeMCPDev.uproject |
| Engine | 5.6.1-44394996+++UE5+Release-5.6 |
| World | /Game/Levels/L_City_World_Master.L_City_World_Master |
| PIE | false |
| Preferred-session dirty inventory | PASS — complete scan, 1,174 loaded packages, one dirty package |

The one dirty package is **/Script/SlateCore**, classified engine_script and not associated with the current level. This is now a fresh result for **unreal-18588**, not a substituted result from the other Editor. The map was not listed dirty. Unloaded package state is outside the inventory.

The bounded MCP client context exited normally and its diagnostic parent exited 0. The final process check found no remaining standard `server.main` host; Editor PID 18588 remained running. No existing process was manually terminated. Native requests may briefly refresh the plugin's authenticated-activity indicator; visual color was not observed.

## Remaining client-integration boundary

This chat still has no ForgeMCP tool namespace managed by its owning Codex client. The successful SDK session was a real MCP handshake/catalog/tool exchange, but it was not attached to that client's existing transport. It must not be represented as a lasting repair of the chat integration or an indefinitely running connection.

The earlier owning-client 20-second handshake failure is **not reproduced by this controlled launch**. An explicit source working directory is a verified successful launch condition. The existing Codex configuration has no explicit cwd; whether the failed client used a different directory, environment or scheduling condition remains unproven. The evidence does not justify a plugin rebuild, Unreal restart, authentication change or timeout increase.

To restore persistent tool access, the owning client must launch/reconnect the existing forgemcp entry with the same verified interpreter/source resolution. An explicit cwd of G:\ForgeMCP is the narrow configuration clarification to review if its effective launch directory differs; no configuration change was made here because that restriction remains in force. A standalone persistent surrogate was not left behind to make the indicator look connected.

No Landscape preview/apply, grant, terrain edit, package save/discard, Editor lifecycle action or source/policy change occurred. Only this report and ordinary host runtime logging were generated. **Native/updated-host connection verified; chat-managed integration unresolved; SlateCore remains a separate creation blocker. Phase 6C remains NO-GO.**
