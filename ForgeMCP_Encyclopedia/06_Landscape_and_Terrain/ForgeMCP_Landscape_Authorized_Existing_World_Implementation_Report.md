# ForgeMCP — Authorized Existing-World Landscape Implementation

Date: 2026-10-22 UTC  
Scope: isolated source implementation and offline regression checks  
Disposition: **SOURCE IMPLEMENTED; PYTHON VALIDATION PASSED; NATIVE COMPILE AND LIVE EDITOR ACCEPTANCE NOT RUN. Not ready for a live Landscape operation.**

## Implementation result

The existing `create_in_place` contract now accepts an exact existing `/Game/...` world package path when World Partition is requested. The native path still requires a host-issued grant, exact active project and world identity, enabled World Partition editor support, no streaming sublevels, no pre-existing Landscape actor or proxy, no active Forge Landscape region loader, and a complete clean dirty-package preflight. A new Landscape is created flat and remains unsaved until a separate, explicit save preview/apply.

The new host-side grant is default-deny and is read only from the ForgeMCP host process environment variable `FORGE_LANDSCAPE_EXISTING_WORLD_AUTHORIZATION`. The typed MCP request has no authorization fields, and the wrapper creates the private native claim; callers cannot grant themselves access by adding a JSON field. The grant binds one `unreal-<PID>` session, one absolute `.uproject`, one exact `/Game/...` package path, a list of allowed Landscape operations, a unique 32-character authorization ID, and a UTC expiry no more than 24 hours away. Native code checks the grant against the active project and world and requires the requested action to be allowed.

Before a future live operation, the host owner must set a narrowly scoped grant. Its shape is:

```json
{
  "authorization_id": "<32 lowercase hexadecimal characters>",
  "session_id": "unreal-<current editor PID>",
  "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
  "world_path": "/Game/Levels/L_City_World_Master",
  "actions": ["create_in_place", "generate", "apply_heightmap", "raise", "lower", "flatten", "smooth", "coastline", "frame", "save"],
  "expires_at_utc": "<UTC ISO-8601 timestamp, within 24 hours>"
}
```

Do not configure this grant until a separately authorized operation has verified the current project, Editor PID/session, active map and dirty-package state. The grant is deliberately an explicit host configuration, not a client option. Every later edit still needs a fresh preview and one-use apply. The native instance also binds the grant ID to the GUID of the Landscape created under that grant; sculpting and saving another actor are rejected. A world transition or Landscape subsystem reset clears that in-memory binding.

The same scoped action grant supports flat creation followed by procedural generation, heightmap application, raise/lower/flatten/smooth/coastline operations, framing, and save. Existing component, sample, edit-chunk, and heightmap limits remain unchanged. The disposable-map `create` path and its existing save behavior remain available.

## Existing-world write protection

Preview checks the active project/world and records a fingerprint of the existing map package and files in that map's World Partition external actor and external object namespaces. Apply rechecks the grant, expiry, active world, Landscape absence, dirty-package inventory and package-scope fingerprint before creating anything. Existing-world creation does not save.

A separate authorized save first refuses unrelated dirty loaded packages, then backs up the existing map and all files found in the target map's external actor/object namespaces. The copies are size- and MD5-verified. The native save writes only the target world package and external packages owned by the new Landscape, then audits the enumerated namespace for unexpected changes or deletions and verifies Landscape height readback and clean target packages. Backups remain under `Saved/ForgeLandscape/<preview-or-job-id>` if saving or post-save validation fails. A partial native save is possible after a write begins; the backup is recovery material and no automatic rollback is claimed.

The scope audit is bounded to 10,000 files and 2 GiB. It is not a system-wide filesystem trace, and it does not prove the absence of incidental Engine/editor writes outside the enumerated package namespaces. If package enumeration, backup, dirty-state inspection, post-save write-scope validation, or height readback fails, the existing-world operation fails closed or reports a partial result and retains the backup.

## Source files changed for this task

| File | SHA-256 |
|---|---|
| `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.cpp` | `9BF9BC0E1554EA770AE0D57F522C9EF5D3387B911BBEA66D46C92DD32AFCC32B` |
| `Plugins/Forge/Source/MajesticForge/Private/ForgeLandscape.h` | `3B26AC3359F0C50FD08E712D587997FCA95F9E669F2834D10234A81F90A9DB51` |
| `server/core/landscape.py` | `9864524F785328A04AEF2F4361A2DA17D1EE8ABE9A03C929ACA1CBE61D80CC33` |
| `server/core/landscape_authorization.py` | `29DC919F83B66BB86C2C2E7232A59A8C5410934FBCE39F526F4431F2D228170D` |
| `server/main.py` | `4312B6D9C1C383F78CCC5297F811C3AC33779179F421B3BA79C5008EAB078D90` |
| `tests/test_landscape.py` | `75E79C51270AEBE0387DCEA28F9F79F7A77AB7EDC55C9CB7979BEC2EA5FC113C` |
| `tests/test_landscape_authorization.py` | `8A19803ACC6917C71F1D2EB79E71B8FA0AFAFFB1D8E944C5A87638D8D5EC4F7E` |
| `tests/test_landscape_authorization_tools.py` | `71F7339A1BD3ECFE56A9FAFDE9E7E95449B0678EEB832EEDB6FD207D9DAD24C4` |
| `tests/test_native_plugin_contract.py` | `6FE9F52D56753EE00CDDC5E52AC24DED2BCE653B6345405B902663B95188A7CB` |

The C0B R23 connection-consolidation files already present in the working tree were not changed by this Landscape task. No project asset, level, plugin binary, Engine configuration, or official Engine installation file was changed.

## Offline validation

- Focused Landscape, authorization, native-contract and dirty-package suite: **67 passed** in 9.15 seconds after the final contract assertions.
- Full Python suite: **510 passed** in 99.14 seconds on the final rerun (an earlier complete run also passed in 58.46 seconds).
- Ruff `check server tests scripts`: **PASS**.
- Python `compileall -q server tests scripts`: **PASS**.
- `git diff --check`: **PASS**.
- Read-only UE 5.6.1 header inspection confirmed the signatures used for `FPaths::IsRelative`, `FPaths::MakePathRelativeTo`, recursive file enumeration, package-name validation, `FDateTime::ToUnixTimestamp`, and `UPackage::SavePackage`.

The native contract tests inspect required source guards and save ordering; they do not replace compilation or an Editor runtime test. The initial focused run exposed a source-search assertion that selected the preview branch instead of the disposable apply branch; the assertion was anchored to the correct branch and the final focused suite passed. No C++ compile, plugin load, live Landscape preview/apply, asset save, or Editor operation was performed because this task expressly prohibits them.

## Activation requirements

The currently observed ForgeMCPDev project loads its project-local plugin binaries from `G:/ForgeMCP/Plugins/Forge/Binaries/Win64`. The changed native file belongs to the `MajesticForge` Editor module. The targeted build to perform later, after a separate build authorization, is the project Editor target against the official UE 5.6.1 installation:

```text
"G:\Program Files\EpicGames\UE_5.6\Engine\Build\BatchFiles\Build.bat" ForgeMCPDevEditor Win64 Development -Project="G:\ForgeMCP\ForgeMCPDev.uproject" -WaitMutex
```

This is a project Editor-target build that compiles the changed `MajesticForge` Editor module and required dependencies; it is not a full Engine rebuild. No build was started in this task. The currently loaded Editor cannot adopt a replaced native DLL safely in place: a cold Editor restart after a successful build is required. The Python host must also be restarted to load the updated `server` modules and any host-side grant configuration. Neither restart is authorized or performed here.

## Acceptance status and remaining blockers

The source path implements a default-deny existing-world workflow, but it is **not ready for a live operation**. The main blockers are:

1. The modified C++ has not been compiled against UE 5.6.1; header signature inspection alone cannot catch all compile or link errors.
2. Native preview/apply, World Partition external actor package saves, backup recovery, and post-save scope auditing have not been exercised in an Editor.
3. No current identity/registration/active-world/dirty-state check or explicit operation grant was made, and the production master level was not accessed.
4. The save path may return a partial result after native writes begin; retained backups support recovery but do not make multiple package saves atomic.

Before a separately authorized live operation, build the project Editor target, load the compiled project-local plugin after a cold Editor restart, restart the Python host, verify the exact session/project/map and complete dirty-package state, then configure a short-lived exact grant and begin with an authenticated preview. Production-level deployment or save should remain a separate explicit decision.

**Final verdict: SOURCE IMPLEMENTED; OFFLINE VALIDATION PASS; NATIVE COMPILE NOT VERIFIED; LIVE OPERATION NOT READY.** No live city-level change was made. Phase 6C remains **NO-GO**.
