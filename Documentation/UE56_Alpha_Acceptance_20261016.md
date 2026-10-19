# UE 5.6 engine-wide alpha acceptance — October 16, 2026

Plugin: **0.2.13-alpha.1** (descriptor version 16). External MCP server: **0.3.6**.
Target: **UE 5.6.1, Win64 Development Editor**, engine module BuildId **43139311**.
This records local alpha acceptance, not public publication or v1.0 completion.

## Package and installation

- Archive: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.1-UE5.6.1-Win64.zip`
- Archive size: 1,616,181 bytes; 50 entries including the manifest.
- SHA-256: `aca7db571041f34d2e679874d87aa42d3b448294a82e6e14bf62a25bdf4ec299`
- Installed at `G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\MajesticForge`.
- Receipt: `forge-install-receipt.json` inside the installed plugin. This was a
  fresh install; no prior engine copy required backup. No project files were edited
  by installation. The development project's local plugin was preserved.
- The packager verified source/config/resource byte equality with the isolated
  build, both module DLLs, source timestamps, engine BuildId and ZIP integrity.
  The installer independently verified the archive manifest and engine identity.

## Verification results

| Gate | Result | Evidence and scope |
| --- | --- | --- |
| Python suite | Passed | 335 tests, including real MCP stdio subprocess regression tests and four new engine-installer tests. |
| Python lint | Passed | Ruff on server, tests and changed Python packaging/install/verification helpers. |
| Installer safeguards | Passed in unit tests | Build mismatch rejection, existing-install protection, backup preservation, open-editor update rejection and restoration after simulated receipt failure. |
| PowerShell syntax | Passed | Build helper and engine installer wrapper parsed successfully. |
| Native compilation | Passed | Both plugin modules compiled and linked with the installed UE toolchain. |
| Full editor target | Passed | UnrealBuildTool completed all 28 actions for the disposable host's UnrealEditor target. |
| Engine installation | Passed | Validated archive installed into the engine's Marketplace plugin directory. |
| Fresh Blueprint-only project | Passed | No project-local plugin directory; loaded module path points to the engine installation. Loaded DLL bytes and reported plugin version match the archive. |
| Native bridge | Passed | Authenticated health, project identity, required capability checks and bounded editor-log inspection. |
| Live MCP subprocess | Passed | Real source stdio server initialized as ForgeMCP, registered 104 tools, discovered the connected test session and returned its correct project identity. |
| Visible UI, viewport and performance | Unverified | Acceptance used disposable NullRHI editors. No claim that all registered operations were exercised. |

The native launch log includes warnings about the disposable startup template's
external actor packages being outside a mounted directory. The recorded checks
passed; this is not a claim of a warning-free Unreal startup.

## Local evidence

- Isolated host: `Saved/AlphaValidation-20261016-01/HostProject`.
- Python output: `Saved/AlphaValidation-20261016-01/pytest.log`.
- Completed native build: `Saved/AlphaValidation-20261016-01/build-parallel.log`.
- Per-step compiler/linker logs: `Saved/AlphaValidation-20261016-01/HostProject/Saved/ForgeBuild`.
- Initial engine-load check: `Saved/UnrealPackageAcceptance-4d43eb1a9e714b469494645deda912db/acceptance.json`.
- Engine-load and real MCP check: `Saved/UnrealPackageAcceptance-d2fa565a7fb24586982fdd697cbf826f/acceptance.json`.

In engine mode, the verifier's legacy `installer_verified` field is false because
that script does not invoke the project-local installer. Engine installation was
performed separately with `Install-ForgeUnrealEngine.ps1`; its receipt and the
subsequent loaded engine DLL establish that separate gate.

The installed Cargo plugin lacked the `KitBash3dUsdTools` build definition.
The first isolated build failed on that unrelated engine plugin. Validation then
used `-DisablePlugin Cargo`; Cargo's files and preferences were not changed. The
initial serial compile was superseded by the completed bounded parallel build.
Only processes belonging to the disposable build were stopped or reprioritized.
The user's ForgeMCPDev editor remained running and was inspected read-only.

## Remaining acceptance

Open a chosen UE 5.6.1 project, enable ForgeMCP, restart, and inspect **Window >
ForgeMCP** visibly. Confirm the alpha version and the target project's identity.
Projects with a local MajesticForge copy need deliberate migration before relying
on the engine copy. External MCP discovery still uses the selected project's
`Saved/MajesticForge` directory. Other engine builds/platforms, packaged games,
all-feature workflows and performance need separate acceptance.

See [alpha setup and rollback](UE56_Alpha.md) and the continuing roadmap for the
next feature increments. Session registration files are private credentials and
are excluded from the archive and this evidence document.
