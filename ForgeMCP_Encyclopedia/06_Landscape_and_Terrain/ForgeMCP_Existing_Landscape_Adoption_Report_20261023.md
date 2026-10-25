# Existing Landscape adoption implementation

Date: October 23, 2026 (America/Toronto)

## Disposition

The source implementation adds a separate `adopted_existing_landscape` authorization origin. It does not replace the existing host-issued grant-created Landscape workflow. Production adoption, layer setup, sculpting, and saving were not requested or performed during implementation.

**Source and offline verification are distinct from activation.** The running MCP host and Unreal module remain the previously loaded versions. The new native commands and layer setup have not been executed in the live Editor. Compile-only checks deliberately use `-NoLink`; they do not produce or activate a replacement DLL. Full linking, controlled activation, native automation execution, and live adoption acceptance remain outstanding.

## Live read-only validation

Sessions were rediscovered through this chat's actual ForgeMCP connection. Windows process inspection independently identified one Editor:

- Session: `unreal-18588`; PID: `18588`.
- Project: `G:/ForgeMCP/ForgeMCPDev.uproject`.
- Engine: `5.6.1-44394996+++UE5+Release-5.6`.
- World: `/Game/Levels/L_City_World_Master`.
- Actor: `/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295`.
- Landscape GUID: `BD45FDD94EC2A29617B50794F2DE4E9D`.
- Resolution: 2041 x 2041 vertices; 64 components; 16 loaded streaming proxies and none unloaded.
- World Partition and Edit Layers are enabled.
- Existing layer: `Layer`, GUID `198824024FF8A77A01535B86021D9B34`.
- Layer height readback: minimum/maximum 0 cm; checksum `9f43572fbc2c06ef497da015879cdb23`.
- PIE is stopped. The Editor remains responsive.

These properties match the requested validation target and make it a **structural candidate** for adoption. The currently loaded adapter still reports `mutation_supported: false`. Eligibility under the new native preflight is **not live-verified**, because activating updated code is outside this turn's authorization. No production grant was issued. The existing layer checksum was unchanged across implementation's read-only inspections.

## Why the previous workflow rejected manual Landscapes

The existing native gate rejects ungranted World Partition production worlds. Its existing-world path additionally requires the Landscape GUID to be present in the map of Landscapes created under the exact host authorization. A manually created actor is absent from that map. Sculpting also requires exactly one layer named `ForgeTerrain`; this actor has `Layer`.

The new adoption path provides an independent exact-actor grant. Existing creation authorization, disposable-world rules, and grant-created GUID checks remain in place.

## Modified source files

The working tree already contained unrelated and overlapping uncommitted work. This task preserved it. Pre-edit copies of the six existing implementation files touched initially were retained under `Saved/ForgeMCP-Adoption-Implementation-20261023/`, without replacing existing copies.

Files changed by this task:

- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp`: native routing into adoption, exact grant validation at preview/apply and between batches, non-destructive layer setup/readback, inspection metadata, localized texture reads, grant reset on world transition.
- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.h`: adoption ID retained in preview/job plans.
- `Plugins/Forge/Source/MajesticForge/Private/MajesticForgeModule.cpp`: advertise and route the two adoption commands.
- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscapeAdoption.inl` (new): native approval state, preflight, pending requests, Editor approval/revocation, checkpoint verification and scope validation. Included by `ForgeLandscape.cpp` after existing read/backup helpers.
- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscapeAdoptionTests.inl` (new): native policy and backup-integrity automation tests.
- `server/core/landscape_adoption.py` (new): typed, bounded request schema with no approval capability.
- `server/core/landscape.py`: `setup_layer` action and explicit `adoption_id`; creation schemas retained.
- `server/core/connections.py`: allowlist the two bounded adoption commands; transport/bootstrap behavior unchanged by this task.
- `server/main.py`: expose preflight and pending-request tools using the existing dispatch/authentication path.
- `tests/test_landscape_adoption.py` (new): schema, wrapper, discovery/annotation and native safety-contract regressions.
- `tests/test_mcp_stdio.py`: include both new tools in subprocess discovery expectations.

## Tools and approval boundary

New MCP tools:

1. `unreal_landscape_adoption_preflight(request, session_id)`: read-only eligibility, exact identity, preparation and request/grant status. Reports native readiness, checkpoint source cleanliness/readability, layer existence/visibility/lock state, approval, expiry, consumption and revocation. It neither creates a request nor copies backup files.
2. `unreal_request_landscape_adoption(request, session_id)`: creates an in-memory pending request only. It does not approve a grant, create a backup, modify assets, or save content.

Existing `unreal_inspect_landscape`, preview/apply, job status and cancellation tools are retained. Inspection reports adoption support and layer visibility/lock state. `unreal_preview_landscape` accepts `adoption_id` and the new `setup_layer` action. Apply obtains the adoption ID from the retained native preview rather than trusting new caller approval fields.

Approval is a local Unreal Editor console action:

```text
Forge.Landscape.ApproveAdoption <pending-adoption-id>
```

That command presents a native Yes/No confirmation showing session, project, world, actor, GUID, permitted actions, bounds, lifetime and World Partition status. Only a human's Yes response advances to checkpoint creation and approval. No MCP approval command or caller-supplied approval payload exists. A pending request cannot approve itself.

Revocation is local:

```text
Forge.Landscape.RevokeAdoption <adoption-id>
```

Approval state lives in native process memory. It binds the current Editor PID-derived session, exact project/world, weak world/actor identity, actor path, Landscape GUID, World Partition status, operations, inclusive vertex bounds, expiration and revocation. World changes clear adoption state. Reusing a PID after process exit cannot recover an in-memory grant.

Pending requests expire after five minutes. Approved grants last 30–3600 seconds and authorize one operation. A consumed grant can continue its already-started staged job, but cannot authorize another Apply. Revocation or expiration stops future batches; it does not undo applied rows.

## Region and World Partition protections

Native validation checks active world/actor ownership, GUID, transform, Edit Layers, component/proxy ownership and registration, collision registration, editor streaming/loading support and source readback. Initial adoption conservatively requires all world Landscape streaming proxies loaded, even if the requested sculpt touches a smaller region.

Sculpt grants are limited to 1,048,576 samples and must include the one-vertex normal-update halo. Preview reads only the affected region/halo. Texture source data from non-intersecting components is skipped. Apply rechecks identity, readiness, a clean checkpoint source, backup bytes, layer/transform/height fingerprint and exact grant scope. Running jobs recheck live grant identity, region, expiration/revocation, layer state, accessible components, backup-file presence and per-stage heights.

World Partition is neither disabled nor globally bypassed. Unloaded, partially covered, mismatched or unregistered terrain is refused. This first adoption path intentionally does not grant loading/unloading regions, map transitions, creation, deletion, frame changes, reload, or automatic saving.

## Dedicated layer setup and recovery

`setup_layer` requires its own approval and checkpoint. The request must explicitly cover the complete selected Landscape extent because a new layer is an actor-wide operation; its limit is 4,194,304 vertices. For this actor that is `[0, 0, 2040, 2040]`. It cannot be combined with sculpt actions in one adoption request.

Setup refuses to overwrite an existing `ForgeTerrain`. It creates that dedicated layer through the native API, makes the new layer visible/unlocked and leaves every original layer in place. Before/after readback verifies original layer GUIDs, names, lock/visibility state and height hashes, plus neutral 32768 height samples in the new layer. Setup is not reported complete if that validation fails.

On setup failure the code attempts to remove only the newly created layer, cancels the transaction record and reports failure plus the checkpoint path. This is not a promise of complete automatic rollback of Unreal's resource side effects. Do not save a failed setup. Preserve evidence and use the verified checkpoint for recovery if removal/readback is insufficient.

Sculpting targets only the new `ForgeTerrain` GUID. Multiple pre-existing layers are permitted only on the adoption path. Missing, locked or invisible target layers are refused; existing layers are never silently renamed or unlocked.

## Backup requirements

Local approval refuses unsaved changes in the world and its loaded external namespaces and requires saved Landscape-owned external packages. It never saves those changes to manufacture a checkpoint.

After human confirmation, the existing native backup helper copies the map, sidecars, and complete map-specific `__ExternalActors__` and `__ExternalObjects__` namespaces into:

```text
Saved/ForgeLandscapeAdoption/<adoption-id>/before/
```

Copies are size/hash verified, and `manifest.json` records the source-file hashes and exact adopted identity. The existing bound is 10,000 files / 2 GiB. Approval fails on unreadable, oversized, missing or mismatched scope. Apply verifies checkpoint files/manifest and compares retained hashes with current source and checkpoint bytes. Deleting required backup files during a job stops further batches. A sculpt job also retains the existing regional `before.r16` and metadata backup.

Recovery is explicit and manual: retain the failed-job metadata; close the affected world/Editor without saving unwanted in-memory changes; verify the manifest; restore the checkpoint's map/sidecars/external-package namespace to their original project-relative paths while the Editor is closed. Account for any separately saved files created after the checkpoint. No automated overwrite/cleanup is performed by this feature. Regional height backups alone are not a substitute for the world/package checkpoint.

No production checkpoint was created during implementation, because no adoption request or local approval was issued.

## Verification results

- Python checks: **152 passed**, final run 25.94 seconds. Covers MCP subprocess discovery, adoption schema/wrappers, original authorization/creation, write-scope audit contracts, connection/configuration regressions and native source safeguards.
- Ruff: `python -B -m ruff check server tests` passed.
- Git whitespace validation: `git diff --check` passed, with existing line-ending notices.
- Native compile: **Succeeded**, final complete source pass, 188.18 seconds, including the adoption policy/backup automation code. Evidence: `Saved/ForgeMCP-Adoption-Implementation-20261023/Compile.log`. Compile-only command deliberately does not link or replace the loaded plugin.
- Final targeted safety assertions: **26 passed**, 2.71 seconds, after adding explicit checkpoint-inventory, manifest-integrity and independent-adoption-origin regression assertions. Ruff passed again.
- Native automation added: `Forge.Landscape.Adoption.Authorization` covers exact identity, wrong GUID/actor/project/world/session/partition, missing approval, operation scope, expiry, revocation, single-use continuation, region containment, unloaded/mismatched/unregistered components, missing/locked/invisible layers and missing backups. `Forge.Landscape.Adoption.BackupIntegrity` covers verified backup bytes, tampering and missing copies using generated Saved fixtures.
- Native automation execution: **not run**. The running module predates these tests; loading the new module is prohibited in this implementation turn. Compilation and Python source-contract checks do not establish native runtime behavior.
- Live evidence: existing authenticated inspections succeeded, target identity/topology matched, height checksum unchanged, one responsive Editor. A final authenticated project-info call after the successful compile still identified session `unreal-18588`, the expected project and `L_City_World_Master`, with PIE stopped. These calls used the existing deployed adapter, not the newly compiled implementation.
- Live production adoption, layer setup, sculpting, saved/reloaded terrain, collision acceptance and performance: **not tested**.

Python test command:

```powershell
.venv/Scripts/python.exe -B -m pytest tests/test_mcp_stdio.py tests/test_landscape_adoption.py tests/test_landscape.py tests/test_landscape_authorization.py tests/test_landscape_authorization_tools.py tests/test_landscape_write_scope_audit.py tests/test_native_plugin_contract.py tests/test_host_config.py tests/test_connections.py -q
```

Compile-only command:

```powershell
& 'G:/Program Files/EpicGames/UE_5.6/Engine/Build/BatchFiles/Build.bat' ForgeMCPDevEditor Win64 Development '-Project=G:/ForgeMCP/ForgeMCPDev.uproject' -WaitMutex -NoHotReloadFromIDE -NoLink -NoLiveCoding -NoEngineChanges '-Log=G:/ForgeMCP/Saved/ForgeMCP-Adoption-Implementation-20261023/Compile.log'
```

## Connection impact and activation blockers

No active host or Editor was restarted/reconnected, no connection configuration changed, and no extra Editor was launched. The `-B` bootstrap and 60-second startup timeout remain untouched. Test subprocesses used temporary fake registrations; they are offline integration evidence, not proof of this chat's connection.

The new tools will require a controlled refresh of the existing MCP host after source activation. Native commands require a full linked plugin build and controlled module loading; an orderly Editor restart is the conservative activation route. Neither was performed or authorized here. Do not work around the old module's denial with configuration, marker files or fabricated grants.

## Exact first controlled operation procedure — future authorization required

These are instructions for a later approved session, not authorization to mutate the city now.

1. Arrange a controlled activation window. Preserve user changes; build/link and load the updated plugin, refresh the existing registered MCP host, and run the two native automation tests above. Rediscover the current session/PID/project/world instead of reusing this report's process ID. Confirm the new native capabilities and both MCP tools are present.
2. Inspect the exact actor and confirm its GUID and topology again. Inspect dirty packages. Do not save unrelated work automatically.
3. Call `unreal_landscape_adoption_preflight` with the current `session_id` and this request, substituting freshly verified identities if they changed:

```json
{
  "actor_path": "/Game/Levels/L_City_World_Master.L_City_World_Master:PersistentLevel.Landscape_UAID_701CE7E46087BA0D03_2100287295",
  "landscape_guid": "BD45FDD94EC2A29617B50794F2DE4E9D",
  "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
  "world_path": "/Game/Levels/L_City_World_Master",
  "world_partition": true,
  "editor_pid": 18588,
  "region": [0, 0, 2040, 2040],
  "actions": ["setup_layer"],
  "lifetime_seconds": 600
}
```

4. If preflight is ready and the user explicitly approves production layer setup, call `unreal_request_landscape_adoption` with that same request. This only creates a pending ID. In Unreal, open **Tools -> Debug -> Output Log**, enter the returned `Forge.Landscape.ApproveAdoption <id>` in its command field, press Enter, review the native confirmation and click **Yes** only for the intended scope. A verified checkpoint must complete before approval exists. Re-run preflight to inspect approval/checkpoint state.
5. Call `unreal_preview_landscape` with `action: "setup_layer"`, the exact `actor_path`, the approved `adoption_id` and `region: [0,0,2040,2040]`. Review the preview. Call `unreal_apply_landscape` with `preview_id` and `confirmation` both equal to the returned preview ID only after explicit permission to perform setup. Require completed-unsaved state, original-layer preservation and neutral-new-layer verification. No automatic save follows.
6. Inspect again. If setup failed, stop and follow checkpoint recovery. If it passed, obtain separate permission to save the intended map/Landscape-owned external packages through the Editor; review the package selection and leave unrelated assets unchecked. Wait for native recomposition and confirm a clean checkpoint source. A consumed setup approval cannot authorize sculpting.
7. Obtain a new pending request/Editor confirmation for `actions: ["raise"]`, `region: [999,999,1041,1041]`, lifetime 600 seconds, and the same freshly verified identity. This grants the 40 m hill region plus its one-vertex normal halo. Verify the new checkpoint and approval status.
8. Preview the controlled hill through `unreal_preview_landscape` using the new `adoption_id`, `action: "raise"`, exact actor path, `region: [1000,1000,1040,1040]`, `height_cm: 200`, `strength: 1`, `rows_per_stage: 4`, and `stage_interval_seconds: 0.3`. Review the before/after hashes and scope. Do not apply a rejected or expired preview.
9. Only with explicit permission to sculpt, Apply using the returned preview ID as confirmation. Poll `unreal_landscape_job_status` until terminal state and require exact height readback validation. Revoke through the local console or cancel the job to stop future batches if needed; neither action undoes completed rows.
10. Reinspect `ForgeTerrain` and confirm the original `Layer` checksum remains unchanged. The job is unsaved. Saving production results requires separate, explicit permission and package review; adopted save/reload is deliberately not exposed by this first workflow. A later authorized save/reopen must prove persistence and collision behavior before claiming playable persisted terrain.

## Remaining restrictions

- Approval permits one operation; setup and each sculpt/checkpoint cycle are separate.
- Saved, clean world and Landscape package state is required for each operation's checkpoint. Unsaved results must be deliberately saved or discarded before requesting the next grant.
- Layer setup must authorize the full selected actor extent. Sculpt grants include their halo.
- All Landscape streaming proxies in the world must be loaded for initial adoption; automatic region loading is outside this adoption scope.
- Existing `ForgeTerrain` layers must already be visible/unlocked; the feature will not overwrite or silently change them.
- Unsupported source-layer readback, transform, component/proxy, backup-size or package states fail closed. Native region coordinates retain the existing nonnegative 0–8191 range.
- Heights operate on the dedicated Edit Layer rather than merged/composite terrain heights; flatten/generate values must be interpreted accordingly.
- Saving/reloading adopted production Landscapes remains manual and separately authorized.
- No production terrain deformation or persistence is claimed. Full linked/native runtime acceptance is still required.
