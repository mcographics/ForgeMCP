# Unreal material graph automation (UE 5.6.1)

This implementation extends ForgeMCP's existing authenticated native bridge. It
does not add editor dependencies to JasperPrism or MajesticForgeRuntime.

## Architecture

- `server/main.py` registers tools using the official MCP SDK's FastMCP.
- `server/core/materials.py` supplies strict Pydantic recipes; arbitrary code,
  unknown fields, non-finite constants, unsupported expressions and graph cycles
  are rejected.
- `server/core/connections.py` retains loopback connections, session-token
  authentication, request correlation, bounded payloads and explicit command
  allowlists. Material apply uses the existing 60-second timeout; a timeout is
  an uncertain outcome and must never be blindly retried.
- `MajesticForgeModule.cpp` dispatches authenticated requests from its game-thread
  ticker. `ForgeMaterials.cpp` independently validates native arguments, mounted
  package paths, asset identity, pin existence, occupied inputs and graph cycles.
- Existing Blueprint, actor, GAS, registry, mesh import, transfer, recovery and
  level-save operations remain registered.
- `MajesticForge` is already an Editor module. It now privately depends on
  `MaterialEditor`. Unity compilation is disabled for this module because its
  independent handler translation units contain helper names that collide in a
  unity translation unit. This is independent of adaptive-unity working sets.

## Tool contract

| MCP tool | Native command | Behavior |
| --- | --- | --- |
| `unreal_inspect_material_graph` | `material_graph_info` | Inspect the exact material, loading if needed; no edits/compile/save |
| `unreal_preview_material` | `material_preview` | Review new material creation; refuse existing destinations |
| `unreal_apply_material` | `material_apply` | Apply creation and validate shaders; remain unsaved |
| `unreal_preview_material_edits` | `material_edit_preview` | Review additive edits or an isolated compile/save action |
| `unreal_apply_material_edits` | `material_edit_apply` | Apply the exact reviewed action once |
| `unreal_preview_material_compile` | `material_edit_preview` | Review compilation only |
| `unreal_compile_material` | `material_edit_apply` | Explicit apply of a compile preview only |
| `unreal_preview_material_save` | `material_edit_preview` | Review save after unchanged shader validation |
| `unreal_save_material` | `material_edit_apply` | Explicit apply of a save preview only |

Apply requires an explicit session, the preview ID, and confirmation equal to
that ID. Previews expire after 600 seconds, are capped at 32 per session, bind to
asset state and operation kind, and are consumed once. Failed/uncertain applies
must be inspected before any further mutation.

Compilation and saving both require preview/apply. A compile/save tool cannot
consume a preview for a different action. Generic edit apply can consume any
reviewed edit/compile/save preview, as its description states.

## Supported scope

Destinations are exact package paths under mounted `/Game/` or `/JasperPrism/`.
Object paths, redirects, traversal, arbitrary filesystem destinations and other
plugin mounts are rejected. `/JasperPrism/Materials/M_JasperPrism_PP` can be
inspected and is protected by default. A narrowly scoped, explicit
`development_authorization` permits only completion of its original three-node
contrast graph or compilation of that exact completed four-node graph.

Authorization is an object inside the recipe with `asset_path` equal to the exact
case-sensitive `/JasperPrism/Materials/M_JasperPrism_PP`, `permission` equal to
`I authorize completing the existing JasperPrism contrast graph`, and
`expected_state_id` copied from the latest inspection. No ambient authorization,
wildcard, global bypass, or authorization for other assets exists. Consent is a
caller assertion through the existing authenticated bridge, not independent
verification of human identity. Preview/apply confirmation is still required.

Use `unreal_preview_material_edits` with that object and the exact recipe: one
`Add` alias `contrast_add`, only parameter `const_b=0.5`, one connection from the
inspected Multiply GUID/output zero to Add.A, and one from Add/output zero to
EmissiveColor. No updates, extra expressions, occupied rewiring, or deletions
are permitted. Native validation verifies the current three-node input chain,
constants, unconnected output, correct domain/location, exact asset identity,
and clean baseline before preview and apply. State/fingerprint drift requires a
new inspection and preview. Apply retains the authorization in its one-use preview
and verifies the completed graph before shader validation.

Authorized compile uses the same generic edit-preview tool with `action=compile`,
no graph changes, fresh state ID, and the same authorization. Only the exact
completed four-node graph is accepted. The dedicated compile wrapper remains
protected because it supplies no development authorization.

Before an authorized apply, the native bridge copies the exact original disk
`.uasset` into a unique project Saved/MaterialRecovery file and verifies its bytes.
Split `.uexp`/`.ubulk` packages are unsupported and stop before mutation. The
graph journal/in-memory rollback remain in place. This authorization does not
permit creation, replacement, or saving an existing asset. Existing-material
save requires a separately designed authorization; the normal new-asset save
gate is unchanged. Material development must not be applied until its installed
plugin and MCP schema have been refreshed and the mechanism has passed testing.

Creation supports Post Process (`MD_PostProcess`) with Scene Color After
Tonemapping (`BL_SceneColorAfterTonemapping`). Editing preserves these settings
and requires them to match. Eight expression types are allowlisted:

- `SceneTexture`: `scene_texture_id=PostProcessInput0`, optional `filtered` boolean
- `Subtract`, `Multiply`, `Add`: `const_a`, `const_b`
- `Constant`: numeric `value`
- `Constant3Vector`: three-component `value`
- `ScalarParameter`: explicit unique `parameter_name`, numeric `default_value`
- `VectorParameter`: explicit unique `parameter_name`, RGBA `default_value`

Creation nodes use recipe-local `id` aliases and bounded integer `x`/`y` positions.
Apply returns native expression GUIDs. Updates use those inspected `node_id`
GUIDs, a matching allowlisted `type`, and a typed parameter dictionary. Existing
parameter renaming is excluded because of its effect on material instances.

Connections use `from_node`, `from_output`, `to_node`, `to_input`. A blank output
selects native output zero. `SceneTexture`'s `Color` alias explicitly selects
output zero; channel names are resolved against native output masks. Existing
occupied input connections cannot be replaced. Property connections support an
unoccupied `EmissiveColor` only. Changes are checked for graph cycles before apply.

Inspection reports every top-level expression, comment, native input/output,
connection output index/mask, property input and editable value within a bound
of 256 nodes/comments and bounded response size. Oversized graphs are rejected
without truncation. Nested material functions and instances are not expanded.

## Native APIs and validation

The Editor module uses `UMaterialEditingLibrary::CreateMaterialExpression`,
`ConnectMaterialExpressions`, `ConnectMaterialProperty` and `RecompileMaterial`.
UE 5.6.1's recompile API returns `void`; this implementation then obtains the
active editor material resource at an explicitly captured quality level. UE 5.6.1's
`PostEditChange` uses `EMaterialShaderPrecompileMode::None`; merely calling
`FinishCompilation` does not submit an unused material's deferred jobs.
The validator polls `IsCompilationFinished` for asynchronous cache readiness,
submits the target resource's deferred jobs using `SubmitCompileJobs_GameThread`,
and pumps `FShaderCompilingManager::ProcessAsyncResults` on the game thread.
It reports every `GetCompileErrors()` message and requires no pending cache/jobs,
a complete shader map with shaders, and a full current material shader-map ID and
platform match. An empty compiler-error array is never proof of success.

UE 5.6.1 sets whole-map finalization/success flags in `ProcessCompiledShaderMaps`
only when full material-map DDC is enabled or the material is required-complete
(default/special engine materials). In lazy per-job-cache mode, an ordinary
material's complete rendering clone may legitimately retain both flags false.
Waiting longer does not make those flags an unconditional completion contract.
The validator reads `IsMaterialMapDDCEnabled` and `IsRequiredComplete` rather than
changing either engine policy. It subscribes to
`UMaterial::OnMaterialCompilationFinished` before recompile, captures the exact
current map only after engine result propagation with finished work, completeness
and no resource errors, and removes the listener when validation ends.

Outside lazy mode, finalized/successful flags remain required. In lazy mode with
unset flags, a positive completion notification pinned to the exact current map
is also required. Completeness alone, an empty error list, a stale map/notification,
pending work, and an explicit finalized failure cannot satisfy validation.
Missing finalization evidence remains pending until the wait budget expires.
Successful notification evidence is retained alongside the validated graph and
rechecked against the same map before saving; edits/failure/save/reset invalidate
it. The save gate uses the same checks. Diagnostics retain the raw flags and add
cache mode, required-complete policy, map identity and completion evidence. Success
with lazy-mode evidence reports `compile_reason=validated_lazy_shader_job_result`.
This validates the active editor RHI
feature level/material quality, not all cooking targets or visual appearance.

`compile_state` distinguishes `pending`, `succeeded`, `failed`, `unavailable`, and
`timed_out`. The synchronous apply returns after success, failure, unavailability,
or expiration of its 45-second wait budget; observed intermediate states are
included in `compile_states_observed`. Pending work at expiration is a validation
failure and retains the existing rollback policy. `compile_reason` and
`compile_diagnostics` identify missing resources/maps, skipped compilation,
feature/quality levels (including the actual resource quality fallback), pending
cache/jobs, map finalization/completeness, shader count, and errors. The budget is
checked between engine calls, not a hard interruption of synchronous Unreal APIs.
Recompile/cache/result processing can exceed it and the editor game thread is
occupied during the wait. This is not an asynchronous MCP operation endpoint.
When restoring an existing graph after failure, shader recovery has a separate
5-second wait budget and is reported as `rollback_shader_validation`. Graph
restoration is checked independently; `state=rolled_back` does not assert that
the restored graph has finished shader compilation.

The engine-independent native decision-table test is
`tests/native/test_material_validation_state.cpp`; compile/run it with a C++17
compiler. Python tests exercise MCP preview/apply and authorization independently.
Neither test suite proves shader acceptance inside the running Unreal Editor.

Native changes use `FScopedTransaction` and `Modify()`. A graph-metadata recovery
journal under the project's `Saved/MajesticForge/MaterialRecovery` is written
before graph mutations; it is not a full binary backup. In-memory recovery
restores modified values/connections and removes only newly added nodes after
failure. State reports `completed`, `rolled_back` or `partial`; transport success
does not establish operation success. Failed creation is unregistered and moved
to transient storage; a retained empty package may require editor restart before
reusing that exact destination.

Saving uses `UPackage::SavePackage` on the exact package only. It supports only
new unsaved materials created by this bridge session, requires an unchanged
successful compile fingerprint, rechecks shader status, and refuses existing
asset files. Save success requires `state=saved` and `saved=true`; a save failure
requires inspection of the reported file before retrying. Saved-asset editing
is in-memory only in this version. Session restart discards previews and new
asset ownership/validation state, so finish an authorized creation/save sequence
within one bridge session.

Unsupported in the material-graph tool: arbitrary expression classes/Custom HLSL,
material functions, nested graphs, texture binding, expression deletion, rewiring
occupied pins, other domains/blend locations/properties, parameter renaming,
cross-session preview replay, and all-platform shader checks. Loaded constant
material instances now have a separate typed MCP surface documented below; it
does not extend the parent graph-expression allowlist.

## Material instances

The additional `unreal_inspect_material_instance`,
`unreal_preview_material_instance`, `unreal_apply_material_instance`,
`unreal_preview_material_instance_save` and `unreal_save_material_instance` tools
inspect, create, update and save `UMaterialInstanceConstant` assets. Native
inspection returns inherited global scalar, vector RGBA and texture parameters
with values and per-instance override flags. Preview validates parameter names
and types against the parent, binds the current parameter state, and rejects a
stale apply or an existing destination. Parent materials and source graphs remain
unchanged.

Create requires an already loaded parent and a new `/Game/...` or `/JasperPrism/...`
package path. Update requires an already loaded constant material instance.
Supported updates are scalar values, four-component linear RGBA values and exact
already loaded texture object paths; `null` sets an explicit empty texture override.
Each operation accepts at most 64 changes. Texture loading, recursive package
loading and caller-selected filesystem paths are not exposed. Applying creates or
updates the in-memory asset; persistence is a separate explicit save preview/apply.
New instances must still have no disk package. Existing instances can be saved only
after a ForgeMCP-reviewed update in the same bridge session, and only if the
package was clean before that update. The save preview binds the in-memory state
and current disk-file fingerprint. Save apply first creates and verifies a unique
backup under the project's `Saved/ForgeMCP/Backups/MaterialInstances` directory.
The backup is retained after success. If Unreal reports a save failure, the bridge
attempts to restore the original disk bytes from the verified backup and reports
the disk and in-memory outcome separately; inspect before retrying.

Static switches, component masks, double vectors, texture collections, runtime
virtual textures, sparse volume textures and font parameters are reported as
unsupported by this increment. Static switches change shader permutations and
need a distinct reviewed compile/save lifecycle. The source compiled and linked
into the UE 5.6.1 plugin and the package loaded in a disposable project. Actual
material-instance parameter editing, backup restoration and save/reopen behavior
remain unverified; see `Documentation/Development_Status.md`.

## JasperPrism acceptance checkpoint

The open editor must load a rebuilt native plugin, and the connected MCP client
must rediscover the updated Python server. Source tests/build are separate from
live material acceptance. Do not forcibly close Unreal or use hot reload to
claim the new bridge is installed.

1. Save any wanted open work and close JasperPrismDev normally.
2. Build its editor target from PowerShell:

   ```powershell
   & 'G:\Program Files\EpicGames\UE_5.6\Engine\Build\BatchFiles\Build.bat' JasperPrismDevEditor Win64 Development '-Project=G:\Unreal Engine Projects\JasperPrismDev\JasperPrismDev.uproject' -WaitMutex -NoHotReloadFromIDE -NoLiveCoding
   ```

3. After a successful build, reopen `JasperPrismDev.uproject`, enable/connect
   ForgeMCP normally, and reconnect the ForgeMCP MCP client to refresh its tools.
   Use `forge_list_sessions` to obtain the new session ID; do not assume the old PID.
4. Continue live acceptance through the discovered tools, or run the prepared
   script with the new session ID:

   ```powershell
   & 'G:\ForgeMCP\.venv\Scripts\python.exe' 'G:\ForgeMCP\scripts\verify_unreal_materials_live.py' --session-id unreal-NEWPID
   ```

The script refuses an existing test destination. It checks project identity,
preview non-mutation, native expression types/connections, constants, explicit
compile/edit/save operations, original graph identity, and existing content
hashes. It temporarily tests contrast 1.09 and restores 1.08 before save. It
persists checkpoints to `Saved/MaterialAutomation/live-verification.json` and
stops on an unexpected result. Do not rerun it blindly after any uncertain or
partial result; inspect the target and retained report first.

The authorized test asset is `/JasperPrism/Materials/M_ForgeMCP_Test`. Its four-node
graph is `SceneTexture(PostProcessInput0).Color -> Subtract(A, ConstB=0.5) ->
Multiply(A, ConstB=1.08) -> Add(A, ConstB=0.5) -> EmissiveColor`, using
`BL_SceneColorAfterTonemapping`. No actor, volume, level or original material is
assigned or saved by the script.

## Exact test-material creation authorization

The new-material preview tool accepts a separate `creation_authorization` object
only for `/JasperPrism/Materials/M_ForgeMCP_Test`. It must contain that exact
`asset_path`, the exact permission statement `I authorize creating the ForgeMCP
test material at the exact target path`, and `expected_state: "absent"`. The
native editor rechecks that the exact package path is absent on preview and again
on apply, and rejects case aliases, existing packages, the existing-material
authorization, and this creation authorization on edit/compile/save requests.
The original `M_JasperPrism_PP` authorization remains separate and unchanged.
All typed-node, graph, transaction, rollback, shader validation and save gates
continue to apply. The authorization does not create or save the asset by itself;
preview and apply remain separate operations.
