# ForgeMCP bridge protocol 1

The editor adapters use their own small local protocol; the external server translates
MCP calls into it. Only the Python server speaks MCP. No Codex-specific logic is built
into either application adapter.

Registration fields: `protocol_version: 1`, `session_id`, `kind` (`unreal` or `blender`),
`host: "127.0.0.1"`, integer `port`, integer `pid`, and a random session `token`.
Session registrations are runtime secrets, excluded from Git, MCP results, and logs.
An application owns its registration file and removes it on normal shutdown.
Version 0.1.2 protects Windows registration directories and files with an
owner-and-SYSTEM-only DACL before advertising a session; protection failures prevent
startup. Tokens use cryptographic randomness and rotate on bridge startup.

A connection carries one UTF-8 JSON object terminated by a newline:

```json
{"protocol_version":1,"request_id":"unique-id","token":"session-secret","command":"health","args":{}}
```

Success:

```json
{"request_id":"unique-id","ok":true,"data":{"read_only":true}}
```

Failure:

```json
{"request_id":"unique-id","ok":false,"error":{"code":"unauthorized","message":"Session authentication failed."}}
```

Malformed JSON has no recoverable correlation ID. The server rejects missing or
mismatched response IDs. Foundation commands are Unreal `health`, `project_info`,
`list_actors`, and Blender `health`, `scene_info`. Unreal actor limit is an integer
from 1 to 1000; its result includes `total_count` and `truncated`. The current editor
world is inspected, including loaded actors; unloaded World Partition content is not
enumerated. Blender reports `fps`, `fps_base`, and `effective_fps` separately.

Adapters cap requests at 16 KiB and 16 concurrent clients, with a ten-second client
lifetime. The core caps responses at 1 MiB, with a ten-second inspection exchange
timeout and sixty-second apply timeout. Outbound client lifetime resets after native
execution so a completed compilation can send its response.
JSON nesting is limited to eight containers and `args`, when supplied, must be an
object. Excessively large input closes the connection. The Python core rejects
linked/out-of-root registrations and does not reflect adapter-supplied error messages.
Sockets are nonblocking on application threads; partially received requests and
partially sent responses are buffered. There is no eval, arbitrary script execution,
unrestricted filesystem write, or asset import endpoint.

Version 0.2.0 adds Unreal `class_info`, `blueprint_info`, `blueprint_preview`, and
`blueprint_apply`, and Blender `object_info`, `scene_preview`, and `scene_apply`.
Preview arguments contain a typed `recipe`. Apply arguments contain `preview_id`
and matching `confirmation`. Previews are session-local, expire after ten minutes,
and are consumed once. Apply returns an explicit operation state (`completed`,
`rolled_back`, or `partial`); `ok: true` means a valid adapter response and must not
be substituted for checking that state. Blueprint save and placement are explicit
recipe flags. Blender recipes do not save the file. See [Engineering.md](Engineering.md).

The development registry also exposes Unreal `gas_info` for bounded read-only GAS
state inspection on one exact actor path in the idle editor world. The Blender scene
recipe allowlist includes reviewed pose-bone keyframes; neither operation executes
arbitrary application scripts.

Error codes include `invalid_request`, `invalid_arguments`, `unauthorized`,
`command_not_allowed`, `editor_not_ready`, `scene_not_ready`, `inspection_failed`,
`session_not_found`, `ambiguous_session`, `disconnected`, `timeout`, and
`invalid_response`. A disconnected registration does not prove its application is
currently running. Listing sessions performs an authenticated health check.
Engineering errors also include `invalid_recipe`, `confirmation_required`,
`preview_not_found`, `stale_preview`, `preview_limit`, `invalid_context`,
`asset_not_found`, `class_not_found`, and `object_not_found`. Apply timeouts report
`outcome_unknown`; inspect state before retrying.

See [Security.md](Security.md) for threat boundaries and update activation.
## Static mesh export stage

The Blender native allowlist additionally supports `export_preview` with exactly
`{"name": "SourceMesh"}` and `export_apply` with exactly `preview_id` and
`confirmation`, both equal to the reviewed export preview ID for apply. Every
request still requires the session token and protocol envelope. No caller-selected
filesystem path is accepted. Previews expire after 300 seconds and are single use.

Exports write a new binary FBX beneath the configured session directory's
`transfers/<blender-session>/<preview-id>/` directory. Preview writes no artifacts.
Source geometry, mesh attributes, transform, units and material changes invalidate
the preview. Existing staging directories are never overwritten. Export records
are written before native export and updated atomically afterward; a retained
`export_started` record requires inspection rather than blind retry.

An `exported` response establishes only the export stage. Unreal import, scene
placement and downstream material/coordinate verification require separate native
responses. Standalone `blender_preview_export` and `blender_apply_export` MCP tools
expose this stage. The connected transfer tools below orchestrate native import
and placement separately.

## Staged Unreal static mesh import

The Unreal native allowlist supports `mesh_import_preview` with exactly one
`recipe` object. Its required fields are `transfer_id` (32 lowercase hex digits),
`artifact_sha256` (64 lowercase hex digits), `artifact_bytes` (integer, 23 bytes to
64 MiB), `asset_path` (new `/Game/` package), `target_project_file` (matching absolute
project path), and `target_session_id` (matching editor PID session). Optional
`save` is a Boolean and defaults to false. Unknown fields and incorrect JSON types
are rejected. No caller-selected source file path is accepted.

The server's staging helper writes the checked artifact as
`<project>/Saved/ForgeTransfers/<transfer_id>/mesh.fbx`, alongside its manifest and
staging record. Preview verifies the file's path, header, size and checksum and
rejects existing destination assets or import recovery records. Previews expire
after 300 seconds, with at most 32 pending previews per bridge.

`mesh_import_apply` accepts exactly `preview_id` and equal `confirmation`. It
consumes the preview, repeats project/session/world/file validation, locks the
Windows artifact against writes and deletion while importing, and persists an
import record before calling the native FBX factory. Responses distinguish
`imported`, `rolled_back`, `partial` (save failed) and `outcome_unknown` (record
update failed). Inspect retained staging and destination state before retrying.
Reusing a transfer with an import record is rejected even after rollback.

Results include asset/class identity, native geometry counts/bounds, at most 256
signed vertex positions with an explicit truncation flag, material-slot names,
save status and bounded relevant native diagnostics. Without material definitions,
this stage creates no material assets. It creates no actors. Native import commands are not yet exposed as standalone
MCP tools or a completed transfer workflow; orchestration and downstream acceptance
remain separate requirements.

## Static-mesh actor placement

The existing actor recipe supports optional `mesh_path` on `spawn` operations
whose `class_path` is `/Script/Engine.StaticMeshActor`. Use the exact loaded object
path, for example `/Game/ForgeTransfer/SM_Cube.SM_Cube`; package-only paths,
unloaded assets, non-static-mesh objects and non-`/Game/` references are rejected.
Mesh assignment is not accepted on transform/visibility operations or other actor
classes. The server validates the corresponding typed recipe before dispatch.

Preview includes the intended mesh reference and transform in its changes and
fingerprints the loaded mesh geometry/topology and material references. Apply
consumes the actor preview and performs native component assignment inside the
editor transaction. Inspection returns `static_mesh`, `material_assets`,
`material_assets_truncated`, `bounds_origin` and `bounds_extent` on StaticMeshActor
results. Location and bounds use centimeters; rotation is pitch/yaw/roll in degrees.
Successful placement leaves the level unsaved. Material references describe what
is assigned in Unreal; they do not establish that Blender material assets transferred.

## Constant-PBR material transfer

Exported material slots may carry a `surface` classification. `pbr_constants`
contains three bounded scene-linear base-color components, roughness and metallic
in 0..1, and a strict Boolean `two_sided`. `unsupported` identifies shader graphs,
transparency, non-default BSDF features, animation or out-of-range values.
Missing/unsupported profiles are rejected when the server staging helper is called
with `transfer_materials=True`. Geometry-only staging remains a separate explicit
mode and does not claim material transfer.

The native import recipe optionally includes `material_definitions`, with at most
32 entries subject to the existing 16 KiB request limit. Each entry has exactly
`index`, `source_name`, `asset_path`, `color_space`, `base_color`, `roughness`,
`metallic` and `two_sided`. Indices must be ordered and contiguous; source names
must be unique. `color_space` must be `scene_linear`. Package destinations must
match `<mesh-package-folder>/M_<transfer_id>_<index>` and must not already exist.
All fields require exact JSON types, and all constants must be finite and bounded.

Preview reports the new material destinations. After FBX import, native slot names
and counts must match the definitions before any material is created. The importer
constructs opaque Default Lit constant graphs, sets sidedness, assigns them to the
mesh and saves materials before saving the mesh when `save=True`. A material save
failure leaves a `partial` result and prevents mesh save; `materials` and
`saved_assets` identify individual outcomes. Recovery records retain planned
package destinations before import starts.

Native material results report constants read from actual expressions,
`native_graph_verified`, individual `saved` status and
`shader_compile_verified: false`. Matching parameters and saved packages do not
establish shader compilation or identical appearance across renderers. Advanced
graphs, textures, transparency and animated materials require further workflows.

## Durable transfer receipts

`forge_inspect_transfer` accepts a 32-character lowercase hexadecimal operation ID
and reads its private receipt under the configured project root's
`Saved/ForgeWorkflows/<operation_id>/record.json`. It accepts no caller-selected
filesystem path. Missing, malformed, linked or oversized records return explicit
errors. Recorded completion is not a fresh application-state verification.

The receipt store orders export, staging, import, verification and optional
placement. A started receipt must precede a native side effect; completion evidence
must be persisted after the native reply. Revisions prevent stale writers and an
OS file lock excludes concurrent writers. A crashed process releases its lock;
the mere presence of `record.lock` never establishes a running operation.

After restart, an unfinished started step reports `effective_state: outcome_unknown`.
A completed step followed by an interrupted coordinator reports `interrupted`.
Every inspection includes `runtime_state_verified: false` and
`automatic_native_replay_allowed: false`. Native reconciliation/recovery remains a
separate requirement. Known credential fields, nonfinite data, excessive nesting
and records above 256 KiB are rejected. Receipt inspection performs no mutation.

### Connected transfer MCP tools

`forge_preview_transfer(request)` requires explicit source/target session IDs,
source object and a new `/Game/` asset destination. Optional fields control asset
saving, placement and its location/rotation/scale. Both adapters must report
`transfer_contract_version: 1`. Preview checks native identity, supported constant
PBR materials and destination availability without writing transfer artifacts.
It returns an operation/preview ID with a 300-second lifetime.

`forge_apply_transfer(preview_id, confirmation)` consumes the matching preview
once and connects export, staging, import, verification and optional placement.
Receipt writes precede native side effects. Native timeouts stop with an unknown
outcome; the coordinator does not automatically retry native mutations. Completed
verification compares bounds/counts and, for meshes of at most 256 vertices,
complete signed vertex positions. It verifies constant material graphs and native
actor references/transform. It does not verify shaders or rendered appearance and
does not save the level. Existing asset destinations are rejected.

### Loaded static-mesh inspection

`unreal_inspect_static_mesh(asset_path, session_id)` invokes native `mesh_info` for
an exact loaded `/Game/` mesh object. Unknown fields and mismatched object/package
names are rejected. It performs no asset loads or writes. Inspection is bounded
to 100000 vertices, 200000 triangles, 32 material slots and 256 sampled positions.
It reports geometry, available constant material graphs, package dirty flags and
disk-package presence with `runtime_state_verified: true`. This verifies current
loaded state; disk existence is explicitly weaker than saved-content verification.
A missing loaded object returns `mesh_not_loaded`, rather than reimporting it.

`forge_reconcile_transfer(operation_id, target_session_id)` reads the retained
receipt and verifies the explicitly selected Unreal project's identity before
native mesh inspection. It compares loaded geometry and constant material graphs
with completed export evidence where available. It reports recorded state and
current observations separately; receipts remain unchanged and recovery remains
incomplete. When a mesh is not loaded, registry inspection supplies limited
evidence without loading or reimporting. Actor placement and saved disk contents
require separate verification.

### Evaluated Blender rig inspection

`blender_inspect_rig` accepts optional `include_evaluated: true` in addition to
weight inspection. It reports the current frame and native evaluated bone matrices
in armature/world space, plus world head/tail positions. It never changes the
scene frame. Evaluated inspection requires the active view layer and at most 256
bones; nonfinite results are rejected. These measurements describe evaluated
application state, not proof of visible playback or rendered animation.

Adapter 0.2.4 also returns `evaluated_meshes_included` and an `evaluated_mesh`
entry for each related mesh when evaluation is requested. The entry contains
`frame`, `vertex_count`, `face_count`, `world_vertices`, `vertices_truncated`,
`world_bounds_min`, `world_bounds_max`, `coordinate_space: blender_world`,
`includes_modifier_stack: true` and `vertex_indices_match_source: false`.
Empty meshes have null bounds. Sampling is limited to 256 positions per mesh;
bounds cover every evaluated vertex. Queries allow at most 32 related meshes and
100000 total evaluated vertices, and reject related meshes outside the active
view layer. Temporary evaluated mesh data is cleared even if inspection fails.

### Retained-export asset recovery

`forge_preview_asset_recovery(operation_id, target_session_id, new_asset_path)`
accepts eligible partial/uncertain/interrupted transfers with completed export and
staging evidence. It requires the recorded Unreal project and a different, absent
destination. Retained binary FBX integrity is checked before preview and again
before apply. The expiring preview binds the session token identity, project/level,
source receipt revision and artifact metadata. No live Blender session is required.

`forge_apply_asset_recovery(preview_id, confirmation)` consumes that preview once,
creates a separate recovery receipt and stages a copy under a new transfer ID.
Native import and geometry/material verification follow, with new asset saves.
Recovery receipts use ordered `staging`, `import`, `verification` stages; they do
not claim a new Blender export. Original receipts, backups and partial assets are
preserved. Existing destinations are protected. Partial/unknown results stop
without automatic replay. This restores assets only, without placement or level
save; disk-content reopening and rendered checks remain separate acceptance.

Eligible incomplete recovery receipts can also be selected as the origin of a new
reviewed recovery. Their completed staging evidence is required; retained export
metadata must identify that recovery operation's own transfer ID. Integrity checks
use its staged artifact, rather than silently falling back to an earlier backup.
Each recovery keeps a direct `original_operation_id` link to its selected origin.
Earlier receipts and partial assets remain untouched; every attempt requires a
fresh preview and different absent destination. This does not automatically retry
or discard the earlier operation.

### Reviewed Unreal level save

`unreal_preview_level_save(asset_path, session_id)` proposes saving the current
single persistent editor world to a new `/Game/` map. The destination must be in
an absent folder so existing maps and companion files are protected. Win64 path
checks reject reparse ancestors and reserved names. Preview snapshots nontransient
properties of bounded world-package objects, binds world identity, expires after
300 seconds and reports that saving may change current world identity. Saving a
copy of an already loaded map can leave the source world open; apply reports the
actual post-save editor world and whether it changed.
PIE, streaming/world-partition levels and external packages are unsupported.

`unreal_apply_level_save(preview_id, confirmation, session_id)` consumes the preview
once, repeats state/destination checks and exclusively reserves its destination
folder before calling native `UEditorLoadingAndSavingUtils::SaveMap`. Intent and
result JSON records use temporary-file replacement under
`Saved/ForgeLevelSaves/<operation_id>/record.json`. No referenced mesh/material
assets are saved by this operation. Inspect `state` separately from transport `ok`:
`saved`, `partial` and `outcome_unknown` are explicit; failed result recording leaves
uncertainty and does not trigger a replay. Rollback and reopen are not claimed by
apply. These native records do not yet have the server receipt store's OS-lock,
fsync and reconciliation guarantees; native save failures and abrupt interruption
require further acceptance.

The MCP server now adds a private durable `level_save` receipt under
`Saved/ForgeWorkflows/<operation_id>` before requesting native save. Public receipt
IDs are lowercase; `native_operation_id` preserves the bridge's original GUID.
Preview binds the target session identity and project/world. Started/completed
events use the receipt store's OS lock, fsync and atomic replacement guarantees;
unfinished native intents are uncertain after restart. A failed started write
prevents the native request, and a failed completion write does not trigger replay.
`forge_inspect_transfer` also reads these level-save receipts without changing or
replaying them. Recorded saving does not prove current world state or disk contents.

`unreal_reconcile_level_save(operation_id, session_id)` verifies the selected
project, observes current world identity and reads only the map path derived from
the receipt's `/Game/` destination. The bounded read rejects links/reparse paths,
hardlinks, oversized files and changes during reading. Successful saves retain
map size/SHA256 evidence; reconciliation compares current bytes where that evidence
exists. Earlier receipts without checksums and uncertain saves report no checksum
comparison. File absence never resolves an unknown native operation automatically.
Reconciliation does not load/save/replay maps, change receipts, infer native map
contents from bytes, inspect unsaved world changes or claim completed recovery.

Level-save previews now scan the loaded hard-reference graph of persistent world
objects, bounded to 20000 queued objects, 10000 references per object and 256
external packages. Package dirty flags and disk-package presence are reported.
Dirty/missing packages block preview without creating a preview ID or receipt;
apply repeats the scan and rejects a dependency becoming unsaved after preview.
Referenced transient material/render assets are also considered unpreserved.
The operation never saves these dependencies automatically. Limits fail explicitly
instead of returning a truncated successful inspection. The server requires these
dependency fields and rejects older adapters without the guard.

Responses explicitly identify `dependency_scan_scope: loaded_hard_references`,
`soft_references_verified: false` and `dependency_saved_contents_verified: false`.
This guard does not establish unloaded soft-reference coverage, native saved
contents or rendered equivalence. Those remain separate completion requirements.

### Reviewed Blender skin binding

Adapter 0.2.5 supports `bind_mesh` through scene preview/apply. Required fields
are `source` (existing mesh), `armature` (existing rig), `name` (new output), and
`weights`: explicit `{vertex, bone, weight}` assignments. Every vertex must be
covered with a normalized sum (tolerance 1e-5) and at most four deform-bone
influences. Assignments must be unique, finite and positive; missing bones,
existing output names and singular transforms are rejected. Limits are 128
vertices/faces, 64 bones and 512 assignments, also subject to the 16 KiB bridge
request limit. Optional `collection` must name an existing collection.

The input must be a local unbound static mesh without parenting, modifiers,
constraints, shape keys, animation or vertex groups. Both objects must be in the
active view layer in Object mode. Mesh attributes are bounded; string attributes
are unsupported. The output has independent mesh data, native vertex groups and
an Armature modifier using those groups, with bone envelopes disabled. Native
weight assignments are verified before completion is reported. The original is
preserved; the scene remains unsaved. Preview binds source geometry/attributes
and rig rest/pose/transform facts. Failure uses the existing rollback/partial
contract. This describes the initial 0.2.5 binding profile.

Adapter 0.2.6 adds `reweight_mesh` with the same explicit normalized weight
contract and limits. The source must already have exactly one enabled Armature
modifier using vertex groups on the specified rig. Parenting may be absent or
object-parenting to that same rig. Bone envelopes, masks, multiple-modifier
skinning, non-bone groups and other modifier types are rejected. The reviewed
new copy replaces its copied bone groups/weights while preserving original skin
data, parenting/world transforms and the preserve-volume setting. Preview also
fingerprints original weights, group definitions and parent facts. Failure removes
only new datablocks. In-place changes, automatic weights and skeletal transfer
remain outside this profile.

With `include_weights`, rig inspection now includes `vertex_weight_samples`
(`vertex`, `weights: [{bone, weight}]`) for the first 128 source vertices and up
to 512 bone assignments per related mesh. `vertex_weight_samples_truncated`
explicitly identifies incomplete samples. Aggregate statistics still cover the
full bounded scan. Supported skin-copy workflows fit the full sample bounds.

Adapter 0.2.7 adds `auto_bind_mesh` with required `source`, `armature`, new `name`
and `weight_method: blender_heat_top4`; explicit weights are not accepted for this
method. The native Blender `ARMATURE_AUTO` solver runs only after apply, on a new
independent mesh copy. Its results are limited to the strongest four deform-bone
influences per vertex and normalized, then actual native assignments are verified.
Unweighted vertices, invalid solver output or operator failure yield the bounded
`automatic_weights_failed` code and batch rollback/partial status. Source objects,
selection and active object are preserved. Preview exposes the algorithm, not
already-computed weights; apply marks `requires_deformation_review: true`.

Automatic binding supports up to 10000 source vertices, 20000 faces and 64 bones,
on an unbound local static mesh with the same source/context restrictions as
explicit binding. Mesh attribute data remains bounded. Rig rest/pose, transforms,
bone envelope/radius facts and source geometry/attributes participate in preview
binding. It is a native solver starting point, not a promise of production-quality
deformation on arbitrary characters. Skeletal transfer and general control-rig
workflows remain separate requirements.

## Reviewed Blender positional IK profile (adapter 0.2.10)

Use scene preview/apply to create an Empty control (`create_empty`, with name,
optional location/rotation/scale/collection). A subsequent reviewed operation uses:

```json
{"op":"create_ik_constraint","name":"CharacterRig","ik":{"bone":"Forearm","constraint":"ForgeArmIK","target":"HandControl","chain_count":2,"iterations":128}}
```

Names in the IK spec use bounded ASCII identifiers. Chain count is explicitly
1..16; iterations are 1..256 (default 64). The native profile uses tail position,
full influence, no stretching and no rotation target. It requires an existing
local rig (at most 64 bones), an unconstrained chain and existing Empty target.
Both objects must be unparented, in Object mode and the active view layer, without
object constraints/drivers/NLA. Only one IK creation is allowed per batch. Preview
is single-use and fingerprints rig/target state. Rollback removes the newly created
constraint; existing constraints are not overwritten. Results require deformation
review. Inspect evaluated rig output to measure the actual result, including
unreachable target behavior. Pole-target setup and constraint revisions are not
implemented by this profile.

Adapter 0.2.11 extends the positional IK spec with optional `pole_target` (a distinct
existing Empty) and `pole_angle` (finite radians within +/-pi, default zero). A pole
requires at least two bones and a non-collinear bend plane. Its identity/transform
and Action are included in preview fingerprints. IK apply reports evaluated tail
and target positions, `target_distance_world`, `position_tolerance_world` (0.0001),
`target_reached`, frame and warning code `ik_target_not_reached` when outside
tolerance. Creation success verifies the constraint setup; clients must review the
measured convergence, especially for straight rest chains or unreachable targets.
