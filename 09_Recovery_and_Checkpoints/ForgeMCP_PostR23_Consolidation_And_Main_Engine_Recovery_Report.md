# ForgeMCP — Post-R23 Consolidation and Main Engine Recovery (as-is)

Date: 2026-10-22 UTC  
Disposition: **Main-source consolidation passed offline; regular-Engine connection remains unverified.** An experimental package was staged without deployment. Production Phase 6C remains **NO-GO**.

This report records the state at the interruption. The last observation of the regular-Engine safe test was at approximately 18:42 UTC on 2026-10-22. No later Editor or registration state is inferred.

## R23 final verdict

R23's single C0B host session authenticated native startup health and project information, then completed two explicit project-info requests and two complete dirty-package inspections. The before/after inventories both reported 930 inspected loaded packages and the same three dirty rows. Five monitored Content/Config hashes were unchanged. The rendered green indicator was **not observed**; R23 did not stage a release or authorize official-Engine deployment. Its full evidence is in the existing `ForgeMCP_A7K46-C0B-R23_Persistent_Worker_Acceptance_Report.md`.

## Consolidated source and validation

The R18–R23 connection path was consolidated into the main `G:\ForgeMCP` Python tree: `server/core/connections.py`, `process_identity.py`, `connection_monitor.py`, `windows_tcp_listener.py`, `windows_tcp_bootstrap.py`, `persistent_listener_worker.py`, `windows_tcp_worker.py`, and the focused worker tests. The regular host catalog in `server/main.py` was not replaced with the C0B-only four-tool preservation catalog. The official Engine plugin and its loaded binaries were not edited.

The main-tree offline regression run passed **490 tests in 29.45 seconds**. Ruff `check server tests scripts` and Python `compileall -q server tests scripts` both passed. This establishes Python regression compatibility, not a regular-Engine live connection or native rebuild. The original R21/R22 pre-bootstrap listener stall was never causally explained; R23 eliminated the repeated listener child startup and passed its bounded disposable live test. The persistent worker's small pipe write lacks an independent OS-level write watchdog, and broader lifetime reliability remains unproven.

## Experimental alpha staging

A **non-deployable experimental** candidate was staged at:

`G:\ForgeMCP\Saved\ForgeMCP-ExperimentalConnectionRecovery-0.2.16-alpha.2-20261022`

Its staged descriptor is numeric version **31 / 0.2.16-alpha.2** and its copied host package metadata is **0.3.16**. It combines the consolidated host Python source with a copy of the current official UE 5.6.1 Forge plugin; its native DLLs are reused from the installed version 30 plugin and were **not rebuilt**. The stage includes release notes, a file-hash manifest, the previous installed plugin tree, a Git-HEAD source rollback archive, and rollback instructions. Its ZIP has **94 files**, SHA-256 `44A3273F1F3D4039B01A13D0611F9F251AAB24F3BF82570072B42EB1EC7A9687`. ZIP entry count, entry hashes and CRC integrity were checked with no mismatch. Installability, rendered indicator behavior, and regular-Engine compatibility were **not accepted**. No official installation was overwritten.

## Isolated Editors and retirement

The last passive process inventory found protected A7K41 Editor PID **15144** on the official UE 5.6.1 executable and C0B disposable Editor PID **42880** on the StageA7G UE 5.6.1 executable. R23's last C0B native inventory had three dirty rows: `/Engine/Maps/Entry`, `/Script/MediaPlate`, and `/Script/SlateCore`. That is historical to R23, not a current shutdown snapshot. A7K41's current dirty/unsaved state was **not queried**. Neither Editor was closed, saved, discarded, or restarted. **Isolated-environment retirement is NOT READY** until current dirty state is safely established and the owner directs lifecycle handling.

The separately created build Engine is `G:\ForgeMCP-StageA7G-UE56\UE_5.6`. Its `Build.version` hash matches the official Engine, but its Engine plugin descriptor and Editor DLL hashes differ from the official installation; its Engine Intermediate directory and 25 UBT run markers existed at the last inspection. A complete unique-source/dependency/evidence comparison was not performed. **Deletion eligibility is NOT ESTABLISHED; no deletion was attempted.**

## Regular UE 5.6.1 recovery attempt

The official installation at `G:\Program Files\EpicGames\UE_5.6` reports UE **5.6.1 / changelist 44394996**. Its installed Forge descriptor remained numeric version **30 / 0.2.16-alpha.1**. Official Editor and Runtime DLL hashes differed from the C0B disposable binaries; their Engine `UnrealEditor.modules` BuildId was `43139311`.

An initial existing empty validation project, `Saved\PublicationHostCheck-20261010\ForgeMCPDev.uproject`, unexpectedly preferred its **project-local MajesticForge** plugin over the Engine copy. That Editor (PID **28816**) subsequently logged `MajesticForgeRuntime` module-not-found and exited. No host was launched against it. This result does not test the regular installation's plugin.

A second existing asset-free package-acceptance project, `Saved\UnrealPackageAcceptance-d2fa565a7fb24586982fdd697cbf826f\ForgePackageTest.uproject`, has no local Forge plugin. The official Editor launched as PID **43340**, and its log confirmed **Mounting Engine plugin MajesticForge**. At the last observation it was alive and doing startup shader work, but the dedicated private registration directory was still empty. Therefore no host startup, token authentication, explicit `project_info`, repeated read-only request, or rendered indicator check was attempted against this regular-Engine session. Its later status is **UNKNOWN**; this report does not authorize a retry or shutdown. Stage logs are under `Saved\ForgeMCP-RegularEngineRecovery-20261022T183507Z-0e68092697f24b27b2c602ef35741570`.

## Boundaries and next action

- **Main source consolidation:** PASS for offline tests; live main-Engine integration unverified.
- **Experimental candidate:** STAGED, explicitly non-deployable and not connection-ready.
- **Regular-Engine connection:** BLOCKED before session registration at the last observation; no authenticated request was made.
- **Connection indicator:** NOT VERIFIED in either R23 or the regular-Engine test.
- **Isolated Editor retirement:** NOT READY; current unsaved state is incomplete.
- **StageA7G Engine deletion:** NOT ELIGIBLE on the evidence collected; owner authorization would also be required.
- **Production project/city:** NOT ACCESSED; production readiness remains NO-GO.

The next bounded action, only under a fresh owner instruction, is to check whether the already-launched official-Engine safe Editor finished startup and registered its private session, verify its exact process/project/module identity, then run one authenticated read-only host acceptance against that session. Do not route through A7K41, deploy the experimental package, close Editors, or delete the build Engine on the strength of this report.