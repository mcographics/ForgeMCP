# Roadmap implementation status — October 16, 2026

The full user goal remains active. The original roadmap is preserved as supplied.
The MCP server source is version 0.3.13, the engine-installed Unreal plugin is
0.2.13-alpha.9, and the latest Blender add-on is 0.2.35-alpha.6 (Blender numeric
metadata 0.2.35). Component versions
advance with validated component changes. Coordinated
v1.0.0 remains gated on completing the roadmap's installation, live-session,
capability, recovery and packaging criteria; these development versions are not
completion of universal Unreal/Blender control.

The alpha.9 Unreal tab white-screen fix is installed engine-wide. Its single-file
React bundle passed Chromium runtime and isolated UE 5.6.1 package checks; the
standard desktop Unreal WebBrowser still needs a visual refresh check. See
[white-tab fix evidence](UE56_Alpha9_White_Tab_Fix_20261016.md) and the
[official partner logo integration record](UE56_Alpha9_Official_Partner_Logos_20261016.md).
The current reference-matched spacing and icon refinement is documented in
[the compact layout note](UE56_Alpha9_Compact_Layout_20261016.md).

## October 16 — Automatic dual-application session check

Server **0.3.11** adds `forge_ensure_connected`. Each call rediscovers registered
sessions, authenticates each app with a health request and returns a session ID
only when exactly one live bridge exists for that app. Optional explicit IDs
resolve multiple live sessions without guessing. This verifies connectivity with
short requests; it does not retain sockets or launch bridges. Unit and stdio MCP
tests cover automatic selection, explicit selection, ambiguity, missing bridges
and registration discovery. In the current environment Blender `blender-5048`
responds as **0.2.35-alpha.4**; no Unreal bridge is responding, although an
UnrealEditor process exists. Unreal connection remains pending its bridge startup.

## October 16 — Blender add-on alpha.4 alignment

Blender add-on **0.2.35-alpha.4** aligns its release label with the Unreal
alpha.4 milestone. Its Send to Unreal **Asset path** now defaults to
`/Game/Content/Returns/`; the existing transfer flow appends the exact Blender
source object name. Blender's numeric `bl_info` version remains `(0, 2, 35)`;
the package filename and authenticated bridge health expose the full prerelease
label. The 10-module ZIP (`Artifacts/ForgeMCP-Blender-Addon-0.2.35-alpha.4.zip`,
SHA-256 `ca052fdbd6f18dc9d93e2c429140886d35d3ed1dfcc4b83f5577f7d6459b5a9f`)
passed the Blender 5.2.2 clean-profile install, enable/disable, cached-module
reload and existing native acceptance checks. The user Blender 5.2 add-on source
was updated with per-file backups. Blender was running during installation, so
its already-loaded adapter still needs an add-on reload or Blender restart before
the live bridge reports the new version. No scene data or preferences were changed.

## October 16 — Blender tab redesign, alpha.5

The Blender 3D Viewport ForgeMCP sidebar now follows the supplied reference with a
branded version card, grouped Bridge Status and Send to Unreal panels, clear
connection/session timing, and aligned transfer settings. The transfer still uses
the existing reviewed preview/confirm flow and `/Game/Content/Returns/` default.
The source and package report **0.2.35-alpha.5**; Blender's numeric add-on metadata
remains `(0, 2, 35)`. Blender 5.2.2 headless draw and clean-profile package checks
passed, the add-on was installed in the 5.2 user folder, and a fresh process
registered the installed source. Interactive sidebar rendering in a live Blender
window remains a separate visual check. See
[alpha.5 Blender UI acceptance](Blender_Alpha5_Tab_Redesign_20261016.md).

## October 16 — Blender reference-match refinement, alpha.6

The alpha.5 layout was too generic compared with the supplied image. Alpha.6
centers the large logo above the product name/version, enlarges the bridge action,
removes the duplicate transfer heading, and presents placement coordinates as
separate X/Y/Z rows. The installed alpha.5 process is still running; alpha.6 source
and package validation plus installation are tracked in
[alpha.6 visual refinement](Blender_Alpha6_Tab_Visual_Refinement_20261016.md).

## October 16 — Alpha.2 engine-mesh panel transfer fix

Installed alpha.2 and server source 0.3.7 fix the selected engine sphere's rejected
source path and the async exception masking behind `panel_worker_failed`. Python
tests (339), lint, the module-restricted editor build, native source-preservation
automation and real FBX/OBJ panel-worker transfers into disposable Blender passed.
The updated engine DLL passed fresh-project load and real stdio MCP inspection.
Native source stays in the engine installation at the user's request. See
[alpha.2 evidence](UE56_Alpha2_Transfer_Fix_20261016.md).

## October 16 — Alpha.3 Blender handoff and import preflight UX

The import message identified an existing destination only as `destination_exists`.
The live project already contains `/Game/ForgeMCP/Returns/SM_Return`, so the guard
was correct; the panel now explains how to choose a new path or use an eligible
bound replacement. The Send to Blender object-name field now starts blank and
keeps the source mesh asset name unless the user enters an override. The isolated
27-action native build, engine update, fresh engine-wide plugin load, and live
ForgeMCPDev bridge check passed. Visual panel confirmation remains unverified.
See [alpha.3 evidence](UE56_Alpha3_Transfer_UX_20261016.md).

## October 16 — Transfer name preservation and Unreal return folder

Server 0.3.10 and Unreal alpha.4 use `/Game/Content/Returns/` as the Blender-to-
Unreal destination folder and retain the exact source object name as the new mesh
asset name. No prefix, suffix, or collision-driven rename is generated; an
existing exact destination remains a preflight error. Unreal-to-Blender continues
to default to the source Unreal asset name, with a blank optional override. Alpha.4
source is in the engine installation. Build, package and engine-wide load evidence
is recorded in [transfer name acceptance](UE56_Alpha4_Transfer_Names_20261016.md);
interactive two-application transfer verification remains open until both bridges
are connected.

## October 16 — UE 5.6.1 engine-wide alpha

Plugin 0.2.13-alpha.1 was packaged and installed engine-wide for UE 5.6.1 Win64
Development Editor. Python regression tests (335), lint, native module builds and
the full isolated editor target passed. A fresh Blueprint-only project without a
local plugin copy loaded the engine DLL, matched the package bytes/version, and
passed authenticated inspection plus real source stdio MCP discovery and project
identity checks. Visible UI, all-feature and performance acceptance remain open.
See [alpha evidence](UE56_Alpha_Acceptance_20261016.md) and
[installation/update/rollback](UE56_Alpha.md). Feature development continues in
the separate project-local plugin; the v1.0 roadmap remains active.

## October 13 — Blender creative commands and complete operator discovery

Added nine MCP tools for every registered native operator's discovery/schema,
RNA type/property inspection, reviewed creative authoring, save-copy, background
render jobs and cancellation. The source registry contains 104 tools. The factory
Blender 5.2.2 catalog reports 2,499 operators and 4,012 RNA types; 21 creation and
44 mesh operators have execution adapters, alongside separate native data/RNA
workflows. The source add-on session exposes 2,504 operators including its UI.
Remaining operators are explicitly `discovery_only`.

Full Python tests: 330 passed. Disposable native acceptance: 39 checks including
save-copy reopening and real 4K rendering. Real source stdio MCP acceptance
authenticates add-on 0.2.33, authors a sphere/camera/shader/keys, saves a copy,
renders and decodes two animated 4096 × 2304 PNGs while the bridge remains
responsive, and cancels a running render worker. The 0.2.33 ZIP passes clean-profile
installation, enable/disable, cached-module reload and legacy native export tests.
No open user scene was modified for these tests. See
[Blender creative automation](Blender_Creative_Automation.md) and retained
`Saved/creative*-acceptance.*` evidence. The original interactive Blender session
and this chat's MCP binding remain separate activation gates.

| Requirement | Authoritative current evidence | Remaining work |
| --- | --- | --- |
| Original server, adapters, provider-independent MCP | Original source, official MCP SDK, separate authenticated native runtimes; stdio tests | Broader client acceptance |
| Codex foundation inspection | Five original tools previously accepted in the IDE; the current source MCP registry contains 87 tools | Reload the extension for the current development registry |
| Secure local endpoints and panels | Native panels, loopback listeners, protected token files, bounded parsing, allowlists | Continued adversarial tests as operations expand; interactive panel QA |
| Blueprint create/compile/place | Live guarded MCP proof created `/Game/ForgeValidation/BP_ForgeProof_6e09960d`, compiled with 0 errors/0 warnings, saved a 43,821-byte asset, placed its actor in the isolated editor world | PIE/gameplay execution proof and repeat clean-project acceptance |
| Variables/components/functions/nodes/pins | New Blueprint recipes and reviewed edits to existing normal Blueprints support typed function input/output signatures and pure functions; existing-asset primitive variable/native component/node additions, GUID-based rewiring, movement/default edits, compile and rollback proof | Editing/removing existing members, changing/removing existing function signatures, richer pin types, broader safe node families |
| GAS | Typed setup for new Blueprints; persistent ASC replication-mode config; live MCP inspection of an isolated placed actor validated | Gameplay Ability/AttributeSet/GameplayEffect asset authoring, deeper ability/tag/effect operations, full PIE/network gameplay acceptance |
| Actors, assets, levels, materials, UMG, World Partition, PCG | Actor inspection/edit recipes, Blueprint asset creation/placement, native class metadata, bounded Asset Registry queries, Content Browser selection/open/sync, DataAsset discovery/schema/guarded creation and guarded multi-property edits with explicit save and pre-edit backup, native material/instance graph authoring, read-only DataTable schema/row inspection, and bounded read-only Editor log tail | Broad actor/world control, fuller asset lifecycle, broader DataAsset property types and recovery cases, UMG graph editing, partition/data-layer/PCG operations |
| Unreal skeletal/animation/retarget assets | No asset-specific implementation | Inspect/edit/import/retarget workflows and acceptance |
| Blender object/mesh/material/collection/rig inspection | Native object/mesh/material/collection/rig inspection; reviewed bounded topology replacement, paged geometry and UV inspection/editing, modifier creation/settings edits, existing material socket and additive graph edits, existing-node position/operation/blend/default edits with rollback and stale-preview checks | Rig/weight editing, topology remapping for custom data or skinned meshes, modifier removal/properties, existing node/link removal and replacement, broader object operations |
| Blender animation/timing | Transform/pose-bone keyframes, native evaluated playback, paged Action inspection and reviewed single-key frame/value edits on a copied Action | Rig/weight editing, key deletion/interpolation/handle editing, NLA, retargeting, skeletal animation transfer and live activation of add-on 0.2.30 |
| Recovery and authorization | Expiring single-use previews, explicit confirmations, stale scene checks, Blueprint scratch discard; native Blender recipe and transfer rollback fault injection passed | Durable operation history/backup management, more failure modes and higher-impact previews |
| Cross-application transfer | Reviewed Unreal↔Blender static-mesh send/import, stable bindings, revision comparison and recoverable bound-mesh replacement; native FBX and OBJ MCP acceptance | Broader format/content profiles, recovery edge cases, richer conflict resolution and real-time synchronization |
| API retrieval / RAG | Version-scoped local SQLite retrieval; installed Unreal Python stub and native bpy metadata indexed; no source execution | Expand retrieval evaluation and link retrieved APIs to operation capabilities; governed scripting remains typed native recipes |
| Packaging/setup | UE 5.6.1 development ZIP 0.2.8 passed clean-project plugin-load verification; disposable MCP acceptance passed DataAsset preview/apply, backup, stale-preview rejection and fresh-process reopen; Blender ZIP 0.2.32 passed clean-profile node-edit and rollback checks | Activation in original sessions, repeatable user setup, distribution strategy |


## Guarded existing DataAsset edits — 2026-10-11

October 12 distance readout acceptance: native widget edits removed 1,000 km display
quantization while retaining the existing live distance/timer path. The user
confirmed the numbers move again; a 59.235-second user-operated PIE run recorded
changing raw values and zero divide-by-zero, Accessed None or missing-media errors.
Temporary logging was disconnected/disabled and the final assets were saved.
See [OnTheGoNav_Distance_Readout_20261012.md](OnTheGoNav_Distance_Readout_20261012.md)
for exact scope and remaining astronomical-distance limits.

October 12 update: server source 0.3.2 fixes existing Blueprint graph/member name
validation. A reviewed OnTheGoNav repair compiled cleanly, was manually saved, and
its user-operated PIE run produced no new divide-by-zero warnings. Full Python
regression: 297 passed; Ruff passed. See
[OnTheGoNav_Repair_20261012.md](OnTheGoNav_Repair_20261012.md) for backups, exact
changes, runtime evidence, restored media and remaining issues.

The server source is 0.3.1 and the Unreal plugin is 0.2.8. Two MCP tools now
provide reviewed edits to existing loaded DataAssets: `unreal_preview_data_asset_edit`
and `unreal_apply_data_asset_edit`. They accept one asset and 1–32 supported,
editable simple reflected properties under `/Game` or `/JasperPrism`. Apply requires
the exact unexpired preview confirmation, rejects changed or dirty targets, uses
native Unreal boolean accessors for bitfield values, and saves only when requested.
A successful apply verifies read-back and retains a SHA-256-verified original package
backup under the disposable project's `Saved` directory. Arrays, nested containers,
and object/asset references are not in this edit profile.

The disposable UE 5.6.1 MCP acceptance passed: two boolean values changed, an incorrect
confirmation was rejected, a stale preview was rejected, the original package backup
matched its recorded hash, Asset Registry results reflected the asset, duplicate
creation was rejected, and a fresh Editor process reopened the asset with both values
persisted. Focused Python checks passed (62 tests), Ruff and Python compilation passed;
the modified native source compiled and the module linked successfully. The broader
ForgeMCPDev Editor target did not finish, so that full-target build is not claimed.
The 39-file development package
`Artifacts/ForgeMCP-Unreal-Development-0.2.8-UE5.6.1-Win64.zip` has SHA-256
`bfdcc0ff0cce2b49b8d91b9be3a5a142ffba0dc50d6d57043d5ca72708a561b1` and passed clean-
project packaged plugin load verification.

That increment's earlier connected-host snapshot was server 0.2.0 with disconnected
sessions. The October 11 showcase supersedes that connection snapshot: the host now
reports server 0.3.1 and connected Unreal bridge 0.2.8 in ForgeMCPDev. Blueprint
creation/compile/save/read-back passed through the host. This does not establish
live DataAsset-edit acceptance through that host or JasperPrismDev acceptance.

## Connected Unreal showcase — 2026-10-11

The connected Codex host successfully inspected ForgeMCPDev in UE 5.6.1, queried
the native Asset Registry, discovered the wooden-box and sphere actors in TestArea,
and read the wooden-box component hierarchy and mesh reference. A reviewed new
Blueprint at `/Game/ForgeMCP_Demos/BP_MCP_Showcase_20261011` was created, compiled
with zero errors/warnings, saved and opened in its native asset editor. It contains
two initialized variables, a static-mesh component and a typed `EchoValue` function
with inspected bidirectional input/output pin links. Wrong confirmation, consumed
preview replay and duplicate creation were rejected. No actor was placed or level saved.

The full Python suite passed (288 tests), including MCP subprocess tests; Ruff passed.
The new read-only `scripts/verify_unreal_showcase_mcp.py` independently discovered 85
tools through a fresh source stdio subprocess, verified project identity, Blueprint
defaults/component/pin links, native registry presence, unchanged world context and
unchanged 31,863-byte package bytes. Token-free evidence is retained under
`Saved/ForgeMCPShowcase/`. See [Unreal_MCP_Showcase.md](Unreal_MCP_Showcase.md) for
repeatable verification and remaining visual/gameplay acceptance steps.

The first full `ForgeMCPDevEditor Win64 Development` build encountered LNK1104
because the running Editor held the project/runtime DLLs. After the user saved and
closed Unreal, `BuildAndOpen.ps1 -BuildOnly` succeeded on October 12: project and
runtime DLL links and `ForgeMCPDevEditor.target` metadata completed. Unreal was
reopened as session `unreal-27496`; native project identity and asset opening passed.
Windows module enumeration confirmed it loaded this checkout's rebuilt
`Plugins/MajesticForge/Binaries/Win64/UnrealEditor-MajesticForge.dll`.
The read-only MCP verifier passed again in that fresh Editor process with the same
package SHA-256, variable defaults, component and function links. This establishes
saved-package persistence across restart; PIE/gameplay and interactive visual QA
remain unverified. Evidence includes `20261012-editor-build.log` and
`20261012-fresh-editor-readback.json` under `Saved/ForgeMCPShowcase/`.

## Current progress estimate — 2026-10-11

These are engineering estimates against roadmap breadth, integration, failure recovery
and release readiness, not a count of command names. The coordinated v1.0.0 goal is
approximately **55% complete**. Unreal automation is approximately **58%**, Blender
automation **62%**, bidirectional file transfer **60%**, and clean installation/live
integration/recovery **42%**. Estimates reflect tested workflows as well as gaps;
real-time synchronization is not implemented.

Currently practical: typed, reviewed MCP operations can inspect and edit supported
Unreal actors, assets, Blueprints, materials, levels and DataAssets; inspect Blender
objects, meshes, materials, rigs and animation; perform several reviewed Blender
mesh/material/node/modifier edits; and transfer static mesh FBX/OBJ assets between
Unreal and Blender with bindings and revision checks. Python is used by the server and
Blender adapter, but arbitrary user-supplied Unreal Python execution is not an approved
remote operation. C++ plugin changes can be made in source and packaged; compilation
can be triggered locally, though a complete editor-target build and live editor
activation remain unverified for this increment.

Still outside reliable coverage: arbitrary Blueprint graph authoring, UMG, broad
World Partition/PCG/Niagara workflows, Unreal skeletal/animation pipelines, Blender
rig/weight editing and broad destructive graph edits, durable cross-operation recovery,
real-time two-way synchronization, and universal clean-install activation. The current
Codex connection is disconnected and must be refreshed before any newly exposed MCP
operation can be claimed against the user's live editors.


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

## Active asset-transfer milestone: contract foundation

The adopted objective and acceptance gates are recorded in
`Documentation/Active_Development_Plan.md`. The full platform objective remains
active, including clean installation, interactive operation, recovery, capability
coverage, and installable packages for both adapters.

`server/core/transfer.py` now defines the static-mesh transfer manifest and staged
binary-FBX integrity verifier. It requires explicit source/target session identities,
an absolute project identity, a bounded `/Game/` asset destination, declared units,
bounds, counts and material slots. It rejects overwrite requests, traversal/device
filenames, links/reparse points, oversized artifacts and checksum changes. It also
checks file identity during reading. Integrity verification explicitly does not
establish native geometry correctness or authorize import.

Validation: all 81 Python tests passed; Ruff passed. The added transfer tests exercise
invalid contracts, missing/changed files, incorrect format headers, file links and
linked staging roots. No application session or scene was changed by these tests.
The pre-existing `Config/DefaultEngine.ini` edit remains separate from this work.

Native Blender export, Unreal import, placement, durable recovery and interactive
end-to-end transfer acceptance remain outstanding. The new contract is not yet
connected to a transfer MCP tool, and no end-to-end transfer success is claimed.

## Native Blender static-mesh export stage

The source now includes reviewed native FBX export in
`blender-addon/majestic_forge/exporting.py`, authenticated export routes in the
Blender bridge, and standalone `blender_preview_export` / `blender_apply_export`
MCP tools. The development registry contains 25 tools. Export is a distinct stage;
no Unreal import or complete asset-transfer capability is claimed.

Previews are read-only, expire after 300 seconds, and bind to source geometry,
attributes, material state, transform and scene units. Apply requires the reviewed
preview ID as confirmation and consumes it once. Output paths are generated inside
private per-session staging, existing destinations are rejected, and the source
scene is not saved. Recovery records are persisted before export and updated
atomically after success or failure. Unknown outcomes require inspection before
retry. The initial exporter explicitly rejects animation, modifiers, parenting,
constraints, shape keys and texture/group materials; those require later stages.

Validated in separate Blender 5.2.2 factory-startup processes:

- Native preview/apply exported and reimported an asymmetric mesh, preserving
  dimensions, signed vertex coordinates, vertex count and material slots in a
  Blender roundtrip. This does not establish Unreal coordinate conversion.
  Source selection and active object were preserved. Stale geometry/UV/material/units,
  unsupported modifiers, expired
  previews, incorrect confirmations and replay were rejected. Cancelled export
  retained an export-failed record. Authenticated bridge routing and argument
  allowlists were exercised.
- Real MCP stdio discovery and export returned a new FBX whose checksum matched the
  native response and retained report. Replayed apply was rejected; scene-info
  responses before and after were equal.
- The rebuilt six-module ZIP was installed with Blender's native install operator
  into an isolated user profile. Add-on enablement, panel-class registration and
  bridge start/stop/disable passed. No user preferences were saved.

All 81 Python tests and Ruff passed. The source installer includes the exporter;
`scripts/package_blender_addon.py` builds a deterministic source-only ZIP and
preserves the previous archive when its bytes change. No add-on was deployed or
reloaded in an existing user session during this stage. Headless installation and
registered panel classes do not establish interactive panel click-through.

Unreal import, native result comparison, level placement, coordinated recovery and
interactive end-to-end transfer acceptance remain outstanding. The complete
platform goal remains active.

### Unreal staged static-mesh import implementation

The Unreal plugin now routes native `mesh_import_preview` and `mesh_import_apply`
commands. These commands accept bounded recipes identifying the target project,
editor session, new asset package and private staged binary FBX. Preview checks
the file header, size and SHA256 and rejects existing destinations. Apply consumes
the preview once, repeats validation and uses Unreal's FBX factory on the editor
game thread. It retains an import status record and reports native mesh geometry
and material-slot metadata. Material asset creation and actor placement are not
implemented by this stage.

These commands are in the native bridge allowlist but are not exposed as new MCP
tools. The isolated UE 5.6 Editor target compiled and linked successfully. Existing
application sessions have not been reloaded.

After the routing changes, all 81 Python tests passed and Ruff passed. An initial
regression run encountered one 100 ms malformed-response timeout; its focused
connection suite and the complete rerun both passed.

The server now stages validated exports into private target-project runtime storage
and retains manifests and staging status records. Corrupted source data is rejected
before target writes; changes while copying retain a staging-failed record. Existing
transfer directories are never reused. All 85 Python tests passed after these additions.

`scripts/verify_unreal_mesh_import.py` runs factory Blender and its own unattended
Unreal instance, restricted to generated disposable validation hosts. Native import
acceptance passed for an asymmetric eight-vertex/twelve-triangle mesh: signed
coordinate conversion, meter-to-centimeter scale, bounds, material-slot names,
static-mesh class/package identity, package save, wrong-session and unknown-field
rejection, replay rejection, stale-checksum rejection and invalid-native-FBX rollback.
The actor list stayed unchanged. Recovery records persisted both imported and
rolled-back outcomes, including native FBX errors. This is headless native acceptance,
not interactive UI verification, a full material transfer, or completed orchestration.

The importer holds a Windows handle denying writes/deletion during native import
and captures at most 32 relevant native warnings/errors, each bounded to 1,024
characters. Blender export includes face smoothing groups. The updated six-module
addon ZIP passed isolated native installation and enable/disable validation, and its
previous archive was preserved under `Artifacts/Backups`.

### Native static-mesh placement and MCP acceptance

Actor spawn recipes now accept `mesh_path` for `/Script/Engine.StaticMeshActor`
only. The path must identify an exact loaded `/Game/` static mesh; preview does not
load caller-selected assets. Supported meshes are bounded to 100,000 vertices,
200,000 triangles and 32 material slots. Fingerprints include the mesh instance,
lighting GUID, geometry/topology and material references, plus world/current-level
identity. Existing actor edits do not accept mesh assignment through this field.

Apply binds the mesh through the native static-mesh component inside the editor
transaction. A binding failure uses the existing created-actor rollback path.
Actor inspection now includes the mesh reference, material asset references and
world bounds. No level save is implied by successful placement.

The isolated UE 5.6 Editor target passed after these changes. All 86 Python tests
passed, including recipe boundary checks and real stdio schema/validation checks.
An unattended Unreal acceptance run imported the asymmetric Blender fixture and
then used real MCP stdio `unreal_preview_actors`, `unreal_apply_actors` and
`unreal_inspect_actor` calls to place and inspect it. Verified native location,
rotation, nonuniform scale, world bounds, mesh reference and material-reference
count matched expectations. Preview did not change actors; replay was rejected.
The run retained `acceptance.json`, `native-result.json` and `placement-result.json`
under its isolated `Saved/MeshImportAcceptance-*` directory. The record explicitly
states `interactive: false`, `level_saved: false` and
`material_assets_transferred: false`.

This acceptance also caught and fixed a diagnostic-capture race: Unreal's dedicated
logging thread could still have queued import errors when the recovery report was
written. Diagnostic capture now flushes before attaching and before collecting its
bounded results. The rebuilt native test required an actual FBX error in the
invalid-input rollback report and passed.

Full material transfer, durable production placement/recovery coordination,
general transform/unit acceptance, saved-level/reopen acceptance and visible
interactive workflows remain outstanding. Existing user sessions were left running;
the isolated validation processes were closed after testing.

### Constant-PBR material transfer

Blender export slots now include an explicit transfer-surface classification.
Supported opaque constant Principled surfaces retain scene-linear base color,
roughness, metallic and sidedness. Procedural/linked graphs, transparency,
non-default advanced BSDF features, animated surfaces and out-of-range constants
are classified as unsupported. Standalone geometry export may retain that
classification, but material-transfer staging rejects unsupported/missing profiles
before writing target files.

Unreal staged import accepts bounded material definitions with generated new
package destinations. It rejects existing material packages, verifies imported
slot names/counts, creates native Default Lit constant graphs, assigns them to the
mesh and records per-material save results. Planned mesh/material destinations
are persisted before native import. Materials save before the mesh; any material
save failure produces a partial outcome and prevents mesh save. Save-failure
recovery remains a required acceptance case, not proven by the successful run.

The isolated UE 5.6 Editor build passed. All 94 Python tests and Ruff passed.
Factory Blender 5.2.2 profile checks passed for active shader constants, sidedness,
unsupported advanced BSDF settings, transparency, linked/procedural graphs and
animation. The test confirmed that this Blender version keeps node shading active
despite the deprecated `use_nodes=False` setter: viewport properties must not
replace the active shader values. A legacy non-node branch is implemented but is
not claimed as exercised in this Blender version.

Native acceptance exported a non-default Principled material and verified the
created Unreal graph's base color, roughness, metallic, sidedness and package save.
Real MCP placement/inspection verified that the actor referenced the generated
material. The acceptance record now distinguishes material assets transferred
from shader compilation and visual equivalence, which remain unverified. The
Blender add-on ZIP was rebuilt with these classifications, preserving its previous
archive. Clean ZIP installation/enable/disable and real MCP native export checks
passed. Existing application sessions were not reloaded or replaced.

The complete goal remains active: end-to-end MCP orchestration and durable recovery,
material save-failure acceptance, broader transforms/units, saved-level reopening,
interactive workflows, advanced materials/textures, rigs/animation, clean Unreal
packaging and full capability acceptance still require work.

### Transfer coordinator persistence foundation

`server/core/workflow_journal.py` adds private per-operation receipts for ordered
export, staging, import, verification and optional placement. Record updates use
an actual OS file lock, expected-revision checks, fsynced temporary data and atomic
replacement. Existing operation IDs cannot be reused and terminal outcomes cannot
be replayed through the transition API. Linked/reparse paths and hardlinked record
files are rejected. Known credential fields and bounded-data violations are
rejected before storage.

`forge_inspect_transfer` is a new read-only MCP tool, bringing the current source
registry to 26 tools. It reports retained evidence without treating that evidence
as a current application-state check. An unfinished native intent becomes
`outcome_unknown` after restart; no automatic native replay is allowed. The
coordinator still needs native reconciliation and the connected preview/apply
pipeline. A successful receipt-store test does not establish recovery of native
application assets.

All 112 Python tests and Ruff passed. New checks exercised ordered completion,
terminal/replay rejection, stale revision rejection, active-versus-restarted
inspection, partial/failed/unknown/rolled-back receipts, injected write failure,
credential/size/path rejection, actual lock contention and lock release when a
separate process exits without releasing its handle. Real MCP stdio discovery and
receipt inspection, missing-record handling and input-path rejection also passed.
No native plugin/add-on source changed in this step, and no application session was
reloaded or replaced.

### Manual Unreal / Blender round-trip handoff — 2026-10-11

The original roadmap's bidirectional editing workflow now has its first native
static-mesh milestone. Blender's visible transfer controls use **Send to Unreal**.
The Unreal ForgeMCP panel adds **Send to Blender** and **Import from Blender**.
The latter pulls a named Blender mesh, or the active object when the field is
blank, into a reviewed new Unreal asset without requiring Blender's send button.
See [Roundtrip_Workflow.md](Roundtrip_Workflow.md) for setup and limitations.

The new `forge_preview_send_to_blender` / `forge_apply_send_to_blender` tools
coordinate native Unreal FBX export, private checksum-verified staging and native
Blender import. They share the existing durable transfer journal. Both Unreal
buttons use the external MCP worker. Preview/apply guards reject changed context,
replay and existing destinations. Blender creates editable constant material
placeholders and makes the received mesh active; Unreal shaders are not transferred.

Validation passed on Unreal 5.6.1 Win64 and Blender 5.2.2 LTS:

- All 249 Python tests and focused Ruff checks passed.
- The isolated Unreal Editor target compiled, linked both plugin modules and
  wrote target metadata successfully. The Blueprint-only host target fallback
  was corrected in the build script. Two missing includes in the existing
  material implementation were corrected for the clean non-PCH build.
- Actual MCP stdio acceptance passed Blender -> Unreal -> Blender -> Unreal for
  an asymmetric fixture: vertex/triangle counts, bounds and every vertex position
  matched. Native preview IDs were normalized and FBX front-axis metadata was
  aligned with the existing return importer after acceptance exposed mismatches.
- A typed Blender edit followed by the actual **Import from Blender** worker
  passed connected-session discovery, active-object resolution and edited bounds
  verification. Evidence:
  `Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-92dd32336b734491948c745be6f7d1a1/acceptance.json`.
- The native Blender transfer operators passed preview/cancel/confirm/apply and
  Unreal import/placement, including the new visible labels. Evidence:
  `Saved/RoundtripValidation-20261011/HostProject/Saved/PanelAcceptance-600c951719734ab5819402abe53f80b2/acceptance.json`.
- The Blender 0.2.14 ZIP passed clean-profile install/enable/disable, cached-module
  upgrade and native export authentication/stale/replay checks.
- The rebuilt Unreal development ZIP passed installation and exact DLL loading
  in a fresh Blueprint-only project. Its live health report included both new
  mesh-export capabilities. Evidence:
  `Saved/UnrealPackageAcceptance-81425b48c25f4fa4a6a66faf4c91c871/acceptance.json`.

These are native headless acceptance results. Interactive Slate button operation,
rendered shader appearance, broader UV/normal/unit fixtures and material fidelity
remain unverified. The packages were not installed into the running JasperPrismDev
Editor or the user's Blender profile. The active Codex MCP process also needs a
reconnect to load the new source tools.

This stage uses binary FBX, static LOD0 source geometry and new destinations.
OBJ, automatic replacement/reimport, real-time synchronization, textured shaders,
skeletal/animation transfer and the wider roadmap remain development work.
Next: stable asset bindings and revision tracking, then reviewed recoverable
reimport, followed by conflict-aware/debounced bidirectional live updates.

### Unreal material-instance MCP surface — 2026-10-11

Following the MDS reference audit, Unreal now has typed MCP operations to inspect
loaded constant material instances; preview/create a new instance from a loaded
parent; review scalar, vector and texture overrides on existing or new instances;
apply the preview; and separately preview/save a new instance created in the same
bridge session. Asset destinations reject loaded packages and existing disk
files. Parameter previews bind the loaded target's state and reject stale applies.
Edits update only the instance's supported global overrides; they do not rewrite
the parent material graph. Texture overrides require an exact already-loaded
asset path. Saving is separately confirmed and limited to new bridge-created
instances in the current session.

Five native commands and MCP tools are registered: `material_instance_info`,
`material_instance_preview`, `material_instance_apply`,
`material_instance_save_preview`, and `material_instance_save_apply`.
The supported parameter types in this increment are scalar, vector RGBA and
texture. Static switches/masks and specialized parameter families require
separate permutation/rebuild handling. This increment is Unreal-only; Blender
material graphs remain governed by their existing recipe surface.

The UE 5.6.1 `MajesticForge` editor module compiled and linked successfully in the
isolated host with UBT's `-Module=MajesticForge` filter (18 actions). The regenerated
development archive contains 37 files and SHA-256
`06a30f93563effd8ee93558faf1f3f97e6c81deee79c46252106a2b118ad181e`.
The packager verified exact source/build correspondence, plugin module manifest and
Engine BuildId. The existing clean-project package verifier then installed the ZIP
in a disposable Blueprint-only project, launched Unreal 5.6.1 and confirmed the
exact packaged `UnrealEditor-MajesticForge.dll` loaded. Its native health response
advertised all five new material-instance commands and both mesh-export commands.
This verifies installation, module loading and capability registration, not actual
material-instance parameter edits or save/reopen behavior. The full command target
remains open: this feature adds partial typed coverage for three audited material
operations and does not provide unrestricted command execution or parity with the
audited catalog.

### Live ForgeMCP source-to-runtime checkpoint — 2026-10-11

Read-only MCP calls to `forge_status`, `unreal_project_info` and
`blender_scene_info` succeeded through the connected Codex server. The active Unreal
session reports project `JasperPrismDev`, UE `5.6.1-44394996+++UE5+Release-5.6`,
level `/Game/NewMap.NewMap` and PIE disabled. The live Unreal bridge is version
0.2.0 and does not yet advertise the source's material-instance commands or the
new bidirectional transfer capabilities.

The live Blender session reports Blender 5.2.2 LTS, add-on 0.2.3, an unsaved empty
`Scene` at frame 1, and only the earlier scene/object/material/rig/static-export
capabilities. It does not yet advertise the newer source's skin, import, evaluated
rig, animation or return-transfer operations. No application scene or project was
changed during these inspections.

The full host Editor build was stopped at 129/773 after confirming it was
rebuilding unrelated Engine modules. A targeted `-Module=MajesticForge` build then
compiled and linked the editor plugin successfully. The source-matched 5.6.1
archive passed the existing clean-project install/load verifier in a separate
disposable Editor process. The active JasperPrismDev Editor still advertises its
old native capabilities, and Codex still has only 45 of 52 source-declared tools.
Do not claim the source additions are live in those user sessions until the package
and MCP source are activated and the app/server reconnect normally.
A read-only Asset Registry query for `/JasperPrism` also succeeded without loading
assets. It returned four entries, including the existing
`MI_JasperPrism_Photo` (`MaterialInstanceConstant`) and three materials. This verifies
registry search only; it does not verify instance parameter inspection or modification.
The prior `/JasperPrism/Materials/M_ForgeMCP_Test` asset is present, so its creation
acceptance path must continue to reject that destination rather than overwrite it.
At the same time, the current Codex MCP registry exposes 45 ForgeMCP tools (27
Unreal, 9 Blender and 9 coordination/API tools). It does not yet list the source's
`forge_preview_send_to_blender` / `forge_apply_send_to_blender` or any
`unreal_*material_instance` tools. Thus the connected server can reach the old
native adapters, but the current source tool additions are not yet exposed in this
Codex session; a server reconnect after packaging is still required.
Source inventory cross-check: `server/main.py` currently declares 52 `@mcp.tool`
registrations. The seven additions absent from this session's registry are the two
Send-to-Blender coordinator tools and five material-instance tools; all other 45
source tools are present in the current Codex registry.

### Reviewed persistence for existing Material Instances — 2026-10-11

The save workflow now supports updating an existing loaded `UMaterialInstanceConstant`
that ForgeMCP changed through a reviewed apply in the same bridge session. It rejects
an asset package already dirty before ForgeMCP's edit, binds save preview to the
instance fingerprint and current package-file hash, verifies a unique backup under
`Saved/ForgeMCP/Backups/MaterialInstances`, then performs the explicit package save.
The backup is retained. If Unreal reports failure, the native handler attempts to
restore original disk bytes and reports whether disk restoration succeeded while
keeping the in-memory partial outcome explicit. New-instance no-overwrite saves
remain supported. Multiple consecutive ForgeMCP edits are permitted only while the
current fingerprint still matches the session's tracked state.

The updated editor module compiled and linked with UBT `-Module=MajesticForge`.
The development archive was regenerated with SHA-256
`7e68e7dac28fb8bfafd6a4e7b5bcb1dc1762316c0815be1a59114ee1b2dd9346` and passed the
clean-project package install/load verifier. The health response advertises the
five material-instance operations. Actual native edits, backup creation, save,
rollback and reopen persistence remain unverified. The package is not installed
into the active JasperPrismDev Editor; its old capability set and the old 45-tool
Codex registry remain unchanged.

### OBJ option for Unreal Send to Blender — 2026-10-11

Unreal's **Send to Blender** panel now offers FBX (default) and OBJ. The native Editor exporter stages the selected static mesh; the coordinator validates the exact triangle-only OBJ structure and checks the staged bytes before Blender imports it. The Blender add-on imports OBJ through Blender's native importer, applies the documented axis/unit conversion, welds corner-expanded positions while retaining loop UVs, and reports the source format. Material sidecars and MTL directives are rejected; OBJ does not preserve material graphs and requires the native exporter triangle count to match. The coordinate conversion and geometry fidelity still need an asymmetric live transfer fixture.

The UE 5.6.1 plugin module compiled and linked with UBT's `-Module=MajesticForge` filter. `Artifacts/ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip` (SHA-256 `acc333989b305c69c45aa19a749dc48126f839cb76e9a23ce849e509635956f6`) passed the disposable clean-project install/load verifier. `Artifacts/ForgeMCP-Blender-Addon-0.2.15.zip` (SHA-256 `0847a0c8da97c467827d61f13cd6e09718c750548638015bf3103a1456071d08`) passed the Blender 5.2.2 isolated-profile install, enable, native FBX export, disable and cached-update checks. These checks validate package loading and existing add-on export behavior; neither is an end-to-end OBJ round trip.

The active JasperPrismDev Editor and Blender scene remain untouched. The Codex ForgeMCP registry is still stale relative to source, and the live sessions have not been reconnected to this package. Next acceptance step is a disposable asymmetric mesh OBJ export/import in both directions with vertex, triangle, UV, axis and scale comparisons, followed by normal server/add-on activation and live MCP verification. No real-time bidirectional synchronization is implemented; transfers remain explicit, reviewed operations.

### Asymmetric native OBJ round trip and axis correction — 2026-10-11

A disposable UE 5.6.1 and Blender 5.2.2 native MCP round trip exposed a reflected
axis in the new OBJ importer. The exporter’s vertex ordering and the application's
actual importer matrix showed that the source forward axis must be `NEGATIVE_X`.
After that correction, `scripts/verify_roundtrip_mcp.py --reverse-format obj` passed
through MCP stdio: the exported Unreal static mesh imported to Blender, returned to
Unreal, and matched the original full signed vertex positions, bounds, vertex count
and triangle count. The fixture also made a reviewed Blender transform edit and
exercised the UI worker used by Unreal's **Import from Blender** button. Evidence is
retained under `Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-767d5b4499c8449aab313fd0268564e0`.

This verifies one asymmetric static-mesh OBJ profile in disposable headless
applications. It does not verify all unit settings, complex transforms, materials,
visible panels or live bidirectional synchronization. Blender's package version is
advanced to 0.2.16 to carry the corrected axis mapping; the old 0.2.15 archive must
not be used as the distribution containing this fix.

The corrected Blender 0.2.16 source-only package was rebuilt after restoring the prior 0.2.15 archive from its verified backup. The 0.2.16 ZIP SHA-256 is `293685731aa8fd1e73a57571815bb0340176959e7235868c5d914d258a3730e5`. Its isolated Blender 5.2.2 install/enable/disable, authenticated bridge, and native FBX export checks passed. The existing FBX bidirectional round-trip acceptance also passed after extending the verifier to assert the source format from the durable receipt. Ruff and all eight focused `tests/test_roundtrip.py` tests passed. No Unreal plugin rebuild was needed for this Blender importer correction.

### Bounded reflected Unreal asset properties — 2026-10-11

The audited Asset MCP surface had no loaded-object property query. ForgeMCP now
exposes `unreal_inspect_asset_properties` through native `asset_property_info`.
It is read-only and limited to a single `/Game` or `/JasperPrism` asset. Supported
values include booleans, numeric values, enums, names, bounded strings/display text,
FVector, FRotator, FLinearColor and FColor. It returns native type and editor
editability flags, counts omitted complex/container/transient properties, applies a
result limit, and does not traverse object references. Unreal may load normal
dependencies with the selected asset. `/Engine` and other roots are rejected. This
is property inspection, not generic property editing.

UE 5.6.1 targeted module build and link passed. Actual MCP stdio acceptance against a
saved disposable StaticMesh returned 28 supported values and 35 omitted properties;
all returned entries were marked read-only. An `/Engine` asset query returned
`unsupported_asset_path` without loading it. The Unreal ZIP passed the clean
Blueprint-only installer/load verifier and its health response advertised the new
command. The final package was rebuilt after clarifying that Unreal may load normal
dependencies with the selected object, then passed the clean Blueprint-only install/
load verifier; evidence is under
`Saved/UnrealPackageAcceptance-c9466773e0f644b9b13e865458e0f6d0`. Final package
SHA-256: `c601e889fbb7c094794b44cede89ddfc1da5b9c49908086c294bf6027454e899`.
All 249 Python tests and scoped Ruff passed. Property types outside the fixture,
visible Editor interaction and asset editing remain unverified.

### Reviewed Unreal asset property edits — 2026-10-11

Added `unreal_preview_asset_property_edit` / `unreal_apply_asset_property_edit` for
single editable scalar/enum/name/string/vector/rotator/color properties. The native
adapter validates the proposed native text against the exact reflected property,
binds preview to the target object/class/property/current value, rejects dirty
packages, and applies only after one-use confirmation. It records an Unreal Editor
transaction (setting `RF_Transactional` on the loaded object when absent), verifies
the post-edit value, marks the package dirty and never saves it. Stale previews,
replay, incorrect confirmation, invalid numeric text, non-finite values and dirty
package edits were rejected in the real MCP fixture. `LightMapResolution` changed
from 64 to 128 and was re-inspected at 128. The test package remained unsaved;
interactive Editor Undo behavior remains unverified.

The UE 5.6.1 plugin compiled and linked, and the updated module passed the isolated
native acceptance route through MCP stdio. The final development ZIP passed the
clean Blueprint-only installer/load verifier; evidence is under
`Saved/UnrealPackageAcceptance-b6b4db0856434da0bd72795757559411`. Its health response
advertised both edit commands. Package SHA-256:
`8f0d558c461fbb792784b53f11ec4a17e3dc7b7e9abba932c09042164d4ba6a7`. All 253 Python
tests and scoped Ruff passed. Saving, backup/recovery, complex/reference property
edits and visible Editor QA remain outside this increment. JasperPrismDev and the
user's Blender scene were not changed.

### Stable Unreal / Blender mesh bindings — 2026-10-11

The reviewed static-mesh handoff now carries a stable 128-bit binding ID. Blender
creates it in the export preview and attaches it to the source object only after a
confirmed successful export; its scene remains unsaved. Unreal stores the binding
ID and Blender source snapshot SHA-256 in imported static-mesh package metadata.
Unreal-to-Blender reuses stored identity, or derives one from the project and asset
path for an unbound Unreal asset; Blender stores it on the received object. The
Blender add-on is now 0.2.17.

Actual MCP stdio acceptance runs transferred Blender → Unreal → Blender → Unreal
over both FBX and OBJ, checked the same binding in both adapters, restarted the
disposable Editor, loaded the saved asset and verified both binding ID and stable
content fingerprint after package reload. FBX evidence:
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-c81bd65ae3254bec9f6d152e43add025/acceptance.json`;
OBJ evidence:
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-067bae889d9c45ce9a49fb04d6924b01/acceptance.json`.
UE 5.6.1 compiled and linked the plugin; the packaged plugin passed clean-project
loading. The Blender 0.2.17 archive passed clean-profile install/enable/disable and
native export checks. All 253 Python tests and scoped Ruff passed.

Packages: Unreal `Artifacts/ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip`
(SHA-256 `966952417301ff7c81950d6d34a438b88e51c454aed70af8f1014c472a827021`);
Blender `Artifacts/ForgeMCP-Blender-Addon-0.2.17.zip` (SHA-256
`ca305c61b53f6ca2f9cdcb9e321c3cf2cdf834de27b10d6663ca8806ffbb93a3`). Interactive
Slate operation and visible QA remain unverified. Binding IDs and fingerprints are
identity/revision foundations only; reviewed replacement, recovery, conflict
detection and real-time synchronization remain future work. JasperPrismDev and the
user's Blender scene were not modified.

### Read-only mesh binding revision comparison — 2026-10-11

Added native `binding_info` for Blender and `mesh_binding_info` for Unreal, plus
MCP tools `blender_inspect_mesh_binding`, `unreal_inspect_mesh_binding` and
`forge_compare_mesh_binding`. The comparison reads each app's current content
fingerprint and saved baseline; it reports synchronized, Blender changed, Unreal
changed, both changed/conflict, binding mismatch, unbound or missing baseline.
It creates no apply preview and edits or saves neither asset. Unreal's baseline
covers the static-mesh description and material-slot references, not edits inside
referenced material graphs.

Actual MCP stdio acceptance observed synchronized state on the original and
returned assets, then Blender-changed after changing the received object's transform.
It repeated those checks for FBX and OBJ and confirmed the binding and Unreal content
fingerprint survived Editor restart/reload. FBX evidence:
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-3e84275463df48bfa485a5295587346e/acceptance.json`;
OBJ evidence:
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-6175c320c6284cfeacc7a0c806a209b0/acceptance.json`.
Coordinator tests cover all comparison result states; Unreal-changed and two-sided
conflict were not exercised by native Editor edits.

UE 5.6.1 compiled/linked; clean-project plugin loading passed under
`Saved/UnrealPackageAcceptance-b78da4e5c4df4564b737294977cb154f`. All 260 Python
tests and scoped Ruff passed. Blender add-on 0.2.18 passed clean-profile install,
enable/disable and native export checks. Package SHA-256 values:

- Unreal `Artifacts/ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip`:
  `1e1a80f62bc1e3ed04e507b7062e0e1924a3c7f73cf1c56389f24b98010adb4a`
- Blender `Artifacts/ForgeMCP-Blender-Addon-0.2.18.zip`:
  `20371c73a2ca8013a2f4b11c6fd3321fe107da8de99a1bd047cca0a0754d6409`

Next is reviewed asset replacement/reimport with package backups, material-slot
preservation, rollback and recovery evidence. The current transfer remains new-path
only; the live user applications were not replaced or modified.

### Unreal editor-host build verification — 2026-10-11

The complete ForgeMCPDevEditor target now builds and links against UE 5.6.1,
including `UnrealEditor-MajesticForge.dll`. The clean build exposed missing
complete-type includes for reflected text properties and weak object pointers;
those includes are now explicit. The repository's custom build script also
encountered an obsolete unity response file left by UBT for the non-unity editor
module, so it now skips only that stale editor-module response while preserving
the runtime module's generated unity response. The disposable host build passed
its final editor DLL link and target metadata checks. JasperPrismDev remained open
and was not rebuilt or modified. This validates compilation only; it does not
replace the installed plugin or verify visible controls in the user's live Editor.

### Reviewed bound-mesh replacement acceptance — 2026-10-11

Implemented the opt-in `replace_existing` path for Blender-to-Unreal transfers.
The review binds the preview to the source binding/revision, target revision,
saved package fingerprint and exact material-slot identities. Apply makes and
SHA-256 verifies a package backup before native FBX reimport, disables imported
materials/textures, restores the original Unreal material assignments, saves the
existing asset and commits the Blender revision baseline only after verification.
Normal imports remain new-path only; the replacement option requires saved assets
and cannot place an actor as part of the same operation.

Fixed a native preview identity comparison that compared `Package.Asset` against
the recipe's package-only path. The native check now normalizes the reviewed object
path before comparison. The acceptance verifier also checks post-replacement
revision metadata using the distinct source and target revision fields.

The updated plugin compiled and linked in the disposable UE 5.6.1 host. Actual
ForgeMCP MCP-stdio acceptance passed in
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-04f3345f9a664be6a3e66a2ec778d26b/acceptance.json`.
It exercised a Blender edit, reviewed replacement of the existing bound Unreal
mesh, retained material assignment, verified backup file hashes, synchronized
binding comparison, the `Import from Blender` worker, and binding/revision reload
after restarting the disposable Editor. Python suite: 266 passed; Ruff and
`git diff --check` passed. The root Unreal plugin was not installed into the
JasperPrismDev project. Interactive Slate controls and visible QA remain
unverified. The acceptance used a `.uasset`-only package backup; sidecar packages,
forced reimport/save failures, rollback recovery, and native conflict edits still
need dedicated validation. This is reviewed manual handoff, not real-time sync.

### Reviewed Unreal level-actor property access — 2026-10-11

Added MCP tools `unreal_inspect_actor_properties`,
`unreal_preview_actor_property_edit` and `unreal_apply_actor_property_edit`.
The native Unreal adapter reads bounded simple reflected values (numeric, boolean,
enum/byte, name/string/text, vector, rotator and color) and editability metadata.
One-property previews bind the exact actor, class, current world, field and prior
value. Apply revalidates them, uses Unreal's native property parser and editor
change notifications, records an editor transaction, verifies the new in-memory
value and leaves level saving separate. Component fields, arrays, object traversal,
PIE editing and implicit save are not supported.

The disposable native MCP acceptance exercised inspection, successful apply,
read-back and stale competing-preview rejection against the placed actor in a
UE 5.6.1 test project. Evidence is in
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-3b089c9b63e34e05a614f8bac630e554/acceptance.json`.
The updated Unreal plugin and `ForgeMCPDevEditor` target compiled and linked in
that disposable host. This does not verify visible Details-panel refresh or Undo;
JasperPrismDev was not rebuilt or modified.

## Reviewed Blender modifier inspection and creation — 2026-10-11

Blender object inspection now includes viewport/render visibility and supported
settings for Subdivision, Bevel, Solidify and Weighted Normal modifiers. The
existing reviewed `blender_preview_scene` / `blender_apply_scene` recipe path can
add these modifier types to mesh objects with bounded per-type settings. Preview
fingerprints include current modifier state, duplicate names are rejected within
a batch and against the scene, and apply removes newly created modifiers if a
batch fails. Linked and edit-mode meshes remain protected. This slice does not
edit or remove existing modifiers, use arbitrary node modifiers, or expose every
Blender modifier property.

Native MCP stdio acceptance passed in the disposable Unreal/Blender transfer
host at
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-c173f276243f4c3c99066f77d2f528c7/acceptance.json`.
It applied and inspected a reviewed Bevel, verified its `segments` setting, and
confirmed a competing stale Subdivision preview was rejected without creating
that modifier. All 272 Python tests, Ruff and `git diff --check` passed. The
interactive Blender UI was not visually tested, and this does not establish
real-time two-way synchronization.

## Reviewed Unreal actor component inspection — 2026-10-11

Added the read-only MCP tool `unreal_inspect_actor_components`. It resolves one
exact actor in the active editor world and returns at most 128 owned components
with names, paths, class paths, registration/activity, scene attachment, visibility,
relative transforms, world location, primitive mobility and an already-assigned
static mesh path. It does not load assets, traverse arbitrary object references,
or expose/edit component properties. The response identifies its world and reports
the total count and truncation state.

The disposable UE 5.6.1 MCP stdio acceptance inspected the placed actor and verified
its component's static mesh path matched the asset already reported by actor
inspection. Evidence is in
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-f2e534694b5c4672918295aff7dac9b5/acceptance.json`.
The plugin and `ForgeMCPDevEditor` target compiled and linked in that disposable
host. Interactive Editor selection/Details behavior and broad component property
access remain unverified.

## Read-only Unreal component property inspection — 2026-10-11

Added `unreal_inspect_component_properties`, which resolves one exact component
already owned by an actor in the current editor world. It returns a bounded page
of supported simple reflected scalar, enum, name/string/text, vector, rotator and
color properties, including native type and whether each field is editable in
the Editor. Arrays, nested references, object loading and writes are excluded;
component paths are resolved by enumerating loaded actors rather than loading a
caller-provided object path.

The disposable UE 5.6.1 MCP acceptance inspected the placed static-mesh component,
verified its exact component path and owning actor, and received supported
properties through the registered MCP tool. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-24f5a0661f524973a5a938ab7682f08b/acceptance.json`.
The updated plugin and editor target compiled and linked in the disposable host.
Property editing for components and interactive Details-panel refresh remain
unverified.

## Reviewed Unreal component property edits — 2026-10-11

Added `unreal_preview_component_property_edit` and
`unreal_apply_component_property_edit`. A preview binds one exact loaded
component, owner actor, class, Editor world, property and prior value. Apply
rechecks that state, uses Unreal's native `FProperty` parser and change
notifications, records an Editor transaction, verifies the in-memory result and
leaves level saving explicit. It reuses the bounded simple-property type set;
arrays and nested references remain excluded. Editor editability metadata is not
a guarantee that every proposed text representation parses; invalid values are
rejected before mutation.

Native MCP acceptance changed the static-mesh component's
`StreamingDistanceMultiplier` from `1.000000` to `1.125000`, read the new value
back through MCP, confirmed `saved: false`, and rejected a competing preview as
`stale_preview`. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-d14e0ccc28ea4c65ae894a5066269bfd/acceptance.json`.
The disposable UE 5.6.1 plugin and editor target compiled and linked. The live
test established this float-property path; other component property types and
interactive Undo/Details behavior need separate verification.

### UE bitfield boolean property parsing — 2026-10-11

Fixed the component/actor property adapter's handling of Unreal bitfield booleans.
`uint8 Name:1` fields are `FBoolProperty` values even though `GetCPPType()` reports
`uint8`; the adapter now reports the reflection class, accepts `true`/`false` and
`1`/`0`, accesses the value through the `FBoolProperty` container APIs, and emits
the same lowercase normalization used by the Editor export. This also avoids
mistaking the export function's false return for an export failure when the actual
boolean value is false. Bridge errors now preserve a bounded, single-line native
diagnostic so property/parser failures remain actionable.

The disposable MCP acceptance successfully changed `bRenderInMainPass` from
`true` to `false` through preview/apply and confirmed the false value by a fresh
component inspection. The same run also passed float editing, stale preview
rejection and the larger Unreal/Blender coordinator acceptance:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-c54ba6efd8fd43bfbec038032412e55b/acceptance.json`.

## Read-only selected Unreal actors — 2026-10-11

Added `unreal_get_selected_actors`, returning a bounded list of actor IDs, names,
labels, classes and paths from the active Editor selection, plus the current level,
total count and truncation status. The operation does not change selection or actor
state. This provides a reliable selection context for future explicit actor workflows;
it does not implicitly authorize or execute edits.

The MCP stdio test verifies tool registration, read-only annotations, disconnected
behavior and input bounds. The disposable native workflow acceptance queries the
tool against the running UE Editor and checks the response shape. Interactive actor
selection behavior in the visible Slate Editor remains a separate manual check. The
acceptance response was empty because the fixture had no selected actors; evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-f9e33c176feb4571b2ad05fc8068e5aa/acceptance.json`.

## Reviewed typed Blueprint functions on existing assets — 2026-10-11

The existing Blueprint preview/apply recipe now accepts bounded function definitions
with up to 16 typed primitive inputs and outputs, plus pure-function metadata. In the
same reviewed edit, callers can add the function entry/return references and connect
compatible pins using the native graph schema. Apply compiles the Blueprint and
reports diagnostics; it leaves the asset unsaved. Recovery removes newly created
function graphs if a later operation fails, and stale state is rejected before the
recipe is revalidated against the changed Blueprint.

Native MCP stdio acceptance created an unsaved disposable Blueprint, previewed and
applied a pure float function with a connected input/return, verified zero compiler
errors and warnings, confirmed a competing preview was stale, then forced a later
connection failure and verified exact inspected-state rollback including removal of
the new function graph. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-0dda64ca21714bd28a9c45a1c2c26666/acceptance.json`.
The UE 5.6.1 disposable editor target compiled and linked. The full suite and
interactive Blueprint editor/Undo behavior remain separate checks; existing
function signatures still cannot be modified or removed.

## Read-only Unreal Editor log query — 2026-10-11

Added `unreal_read_editor_log`, which returns the active project's bounded log
tail from the native Editor bridge. The adapter reads no more than 128 KiB from
the generated project log, returns at most 200 lines (default 100), caps each
returned line, and reports whether either byte or line limits truncated the
tail. It does not accept caller-supplied paths or expose arbitrary file access.

The native transfer-workflow MCP acceptance read an eight-line tail from the
disposable Unreal Editor through the registered MCP tool and validated the
response and truncation metadata. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-b82b558d28cb48408ef163e7fcaa6665/acceptance.json`.
The UE 5.6 Editor module source compiled and linked against its generated native
response files; the packaged plugin then loaded in a fresh project and returned
log lines through the native adapter. Package SHA-256:
`2f937ca7dd9c4fa37d015cbef41e7c3f11dcd98c9f28e248de314a13ba399bdf`.
The normal full-target build command was blocked because Live Coding is active in
the already-running JasperPrismDev Editor; that user session was left untouched.
All 274 Python tests, Ruff and `git diff --check` passed. This is a bounded tail
of the active file log, not an in-memory history of every log device or category.

## Reviewed Blender mesh topology replacement and inspection — 2026-10-11

Added `set_mesh_geometry` to the reviewed Blender scene recipe. It replaces a
local mesh's vertices/faces with up to 512 vertices and 512 faces, after validating
all finite coordinates, face indices, Object Mode and supported mesh data. It
rejects skinned meshes, shape keys, UV/color/custom attributes and multiple
material slots rather than silently remapping or discarding them. Existing mesh
data is copied before editing, so a failed operation restores the original
datablock and cleans the temporary copy. Geometry fingerprints now include face
indices as well as vertex coordinates, so topology changes invalidate previews.

Added the read-only `blender_inspect_mesh_geometry` MCP tool with independently
bounded vertex and face pages (up to 256 records each), including coordinates,
polygon indices, smooth state and material index. Blender's authenticated native
request bound is now 512 KiB, while an individual scene recipe remains capped at
256 KiB and 32 operations.

The disposable native MCP workflow replaced topology and read back exact faces,
rejected a stale competing preview, then injected a failure after a later
topology replacement and verified exact vertex/face restoration with no rollback
errors. It also applied the maximum tested 512-vertex/510-face payload over MCP
and read the final vertex/face pages back. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-5dc407cd1e4849b2878c6a61ab30bb73/acceptance.json`.
All 275 Python tests passed, as did Ruff and `git diff --check`. Blender 5.2.2
clean-profile installation/lifecycle checks passed for
`Artifacts/ForgeMCP-Blender-Addon-0.2.20.zip` (SHA-256
`bc406507b176fd4aadc5b261e2e418c1b4126a4b665f2cd4c37560316c73ffdb`). The
acceptance fixture and package checks are headless; interactive panel QA remains
separate. This is not unrestricted geometry access: UV/custom-data and skinned
topology remapping remain unsupported.

## Reviewed Blender modifier settings — 2026-10-11

Extended the typed Blender scene recipe with `set_modifier_settings` for an
existing supported modifier on a local mesh in Object Mode. Supported settings
are validated against that modifier's allowed properties and read back after
application. A failed later operation restores captured settings, and modifier
state participates in preview fingerprints so competing edits invalidate old
previews. This changes local Blender scene state only; modifier transfer to
Unreal remains unsupported.

Actual native MCP stdio acceptance added a Bevel, injected a later-operation
failure and verified rollback restored the original `segments` value, then
confirmed stale competing previews were rejected and a fresh applied value was
read back. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-703f28a17050474690d1ca575a79cf3a/acceptance.json`.
All 274 Python tests passed; Ruff and `git diff --check` passed. Blender 5.2.2
clean-profile installation and native add-on acceptance passed for
`Artifacts/ForgeMCP-Blender-Addon-0.2.19.zip` (SHA-256
`019c2ec5d93d61b37c6740655ae4ce24621c65e308c483ae2012518b79080f2a`). The
interactive Blender panel was not visually tested, and the installed running
user session was not replaced.

## Reviewed Blender UV-layer inspection and editing — 2026-10-11

Added the read-only `blender_inspect_mesh_uvs` MCP tool for paged UV-loop data,
layer names and loop-to-vertex references. Added the typed `set_uv_coordinates`
scene operation for up to 512 existing loops on one exact UV layer. Coordinates
are finite and bounded but may lie outside 0..1 for tiled workflows. Preview
fingerprints bind the requested layer and its target range; apply copies the mesh
datablock before writing and verifies each coordinate, so failures restore the
original data. The edit preserves topology and does not save the `.blend` file.

Native MCP acceptance read the factory Cube's `UVMap`, edited a loop, read back
the result, rejected a competing stale preview, then injected a post-write
failure and verified exact rollback without errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-13d956c8a514448d911e23ea431a6eea/acceptance.json`.
All 276 Python tests passed, as did Ruff and `git diff --check`. The Blender
0.2.22 clean-profile package verifier installed the ZIP, applied and inspected
topology and UV edits from the packaged add-on, then removed the disposable test
object and passed lifecycle/export checks. ZIP SHA-256:
`a22f5a2f69de86dcca819be30b94c3a5d97429a4f66fbc7c7063be6250f7b50c`. UV layer
creation, seams/unwrap algorithms and material-node editing remain separate
capabilities.

## Reviewed Blender UV-layer creation — 2026-10-11

Added `create_uv_layer` as a typed scene operation. It creates an exact named
layer on a local mesh in Object Mode, optionally initializes every loop for
meshes of up to 512 loops, and can be followed by bounded `set_uv_coordinates`
operations in the same reviewed recipe. Creation rejects duplicate names and
malformed initial loop data; the existing mesh-copy transaction gives the new
layer the same preview, read-back and rollback protections as UV edits.

Actual MCP stdio acceptance against disposable Unreal 5.6.1 and Blender 5.2.2
created and edited a UV layer in a reviewed recipe, read all six loop coordinates
back, then injected a failure immediately after creating another layer. Apply
reported `rolled_back` with no rollback errors, and a subsequent MCP query
confirmed the failed layer was absent. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-a94a2f5d780c4f3ba4b4941b3bdb96d8/acceptance.json`.
The Blender 5.2.2 clean-profile verifier also installed package 0.2.24, created,
edited and read the layer, then passed lifecycle/export checks. ZIP SHA-256:
`dfa6942328ad5909450a7d8d526483762cc4ede3b0c5884a65d2a7258964e821`. The complete
Python suite passed (277 tests) and Ruff passed. Seam authoring, unwrap
algorithms and packing optimization remained future capabilities at that
checkpoint; Smart UV Project is covered below.

## Reviewed Blender Smart UV Project — 2026-10-11

Added `smart_uv_project` to the typed, preview/apply scene-recipe system. It
unwraps all faces of one local static mesh into an exact UV layer using Blender's
native Smart UV Project operator, with bounded angle limit and island margin.
The operation supports up to 200,000 loops, creates the named layer when absent,
temporarily manages selection and Edit Mode, checks generated coordinates are
finite and within 0..1, and restores the prior selection and mode. The stale
preview fingerprint includes topology, layer identity and every current UV in
the target layer. Apply edits a copied mesh datablock so transaction failures
restore the exact previous UV values.

Actual MCP stdio acceptance on a disposable mesh verified projection and UV
read-back, rejected a competing stale preview, injected a post-projection
failure, and confirmed rollback restored all coordinates without rollback
errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-e130c52eb760434dac3c4fc90c53599e/acceptance.json`.
Blender 5.2.2 clean-profile package 0.2.25 passed UV-layer creation/editing,
Smart UV Project, installation/lifecycle and export checks. ZIP SHA-256:
`917457985e72a6732734fee507fb72bce76c3aa9ef76ef51828b49217ea65d05`. All 278
Python tests and Ruff passed. This is UV unwrapping, not seam authoring or
packing optimization; those remain future capabilities.

## Reviewed Blender mesh seam inspection and editing — 2026-10-11

Added the read-only `blender_inspect_mesh_edges` MCP tool and native
`mesh_edge_info` command. It pages up to 256 indexed edges and reports endpoint
vertices plus seam and sharp flags. Added the typed `set_mesh_edge_seams` scene
operation for up to 512 unique indexed seam changes per recipe. Preview
fingerprints bind the targeted edge flags and mesh datablock; apply copies the
mesh before writing and verifies every flag, allowing the existing transaction
to restore the source mesh after a failure. Sharp-edge changes are inspection
only in this increment.

Actual MCP stdio acceptance on disposable Blender 5.2.2 and UE 5.6.1 inspected
five edges, set a seam, rejected a competing stale preview, injected a failure
after the seam write, and confirmed rollback left the seam set with zero rollback
errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-3dff767e4bf442b19f41ae0056c5cbe9/acceptance.json`.
Blender 5.2.2 clean-profile package 0.2.26 passed seam inspection/editing plus
UV projection, install/lifecycle and export checks. ZIP SHA-256:
`9547d83dc6876e28c1348d043f3b5eb44f0727265f3f685b3d8dd001b0e28dc7`. All 279
Python tests and Ruff passed. Seam-aware unwrap/packing and transfer of normals,
materials/textures, skeletal data and animation remain open.

## Reviewed Blender UV island packing — 2026-10-11

Added typed `pack_uv_islands` to run Blender's native `bpy.ops.uv.pack_islands`
against an exact existing UV layer. Packing uses a bounded 0-to-0.5 margin,
requires a local mesh in Object Mode, and is limited to 200,000 loops. The helper
temporarily activates the mesh/layer, verifies all resulting loop coordinates
remain finite and within 0..1, and restores the prior active object and selection.
Preview fingerprints include topology, layer identity and all target UV values;
apply copies the mesh so failed batches can roll back.

Actual MCP stdio acceptance on disposable Blender 5.2.2 and Unreal 5.6.1 packed
all 24 Cube UV loops and read them back, rejected a stale competing preview, then
injected a post-pack failure and verified exact UV restoration with zero rollback
errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-a77b3e52f0c241f99a3a76a0eb386f0d/acceptance.json`.
Clean-profile Blender 5.2.2 package 0.2.28 passed UV creation/editing, projection,
seam editing, unwrap and packing, native export, and add-on lifecycle checks. ZIP
SHA-256: `943fc98437cbcbbc76ea2b78beb25bea091beaed85a0f3b47e01ad5a34c606f6`.
All 281 Python tests and Ruff passed. Automated seam placement, remaining transfer
payloads and real-time synchronization remain outstanding.
The Codex-connected ForgeMCP runtime was separately checked after packaging: its
Blender session still reports add-on 0.2.3, so package 0.2.28 and its updated MCP
recipe schema are not active in that session. The connected Unreal bridge reports
5.6.1 and ForgeMCP 0.2.0. Reinstall/reload the Blender package and reconnect the
server before claiming the new operation is available in the user's live tools.

## Reviewed Blender seam-aware UV unwrap — 2026-10-11

Added typed `unwrap_uv` to run Blender's native angle-based or conformal UV
unwrap against the selected mesh's marked seam edges. It requires at least one
seam, uses a bounded 0-to-0.5 UV margin and a mesh limit of 200,000 loops, and
creates the requested layer if missing. Apply operates on a copied mesh and
checks the resulting loop coordinates. Preview state fingerprints include all
target-layer UV coordinates and every seam flag on the mesh so edits to either
invalidate a pending unwrap.

Actual MCP stdio acceptance marked all 12 edges on a disposable cube, unwrapped
all 24 UV loops, read them back, rejected a stale competing preview, then
injected a post-unwrap failure and verified exact UV restoration with no rollback
errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-07ee4d942c9544b5be9ffc2989bb6ac4/acceptance.json`.
Blender 5.2.2 clean-profile package 0.2.27 passed seam marking, seam-aware
unwrap, UV read-back, lifecycle and export checks. ZIP SHA-256:
`73f0334b35b58c8df7a0ba0840c7ad1bfe51c16a8a4ef0e695f34a7bc34b22ff`. All 280
Python tests and Ruff passed. Automated seam placement and UV island packing
remain separate capabilities.

## Reviewed Unreal active-world actor search — 2026-10-11

Added read-only MCP tool `unreal_find_actors`. It searches the active editor world
by a case-insensitive substring in the UObject name or display label, exact native
class path, or both. Results support bounded offset/limit pagination up to 1,000
actors per page and report total matches, returned count, truncation and level
identity. The native bridge requires at least one filter, rejects unknown fields
and malformed bounds, and performs no selection or world mutation. Added the
native `find_actors` health capability and source allowlist route. Updated the
pinned Unreal reference coverage: its `find_actors` and `find_actors_by_name`
registrations now have partial coverage. Exact actor-tag filtering and optional
location/rotation/scale output are now implemented and verified; wildcard/exact
name patterns and property predicates remain unsupported.

The UE 5.6.1 plugin compiled and linked in the isolated transfer host. Actual MCP
stdio acceptance verified combined name/class pagination, exact actor-tag search,
optional transform values within native floating-point tolerance, absent-tag zero
results and rejection of a request with no filters. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-d0cce0c9144344ea874df7b4711f218b/acceptance.json`.
This feature advances the MCP server and Unreal plugin to 0.2.1; the source,
packaged descriptor, in-editor label and health response use the same version. The
0.2.1 Win64 development ZIP passed clean-project installation and native module
load with `find_actors` in packaged-health assertions. Evidence:
`Saved/UnrealPackageAcceptance-8b8b1c6d14924dee91dd85537fccce90`. Package SHA-256:
`bf7992c3a0e8f9ec50d3aa4bec32d59c073f58135375396e38aded998ef32901`. The current
Blender add-on remains 0.2.29 because this feature did not change Blender source;
its rebuilt package passed clean-profile install, feature and lifecycle checks, SHA-256
`2f7af27e63eb7383727479b669c550e56fbefc26c8e134bc05799fe6e532d20f`. All 282
Python tests, Ruff, Python compilation and `git diff --check` passed. The live
JasperPrismDev editor and connected MCP server still run 0.2.0 and do not expose
this increment; deployment requires the project plugin update and editor/server
reconnect. The broader Unreal command catalog and full Blender coverage remain open.

## Reviewed Blender active Action inspection — 2026-10-11

Added read-only MCP tool `blender_inspect_animation`, backed by the Blender
`animation_info` adapter command. It reports an object's active Action, Blender
5.2 layered-Action slot/layer/strip identity, F-curve metadata and paged keyframe
frame/value/interpolation/type data. F-curve pages are limited to 32 and
keyframe pages to 128; offsets, non-finite values and Actions exceeding the
10,000-curve inspection bound are validated. This inspects the active Action
only; it does not edit curves, enumerate NLA playback, retarget animation or
transfer animation to Unreal.

The Blender 5.2.2 clean-profile installed-ZIP verifier passed Action inspection
and pagination using an isolated probe mesh, followed by the existing UV,
export, install/lifecycle checks. Actual MCP stdio acceptance in a disposable
UE 5.6.1/Blender 5.2.2 workflow created two transform keyframes on
`ForgeTopologyProbe`, read all three location curves and both keys, then queried
a second page and verified frame 7. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-34443b7cde834a35844977ecf2bfc0d1/acceptance.json`.
The add-on package is version 0.2.29, SHA-256
`2f7af27e63eb7383727479b669c550e56fbefc26c8e134bc05799fe6e532d20f`. All 281
Python tests and Ruff passed. The connected Blender add-on remains 0.2.3, so
this development package has not yet been activated in the user's live Blender
session. Action editing, NLA, retargeting and animation transfer remain open.


## Reviewed Blender active Action key editing — 2026-10-11

Extended the typed scene recipe with `set_keyframe`, which updates one existing
key selected by the curve and key indices reported by `blender_inspect_animation`.
The operation requires an active Action, bounds the target frame/value, rejects an
occupied frame, checks the inspected scene fingerprint before apply, copies the
Action before mutation, sorts/updates the native curve and reads the resulting key
back. The existing Action remains available; the scene and blend file are not saved.
Key deletion, interpolation/handle edits, NLA, retargeting and animation transfer
are not included.

The Blender add-on advances to 0.2.30 and the MCP server schema to 0.2.2. The
clean-profile 0.2.30 ZIP verifier installed the packaged add-on, created two
location keys, moved the first from frame 3 to 4 while changing its value from 0
to 2.5, and confirmed that inspection read back `(4, 2.5)` and `(7, 1)` on a copied
Action. MCP stdio acceptance also rejected moving a key onto an occupied frame and
verified the successful edit through the disposable UE 5.6.1/Blender 5.2.2 pair.
Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-022258711d134e13a77517c81807d17e/acceptance.json`.
The package SHA-256 is
`6a8efb73c9d14973da937ce5853a746bc1351902411b73b711b99427799e8ec9`. All 283
Python tests, Ruff, Python compilation, `git diff --check`, packaged-addon checks
and the two-application MCP acceptance passed after this slice. The connected Blender add-on remains 0.2.3 and
the connected MCP process remains 0.2.0, so neither live session exposes this
increment yet.

## Current implementation checkpoint — Unreal Content Browser commands and session discovery (October 11, 2026)

ForgeMCP server 0.2.4 and Unreal plugin 0.2.3 add `unreal_get_selected_assets`, `unreal_open_asset`, and `unreal_sync_content_browser`. The selection query returns a sorted, bounded Asset Registry description. Open and sync accept one exact top-level `/Game` or `/JasperPrism` asset path. Opening loads and opens the native editor but does not save; it rejects unattended sessions because Unreal may crash while persisting a Slate toolkit layout without a desktop window. Sync reports that navigation was requested and explicitly does not claim visible focus. The Unreal reference audit now classifies these three commands as partial coverage.

The plugin compiled and linked against UE 5.6 in the disposable `TransferImportValidation` host. The 0.2.3 Win64 development package is `Artifacts/ForgeMCP-Unreal-Development-0.2.3-UE5.6.1-Win64.zip`, SHA-256 `4c275606b8e7c8da0d95c1393c50f2ad1cea6bcc03035f975d6b090c9d69ce85`; its clean-project plugin load verifier passed. The full Python suite passed (284 tests), with Ruff, compileall and `git diff --check` passing. Disposable native MCP acceptance passed after correcting session discovery and verified selection query, sync request and the expected unattended-editor rejection for asset opening. The selection was empty before and after sync in the headless host, so visible Content Browser selection/focus remains unverified. The earlier unguarded open experiment returned success, then Unreal crashed during Slate layout persistence; the final plugin guard prevents this in unattended mode. Interactive opening remains to be verified with a connected desktop Editor. Evidence: `Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-5303bbea846142849cee8bda590e68a7/acceptance.json`. No user project or Blender profile was changed. The connected session registry still reports the user applications disconnected, so live project verification remains outstanding.

Live connector checkpoint: Codex currently reports the connected ForgeMCP server at 0.2.0 with zero connected Unreal/Blender sessions. The source and distributable builds are 0.2.4/0.2.3/0.2.30; restart or reconnect the MCP server and launch the updated apps before attempting live use.

## DataTable inspection — Unreal plugin 0.2.4 / MCP server 0.2.5

The MCP registry adds `unreal_inspect_data_table_schema`,
`unreal_list_data_table_rows`, and `unreal_inspect_data_table_row`. The native
editor bridge restricts exact asset paths to `/Game` and `/JasperPrism`, reports
bounded row-struct field metadata and supported simple values, and provides sorted
row-name pagination. It does not edit DataTables or traverse nested/container values.

`scripts/verify_data_table_mcp.py` passed against a disposable UE 5.6.1 Editor and
the actual MCP stdio server. Schema reflection, two-page row listing, exact row
values, missing-row rejection, `/Engine` path rejection and unchanged saved-package
SHA-256 were verified. Evidence is under
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/DataTableAcceptance-228e614311d0470989d332f6fcba60e6/acceptance.json`.
The 1,443,828-byte Unreal development ZIP passed clean-project extraction and native
plugin-load verification; SHA-256 is
`1991ec9e3ea93c9f741242708410bb9f1f33360b1dc3ebece0368604aa27b16e`.
All 284 Python tests and Ruff passed. This validates the isolated MCP/plugin path,
not activation in the separately configured Codex server or an interactive editor.
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

Codex's connected ForgeMCP endpoint still reports server 0.2.0 and six registered sessions, all disconnected (0 connected). The development MCP server and tools in the sections above are verified through isolated MCP stdio acceptance, but are not yet loaded into the connected Codex endpoint. Restart/reconnect that endpoint before claiming its live activation.

## DataAsset discovery — Unreal plugin 0.2.5 / MCP server 0.2.6

Two read-only MCP tools now cover DataAsset class and instance discovery:
`unreal_list_data_asset_classes` enumerates loaded `UDataAsset` subclasses with
filtering and pagination, while `unreal_list_data_assets` uses the native Asset
Registry to list recursively derived assets under `/Game` or `/JasperPrism`. Both
are bounded; class discovery intentionally reports loaded classes and excludes
abstract classes by default, hidden/deprecated classes, and transient Blueprint
reinstancing classes. The Asset Registry query does not load assets.

The disposable UE 5.6.1 MCP acceptance created a concrete `PrimaryAssetLabel`,
found its exact asset path, and discovered `/Script/Engine.PrimaryAssetLabel`.
It also verified that `include_abstract=true` exposes the abstract
`/Script/Engine.PrimaryDataAsset` parent class.
The same run retained the DataTable schema/row checks and confirmed both saved
fixture package hashes were unchanged by inspection. Evidence is in
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/DataTableAcceptance-6b58a5215b944ccaa202d6b40ec4b7f6/acceptance.json`.
The plugin and host Editor target compiled and linked; the 1,451,261-byte 0.2.5
development package passed clean-project extraction/native-load verification.
Package SHA-256: `f01ca3c434de67a75a8b5e6589663afb0517e999f2c45927068f38bc7e5f9889`.
All 284 Python tests and Ruff passed. The latest connected Codex endpoint still
reports server 0.2.0 with zero connected sessions, so activation there remains open.


## Unreal DataAsset class schema — plugin 0.2.6 / MCP server 0.2.7

Added the bounded, read-only `unreal_inspect_data_asset_schema` MCP tool. It
reflects an exact loaded `/Script/` or `/Game/` `UDataAsset` subclass and reports
property ownership/inheritance, editor and Blueprint editability, type/value kind,
container inner/key/value metadata, and object/class reference constraints. It
rejects unrelated classes and does not load DataAsset instances. The existing
class and instance discovery tools remain available.

Native MCP acceptance passed in the disposable UE 5.6.1 host for
`/Script/Engine.PrimaryAssetLabel`, including Boolean and array field metadata,
`include_inherited=false`, bounded/truncated output, and rejection of a non-DataAsset
class. The fixture package hashes remained unchanged. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/DataTableAcceptance-ea81873fd40f4a3f8099540ba9786827/acceptance.json`.
The focused MCP/connection tests passed (22 tests), the full suite passed (284
tests), and Ruff/Python compilation passed. The plugin module compile/link stage
completed and produced the 0.2.6 Editor DLL. A separate full host Editor target
build stopped making progress and was interrupted; that full target result is not
claimed as passed.

The development ZIP is
`Artifacts/ForgeMCP-Unreal-Development-0.2.6-UE5.6.1-Win64.zip` (1,459,271 bytes,
SHA-256 `23cce25e28f13a8bccd8581ac2b0d9d1e569cf29111e07690f84e6296e382520`).
Package extraction and plugin health printed the verifier's PASS marker on an
earlier run, but its later module-path/shutdown stage timed out. After that helper
was corrected, a rerun failed to receive bridge health before its deadline.
Therefore repeatable clean-package bridge startup remains unverified. The currently
connected Codex MCP endpoint still runs ForgeMCP 0.2.0 and reports six stale
registrations with zero connected sessions; it does not expose this new tool.

The reference comparison now records the class schema as partial coverage for
`get_data_asset_properties`; generic scalar asset edits provide partial coverage
for `set_data_asset_property`. DataAsset creation, bulk edits, Mass traits and
interactive activation remain open. Blender receives no version bump for this
Unreal-only change (still 0.2.30). This is an incremental development release,
not the coordinated v1.0.0 completion.

## Guarded Unreal DataAsset creation — plugin 0.2.7 / MCP server 0.2.9

Added `unreal_preview_data_asset` and `unreal_apply_data_asset`. Preview accepts
an exact absent `/Game` or `/JasperPrism` package path, a loaded concrete visible
`UDataAsset` subclass, and up to 32 editable initial values in the supported
scalar/enum/name/string/vector/rotator/color profile. It normalizes values through
Unreal reflection and creates no object. Apply requires the single-use preview ID
as confirmation, rechecks class and target state, creates only a new asset, verifies
native property read-back, and saves only when `save=true` was explicitly requested.
Failure paths roll back the object and any partial package file. Existing asset
edits, arrays/references, and close/reopen validation remain unsupported.

Disposable UE 5.6.1 MCP acceptance passed with a new `PrimaryAssetLabel`: preview
made no changes; wrong confirmation was rejected; apply created and saved the
package; the boolean property read back as native `true`; Asset Registry listing
found it; duplicate creation was rejected as `asset_exists`. DataTable/DataAsset
inspection and invalid-row/class/path rejections also passed. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/DataTableAcceptance-c747d611b5b54609974a427201c3cb8d/acceptance.json`.

All 61 focused MCP/connection/recipe tests and the full 287-test Python suite passed;
Ruff and Python compilation passed. Plugin modules compiled and linked into the 0.2.7 Editor DLL. The subsequent
full host Editor target stalled during UBT actions and was interrupted, so that
broader target is not claimed as passed. The 0.2.7 development ZIP contains 39
files and has SHA-256 `f91c2f17ff401f7830f9ac7537a513c3853f713fcf6e7c1650e151ff9157ec5f`.
The exact 0.2.7 ZIP then passed clean-project extraction, installation, bridge
startup, health/project identity, Editor log query and loaded-binary-path checks.
Evidence is in `Saved/UnrealPackageAcceptance-442035ae2a0b45bb949befecefba6586/acceptance.json`.
Blender receives no version bump for this Unreal-only increment (0.2.31);
coordinated v1.0.0 remains gated on the full roadmap.


## Blender existing-material graph additions — add-on 0.2.31 / MCP server 0.2.8

`edit_material_graph` extends the existing reviewed scene preview/apply tools to
add allowlisted shader nodes and links to a local existing material. It accepts
only exact inspected material/node names, rejects linked input replacement,
unsupported node types, duplicate targets, incompatible sockets and graph cycles,
and protects linked materials. Preview fingerprints the bounded existing graph;
apply verifies the new node/link read-back. Failed batches remove the added links
and nodes and compare the restored graph with its pre-apply snapshot. Existing
node deletion/replacement, moving nodes, and editing their operations or defaults
are still unsupported by this graph-structure slice; simple socket-default edits
remain supported by `set_material_input`.

The MCP stdio schema accepts the new operation through `blender_preview_scene`
and rejects adding/replacing a material output. The clean-profile Blender 5.2.2
package verifier passed with the actual packaged 0.2.31 add-on, including additive
node/link read-back, stale graph rejection, linked-input refusal, rollback
injection, install/enable/disable, cached-module replacement, UV/Action, and native
export checks. Package: `Artifacts/ForgeMCP-Blender-Addon-0.2.31.zip`, 632,173
bytes, SHA-256 `29c48bd6164f4e02a75c8d2cf7e2d8533e125aa61235df96cf6405fbe08c1817`.
The server source version is 0.2.8 because its typed recipe schema changed; the
Unreal plugin stays 0.2.6. The external Codex MCP endpoint remains separately
loaded at 0.2.0 with no connected app sessions, so interactive activation of this
increment is not established.

## Reviewed Blender existing-node graph edits — add-on 0.2.32 / MCP server 0.3.0

Extended the existing `edit_material_graph` recipe with bounded
`shader_node_edits`. A reviewed batch can move exact inspected allowlisted nodes,
set allowlisted Math/VectorMath operations or MixRGB blend modes, and set primitive
defaults on supported unlinked VALUE, VECTOR and RGBA inputs. Linked socket defaults,
unsupported nodes/settings, duplicate edit targets, nodes added in the same recipe,
and out-of-range values are rejected. Existing links remain unchanged. Preview
captures the graph state; apply reads native positions, operations, modes and values
back; failures restore edited node state and remove additions before verifying the
original graph snapshot. Node/link deletion and replacement remain unsupported.

The clean-profile Blender 5.2.2 verifier passed against the 0.2.32 ZIP, including
native position/default/operation read-back, linked-input refusal, stale-preview
rejection, rollback injection after changing existing nodes and adding a node, and
the existing install/enable/disable/export checks. Persistent evidence:
`Saved/BlenderPackageAcceptance-7875e02600814f68956df0561a744371/acceptance.json`.
The package contains 9 add-on modules and is 633,289 bytes; SHA-256
`95ad9d25e3afae94c3c8f4554abb73d5efb903fc63002096c465a3ea2f44385b`. The full
Python suite passed (287 tests); Ruff and Python compilation passed. Unreal remains
at 0.2.7 because this increment changed no Unreal plugin source. The currently
connected Codex endpoint still runs 0.2.0 with six disconnected sessions; this
source/package validation does not establish activation in those original apps.
