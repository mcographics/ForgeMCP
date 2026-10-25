# First Riverbed — Native Authorization Checkpoint

Date: October 23, 2026  
Status: **AWAITING REQUIRED LOCAL EDITOR APPROVAL — NO SCULPT APPLIED**

Fresh authenticated Editor: unreal-22604 / PID 22604, G:/ForgeMCP/ForgeMCPDev.uproject, UE 5.6.1, /Game/Levels/L_City_World_Master. PIE stopped. Complete loaded dirty inventory contains only compiled-in /Script/SlateCore and /Script/UnrealEd, zero dirty production Content. Landscape BD45FDD94EC2A29617B50794F2DE4E9D, Original Layer 198824024FF8A77A01535B86021D9B34 and ForgeTerrain 2E6FC5F94C4EF704F700299B5D08C23B match baseline. Both layers visible/unlocked, neutral 2041 × 2041, full MD5 9f43572fbc2c06ef497da015879cdb23. Sixteen loaded proxies.

## Exact prepared scope

Landscape transform: location [-102000,-102000,0] cm, rotation [0,0,0], scale [100,100,100]. Vertex spacing 100 cm; native height quantum 100/128 = 0.78125 cm.

- Center: world [5000,5000,0] cm, or 50 m east / 50 m north of world origin.
- Edit vertices inclusive: [1055,1067,1085,1073], 31 × 7 = 217 height samples.
- Authorization inclusive including mandatory one-vertex native normal halo: [1054,1066,1086,1074], 33 × 9 = 297 samples.
- Edit world bounding rectangle: X 3500–6500 cm, Y 4700–5300 cm. The bounding rectangle includes zero-height border samples around the curved channel.
- Authorization rectangle: X 3400–6600 cm, Y 4600–5400 cm.
- River longitudinal extent approximately 30 m, local bank-to-bank width approximately 4 m, maximum depression 100 cm. A one-meter sine meander and cosine-squared lateral / sine-squared end taper produce a smooth sampled channel; 1 m vertex spacing limits geometric detail.
- All planned values are between -100 and 0 cm. Original Layer is outside the operation's layer target. Native sculpt code selects the dedicated ForgeTerrain layer; the request schema carries actor/GUID/action/region rather than a user-provided layer GUID.

PlayerStart at [-180,0,100] and inspected UDS/weather origins at [0,0,20] are away from the selected region. No actors matching StaticMesh were found in the active-world search. This is inspected actor-placement evidence, not an exhaustive collision-clearance survey.

## Recovery

New independent checkpoint: G:/ForgeMCP_Recovery_Checkpoints/FirstRiverbed_20261023T192135Z.

manifest.json contains 23 native map/external-package files plus nine supplemental files, all independently copied, readable and SHA-256 matched to current production sources. Link count one and source/destination identity inequality verified. riverbed_plan.json retains the exact sample array and coordinate mapping. Originals and prior checkpoints were not overwritten.

All three older manifest pins, all Stage 1 backups, all native adoption backups and all post-adoption backups were freshly verified. The three current Sky/Weather/PlayerStart source differences relative to the older post-adoption checkpoint match the owner's previously authorized current-state baseline; all remaining protected sources match. See Saved/ForgeMCP_FirstRiverbed_CheckpointAudit.json. Its aggregate postadoption_pass=false reflects those expected source differences, not damaged backups.

## Native preflight and request

Exact action allowlist: [apply_heightmap], lifetime 1800 seconds after approval, exact actor/Landscape/project/PID/world identity and halo-inclusive region above. No setup_layer action, blanket extent or additional capability was requested. Preflight: potentially_adoptable=true, readiness_blocker empty, checkpoint_source_clean=true, target_layer_ready=true, requires_layer_setup=false, backup_scope_readable=true, 23 backup sources, setup_affects_entire_selected_landscape=false, local_editor_confirmation_required=true.

Exactly one new request was issued. Native response:

```json
{"adoption_id":"9633FCA74828A98705B0DBBF690F54A4","state":"pending_local_approval","local_editor_command":"Forge.Landscape.ApproveAdoption 9633FCA74828A98705B0DBBF690F54A4"}
```

The owner must enter the exact command in the existing Unreal Editor console and personally accept the native Yes/No identity/scope dialog. The pending request expires after 300 seconds. Approval creates/verifies the native full world/external-package recovery checkpoint and enables one operation for the requested lifetime. Codex has not entered the command or accepted the dialog. A chat reply alone cannot establish approved native state.

After approval, fresh preflight must verify approved, unused, unexpired/unrevoked state and independently verify the native approval-generated checkpoint before applying. If the request expires, no replacement request will be issued automatically. The old setup grant cannot be reused.

## Execution and remaining acceptance

No sculpt preview/apply, job, height mutation, frame, screenshot or save was performed during this authorization stage. No additional adoption setup, level creation, city-builder execution, new Editor, rebuild, actor modification, startup diagnosis or restore occurred. Existing production bytes remain the checkpoint source; pending request registration is in-memory authorization state only.

After verified local approval: review one native apply_heightmap preview, apply once if the preview matches, poll to completion, verify actual ForgeTerrain changes and Original Layer preservation/outside-region protection, then assess supported scoped save and viewport framing under native safeguards. Saving and independent reload acceptance remain separate. Authorization alone is not successful sculpting.

Complete native request/response and baseline: Saved/ForgeMCP_FirstRiverbed_Authorization_Evidence.json.
