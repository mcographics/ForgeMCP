# Native Landscape editing sessions — 0.2.17-alpha.1

This alpha adds `landscape_edit_session`, a separate owner-approved, process-local
authorization for multiple native height edits. Existing one-operation adoption grants
keep their consume-once behavior. No production grant is created by installing or
discovering these tools, and no old approval is upgraded automatically.

## Tools and local commands

| MCP tool | Effect |
|---|---|
| `unreal_landscape_edit_session_preflight` | Read readiness, identity, layer and backup scope |
| `unreal_request_landscape_edit_session` | Register a pending request; cannot approve it |
| `unreal_landscape_edit_session_status` | Read expiry/revocation, active operation and recovery/result records |
| `unreal_revoke_landscape_edit_session` | Reduce permission immediately; future batches stop without restoring written rows |
| `unreal_read_landscape_height_region` | Read at most 32,768 exact edit-layer samples, row-major in local cm |
| Existing `unreal_preview_landscape` / `unreal_apply_landscape` | Review and execute one operation using `edit_session_id` |
| Existing `unreal_landscape_job_status` | Poll the native job until terminal state |

The owner approves in the local Editor console with
`Forge.Landscape.ApproveEditSession <id>` and accepts the native Yes/No dialog.
`Forge.Landscape.RevokeEditSession <id>` is also available locally. MCP never exposes
an approval command. Approving an edit session through the old ApproveAdoption command
is rejected. Status/revocation is available during PIE; sculpting remains blocked.

## Request scope

Requests contain exact `editor_pid`, `project_file`, `world_path`, `world_partition`,
`actor_path`, `landscape_guid`, `layer_name="ForgeTerrain"`, `layer_guid`, inclusive
`region`, `actions`, `region_scope`, and `lifetime_seconds`. Inspect current identity
before constructing them; never copy an old process ID or approval.

Default lifetime is **7,200 seconds (two hours)** after local approval; allowed range
is 60–86,400 seconds. Pending requests expire after 300 seconds. The session remains
only in its approving process/world and cannot survive restart or world replacement.
Changing the layer GUID or Landscape transform invalidates it. Region, actions and
duration cannot be patched or silently expanded; request a new owner-reviewed scope.

`region_scope="bounded"` permits at most 1,048,576 authorization samples.
`region_scope="entire_landscape"` is an explicit opt-in, permits at most 4,194,304
samples, and native validation requires the provided bounds to equal the actual full
Landscape extent. It does not enlarge any individual operation limit. Each operation's
one-vertex normal halo must fit the authorization. All required proxies/components
must be loaded and registered. ForgeTerrain must already exist, visible and unlocked.
There is no implicit setup_layer, layer replacement, save or reload permission.

For example, a disposable eight-by-eight fixture can request actions
`["raise", "lower", "apply_heightmap"]`, region `[0,0,7,7]`, exact inspected layer GUID,
and default lifetime. After approval, successive previews use `edit_session_id` and
smaller edit rectangles whose halo stays inside `[0,0,7,7]`. Do not send `adoption_id`
with `edit_session_id`. Existing one-operation callers continue to use `adoption_id`.

## Native sculpt capabilities and natural-language planning

| Desired terrain | Supported implementation |
|---|---|
| Raise/lower, hill/valley | Existing native radial cosine falloff with bounded height magnitude |
| Flatten/blend toward a plane | Existing flatten action and strength |
| Smooth/blend transitions | Existing neighborhood smoothing and strength, or calculated heightfield interpolation |
| Riverbed/mountain range/custom landform | Calculate height samples from the instruction and current bounded readback; submit `apply_heightmap` |
| Periodic terrain | Existing deterministic sine `generate` action |
| Coast profile | Existing bounded `coastline` action |

These are compositions of verified native heightfield operations, not separate semantic
river/mountain APIs or mesh-based terrain. The AI chooses a plan and calculations; the
adapter validates action, actor, layer, region, numbers and resources. A heightmap action
sets absolute **edit-layer** local-cm values, not deltas or composed-world elevations.
Use bounded readback to preserve existing values when blending. Convert world coordinates
through the inspected Landscape transform. Do not assume one vertex equals one meter.

Per heightmap input: at most 32,768 samples. Other edit chunks: at most 1,048,576 samples.
Native writes run on the game thread in batches of at most eight rows. Larger goals need
multiple bounded preview/apply jobs; one active job at a time. The existing job-history
and new per-session operation limits are 64. Reaching that limit requires a new controlled
host/session lifecycle; history is never silently erased to regain permission.

Session protection has additional cost beyond the existing preview/stage budget: full
layer hashing and per-operation recovery snapshots read up to 4,194,304 samples per
layer. Snapshot/write-readback arrays can temporarily add up to 16 MiB, plus native
texture-source/derived-data allocations, while layers are processed sequentially.
Disk recovery grows by two bytes per vertex per layer per operation. A small brush on
a large Landscape therefore still has full-layer verification/checkpoint cost; no
interactive latency or production performance acceptance is claimed for this alpha.

## Per-operation safety and recovery

1. Read current data; calculate a bounded plan and halo.
2. Preview using the active editing-session ID. Validate the returned request, before/after
   hashes, resource bounds and full expected target height hash.
3. Apply the one-use preview. The same approval covers later valid previews; it does not
   bypass preview freshness, actor/layer/transform/action/region checks.
4. Before any row write, retain/verify the region `before.r16` and metadata, plus complete
   **in-memory** snapshots of every Landscape height layer. These preserve previous
   unsaved session operations, which a disk-only backup cannot capture.
5. Before each batch, check grant identity, expiry/revocation, original-layer data/settings
   and the operation recovery files. Stop on mismatch; never auto-restore partial edits.
6. On completion verify the full target array against the predicted hash, all non-target
   layer height hashes, and native row readback. Log the terminal result. Failure revokes
   the session and retains the evidence. Cancellation/revocation stops later batches only.

Approval creates an immutable full world/external-package disk checkpoint. Every operation
adds `Saved/ForgeLandscape/<operation-id>/edit_session_checkpoint.json`, verified layer
`.r16` files, the localized backup and exact request/transform metadata. Terminal state is
written to `edit_session_result.json`. Status lists these recovery roots/results. Missing,
modified or unwritable recovery evidence blocks further writes; partial backup files are
retained for diagnosis. No destructive cleanup is performed by session execution.

Original layers are read for protection/checkpoints and never selected for writing. Layer
order/name/visibility/lock changes invalidate the recorded session layer state. The target's
full hash must match the last verified result between operations; an unrelated user edit
is not silently accepted. Unrelated dirty production packages also block further edits.

Recovery is an explicit review: preserve failed state, identify the last verified operation,
and use the retained package checkpoint and exact layer/extent/transform snapshots to plan
an authorized restore. Never copy packages over a loaded world. No automatic rollback or
tested full restore/reopen guarantee is provided by this alpha.

## Save boundary and compatibility

**This first implementation supports multiple unsaved edits per approval.** A save or
external disk modification invalidates the immutable approval checkpoint for future edits;
it requires a new clean checkpoint and owner approval. There is no silent rebasing after a
manual save. Save/reload automation and permission are separate, and this session does not
change the existing save adapter's recovery behavior. Do not use an adapter that conflicts
with an owner's no-automatic-restore restriction. Revoke the session before a planned final
scoped save, audit the exact package set and preserve the recovery chain.

New source/plugin version is 0.2.17-alpha.1. External server package versioning is separate
and was not reset to the plugin version. The legacy isolated-acceptance launcher remains
pinned to its historical 0.2.16 manifest contract; it is not evidence for this alpha.
The original running Editor remains on its installed 0.2.16 binary until separately
activated. Do not hot-swap its DLLs. Refresh native plugin and MCP host only through an
owner-controlled activation, then rediscover the five tools and read-only capabilities.

Source/unit/subprocess discovery, native compile/link, isolated fixture edits, local
approval-dialog behavior, production activation, visible production edits, collision,
and genuine saved/reloaded persistence are separate evidence gates. See the development
report for the tests actually completed; this document does not grant production access.
The new actual multi-edit native fixture is non-World-Partition. Exact partition identity
and existing loaded-proxy guards remain enforced, but a production-scale World Partition
editing-session sequence has not been accepted by that fixture.
