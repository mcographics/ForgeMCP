# ForgeMCP Coordinated Release Candidate — October 20, 2026

Status: **Local release candidates built and validated in bounded tests. Not installed into either existing Unreal Editor or the user's Blender profile.** Phase 6C remains **NO-GO**.

## Component changes

| Component | Candidate | Changes |
|---|---|---|
| ForgeMCP core | `0.3.14` | Adds an explicit isolated-host policy with private session roots, exact session allowlisting, pinned process identity checks, and typed dirty-package inventory requests with stable snapshot paging. Existing inspection and connection flows remain in place. |
| Unreal Editor plugin | `0.2.14-alpha.3` | Uses the active plugin source as its baseline, retains the existing Landscape operation slice, and adds the native loaded-package dirty observer. Landscape jobs report staged height readback; Complex collision validation is deferred until save/reload and then checked separately. |
| Blender add-on | `0.2.36-alpha.1` | Exposes explicit bridge protocol and transfer-contract versions in authenticated health data and the connection panel while retaining the current transfer workflow. |

The dirty-package observer runs on the Editor game thread and reads `UPackage::IsDirty()` across loaded packages. Its snapshot and paging are stable for one inventory request. It does not cover unloaded packages or non-package transient state, and its package/actor association fields can remain unresolved. Consumers must treat unresolved rows as a preservation stop condition rather than infer that the Editor is clean.

## Release artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Artifacts/majestic_forge_mcp-0.3.14-py3-none-any.whl` | 89,076 bytes | `219bd24b184779905649a38c0eb24ae7f99c8af4423ae9109a41350704f53ab1` |
| `Artifacts/ForgeMCP-Unreal-Alpha-0.2.14-alpha.3-UE5.6.1-Win64.zip` | 3,254,336 bytes | `88aec55c3dd529e832f46bc2ee4456eb3de58b663cc4fccf1df715b2a0682dfd` |
| `Artifacts/ForgeMCP-Blender-Addon-0.2.36-alpha.1.zip` | 647,684 bytes | `acf0b50089e36c1431ade45d73e3a390a1694ebd3d5c9f9a7c94e7f7f25896c8` |

The Python wheel build exposed a missing `wheel` build requirement. `pyproject.toml` now declares it explicitly; the wheel was built successfully with the local build environment.

## Verification

- Python tests: **469 passed** using `python -m pytest -q`.
- Ruff: **passed** for the repository after correcting an existing import-order violation in `scripts/verify_unreal_package.py`.
- Python bytecode compilation: **passed** for `server`, `tests`, `scripts`, and the Blender add-on source.
- Blender package: **passed** clean-profile installation, enable/disable, protocol/authentication and transfer acceptance on Blender 5.2.2 LTS, with nine acceptance markers. The test used a private temporary profile and did not alter the user's Blender profile or scene.
- Unreal plugin: the Editor target compiled and linked (33/33 actions). The full Unreal Automation Tool `BuildPlugin` pipeline did not complete: its `UnrealGame` target stopped because the installed engine lacks the `BuildSettings.precompiled` manifest. This is an engine packaging limitation; it is not reported as a successful full `BuildPlugin` run.
- Packaged plugin runtime: **passed** in a fresh disposable, private-session Unreal project. The isolated host authenticated to that one process, reported `inspect_dirty_packages`, exercised Landscape create/edit/generate/coastline/heightmap/save/reload/cancel flows, and verified the loaded DLL path and SHA-256 matched the release package. The disposable Editor exited cleanly.

The Landscape acceptance used `-NullRHI`, so it does not prove interactive viewport appearance. It used a small non-World-Partition test level and does not close the World Partition, city-scale, performance, or full coastline-collision gates.

The observer returned a complete loaded-package enumeration in the disposable test, but one dirty `/Script/SlateCore` package had `classification_complete: false` and truncated associated objects. This is reported as unresolved observer output; it is not evidence about the user's existing Editor. The observer therefore improves visibility but does not establish a general restart-safe inventory.

## Safety and next gate

The release test used a newly created disposable project, a private registry/session root, and a dedicated isolated host. No existing production or saved isolated Editor was contacted, changed, restarted, or deployed to. No city assets or source project files were edited by the Landscape test. The existing active Editor's in-memory state remains outside these release artifacts.

These packages are local alpha candidates, not a production deployment or Phase 6C acceptance. Before using them in the city project, preserve and review the current Editor state, separately authorize the exact isolated deployment target, and verify the observer's unresolved package rows. Continue to keep maps, World Partition packages, plugin source, configuration, autosaves, and recovery files in scope. Do not treat a passing disposable smoke test as proof of city-scale or complete project-state preservation.
