# Alpha.2 — Unreal Send to Blender fix, October 16, 2026

The installed Unreal plugin is **0.2.13-alpha.2** (descriptor version 17).
The external MCP server source is **0.3.7**. Native source remains in
`G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\MajesticForge`,
as requested. The checkout's removed project plugin was not restored.

## Root cause and changes

The selected `Sphere` actor in ForgeMCPDev uses
`/Engine/BasicShapes/Sphere.Sphere`. The panel accepted a loaded StaticMeshActor,
but both the Python request schema and native exporter restricted source paths to
`/Game` and `/JasperPrism`. Python validation therefore rejected the request before
export. Leaving the MCP async task group wrapped that ValidationError in nested
ExceptionGroups; the outer catch-all reported `panel_worker_failed`.

The panel worker now reports typed input validation failures before leaving the
task group, using bounded diagnostic codes without echoing input or exceptions.
Known wrapped failures are classified by their leaf exceptions. Invalid object
names produce `invalid_target_object_name`, and invalid source paths produce
`invalid_source_asset_path`.

Send-to-Blender accepts `/Engine` as a read-only export source. Native export still
requires an already-loaded bounded static mesh, a reviewed preview and matching
confirmation, source snapshot checks, and generated private staging. Engine assets
remain excluded from return/replacement targets and binding-comparison targets.
No unrestricted execution interface or automatic apply/retry was added.

`create_unreal_host.py --plugin-source` and `package_unreal_plugin.py --source`
support the user-selected engine source location. Packaging still compares the
source with a separate isolated build.

## Verification

| Check | Result |
| --- | --- |
| Python suite | 339 passed; `Saved/alpha2-pytest-final.log`. |
| External server installation | Editable installation updated to 0.3.7; installed package metadata verified. Runtime dependencies were retained. |
| Lint | Ruff passed for server, tests and changed Python helpers. |
| Windows panel launch reproduction | Original error reproduced with piped stdin/stdout and no stderr handle. Exception inspection identified nested ValidationError, not a pipe creation failure. After the worker fix, invalid names returned the typed diagnostic. |
| UE 5.6.1 editor build | Passed, restricted to MajesticForge and MajesticForgeRuntime with `-NoEngineChanges`; all 25 actions completed. |
| Native automation | `ForgeMCP.Transfer.EngineSource` passed: engine sphere preview/export for FBX and OBJ, unchanged source snapshot, unchanged engine package bytes and unchanged dirty state. |
| End-to-end panel worker | Both FBX and OBJ transfers completed into separate background Blender; imported objects were verified as meshes. User scenes were not used for mutation tests. |
| Engine update | Installed after the user saved and closed Unreal; installer retained a backup and modified no project files. |
| Installed DLL and MCP | A fresh Blueprint-only project loaded the engine DLL. Version alpha.2, DLL checksum and archive identity matched; real stdio MCP discovery and project identity passed with 104 registered tools. |
| User Blender scene | Re-inspected after tests: unsaved Scene with Camera and Light, no mesh added. |

The first disposable transfer run completed both workflows but its harness checked
the automation log before the queued test finished. The harness was corrected to
wait for completion; the subsequent complete run passed. An initial unrestricted
native build was stopped when it scheduled unrelated engine-plugin modules; the
accepted build used explicit module filters and `-NoEngineChanges`.

Visible Slate button interaction and visual mesh/material quality were not
verified. The successful end-to-end check exercised the same worker protocol used
by the panel, with real native export/import and confirmation.

## Package, backups and evidence

- Package: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.2-UE5.6.1-Win64.zip`.
- SHA-256: `17ead4e59f4f04beb2db0919f6880695934df694d3937eb89565999752d11556`.
- Build log: `Saved/AlphaValidation-20261016-01/build-alpha2-focused.log`.
- Native and FBX/OBJ panel acceptance:
  `Saved/AlphaValidation-20261016-01/HostProject/Saved/EnginePanelAcceptance-7243068d80e84d1fbed5f8b3659f35a5/acceptance.json`.
- Installed engine DLL and live MCP acceptance:
  `Saved/UnrealPackageAcceptance-ad84e04e153f4918b7d2ea911cf02d55/acceptance.json`.
- Original alpha.1 installation, preserved before source edits:
  `<EngineRoot>/Engine/Saved/ForgeMCPDevelopmentBackups/TransferFix-20261016-alpha1`.
- Pre-update installation backup, including pending source edits:
  `<EngineRoot>/Engine/Saved/ForgeMCPInstallBackups/f3394c7e2bb24588800a398448b5dbf0/MajesticForge`.

The isolated build host was reused; the alpha.1 ZIP and its dated evidence document
remain available. For rollback, close editors and reinstall the retained alpha.1
ZIP with the validated engine installer, or restore the original pre-edit backup.

Reopen Unreal, select the sphere, choose **Send to Blender**, review the preview,
then confirm. The Unreal panel starts a fresh Python worker for each transfer.
Restart a separately running MCP client/server connection to load server source
0.3.7 when using its tools directly.
