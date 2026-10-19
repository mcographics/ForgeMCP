# Level opening and required editor plugins

Project: ForgeMCPDev, UE 5.6.1. Date: October 16, 2026.

## Findings

`NewMap_PCGTest.umap`, `NewMap.umap` and `TestArea.umap` exist under
`Content/Levels`. The live log records successful normal loading and a clean map
check for `NewMap`, but subsequent asset activation for `NewMap_PCGTest` creates
an inactive World asset rather than changing the main Editor world.

The project uses `DisableEnginePluginsByDefault: true` and did not enable
`EngineAssetDefinitions`. In the installed Epic source,
`Engine/Plugins/Editor/EngineAssetDefinitions/Source/Private/AssetDefinition_World.cpp`,
`UAssetDefinition_World::OpenAssets` supplies the normal Content Browser level-open
handler and calls `FEditorFileUtils::LoadMap`. That plugin is enabled by default in
normal engine configurations, but the project's explicit opt-in policy disables it.
This is a strong explanation for opening a World as a generic asset rather than
activating a level; interactive confirmation after restart is still required.

The log also reports missing `/Script/WorldPartitionHLODUtilities` classes when
loading Open World template HLOD assets. Its engine plugin is normally enabled
by default and was likewise omitted from this project's explicit list.

## Correction and preservation

Enabled `EngineAssetDefinitions` and `WorldPartitionHLODUtilities` explicitly in
`ForgeMCPDev.uproject`, preserving its other settings and plugin entries.
The pre-change descriptor and SHA-256 hashes for all three maps are stored in
`Saved/ReferenceCity_20261016_v1/LevelOpenRecovery/`.
No original map or external actor package is resaved for this diagnosis.
The previous gameplay dependency corrections remain in place.
Also enabled `IKRig` after native startup exposed a missing
`ik_rig_asset_query` Python helper required by Control Rig's startup workflow.
The helper is supplied by the installed IKRig plugin; this final dependency addition
has not yet been verified in a fresh interactive startup.

## Verification

A separate validation project copies the map packages, external actor packages,
required project binaries/configuration, Ultra Dynamic Sky and existing city
assets. Native Editor startup uses `/Game/Levels/NewMap_PCGTest`, NullRHI and
automatic quit; output is retained in `LevelOpenRecovery/MapOpenValidation.log`.
The original project files are checked against their pre-validation hashes.
Native map loading is separate evidence from interactive double-click behavior,
PIE, visual rendering, streaming performance and full city recovery.

Result: the copied `NewMap_PCGTest` loaded as World Type `Editor`, completed World
Partition initialization and passed Map Check with zero errors and zero warnings.
The test still logged missing Interchange import-metadata classes in sky assets;
those messages did not prevent this map load. Hashes of all three original maps
matched during the earlier preservation checks. During the final check, the live
`NewMap_PCGTest.umap` and `NewMap.umap` files were absent; the user was creating a
new unsaved world in the live Editor. No restore was performed pending clarification
of whether that removal was intentional. All three copied maps still match their
recorded original hashes. `verification.json` records this distinction.
The isolated diagnostic process was closed after the map checks; its process exit
code is not used as a pass criterion.

The running user Editor predates the new plugin configuration. Restart the project
before testing Content Browser level activation. Keep city imports stopped until
the intended live level and saved actor state have been inspected again.
