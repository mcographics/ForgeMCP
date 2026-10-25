# Reference city interruption and gameplay dependency recovery

Date: October 16, 2026. Project: ForgeMCPDev, UE 5.6.1.

## Observed crash

The original live Editor (`unreal-26804`) crashed during PIE startup from
`/Game/Levels/NewMap_PCGTest.NewMap_PCGTest`. The log records PIE world creation
at 21:56:03 UTC and a null-read access violation at 21:56:35 UTC.
The stack enters `UAnimBlueprintExtension_PropertyAccess::HandleStartCompilingClass`,
Blueprint compilation, package loading and `UGameInstance::CreateGameModeForURL`.
The crash context does not flag an out-of-memory condition. This evidence points
to a gameplay/animation dependency problem; it does not establish a GPU or city
geometry fault, nor exclude every possible concurrent factor.

Immediately before the crash, the log reports absent EnhancedInput classes,
ControlRig/RigVM classes, AnimationData, and an unknown `AnimNode_ControlRig`
structure in `ABP_Unarmed`. The project explicitly disables engine plugins by
default while selecting `BP_ThirdPersonGameMode` as its global default game mode.
The required gameplay plugins were not explicitly enabled.

## Changes

- Preserved the original descriptor at
  `Saved/ReferenceCity_20261016_v1/CrashRecovery/ForgeMCPDev.before_dependency_fix.uproject`.
- Enabled `EnhancedInput`, `ControlRig`, `AnimationData` and `FullBodyIK` in the
  project descriptor. Existing plugin entries and gameplay asset bytes are preserved.
  FullBodyIK supplies the PBIK structures used by `CR_Mannequin_FootIK`.
- Stopped further city import work. The interrupted transfer
  `90305d885d8f43a5879551395a1fa1b4` ended during staging with `disconnected`;
  no native import-start event or native import report exists for that transfer.
  Its receipt is retained and must not be blindly replayed.
- Updated the importer to require a freshly inspected explicit target session and
  save the level/external actor packages after each successful placement, before
  the next import can invalidate a save preview.

## Preserved city work

Nineteen city static-mesh packages were inventoried on disk under
`/Game/ReferenceCity_20261016_v1/`. This is partial Unreal import completion.
The full 37-mesh Blender source, overview, closer render and source reload report
remain under `Saved/ReferenceCity_20261016_v1/`. The scene contains 5,168 generated
building masses over ten manually interpreted districts, using an assumed three
metres per image pixel. It is an approximate reference-based scene, not a surveyed
1:1 reconstruction, photorealistic completion or a native PCG/spline implementation.

The attempted mid-import level checkpoint was rejected as stale. Consequently,
placement persistence cannot be inferred from import receipts or mesh files.
Reinspect the reloaded target level before restoring missing actors.

## Validation evidence and remaining steps

Validation logs and package hashes are retained in
`Saved/ReferenceCity_20261016_v1/CrashRecovery/`. Initial commandlet attempts failed
to apply their intended allowlist due path handling and native argument parsing;
those diagnostic processes were stopped without saving assets. The corrected
targeted run loaded/compiled the Third Person game mode, character and ABP_Unarmed
without the original crash. It exposed missing PBIK types in the dependent foot-IK
rig, leading to the additional FullBodyIK dependency fix.

The final targeted gameplay/foot-IK compile result is recorded in
`BlueprintValidation_WithFootIK.log` and `footik_exit_code.txt`; inspect both before
claiming validation success. This commandlet does not test interactive PIE, GPU
rendering, collision, World Partition streaming or city performance.

The final log confirms successful compilation of `BP_ThirdPersonGameMode`,
`BP_ThirdPersonCharacter`, `ABP_Unarmed` and `CR_Mannequin_FootIK`, with zero
Blueprint compile errors, warnings or failed loads. The engine reports zero errors
and nine startup warnings: missing ACL animation compression presets and a duplicate
DDC cache path. Those warnings remain outside this minimal dependency correction.
The tracked gameplay package hashes match before/after the diagnostic runs; original
plugin entries compare unchanged, with only the four required entries appended.

The user's replacement Editor launched before the descriptor fix. A fresh Editor
startup is required to load the newly enabled dependencies. Reconnect using a live
session, verify project and `NewMap_PCGTest`, inspect saved city placements, then
resume only the missing imports and placements with per-placement checkpoints.
