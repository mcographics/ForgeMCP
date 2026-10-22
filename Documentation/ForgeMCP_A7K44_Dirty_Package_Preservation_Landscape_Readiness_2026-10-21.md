# ForgeMCP Stage A7K44 — Dirty-Package Preservation and Landscape Readiness

Date: 2026-10-21  
Project: `G:\ForgeMCP\Saved\LandscapeDevelopment\A7K41_CleanLandscape_20261021\A7K41_CleanLandscape.uproject`  
Engine: Unreal Engine 5.6.1  
Phase 6C: **NO-GO for production**  
Disposition: **Read-only inspection complete. No package was saved or discarded; no recovery file was copied or restored; no map was created; no Landscape Apply was run.**

## 1. Result

Fresh process and private-session checks passed. One dedicated `server.isolated_host` process authenticated to `unreal-15144` using core 0.3.15 and the read-only tool profile. The active world remained `/Engine/Maps/Entry.Entry`; PIE was stopped before and after inspection. A single immutable inventory page reported 1,068 loaded packages and four dirty packages, with a complete scan and no observer errors.

The Entry map asterisk corresponds to a currently dirty map package. The dirty list is:

- `/Engine/Maps/Entry`
- `/Game/LevelPrototyping/Meshes/SM_SM_ChamferCube`
- `/Script/MediaPlate`
- `/Script/SlateCore`

The exact SlateCore row meets the existing narrow disposable-only exception predicates. That exception is eligibility under the existing policy; it does not clear the dirty flag. Entry, the newly-created project mesh, and MediaPlate remain Apply blockers. The SlateCore exception does not make the inventory clean or override those blockers.

A targeted evidence bundle is prepared below but was **not copied**. Landscape Apply remains **NO-GO**.

## 2. Fresh Editor and private-session identity

Passive checks immediately before the dedicated host found:

| Check | Fresh result |
|---|---|
| PID / owner | `15144` / `Kenne` |
| Process start UTC | `2026-10-21T05:32:11.2726000Z`; exact tick match to the supplied pin |
| Executable | `G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe` |
| Exact project argument | `G:\ForgeMCP\Saved\LandscapeDevelopment\A7K41_CleanLandscape_20261021\A7K41_CleanLandscape.uproject`; exact argument-token check passed |
| Other UnrealEditor processes | None at the preflight snapshot |
| Private listener | One listener at `127.0.0.1:60688`, owned by PID 15144; no non-loopback bind was observed |
| Registration metadata | One Unreal registration named `unreal-15144.json`; safe fields match session `unreal-15144`, host `127.0.0.1`, port 60688 and PID 15144; no Blender registration |
| Private-root ACL | Restricted to SYSTEM, Administrators and the current user; no broad principal was found |
| Disposable marker | `Saved\ForgeMCPDisposableProject.json` exists and names the exact A7K41 project |
| Existing isolated hosts | None before the run |

No credential value was emitted. The dedicated host was configured with exactly one allowed session, pinned PID, start time, executable, project and expected level; it used the private registration root and no shared-session fallback.

The project descriptor enables `MajesticForge`. The active project-local descriptor is `Plugins\Forge\MajesticForge.uplugin`, VersionName `0.2.16-alpha.1`, EngineVersion `5.6.0`, with Runtime and Editor modules. The loaded modules mapped from the project-local plugin directory:

| Loaded module path | On-disk SHA-256 |
|---|---|
| `...\A7K41_CleanLandscape_20261021\Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.dll` | `297427727F3EEA60419E8CCCBD37289DE534FCE2FFA2D7CFB0D3FA6F070D20DF` |
| `...\A7K41_CleanLandscape_20261021\Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.dll` | `DA58F75E596F91BE0ED798185686179E89ED2C1063AE1B64D9F12D8F626F0BAB` |

These are hashes of the files at the mapped paths; process metadata does not fingerprint the exact in-memory image bytes.

The runtime host reported ForgeMCP core **0.3.15**, plugin **0.2.16-alpha.1**, and engine build `5.6.1-44394996+++UE5+Release-5.6`. The dedicated host reported `read_only: true` and exposed 12 tools; it did not expose save/apply tools. The native health response separately advertises the plugin's broader native capabilities and reports `read_only: false`; the host restriction is the boundary used for this inspection. `forge_list_sessions` was present in the catalog but was not called. No broad discovery was performed.

After the stdio client ended, PID 15144, its listener and start time still matched; no `server.isolated_host` process remained. The session’s last-authenticated activity telemetry and diagnostic logs can change during authenticated reads.

## 3. Current world and complete dirty inventory

Authenticated `unreal_project_info` returned the same result before and after the inventory:

- Project: `A7K41_CleanLandscape`
- Project path: exact A7K41 `.uproject`
- Current level: `/Engine/Maps/Entry.Entry`
- PIE: `false`

The observer returned one page at limit 50, offset 0:

| Inventory field | Result |
|---|---|
| Snapshot ID / compatibility inventory ID | `075803D641667192AAFFF5BC76B1571C` |
| Packages inspected | 1,068 |
| Dirty packages observed / total | 4 / 4 |
| Returned rows / next page | 4 / none |
| Inventory complete | Yes |
| Snapshot cap reached | No |
| Inspection errors | None |
| Duplicate or missing rows | None in the single returned page |
| Snapshot timestamp | Not included in the native response |

The scan covers loaded `UPackage` objects in the current Editor process. It does not classify unloaded packages or non-package transient state as clean. The missing observer timestamp is recorded as an output limitation.

### Dirty rows

| Package | Current evidence | Preservation and policy result |
|---|---|---|
| `/Engine/Maps/Entry` | Dirty; current-world category, engine-content domain; `package_contains_map=true`; package itself is the active level. Ownership scan complete; three objects scanned (`Polys_1`, `Entry` UWorld, `Model2`); no actor or external-actor association. | **Blocks Apply.** The observer field `associated_with_current_level=false` describes actor/object association; it does not negate `is_current_level_package=true`. The active package is dirty. The user-visible asterisk is consistent with this `IsDirty()` result. |
| `/Game/LevelPrototyping/Meshes/SM_SM_ChamferCube` | Dirty project-content package; `package_newly_created=true`; complete classification and ownership scan; one `/Script/Engine.StaticMesh` object; no actor/current-world association. The exact project `.uasset` path is absent; its Auto1 file exists. | **Blocks Apply.** The loaded package contains unsaved StaticMesh state. The available evidence does not reveal its author, geometry values, or complete recoverability. |
| `/Script/MediaPlate` | Dirty, compiled-in engine-script package with verified engine-module provenance. Ten objects were scanned and ownership scan completed; only four object rows were returned, so the display sample is truncated. The actor-association field reports `/Script/MediaPlate.Default__MediaPlate`, a class default object path, not evidence of a placed level actor. No current-world association was reported. | **Blocks Apply.** The package is not the exact SlateCore exception. The scan is complete, but the sample is incomplete; the reason for its dirty bit remains unknown. Do not save or whitelist it. |
| `/Script/SlateCore` | Dirty, compiled-in engine-script package with verified engine-module provenance. 116 objects scanned; ownership scan complete; the four-row display sample is truncated; zero actor associations and no current-world association. | **Eligible only for the existing exact disposable-only exception.** It remains dirty. No exception was applied to or used to clear the package. |

For both engine-script rows, `belongs_to_test_project=true` appears alongside `package_domain=engine_script` and verified compiled-in engine-module provenance. That membership field is internally inconsistent with the domain and was not used to widen any exception.

## 4. Entry and ChamferCube disk evidence

The current recovery index is valid UTF-16LE JSON without a BOM, 802 bytes, SHA-256 `75555E7A3D000EFD2B8B96BAD537A462B10F7A181E7890585767505D091AFE94`. It has `RestoreEnabled: true` and two entries:

- `/Engine/Maps/Entry` -> `Engine/Maps/Entry_Auto1.umap`
- `/Game/LevelPrototyping/Meshes/SM_SM_ChamferCube` -> `Game/LevelPrototyping/Meshes/SM_SM_ChamferCube_Auto1.uasset`

| Artifact | Exact current evidence |
|---|---|
| Entry Auto1 | `Saved\Autosaves\Engine\Maps\Entry_Auto1.umap`; 28,546 bytes; last write `2026-10-21T05:44:00.8534832Z`; SHA-256 `006E7D122CB54D4C00558E08B9A2D92E8AEDDECCC8DE5F62826F4FC1A56713EB` |
| Installed Engine Entry map | `G:\Program Files\EpicGames\UE_5.6\Engine\Content\Maps\Entry.umap`; 28,347 bytes; last write `2025-06-04T04:31:56.3068126Z`; SHA-256 `1078B5079D8FF41BF250EB652BA5D6A851FBEAD9B09C69341CF4D77C0A83158A` |
| Dirty SM_SM Auto1 | `Saved\Autosaves\Game\LevelPrototyping\Meshes\SM_SM_ChamferCube_Auto1.uasset`; 125,595 bytes; last write `2026-10-21T05:44:01.0819854Z`; SHA-256 `D0826BAB5BEEA84DC415E0275CE99806D41986D824C12B014938679F987EB172` |
| Dirty SM_SM saved counterpart | `Content\LevelPrototyping\Meshes\SM_SM_ChamferCube.uasset` is absent. |
| Separate saved SM_ChamferCube | `Content\LevelPrototyping\Meshes\SM_ChamferCube.uasset`; 121,486 bytes; last write `2026-10-21T05:35:15.7869831Z`; SHA-256 `40181A9F7B7F5246961BB2AEF6ED4BBBA9B36B6CBFE1D20713640BC6F3AFF19D` |

The Entry Auto1 and installed Engine Entry map have different sizes and SHA-256 hashes. This verifies a serialized byte difference; it does **not** identify which fields differ or prove that the difference is user-authored rather than initialization, serialization-version, or other Editor state. The restore index directly points to the Entry Auto1, so it is relevant evidence, not proof that every current in-memory change is recoverable.

The two ChamferCube package names are distinct. The SM_SM package is a newly-created in-memory package with a StaticMesh object and a matching Auto1 reference; its normal project-content file is absent. The separate `SM_ChamferCube` asset is a saved package with a different package name. The Editor log records a build for `SM_SM_ChamferCube`, a separate save/reimport for `SM_ChamferCube` from its own FBX, and the SM_SM Auto1 write. This does not prove the origin or full mesh/build data of SM_SM. The normal `SM_ChamferCube.uasset` must not be used as a replacement.

Current `Saved\SourceControl\UncontrolledChangelists.json` is valid JSON, 1,637 bytes, last write `2026-10-21T05:35:16.2029837Z`, SHA-256 `AA097B53F9515FD633A99339BCA9E357B30DD61AC699E365CA63FB311B0B6E36`. It has ten file paths, including the separate saved `SM_ChamferCube.uasset`, and no Entry or SM_SM_ChamferCube path. This is bookkeeping evidence only; it does not prove a source-control submission or explain the dirty package.

## 5. Entry asterisk and startup evidence

`Config\DefaultEngine.ini` is 1,612 bytes, SHA-256 `EF962AA47C5AC01E839B40F9C6307BD0CE657FBAD0480C4CAEA33D18244A68B8`. Both `GameDefaultMap` and `EditorStartupMap` are `/Engine/Maps/Entry`. The project descriptor enables `MajesticForge`.

The fresh inventory confirms the active Entry map package is dirty now, unlike an older snapshot that omitted it. The snapshots differ in time; the current one is authoritative for this run. The log records PIE creation from Entry at `2026-10-21 05:40:46Z` and later autosaves for Entry and SM_SM_ChamferCube at approximately `05:44:00Z`. These events do not establish that PIE, ForgeMCP initialization, or template initialization caused the Entry dirty flag. No read-only evidence identifies the specific changed map properties or newly created objects. The state may include unsaved user data, so it must be treated as preservation-sensitive.

## 6. MediaPlate and SlateCore assessment

The native observer provides authoritative engine-script provenance when the package is compiled in and its owning module resolves to a loaded Engine module; both current rows report that evidence. Ownership scan completeness and sample truncation are separate fields:

- MediaPlate: full ownership scan of ten objects; only four names displayed. One actor-association path is the class default object `Default__MediaPlate`, not a placed actor. The dirty reason is unknown and no exemption applies.
- SlateCore: full ownership scan of 116 objects; four names displayed. No actor or current-world association was found. The existing exception’s exact-path, category, provenance, complete-classification, complete-ownership, current-world, actor/external-actor, compiled-in and unsafe-package-flag predicates are satisfied for this row in this disposable project.

Neither package was saved, cleaned, or altered. MediaPlate remains a blocker. No policy change is needed to preserve fail-closed behavior; changing the Landscape implementation to suppress MediaPlate would be unsafe and is not proposed.

## 7. Targeted preservation bundle — proposed, not executed

Proposed collision-resistant destination (outside the A7K41 project and verified absent):

`G:\ForgeMCP\Saved\LandscapeDevelopment\A7K44-A7K41-Preservation-20261021T170005Z-eccd05fcb94746ec8f0b72341b86f862`

The exact nine-file scope totals **521,348 bytes** at this check:

| # | Source relative to A7K41 project | Size | SHA-256 | Role |
|---:|---|---:|---|---|
| 1 | `Saved\Autosaves\Engine\Maps\Entry_Auto1.umap` | 28,546 | `006E7D122CB54D4C00558E08B9A2D92E8AEDDECCC8DE5F62826F4FC1A56713EB` | Entry recovery evidence |
| 2 | `Saved\Autosaves\Game\LevelPrototyping\Meshes\SM_SM_ChamferCube_Auto1.uasset` | 125,595 | `D0826BAB5BEEA84DC415E0275CE99806D41986D824C12B014938679F987EB172` | Dirty mesh recovery evidence |
| 3 | `Saved\Autosaves\PackageRestoreData.json` | 802 | `75555E7A3D000EFD2B8B96BAD537A462B10F7A181E7890585767505D091AFE94` | Current pointers to both Auto1 files |
| 4 | `A7K41_CleanLandscape.uproject` | 452 | `BE5646BADD87789669C2F3ED0221567D6FE72296A8917E62A837EE4D27269164` | Project and enabled-plugin configuration |
| 5 | `Config\DefaultEngine.ini` | 1,612 | `EF962AA47C5AC01E839B40F9C6307BD0CE657FBAD0480C4CAEA33D18244A68B8` | Startup-map configuration |
| 6 | `Plugins\Forge\MajesticForge.uplugin` | 926 | `55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07` | Project-local plugin descriptor |
| 7 | `Saved\Logs\A7K41_CleanLandscape.log` | 240,292 | `06D7D25B5503FC540D76BE74024A82D24E036AED978C4292B0DF03B92C4F7B15` | Relevant diagnostic log; hash read with sharing and stable size/mtime during that read |
| 8 | `Saved\SourceControl\UncontrolledChangelists.json` | 1,637 | `AA097B53F9515FD633A99339BCA9E357B30DD61AC699E365CA63FB311B0B6E36` | Shows which separate saved assets are listed |
| 9 | `Content\LevelPrototyping\Meshes\SM_ChamferCube.uasset` | 121,486 | `40181A9F7B7F5246961BB2AEF6ED4BBBA9B36B6CBFE1D20713640BC6F3AFF19D` | Comparison evidence only; not a substitute for SM_SM |

On approval, the copy procedure should create the destination exclusively, preserve these relative paths under a clearly named evidence root, and write a manifest containing each original full path, relative path, size, last-write UTC, SHA-256, destination path and result. Hash every source immediately before copy; copy only these nine files; verify destination count, size and SHA-256; then rehash sources. Stop on any collision, change, mismatch, copy error or extra destination file. The live log can continue changing, so any changed log hash during the approved copy must stop the operation. Do not modify the originals or restore either Auto1.

This location is on the same G: volume and host. It reduces the risk of a change to the A7K41 path but is not off-volume protection. No bundle or destination directory was created in this stage.

The active Editor log grew by 336 bytes between the pre-host metadata check (239,956 bytes at 2026-10-21T16:50:27.7727530Z) and the post-host measurement (240,292 bytes at 2026-10-21T16:56:25.2128374Z). It remained stable while its current hash was calculated. This is consistent with diagnostic activity during the observation window, but the increment cannot be attributed to host requests alone. A zero-byte log at G:\ForgeMCP\Saved\LandscapeDevelopment\PrivateSessions\A7K41_CleanLandscape_20261021_ac6030d3924141b4ab3c492edf83f610\logs\server-7920.log (last-write UTC 2026-10-21T16:57:10.2294397Z) was present after the host run; its timestamp is consistent with the run, but no pre-run directory manifest was captured, so whether it was newly created or touched cannot be proven.

## 8. Landscape destination and existing write policy

The proposed map destination, not specified by the user and therefore only a candidate, is:

`/Game/ForgeMCPTests/Landscape/L_A7K44_Interactive_WP_20261021_01`

Its corresponding `Content\ForgeMCPTests\Landscape\L_A7K44_Interactive_WP_20261021_01.umap` file and parent directory were absent at inspection. No map or preview was created.

Source review of `ForgeLandscape.cpp` and `ForgeDirtyPackages.cpp` shows that create preview:

- Requires an absent disposable test-map package and checks that the map, external-actor and external-object roots, predicted HLOD packages, and target WorldState file are absent.
- Reports exact deterministic map, HLOD and WorldState destinations, while external-actor and external-object outputs are allowed namespaces rather than guessed exact filenames.
- Lists expected auxiliary categories including autosave/restore metadata, uncontrolled-changelist bookkeeping, logs, per-project Editor settings, WorldState, and explicit ForgeLandscape backup payloads.
- Checks dirty inventory completeness and package policy, disposable-project status, and World Partition Editor readiness before setting `apply_allowed`.
- Requires matching preview confirmation for Apply. The implementation creates a new active Editor world before serializing the target map, so that world transition itself is a consequential Editor-state change even before Landscape package serialization.
- Keeps post-operation auditing separate from prevention; a file audit would detect an unexpected write after it happened.

The dedicated read-only host did not expose `landscape_preview`, so no live typed preview or exact per-run write set was produced. No Apply or map transition was attempted. The current dirty Entry package, SM_SM project content, and MediaPlate package fail the existing policy; the complete inventory and exact SlateCore exception do not override them. These preservation blockers can be addressed without changing the Landscape implementation only if the user makes explicit package-preservation decisions and MediaPlate ceases to be dirty or is resolved under a separately reviewed policy. This stage establishes no such resolution.

## 9. Separate preservation options

### Option A — Keep current work

1. Separately authorize and verify the nine-file evidence bundle first.
2. Preserve the dirty Entry world by a user-reviewed **Save Current Level As** to a new, confirmed-absent project path (candidate: `/Game/ForgeMCPTests/Preservation/L_A7K44_Entry_20261021_01`). Do not save the current Engine map in place under `/Engine/Maps/Entry`. Stop on any unexpected prompt or package.
3. Separately authorize saving only the exact dirty StaticMesh package `/Game/LevelPrototyping/Meshes/SM_SM_ChamferCube` to its currently absent `Content\LevelPrototyping\Meshes\SM_SM_ChamferCube.uasset` path, if the UI can select that exact in-memory asset. Do not substitute, overwrite or consolidate `SM_ChamferCube`.
4. Re-inventory after the individually approved operations. Do not save `/Script/MediaPlate` or `/Script/SlateCore`.

These writes may serialize only the exact objects Unreal saves. The Auto1 files preserve useful disk evidence but do not prove they contain the latest or complete in-memory state. MediaPlate remains a Landscape Apply blocker unless its dirty state is separately understood and safely resolved.

### Option B — Discard disposable in-memory changes through a controlled reset

1. Separately authorize a graceful user-supervised exit without saving only after the evidence bundle verifies.
2. If Unreal presents a save/recovery prompt, stop until the user reviews the exact package list and choices. Do not delete or clear Auto1 or restore metadata.
3. If the user explicitly chooses to discard, the in-memory changes in Entry and the newly-created SM_SM mesh may be lost; the script-package dirty state and other transient/session state may also be lost. The retained Auto1 files may offer recovery evidence, but recovery is not guaranteed.
4. Reopen only the disposable A7K41 project under its private session and rerun the complete inventory. A fresh launch is not proof that MediaPlate will be clean; stop if any blocking dirty row remains.

Neither option is authorized here. Neither guarantees preservation of arbitrary non-package Editor memory.

## 10. Files/services affected, unknowns and next approval

No write operation targeted A7K29, ForgeMCPDev, production city, the Blender profile, project assets, or recovery files. No plugin binary was replaced. No save, discard, restore, copy, restart, Landscape preview or Apply was issued. Hashes for the named autosaves, saved mesh, recovery index, project descriptor, startup config, plugin descriptor and source-control metadata matched their pre-host measurements. The active Editor log grew as described above. The dedicated isolated host exited; the Editor was left running.

Remaining unknowns:

- Exact fields represented by Entry's different Auto1 bytes, and whether those differences are user-authored.
- Whether the SM_SM Auto1 fully contains the desired mesh geometry/build data and who created the package.
- Why MediaPlate is dirty, why its CDO is reported in the actor-association field, and whether any unreturned objects affect preservation.
- Whether SlateCore remains eligible at a future Apply time; predicates must be re-evaluated from a fresh inventory.
- Whether the current Entry map is World Partition-enabled. A prior inspection reported it was not, but this was not freshly queried in A7K44; this does not affect the current dirty-package NO-GO.
- Any unloaded-package or non-package transient state outside the observer's scope.

**Recommended fastest safe path:** authorize the exact nine-file, hash-verified evidence bundle first. Then choose Option A or B for the two project packages. Re-inventory after that decision. Do not authorize Landscape Apply until Entry, SM_SM_ChamferCube and MediaPlate no longer block the existing policy and a fresh read-only preview confirms the exact allowed scope. No Landscape implementation change is recommended to bypass the present blockers.

The next approval required is specifically for the nine-file copy to the absent destination above. This report does not authorize saving, discarding, restart, or Landscape Apply.

**Final disposition: bridge and inventory PASS for bounded read-only diagnostics; dirty-package preservation unresolved; Landscape Apply NO-GO; Phase 6C remains NO-GO.**

