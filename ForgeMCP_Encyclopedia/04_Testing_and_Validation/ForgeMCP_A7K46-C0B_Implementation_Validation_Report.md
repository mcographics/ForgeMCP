# ForgeMCP Stage A7K46-C0B — Implementation and Validation Report

Date: 2026-10-22  
Engine target: Unreal Engine 5.6.1  
Disposition: **STOPPED after an UnrealBuildTool log escaped the isolated development root. No Editor or ForgeMCP host was launched. No protected project was contacted or modified. No candidate is ready to use. Production Phase 6C remains NO-GO.**

## Result

A preservation-only host profile and two read-only native inspection implementations were drafted in an independent source copy. The profile and relevant Python contracts passed focused automated checks. The Unreal plugin did not reach C++ compilation: UnrealBuildTool failed while resolving the engine plugin dependency KitBash3dUsdTools, referenced through the default Cargo.uplugin.

During that attempted build, UnrealBuildTool reported its log at C:\Users\Kenne\AppData\Local\UnrealBuildTool\Log.txt, outside the isolated root. This violates the stage's separate-log boundary. I stopped the build attempt and performed no Editor startup or host launch afterward. There is no pre-build hash or metadata baseline for that user-profile log, so its prior existence and whether the build changed its contents are UNKNOWN. The observed file was 9,391 bytes, last written at 2026-10-22T01:25:51.9043595Z, with SHA-256 21C6BEB97F3FF7B7292AF1130AEB7E36C95B1790549EA9B7FCEF41F331F22AEC. It was not modified by this report.

The isolated development root is:

~~~text
G:\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1
~~~

Its independent source copy contains 355 files / 8,214,630 bytes at initial copy verification. The copy manifest SHA-256 is FDFC716DCC2B4A6D083E9307A0F354F6120216D44E9ECD0B931250FD266AB643. The source directories were checked for reparse points before copying; none were found. Original repository files were not edited. The source-copy manifest and hash checks showed the copied source matched the original source set at copy time.

A fresh marked C++ Blank project was created at:

~~~text
G:\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject
~~~

The project contains a disposable marker and a project-local copy of the Forge plugin source. It has no content assets. No Forge plugin binary or Editor target binary was produced. The build may have generated project-local Intermediate files; no cleanup was attempted. A private session directory or registration was not created.

## Implementation in the isolated source copy

The following nine files were changed or added only beneath the isolated source copy:

- server/core/host_config.py
- server/core/connections.py
- server/main.py
- tests/test_host_config.py
- tests/test_mcp_stdio.py
- Plugins/Forge/Source/MajesticForge/Private/ForgeMeshImport.cpp
- Plugins/Forge/Source/MajesticForge/Private/MajesticForgeModule.cpp
- Plugins/Forge/Source/MajesticForge/Private/ForgeWorldSaveScope.cpp (new)
- Plugins/Forge/Source/MajesticForge/Private/ForgeWorldSaveScope.h (new)

The profile implementation adds preservation_readonly with the exact declared catalog:

1. unreal_project_info
2. unreal_inspect_dirty_packages
3. unreal_inspect_static_mesh
4. unreal_inspect_world_save_scope

It uses a separate allowlist rather than inheriting the existing readonly or landscape_smoke lists. The focused regression test checks the exact catalog and profile validation. Authentication logic was not intentionally changed. This result verifies Python-level declarations and tests only; it does not prove that a running native plugin and host agree on this catalog.

### StaticMesh inspector

The candidate inspection path avoids UStaticMesh::GetMeshDescription. It proposes using bounded CloneMeshDescription data when the relevant mesh-description data is already cached or the source bulk data is within the configured limit. It reports collision/body-setup information unavailable rather than calling an unsafe waiting accessor, and it marks references, external relationships, and complete save dependencies as incomplete where they cannot be proven.

The required disposable side-effect test was not run. Therefore the clone path has not been shown to preserve dirty flags, UObject identity, loaded-package inventory, or asset files. Geometry inspection must be considered unvalidated and not deployable. Before any future build/runtime use, gate geometry as unavailable until a disposable test proves the clone path does not mutate package or asset state. No mesh was loaded, built, compiled, saved, or inspected in an Editor during C0B.

### World save-scope inspector

The candidate implementation gathers bounded read-only evidence for the active world and persistent level; PIE state; World Partition initialization and descriptor/container information; streaming references; loaded external packages and package roots; map build-data; direct Asset Registry dependency evidence; and a hypothetical project-content destination. Its directory enumeration is bounded to 512 entries and 128 package files with a 0.5-second scan budget. It does not create destination directories, load missing assets, force Asset Registry completion, initialize World Partition, or claim a Save As is safe.

It reports evidence as observed, predicted, exact, or unknown where available, and it leaves Save As readiness blocked. This source is not compiled or runtime tested. World Partition metadata, invalid descriptors, streaming relationships, dependency completeness, and destination collision behavior therefore remain UNKNOWN for both the new project and A7K41.

## Validation results

| Gate | Result | Evidence and limits |
|---|---|---|
| Isolated source copy | PASS at copy time | 355 files / 8,214,630 bytes; manifest hash recorded above; no reparse points in copied source roots. |
| Disposable project and marker | PASS for setup | New C++ Blank project and explicit marker exist under the isolated root; no content assets were added. |
| Python focused regression tests | PASS | 92 passed across test_host_config.py, test_mcp_stdio.py, test_connections.py, test_security.py, and test_dirty_packages.py. The full repository test suite was not run. |
| Ruff | PASS | ruff check server tests scripts passed in the isolated source copy. |
| Python compilation | PASS | python -m compileall -q server tests scripts passed. |
| Authentication/session unit coverage | PASS at unit-test level | Included in the focused Python tests. No live authentication or session identity validation occurred. |
| Unreal Editor target build | FAIL before C++ compilation | UnrealBuildTool could not resolve module KitBash3dUsdTools, referenced via default plugin Cargo.uplugin; candidate C++ compilation was not reached. |
| Build/log isolation | FAIL | UnrealBuildTool wrote/reported a log under the user profile. No retry was made. |
| Native plugin registration/runtime | UNKNOWN / NOT RUN | No plugin binary was produced and no Editor was launched. |
| Dedicated host and private authentication | NOT RUN | No host was launched, no session registration or credentials were used, and no connection was attempted. |
| StaticMesh side-effect acceptance | NOT RUN | No native inspection operation was executed. |
| World/World Partition acceptance | NOT RUN | No native inspection operation was executed. |
| Destination collision/limit failure tests | NOT RUN | Python contract tests do not establish native filesystem behavior. |
| Before/after Editor/project integrity comparison | NOT RUN | The Editor and project inspection operations were never run. The disposable project has no Content assets; UBT may have produced Intermediate files. |
| A7K41 or production project access | NONE | No connection, process restart, file read, or modification was performed against A7K41 or production. |

## Yellow bridge indicator analysis

Offline source inspection of MajesticForgeModule.cpp verifies that the native status uses a six-second authenticated-activity window:

- IsForgeMcpConnected() is true only when the listener exists, at least one request authenticated, and the last authenticated request was no more than six seconds ago.
- With the listener present, an older authenticated timestamp produces the text “Connection interrupted” and an amber status dot.
- The timestamp is updated immediately after token validation, before request command validation and handler execution.
- The UI state reports bridge_running, connected, and interrupted as separate booleans.

Therefore yellow means the listener remains present but authenticated activity is older than six seconds. It does not establish that the host process crashed, that a request failed, or that the listener is unavailable. It also does not prove a client is still active. This is an offline source finding; no live UI was observed.

A later status-only change should expose separate states for listener availability, recent authenticated activity/age, and the last request outcome. An idle listener should be labeled listening/idle, not failed. Do not add artificial polling solely to keep the indicator green. This correction was not implemented or deployed in C0B.

## Preservation readiness

These are not fresh findings about the protected Editor. C0B did not connect to A7K41, so its current process, world, dirty packages, mesh object, and script-package state remain UNKNOWN.

- **SM_SM_ChamferCube:** C0A's historical evidence and plan remain the reference. C0B did not validate the in-memory object or save dependencies. No save is ready.
- **Entry world:** C0A's review found that Save As may re-home the active world, alter streaming references, load World Partition actors, save external packages and build data, and interact with destination-family files. The complete write scope remains unproven. **SAVE AS: BLOCKED.**
- **MediaPlate:** remains independently blocked under the historical evidence; C0B made no new observation and adds no exception.
- **SlateCore:** C0A's exact narrow disposable-only exception is not broadened. Its current eligibility in A7K41 is unknown and must be recomputed from a fresh complete snapshot before any future policy decision.

A successful disposable inspector test would not authorize saving protected A7K41 packages. If the complete write scope remains unprovable, preservation experiments belong in a new fully disposable project.

## Isolation breach and next gate

The build boundary did not pass. The out-of-root UnrealBuildTool log is an unexpected side effect. Its prior state is unknown, so this report makes no claim about whether it was newly created or changed. The log was left untouched. No Editor or host was started after discovering the boundary failure.

Before another build attempt, a separate bounded stage should:

1. Determine a supported UnrealBuildTool log-routing mechanism and verify, with a harmless no-build invocation, that the resulting log path is inside the isolated root.
2. Resolve the missing KitBash3dUsdTools module requirement in the disposable build configuration without changing the official engine installation.
3. Recheck all paths and hashes immediately before build, then compile only the disposable Editor target.
4. Proceed to disposable Editor/host tests only after both the build dependency and log-isolation gates pass.

Until then, the source changes are a draft in an isolated development copy, not a validated release candidate. No candidate artifact should be installed or used.

**Final disposition:** Python contract and lint checks passed; native compilation, authenticated runtime inspection, side-effect tests, World Partition checks, and destination tests are unverified or blocked. The log-isolation gate failed, so C0B stops here. A7K41 was not contacted. Production Phase 6C remains **NO-GO**.
