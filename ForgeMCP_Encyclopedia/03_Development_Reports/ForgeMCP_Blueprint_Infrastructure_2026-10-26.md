# ForgeMCP Blueprint infrastructure implementation and acceptance boundary

Date: 2026-10-26 (America/Toronto)  
Priority: P0 core infrastructure  
Status: **INCOMPLETE — inspection activation and native test passed; mutation and persistence work outstanding**
Repository: `G:\Unreal Engine Projects\ForgeMCP`  
Source baseline: `dceb5e1e` (`Add Blueprint Inspection functionality and associated tests`), plus the inspection hardening changes recorded below.

## Scope and decision

**Later October 26 status:** the subsequent scoped-journal full Editor build passed 37 actions, but its approved reopen failed in TedsOutliner startup while LevelEditor was unloaded. Both queued native tests were NOT RUN, and no connected Editor remains. The [latest progress matrix](ForgeMCP_Blueprint_Progress_Update_2026-10-26.md) and [activation failure record](ForgeMCP_Scoped_Blueprint_Activation_2026-10-26.md) supersede present-tense connection/activation claims below. This report retains the earlier successful inspection evidence as history.

This report covers the requested architecture audit and the first inspection implementation phase. It does not establish completion of the general Blueprint editing, component-template, Niagara, scoped journal, save, reload, or runtime requirements.

The owning Codex client's native ForgeMCP namespace is now available. Pre-activation `forge_list_sessions` and `unreal_project_info` calls verified the same connected session, `unreal-20136`, with this identity:

- Project: `G:/Unreal Engine Projects/ForgeMCP/ForgeMCPDev.uproject`.
- Engine: `5.6.1-44394996+++UE5+Release-5.6`.
- Level: `/Game/Levels/TestArea.TestArea`.
- PIE: stopped.
- Loaded adapter: `0.2.17-alpha.1`.

Before activation, the new Python inspection tools were discoverable, but the older loaded native adapter rejected `blueprint_capabilities` with `command_not_allowed`. Its health response did not advertise the five new inspection commands. This historical exposure blocker was resolved by the approved activation described below.

The user subsequently explicitly approved one controlled close, binary backup, build, and reopen of the same Editor. The initial no-automatic-restart boundary was preserved until that approval. No production Blueprint mutation or additional Editor session was authorized by that approval.

## Approved activation result

Subsequent source milestone: [scoped journal foundation](ForgeMCP_Scoped_Blueprint_Journal_Source_2026-10-26.md). That code is newer than the activated inspection DLL and has its own pending native gate. Full build/activation passes in this report apply to the preserved inspection-phase source and binary only.

The existing Editor (PID 20136) closed normally through its main window, without force termination. Ten plugin/project binary files totaling 215,446,649 bytes were copied with preserved relative paths and independently verified SHA-256 hashes. The original backups were verified again after the build. Both Codex configuration-file hashes remained unchanged.

`Build-ForgePlugin.ps1` completed successfully with the official UE 5.6.1 installation. Both plugin modules linked, and the final `ForgeMCPDevEditor` target passed all 38 actions. The project and plugin module BuildIds matched. The main built plugin DLL has SHA-256 `A56EAB1256F1101C060A09E041099A87FB2047D973B37D88F71271D5E39EB003`.

The project was reopened once on TestArea with only the exact inspection automation test queued. Fresh owning-client discovery and project-info calls verified `unreal-15036`, PID 15036, the same project, UE 5.6.1, TestArea, and PIE stopped. Loaded module paths match this project's plugin binaries. All five new inspection commands are advertised and `unreal_blueprint_capabilities` responds successfully.

`ForgeMCP.BlueprintInspection.LargeGraphPaginationAndTrace` **passed** in the reopened Windows Editor: 1 test succeeded, 0 failed, 0 warnings, 0 errors, duration approximately 1.024 seconds. This verifies the test's 1,001-node native handler enumeration and its filtering, traversal, and negative cursor/identity cases. It does not establish the unimplemented authoring, Niagara, save/reload, full fixture, runtime, or production requirements. Separate owning-client MCP pagination against a retained disk-backed fixture remains to be exercised.

The post-test complete dirty inventory again reported only `/Script/SlateCore` as an engine script package, with no dirty project Content packages and no further pages. A pre-existing missing `TestArea_HLOD0_Instancing` load warning also occurred before this activation; no recovery or asset deletion was performed.

Curated evidence: [activation and native automation result](../04_Testing_and_Validation/ForgeMCP_Blueprint_Inspection_Activation_2026-10-26.json). Raw lifecycle manifests, before/after binary hashes, source hashes, build transcript, Editor log snapshots, and native automation `index.json`/`index.html` remain local under `Saved/ForgeBuild/BlueprintInspectionActivation-20261026T012939`.

## Architecture audit and original root causes

| Area | Existing implementation and limitation | Consequence |
| --- | --- | --- |
| Blueprint inspection | `ForgeBlueprints.cpp::Inspect` returns at most 64 graphs and 128 nodes per graph. It reports truncation but has no continuation cursor. | An 850-node EventGraph cannot be completely enumerated through that response. |
| Edit snapshot | `ForgeBlueprintEdits.cpp::Snapshot` requires at most 512 variables, 512 SCS nodes, 64 graphs, 512 nodes per graph, and 8,192 total pins. | An unrelated large graph blocks a small edit before operation validation. |
| Snapshot representation | Preview serializes the full asset state plus Blueprint/world instance identities. A missing complete graph snapshot or a serialized fingerprint length above `4*1024*1024` produces `asset_too_large`. The check is on `FString` character length, despite the diagnostic saying MiB. | Raising an MCP response limit alone cannot repair the editing architecture. |
| Preview and apply | Process-local preview records contain recipe, full fingerprint, and a 600-second expiry. Maximum 32 outstanding previews. Apply consumes a preview and requires `confirmation == preview_id`. | Replay/stale-state checks exist, but there is no scoped before-state journal or independently verified binary package backup. A preview ID is not independent evidence of human authorization. |
| Legacy operations | Move a node, set primitive input defaults, connect/disconnect pins, remove selected allowlisted node kinds; add bounded variables, components, typed functions, and nodes. | This is a bounded recipe system. It is not a general reflected Blueprint editor. Existing variable-definition edits and arbitrary function/macro modifications are not supplied. |
| Node/function construction | Branch, Sequence, Self, Reroute, event/custom event, variable get/set, selected function calls, and new function entry/result references. Function calls use class/name resolution plus a fixed native allowlist. | Niagara `SetAsset` is not covered. Display titles are not suitable identifiers. Special graph/node types need explicit adapters. |
| Connection handling | Apply uses native `TryCreateConnection`. Preview checks exact endpoint names and the narrow node allowlist. | A general patch layer still needs explicit handling of schema responses that would replace existing links; silent replacement must be rejected or included in the reviewed change set. |
| Transactions and recovery | `FScopedTransaction`, a full JSON recovery snapshot under `Saved/MajesticForge/Recovery`, retained removed-node objects, reconstruction rollback, and recovery compilation. | Rollback is broad rather than scoped. The snapshot does not preserve every class-specific property. It is not a verified original package backup. |
| Compile/save | Existing edits compile in memory and report diagnostics and `saved:false`. New-Blueprint creation has a separate optional `UPackage::SavePackage` path. | Existing-asset edits lack an approved save workflow, package hashes/backups, independent unload/reload, and runtime proof. |
| Components | Own SCS component enumeration and restricted mobility/static-mesh material settings; actor-instance component property tools are separate. | No complete inherited/native/generated-class default source model, typed Niagara assignment, or safe inherited override workflow. |
| Transport | Request cap 512 KiB, native response cap 1 MiB, matching Python bridge bounds. The old native path closes the client on an oversized reply. | A client can receive a generic closed/invalid response instead of an actionable size error. |

These findings are source/configuration evidence. Historical native tests of other features do not verify this implementation.

## Implemented inspection changes

`ForgeBlueprintInspection.h/.cpp` add read-only, game-thread inspection commands:

| Native command | MCP tool | Request and response contract |
| --- | --- | --- |
| `blueprint_capabilities` | `unreal_blueprint_capabilities` | Session-specific capability registry with exact `PARTIAL`, `UNSUPPORTED`, and `BLOCKED` states; it does not hardcode unearned runtime passes. |
| `blueprint_graph_list` | `unreal_list_blueprint_graphs` | Exact `/Game` package selector; graph path, name, type, schema/class, valid node count, null slots, and invalid-GUID counts. All metadata is returned if it fits; otherwise an explicit `graph_list_too_large` error is returned. |
| `blueprint_graph_page` | `unreal_page_blueprint_graph` | One exact, unambiguous graph name; 1–64 nodes per page (default 32); optional GUID/class/title/function/comment filters; exact matching-node total, returned count, offset, fingerprint, continuation cursor, and explicit truncation metadata. |
| `blueprint_node_inspect` | `unreal_inspect_blueprint_node` | Exact unique NodeGuid; reflected properties and 1–128 pins per page (default 32); pin IDs, types, defaults, object references, linked endpoints, integrity flags, and continuation metadata. |
| `blueprint_graph_trace` | `unreal_trace_blueprint_execution` | Exact unique start GUID; forward/backward/both execution traversal, depth 0–32 and node limit 1–512; identified source/destination endpoints, deduplicated edges, and explicit boundary flags. |

Node ordering uses NodeGuid, with object-path fallback where the GUID is absent. Returned identities never use pagination offsets as permanent node identities. Pin cursor offsets are internal, short-lived positions revalidated against the same graph and node objects and a revision fingerprint before use. UE 5.6 graph pins are not UObjects, so the implementation does not store them in `TWeakObjectPtr`.

Graph fingerprints include persistent reflected graph/node properties, positions/comments, pin order/types/defaults, object/text defaults, and sorted link endpoints. Cursors expire after 300 seconds and are bounded to 24 cached inspections; expiry, eviction, incompatible selectors, object replacement, and state changes fail explicitly. MD5 is used as an in-process revision marker, not as authorization or a package-backup hash.

Native inspection replies target a 768 KiB data budget. Node and pin pages shrink to fit that budget. A single oversized detail returns an error. The module now returns a structured `response_too_large` failure with the original request ID rather than silently dropping an oversized response. The existing authenticated loopback transport and original tools are retained.

Additional hardening after `dceb5e1e` rejects duplicate graph names and duplicate NodeGuids for individual selection, adds an explicit `default_text_truncated` flag, and enforces the data budget even when a node has zero pins.

### Current inspection limitations

- Graph-list metadata itself has no continuation cursor; unusually large graph indexes return an explicit error.
- Reflected properties are capped at 256 entries and 4,096 characters per value. Each cap is reported. Property inspection does not imply permission or support to mutate that property.
- A pin with an exceptionally large fan-out has no separate link cursor and can return `pin_detail_too_large`.
- Title, comment, default-value, and default-text length limits are explicit. Full arbitrary property/default export is not implemented.
- Function and macro targets are resolved and reported where available. Cross-graph execution traversal is not implemented.
- `unresolved` pin diagnostics currently identify a missing pin category. They are not a complete dependency or missing-asset validator.
- Graph names must be unique for this API. Ambiguous names return `ambiguous_graph`; selection by full graph path is a future extension.
- Special graph classes can expose generic reflected inspection, but no dedicated animation, rig, state-machine, or other special mutation adapter has been added.
- A graph fingerprint is recomputed for each continuation request. Latency and memory scaling have not been measured.

## Files and compatibility

The initial inspection implementation is in commit `dceb5e1e`:

- `Plugins/Forge/Source/MajesticForge/Private/ForgeBlueprintInspection.h`
- `Plugins/Forge/Source/MajesticForge/Private/ForgeBlueprintInspection.cpp`
- `Plugins/Forge/Source/MajesticForge/Private/ForgeBlueprintInspectionTests.cpp`
- `Plugins/Forge/Source/MajesticForge/Private/MajesticForgeModule.cpp`
- `server/core/blueprint_inspection.py`
- `server/core/connections.py`
- `server/main.py`
- `tests/test_blueprint_inspection.py`
- `tests/test_mcp_stdio.py`

This continuation adds the selection/budget hardening and native negative cases in the two inspection `.cpp` files, this report, and Encyclopedia evidence entries. No existing mutation recipe was rewritten. Old tools and schemas remain available. New Python tools require the corresponding rebuilt native adapter; an old adapter explicitly rejects those commands.

No engine installation, production asset, level, plugin preference, registration token, recovery checkpoint, or unrelated file was moved for documentation. No source was published by this task.

## Fixture and validation

The native automation test `ForgeMCP.BlueprintInspection.LargeGraphPaginationAndTrace` constructs an in-memory transient `/Game/ForgeMCPTests/BlueprintInspection/BP_InspectionFixture_<guid>` package. Its EventGraph contains 1,000 branch nodes plus one custom event (1,001 nodes). A three-node synthetic execution chain uses comments identifying input/acceleration/deceleration fixture roles. Native schema APIs create its connections.

The test is designed to check full enumeration, no duplicate/missing GUIDs across pages, exact counts, explicit pagination status, targeted comment discovery, forward/backward/both traversal, deduplicated edges, graph and pin cursor invalidation, duplicate-GUID rejection, and duplicate graph-name rejection using a nested graph. It does not save any package or modify the active world.

This inspection-only fixture has now passed in the Editor. It is not the complete requested authoring/persistence fixture: Niagara templates, inherited cases, variables, representative functions, actual activation behavior, scoped mutations, compile-failure/rollback tests, semantic before/after preservation checks, explicit save, and independent reload remain outstanding. Synthetic labels do not demonstrate production acceleration or braking behavior.

| Evidence gate | Result |
| --- | --- |
| Python lint | PASS: `python -m ruff check server tests`. |
| Python automated tests | PASS: 565 tests, including typed request validation, read-only dispatch, real MCP stdio tool discovery, and existing regression coverage. This is not native Editor regression proof. |
| UE installation identity | VERIFIED from official installed `Engine/Build/Build.version`: UE 5.6.1, changelist 44394996, `G:\Program Files\EpicGames\UE_5.6`. |
| UBT header/build-graph generation | PASS in the earlier full-build attempt. |
| Inspection and native test compile | Selected translation units compile using UBT-emitted response files and installed MSVC 14.38.33130; final hardening recompilation recorded in local logs. No linker is invoked for these checks. |
| Module compile | PASS: `MajesticForgeModule.cpp` compiler exit 0. |
| Full native plugin/editor target | PASS after the authorized normal close. The earlier `LNK1104` against the loaded DLL is preserved as historical evidence and superseded for this activation. |
| Owning-client MCP discovery and identity | PASS: fresh native tools returned connected `unreal-20136` and the exact project identity above. |
| New command exposure in loaded DLL | PASS: new session `unreal-15036` advertises the commands and returns the capability registry through the owning client's tools. |
| 850+/1,001-node native enumeration | PASS in the inspection automation fixture. Retained-fixture MCP socket pagination is a separate outstanding check. |
| Native graph traversal and stale-cursor tests | PASS in the inspection automation fixture, including forward/backward/both, stale graph/pin cursors, duplicate GUIDs, and ambiguous graph names. |
| Scoped patch, rollback, Niagara, explicit save, reload, PIE | NOT IMPLEMENTED / NOT RUN. |
| Existing native capability regression | NOT RUN for the new binary. |

Local build evidence is retained in `Saved/ForgeBuild`, including `InspectionGate-*.stdout.log`, corresponding stderr logs, and timestamped `BlueprintInspection-20261026T010743-*` compiler logs. Initial missing-include errors were corrected before successful compile-only validation. Source compile is a distinct gate from linking, loading, native automation, persistence, and runtime behavior.

## Capability matrix

`VERIFIED` below always names its evidence scope; it does not imply universal Blueprint support.

| Capability | Classification | Evidence / remaining requirement |
| --- | --- | --- |
| New Python schema validation, dispatch, and stdio discovery | VERIFIED | Python test and lint gates. |
| Current native session identity | VERIFIED | Owning-client discovery plus project-info response for the same live ID. |
| Paged graph/node/pin inspection implementation | PARTIAL | Native source compiles; live acceptance and listed limits remain. |
| Complete 850+ node enumeration in the native fixture | VERIFIED | 1,001 nodes enumerated exactly once in the successful Editor automation test. |
| Intra-graph execution traversal | PARTIAL | Implemented and compiled; native fixture execution pending. |
| Cross-graph function/macro execution traversal | UNSUPPORTED | Reference readback only. |
| Legacy bounded Blueprint authoring/editing | PARTIAL | Existing allowlists and whole-asset snapshot requirements remain. No new native regression result. |
| General reflected function-call creation including Niagara SetAsset | UNSUPPORTED | Fixed legacy function allowlist remains. |
| Scoped reversible change journal and verified package backup | UNSUPPORTED | Must be implemented before large-asset mutation acceptance. |
| Own SCS mobility/static-mesh material edits | PARTIAL | Existing narrow implementation; not revalidated here. |
| Niagara template assignments and inherited overrides | UNSUPPORTED | New component-default identity and override layer required. |
| Existing Blueprint approved save and independent reload | UNSUPPORTED | Legacy edit path reports `saved:false`. |
| Native activation and full Editor-target acceptance | VERIFIED | Approved close/backup/build/reopen; successful target, fresh identity, loaded paths, and command response. |
| Runtime Niagara switch/restoration behavior | BLOCKED | Infrastructure and disposable fixture acceptance have not passed. |
| ViperBP readiness | BLOCKED | No production inspection/change preview authorized by passing infrastructure gates yet. |

## Safety state and next gates

The read-only dirty-package scan examined 1,309 loaded packages. It was complete, reported one dirty package, and had no additional pages or inspection errors. The sole dirty package was `/Script/SlateCore`, classified as a compiled-in engine script package; no dirty project Content package was reported. Unloaded packages were not inspected. Refresh this inventory immediately before any lifecycle or mutation step; this result is not a blanket future clean-state assertion.

The approved controlled lifecycle step is complete. The Editor is running on TestArea. The one-reopen authorization has been used; no further restart is implied. Any later native activation requires another explicit lifecycle authorization or a manual owner close. Do not use Live Coding to conceal a module-layout/activation boundary.

Fresh session identity, loaded command exposure, native fixture enumeration, tracing, and stale-cursor checks have passed. Retain these proof scopes separately from the later complete fixture's end-to-end MCP and disk-backed checks. The capability registry remains conservative and does not automatically promote support based on a test report; its pending-validation wording is not a dynamic test-status feed. Failure at any later gate blocks production changes.

Only after that gate passes should development proceed in this order:

1. Typed operation/capability adapters and a graph patch composed of independently validated operations. Resolve exact UFunctions, signatures, contexts, pin IDs/types, and schema compatibility; require explicit reviewed replacement links.
2. Scoped before-state journals with exact preconditions, separate verified original-package backups, safe scoped restoration checks, compile diagnostics, and untouched semantic comparisons. Reject stale previews without mutation.
3. Blueprint component-default enumeration/source identity, typed property references, own and inherited override handling, and Niagara System assignments without modifying parent Blueprints.
4. Generic callable-function construction for Niagara `SetAsset`, `Activate`, and `Deactivate`, including reset semantics and each component's distinct original System.
5. Approved save preview/apply with exact package path, dirty state, backup path/hash, and independent disk-backed verification. Report reload as blocked when safe unload cannot be established.
6. Complete the disposable 1,000+ node multi-graph/function/Niagara/inheritance fixture; run all failure, rollback, preservation, save/reload, and runtime acceptance gates.
7. Only then inspect ViperBP read-only and prepare the exact Boost/Afterburn change preview. Production Apply still requires separate explicit authorization.

## ViperBP boundary

No ViperBP asset was loaded, inspected, changed, compiled, saved, reloaded, or run by this work. The paths and actual behavior of ThrusterT, EngL, EngR, existing Cascade systems, input/acceleration/braking chains, and `NS_RocketExhaust_Afterburn_Jet` remain unverified. No original Niagara System references have been inferred. Production readiness is **NO-GO** until the reusable infrastructure and complete disposable fixture pass their acceptance gates.
