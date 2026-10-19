# ForgeMCP

The **UE 5.6.1 Win64 engine-wide alpha** can be installed once for the engine and
enabled in individual projects while feature development continues separately.
See [alpha installation, updates and rollback](Documentation/UE56_Alpha.md).

**Free and open source.** All original ForgeMCP source uses the [MIT license](LICENSE).
See [credits and upstream notices](CREDITS.md) for separately licensed material.
The Unreal plugin, Blender add-on and external MCP server live in this repository;
the author's active Unreal development project is preserved locally and excluded
from the current source checkout. This is a development release with documented
operation limits, not universal control of either application.

Original Majestic Creations ForgeMCP integration for Unreal Engine and Blender, with Codex in
VS Code as the primary intended client. ForgeMCPDev is the Unreal 5.6 test project.
The current development source retains the inspection foundation and adds native Blueprint
construction and reviewed existing graph edits, Unreal registry asset queries, bounded GAS
Blueprint setup and live inspection, Blender rig animation, scene/material graph recipes,
and local version-aware API retrieval. GAS, UMG, World
Partition, broad graph/property coverage, asset interchange and wider workflows remain
in development.

The [active development plan](Documentation/Active_Development_Plan.md) defines the
full completion gates and the next Blender-to-Unreal asset-transfer milestone.
The original roadmap remains the historical vision.

Standalone `blender_preview_export` and `blender_apply_export` tools export a reviewed
static mesh to private FBX staging without saving the scene or accepting arbitrary
output paths. The development MCP registry exposes the current inspection and reviewed workflow tools. This stage requires
the updated Blender add-on; it does not perform Unreal import or asset placement.
Texture/group materials and modified/animated meshes are explicitly unsupported by
the initial export stage.

`forge_preview_transfer` and `forge_apply_transfer` connect export, protected
staging, Unreal import, native geometry/material verification and actor placement.
They require explicit Blender and Unreal sessions and current adapter builds.
`forge_inspect_transfer` reads durable operation receipts without claiming current
application state. Headless native acceptance passed for asymmetric identity and
transformed metric fixtures; interactive use, level saving, shader appearance and
native recovery reconciliation remain outstanding.

`unreal_inspect_static_mesh` reports bounded geometry and material graphs for an
already loaded mesh, including dirty flags and disk-package presence. It never
loads, saves or retries imports. Disk presence alone does not prove saved contents.

`forge_reconcile_transfer` compares a retained operation with an explicit Unreal
session in the recorded project. It verifies loaded geometry/materials against
export evidence without changing the receipt or performing recovery mutations.

`forge_preview_asset_recovery` / `forge_apply_asset_recovery` restore a retained
export from an incomplete operation into a reviewed new destination in the same
Unreal project. They require no Blender session, preserve the original receipt
and partial assets, verify the restored geometry/materials and save new packages.
This recovery restores assets only; it does not place actors or save a level.

Build the source-only Blender installer ZIP with
`.venv\Scripts\python.exe scripts/package_blender_addon.py`. Previous package bytes
are preserved in `Artifacts/Backups` when the package changes. The native export,
MCP export and clean-profile ZIP-install verifiers are respectively
`scripts/verify_blender_export.py`, `scripts/verify_blender_export_mcp.py`, and
`scripts/verify_blender_package.py`.

The Blender 0.2.32 add-on includes **Send to Unreal** in the 3D Viewport sidebar
under **ForgeMCP**. Select an active static mesh in Object mode, choose a new
`/Game/.../SM_Name` asset path, and click the button. Review the connected Unreal
project, asset path, save option and placement before clicking **Confirm Send
to Unreal**. Placement defaults to `(0,0,0)` in Unreal centimeters. Leave the
session field empty only when exactly one Unreal bridge is connected; otherwise
enter the intended `unreal-PID` session ID. The Blender bridge must be running.
The **ForgeMCP folder** setting points to this development checkout and its
`.venv`; the source-only add-on ZIP does not bundle the external MCP runtime.

The Unreal **Window > ForgeMCP** panel also provides **Send to Blender** and
**Import from Blender**. Send exports one selected static mesh through a reviewed
binary FBX handoff into a new Blender object. Import pulls a named or active Blender
mesh into a new Unreal asset. These are manual round-trip operations; existing
destinations are not replaced and real-time synchronization is not enabled.
See [round-trip workflow and limits](Documentation/Roundtrip_Workflow.md).

Transfers use the existing authenticated MCP preview/apply tools and durable
receipts. Existing assets are not overwritten, scenes and levels are not saved,
and unsupported procedural/textured materials produce an explicit error. Use
an opaque constant Principled material for this stage. Do not close either app
during apply. An uncertain result must be inspected using its receipt before
retrying. `scripts/verify_blender_transfer_panel.py` exercises the actual native
Blender operators and Unreal import/placement in disposable sessions; it does
not claim visual interaction or rendered acceptance.

The current Unreal development installer is
`Artifacts/ForgeMCP-Unreal-Development-0.2.8-UE5.6.1-Win64.zip`. Extract its
`Forge` folder into a closed project's `Plugins` directory, or pass that
extracted folder as `-PackageDirectory` to `scripts/Install-ForgeUnreal.ps1`.
The installer now defaults to this ZIP and accepts `-PackageArchive` explicitly;
it validates checksums, bounded archive scope and paths before extraction into
private project-local staging. The ForgeMCP Python environment is required for
archive validation. It refuses replacement while that project is open in either
UnrealEditor or UnrealEditor-Cmd and preserves an existing plugin/project backup.
The package includes current source/configuration and both compiled modules for
the verified Unreal 5.6.1 Win64 editor BuildId. A fresh Blueprint-only test project
loaded the extracted DLL and exposed native transfer/inspection capabilities.
It is a development package; other engine builds require a matching rebuild.
`scripts/package_unreal_plugin.py` checks source/build identity and creates the ZIP;
`scripts/verify_unreal_package.py` validates extraction and native loading separately.

The current Blender installer is
`Artifacts/ForgeMCP-Blender-Addon-0.2.35-alpha.4.zip`. Install the ZIP through Blender's
Install from Disk action and enable ForgeMCP. The add-on reports its own component
version in the bridge health response. Clean-profile install and feature-specific
native acceptance are recorded in `Documentation/Development_Status.md`; these
checks do not assert installation in an existing user session.

The external Python server uses the official MCP Python SDK. The Unreal C++ plugin,
Blender Python add-on, session protocol, and routing code were authored here. No
third-party Unreal/Blender MCP implementation is required. No cloud API key or hosted
AI is required by the server or adapters.

## Foundation inspection tools

| Tool | Result |
| --- | --- |
| `forge_status` | Server version and live health of registered adapters |
| `forge_list_sessions` | Session IDs, adapter kinds, connection state, and diagnostics |
| `forge_ensure_connected` | Rediscover and authenticate one live Unreal and Blender bridge; selects only unique live sessions |
| `unreal_project_info` | Engine version, project file, current editor world, PIE state |
| `unreal_list_actors` | Loaded world actors: IDs, labels, classes, paths; capped results |
| `blender_scene_info` | Version, file, scene, object counts/types, frame range and frame rate |

Application tools accept an optional `session_id`. If multiple registrations exist,
choose explicitly using `forge_list_sessions`; the server does not guess which project
you intended. `forge_ensure_connected` retries discovery and performs authenticated
health checks for both adapters, returning explicit session IDs when unique. It cannot
start an application bridge; if one is unavailable, open that app and start ForgeMCP.
MCP calls use short-lived authenticated requests rather than persistent sockets. Actor
`limit` defaults to 200 and accepts 1–1000. Scene object samples are
capped at 200. Each result contains `ok` and either `data` or `error`; an unavailable
application is reported rather than replaced with simulated data. SDK validation
errors use MCP's `isError` result.

Seventeen native engineering tools inspect Unreal classes, actors, GAS state, registry assets and Blueprints,
preview/apply Blueprint creation and graph edits, inspect Blender objects and rigs, and preview/apply Blender
scene and bone-animation recipes. `forge_search_api_docs` retrieves installed Unreal Python and Blender bpy
reference data for an exact version. Engineering tools require explicit session IDs.
Reviewed actor recipes support native spawning, transforms and game-hidden state;
Blender recipes also duplicate local mesh/empty objects with independent mesh/Action data.
The development source currently registers 85 MCP tools, including reviewed saving
of a persistent Unreal level to a new map destination and guarded multi-property
edits to existing Unreal DataAssets. The live Codex ForgeMCP connector still needs
reconnection to expose the latest source registry. The local application
packages and the older combined release ZIP have different validation histories.
See [engineering interfaces](Documentation/Engineering.md)
and [the current roadmap status](Documentation/Development_Status.md).

## Installation and repository organization

ForgeMCP is a free local integration. Unreal Engine, Blender and your MCP client
remain separately installed products with their own terms. The core workflow does
not require paid APIs or cloud services.

Follow [the source installation guide](Documentation/Installation.md) to install
the external server, build the Unreal plugin in your own project and package the
Blender add-on. See [repository layout](Documentation/Repository_Layout.md) for
published components and excluded local development files.

The Unreal plugin lives in `Plugins/Forge`; the Blender add-on lives in
`blender-addon/majestic_forge`. Their internal identifiers remain stable while both
appear as **ForgeMCP** in the applications. The local `ForgeMCPDev.uproject`, root
`Config`, `Content` and `Source` remain on disk for development but are excluded from
Git. A new clone can generate an independent minimal Unreal host with
`scripts/create_unreal_host.py`. No full game project is required to use the plugin.

Native version-specific development packages are generated locally under
`Artifacts` and are not committed. A source checkout is not an installed application
adapter, and a packaged adapter is not proof of visible interactive acceptance.

## Try it in Codex

After restarting the extension and enabling the adapters, ask:

> Use ForgeMCP. List running sessions, inspect ForgeMCPDev and its loaded
> actors, and report the active Blender scene and frame rate. Do not modify either scene.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check server tests scripts blender-addon
.\.venv\Scripts\python.exe scripts\verify_live.py
.\.venv\Scripts\python.exe scripts\verify_bridge_rejections.py
```

Installed Blender panel and start/stop lifecycle verification, using a separate
factory-startup process:

```powershell
& 'E:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python "$PWD\scripts\verify_blender_ui.py"
```

Automated tests exercise real TCP framing/authentication/correlation failures and a
real subprocess MCP stdio handshake, all five tool definitions, structured output,
disconnected applications, and argument bounds. `verify_live.py` requires responding
Unreal and Blender sessions and saves a token-free report under
`Saved/MajesticForgeValidation/live-report.json`. Live tests are described separately in
[the milestone validation record](Documentation/Milestone_1_Validation.md).

## Architecture and boundaries

Codex → MCP stdio → Python core → authenticated loopback TCP → native editor adapter.
Session files contain local credentials and remain outside version control. Unreal
writes under `Saved/MajesticForge`; Blender writes under
`%LOCALAPPDATA%/MajesticForge/sessions` (overridable with
`FORGE_BLENDER_SESSION_DIR`). Both adapters bind only to `127.0.0.1`, use an ephemeral
port and a fresh token, and expose allowlisted inspection commands.

Unreal uses nonblocking socket work on its game-thread ticker; Blender uses a main-thread
application timer. Each connection handles one newline-delimited JSON request, with
bounded buffers, client counts, and deadlines. The external server bounds responses
and checks request correlation. Inspection tools do not change native scenes/assets;
preview/apply tools perform the explicitly reviewed recipe through native APIs.
The server logs operation types and error codes to stderr and rotating per-process
files in `Saved/MajesticForgeLogs`; it does not log authentication tokens or scene data.

Version 0.1.2 automatically restricts credential directories and files to their owner
and SYSTEM on Windows, and refuses startup if protection fails. Request parsing also
limits nesting and validates argument types. This authenticates application connections;
software running as the same user and administrators remain outside that boundary.
Stale crash registrations are reported disconnected; they are not silently deleted.
Read-only tools still expose project/scene metadata to the authorized MCP client.
See [security boundaries and update activation](Documentation/Security.md).

This checkout includes the supplied [original roadmap](Documentation/Forge_MCP_Original_Development_Roadmap.md).
Source publication, a distribution license, releases, and advanced workflows are not
part of this milestone. Dependencies retain their own licenses; see [CREDITS.md](CREDITS.md).

Official references: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x),
[Codex MCP configuration](https://developers.openai.com/codex/mcp/),
[Unreal networking API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Networking/FTcpSocketBuilder),
and [Blender Python API](https://docs.blender.org/api/current/).
