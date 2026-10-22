# ForgeMCP active development plan

The authoritative source location is `G:\ForgeMCP`. The original roadmap remains
the historical vision; this plan governs completion evidence for ongoing development.

## Current coordinated release candidate — October 20, 2026

Current local versions are core **0.3.14**, Unreal plugin **0.2.14-alpha.3**, and
Blender add-on **0.2.36-alpha.1**. The exact artifact hashes, acceptance evidence,
and limitations are recorded in the
[coordinated release record](ForgeMCP_Release_0.3.14_2026-10-20.md). The core
suite passes 469 tests; Blender clean-profile acceptance passes; and the
packaged Unreal plugin passes a bounded disposable isolated Landscape test.
The full UAT `BuildPlugin` pipeline remains blocked by the installed engine's
missing `BuildSettings.precompiled` manifest. No existing Editor was updated.

Next safe work is a separately authorized deployment to a disposable or
preserved isolated project, followed by a controlled World Partition/Landscape
test. The observer's unresolved dirty `/Script/SlateCore` row must remain a
review blocker. Do not install into the current long-running Editor or advance
Phase 6C from the disposable smoke result; Phase 6C remains **NO-GO**.

## Next Unreal milestone — Splines, PCG and city reconstruction

Prioritize the [Splines/PCG implementation specification](Splines_PCG_City_Reconstruction.md)
requested October 16, 2026. Deliver versioned capability inventory and read-only
inspection first, followed by spline authoring, roads/junctions/Landscape integration,
PCG graph authoring and generation, city districts, and calibrated reference-image
reconstruction. Full exposure remains the target; each increment must state its
coverage gaps. Reference calibration and accuracy constraints must inform the data
contracts from the first increment. The specification records the live baseline,
acceptance gates and 1:1-scale accuracy contract; these capabilities are not yet
implemented. Existing roadmap obligations and release gates remain active.

Component versions advance when that component receives a validated change.
The versions above are the current local release candidates; component versions
remain independent and do not imply that every feature or workflow is complete.
The coordinated v1.0.0 release is reserved for completion of the roadmap's clean
installation, live-session, capability, recovery, and package acceptance criteria.

October 16 engine-wide alpha: UE 5.6.1 Win64 installation and fresh-project native
and real stdio MCP inspection passed. Keep the installed alpha snapshot separate
from active source development. See [acceptance evidence](UE56_Alpha_Acceptance_20261016.md)
for the 335-test result, full editor-target build, loaded DLL proof and remaining
visible UI/performance gates; [alpha setup](UE56_Alpha.md) covers updates and rollback.

Alpha.9 brings a reference-inspired React UI into the Unreal editor tab. Its first
split-file bundle failed to load from the local file URL; the corrected self-contained
bundle passed Chromium runtime and clean-project UE package checks. Rendering and
control interaction inside the user's standard desktop Editor remain unverified.
See [alpha.9 UI acceptance](UE56_Alpha9_React_Tab_UI_20261016.md) and the [white-tab
fix record](UE56_Alpha9_White_Tab_Fix_20261016.md).
The transfer actions also use locally embedded official Unreal Engine and Blender
marks; see the [logo integration record](UE56_Alpha9_Official_Partner_Logos_20261016.md).
The reference-matched compact panel is recorded in the
[layout refinement note](UE56_Alpha9_Compact_Layout_20261016.md).

## Objective

Alpha.4 transfer-name retention: Blender-to-Unreal defaults to
`/Game/Content/Returns/` and uses the exact Blender source object name. The
reverse handoff keeps the Unreal asset name as Blender's object name when the
optional override is blank. Exact-name collisions are reported instead of
silently renamed. See [alpha.4 acceptance](UE56_Alpha4_Transfer_Names_20261016.md).

Alpha.3 transfer UX: Import from Blender reports the existing Unreal destination
and offers the safe next step; Send to Blender keeps the source name when its
optional name override is blank. The engine package was installed and loaded in
a fresh project; visible panel acceptance remains. See [the fix record](UE56_Alpha3_Transfer_UX_20261016.md).

Alpha.2 transfer fix: built-in `/Engine` meshes support read-only Send to Blender;
typed validation errors no longer disappear inside async exception groups. Both
FBX and OBJ panel-worker handoffs and the installed engine copy passed acceptance.
Native source stays in the engine installation; use explicit source arguments for
host generation and packaging. See [the fix record](UE56_Alpha2_Transfer_Fix_20261016.md).

October 13 Blender expansion: the source now exposes native operator/RNA catalogs
and reviewed creative workflows for primitives, cameras/lights, properties, shader
graphs, numeric keys, modifiers/constraints, save-copy and asynchronous PNG renders.
The complete source registry contains 104 MCP tools. Native and real stdio MCP
tests rendered 4096 × 2304 outputs in disposable sessions. Existing interactive
Blender/client processes require their own version refresh. See
`Documentation/Blender_Creative_Automation.md` for exact execution coverage,
remaining adapters and acceptance evidence; discovery does not imply universal
operator execution.

Develop ForgeMCP into a dependable local MCP platform for practical game-development
workflows across Unreal Engine and Blender. Build on the existing server, Unreal
plugin, and Blender add-on so an authorized AI client can inspect application state,
propose changes, execute supported native operations, verify results, and recover
from failures.

Deliver complete workflows for scene and asset creation, Blueprint authoring,
materials, rigs and animation, and validated Blender-to-Unreal asset transfer. Each
workflow must identify its target session, expose operation limits, protect existing
work, report application-level errors, and provide evidence of resulting changes.

Completion requires repeatable installation on a clean environment, reliable use in
interactive application sessions, tested failure and recovery behavior, documented
capability coverage, and installable packages for both applications. The existence
of a tool, a passing unit test, or an adapter health response alone does not prove a
complete workflow.

## Current capability note — Blender modifiers

The native modifier slice currently supports inspection and reviewed creation of
Subdivision, Bevel, Solidify and Weighted Normal modifiers through the existing
preview/apply scene recipe. It validates bounded settings, protects linked and
edit-mode meshes, includes modifier state in stale-preview checks and rolls back
modifiers created by a failed batch. Editing/removing existing modifiers and
arbitrary Geometry Nodes graphs remain outside this slice. See
`Documentation/Development_Status.md` for the latest MCP acceptance evidence.

Unreal DataTables now support bounded, read-only schema inspection, paginated row
names and exact row-value inspection through three MCP tools. Only `/Game` and
`/JasperPrism` asset paths are accepted; nested/container values are omitted. The
disposable UE 5.6.1 MCP acceptance and unchanged-package hash are recorded in the
development status report.

DataAsset support includes native Asset Registry search under `/Game` or
`/JasperPrism`, loaded `UDataAsset` subclass discovery, and bounded reflected class
schema inspection. The schema reports inherited/editable flags, native property
types, container element/key/value types, and reference constraints without loading
instances. DataAsset creation now uses a separate reviewed preview/apply path for
one new asset of an exact loaded concrete class, with bounded editable initial
values and optional explicit saving. Existing-instance editing now uses `unreal_preview_data_asset_edit` and
`unreal_apply_data_asset_edit`: each operation is bounded to 1–32 supported simple
editable reflected properties on one existing asset, requires an exact single-use
preview confirmation, rejects stale/dirty targets, and only saves when explicitly
requested. Apply preserves a verified pre-edit package backup under the disposable
project Saved directory and validates values after save. Native boolean accessors
handle Unreal bitfield booleans. Arrays, nested containers, object/asset references,
and arbitrary property editing remain unsupported. A disposable UE 5.6.1 test also
reopened the saved asset in a fresh Editor process and confirmed the values.

Unreal also exposes `unreal_inspect_actor_components` for bounded native
component hierarchy, attachment, transform, mobility and assigned static-mesh
inspection, plus `unreal_inspect_component_properties` for a bounded set of simple
reflected values and editability metadata on one exact loaded component. Neither
component tooling provides recursive object/container access. Component values
can also be edited through reviewed `unreal_preview_component_property_edit` /
`unreal_apply_component_property_edit` transactions, with separate level saving.
Bitfield booleans use Unreal's native boolean property accessors and verified
lowercase read-back; component property reflection class is returned alongside
the C++ type string. See the development status record for native MCP acceptance
evidence.

## Next milestone: validated Blender-to-Unreal asset workflow

October 11–12 live integration checkpoint: the Codex host reports server 0.3.1
and connected Unreal bridge 0.2.8 in ForgeMCPDev. The separate Blueprint showcase
passed guarded creation, compilation, save, opening and native read-back. The full
ForgeMCPDevEditor target passed after orderly Editor closure; saved Blueprint
read-back passed again after restart. See `Unreal_MCP_Showcase.md`. Other operation
families and JasperPrismDev keep their own acceptance gates.

Create or modify a supported asset in Blender, validate and export it, import it
into Unreal, place it in a level, and verify scale, orientation, materials, and asset
references. Include explicit previews, overwrite protection, recoverable backups,
and a structured report for every step. Validate in separate test projects and in
interactive Blender and Unreal sessions.

The primary Blender-to-Unreal transfer and return-to-Unreal path handles static
meshes using binary FBX. Unreal-to-Blender additionally supports a constrained OBJ
route, now covered by an asymmetric round-trip fixture. These are initial acceptance
cases, not a replacement for the full asset, rig, animation, material, or
cross-application objective. Unsupported source types must be reported explicitly;
they must never silently produce a partially compatible asset.

| Stage | Required behavior | Evidence required |
| --- | --- | --- |
| Identity | Explicit Blender and Unreal session IDs, source object identity, target project and asset path | Native responses before preview; ambiguous sessions fail |
| Preview | Describe source geometry, units, coordinate conversion, materials, destination, saves and placement | Structured proposed changes; no source or destination mutation |
| Source protection | Detect source changes after preview; preserve scene and exporter context | Stale-preview rejection; selection, mode and scene comparison |
| Export | Export through Blender's public API into private per-transfer staging | Native export success, manifest, file checksum and size |
| Transfer validation | Reject traversal, links, corrupt/changed files, excessive sizes and unsupported formats | Rejection tests and repeat verification immediately before import |
| Import | Use native Unreal editor APIs on the game thread; prevent unapproved overwrite | Native import diagnostics; verified asset class and package location |
| Verify | Measure imported geometry, unit conversion, orientation and material slots; inspect references | Compare native measurements with declared export metadata; asymmetric geometry fixture |
| Placement | Preview the target world and transform; place the verified asset with a native editor transaction | Native actor/mesh identity, transform and world responses |
| Recovery | Preserve recoverable backups; distinguish completed, rolled back, partial and unknown outcomes | Fault injection at export, import, save and placement boundaries |
| Report | Preserve token-free records of every stage and resulting asset paths | Report with status, diagnostics, evidence and recovery actions |
| Acceptance | Repeat on clean setup and in visible application sessions | Install logs, regression results and interactive verification record |

Existing destinations remain protected. Overwrite support requires a separate
reviewable backup/restore workflow; the initial transfer contract rejects overwrites.
No arbitrary script execution is required for the transfer workflow.

## Full completion gates

- Session handling: discover and explicitly select intended projects/scenes across
  multiple sessions; reject stale or changed identity at apply time.
- Editing: verify native outcomes for scene/assets, Blueprint compiler results,
  materials, rigs, animation and evaluated Blender output. Document unsupported
  operations rather than inferring support from neighboring tools.
- Recovery: exercise interrupted operations, stale previews, failed imports,
  overwrite protection, rollback failure and unknown outcomes. Keep records and
  recoverable material across process restarts.
- Capability reporting: connect each supported workflow to native implementation,
  operation limits and its unit, subprocess, live and interactive acceptance evidence.
- Installation: build reproducible packages for both adapters and verify clean
  installation, discovery, activation, connection and update behavior.

## Current transfer implementation

`server/core/transfer.py` defines a versioned static-mesh manifest with source and
target session identity, snapshot checksum, project/asset destination, geometry
bounds/counts, source units, coordinate-system labels and material-slot metadata.
It checks a staged artifact's filename, bounded size, binary FBX header, checksum,
file identity and link/reparse restrictions. Integrity success explicitly does not
claim valid FBX geometry, authorization, native export/import, or completed transfer.

Native Blender static-mesh export now exists in `blender-addon/majestic_forge/exporting.py`.
Authenticated native `export_preview` / `export_apply` commands use expiring single-use
previews, source fingerprints, private staging and persistent export status records.
A disposable Blender test exports and reimports an asymmetric mesh, checking selection
and active-object preservation, dimensions, material slots, stale/replay rejection and
failed-export reports. Texture and group materials, animated or modified meshes are
explicitly unsupported by this initial export stage.

Native Unreal staged static-mesh import now exists in `ForgeMeshImport.cpp`.
The server stages verified artifacts into the explicit project's private
`Saved/ForgeTransfers/<transfer_id>` directory, preserving a manifest and staging
record. Native preview/apply revalidate identity and integrity, reject existing
destinations and reused transfer records, hold a Windows read lease during import,
and report saved geometry, material slots and bounded native warnings/errors.

An isolated UE 5.6 Editor build passed. A separate unattended Unreal process imported
a factory Blender asymmetric mesh and verified signed vertices, units, bounds,
counts, material slots, package save, wrong-session rejection, stale artifact/replay
rejection and invalid-FBX rollback. For the current -Y-forward/Z-up FBX settings and
forced Unreal X-front conversion, Blender `(x, y, z)` maps to Unreal
`(-y, -x, z) * meters_per_source_unit * 100` centimeters in this acceptance case.
General object transforms and further unit settings require additional acceptance.

Native actor placement can now bind an exact loaded `/Game/` static mesh through
the existing `unreal_preview_actors` / `unreal_apply_actors` tools. Preview fingerprints
the mesh instance, geometry/topology and material references as well as the target
world/level and existing actors. Inspection reports the assigned mesh, material
references and world bounds. A real MCP stdio acceptance run placed the imported
fixture with nontrivial location, rotation and scale and verified these native
results. The level remained unsaved; the test's own process was then closed.

Constant-PBR material transfer now supports opaque scene-linear base color,
roughness, metallic and sidedness from an unlinked Principled shader. The exporter
classifies unsupported graphs, transparency, advanced BSDF settings and animation.
Material-transfer staging rejects unsupported or missing profiles before target
writes. Native Unreal import creates new generated material packages, verifies
their constant graphs, binds them to matching mesh slots and reports individual
save results. The acceptance fixture verified native constants and the placed
actor's material references. Shader compilation and visual equivalence remain
explicitly unverified; this does not establish arbitrary Blender shader conversion.

Advanced material/texture transfer, cross-process recovery coordination, level
saving, rendered-material verification and interactive transfer acceptance remain
outstanding. Native import evidence does not establish final pipeline completion.

`server/core/workflow_journal.py` now provides private durable receipts with ordered
export/staging/import/verification/placement stages, revision checks, atomic writes
and operating-system file locks. Started native steps become uncertain on restart;
the store never replays application operations. `forge_inspect_transfer` exposes
read-only receipt inspection and explicitly distinguishes recorded state from
currently verified application state. This is the coordinator's persistence
foundation for the connected transfer coordinator.

`server/core/workflows.py` now connects native export, protected staging, import,
geometry/material verification and actor placement through `forge_preview_transfer`
and `forge_apply_transfer`. Explicit session IDs and adapter contract versions are
required. Each native side effect receives a started receipt before execution;
uncertain transport outcomes stop the workflow without automatic replay. Source
and target identity are checked against the preview, existing destinations are
rejected, and the source export remains available for recovery.

`scripts/verify_transfer_workflow_mcp.py` passed against separate factory Blender
5.2 and unattended Unreal 5.6 processes using real MCP stdio. The asymmetric mesh
workflow completed all five stages, saved its mesh and material assets, verified
native geometry and material graphs, placed an actor with nontrivial transform,
preserved source scene facts and rejected replay. Evidence is retained under the
disposable host's `Saved/WorkflowAcceptance-*` directories. This is headless native
acceptance; the level remained unsaved and shader/rendered appearance and visible
interactive use remain unverified. The current Python regression suite passes
121 tests, including coordinator boundary tests; Ruff passes for server and tests.

The same native MCP acceptance also passed with `--variant transformed_metric`:
the source used an offset, nontrivial rotation, nonuniform object scale and a
metric scene scale of 0.01 meters per unit. Complete imported signed vertex
positions and bounds matched the declared world-space conversion. This verifies
that additional fixture; it does not establish every transform or unit setting.

The acceptance runner now audits saved mesh/material package files and records
their sizes/checksums, verifies the retained source FBX checksum, checks all five
started/completed receipt pairs and compares the durable receipt with the MCP
reply. `--audit-existing <acceptance-directory>` repeats these checks without
starting application processes and reads the receipt through a fresh MCP server.
This audit passed after the transformed fixture's native processes closed. The
fresh server returned the same completed receipt with runtime verification and
automatic native replay explicitly disabled. This establishes receipt persistence
and retained files; reopening assets and native recovery reconciliation remain
separate acceptance requirements.

`scripts/verify_unreal_saved_transfer.py` now verifies native asset reopening in
a separate Unreal Python commandlet restricted to the generated disposable host.
It passed for the transformed metric transfer: saved mesh/material assets loaded
as their expected native classes, mesh material references matched the receipt,
and opaque/sidedness settings survived saving. Package checksums were unchanged
after the read-only probe. Evidence is retained under the acceptance directory's
`Reopen-*` folder. This does not reopen a saved level, verify rendered appearance
or complete native recovery reconciliation.

Native connected-workflow failure acceptance now rejects an existing destination
without changing saved package checksums or target actors. It also previews a new
transfer, edits the source transform through Blender MCP, and confirms stale-source
rejection before staging/import with a failed durable receipt and no completed
stages. This test exposed delayed Blender dependency-graph evaluation after scripted
transforms; export snapshots now update the view layer before fingerprinting the
world matrix. The corrected transformed-metric native acceptance passed. This
does not establish interrupted-import or save-failure recovery.

Native save-failure acceptance now blocks a unique destination directory with an
exclusive file in the disposable host. The first run exposed Unreal's fatal
default save-error handling: the application disconnected and the coordinator
correctly retained an unknown outcome. Mesh and material saves now use
`SAVE_NoError`, allowing the importer to report package-write failures instead of
terminating the editor. The isolated Editor target rebuilt successfully and the
full native fixture passed: save failure returned `partial`, no assets were saved,
placement was not attempted, and existing packages/actors remained unchanged.
The fixture removes its own blocker and retains the source export and receipts.
This verifies failure reporting and containment; recovery of the partial in-memory
assets is not yet implemented or proven.

`unreal_inspect_static_mesh` now provides read-only native inspection of loaded
meshes: bounded geometry, constant material graphs, package dirty flags and disk
package presence. The updated isolated Editor build passed, as did all 121 Python
tests and Ruff. A real MCP native save-failure fixture then verified that the
partial mesh remained loaded with 8 vertices/12 triangles, its package was dirty,
and neither it nor its generated material had a disk package. The server exposes
29 tools. This supplies current-state evidence for recovery decisions; it does
not automatically save, discard, reimport or reconcile a retained operation.

`forge_reconcile_transfer` now connects a retained operation to explicit native
session inspection. It rejects a different project before asset inspection and
compares available loaded geometry/materials with recorded export metadata. A
missing loaded mesh produces limited registry evidence without asserting disk
absence. It never changes receipts or automatically replays operations. All 124
Python tests passed, including three reconciliation boundary tests. The native
partial-import fixture passed through this MCP tool with geometry/materials
verified and recovery explicitly incomplete. The server now exposes 30 tools.

One native acceptance attempt encountered receipt-storage failure after export;
the coordinator retained the started receipt, returned unknown outcome and did
not proceed to import. The retained source export was readable. A subsequent new
disposable fixture passed. Receipt failures now include a bounded storage error
code for diagnosis; the intermittent storage failure's cause remains unresolved.

The successful native transfer acceptance now modifies source vertex positions
through actual `blender_preview_scene` / `blender_apply_scene` MCP calls before
transfer. It verifies Blender reports preservation of the original mesh datablock,
then compares the edited geometry's complete signed vertex positions after Unreal
import. The transformed-metric run passed with this source-edit step plus asset
saving, placement, overwrite/stale rejection, partial save reporting and read-only
reconciliation. Source scene preservation is measured after the authorized edit;
the transfer does not undo that edit or save the Blender scene.

The same successful MCP source-edit recipe now changes Principled base color to
`[0.12, 0.34, 0.56, 1]`, roughness to `0.27` and metallic to `0.63`. Native transfer,
save-failure and reconciliation acceptance passed with those non-default values.
The saved-asset commandlet verifier now inspects the connected native Constant3Vector
and Constant expressions after a fresh process loads the saved material. Their
values matched the import receipt and package checksums remained unchanged. This
proves saved constant graph values for this profile, not rendered equivalence or
general shader conversion. Ruff and scoped whitespace checks passed for the
updated verifiers.

The current source-only Blender ZIP passed expanded clean-profile installation
acceptance on Blender 5.2.2. The verifier confirmed it imported the installed
module from the isolated profile, registered the ForgeMCP panel, reported transfer
contract version 1, rejected an incorrect token and caller-selected output path,
performed native FBX export with matching size/checksum and complete small-mesh
world-position metadata, preserved selection/active-object context, rejected
replay and a scripted-transform stale preview, stopped/restarted the bridge and
disabled cleanly. No preferences were saved and the user's profile/session was
untouched. This is headless installed-package acceptance, not visual panel QA.

The current Unreal development ZIP is
`Artifacts/ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip` (23 files,
SHA256 `986be859518c51b03247932676e72687cd2a8902027fdda8edc5a529f5189948`).
Packaging checks current source/configuration against the isolated build, requires
both editor/runtime modules, checks binary timestamps and the installed editor's
BuildId, verifies ZIP contents and preserves replaced packages. Repeated packaging
produced identical bytes. The final ZIP passed loading in a newly generated
Blueprint-only project. Native health/project responses matched that project;
process-module inspection confirmed its extracted DLL was loaded. The test closed
only its own process and retained evidence in `Saved/UnrealPackageAcceptance-*`.
This is Win64 development-package acceptance on the existing Unreal 5.6.1 machine,
not a clean operating-system install or interactive release acceptance.

Visible panel acceptance remains unverified: the computer-use skill is installed,
but its required `node_repl` runtime is not exposed in this agent session. No UI
input or screenshot-based verification was performed.

`Install-ForgeUnreal.ps1` now defaults to the current development ZIP instead of an
older extracted artifact directory. Archive mode validates bounded size/count,
manifest file scope, checksums, path traversal, Windows case aliases, encrypted
entries and links before extraction writes. Extraction requires a new staging
directory and refuses existing destinations. Running GUI and commandlet editors
for the target project are checked before staging; existing plugin/project backups
remain preserved. A fresh Blueprint-only project's native package acceptance now
invokes the actual installer, confirms it enabled the plugin and then verifies the
loaded DLL came from that installed project. That acceptance passed. All 131
Python tests and Ruff passed, including seven archive-boundary tests. Checksums
establish archive integrity, not a publisher signature or trust in third-party code.

Coordinator receipt-failure regression now covers completion writes after export,
staging, import and placement with both permission errors and journal-busy errors.
Each case retains a started/uncertain receipt, reports only a bounded storage code,
stops subsequent native operations, clears in-process active state and rejects
preview replay. Additional tests confirm a failed started-receipt write prevents
the corresponding export/import/placement request. These are protocol-fixture
fault-injection tests with real receipt storage; they do not recreate or diagnose
the earlier intermittent native storage failure.

Blender rig inspection now accepts optional `include_evaluated`. It reports native
dependency-graph bone matrices in armature/world space and world-space head/tail
positions at the current scene frame, bounded to 256 bones with finite-value
checks. It does not change the frame. Default queries omit the new flag so older
running adapters retain their existing inspection behavior.

Native recipe acceptance verified evaluated poses at two authored keyframe
endpoints, different world matrices across those frames and expected world-space
head positions under rig translation/nonuniform scale. Exact boolean validation
also passed. Real MCP inspection and hierarchy/skin-weight/rig-creation acceptance
passed in a separate factory session, with evidence under
`Saved/RigPoseAcceptance-f331ff36d9314516935ec94774dda067`.
All 142 Python tests and Ruff passed before the final compatibility adjustment;
the final focused MCP regression also passed. The current Blender ZIP was rebuilt
and passed isolated installation/export checks (SHA256
`33bfc95548d84bbbc9dfc675818e328e35e03b9a44cd0fd82c9695faccd588af`).
This establishes bounded current-frame evaluated inspection and the tested native
animation fixture; visible playback, broader rig workflows and animation transfer
remain separate completion requirements.

Recovery-journal reads now replay the bounded event sequence to derive state,
active stage and completed stages, then compare those values with the receipt's
reported summary. Completion without events, completion without a start, skipped
stages, duplicate starts and events after terminal outcomes are rejected. All 147
Python tests and Ruff passed. A fresh MCP server also read the retained native
material-transfer receipt successfully through the persistence audit, confirming
valid existing records remain compatible. This enforces receipt consistency;
it does not authenticate event claims or replace native reconciliation.

Retained-export recovery is now connected through `forge_preview_asset_recovery`
and `forge_apply_asset_recovery` (32 MCP tools total). Eligible incomplete transfers
with completed export/staging evidence can restore to an absent new destination
in the same project. Preview checks artifact integrity and binds target session,
project/level and original receipt revision. Apply consumes the preview once and
creates a separate recovery receipt with staging/import/verification stages.
It performs no new Blender export, preserves partial assets and original receipts,
and verifies/saves the new mesh/material assets without actor placement or level
saving. Failure or uncertainty stops without replay.

Native transformed-metric acceptance passed with Blender closed before recovery.
The save-failure fixture's retained FBX restored into a new destination; native
geometry/material reconciliation passed, original receipt and existing actors/
packages remained unchanged, and recovery replay was rejected. Evidence is in
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-6ee6758fa98c40faa6eecc0928219d36`.
This verifies the new-destination restoration path; saving/discarding the original
partial in-memory assets and automatic placement recovery remain unfinished.

All 154 Python tests and Ruff passed, including recovery cases for absent Blender,
unchanged original receipts, replay/confirmation, stale context, wrong project,
active originals and changed retained artifacts. The saved-asset verifier's new
`--recovery` mode also passed in a fresh Unreal commandlet: restored mesh/materials
loaded, references and constant graph values matched, and package checksums remained
unchanged. Original partial objects and actor/level recovery are still separate work.

Blender add-on 0.2.1 fixes an installation/update failure reported in Blender 5.2:
the new exporter could encounter an older cached `materials` module without
`transfer_surface` even though the replacement file on disk contained it. Package
initialization now reloads cached helpers in dependency order before importing
their symbols. The isolated installed-ZIP test reproduces the missing cached
function, re-enables the add-on and verifies panel registration, bridge startup
and export preview. Clean installation, native authenticated export, stale/replay
rejection and disable cleanup passed against Blender 5.2.2. The corrected ZIP is
`Artifacts/ForgeMCP-Blender-Addon-0.2.1.zip`; the existing user session was untouched.

Recovery can now use the retained export of an eligible incomplete recovery, with
completed staging required and the retained transfer ID bound to that receipt's
operation ID. A fresh preview and a different absent destination are required;
neither earlier receipt is modified and no native operation is replayed.
Protocol regression verifies recovery after a server restart and rejects a changed
artifact belonging to the interrupted recovery. All 156 Python tests passed.

Native transformed-metric MCP acceptance now deliberately blocks saves during a
first recovery, verifies its partial result and restores from that recovery's
retained FBX into a second new destination with Blender closed. The original
transfer and failed-recovery receipts, existing package checksums and actors remain
unchanged. The restored mesh/material reopened in a fresh Unreal commandlet with
matching references and constant graphs and unchanged package checksums. A fresh
MCP server separately inspected all three receipts and verified their staged-FBX
checksums and recorded lineage after the native processes closed. Evidence is in
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-fc3c0ee8aa9f4129aa72129f50b5a0db`.
Ruff passed. This validates native save-failure recovery chaining and persistent
evidence; it does not establish recovery from every interruption, visible UI use,
shader appearance or saved-level/actor reopening. Those gates remain open.

`scripts/verify_unreal_level_persistence.py` now establishes the native API
foundation for reviewed level saving. In the generated disposable host, a first
Unreal commandlet creates a new blank map, loads the recovered mesh/material and
places an actor with nontrivial transform, then saves to a unique absent map path.
A second commandlet loads that saved map and verifies actor identity by unique
label, world package identity, transform and mesh/material references. The saved
map checksum remains unchanged during reopening; existing asset checksums remain
unchanged through both stages. Evidence is under the latest workflow acceptance's
`LevelPersistence-c712b994cd164fda9c5efe84a6e5d830` directory. Ruff passed.
This fixture calls native Unreal Python APIs directly and creates its own actor;
it does not prove persistence of the original MCP-placed actor or implement a
reviewed MCP level-save operation. The next implementation must bind a save preview
to the selected editor world and its state, protect existing map destinations,
report failed/uncertain saves and verify the MCP-placed actor after reopening.
Streaming/world-partition behavior, interactive acceptance and rendered appearance
also remain open. The complete development goal remains unfinished.

Reviewed native level saving is now connected through
`unreal_preview_level_save` / `unreal_apply_level_save` (34 MCP tools). Preview
binds bounded nontransient world-package state and map identity; apply requires
matching confirmation, a fresh destination folder and unchanged state. Win64
destination checks reject reserved names/reparse ancestors. Existing map folders
are protected. Saving may change current world package identity and does not save
referenced mesh/material assets. Native intent/result records are retained under
`Saved/ForgeLevelSaves`; partial or uncertain results never claim rollback/reopen.

The isolated Unreal Editor build passed. Real transformed-metric MCP acceptance
saved the original MCP-placed actor to a new map. Actor edits after preview caused
stale rejection before destination creation; consumed-preview replay and an
existing destination were rejected. The saved map reopened in a fresh Unreal
commandlet: original actor object name/label, transform and mesh/material references
matched. Read-only reopening preserved map and asset checksums. Evidence is in
`WorkflowAcceptance-b4de8b0487824770a1e6d0f5c546517d`, with reopening evidence under
`LevelPersistence-0b9fc8ea9b61440aa0ca744ce33480df`. All 156 Python tests and Ruff
passed. The Unreal development ZIP was rebuilt from matching source/binaries
(SHA256 `cdf4638f64192b880c6838874252152beb2932ea58d0751ea2d7658b7fdfced6`).
The actual archive installer and extracted DLL load passed in a fresh Blueprint-only
project under `Saved/UnrealPackageAcceptance-e10db7abf38a487a851c4d8ef208b739`.
Its retained native health response includes both level-save commands. Existing
user-session binaries were not replaced; this is isolated package acceptance.
Native records still need the server store's crash-durability/reconciliation
guarantees, map-save failure acceptance and reviewed handling of unsaved referenced
assets. World-partition/streaming support, visible interactive use and rendered
appearance remain unfinished requirements of the full goal.

`server/core/levels.py` now wraps level saves with the same private, fsynced,
OS-locked receipt store used for transfers. Preview binds explicit session token
identity and target project/world. Apply requires matching confirmation, consumes
the preview once, writes a `level_save` started event before the native request
and records completed/partial/unknown results separately from transport success.
An intent-write failure prevents native saving; a completion-write failure retains
uncertainty. Restart inspection never replays. Native uppercase GUIDs are retained
for bridge calls while public receipt IDs are normalized to lowercase; the native
operation ID is also retained in the plan for uncertain-result correlation.

All 164 Python tests passed. New protocol fault tests cover timeout/disconnection,
malformed native responses, started/completion receipt-write failures, wrong
session/confirmation, changed session binding and native GUID casing. Final focused
level/receipt regression passed after the metadata addition; Ruff passed. Native
transformed-metric MCP acceptance saved and inspected the level receipt, rejected
stale/replayed saves, and passed the complete transfer/recovery sequence. A fresh
MCP server read the unchanged completed level receipt after the application
processes closed. The map reopened in a fresh Unreal commandlet with the original
actor and unchanged map/asset checksums. Evidence is in
`WorkflowAcceptance-231a7fb694c245878767acf5ad843736`, with reopening under
`LevelPersistence-61288c767ac240ab8b90f3714c35ab0d`.
The native auxiliary JSON record retains its earlier durability limits; the server
receipt supplies the stronger intent persistence. Real native save-failure/abrupt
termination acceptance, level reconciliation and unsaved referenced-asset handling
remain unfinished. This server-only change does not replace application-session
binaries or alter the existing adapter packages.

Read-only `unreal_reconcile_level_save` is now available (35 MCP tools). Successful
save receipts include bounded derived-map size/SHA256 observations. Reconciliation
requires the recorded project, rejects active operations, checks current world
identity and compares current file bytes with recorded save evidence where present.
It leaves receipts unchanged and never loads/replays/saves a map. Unknown outcomes
without checksum evidence stay unresolved even when a file is absent. Hardlinks,
reparse paths, oversized files and read-time changes are rejected. A failed map
read after native saving is reported as uncertain with a bounded diagnostic.

Native acceptance clarified SaveMap semantics: saving a copy of the loaded engine
template leaves the source world open. Preview now reports possible identity change;
apply reports the actual post-save world and whether it changed. Reconciliation
correctly observed the destination not loaded while verifying its saved checksum.
The destination subsequently reopened in a fresh Unreal commandlet with the original
MCP-placed actor and matching transforms/references and unchanged checksums. A fresh
MCP server also read the retained receipts after process shutdown. Evidence is in
`WorkflowAcceptance-0c3d3ef6051543aa9d7be147b831865a`, with reopening under
`LevelPersistence-78d5b31144b847d79a8b3dbda3f246c9`. All 169 Python tests and Ruff
passed. Regression includes altered/hardlinked maps, wrong project, active saves,
uncertain absent files and map-read permission failures.
The isolated native build passed; the corrected Unreal development ZIP was rebuilt
(SHA256 `1ee6e5c897a4d1acf5ffb520ef6d957d6dc6abf388e221b20acb7da648fcf5d4`)
and passed actual archive installation/extracted-DLL loading in a fresh project
under `Saved/UnrealPackageAcceptance-776cc67f299740d5b5012d5213acbda5`.
Native contents, dirty-state/unsaved dependencies, map-save failure/interruption
recovery and visible interactive acceptance remain separate unfinished gates.

Native level-save precondition failure acceptance now covers a destination changed
after preview and an unavailable native intent-record path. The disposable fixture
uses exclusive files at those paths, confirms native rejection before SaveMap,
failed durable receipts with no completed stages and no map file, consumed-preview
rejection, unchanged original placed-actor inspection and unchanged checked asset
package checksums. It removes only its own blocker files. The native intent failure
retains the empty map folder reserved before record preparation; this is reported
as a filesystem side effect, not rolled back or hidden.

The same native MCP run then completed a fresh reviewed save and reconciliation.
A fresh server read both failed receipts unchanged after process shutdown, with
runtime verification/replay disabled. The successful destination reopened in a
fresh Unreal commandlet with original actor/transforms/references and unchanged
map/asset checksums. Evidence is in
`WorkflowAcceptance-65013ac38a0547bdac424f491ee610b2`, with reopening under
`LevelPersistence-fe874c7534ca4c6d98170703ceb57150`. Ruff passed for the changed
verifier. No production adapter/server source or application package changed in
this step, and user sessions were untouched. These are pre-save rejection checks;
write failure inside SaveMap, abrupt termination during saving and uncertain-result
recovery remain separate unfinished native acceptance requirements.

Native level saving now protects unsaved loaded dependencies. A bounded hard-reference
graph scan reports external package names, dirty flags and disk-package presence.
Dirty/missing packages block preview without a token or receipt; apply rescans and
rejects a dependency becoming unsaved after preview. The scan is bounded to 20000
queued objects, 10000 references per object and 256 packages, with explicit limit
failure. Transient material/render references are treated as unpreserved. Other
assets are not automatically saved. Server validation requires the guard fields,
rejects inconsistent observations/older adapters and explicitly reports unverified
soft references and dependency saved contents.

The isolated Editor build passed, as did the existing native transfer/save workflow
with clean dependencies. `scripts/verify_unreal_level_dependencies.py` passed in a
separate editor: a disposable cloned material assigned to the original placed actor
blocked preview while absent on disk; separate native-fixture saving made preview
available. Dirtying it after preview blocked apply before destination creation with
a failed receipt. Restoring/saving it separately allowed a fresh reviewed map save.
Original asset files were unchanged, and the source map still matched its earlier
recorded checksum. The fixture created/saved the cloned material through native
Python setup; it does not claim those actions occurred through an MCP asset tool.
Evidence is under `LevelDependencyAcceptance-7ed5a9f51e5143928d1fec0724daf19d` in
the disposable host's Saved directory. All 171 Python tests and Ruff passed.
The Unreal development ZIP was rebuilt from matching source/binaries (SHA256
`9611933eea5b728ea43aa631e3320900ccbbd4c322569a9740aa83216932f929`)
and passed archive installation/extracted-plugin loading in a fresh project under
`Saved/UnrealPackageAcceptance-0ca812c2f33a41258a3668f521f079a8`.
Existing user sessions were untouched. Reopening this specific dependency-override
map, unloaded soft-reference coverage, native disk-write/interruption failure
acceptance, visible interactive use and the complete broader goal remain unfinished.

### 2026-10-10: live wooden-box transfer and missing-UV repair

The user requested creation of a wooden box in their connected Blender session and
MCP transfer into the connected Unreal project at world origin. Native creation,
transfer, saved mesh/material assets, and actor placement were confirmed. The
procedural Blender wood shader is outside the constant-PBR transfer profile; the
Unreal copy uses an explicitly disclosed brown rough material. Initial import
reported degenerate tangents and nearly zero binormals because the recipe mesh had
no UV layer.

Blender adapter 0.2.2 now generates separate planar face UV islands only when a mesh
has no UV layers, on a temporary export mesh/object. Existing UV layers and the
source scene are preserved. Collapsed projected triangles are rejected, and
temporary datablocks are removed on success and exporter failure. These UVs are a
basic tangent-compatible layout, not authored texture mapping or a wood bake.
Native FBX reimport verified UVs and unit-length tangents/bitangents, source
preservation, and failure cleanup. All 171 Python tests and focused Ruff passed.
The 0.2.2 ZIP passed isolated installation, activation, cached-module update,
authentication, export, stale-preview and replay checks.

Using a separate background Blender export worker with the updated adapter and
the retained, unchanged box geometry, a real MCP stdio client transferred the
corrected copy to `/Game/ForgeMCP/WoodenBoxUV/SM_WoodenBoxUV` in the user's live
Unreal session. Import diagnostics were empty; geometry, constant material, saved
assets, and actor position `(0,0,0)` passed verification. The earlier actor was
hidden through a reviewed MCP visibility operation; its actor and assets remain.
Evidence: `Saved/wooden_box_uv_repair.json`. The user's Blender session remains on
0.2.1 and was neither reloaded nor modified by this repair. Its installed adapter
still needs the 0.2.2 update. The Unreal level is unsaved, and visual shader
equivalence and rendered shading acceptance remain unverified.

### 2026-10-10: Blender Export to Unreal panel

Blender adapter 0.2.3 adds a dedicated **Export to Unreal** panel in the ForgeMCP
sidebar. The active static mesh, new asset path, save option, target session and
placement location are configurable; placement defaults to Unreal world origin.
The export button starts an external local client that uses the official MCP SDK
and existing transfer tools. Preview and apply share one MCP session. The user
reviews the actual project path and destination before confirming; cancellation
never applies, ambiguous live sessions require explicit selection, and unsupported
materials remain explicit errors. Blender main-thread timers keep its bridge
responsive while a bounded reader thread handles only subprocess output. Active
apply cannot be cancelled or interrupted by disabling the add-on or its Stop
Bridge button. Uncertain outcomes expose a receipt ID and are not replayed.

The add-on requires the configured ForgeMCP development folder and its external
Python environment. The ZIP contains adapter source, not the MCP runtime.
`FORGE_UNREAL_SESSION_DIR` optionally selects the Unreal registration directory
for isolated deployments; the default remains the project's Saved/MajesticForge.
No application or global configuration was changed in this work.

All 179 Python tests and Ruff passed. The current ZIP passed isolated installation,
panel/operator registration, bridge lifecycle, cached-module update and native
export checks. `scripts/verify_blender_transfer_panel.py` exercised actual Blender
operators against the disposable compiled Unreal host: preview, cancellation
without a receipt, confirmation, all five transfer stages, source preservation,
and independently inspected actor placement at `(0,0,0)`. Evidence is under
`PanelAcceptance-b1beef4c4bd4451c858261f90b8a0543` in that host's Saved directory.
These are native automated checks, not visual button-click or rendered acceptance.
No C++ source changed, so this used the existing compiled host without rebuilding.
The user's open Blender scene/add-on was not installed, reloaded or changed.
Install `Artifacts/ForgeMCP-Blender-Addon-0.2.3.zip` after saving the current scene
to make the new panel available in that session.

### 2026-10-10: evaluated skin geometry inspection

Blender adapter 0.2.4 extends `blender_inspect_rig(include_evaluated=True)` to report
evaluated related-mesh geometry at the current frame, including the modifier stack.
Each mesh reports vertex/face counts, full world-space bounds, up to 256 sampled
world-space vertices and an explicit truncation flag. Evaluated queries require
meshes in the active view layer and are limited to 256 bones, 32 related meshes and
100000 total evaluated vertices. Output indices are not asserted to match source
indices, since modifiers can change topology. Temporary evaluated meshes are
released on success and failure, and inspection does not change the frame.

Native weighted-mesh acceptance verified actual skin movement from a bone-local
translation and from recipe-authored keyframes at frames 1 and 20. Original mesh
vertices and datablock counts were preserved. Non-finite evaluated geometry was
rejected without retaining temporary mesh data. A 300-vertex fixture verified
sampling stops at 256 while bounds include all vertices. Real MCP inspection of
the new fields passed in the disposable Blender fixture, with retained evidence
at `Saved/RigEvaluation-abf3f58178d94bcfbf0dac2d85be6ce6/mcp-report.json`.

All 179 Python tests, focused Ruff and clean-profile installation/native export
checks passed for `Artifacts/ForgeMCP-Blender-Addon-0.2.4.zip`. Existing user
application sessions were untouched. Mesh binding and weight authoring are still
not exposed as complete reviewed workflows, and rig/animation transfer to Unreal,
visible playback, rendered acceptance and the full platform goal remain open.

### 2026-10-10: reviewed skin-copy binding and explicit weights

Adapter 0.2.5 adds a typed `bind_mesh` scene recipe. An existing unbound mesh and
armature produce a new independent skinned mesh copy with an Armature modifier
and explicit normalized vertex-group weights. Native assignments are verified;
apply reports the source, target rig, assignment count, preservation and weight
verification. The source remains unbound and unchanged. Every vertex needs full
coverage with at most four deform-bone influences; existing output names, invalid
weights/bones, unsupported source state and singular transforms are rejected.
Current bounds are 128 vertices/faces, 64 bones, 512 assignments and the existing
16 KiB bridge request limit. This is an initial bounded binding workflow, not
completion of general character rigging or existing-skin editing.

`scripts/verify_blender_skinning.py` passed native mixed-weight assignment,
recipe-authored animation with evaluated skin movement, original geometry and
selection preservation, stale previews after source/rig changes, replay/name
protection, invalid weights/bones and rollback after real binding followed by an
injected failure. Real MCP scene preview/apply and rig inspection confirmed a
new eight-vertex skinned copy and its weights in the disposable rig session;
evidence is at `Saved/RigEvaluation-0c5de19cccda49cfbf2aca7bac608f71/mcp-report.json`.
The Python suite passed 188 tests. Ruff and clean ZIP install/export checks passed.
The current package is `Artifacts/ForgeMCP-Blender-Addon-0.2.5.zip`.
User application sessions were not modified. Automatic weighting, weight edits on
existing skins, controls/IK, skeletal/animation transfer and interactive acceptance
remain outstanding within the full goal.

### 2026-10-10: reviewed existing-skin weight revisions

Adapter 0.2.6 adds `reweight_mesh`, a reviewed new-version workflow for an existing
skin. It replaces explicit bone weights on an independent mesh copy, preserving
the original weights, parenting/world transforms and volume-preservation setting.
The source must use exactly one enabled, unmasked Armature modifier with vertex
groups on the same rig; envelope/multi-modifier modes and non-bone groups are
unsupported. The earlier 128-vertex/face, 64-bone and 512-assignment limits and
16 KiB request limit still apply. Preview fingerprints now include original
weights and group/parent facts. Rig inspection exposes bounded per-vertex weight
samples so clients can review input weights before proposing revisions.

Native tests passed source-weight preservation, stale preview after weight edits,
distinct deformation under revised weights, parented meshes under translated and
nonuniformly scaled rigs, preserve-volume retention, invalid-mode rejection and
rollback after actual reweighting followed by an injected failure. Real MCP
preview/apply/inspection confirmed the new copy's Child weights while the original
kept its Root weights, including full per-vertex samples. Evidence is at
`Saved/RigEvaluation-f461241eac8842bcbfcd21e3b4f6d333/mcp-report.json`.
The Python suite passed 190 tests; focused Ruff and package checks passed.
The current installer is `Artifacts/ForgeMCP-Blender-Addon-0.2.6.zip`.
No user application session was changed. General in-place weight editing,
automatic weighting, IK/control rigs, skeletal/animation transfer and visual
interactive acceptance remain open within the full objective.

### 2026-10-10: native automatic skin weighting

Adapter 0.2.7 adds reviewed `auto_bind_mesh` using the explicitly selected
`blender_heat_top4` method: native Blender bone-heat weights, strongest-four
influence limiting, normalization and native assignment verification. The solver
runs only on apply, on an independent mesh/object copy. Preview does not claim
weights have already been computed. The result explicitly requires deformation
review. This method supports 10000 vertices, 20000 faces and 64 bones without
transmitting an explicit per-vertex weight list. Source/rig context, source
geometry/attributes and bone rest/pose/envelope facts are fingerprinted.

`scripts/verify_blender_auto_skinning.py` passed native weighting of a UV sphere
larger than the 128-vertex explicit profile, normalized coverage, evaluated bone
deformation, source and selection preservation, and rest-world geometry under
translated/nonuniformly scaled source and rig transforms. Injected cancellation
and an incomplete solver result after real native heat execution returned
`automatic_weights_failed` and removed new datablocks. Existing explicit binding
and reweighting native regressions also passed. Real MCP preview/apply/inspection
verified the automatic skin's normalized weights; evidence is under
`Saved/RigEvaluation-2c18a74c50e34ef7b9ce972819f075f7/mcp-report.json`.
All 191 Python tests, focused Ruff and clean package install/export checks passed.
The current installer is `Artifacts/ForgeMCP-Blender-Addon-0.2.7.zip`.
Existing user sessions were untouched. Production-quality deformation review,
larger/more complex character acceptance, control rigs/IK, skeletal/animation
transfer and full interactive acceptance remain unfinished.

### 2026-10-10: partial skin corrections and exact paged inspection

Blender adapter 0.2.8 adds `patch_skin_weights`: reviewed corrections on an
independent copy of an existing skin, preserving the original and all untouched
weights. It supports meshes up to 10000 vertices/20000 faces, 64 bones, and at most
128 edited vertices/512 explicit assignments per recipe. Edited vertices must have
normalized positive weights with at most four influences. The existing skin must
use the supported single-Armature-modifier profile; untouched weights must also
satisfy normalized deform-bone coverage. Source weight changes invalidate previews.

The read-only MCP tool `blender_inspect_skin` returns exact source vertex weights
in pages of up to 128 vertices/512 assignments, with the next source index. It does
not substitute evaluated geometry indices for source indices.

Native Blender 5.2.2 acceptance passed a vertex-300 correction on an automatically
weighted sphere, exact preservation of untouched/original weights, paged inspection,
invalid range rejection, stale source rejection and rollback after a real correction
followed by an injected failure. All 192 Python tests and focused Ruff passed.
The 0.2.8 ZIP passed clean-profile installation, enable/disable, cached-module update,
authenticated export and stale/replay checks. User sessions were untouched; these
are native background checks, not visible UI or production character acceptance.
Package: `Artifacts/ForgeMCP-Blender-Addon-0.2.8.zip`.
SHA256: `cd1b5af25404f0504602880e0ca09971bd081060cda19ee1205504e04ee894d2`.
Control rigs/IK, skeletal/animation transfer and full interactive acceptance remain
open within the full objective.

The 0.2.8 real MCP acceptance run also previewed/applied `patch_skin_weights`,
inspected the corrected copy, compared every untouched vertex and independently
confirmed the source page remained unchanged. This complements the larger native
sphere test; the MCP fixture itself uses an eight-vertex mesh. Token-free evidence:
`Saved/RigEvaluation-7c2f0409eddf4ac0a9df1cb257dc4314/mcp-report.json`.

A subsequent full MCP run used a 482-vertex UV sphere: reviewed native automatic
binding, exact inspection at vertex 300, reviewed partial correction, independent
inspection of the corrected copy and preservation of the source page and adjacent
untouched vertex all passed. Earlier native tests separately compare all untouched
weights. The sphere fixture is created by the disposable test harness, not through
the bounded mesh-creation recipe. Evidence:
`Saved/RigEvaluation-8f2ba6e9e5c6480c801ba3fc807d3337/mcp-report.json`.
Focused Ruff passed. This does not establish production character deformation,
interactive UI acceptance or skeletal transfer to Unreal.

### 2026-10-10: bounded constraint and IK inspection

Blender adapter 0.2.9 extends `blender_inspect_rig` with object/pose constraint
metadata, target and pole-target object identities, bone subtargets, influence,
validity, mute state and owner/target spaces. IK records chain length, iterations,
pole angle, tail/stretch and location/rotation settings. Pose reports include
location/rotation/scale locks and axis-specific IK locks. This is inspection;
constraint authoring/editing and complete control-rig workflows remain open.

Reports contain at most 32 constraints per object/bone, with total count and explicit
truncation. More than 512 pose constraints is rejected. Non-finite reported numeric
settings are rejected. Native Blender tests validated an IK target and settings,
read-only preservation of frame/selection/constraint identity, truncation and the
aggregate rejection limit. Full MCP inspection confirmed the IK metadata alongside
the existing binding/weight/large-mesh acceptance sequence. Evidence:
`Saved/RigEvaluation-350dc7fe5e314edf8974fb1894c45452/mcp-report.json`.

All 192 Python tests and focused Ruff passed. Clean-profile ZIP install, lifecycle,
cached-module update and authenticated export checks passed. Current package:
`Artifacts/ForgeMCP-Blender-Addon-0.2.9.zip` (34693 bytes).
SHA256: `cb0f78e69b784cd68dd9537ad174c17279c67fa14119e444de2937d9999cacff`.
User sessions were untouched. Visible UI acceptance, active IK deformation acceptance,
reviewed control-rig editing and skeletal/animation transfer remain unfinished.

### 2026-10-10: reviewed positional IK control setup

Blender adapter 0.2.10 adds `create_empty` control objects and
`create_ik_constraint` with an explicit owner bone, unique constraint name, existing
Empty target, chain count (1..16) and iteration count (1..256). This first profile
uses positional IK, tail targeting, full influence and no stretching or rotation
targeting. Rigs are bounded to 64 bones; the affected chain must be nonzero and
unconstrained. Rig and target must be local/unparented, in the active view layer and
Object mode, without object constraints, drivers or NLA tracks. One IK setup is
reviewed per batch. Create the control and rig first, then inspect/preview IK setup.
Pole controls, constraint revisions, constrained-chain integration and general
production control rigs remain open.

Preview fingerprints include target transforms, rig rest/pose state, IK locks,
limits/stiffness, constraint summaries and Action curves. Newly linked controls
refresh the view layer before membership checks. Failed apply removes only the new
constraint, with explicit cleanup failure reporting. Native results declare settings
verification and require deformation review; unreachable targets are not promised
to converge. These operations do not save the .blend file.

Native acceptance passed Empty/rig creation, target-following evaluated bones and
skinned geometry, stale rejection after target and IK-stiffness changes, rollback
after actual native constraint creation and preservation of selection/frame.
Full MCP acceptance created a target, reviewed/applied the constraint on the
client-created rig, moved the target and verified the evaluated bone tip. Evidence:
`Saved/RigEvaluation-477b68140c3a4c26ba7b55ddfedd60ce/mcp-report.json`.
All 193 Python tests and focused Ruff passed. Clean-profile ZIP install, lifecycle,
cached-module update and authenticated export checks passed. Current package:
`Artifacts/ForgeMCP-Blender-Addon-0.2.10.zip` (36426 bytes).
SHA256: `65e871df94fc326c509364153abf06020cff0d63b5b02ada98bcb2b6edb27916`.
User sessions were untouched. No visible UI or production character acceptance,
skeletal/animation transfer or full goal completion is claimed.

### 2026-10-10: pole controls and measured IK convergence

Blender adapter 0.2.11 extends reviewed IK creation with an optional distinct Empty
`pole_target` and finite `pole_angle` in radians within +/-pi. Pole controls require
at least two chain bones and a non-collinear target/root/pole bend plane. They use
the same local-object profile as the primary target. Preview fingerprints include
pole identity, transforms and Action curves; pole movement invalidates the preview.

IK apply now reports evaluated tail/target world positions, world-unit distance,
`position_tolerance_world` (0.0001), `target_reached`, evaluated frame and a structured
`ik_target_not_reached` warning outside tolerance. Constraint creation can complete
while convergence still needs review: native tests exposed a straight-chain pole
solver that remained short of a reachable target. This outcome is reported instead
of claiming that a successfully configured constraint guarantees target reach.

Native acceptance passed pre-bent pole IK, primary/pole target movement, changed bend
plane, evaluated skin deformation, stale pole rejection, collinear-plane rejection,
rollback after real native creation, and measured nonconvergence. The no-pole profile
also retained its expected near-target native behavior. All 194 Python tests and
focused Ruff passed. Full MCP acceptance created primary/pole controls, configured
IK on the client-created pre-bent rig, moved both controls, measured the tip and
verified changed joint position. Evidence:
`Saved/RigEvaluation-036b6c8e2dc84a8d902240597d2ecd42/mcp-report.json`.

Current package: `Artifacts/ForgeMCP-Blender-Addon-0.2.11.zip` (37106 bytes).
SHA256: `36dcca108694e2b1ed3cd106cd642e98d7b96393298b5334a621a2c7abb4d96d`.
User sessions were untouched. This is native/background acceptance; production
characters, visible interactive QA, constraint revisions and skeletal/animation
transfer remain open.
The 0.2.11 ZIP passed clean-profile installation/lifecycle, cached-module update and
authenticated native export/stale/replay checks.

## GitHub publication preparation — 2026-10-10

The repository is organized as Unreal plugin (`Plugins/Forge`), Blender
add-on (`blender-addon/majestic_forge`), external server, scripts, tests and docs.
Local Unreal host/configuration/content remain on disk and are excluded from the
current tracked scope. A verified Git bundle and private local-development-file
backup are outside the repository at `G:\ForgeMCP-Backups\Publication-20261010`.
The host generator creates an independent project without personal settings or
Marketplace requirements. Original source is MIT-licensed at the user's choice;
upstream reference-catalog licensing and Python dependency metadata are retained.

The public development snapshot also includes reviewed `set_frame` timeline
navigation, explicit object-keyframe vector values, and rollback that restores
original Actions before reevaluating the saved frame/subframe. Native IK/skin
animation checks passed at frames 1/10/20, including mixed Action/frame rollback
and stale timeline rejection. Full MCP evidence is in
`Saved/RigEvaluation-50e48a7c289c407aaae779f31ca48db8/mcp-report.json`.
All 196 Python tests and focused Ruff passed. The MIT-noticed Blender 0.2.12 ZIP
passed clean installation/lifecycle, cached-module update and native authenticated
export checks. SHA256:
`b419fd7d2056c139dd6bdf8cce394257f4de534a72d7e7ae7285c85590de1cec`.
The full development objective remains unfinished; public source availability is
not production or visible interactive acceptance.

## OBJ round-trip acceptance — 2026-10-11

The optional Unreal-to-Blender OBJ route now has an asymmetric native acceptance case in addition to FBX. `scripts/verify_roundtrip_mcp.py --reverse-format obj` drove an actual MCP stdio session against a disposable UE 5.6.1 Editor and Blender 5.2.2 process. It exported a non-cubic, offset mesh with UE's native OBJ exporter, imported and welded it in Blender, returned it through the existing Blender FBX path, and compared the full vertex set, bounds, vertex count and triangle count in Unreal. The same fixture exercised a reviewed Blender transform edit and the external UI worker used by **Import from Blender**.

The first acceptance run exposed an X-axis reflection. Blender's OBJ importer had been configured with positive X forward; using `NEGATIVE_X` matched UE's emitted coordinate convention. The corrected complete round trip passed, with all signed vertex positions and bounds matching within the existing geometric tolerance. The verifier now accepts a reverse-leg format argument and asserts the format recorded in the durable import receipt. This is headless native acceptance for this tested static-mesh fixture; materials, broad unit/transform profiles, visible panel operation and real-time synchronization remain unverified or unimplemented.

Blender source version is now 0.2.16. Rebuild the source-only archive and run the isolated clean-profile ZIP verifier before distributing it. The Unreal package is unchanged. Do not install into the user's open applications as part of this acceptance.

## Read-only Unreal reflected asset-property query — 2026-10-11

Added `unreal_inspect_asset_properties` and native `asset_property_info` to close part of the audited asset-property discovery gap. It accepts one exact `/Game` or `/JasperPrism` asset path, loads that selected object on the Editor game thread, and returns a bounded page of supported scalar/enum/name/text/vector/rotator/color properties with native type and editability metadata. It reports omitted complex/container/transient fields explicitly and does not traverse object references; Unreal may load normal dependencies with the selected asset. `/Engine` paths are rejected. The older `unreal_inspect_asset` remains registry-only and does not load objects.

The C++ adapter was targeted-built and linked in the disposable UE 5.6.1 host. Actual MCP acceptance queried a saved generated `StaticMesh` and returned 28 supported properties while counting 35 omitted fields; it verified every returned item is labelled read-only and rejected an `/Engine` query. The build archive now advertises `asset_property_info`. Current acceptance is limited to this static-mesh fixture and scalar/common-struct profile; it does not establish complete property coverage or editing.

## Reviewed Unreal asset property edits — 2026-10-11

`unreal_preview_asset_property_edit` and `unreal_apply_asset_property_edit` now cover a bounded portion of the audited `set_asset_property` surface. They accept one exact `/Game` or `/JasperPrism` asset, one editable property and Unreal-native property text. Supported edits are scalar/enum/name/string and common vector/rotator/color types; object references and containers remain excluded. Preview validates against the real `FProperty`, binds object/class/property/current value and expires after five minutes. Apply is single-use, checks the package is still clean, records an Editor transaction, enables `RF_Transactional` when necessary, performs native edit notifications, verifies the result and leaves the package dirty and unsaved. It reports that an Editor transaction was recorded; actual interactive Undo behavior remains unverified. Saving remains a separate manual action.

Native MCP acceptance passed on a generated `StaticMesh`: `LightMapResolution` changed from 64 to 128 in memory and was re-read as 128. Invalid integer text, NaN, wrong confirmation, replay, a stale concurrent preview and a new preview against the dirty package were rejected. The test asset was not saved. This does not provide disk persistence, backups, batch edits or broad property-type coverage; details are in `Documentation/AssetPropertyAutomation.md`.

The final UE 5.6.1 development ZIP passed the clean Blueprint-only install/load verifier under `Saved/UnrealPackageAcceptance-b6b4db0856434da0bd72795757559411`; native health advertised both property-edit commands. Package SHA-256 is `8f0d558c461fbb792784b53f11ec4a17e3dc7b7e9abba932c09042164d4ba6a7`. All 253 Python tests passed, as did scoped Ruff. The user project and interactive Blender scene were not modified.

## Stable Unreal / Blender mesh bindings — 2026-10-11

Static-mesh transfers now carry a stable binding ID and source snapshot SHA-256
computed from transferable content rather than process-local object addresses.
Blender previews establish or reuse the ID and attach it to the object only after
the confirmed export succeeds. Unreal saves the ID and Blender revision fingerprint
with imported mesh metadata. Unreal-to-Blender reads an existing ID or derives one
from the explicit project and asset path; Blender stores it on the received object.
No scene auto-save or existing asset replacement is performed.

Actual MCP stdio round-trip fixtures verified the same ID Blender → Unreal →
Blender → Unreal over FBX and OBJ, restarted the disposable UE Editor, reloaded the
saved asset and verified the ID and content fingerprint again. Evidence:
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-c81bd65ae3254bec9f6d152e43add025/acceptance.json`
and
`Saved/RoundtripValidation-20261011/HostProject/Saved/RoundtripAcceptance-067bae889d9c45ce9a49fb04d6924b01/acceptance.json`.
UE 5.6.1 compiled/linked; clean-project Unreal plugin load passed; Blender 0.2.17
clean-profile install and native export checks passed; 253 Python tests and scoped
Ruff passed. Unreal ZIP SHA-256:
`966952417301ff7c81950d6d34a438b88e51c454aed70af8f1014c472a827021`; Blender ZIP
SHA-256: `ca305c61b53f6ca2f9cdcb9e321c3cf2cdf834de27b10d6663ca8806ffbb93a3`.

Read-only revision comparison now exposes the states `synchronized`,
`blender_changed`, `unreal_changed`, `both_changed_conflict`, `binding_mismatch`,
`unbound` and `baseline_unavailable` through `forge_compare_mesh_binding`,
`blender_inspect_mesh_binding` and `unreal_inspect_mesh_binding`. Actual MCP stdio
acceptance observed synchronized and Blender-changed states in both FBX and OBJ
round trips; coordinator tests cover the full state table. Changes to referenced
material graphs are outside the current Unreal mesh fingerprint.

Reviewed Blender-to-Unreal replacement is implemented for an existing bound
static mesh. The native MCP acceptance run verifies package backup, retained
material assignment, synchronized binding comparison and revision metadata after
Editor restart. Failure-injection/recovery verification and package sidecar cases
remain. Live synchronization must wait for a tested two-sided conflict policy,
debounce, loop suppression and an explicit enable switch.

## Native MCP acceptance for Blender UV-layer creation — 2026-10-11

The reviewed `create_uv_layer` operation is now covered through the actual MCP
stdio server, not only the add-on's direct package verifier. A disposable
UE 5.6.1/Blender 5.2.2 run created a new layer, edited all six loop coordinates
in the same reviewed recipe, and inspected the values through MCP. A fault
injected immediately after a second layer was created caused a clean rollback;
the apply result had no rollback errors and an MCP inspection confirmed that
the failed layer was absent. Evidence is retained at
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-a94a2f5d780c4f3ba4b4941b3bdb96d8/acceptance.json`.

Blender 5.2.2 clean-profile package 0.2.24 passed installation, UV layer
create/edit/read-back, lifecycle and export acceptance. All 277 Python tests
and Ruff passed. This closes UV-layer initialization for bounded static mesh
work; unwrap/seam tools and broader recovery, sidecar, material/texture,
skeletal/animation transfer and real-time synchronization remain outstanding.

## Reviewed Blender Smart UV Project — 2026-10-11

Added a typed `smart_uv_project` scene operation backed by Blender's native Smart
UV Project operator. It accepts one exact layer name, a 0-to-90-degree angle
limit and a bounded island margin; it creates the target layer when missing and
is limited to 200,000 loops. The bridge temporarily manages selection and Edit
Mode, validates the resulting coordinates, and restores the previous selection
and mode. Preview fingerprints include topology, target layer names and all UV
values on the layer. Mutations use the copied-mesh rollback transaction.

Actual native MCP stdio acceptance projected and read back six loop UVs, rejected
a competing preview after the mesh changed, injected failure after projection,
and verified exact UV restoration with zero rollback errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-e130c52eb760434dac3c4fc90c53599e/acceptance.json`.
Blender 5.2.2 clean-profile package 0.2.25 passed create/edit/project/read-back,
lifecycle and export checks. All 278 Python tests and Ruff passed. Seam tools and
packing optimization remain open, along with replacement recovery, sidecars,
material/texture and skeletal/animation transfer, and real-time synchronization.

## Reviewed Blender mesh seam inspection/editing — 2026-10-11

Added native `mesh_edge_info` and MCP tool `blender_inspect_mesh_edges` for
bounded pages of edge indices, endpoints, seam flags and sharp flags. The typed
`set_mesh_edge_seams` scene operation changes up to 512 unique edge flags in a
reviewed recipe. Preview fingerprints include the requested edge seam values;
apply copies the mesh datablock, writes and verifies the changes, and uses the
existing rollback path on failure.

The real MCP stdio run on disposable Blender 5.2.2 inspected five edges, applied
a seam, rejected a stale competing preview, injected a post-write failure and
verified the seam stayed at its original value after rollback, with zero rollback
errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-3dff767e4bf442b19f41ae0056c5cbe9/acceptance.json`.
Clean-profile Blender package 0.2.26 passed seam and UV operations plus lifecycle
and export checks. All 279 Python tests and Ruff passed. Sharp-flag editing,
seam-aware unwrap/packing, broader transfer payloads and live sync remain open.

## Reviewed Blender seam-aware UV unwrap — 2026-10-11

Added the `unwrap_uv` scene operation for Blender's native ANGLE_BASED and
CONFORMAL unwrap methods. It requires at least one seam edge, accepts a bounded
UV margin, can create the named UV layer if needed and is limited to 200,000
loops. The helper activates the requested layer, switches selection and Edit
Mode safely, verifies finite normalized coordinates and restores prior editor
selection/mode. Preview fingerprints include every target UV coordinate and the
mesh's full seam map; apply edits a copied mesh for rollback.

Actual MCP stdio acceptance marked all 12 edges on the disposable factory Cube,
unwrapped and inspected all 24 loop UVs, rejected a stale competing preview,
then injected a failure after unwrap and verified exact restoration with zero
rollback errors. Evidence:
`Saved/TransferImportValidation-f81c125453ba42a7871d9b9f8f9176fe/HostProject/Saved/WorkflowAcceptance-07ee4d942c9544b5be9ffc2989bb6ac4/acceptance.json`.
Blender 5.2.2 package 0.2.27 passed clean-profile seam/unwrap and lifecycle/export
checks. All 280 tests and Ruff passed. Automated seam placement, UV packing,
remaining transfer payloads and real-time synchronization remain outstanding.

## Reviewed Blender UV island packing — 2026-10-11

Added the typed `pack_uv_islands` recipe for Blender's native island packer. It
requires an existing named UV layer, local mesh in Object Mode, a margin from 0
to 0.5, and no more than 200,000 loops. Preview fingerprints bind topology and
the target layer's current UV values; apply uses a copied mesh, validates
normalized output and restores selection/active object. Actual MCP stdio
acceptance packed and read back all 24 UV loops, rejected stale previews, and
verified exact rollback after an injected post-pack failure. The Blender 5.2.2
clean-profile 0.2.28 ZIP passed UV, export, install and lifecycle checks. All
281 Python tests and Ruff passed. Evidence and package hash are recorded in
`Development_Status.md`. Remaining priorities include seam placement, richer
mesh/material/texture/skeletal/animation transfer, and eventual live sync.

## Reviewed Unreal actor search — 2026-10-11

Added read-only `unreal_find_actors` for bounded active-world search by
case-insensitive name/label substring, exact class path and exact actor tag, with
combined filters, pagination and optional transform output. Server/plugin version
0.2.1 passed UE 5.6.1 compile/link, clean package load, MCP stdio result verification,
and missing-filter rejection. The current Blender 0.2.29 package also passed its
clean-profile verifier; no Blender version bump was needed for this Unreal-only
change. The reference catalog now records
both actor-search registrations as partial rather than missing. Exact tag search
and optional transforms are implemented; property predicates and exact/wildcard
name patterns remain open. See `Development_Status.md` for native MCP acceptance
evidence. The connected editor still requires the updated plugin and reconnect to
expose this increment in its live tool registry.

## Reviewed Blender existing Action key editing

`blender_inspect_animation` provides bounded, paged inspection of active Action
F-curves and keys. The reviewed `set_keyframe` recipe edits one inspected curve
and key index, with bounded frame/value data, collision rejection, stale-scene
fingerprinting, a copied Action and native read-back. The Blender add-on advanced
to 0.2.30. Clean-profile ZIP and disposable MCP acceptance passed; see
`Development_Status.md` for evidence and package hash. Key deletion, interpolation
and handle editing, NLA, retargeting and animation transfer remain separate work.
The live Blender add-on is still 0.2.3 and does not expose this increment yet.

For the cross-application workflow, the roadmap's user-facing handoff labels are
**Send to Unreal** in Blender and **Send to Blender** / **Import from Blender** in
Unreal. These are staged transfer operations today. Keep real-time synchronization
as a later milestone requiring revision detection, two-sided conflict resolution,
loop suppression, recovery and an explicit enable/disable control; do not describe
the current transfer tools as live synchronization.

## Unreal Content Browser and session discovery — server 0.2.4 / plugin 0.2.3

The Unreal 0.2.3 plugin and server 0.2.4 expose bounded Content Browser selection inspection, native opening of one exact project/plugin asset, and Content Browser synchronization. These are UI-level navigation operations with no asset edit/save behavior. The plugin build, clean package load, stdio tool registration, and disposable cross-application MCP acceptance passed. A headless native run returned a valid empty selection and accepted the sync request; visible navigation could not be verified. Server 0.2.4 checks the 64 most recent regular registration files after testing exposed alphabetical truncation hiding a new Editor session behind stale registrations. A regression test covers this case. Asset opening explicitly rejects unattended hosts; the interactive editor path still needs verification after an Editor session reconnects. Keep Blender add-on version 0.2.30 unchanged until a validated Blender-specific change lands.

Live connector checkpoint: Codex currently reports ForgeMCP server 0.2.0 and zero connected sessions. Restart/reconnect ForgeMCP and relaunch the intended Unreal and Blender applications to activate and verify these source/package increments.

## Current development continuation — DataAsset editing and Blender graph completion

Unreal's DataAsset class/instance discovery and native class property-schema
inspection now cover a broader read-only slice of the audited DataAsset module.
The next Unreal increment should extend reviewed edits to existing DataAsset
instances, with stale-state checks, atomic rollback, explicit save and reopen
verification, then widen existing material graph editing. Do not treat generic
asset scalar edits as full DataAsset authoring.

For Blender, the first existing-graph edit slice now adds allowlisted nodes and
links onto unoccupied inputs; it verifies endpoint types and cycles, fingerprints
the inspected graph for stale-preview rejection, reads native results back and
removes added nodes/links on rollback. Existing-node edits now support bounded
positions, selected Math/VectorMath operations, MixRGB blend modes and supported
unlinked scalar/vector/color defaults, with stale-preview and rollback checks.
Existing-node/link removal/replacement and broader node coverage remain open.
Continue filling animation/NLA, rig controls, texture transfer and two-sided
synchronization afterward. Advance component versions only with native acceptance
and clean package verification; v1.0 remains gated on the full roadmap and
interactive activation.


Current release checkpoint: Unreal plugin 0.2.8, MCP server 0.3.1, Blender add-on
0.2.32. Guarded DataAsset creation and reviewed Blender existing-node graph edits
passed disposable native acceptance. Both packages passed fresh-project/profile
load checks; the broader Unreal host Editor target build remains unresolved. Next,
extend existing DataAsset instance editing and Blender graph node/link management,
then broaden session activation and recovery acceptance before v1.0.0.
