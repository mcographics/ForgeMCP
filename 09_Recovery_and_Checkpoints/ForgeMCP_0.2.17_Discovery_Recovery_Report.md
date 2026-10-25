# ForgeMCP 0.2.17-alpha.1 — Post-deployment MCP discovery recovery

Checked: October 23, 2026, 17:22 EDT (21:22 UTC).
Final verdict: **CONNECTED — ALL FIVE TOOLS VERIFIED**

This verdict covers current MCP registration, actual Codex callable exposure, schema retrieval, and authorized read-only native inspection. Request/revocation lifecycle execution and production sculpt acceptance remain untested in this recovery.

## Connection and configured host

The configured server is `forgemcp` in `C:/Users/Kenne/.codex/config.toml`: command `G:/ForgeMCP/.venv/Scripts/python.exe`, arguments `-m server.main`, project root `G:/ForgeMCP`. Configuration was read without modification or credential disclosure.

Fresh calls through this conversation's ForgeMCP connector authenticated the existing session `unreal-43744`, PID 43744. `unreal_project_info` confirms `G:/ForgeMCP/ForgeMCPDev.uproject`, level `/Game/Levels/L_City_World_Master.L_City_World_Master`, UE `5.6.1-44394996+++UE5+Release-5.6`, and PIE stopped. Native health reports `0.2.17-alpha.1`. `forge_status` returns ok=true and one connected session.

Version identifiers are separate: native adapter `0.2.17-alpha.1`; forge_status's Python host version `0.3.15`; diagnostic MCP initialize serverInfo.version `1.30.0`. Native version proof comes from the authenticated Unreal health response.

## Host and Codex inventories

A fresh separate stdio client used the configured command, arguments and environment to initialize ForgeMCP and request tools/list. It returned **121 tools** and JSON input schemas for all five interfaces. No tools/call was issued through that diagnostic subprocess. This is a fresh host-registration check, not a refresh or interception of this conversation's existing MCP transport.

This conversation's actual ALL_TOOLS catalog independently exposes **121 ForgeMCP tools**. After removing the client namespace prefix, the complete host and client name sets match exactly: **zero host-only tools, zero client-only tools**. All five target names resolve to callable functions in the current tools namespace.

| Registered MCP name | Host schema | Current Codex callable | Execution in this recovery |
|---|---|---|---|
| unreal_landscape_edit_session_preflight | Retrieved | Yes | Successful native read-only response |
| unreal_request_landscape_edit_session | Retrieved | Yes | Not invoked; would register a pending request |
| unreal_landscape_edit_session_status | Retrieved | Yes | Not invoked; no existing editing-session ID |
| unreal_revoke_landscape_edit_session | Retrieved | Yes | Not invoked; permission mutation outside inspection |
| unreal_read_landscape_height_region | Retrieved | Yes | Successful native read-only response |

Codex names have the prefix `mcp__forgemcp__`. Preflight/request use `LandscapeEditSessionRequest`; status/revoke use `LandscapeEditSessionReference`; bounded read uses `LandscapeHeightRegionRequest`. Every schema requires `request` and explicit `session_id`. Full schemas and both complete inventories are in the companion JSON evidence file.

The earlier 116-tool / zero-of-five result is historical. All five are available now. The precise event that refreshed the catalog was not observed, so no cause is asserted. No connection refresh or manual client action was required in this turn.

## Read-only Landscape and riverbed verification

Landscape GUID: `BD45FDD94EC2A29617B50794F2DE4E9D`.
Actor: `/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295`.

| Check | Current result |
|---|---|
| Dimensions | 2041 x 2041 |
| Original layer name / GUID | Layer / 198824024FF8A77A01535B86021D9B34 |
| Original full height MD5 / min-max | 9f43572fbc2c06ef497da015879cdb23 / 0 to 0 cm |
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B |
| ForgeTerrain full height MD5 / min-max | dd428766880ec01a848b4381fba82838 / -100 to 0 cm |
| Layer settings | Both visible and unlocked |
| Loaded / unloaded streaming proxies | 16 / 0 |
| Registered Landscape / collision components | 64 / 64 |
| Landscape dirty / layers up to date | false / true |

These identity, hash, elevation and topology values match the supplied activation baseline.

The newly exposed bounded-read tool successfully read inclusive saved riverbed bounds `[1054,1066,1086,1074]`: **33 x 9 = 297 samples**, min **-100 cm**, max **0 cm**, region height MD5 `08d6ac338669dfa1918c1644ce374ef8`. The response explicitly identifies edit-layer data, not composed terrain or collision, and read_only=true.

The newly exposed preflight was called for the earlier proposed bounded region `[1116,1116,1132,1132]`, actions raise and smooth, exact current project/PID/actor/layer identity, and 7200-second requested lifetime. It returned ok=true, read_only=true, potentially_adoptable=true, target_layer_ready=true, backup_scope_readable=true (23 source files), no readiness blocker string, and **requests=[]**. It also returned **checkpoint_source_clean=false**. This inspected a proposal; it did not register or approve a session, create a checkpoint, or validate an operation-specific preview/halo.

## Separate editing-readiness finding

A complete current loaded-package snapshot inspected **1183 packages**, with no inspection errors or further pages. Four dirty packages remain: three production Content packages and compiled-in engine-script `/Script/SlateCore`.

- `/Game/UltraDynamicSky/Blueprints/Ultra_Dynamic_Weather`
- `/Game/__ExternalActors__/Levels/L_City_World_Master/9/UX/QWIT4Q5JJ8585ENBY5400I` — existing Ultra Dynamic Weather external actor
- `/Game/__ExternalActors__/Levels/L_City_World_Master/C/L1/9FKOG7WXO3MCN53CTMWDWE` — newly created Ultra Dynamic Weather external actor

No cause is inferred. No package was saved, restored, or cleared. Loaded-package inspection does not classify unloaded packages as clean. An initial limit=100 inventory call was rejected by validation; the supported limit=50 call succeeded.

## Recovery outcome and limits

There is **no remaining MCP discovery blocker**, and no manual client refresh is needed. The current evidence does not establish whether the previous catalog was stale due to a particular refresh event.

No build, deployment, binary replacement, Unreal restart/launch, UI automation, client reconfiguration, editing-session request/revocation, terrain operation, or project asset save occurred. Only this new report and its companion evidence JSON were deliberately written by the recovery work; routine host diagnostics may be emitted by the existing server.

The dirty production state and checkpoint_source_clean=false remain separate gates before editing acceptance. Request/status/revocation lifecycle behavior, production World Partition multi-operation edits, collision behavior and disk reload acceptance were not exercised.

Evidence: [ForgeMCP_0.2.17_Discovery_Recovery_Evidence.json](ForgeMCP_0.2.17_Discovery_Recovery_Evidence.json).

