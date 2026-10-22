# ForgeMCP Stage A.7K-37 — Landscape Transaction Safety and Write-Scope Validation

Date: 2026-10-20 (America/Toronto)  
Engine target: Unreal Engine 5.6.1  
Source versions: ForgeMCP core 0.3.15; Unreal plugin 0.2.15-alpha.1  
Disposition: **Source repair and build checks passed. World Partition runtime acceptance stopped before Apply because the fresh disposable Editor reported one unresolved dirty engine-script package. No release candidate was produced.**

## Implemented changes

The create preview now includes a structured `write_scope` contract with:

- The exact deterministic `.umap` destination.
- Separate `/Game/__ExternalActors__/<target-map>/**` and `/Game/__ExternalObjects__/<target-map>/**` namespaces whose filenames are explicitly identified as Unreal-generated and not exact predictions.
- Expected package sidecar, autosave/recovery, source-control, log, per-project settings, and ForgeLandscape backup categories.
- Existing map, sidecar, loaded-package, external-actor-root, and external-object-root overwrite checks.
- Potential Editor-generated side effects, unknown or unbounded effects, and preservation/rollback limitations.

Before create Apply, the native handler now rechecks the target destinations, requires the exact active project to carry a disposable-project marker and matching `FORGE_LANDSCAPE_DISPOSABLE_PROJECT_ROOT`, requires a complete loaded-package dirty scan with zero dirty packages, verifies World Partition Editor support before map transition, and rechecks that the requested target and generated namespaces are absent. Any dirty package blocks Apply, including unresolved engine-script packages. In-place creation is disabled by this disposable-project policy.

After a successful create, the plugin reports loaded package names in the target map and external namespaces, marked explicitly as incomplete observations. This is not treated as a filesystem manifest. The disposable acceptance runner hashes the project file set before and after testing and flags every changed path outside its declared policy. That audit detects writes after they happen; it does not prevent Unreal from issuing an unanticipated write. Because `SaveLevel` cannot predeclare or fence all engine-generated output, create Apply is restricted to a marked disposable project. No complete rollback is promised; after a partial map transition or save failure, retain evidence and discard the disposable project as a whole.

The runtime harness also sends an authenticated preview-only create request directly through the isolated `ConnectionManager` to the native Editor bridge, bypassing the MCP request schema. An out-of-scope map path was rejected by the plugin with `invalid_destination`; the full disposable project file snapshot was identical before and after, and Apply was never called. This proves that specific native path guard rejects that request. It does not prove that every possible Unreal-generated file side effect can be prevented.

The dirty-package request now accepts an optional `target_map_path`, bound to the immutable snapshot context. Rows report package domain, unresolved engine-script/project-content classification, current-world association, and a package-path-only match against the proposed target namespace. `classification_complete` remains false for unknown or truncated rows. These fields do not claim ownership where package-path evidence is insufficient.

## Source files changed by this stage

- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp`
- `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.h`
- `Plugins/Forge/Source/MajesticForge/Private/ForgeDirtyPackages.cpp`
- `Plugins/Forge/MajesticForge.uplugin` — version advanced to 0.2.15-alpha.1.
- `server/core/dirty_packages.py`
- `server/main.py` — core status version advanced to 0.3.15.
- `pyproject.toml` — package version advanced to 0.3.15.
- `scripts/verify_landscape_mcp.py`
- `scripts/run_isolated_landscape_acceptance.py`
- `scripts/package_unreal_plugin.py`
- `tests/test_dirty_packages.py`
- `tests/test_native_plugin_contract.py`
- This validation report.

Other existing local changes in the checkout were preserved.

## Verification results

- Python regression suite: **479 passed**.
- Ruff: **passed** for the full repository.
- Python bytecode compilation: **passed** for `server`, `tests`, `scripts`, and the Blender add-on source.
- Unreal Editor target: **39/39 actions passed**, including `ForgeLandscape.cpp` and `ForgeDirtyPackages.cpp`. The first build attempt stopped at UnrealBuildTool's Live Coding guard. The successful retry used `-NoHotReloadFromIDE -NoHotReload` on the disposable build target; the running Editor and Live Coding state were not changed.
- A temporary plugin archive was built only as disposable runtime-test input: `Saved/A7K37-LandscapeSafety-fab1d86594f9442c8a8e29556001ee68/AcceptanceInput/ForgeMCP-Unreal-Alpha-0.2.15-alpha.1-UE5.6.1-Win64.zip`, SHA-256 `cafe80919c19ed7c32bfaac3daf7a85f51cd765e3068599d3ff6022d5481c6af`. Its manifest declares core compatibility 0.3.15, write-scope schema 1, and `interactive_acceptance_complete: false`. It is not a release candidate.
- The final corrected disposable rerun completed under the private root `%LOCALAPPDATA%\ForgeMCP\IsolatedLandscapeSmoke\4819de345c9a475e89ff2ba852b237b1`, with Editor PID `11244`, session `unreal-11244`, and port `52892`. Its authenticated plugin health reported `0.2.15-alpha.1`; the loaded project-local DLL SHA-256 was `0ac68e4ca020204b09d6db9e46596ccfdb5016cbfaec067c58148ea43e9b2db4`, matching the extracted package manifest. Core status reported `0.3.15` in the isolated stdio acceptance.

## Disposable World Partition runtime result

A fresh private project and Editor were launched from the UE 5.6.1 installation. The runner verified the private registration and process identity, then the stdio acceptance started `server.isolated_host` with `FORGE_HOST_MODE=isolated` and exact session allowlisting. The Editor used the project-local plugin DLL matching the temporary archive manifest. Core status reported 0.3.15 and plugin health reported 0.2.15-alpha.1. No existing Editor or `server.main` process was contacted or changed.

The read-only dirty-package inventory inspected 600 loaded `UPackage` objects and was complete for that loaded-object scope. It returned one dirty row under snapshot `E8798873499B4584AD1CD1B738C51EF7`: `/Script/SlateCore`. The row was identified as an engine-script package but had `classification_complete: false` and `associated_objects_truncated: true`, so its association remains unresolved. It was not assumed harmless or exempted. The row blocked Apply as required.

The create preview verified the disposable-project marker, absent target destinations, and World Partition Editor preflight, but returned `apply_allowed: false` because the dirty-package gate found the unresolved package. No world transition, Landscape Apply, SaveLevel, Landscape package creation, or rollback test occurred. The exact proposed map was `/Game/ForgeMCPTests/Landscape/L_A7K37_WP_4819de34`; its `.umap` file remained absent.

Two negative path checks passed. The typed MCP/core request was rejected before native Editor dispatch. The direct authenticated native preview returned `invalid_destination` for the out-of-scope map path; its before/after project file snapshot was unchanged, and Apply was not invoked. The final run's post-run audit found only the harness report `Saved/LandscapeDevelopment/phase6-L_A7K37_WP_4819de34.json`; there was no map, Landscape package output, or out-of-scope path. These checks verify those rejection paths and the blocked run, not a successful Landscape write set or general prevention of every engine side effect.

The disposable Editor process exit was confirmed after the final test. The runner stopped only the child process it had launched; this was disposable-test cleanup, not a transition of the user's existing Editor. The final isolated validation root remains at `%LOCALAPPDATA%\ForgeMCP\IsolatedLandscapeSmoke\4819de345c9a475e89ff2ba852b237b1`. Earlier corrected-harness attempts also left their own disposable roots; none were used as a user project or modified the existing Editor. The source-build and temporary archive evidence remains under `Saved/A7K37-LandscapeSafety-fab1d86594f9442c8a8e29556001ee68`.

## Remaining blockers and deployment gate

The native package compiled and automated checks passed, but World Partition Landscape creation, external actor generation, save/reload persistence, height-data persistence, collision after reload, post-Apply write-set accounting, and mutation rollback behavior remain untested because the unresolved dirty package correctly blocked Apply. The test used `-NullRHI`, so it would not establish interactive viewport appearance even if Apply had proceeded.

No wheel or final plugin candidate was built or placed in `Artifacts`. The temporary plugin was copied only into the fresh disposable runtime-test project; it was not installed into the user's existing project or Editor. The next deployment gate is to resolve the `/Script/SlateCore` inventory ambiguity through an explicitly reviewed policy decision or a better bounded observer classification. Do not add a broad engine-package exception without separate approval. Then rerun the fresh disposable World Partition acceptance; only a successful Apply, persistence/collision verification, and clean declared-scope file audit can justify packaging a coordinated 0.3.15 / 0.2.15-alpha.1 candidate. The current Editor, installed binaries, production city, Blender profile, and existing server processes remain untouched.
