# ForgeMCP A7K-38 Revalidation — Classification and Disposable Landscape Acceptance

Date: 2026-10-21 (America/Toronto)  
Project: `G:\ForgeMCP`  
Engine target: Unreal Engine 5.6.1  
Phase 6C: **NO-GO**  
Disposition: **A7K-38 candidate and recorded disposable acceptance remain validated; interactive viewport acceptance is still unverified.**

## Scope and current work

The existing [A7K-38 validation report](ForgeMCP_A7K38_Dirty_Package_Classification_Validation_2026-10-21.md) already records the classification repair, native policy tests, a private disposable World Partition Landscape runtime acceptance, and a 44-path write audit with zero out-of-scope paths. This revalidation did not repeat Apply or modify any Landscape map.

A fresh regression run exposed six source-contract test failures because `tests/test_native_plugin_contract.py` expected a canonical `Plugins/Forge` tree that was absent; the candidate source existed only in ignored stage copies under `Saved`. I restored the validated A7K-38 plugin source into the repository's expected `Plugins/Forge` location. The 59 copied source, descriptor, config, license, and resource files each matched both the A7K-38 stage source and the corresponding entry in the candidate archive. No plugin binaries were copied. The candidate archive and the existing saved acceptance project were not modified.

## Observer classification and policy

The earlier completeness defect combined ownership-scan completeness with display-sample truncation. The repaired observer reports those separately. It scans the package's associated objects up to 100,000 objects and caps the returned display sample at four. Reaching the full-scan limit leaves classification incomplete and blocking; truncating only the sample remains visible without claiming an incomplete ownership scan.

The A7K-38 runtime evidence reports `/Script/SlateCore` as an engine script package using Unreal script-package metadata, the compiled-in package flag, and verified engine-module provenance. Its ownership scan covered 116 objects, found zero actor/external-actor associations, and determined it was not associated with the current world. The four-item display sample was truncated. The row remained visible and was admitted only by the exact disposable-only exception; it was not relabeled clean.

All dirty project content, current-world packages, external actors, unknown classifications, unresolved ownership, incomplete scans, and incomplete snapshots continue to block Apply. The exception is limited to exact `/Script/SlateCore` in a marked disposable project and requires complete classification and ownership evidence, safe package flags, no transient state, zero actor associations, and a determined non-current-world result. This does not establish that unloaded packages or non-package transient Editor state are clean.

## Current verification

| Check | Current result |
|---|---|
| Python regression suite | **483 passed** in 50.47 seconds using the repository `.venv` |
| Ruff (`server tests scripts blender-addon`) | **Passed** |
| Python bytecode compilation | **Passed** |
| `git diff --check` | **Passed**; Git printed existing LF-to-CRLF conversion warnings for unrelated modified scripts |
| Unreal Editor target | **Succeeded**, `ForgeMCPA7K38CompileEditor Win64 Development`; this revalidation was incremental and executed one `WriteMetadata` action because C++ outputs were already current |
| Prior A7K-38 native C++ build | Existing A7K-38 report records success |
| Prior native automation | Existing A7K-38 report records **2/2 passed**: disposable exception policy and native preview fail-closed |
| Candidate artifact identity | Current SHA-256 values match the A7K-38 report |

The candidate artifacts are:

| Artifact | Version | Size | SHA-256 |
|---|---|---:|---|
| `Artifacts/A7K38-Classification-20261020/majestic_forge_mcp-0.3.15-py3-none-any.whl` | Core 0.3.15 | 89,776 bytes | `9159465283832F467E43E1F9C9AEFB038BA193E9F11F06F651E35A10D15752B1` |
| `Artifacts/A7K38-Classification-20261020/ForgeMCP-Unreal-Alpha-0.2.16-alpha.1-UE5.6.1-Win64.zip` | Plugin 0.2.16-alpha.1 | 3,298,407 bytes | `FE34EFEBEEADEDD02ECF8E1BA8980A42F1450F6F27105FFAAEBBB46FA800D735` |

No install or deployment occurred.

## Disposable Landscape acceptance evidence

The existing A7K-38 report records a fresh private runtime project, authenticated isolated host, core 0.3.15, and plugin 0.2.16-alpha.1. Its test map was `/Game/ForgeMCPTests/Landscape/L_A7K38_WP_f045e636`, with 2x2 components, 63 quads per section, 100 cm XY scale, Engine BasicShape material, and World Partition enabled. The saved/reloaded Landscape reported 127x127 vertices, four Landscape components, four collision components, and one loaded external streaming proxy. Height-data persistence and post-reload collision checks passed, along with raise/lower/flatten/smooth test operations.

That run used `-NullRHI`; it proves the reported native and persistence behavior, not interactive viewport appearance, rendered material quality, or human-observed sculpting. The report's filesystem audit recorded 44 additions/changes and zero paths outside its declared disposable write scope. It also records rejection-before-Apply checks for an out-of-scope map path, an existing map destination, an existing predicted HLOD destination, and an existing WorldState destination. Native policy tests covered dirty project-map, external-actor, unknown, and incomplete-evidence blockers.

## Files and services affected in this revalidation

Created `Plugins/Forge` with 59 source/config/resource files from the validated candidate; no binary was copied. Existing source files elsewhere in the working tree, the A7K-29 baseline, A7K-38 acceptance project, candidate artifacts, existing Unreal installations, Blender profile, `server.main` processes, production project, and `L_City_World_Master` were not changed. The compile command wrote only to the stage-scoped A7K-38 compile project. A passive process check found no `UnrealEditor.exe` or `CrashReportClientEditor.exe` process at the end of the checks.

## Remaining risks and decision

The engine cannot completely pre-fence every possible `SaveLevel` side effect. The filesystem audit is post-operation detection rather than prevention, so Landscape creation remains limited to a marked disposable project with bounded destinations and no promise of full rollback. The observer covers loaded `UPackage` objects only. The A7K-38 result does not authorize deployment to an existing Editor, does not establish restart readiness, and does not close city-scale, interactive viewport, or production World Partition acceptance.

**Recommendation:** the classification repair and headless disposable acceptance are validated for the A7K-38 candidate. Keep Phase 6C **NO-GO**. Require a separately authorized interactive viewport acceptance in a fresh disposable project before claiming visual Landscape acceptance or production readiness.
