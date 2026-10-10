# Milestone 1 validation — October 9, 2026

Implemented version: 0.1.0. The original roadmap remains a planning document; this
record describes work actually exercised in this checkout.

| Check | Evidence |
| --- | --- |
| Unreal plugin compilation | ForgeMCPDevEditor / Win64 / Development, UE 5.6.1: `Result: Succeeded`; original plugin DLL linked |
| Automated server tests | 14 passed, including a real MCP subprocess handshake and all five tool schemas/results |
| Python lint | Ruff check passed for server, add-on, scripts, and tests |
| Live MCP tool calls | All five tools returned successful structured results through SDK stdio client |
| Unreal inspection | Separate editor process, null renderer; actual project `ForgeMCPDev`, UE 5.6.1, editor world `/Temp/Untitled_1.Untitled_1` |
| Actor inspection | 144 loaded actors; requested sample limit 10 correctly reported `truncated: true` |
| Blender inspection | Separate factory-startup background Blender 5.2.2 LTS process; scene `Scene`, 3 objects, 24 FPS |
| Live rejection probes | Each adapter rejected bad tokens, unsupported protocol versions, and `execute_python`; split TCP request framing handled |
| Codex registration | CLI `codex mcp get majestic_forge` reports enabled stdio server with the project environment |
| Blender local installation | Add-on file installed in Blender 5.2 user scripts directory; Blender's native add-on discovery found exactly one `majestic_forge` module; persistent enablement not changed |

The validation Blender process explicitly pumped the bridge timer callback on its
main thread because background mode has no interactive timer loop. This proves bpy
inspection and network integration in a real Blender process, not interactive timer
behavior in the user's open Blender window. The Unreal probe loaded the plugin and
inspected the real editor world without saving assets.

Runtime evidence is stored under `Saved/MajesticForgeValidation` and excluded from
source control. Session credentials are never included in the live report. Isolated
probe processes are stopped after validation; the user's existing editor and Blender
processes are preserved.

## Codex client acceptance completed — October 9, 2026

All five `mcp__majestic_forge__*` tools were available and successfully invoked directly
from the user's Codex IDE conversation, using explicit session IDs for the application
calls. Each returned `ok: true`, structured MCP content, and `isError: false`.

| Tool | Confirmed result from the user's open application sessions |
| --- | --- |
| `forge_status` | Version 0.1.0, stdio, two responding read-only adapters |
| `forge_list_sessions` | Connected Unreal session `unreal-40584` and Blender session `blender-43952` |
| `unreal_project_info` | ForgeMCPDev, UE 5.6.1, world `/Temp/Untitled_1.Untitled_1`, PIE inactive |
| `unreal_list_actors` | 144 loaded actors; sample of 10 with `truncated: true`; actor IDs, labels, classes, and paths returned |
| `blender_scene_info` | Blender 5.2.2 LTS, unsaved `Scene`, zero objects, frames 1–250, current frame 1, effective 24 FPS |

These calls used the user's normal application processes, not the earlier isolated
probes. The live Blender bridge responded through its interactive application timer.
No restart or add-on activation was necessary in this acceptance turn: both bridges
were already connected. No scene, asset, or preference changes were made.

The first milestone's five-tool client acceptance criterion is satisfied. Persistence
of Blender add-on enablement across a future restart has not been tested. No UI
screenshot/click-through test was performed. Blueprint creation, scene modification,
export/import, packaging, and public publication are future milestones.

## Blender sidebar update — add-on 0.1.1

Added a 3D Viewport sidebar tab named `Majestic Forge`, a `Forge MCP Connection`
panel, bridge start/stop operators, status/endpoint/session display, last authenticated
request timing, and an auto-start add-on preference. Tokens are not displayed. Scene
data is not changed by the panel or connection controls. Auto-start is applied when
the add-on is enabled, with persistence controlled by Blender's normal preferences.

Installed the updated module in the Blender 5.2 user add-ons directory, preserving a
backup of the previous installed source. A separate factory-startup Blender 5.2.2
process verified native panel registration, start/stop operators, disable/re-enable,
auto-start true/false behavior, and unchanged scene object/frame/FPS state. The installed
add-on verification printed `FORGE_INSTALLED_UI_PREFERENCES_AND_LIFECYCLE_PASS`.
Python lint and all 14 server regression tests passed.

These are native Blender API checks, not a screenshot or visual inspection of the
sidebar. An already-running Blender process must reload the updated add-on to show
the tab; copying the source file does not replace its in-memory module. No open scene
was closed or saved and no user preference file was rewritten by this update.

## Unreal panel and installable plugin — version 0.1.1

Implemented a native Slate dockable `Majestic Forge` panel and a `Window > Majestic
Forge` menu entry. The panel exposes bridge status, local address/session ID, last
authenticated request timing, start/stop controls, and a per-project auto-start
checkbox. No authentication token is displayed. The checkbox applies at the next
project launch and writes only its Majestic Forge editor setting when the user changes
it. Scene and asset data is not modified by the connection controls.

Epic's AutomationTool `BuildPlugin` compiled and linked the Win64 UnrealEditor target,
then reported `BUILD SUCCESSFUL` with exit code 0. The package's module BuildId matches
the installed engine's `43139311`. The local ZIP is
`Artifacts/MajesticForge-0.1.1-UE5.6.1-Win64.zip` and includes the native plugin source
and the compiled editor binary. No public publication or distribution license was
chosen. Python regression tests still report 14 passed and Ruff checks passed.

The installer was exercised twice against a separate UE 5.6 test project: initial
installation enabled Majestic Forge while preserving its description and an unrelated
disabled plugin; repeat installation created a backup of the previous plugin and
project descriptor. It checks for a running editor before replacing target binaries.

The packaged plugin was loaded in a separate installed test project's real editor
process. Authenticated health returned version `0.1.1`, and project inspection returned
`ForgeInstallCheck`. The isolated editor was then stopped. The installer's running-editor
guard was also verified against the original open ForgeMCPDev project.

Native compilation, packaging, installation, and live loading are verified. No
screenshot or menu click-through verification has been performed. Existing editors
must be closed before their loaded plugin binary is replaced.

After the original editor was closed, `scripts/Install-ForgeUnreal.ps1` installed the
compiled 0.1.1 package into ForgeMCPDev itself and enabled its project plugin entry.
The previous plugin was backed up under `Saved/MajesticForgeInstallBackups`, and the
project descriptor was backed up beside the original. ForgeMCPDev was reopened using
its existing Unreal 5.6.1 installation. The panel entry is `Window > Majestic Forge`.
Direct Codex `forge_list_sessions` subsequently confirmed the reopened project session
`unreal-6528` responding with adapter version `0.1.1`. The user's reopened Blender
session also reported `0.1.1`. Both updated bridges are live.

## Security update — version 0.1.2

Both adapters now protect their credential directories and registration files before
advertising a session. Windows runtime checks confirmed protected DACLs containing
only OWNER RIGHTS and SYSTEM and actual Forge TCP listeners at `127.0.0.1`. The
existing user session directories/files were also restricted immediately. A protection
failure prevents new bridge startup. Unreal tokens now use 256-bit BCryptGenRandom;
Blender retains Python's cryptographic secrets generator. Tokens remain absent from
panels, results, diagnostic object representations, and logs.

Added bounded JSON nesting, object argument validation, safer malformed registration
handling, linked/out-of-root registration rejection, generic bridge error reporting,
and explicit response bounds. The native allowlists still expose inspection only.

| Check | October 9, 2026 evidence |
| --- | --- |
| Python regression and MCP subprocess tests | 22 passed |
| Python lint | Ruff passed for server, tests, scripts, and add-on |
| Dependency advisory audit | pip-audit 2.10.1, 38 pinned packages, no known vulnerabilities |
| Native editor target | UE 5.6.1 Win64 Development: `Result: Succeeded`; original native C++ compiled and DLL linked |
| Installed Unreal package probe | Separate `ForgeSecurityCheck` project loaded adapter 0.1.2 |
| Live rejection probes, both adapters | Bad token, arbitrary execution command, unsupported protocol, invalid arguments, deeply nested JSON, and oversized input rejected; both answered health afterward |
| Live MCP subprocess probes | All five tools returned successful structured results with server 0.1.2; later environment-forwarding verification showed those calls targeted the original 0.1.1 adapters. Separate 0.1.2 rejection/health probes did target the isolated adapters. |
| Native permissions and listener check | Both fresh token files have protected owner/SYSTEM DACLs; Forge TCP listeners are loopback only |
| Installed Blender verification | Factory-startup Blender 5.2.2 LTS printed `FORGE_INSTALLED_UI_PREFERENCES_AND_LIFECYCLE_PASS`; scene state unchanged |
| Running-editor installer guard | Refused to replace the original open ForgeMCPDev plugin |

AutomationTool's initial build and subsequent UBT child launches stalled in this
environment. The MSVC compile/link and UBT metadata steps completed with redirected
diagnostic output, and the final UnrealEditor target check reported success. Compiling
without shared PCH also exposed a missing JSON print-policy include, which was fixed
explicitly. The 0.1.2 package was assembled from the compiled native output, source,
descriptor, and matching engine module metadata, then installed and live-tested.
Its local ZIP is `Artifacts/MajesticForge-0.1.2-UE5.6.1-Win64.zip`; SHA-256 is
`BFBE3A63B25D306897EE95886B4E2EA3C0980219C9607E15B1785EEE8A285DD7`.

Evidence is under `Saved/SecurityAudit` and excluded from Git. The audit result is a
dated known-advisory check, not a guarantee against every defect. See
[Security.md](Security.md) for threat boundaries.

The user's original Unreal session `unreal-6528` and Blender session `blender-44324`
were preserved and still reported adapter 0.1.1 during this update. Blender 0.1.2 is
installed on disk; the Unreal 0.1.2 package is ready for the installer. Save and close
the target Unreal editor, run `scripts/Install-ForgeUnreal.ps1`, then reopen it. Save
work and restart Blender, and restart the Codex extension to load server 0.1.2. No
interactive panel screenshot/click-through validation was performed in this update.
