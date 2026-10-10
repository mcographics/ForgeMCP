# Roadmap implementation status — October 9, 2026

The full user goal remains active. The original roadmap is preserved as supplied.
Version 0.2.0 is concrete progress, not completion of universal Unreal/Blender control.

| Requirement | Authoritative current evidence | Remaining work |
| --- | --- | --- |
| Original server, adapters, provider-independent MCP | Original source, official MCP SDK, separate authenticated native runtimes; stdio tests | Broader client acceptance |
| Codex foundation inspection | Five original tools previously accepted in the IDE; retained in current tool registry | Reload the extension for current 23-tool development registry |
| Secure local endpoints and panels | Native panels, loopback listeners, protected token files, bounded parsing, allowlists | Continued adversarial tests as operations expand; interactive panel QA |
| Blueprint create/compile/place | Live guarded MCP proof created `/Game/ForgeValidation/BP_ForgeProof_6e09960d`, compiled with 0 errors/0 warnings, saved a 43,821-byte asset, placed its actor in the isolated editor world | PIE/gameplay execution proof and repeat clean-project acceptance |
| Variables/components/functions/nodes/pins | New Blueprint recipes support typed function input/output signatures and pure functions; existing-asset primitive variable/native component/node additions, GUID-based rewiring, movement/default edits, compile and rollback proof | Editing/removing existing members, function/signature changes on existing assets, richer pin types, broader safe node families |
| GAS | Typed setup for new Blueprints; persistent ASC replication-mode config; live MCP inspection of an isolated placed actor validated | Gameplay Ability/AttributeSet/GameplayEffect asset authoring, deeper ability/tag/effect operations, full PIE/network gameplay acceptance |
| Actors, assets, levels, materials, UMG, World Partition, PCG | Actor inspection, Blueprint asset creation/placement, native class metadata; native Asset Registry search/metadata/package references | Broad actor/world control, asset mutation/import, material/UMG graph editing, partition/data-layer/PCG operations |
| Unreal skeletal/animation/retarget assets | No asset-specific implementation | Inspect/edit/import/retarget workflows and acceptance |
| Blender object/mesh/material/collection/rig inspection | Factory scene inspection and live MCP proof of armature hierarchy and bounded skin-weight summaries; pose channels exposed by rig inspection | Rig/weight editing, large geometry, modifiers, material graph structure edits, broader object operations |
| Blender animation/timing | Transform keyframes, native evaluated playback at frames 1/30, 30 FPS; reviewed pose-bone location/Euler/quaternion/scale keyframes | Rig/weight editing, retargeting, richer Action/layer operations and cross-application acceptance |
| Recovery and authorization | Expiring single-use previews, explicit confirmations, stale scene checks, Blueprint scratch discard; native Blender rollback fault injection passed | Durable operation history/backup management, more failure modes and higher-impact previews |
| Cross-application transfer | Not implemented | Shared manifests, scale/coordinate/skeleton/material checks, explicit export/import transactions and partial-failure reports |
| API retrieval / RAG | Version-scoped local SQLite retrieval; installed Unreal Python stub and native bpy metadata indexed; no source execution | Expand retrieval evaluation and link retrieved APIs to operation capabilities; governed scripting remains typed native recipes |
| Packaging/setup | 0.2.0 ZIP integrity/secret-exclusion check passed; Blender 0.2.0 installed on disk and native UI lifecycle verified | Activation in original sessions, repeatable clean setup, distribution strategy |
| Publication/license | No publication or distribution license selected | Requires a separate user request |

At this earlier checkpoint, the automated Python suite had 36 passing tests, including real MCP subprocess
discovery, annotations, schema validation, security, and version-scoped retrieval.
Native Blender recipe verification prints
`FORGE_NATIVE_BLENDER_RECIPES_PREVIEW_APPLY_KEYFRAMES_BACKUPS_STALE_REPLAY_ROLLBACK_PASS`.
Native Unreal compilation/linking and final editor target verification succeeded.
The guarded live MCP engineering test prints
`FORGE_LIVE_MCP_BLUEPRINT_COMPILE_SAVE_PLACE_GRAPH_ROLLBACK_AND_BLENDER_RECIPES_PASS`.
Token-free results are in `Saved/Milestone2/engineering-live-report.json`.

Both 0.2.0 adapters passed authenticated rejection probes for bad tokens, unsupported
protocol/argument types, deeply nested JSON, oversized input and arbitrary execution
commands, and remained responsive afterward. The foundation subprocess report now
explicitly proves both adapter versions are 0.2.0. Version-scoped API retrieval through
MCP passed for `unreal.Actor.set_actor_location` (5.6.1) and `bpy.types.Mesh.from_pydata`
(5.2.2), and rejected an unindexed version. The local index contains 62,389 Unreal
chunks and 223,648 Blender reference entries. It is excluded from packages and Git.

Original milestone package (pre-branding refresh): `Artifacts/MajesticForge-0.2.0-UE5.6.1-Win64.zip`. SHA-256:
`754B305D4669C1359A130DA44AE8E50990DE92F3131306630CA49CAF2B7EBA3E`.
No Unreal Automation Test suite, PIE gameplay execution, broad end-to-end pipeline,
or interactive visual acceptance has been completed for this engineering milestone.

## ForgeMCP Unreal display-name refresh — 2026-10-09

The Unreal project's enabled plugin descriptor now advertises `ForgeMCP`; the native
Window menu entry, connection tab, panel title, adapter metadata, and transaction labels
use the same product name. The editor target compiled successfully after these source
changes. The older versioned ZIP and historical staged copies still contain the earlier
display name and remain untouched. A separate development package is staged from the
current descriptor, source, and compiled UE 5.6 Win64 editor binary at
`Artifacts/ForgeMCP-development-0.2.0-UE5.6.1-Win64.zip`; the default Unreal installer
now selects that package and rejects packages with a different display name. The editor
was closed during this refresh. Reopen `ForgeMCPDev.uproject` and choose
**Window > ForgeMCP** to activate the panel. The package SHA-256 is
`9017B585DF7482DD7D8AAE1B9291761C89CD701C06B5AAF1EE8C64C3EBABF147`. Installation into
ForgeMCPDev was verified: its descriptor reports `ForgeMCP`, its plugin entry is enabled,
and the installed DLL matches the staged build. No live Unreal UI click-through was performed.

The MCP subprocess verifier now explicitly forwards session environment variables.
A target-identity assertion exposed an earlier verifier mistake before any mutations
reached the original project; the earlier security record was corrected. The current
engineering proof uses only the guarded isolated project and factory Blender scene.

Original open application sessions were preserved. Updating source on disk does not
update loaded adapters; activation must be reported separately from build evidence.

## Public Unreal-MCP reference audit — 2026-10-09

The requested comparison with aadeshrao123/Unreal-MCP is recorded in
[the complete command comparison](Reference_Audits/Unreal_MCP_Comparison.md), with
[machine-readable signatures](Reference_Audits/Unreal_MCP_Commands.json) and
[CSV inventory](Reference_Audits/Unreal_MCP_Commands.csv). The snapshot is pinned to
`dadf24f460da4249ce7d94ee23a025b0b6e5cdff` and was inspected statically, never executed.
It contains 287 decorated registrations, 286 distinct names (duplicate `spawn_actor`),
and an additional transport-only `ping`. Against current Forge source: one operation
has equivalent inspection purpose, 25 have partial coverage, 260 registrations have
no corresponding operation, and arbitrary `execute_python` is intentionally excluded.
These are registration counts, not a percentage of semantic feature parity.

This audit adds a reference backlog; it does not implement the missing capabilities
or change the original implementation/security requirements. Downloaded source stays
under ignored `Saved/ReferenceAudits`, outside Forge runtime dependencies and packages.
The initial documentation-only audit passed Ruff and 31 Python tests; later asset
query implementation increased partial coverage by four reference registrations.
The audit remains static inspection of the reference, not a live test of its plugin.

## Asset discovery and Blender shader graphs — development continuation

The current source exposes 16 MCP interfaces. New Unreal `unreal_search_assets` and
`unreal_inspect_asset` use native registry APIs without loading/changing assets. New
Blender `blender_inspect_material` reads shader graphs; `create_material` recipes now
construct bounded native shader nodes/defaults/links on new materials only.

The Unreal editor target compiled and linked successfully after exact JSON type
checks were added. Guarded live MCP probes used only
`Saved/Milestone2/HostProject/ForgeEngineeringCheck.uproject` and factory Blender.
They verified class/path asset filters, package/object-path metadata, pagination,
empty results, native malformed-input rejection and 16-tool discovery. Inspecting
the installed engine WorldGridMaterial returned three package dependencies and 93
referencers, with both result sets correctly truncated at a requested limit of one.
MCP also created a Noise → Principled BSDF → Material Output graph and verified its
three nodes, two valid links and numeric defaults. Token-free evidence is in
`Saved/Milestone2/assets-materials-live-report.json`.

Native Blender graph tests passed script-node/cycle/duplicate-input rejection,
reviewed creation, defaults, links, replay rejection and rollback of the whole batch
after an invalid socket. RGBA socket defaults also passed through the authenticated
native request parser; a tenth nesting level was rejected (Blender's fixed limit is
nine, versus eight for Unreal).
The prior native scene/keyframe/copy/stale-preview/rollback checks also passed.
Both live adapters passed bad-token, arbitrary execution, malformed protocol/args,
deep JSON and oversized-input rejection probes and remained responsive. Ruff passed;
the current Python suite has 32 passing tests.

The installed Blender add-on files now match development source, including the new
`materials.py`; changed modules were backed up. The original live Unreal and Blender
sessions still report adapter 0.1.1 and were preserved. Development source and live
activation are separate. The existing 0.2.0 ZIP remains unchanged and predates these
capabilities. An unreleased development Unreal plugin is staged at
`Artifacts/MajesticForge-development-assets-materials/MajesticForge`; its DLL matches
the live-validated binary (SHA-256
`bb0d1a3585a1c754205e1a24f4099a93c7fbc8a2366e7e993cd7d9a1bee097e2`).
The development adapter version label remains 0.2.0; this staging directory is not a
new versioned release. Only isolated probe processes were stopped afterward.

No new interactive UI acceptance or gameplay proof was performed. Existing Unreal
asset mutation, existing Blueprint editing, GAS, Unreal material graphs, UMG,
World Partition, Niagara, StateTree, rigging and interchange remain open roadmap work.

## Native actor control and Blender duplication — development continuation

At this earlier checkpoint, development source exposed 21 MCP tools. `unreal_inspect_actor` reads exact
loaded actor identities, transforms and game-hidden state. Reviewed actor batches
spawn five allowlisted native actor classes, edit world transforms and change
game-hidden state. They use native editor transactions, consume previews once,
check target/world state, refuse PIE and never save the level. Attached actors and
actors without root components are excluded from existing-actor edits.

The Unreal editor target compiled/linked successfully. A real MCP subprocess in
the guarded isolated project created a native camera at `[100,200,300]`, then moved
it to `[400,500,600]`, rotated it to `[10,20,30]` degrees, scaled it to `[2,2,2]` and
set game-hidden state. Inspection confirmed each result. Preview caused no actor
creation; wrong confirmation, replay, stale state, unsupported classes and zero
scale were rejected. Direct authenticated native probes additionally rejected
string booleans, unknown fields and malformed vectors. Token-free live evidence:
`Saved/Milestone2/actors-duplication-live-report.json`.

Blender `duplicate_object` supports local mesh/empty sources, independent mesh/Action
copies, destination collections and local transforms. Native factory tests proved
that editing a duplicate leaves source mesh/Action data intact, source geometry
changes invalidate previews, keyframing avoids unnecessary Action copies, and a
failed batch removes all created object/mesh/Action data. Fault injection exposed
and fixed a cleanup-order issue. Existing native material graph tests still pass.
MCP duplicated the factory Cube at `[3,4,5]` and confirmed unchanged source facts.

Current Python suite: 35 passed; Ruff passed. Both isolated adapters passed bad-token,
arbitrary execution, malformed protocol/args, depth and oversized-request probes
and remained responsive. Native actor failure rollback is implemented but has not
been fault-injected or proven to reverse editor callback side effects. Interactive
UI, editor undo interaction, and PIE gameplay acceptance remain unverified.

The latest Blender files were installed on disk with backups. An unreleased native
plugin is staged at `Artifacts/MajesticForge-development-actors-duplication/MajesticForge`;
its validated DLL SHA-256 is
`4D99763DA88A96869E1149154294E2A64C8C70591A6B80B4600D58F83117B7D0`.
Development labels remain 0.2.0; existing release packages remain unchanged.
Original open application sessions were preserved, and only isolated probes stopped.
Activation in those original sessions and the full remaining roadmap are still open.

## Blueprint control flow and Blender constants — development continuation

New Blueprint recipes support Branch, Sequence (2–16 execution outputs), Self and
Reroute in addition to the prior five node kinds. A guarded real MCP probe connected
BeginPlay to Branch, routed an Enabled boolean through a typed Reroute, connected
three Sequence outputs to approved functions, and connected Self to an actor call.
The native compiler returned zero errors and zero warnings. Inspection confirmed
all four new node classes, connected sequence outputs and boolean reroute pins.
No save, placement or PIE execution was requested in this probe. This proves graph
construction/compilation, not runtime execution of the event logic.

An invalid boolean pin default originally returned completed with zero compiler
errors. Explicit boolean/default schema validation now rolls that case back and
discards its scratch asset. The same path can then be previewed again. Native
sequence count/type probes rejected 17, 1, 2.5 and string "3". The updated editor
target compiled/linked successfully. Evidence:
`Saved/Milestone2/blueprint-flow-live-report.json`.

Blender RGB and Value nodes now accept bounded `outputs` defaults. Native parser
tests and a real MCP probe created a four-node material, connected RGB to Base Color
and Value to Roughness, and confirmed the requested constant values and three valid
links. Evidence: `Saved/Milestone2/shader-constants-live-report.json`. Other shader
node types cannot set output defaults. No rendered-material acceptance is claimed.

At this earlier checkpoint, the Python suite had 36 passes; Ruff passed. Both isolated adapters passed the
authenticated rejection probes and remained responsive. Updated Blender source was
installed on disk with backups. The unreleased native plugin is staged at
`Artifacts/MajesticForge-development-flow-constants/MajesticForge`; its validated DLL
SHA-256 is `13286DA9B38F9F31FA29A4F03F8DBDDEDDDE13DE50D651FE6F4664A7D0B54EA9`.
At this earlier checkpoint, the MCP tool count was 19. Prior
development stages/release packages and original application sessions are preserved.
Only isolated probe processes were stopped. Full roadmap completion remains open.

## Existing graph and material inputs — 2026-10-09

At this earlier checkpoint, the source exposed 21 MCP tools. Existing Blueprint edits supported reviewed
node movement, validated input defaults and connect/disconnect operations on the
approved native node set. The real MCP isolated-editor test verified unchanged preview
state, completed native compilation with zero errors, one-use and stale-preview
rejection, a recovery journal, failed-batch restoration including an automatically
inserted conversion node, and unchanged saved asset SHA-256. Evidence:
`Saved/Milestone2/blueprint-edits-live-report.json`. Graph journals are not full binary
asset backups. Existing variables/components/functions and arbitrary node families
remain open; no interactive Undo or runtime execution acceptance is claimed.

Existing Blender material numeric/vector/RGBA input defaults now use the reviewed
scene recipe. Native tests verified shared-object user reporting, unchanged previews,
staleness, native value bounds and failed-batch default restoration. A real MCP factory
probe confirmed Roughness and Base Color changes. Evidence:
`Saved/Milestone2/material-edits-live-report.json`. Node/link structural editing and
rendered-material validation remain open.

At this earlier checkpoint, the Python suite had 36 passes. Ruff passed. Native editor target compiled/linked and final
UBT verification succeeded. Both isolated adapters passed authentication, allowlist,
protocol/type/depth and oversized request rejection probes and remained responsive.
Blender source was installed on disk with backups; existing user-loaded adapters are
not proven reloaded. The unreleased native development stage is
`Artifacts/MajesticForge-development-blueprint-edits/MajesticForge`, DLL SHA-256
`8D523ED4880B502576613C7F59FE95762E2658A89B902EA7BDCFF019C8F64DF9`.

The pinned public reference audit now records 287 registrations / 286 distinct command
names across 15 modules: 26 partial, 259 missing, one equivalent purpose and one
intentionally excluded unrestricted execution command. Counts describe registrations;
recipe tools are not standalone command parity. Full roadmap completion remains open.

## Existing Blueprint node construction — 2026-10-09

Existing Blueprint edit recipes now add bounded primitive variables and native
ActorComponents, plus allowlisted event/custom-event, variable get/set, branch,
sequence, self, reroute and approved native function nodes to an existing graph.
New nodes connect by recipe ID in the same reviewed operation. The native response
returns created members and node GUIDs. Graph schema connection and Blueprint compile
failures restore the pre-edit graph, variables and components; the recovery journal
still does not back up the binary asset, and no existing Blueprint file is saved.

The guarded real-MCP Unreal probe added a float variable (default 2.5) and a native
StaticMeshComponent, added variable get/set and a three-output Sequence, wired graph
pins, and verified the returned GUIDs, member inspection, and compiled default-object
value. It confirmed compilation and repeated failure-recovery/stale-preview checks.
Evidence:
`Saved/Milestone2/blueprint-edits-live-report.json`. Python suite: 37 passing tests;
Ruff passed; UE 5.6 editor target compiled, linked, and passed final UBT verification.
Unreleased plugin stage:
`Artifacts/MajesticForge-development-existing-blueprint-structure/MajesticForge`,
DLL SHA-256 `501E923C50C3DBD02CDD933CCA584CF1A82663D2438E034D499F3ED427EBD10B`.
Existing member edits/removal and function/signature editing remain open, along with
GAS, UMG, World Partition, broader Unreal material/asset systems and most Blender rig,
modifier and interchange work. The full objective remains active.

## Blender rig inspection — 2026-10-09

The new read-only `blender_inspect_rig` MCP tool reports an explicitly named active
scene armature's bounded bone hierarchy and related mesh vertex groups. Optional skin
weight summaries are capped at 256 bones, 32 meshes, 100000 total vertices and two
million assignments per query; the default query does not scan weight assignments.
Factory Blender validation and live MCP calls confirmed parent/connected bone data,
related-mesh detection, per-bone weighted vertex counts and sums, and rejection of a
mesh queried as an armature. Evidence: `Saved/Milestone2/blender-rig-live-report.json`.
The add-on source is installed on disk with backups; reload in Blender Preferences is
still needed before the existing user session can use this added tool.

Current Python suite: 37 passed; Ruff passed. Unreal variable/component/node additions
and the updated compiled default inspection passed a separate guarded real-MCP probe
with zero Blueprint compile errors and exact failed-batch restoration. The current
unreleased native build remains staged at
`Artifacts/MajesticForge-development-existing-blueprint-structure/MajesticForge`.
Rig creation/weight editing, Unreal GAS/UMG/World Partition, broad asset/material
automation, and cross-application transfer are still incomplete.

## Project-root and dual-application validation — 2026-10-09

At the time of this validation, the Unreal plugin, MCP server, Blender add-on source,
tests, scripts, and documentation lived in `G:/Unreal Engine Projects/ForgeMCPDev`;
no duplicate source copy was needed then. The authoritative development root is now
`G:/ForgeMCP`, where `ForgeMCPDev.uproject` enables ForgeMCP.
The plugin is editor code with `CanContainContent: false`, so it does not add assets
to Unreal's Content Browser. The project `Content` folder currently has only empty
folders.

Fresh validation from that root:

- Python suite: 37 passed. Ruff passed for `server`, `blender-addon`, `tests`, and
  `scripts`.
- `BuildAndOpen.ps1 -BuildOnly` compiled the Unreal 5.6 Editor target successfully.
- Blender 5.2.2 factory-scene checks passed for reviewed scene recipes, shader-graph
  inspection/creation and rollback, and live MCP armature/skin-weight inspection.
- Guarded dual-application MCP validation used only
  `Saved/Milestone2/HostProject` and a disposable Blender factory scene. Unreal saved,
  placed, inspected, and compiled the test Blueprint with zero compiler errors;
  existing-Blueprint edits, stale/replay rejection, and rollback also passed.
  Blender applied and inspected the test mesh/keyframe recipe. Reports are
  `Saved/Milestone2/engineering-live-report.json`,
  `Saved/Milestone2/blueprint-edits-live-report.json`, and
  `Saved/Milestone2/blender-rig-live-report.json`.
- Both live adapters rejected invalid tokens, mutation commands, malformed protocol
  and arguments, deeply nested JSON, and oversized requests, then remained responsive.
- The current MCP registry exposes 23 tools after the bounded GAS inspection addition;
  live verifier counts are kept in sync with the current registry.

The live checks used the current project-built Unreal plugin in the isolated host and
the project Blender source in factory scenes. They did not update the installed
Blender add-on or its preferences, open the user's Unreal project, or validate
interactive panels. This is not a final deployment: Gameplay Ability System, UMG,
World Partition, broader asset workflows, Blender rig editing/interchange, cross-app
transfer, and additional visual/runtime acceptance remain on the roadmap.

## ForgeMCP application name — 2026-10-09

User-facing branding in the Unreal plugin and Blender add-on source now reads
`ForgeMCP`: plugin display name, Unreal Window menu/tab/panel, Blender add-on name,
sidebar tab and panel, adapter metadata, and installer instructions. The MCP server
handshake and status names also read `ForgeMCP`. Internal plugin, Python add-on, and
Blender operator identifiers (`MajesticForge` and `majestic_forge`) remain unchanged.
The Codex MCP alias has since been standardized as `forgemcp`. The
installed Blender add-on received only a branding refresh to `__init__.py`, with the
previous file backed up and preferences untouched. The broader feature deployment is
still deferred until the roadmap is ready.
The renamed source passed the 37-test Python suite and Ruff; Blender 5.2.2 verified the
source add-on metadata, sidebar category, and panel label. The UE 5.6 Editor target
rebuilt successfully with the new plugin display name. The Unreal installer now rejects
an older staged plugin package whose display name is still Majestic Forge. The installed
Blender UI and bridge lifecycle then passed in Blender 5.2.2 with a disposable config.

## Typed Blueprint function signatures — 2026-10-09

New Blueprint recipes accept typed function input/output pins (`bool`, `int`, `float`,
`string`, `name`, `vector`, and `rotator`), pure-function declarations, and explicit
`Entry`/`Return` graph references for wiring. Legacy function-name strings remain valid.
The Unreal adapter creates native function graphs and pins, validates bounded unique
names and supported types, and compiles the resulting Blueprint. Editing or changing
function signatures on an existing Blueprint is not implemented.

Validation: Python suite 40 passed; Ruff passed; the UE 5.6 `ForgeMCPDevEditor` target
compiled and linked from an isolated project copy. A guarded live MCP probe built a pure
float function, connected its typed entry pin to its output pin, compiled with 0 errors
and 0 warnings, and confirmed both pins and their link through Blueprint inspection.
The probe did not save or place the Blueprint. Its token-free report is
`Saved/FunctionSignatureValidation/blueprint-functions-live-report.json`. The user’s
open Unreal session was left untouched; the isolated validation editor was closed.

## GAS Blueprint replication configuration and live inspection — 2026-10-09

The UE 5.6 GAS component probe exposed that UAbilitySystemComponent::ReplicationMode
is not a serialized Blueprint property. Setting it on an SCS component template therefore
left spawned actors at the engine default. Blueprint recipes now store the selected mode
in the ForgeMCP GAS setup component's reflected properties; mixed/minimal requests require
that matching component, while full retains the native default. The component applies the
mode at registration and again before authoritative startup grants/effects. Blueprint
inspection distinguishes the requested mode from the raw component-template default.

Validation: 48 Python tests passed; Ruff passed; the UE 5.6 editor target compiled both
runtime and editor modules from an isolated host. A live MCP probe used 23 tools, previewed
and applied a Blueprint with an ASC and GAS setup component, placed it in the disposable
editor world, and verified mixed mode through both Blueprint inspection and
unreal_inspect_gas. The ASC reported replicated with zero attributes, tags, abilities or
active effects, as expected for an empty setup. The Blueprint asset and level were not
saved. Evidence is in
`Saved/GoalGASInspectionValidation-20261009-192318/HostProject/Saved/gas-inspection-live-report.json`.
Gameplay asset authoring, ability grants with project-specific classes, PIE/network behavior
and cross-application workflows remain incomplete; this probe did not validate them.

## Central source repository and clean-copy validation — 2026-10-09

The approved central development copy is `G:/ForgeMCP`. Ninety-one source/configuration/
documentation files were copied from `G:/Unreal Engine Projects/ForgeMCPDev` and verified
by SHA-256 with no missing, mismatched, or unexpected files. The older roadmap already in
`G:/ForgeMCP/Documentation` is preserved in `Documentation/Archive`; the workspace roadmap
is now the central copy. Build products, caches, Saved validation hosts, local Codex
configuration and artifacts were excluded from the copy. The original workspace, user
MCP configuration, installed Blender add-on and open applications were left in place.

The central folder is initialized as a local Git repository on `main`, with no commits or
remote. Its own pinned Python environment and ignored workspace MCP configuration were
created; the user-level MCP registration still points to the original workspace until a
separate client cutover.

Fresh checks from `G:/ForgeMCP` passed: Python 3.11 environment setup, 48 Python tests,
Ruff, and Blender 5.2.2 factory-scene recipe, duplication, armature and skin-weight
probes. A live Blender MCP probe through the central server inspected a disposable rig,
previewed and applied a typed rig recipe, and confirmed the scene was not saved.

The first clean Unreal build exposed two gaps in `Build-ForgePlugin.ps1`: it linked the
editor module before its Runtime dependency, and its final plugin-filtered build omitted
the project game module. The helper now builds descriptor modules Runtime-first and ends
with the selected project's normal Editor target. The corrected helper compiled the UE
5.6 `ForgeMCPDevEditor` target successfully, including the ForgeMCPDev game module and
both plugin modules. Through the central MCP server's 23-tool registry, an isolated
Unreal 5.6.1 host then passed existing Blueprint edit/create/wire, stale/replay rejection,
saved-asset hash preservation and rollback checks, followed by live GAS Blueprint
replication-mode inspection (`mixed`). The Blueprint asset and level remained unsaved.
Unreal reports are under the ignored `Saved/CentralLiveMcpValidation/HostProject/Saved`
folder; the Blender report is `Saved/central-blender-rig-live-2-report.json`.

The task remains in development. Gameplay ability, AttributeSet and GameplayEffect asset
authoring, PIE/network behavior, UMG and World Partition workflows, broad Unreal API
coverage, Blender rig/weight editing, cross-application transfer and interactive UI
acceptance remain unimplemented or unverified. The central Blender source was validated
without updating the installed user add-on.

## Authoritative workspace migration — 2026-10-09

`G:/ForgeMCP` is the authoritative development root. The global and project-local Codex
MCP configurations now use the `forgemcp` alias, the central `.venv`, and
`FORGE_PROJECT_ROOT=G:/ForgeMCP`; `.codex/config.toml` remains ignored. The workspace
setup script migrates the legacy alias safely, and `Build-ForgePlugin.ps1` now defaults
to the central `ForgeMCPDev.uproject` instead of a generated host under `Saved`. The
root-level `Untitled.blend` is kept out of the source baseline.
The central Unreal config disables Android File Server network connections and carries
no static `SecurityToken`; its original token-bearing config remains only in the
restricted migration backup.

Neither checkout had commits or remotes. The old checkout's single Codex reference
points to a tree object rather than a commit, so it has no commit history for a Git
bundle. Its `.git` object store is preserved separately from a full external copy of
the original working tree: 8,480 files totaling 13.844 GiB. SHA-256 checks matched the
original-only solution, both `.uproject` backups, all four package archives, and the
local Codex config. File and directory counts matched for `Saved` package, autosave,
log, validation-host, and install-backup folders. This
preserves the original-only `Artifacts` and `Saved` data without bringing stale packages,
local settings, or generated build output into the central source baseline. The empty
central Blender scene and a pre-migration copy of the global Codex config are also
preserved outside the repository.

Migration validation from the central root passed: 48 Python tests, Ruff, PowerShell
syntax parsing, and a full UE 5.6 `ForgeMCPDevEditor` build. A headless UE 5.6.1 startup
mounted the Forge plugin and loaded both plugin DLLs. The central 23-tool MCP server
returned the project path `G:/ForgeMCP/ForgeMCPDev.uproject` and connected to the active
Blender 5.2.2 session. A separate factory-startup Blender process loaded the central
add-on source and passed the live rig hierarchy, skin-weight, preview, and apply probe;
that disposable scene was not saved. Interactive UI inspection of either panel has not
been performed.

The old checkout has not yet been moved to the Recycle Bin. The old Unreal Editor and
six `server.main` child processes still run from the original location; the user
confirmed Unreal Save All and that the Blender scene was empty. The global config is
updated, but its active Codex extension must restart before the old child processes can
be cleared. A hidden central Unreal verification process remains open as well. Close or
restart these sessions through the application UI, then verify no process references
the old root before recoverably removing it. No source has been pushed or deployed.
