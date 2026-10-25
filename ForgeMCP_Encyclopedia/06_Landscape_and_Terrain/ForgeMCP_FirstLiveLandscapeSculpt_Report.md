# First Live Landscape Sculpt — Verified Riverbed

Date: October 23, 2026  
Final verdict: **SUCCESS — LANDSCAPE SCULPT VERIFIED**  
State: One native heightmap sculpt completed, height data and visible geometry verified, and the owner's scoped native save verified. Independent disk reload and collision acceptance are not claimed.

## 1. Authenticated identity and authorization

Fresh discovery and project_info confirmed existing Editor unreal-22604 / PID 22604, G:/ForgeMCP/ForgeMCPDev.uproject, UE 5.6.1, /Game/Levels/L_City_World_Master.L_City_World_Master, PIE stopped. Pre-sculpt complete dirty inventory contained only the two compiled-in engine-script packages; no production Content was dirty.

Landscape GUID BD45FDD94EC2A29617B50794F2DE4E9D. Original Layer GUID 198824024FF8A77A01535B86021D9B34. ForgeTerrain GUID 2E6FC5F94C4EF704F700299B5D08C23B. Both layers remained visible and unlocked.

Approval 9633FCA74828A98705B0DBBF690F54A4 was verified approved=true, used=false, expired=false, revoked=false before preview/apply. Scope exactly apply_heightmap, inclusive region [1054,1066,1086,1074], exact actor/world/project identity. Native checkpoint_files_present=true. Final read-only preflight confirms used=true; it must not be replayed. No additional authorization request or setup_layer operation occurred during this continuation.

## 2. Recovery verification before mutation

External checkpoint: G:/ForgeMCP_Recovery_Checkpoints/FirstRiverbed_20261023T192135Z. All 32 independent source/backup SHA-256 pairs matched before application, including all 23 map/external-package sources and nine supplemental sources.

Native approval checkpoint: G:/ForgeMCP/Saved/ForgeLandscapeAdoption/9633FCA74828A98705B0DBBF690F54A4. All 23 native files matched their manifest MD5, current sources and external checkpoint SHA-256. Native manifest SHA-256 is retained in PreApply evidence. No backup was overwritten or restored. Full original checkpoints remain separate from this sculpt checkpoint.

## 3. Riverbed geometry and coordinate mapping

Landscape origin [-102000,-102000,0] cm, scale [100,100,100], rotation zero; world vertex spacing 100 cm. Center world [5000,5000,0] cm, approximately 50 m east and 50 m north of world origin.

- Edit region inclusive [1055,1067,1085,1073], 31 × 7 = 217 supplied samples.
- Authorized/readback region including native one-vertex normal halo [1054,1066,1086,1074], 33 × 9 = 297 samples.
- Edit rectangle X=3500–6500 cm, Y=4700–5300 cm; zero border values bound a curved channel approximately 30 m long and 4 m locally wide.
- Centerline: y_vertex = 1070 + sin(2πt), t=(x_vertex−1055)/30. Lateral cosine-squared falloff across a two-vertex half-width, multiplied by sine-squared longitudinal taper, reaches zero smoothly at banks and ends.
- Maximum depression 100 cm. At Z scale 100, encoded height quantum is 0.78125 cm. Exactly 101 samples differ from flat after native quantization. Interpolated banks are limited by the underlying 1 m Landscape grid; this is a small native heightfield, not a high-resolution erosion simulation.

Exact floating samples are retained in the checkpoint riverbed_plan.json. The Original Layer was never selected for write.

## 4. Native preview and one application

Preview F546B9324DE219547614F1BEBC7644A6 accepted the exact apply_heightmap request using the existing approval ID normalized to lowercase for the typed schema. It produced 297 snapshot samples including halo, a 1,188-byte before/after height buffer and bounded resource estimates. Returned region, values, authorization and action were reviewed before applying.

Independent calculation using the installed native encoding formula reproduced both preview hashes:

| Height array | MD5 |
|---|---|
| Halo-inclusive flat before | 11d9dc53a9e9591a581b08e0821f0b95 |
| Halo-inclusive expected after | 08d6ac338669dfa1918c1644ce374ef8 |
| Full 2041 × 2041 expected ForgeTerrain after | dd428766880ec01a848b4381fba82838 |

Exactly one unreal_apply_landscape call consumed the preview. Job ID F546B9324DE219547614F1BEBC7644A6 returned running, then native job_status returned completed, error empty, 7/7 rows applied, progress=1, height_readback_validated=true, validated_after_height_md5=08d6ac338669dfa1918c1644ce374ef8, saved=false. Maximum reported stage time 178.339 ms is an observation, not a general performance acceptance result.

The job's raw pre-edit height backup remains at G:/ForgeMCP/Saved/ForgeLandscape/F546B9324DE219547614F1BEBC7644A6/before.r16. No job retry, second sculpt or recovery occurred.

## 5. Actual height and layer verification

| Gate | Before | After sculpt and save |
|---|---|---|
| Original Layer full MD5 | 9f43572fbc2c06ef497da015879cdb23 | Same |
| Original min/max | 0 / 0 cm | 0 / 0 cm |
| ForgeTerrain full MD5 | 9f43572fbc2c06ef497da015879cdb23 | dd428766880ec01a848b4381fba82838 |
| ForgeTerrain min/max | 0 / 0 cm | −100 / 0 cm |
| Layers and dimensions | Expected GUIDs, 2041 × 2041 | Same GUIDs/dimensions, visible/unlocked |
| Proxies loaded/unloaded | 16 / 0 | 16 / 0 |
| Registered terrain/collision components | 64 / 64 | 64 / 64 |

The entire native ForgeTerrain height-array hash exactly matches an independently constructed full array containing only the prepared quantized channel and zero elsewhere. Together with per-stage native sample readback, this verifies the 101 modified samples, −100 cm center at vertex [1070,1070] / world [5000,5000], bank taper and unchanged heights beyond the footprint/halo. These are hash-equivalence and stage-readback results, not a separately exported raw full-height array. Original full-layer hash preservation proves its height data remains unchanged.

At the middle cross-section, the independently encoded array matched by native full readback has center −100 cm, adjacent bank samples −50 cm at world Y=4900/5100, and zero at Y=4800/5200. Longitudinal endpoints and all outside samples remain zero.

## 6. Visible verification

Initial native capture was a distant checkerboard view and was not accepted as close-up proof. User then ran the supplied camera-only helper Saved/frame_first_riverbed.py and confirmed completion. It changes only viewport camera to [5000,2000,1600] cm looking toward [5000,5000,−30], after checking project/world and PIE. No sculpt/save/actor change is in that helper.

Subsequent unreal_capture_screenshot captured the actual rendered Editor viewport at frame 332430, 1280 × 583 JPEG. It visibly shows the curved trough and sloping banks in selected Landscape wireframe. This is native geometry, not an image-generation result, mesh proxy or preview. Wireframe visual acceptance is distinct from a polished lit/material result.

![Verified curved riverbed in native Landscape wireframe](FirstRiverbed_VerifiedCloseup.jpg)

Screenshot: G:/ForgeMCP/Saved/FirstRiverbed_VerifiedCloseup.jpg. Earlier wide view retained at Saved/FirstRiverbed_CurrentWideView.jpg. No Editor resize or disk-reload was used for capture.

## 7. Dirty scope and reviewed native save

After sculpt, complete dirty inspection identified exactly two production external actor packages: the existing Landscape root and existing streaming proxy LandscapeStreamingProxy_B7E96FCS9V6MS9RT9VEJH9KT9_510_2_2_0. Only compiled-in SlateCore/UnrealEd were additionally dirty.

Read-only current-level save preview b09431d647c07c740bc89daead734492 observed 23 packages and selected exactly those two; zero deletions, clean map and unrelated actors excluded. Its apply adapter was never invoked. The owner performed the previously reviewed native File → Save Current Level interaction and replied Saved Current Level.

Native logs independently record InternalPromptForCheckoutAndSave at 19:30:38.779–19:30:39.039 UTC / 15:30:38–39 EDT, moving both exact package outputs into place and validating two assets. Subsequent complete inventories show zero dirty production Content, and Landscape is clean with layers_up_to_date=true. Only the same two compiled-in script packages remain dirty.

| Saved package relative path | Before SHA-256 | After SHA-256 | Bytes |
|---|---|---|---:|
| Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset | 3250d0d5fea2d9c8bba0c85f9450102a1043328ce176d1d26cc210287076a0ea | 90e4cdcb0e922f6551def953212beecd268b6d0383f0452df012d81dc7311aa9 | 608675 |
| Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset | 9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df | Same | 5063 |

The root was saved according to its native output log but serialized to identical bytes. One file has changed bytes; two packages were saved. These counts are intentionally distinct.

Full post-save audit rehashed 1,743 dependency files against the pre-sculpt current-state baseline: exactly the authorized streaming proxy changed; no additions, deletions or unauthorized changes. Scope includes all Content, Config, Binaries, Plugins, Source and .uproject, not generated Saved/cache/user state or every drive file. No unrelated Content actor/asset file changed. All 32 external recovery backups remain hash-verified. No checkpoint was updated to new terrain bytes.

## 8. Evidence and limitations

- ForgeMCP_FirstRiverbed_PreApply_Evidence.json: exact authorization, checkpoint checks, native baseline and preview.
- ForgeMCP_FirstRiverbed_PostApply_Evidence.json: apply/job result, height/layer/dirty inventories and read-only save review.
- ForgeMCP_FirstRiverbed_FinalState.json: final project identity, clean Content inventory and consumed grant.
- ForgeMCP_FirstRiverbed_SaveAudit.json: complete file/hash audit and saved-package records.
- ForgeMCP_FirstRiverbed_SaveLog.txt: native save output.
- FirstRiverbed_VerifiedCloseup.jpg: actual native Landscape geometry.
- External recovery checkpoint report_before_sculpt.md preserves the previous blocked report.

A supplemental read-only collision query timed out. An initial collision-call schema mismatch was rejected before native dispatch because advertised string coordinates conflicted with the strict numeric request model; the subsequent numeric request timed out. It was not retried after timeout. No collision-profile/configuration change was made. Native job reports collision_height_validated=false and defers its collision check until save/reload. Thus collision trace acceptance remains unverified, separate from verified native edit-layer height data and rendered geometry. No runtime walking, PIE, erosion, water or performance acceptance is claimed.

No genuine disk reload was performed; saved-byte verification plus current native readback is not independent reload proof. Stage 2E and Phase 6C acceptance remain separate. No Original Layer modification, additional sculpt, new authorization, city prototype, new level/Editor, rebuild, automatic restore or rollback save adapter was executed. No further terrain work follows this report.

## 9. Final verdict

**SUCCESS — LANDSCAPE SCULPT VERIFIED**

One authorized native ForgeTerrain deformation changed real Landscape height data into the planned curved riverbed. Full-array readback matches the independently expected result, Original Layer is preserved, actual wireframe geometry is visible, the owner's exact native package save is independently verified, and the complete audited dependency scope has no unrelated file changes. Collision and independent disk-reload acceptance remain explicitly outside this success claim.
