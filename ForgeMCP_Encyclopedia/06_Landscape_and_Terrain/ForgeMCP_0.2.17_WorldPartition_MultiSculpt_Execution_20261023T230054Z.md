# ForgeMCP 0.2.17 — Complete World Partition Multi-Sculpt Acceptance

Current overall status: **INCOMPLETE — MANUAL SAVE OUTPUT VERIFIED; ROOT BYTES UNCHANGED; INDEPENDENT RELOAD PENDING**.

Latest read-only save verification: [October 23, 2026, 23:17 UTC follow-up](ForgeMCP_0.2.17_MultiSculpt_ManualSave_Verification_20261023T231706Z.md). Owner manual production save is evidenced for both packages; only proxy bytes changed. Historical save-preview failure and unsaved-state findings below are preserved as historical observations. Close-up/collision/reload acceptance remains incomplete.
Native multi-sculpt execution and height-data verification: **PASS**. Complete visual/collision/save/reload acceptance remains incomplete.
Stage 2E independent reload acceptance: **NOT TESTED**.
Phase 6C release acceptance: **NOT TESTED**.

This report belongs to the continuous bounded execution authorized by the owner. Both operations have now completed under one locally approved session. The latest execution section below supersedes the historical preparation record; earlier reports and checkpoints are preserved.

## Historical preparation record

## 1. Editor and ForgeMCP identity — PASS

Fresh session discovery and project identity confirm unreal-43744 / PID 43744, ForgeMCP 0.2.17-alpha.1, UE 5.6.1-44394996+++UE5+Release-5.6, G:/ForgeMCP/ForgeMCPDev.uproject, /Game/Levels/L_City_World_Master.L_City_World_Master, PIE stopped.

## 2. Initial clean-state verification — PASS

Complete native loaded-package inventory inspected 1183 packages, with no errors, no inventory limit and no further pages. No dirty production Content was found. The only dirty entry was compiled-in engine-script /Script/SlateCore. Snapshot: 4FC97A114529306E468829A60D05F930.

Fresh full Content comparison covers 1530 files. Differences from the recorded post-riverbed baseline remain exactly the owner-reviewed weather changes: Weather Blueprint changed, new Weather actor file added, older Weather actor file absent. No additional Content differences were found.

## 3. Landscape baseline — PASS

Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D; 2041 x 2041.
Original Layer GUID 198824024FF8A77A01535B86021D9B34; full height MD5 9f43572fbc2c06ef497da015879cdb23; 0/0 cm.
ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B; full height MD5 dd428766880ec01a848b4381fba82838; -100/0 cm.
Both layers visible/unlocked; Landscape clean and layers_up_to_date=true.
16 loaded / 0 unloaded streaming proxies; 64 registered terrain and 64 registered collision components.
Landscape transform: location [-102000,-102000,0], rotation [0,0,0], scale [100,100,100].
Actor GUID CAA5D71B4DD9384CFF8983A038F9489B is distinct from the Landscape GUID.

Native bounded read [1042,1065,1098,1075] returned 627 samples and MD5 cfdb50245810f533f518bdbe7bf75f7c.

## 4. Checkpoint verification — PASS for preparation; new native checkpoint pending approval

Rehashed all 32 external first-riverbed backup files and all 23 native first-riverbed backups. Native manifest SHA-256 matched e48b4397d48971919004002b8ddfbaa7f62546b50ef243b46d921f17f229c0cc. Historical recovery files were not changed.

An independent SHA-256/MD5 inventory of the current map, sidecars and external actor/object namespace contains 23 files, matching native preflight's backup_source_file_count=23. Exact file paths, sizes and hashes are retained in the plan artifact.

The supported native local approval creates the NEW immutable full world/external-package checkpoint. No such new checkpoint exists before approval. After approval, verify all copied files, manifest, current-source hashes and scope before previews/apply.

## 5. Exact operation preparation — PASS; native previews NOT TESTED

Both operations use apply_heightmap on ForgeTerrain only.

| Operation | Write rectangle inclusive | Normal halo inclusive | Supplied samples | Predicted changed vertices |
|---|---|---|---:|---:|
| Left | [1043,1068,1057,1074] | [1042,1067,1058,1075] | 105 | 60 |
| Right | [1083,1066,1097,1072] | [1082,1065,1098,1073] | 105 | 60 |

Combined authorization rectangle: [1042,1065,1098,1075], 627 vertices. Action scope: apply_heightmap only. Bounded scope, requested lifetime 7200 seconds after approval.

Exact row-major arrays are saved in the plan artifact. Longitudinal cubic smoothstep and transverse raised cosine shape the new sections; all baseline nonzero samples are copied unchanged. At Z scale 100, the native height step is 0.78125 cm; both new minima are -35.15625 cm.

Independent saved-plan checks passed: 105 representable samples per operation, 60 changed zero-to-negative samples each, 120 total changes, all 101 existing carved nonzero samples unchanged, halos within scope, and each new depression connected by submerged vertex adjacency to the existing riverbed. These are computed checks, not native preview or viewport proof of smoothness.

| Predicted localized hash | Left | Right |
|---|---|---|
| Halo before MD5 | f35abdbd758fd302cdede925fe4a97f6 | 2a5fd6031649667dec296863c6cf6ff0 |
| Halo after MD5 | 76649356e29c649ce62ae284849e3330 | 64be01979356c82f4147335d03332d7b |

Native prerequisites require approval before production sculpt previews. ForgeLandscape.cpp rejects unapproved grants/protected-world operations. ForgeLandscapeAdoption.inl creates the checkpoint during local approval. Consequently native previews are deferred until the prerequisite approval, and BOTH must pass before the first apply. No alternate grant or bypass was used.

## 6. Owner editing-session approval — BLOCKED, pending

Exactly one native request was registered:
- Editing-session ID: E1E328994273443311FB4A880BC326BE
- Returned state: pending_local_approval
- Local command: Forge.Landscape.ApproveEditSession E1E328994273443311FB4A880BC326BE
- Project/PID/Landscape/layer/region/action identity matches the scope above.

Pending requests expire after 300 seconds. No automatic second request is authorized by this report. If denied/canceled/expired, stop and report before further work.

Current native status is retained in authorization.json. No editing operation has been applied.

## 7. Operation one result — NOT TESTED

Await local approval, independent checkpoint verification and both successful native previews. Then apply reviewed operation one and poll its job; verify expected readback and preservation before operation two.

## 8. Operation two result — NOT TESTED

Must use the SAME approved editing session. No save between operations. If the session becomes invalid, stop rather than request another automatically.

## 9. Before/after verification — NOT TESTED

After execution verify expected localized hashes, all 101 original carved samples, protected Original layer full checksum, native full expected target checksums, absence of height changes outside the specified rectangles, and native recovery/result artifacts.

## 10. Proxy/collision verification

Baseline topology/registration: PASS. Post-operation topology and actual collision behavior: NOT TESTED. Use only safe supported inspection; no PIE/reconfiguration implied.

## 11. Viewport evidence — NOT TESTED

No rendered deformation evidence exists for the proposed operations. Capture only after real native completion; do not present computed arrays as rendered terrain.

## 12. Authorized save — NOT TESTED

No save approval requested or received. After both verified operations, inventory modified packages and prepare the exact native save scope, then obtain separate owner approval. Revoke the editing session before a final save as required by the documented workflow. Never use Save All or an adapter that restores/deletes files after verification failure.

## 13. Independent disk-reload — NOT TESTED

After a separately approved and verified save, prepare the independent Stage 2E-R copy and isolation proof. Request separate launch approval. No isolated Editor was launched.

## 14. Evidence

- [Exact arrays, native baseline, preflight and current-source inventory](WorldPartitionMultiSculpt_20261023T230054Z/plan_and_baseline.json)
- [Native request and status](WorldPartitionMultiSculpt_20261023T230054Z/authorization.json)

Plan SHA-256: 4fc38bcad254f1e1bb8af62b9e17b3b4fe53832163a56a84ba6ef3e208a5a43d.

## 15. Outstanding issues and verdict

**BLOCKED — LOCAL OWNER APPROVAL REQUIRED**. No failed native sculpt is reported; no sculpt was attempted. Preparation and computed safety checks passed. The new approval checkpoint, native previews, both actual operations, final save and isolated reload remain pending. Continue this same bounded workflow only after actual native approval is verified.

## Latest execution result — October 23, 2026, 19:10 EDT / 23:10 UTC

**Overall workflow: BLOCKED — SAVE-PLAN VERIFICATION AND VIEWPORT ACCEPTANCE GAPS.**

**Native multi-sculpt execution and height-data verification: PASS.**
**Complete visual/collision/save/reload acceptance: NOT TESTED or incomplete as detailed below.**

This section supersedes the earlier pending-approval status. The preparation record above remains historical.

### Approval and current checkpoint — PASS

Native status verified local approval for editing session E1E328994273443311FB4A880BC326BE: approved=true, revoked=false, expired=false, no prior operations at resume. Same Editor unreal-43744 / PID 43744 and expected project/world/plugin; PIE stopped.

The new native checkpoint is Saved/ForgeLandscapeAdoption/E1E328994273443311FB4A880BC326BE. Independently verified all 23 expected source/backup files against the prepared SHA-256, MD5 and size inventory. Manifest SHA-256: f77b772e73774f1516b9fb94ecfd73584ccffa482ecabd92bc92e400a9181ed5. No second request or approval was created.

### Native previews and operations — PASS

Both native previews succeeded before the first apply and exactly matched prepared arrays, regions, session and independent halo hashes. The right operation was previewed again after the left completed so its full expected result used the verified new unsaved baseline. The preliminary right preview was never applied.

| Result | Left extension | Right extension |
|---|---|---|
| Applied operation/job ID | 3899352B47D30728C657E097D672410E | EBF1DA4A435344816097BC808E39C6A1 |
| Write region | [1043,1068,1057,1074] | [1083,1066,1097,1072] |
| Native terminal state | completed, empty error | completed, empty error |
| Rows / supplied samples | 7 / 105 | 7 / 105 |
| Changed vertices | 60 | 60 |
| New minimum | -35.15625 cm | -35.15625 cm |
| Local halo after MD5 | 76649356e29c649ce62ae284849e3330 | 64be01979356c82f4147335d03332d7b |
| Full ForgeTerrain after MD5 | a8c9075f9154c9ba1e50514fca020420 | 08cbe382a59441d8148a674cf0d83851 |
| Native height readback validated | true | true |
| Saved | false | false |

Session status records exactly these TWO completed operations under the same approved editing-session ID, with protected_layers_verified=true for both and no active operation. No save occurred between them, and no operation was repeated.

### Independent preservation and height verification — PASS

Final bounded readback of all 627 authorization-region samples matches the independently prepared combined result exactly. There are 120 changed vertices, all within the two write rectangles. All 101 pre-existing nonzero carved samples are unchanged. Final bounded MD5: 3817bd2c18535a9b4529387de493f2b9.

Independent binary verification validated every retained layer snapshot and result record. Patching operation one's full 4,165,681-sample baseline with the exact left array reproduces full MD5 a8c9075f9154c9ba1e50514fca020420 and is byte-identical to operation two's native target-layer checkpoint. Patching that with the right array reproduces final full MD5 08cbe382a59441d8148a674cf0d83851, matching native inspection/result. This establishes full-height-array changes consistent only with the intended patches; it is not a serialized package comparison.

Original Layer GUID 198824024FF8A77A01535B86021D9B34 and full MD5 9f43572fbc2c06ef497da015879cdb23 remain unchanged. Landscape GUID remains BD45FDD94EC2A29617B50794F2DE4E9D. ForgeTerrain minimum remains -100 cm; maximum 0 cm. Both layers remain visible/unlocked; layers_up_to_date=true.

Final disk check found all 23 pre-operation world/external-package source SHA-256 values unchanged. The new sculpt result remains in memory, not saved to production packages.

### Proxy and collision verification

Topology/registration: PASS — 16 loaded / 0 unloaded streaming proxies, 64 registered terrain components and 64 registered collision components.

Actual collision-height behavior: NOT TESTED. Both native jobs report collision_height_validated=false and collision_validation_deferred_until_save_reload=true. No collision reconfiguration or save/reload was performed to force this gate.

### Viewport evidence — captured; acceptance incomplete

Captured the actual active native wireframe viewport, 795 x 720 JPEG. It shows terrain geometry but is too distant to confidently assess both new extension joins and their smoothness. Do not treat it as accepted close-up visual proof.

![Actual native viewport after both operations; distant view, close-up acceptance pending](WorldPartitionMultiSculpt_20261023T230054Z/final_viewport.jpg)

### Modified-package inventory and save boundary

Complete final inventory: 1183 loaded packages, no inspection errors, no further pages. Exactly TWO dirty production packages, both resolved to the affected Landscape:

1. /Game/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2 — LandscapeStreamingProxy_2_2_0.
2. /Game/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT — Landscape root.

Only /Script/SlateCore is additionally dirty, classified as compiled-in engine-script provenance. No Weather, Sky or unrelated project package is reported dirty.

Candidate future save scope consists of these two Landscape packages only. A validated executable save plan has NOT been established: unreal_preview_current_level_save returned ok=false, code invalid_native_result, message "Current-level save preview could not be completed."

No save apply wrapper, Save All, cleanup, rollback, package deletion or restore was invoked. No save approval is implied by the sculpt approval. The session was not replaced or silently rebased.

### Independent disk-reload — NOT TESTED

No isolated Editor was launched. Preparation/launch must follow a successful separately approved save and use the newly verified saved hashes; separate owner launch approval remains mandatory. Stage 2E reload and Phase 6C release acceptance are unclaimed.

### Remaining blockers and next steps

Stop at the current verification blockers: the save-plan preview failed, and close-up viewport assessment is incomplete. Preserve the current unsaved terrain and recovery artifacts. Do not retry either sculpt.

A close-up camera-only owner inspection/capture is needed to assess both joins. The failed save-plan result must be resolved or replaced by a concrete, reviewed native save procedure for the exact two packages. Obtain separate owner save approval before any save. If saving proceeds later, revoke the editing session at the documented final-save boundary; verify saved bytes and then prepare separately approved isolated reload.

### Latest evidence

[Execution evidence: approval, all previews, both applies/jobs, intermediate/final readbacks and inventories, save-preview failure](WorldPartitionMultiSculpt_20261023T230054Z/execution_evidence.json).

Both native recovery roots retain before.r16, edit_session_checkpoint.json, full-layer .r16 snapshots and edit_session_result.json. Earlier checkpoint/report evidence is preserved.

**Final current verdict: BLOCKED. Two native sculpts and full height-data preservation PASS; complete viewport/collision/save/reload acceptance remains incomplete.**


