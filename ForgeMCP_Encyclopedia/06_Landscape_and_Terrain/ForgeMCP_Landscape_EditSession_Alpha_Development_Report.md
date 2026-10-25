# ForgeMCP persistent Landscape authorization — next alpha development

Date: October 23, 2026  
Source/plugin version prepared: **0.2.17-alpha.1** (descriptor Version 31)  
Disposition: **IMPLEMENTED AND TESTED — PRODUCTION ACTIVATION PENDING**

## 1. Outcome and preserved production achievement

Implemented a distinct `landscape_edit_session` authorization for multiple bounded native
sculpts after one owner approval, with a two-hour default duration, exact process/project/
world/Landscape/layer/transform binding, explicit region/action scope, expiry and revocation.
Existing one-operation adoption remains consume-once. No production grant was issued and
no production Landscape write or save occurred during development.

The original production Editor remains unreal-22604 / PID 22604, running its installed
**0.2.16-alpha.1** binary. It was not restarted, reloaded, hot-recompiled or replaced. Fresh
final native inspection confirms the saved first riverbed is unchanged:

| Production gate | Verified result |
|---|---|
| Project / level | G:/ForgeMCP/ForgeMCPDev.uproject / L_City_World_Master |
| PIE | Stopped |
| Landscape GUID | BD45FDD94EC2A29617B50794F2DE4E9D |
| Original Layer GUID | 198824024FF8A77A01535B86021D9B34 |
| Original height MD5 / range | 9f43572fbc2c06ef497da015879cdb23 / 0–0 cm |
| ForgeTerrain GUID | 2E6FC5F94C4EF704F700299B5D08C23B |
| ForgeTerrain height MD5 / range | dd428766880ec01a848b4381fba82838 / −100–0 cm |
| Both layers | Visible and unlocked, 2041 × 2041 |
| Streaming proxies / components | 16 loaded, zero unloaded, terrain/collision 64/64 |
| Dirty production Content packages | Zero; only the two pre-existing compiled-in script packages |

The file audit checked all **1,537 Content, Config and .uproject files** against the saved
first-riverbed baseline: zero changes, additions or missing files. Development source and
the plugin version descriptor intentionally changed and are excluded from that Content/
configuration audit. Existing recovery checkpoints were not modified or restored.

## 2. Authorization implementation

- Owner approval is exclusively local: `Forge.Landscape.ApproveEditSession <id>` opens a
  native identity/scope Yes/No dialog. No remote approval tool exists.
- Default lifetime 7,200 seconds; configurable 60–86,400 seconds. Pending requests expire
  after 300 seconds. Grants exist only in their approving Editor/world and expire or
  invalidate on identity/transform/layer mismatch and world teardown.
- Exact `layer_name=ForgeTerrain` and existing layer GUID are required. Layer creation,
  setup_layer, save, reload and arbitrary scripting are excluded from session actions.
- A bounded region authorizes at most 1,048,576 samples. Explicit `entire_landscape`
  scope permits up to 4,194,304 and must equal the native full extent. No silent expansion.
- Each edit and its normal halo must fit the grant. Native per-operation limits remain:
  heightmap 32,768 input samples, other edit chunks 1,048,576, at most eight rows per batch.
- Immediate local/remote revocation prevents subsequent batches. Already written rows
  are retained with recovery evidence. Failed/cancelled jobs revoke the session rather
  than silently permitting further edits over an uncertain result.
- Protected non-target layer hashes and layer order/name/visibility/lock state are
  checked. The target full height hash must equal the previous verified result between
  operations. Unexpected user edits are rejected; unsaved work is not discarded.
- Dirty packages produced by this session may remain unsaved for subsequent operations;
  unrelated dirty production packages block them. One job runs at a time.

## 3. MCP interfaces and operation planning

Five typed tools were added and discovered in the source MCP server:

1. unreal_landscape_edit_session_preflight
2. unreal_request_landscape_edit_session
3. unreal_landscape_edit_session_status
4. unreal_revoke_landscape_edit_session
5. unreal_read_landscape_height_region

The existing preview request now accepts `edit_session_id`, mutually exclusive with
`adoption_id`. The same one-use preview/apply and native job-status protocol is preserved.
Revocation is an idempotent permission-reduction operation; it is not marked read-only.
Readback returns at most 32,768 native edit-layer local-cm samples in row-major order,
plus region/layer/Landscape identity and raw-height checksum. It does not claim composed
or collision data, and does not confer write permission.

Existing native operations remain raise, lower, flatten, smooth, generate, apply_heightmap
and coastline. Hills/valleys compose bounded raise/lower falloff; riverbeds/mountain ranges
use calculated heightmaps; transitions use native strength/smoothing or interpolation
against bounded readback. These are explicit compositions, not new semantic terrain
generators or mesh simulation. The native sequence exercised heightmap operations; it
does not establish new visual/runtime acceptance for every higher-level shape.

## 4. Per-operation recovery and verification

Approval retains the immutable full world/external-package checkpoint. Before any edit
row, each operation writes and verifies its localized before.r16 plus exact metadata,
and full current in-memory snapshots of every Landscape height layer. These snapshots
preserve prior unsaved session edits, which disk backups alone would miss.

Operation root: Saved/ForgeLandscape/<operation-id>. edit_session_checkpoint.json pins
the layer recovery files and records exact request, identity, transform and extents;
edit_session_result.json records terminal state, rows and full target hash. Status
returns these recovery roots/results. Recovery file mismatch/missing data blocks writes;
failures retain evidence without automatic restoration or cleanup.

Each stage retains existing stale-before/readback checks, plus editing-session permission
and recovery checks. Completion verifies the full target height array against the predicted
full result and all protected layer hashes. Failures stop the session. Full recovery
read/write verification adds CPU/disk cost and up to 16 MiB of temporary array buffers
beyond the existing plan/stage budget, plus native texture/derived-data allocations.
No production latency/performance acceptance or full restore/reopen result is claimed.

## 5. Save boundary and compatibility limitation

**This alpha supports multiple UNSAVED edits per approval. It does not authorize saving.**
A save or external disk edit invalidates the immutable approval checkpoint for subsequent
operations; the session does not silently rebase. A new clean checkpoint and owner approval
are then required. This is a deliberate boundary of the current implementation, not a
claim of seamless editing across save/reload boundaries. Each session/global job history
is bounded at 64 operations; history is not automatically discarded.

Use a separately reviewed scoped save workflow after ending/revoking an editing session.
The existing rollback-capable save adapter was not changed or invoked. It must not be used
when automatic production restoration is prohibited. Collision and independent disk-reload
acceptance remain separate from height-array and authorization testing.

The legacy isolated-acceptance launcher remains pinned to its historical 0.2.16 manifest
contract. It was not silently broadened. Python server package versioning is separate from
the native plugin descriptor version. No new third-party dependency was added.

## 6. Test and build evidence

Evidence root: G:/ForgeMCP/Saved/LandscapeEditSession_Dev_20261023T200056Z.

| Gate | Actual outcome |
|---|---|
| Full Python regression suite | **562 passed**, pytest_acceptance.xml |
| Python lint | `ruff check server tests`: passed |
| Real stdio subprocess MCP discovery | Passed, including all five new tools and annotation checks |
| Schema/control tests | Defaults/limits, explicit whole extent, rejected setup/save/reload, caller approval injection, ID-kind separation and bounded readback |
| Native UE 5.6.1 compile and link | Passed, BuildRelease.log; separate HostProject output |
| Source-to-build-host comparison | No plugin source mismatches |
| Native Landscape automation | **5 succeeded, 0 failed**, native_report_release/index.json |
| Production preservation | 1,537 files unchanged plus fresh read-only native baseline |

Native tests:

- Forge.Landscape.Adoption.Authorization — legacy single-use and identity policy.
- Forge.Landscape.Adoption.BackupIntegrity — legacy checkpoint corruption/missing checks.
- Forge.Landscape.EditSession.Authorization — repeated operation eligibility, expiry,
  revocation and action/region/identity policy.
- Forge.Landscape.EditSession.RecoveryIntegrity — exclusive recovery manifest, verified
  fixture files, tampering rejection and retained failure evidence.
- Forge.Landscape.EditSession.IsolatedNativeSequence — actual two-layer 8 × 8 native
  non-World-Partition Landscape in a guarded disposable host. It exercises real request/preflight with a
  7,200-second explicit whole-fixture scope, verifies pending requests cannot approve
  themselves, then models an owner-accepted fixture grant. It applies two real heightmaps
  without another approval/save, verifies Original preservation and the first unsaved
  edit in the second operation's recovery snapshot, reads actual quantized height through
  the new API, rejects wrong project/Landscape/layer/region/expiry, and revokes a third
  job before its first batch. The third writes **zero rows** and retains recovery evidence.

The final fixture's two completed operations are 1A30AE6743BAB2C67DDA298256F40E97 and
A785BE3C4606993E999F75A34C65AF91. Their common fixture editing session is
40815FE04016A42CB0AD288FFF5EB3F8. The revoked third operation is
E53739DD418B04319E871DB022FE56C7. These are disposable test identities, not production
approvals. Automated tests do not click or prove the human approval dialog. All test
processes exited; only the original production Editor remains running.

Earlier evidence is retained: the first full suite caught the missing new revocation
annotation expectation; it was corrected. A native compile caught unbraced UE_LOG macro
use; it was corrected. The original backup fixture failed under redirected UserDir because
its source lay outside ProjectDir; its fixture path was corrected to project-local Saved,
preserving the production guard. Final builds/tests above supersede those intermediate
failures. A minimal-host EnhancedInput dependency warning was observed; compilation/link
succeeded and production project plugin settings were not changed.

## 7. Source changes

implementation_manifest.json records hashes of the 15 task files:

- Plugins/Forge/MajesticForge.uplugin — staged alpha version.
- Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.h/.cpp — session integration,
  full result validation, per-job logging and bounded native height readback.
- ForgeLandscapeAdoption.inl — shared identity/checkpoint primitives, distinct session
  mode, local approval/revocation and one-use compatibility.
- ForgeLandscapeEditSession.inl — session validation, operation checkpoints and controls.
- ForgeLandscapeAdoptionTests.inl — portable project-local legacy backup fixture.
- ForgeLandscapeEditSessionTests.inl — new policy/recovery/native sequence tests.
- MajesticForgeModule.cpp — native command dispatch/capability discovery.
- server/core/landscape.py and landscape_edit_session.py — typed operation/session/read schemas.
- server/core/connections.py and server/main.py — allowlist and MCP entry points.
- tests/test_landscape_edit_session.py and test_mcp_stdio.py — schema/control/discovery coverage.
- docs/landscape_edit_sessions.md — exact workflow, limits, compatibility and recovery.

The working tree already contained earlier adoption/connection work. It was preserved;
the aggregate git diff is not attributed entirely to this task. Task source backups are
under the evidence root before/. No commit, publication or distribution-license change
was performed.

## 8. New workflow and remaining activation gate

After controlled activation, rediscover the Editor and five tools. Inspect exact identity,
layer GUID/extent, clean production packages and current terrain data. Submit preflight and
request with an explicit action list, layer and region; the owner runs the returned
ApproveEditSession command and confirms the local dialog once. Verify live approved state
and checkpoint. For each instruction, read/compute, preview, check bounds, apply once, poll,
verify full results and retain recovery. Query status or revoke at any time. No additional
approval is required between valid unsaved operations within that session.

The new compiled DLL is staged under the evidence HostProject/Plugins/Forge/Binaries/Win64;
it was not copied over the running production plugin. Source MCP discovery was verified
in a fresh real stdio subprocess; this chat's already-running MCP host and production
native endpoint have not been refreshed to expose/activate the new interfaces. A later
owner-controlled native installation/Editor activation and MCP refresh must verify that
specific client/endpoint. Do not hot-swap a loaded DLL or infer live activation from source
tests. No production editing-session request was issued during development.

**IMPLEMENTED AND TESTED — PRODUCTION ACTIVATION PENDING.** Native multi-operation editing
and recovery are demonstrated in isolation. The saved production riverbed remains intact.
Production/World Partition multi-operation acceptance, approval-dialog acceptance, collision, independent saved/reloaded persistence,
and Phase 6C release acceptance are not claimed by this development stage.
