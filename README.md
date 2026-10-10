# ForgeMCP

Original Majestic Creations ForgeMCP integration for Unreal Engine and Blender, with Codex in
VS Code as the primary intended client. ForgeMCPDev is the Unreal 5.6 test project.
The current development source retains the inspection foundation and adds native Blueprint
construction and reviewed existing graph edits, Unreal registry asset queries, bounded GAS
Blueprint setup and live inspection, Blender rig animation, scene/material graph recipes,
and local version-aware API retrieval. GAS, UMG, World
Partition, broad graph/property coverage, asset interchange and wider workflows remain
in development.

The external Python server uses the official MCP Python SDK. The Unreal C++ plugin,
Blender Python add-on, session protocol, and routing code were authored here. No
third-party Unreal/Blender MCP implementation is required. No cloud API key or hosted
AI is required by the server or adapters.

## Foundation inspection tools

| Tool | Result |
| --- | --- |
| `forge_status` | Server version and live health of registered adapters |
| `forge_list_sessions` | Session IDs, adapter kinds, connection state, and diagnostics |
| `unreal_project_info` | Engine version, project file, current editor world, PIE state |
| `unreal_list_actors` | Loaded world actors: IDs, labels, classes, paths; capped results |
| `blender_scene_info` | Version, file, scene, object counts/types, frame range and frame rate |

Application tools accept an optional `session_id`. If multiple registrations exist,
choose explicitly using `forge_list_sessions`; the server does not guess which project
you intended. Actor `limit` defaults to 200 and accepts 1–1000. Scene object samples are
capped at 200. Each result contains `ok` and either `data` or `error`; an unavailable
application is reported rather than replaced with simulated data. SDK validation
errors use MCP's `isError` result.

Seventeen native engineering tools inspect Unreal classes, actors, GAS state, registry assets and Blueprints,
preview/apply Blueprint creation and graph edits, inspect Blender objects and rigs, and preview/apply Blender
scene and bone-animation recipes. `forge_search_api_docs` retrieves installed Unreal Python and Blender bpy
reference data for an exact version. Engineering tools require explicit session IDs.
Reviewed actor recipes support native spawning, transforms and game-hidden state;
Blender recipes also duplicate local mesh/empty objects with independent mesh/Action data.
There are currently 23 MCP tools in development source. The existing 0.2.0 release ZIP
predates asset queries and custom material graphs. See [engineering interfaces](Documentation/Engineering.md)
and [the current roadmap status](Documentation/Development_Status.md).

## Setup on Windows

Run from this checkout using Python 3.11 or newer:

```powershell
.\scripts\Setup-Forge.ps1
.\BuildAndOpen.ps1
.\scripts\Install-ForgeBlender.ps1 -BlenderVersion 5.2
```

Setup creates a separate `.venv`, installs the package with the verified dependency
constraints, and prepares `.codex/config.toml`. Project configuration requires a
trusted workspace in Codex. To register the server through Codex's CLI instead:

```powershell
codex mcp add forgemcp --env "FORGE_PROJECT_ROOT=$PWD" -- "$PWD\.venv\Scripts\python.exe" -m server.main
codex mcp get forgemcp
```

That command creates a user-level entry. The environment variable keeps discovery
pointed at this Unreal project even when Codex starts the server elsewhere. It does
not change other MCP entries. Restart the Codex extension after registration. Remove
the entry with `codex mcp remove forgemcp` if desired.

The Unreal plugin is explicitly enabled in `ForgeMCPDev.uproject`. An editor that was
already running before the plugin was built needs to be reopened after saving work.
The plugin automatically advertises a session once it loads.

The Unreal panel is available from **Window > ForgeMCP**. It provides bridge status,
the local address/session ID, last authenticated request timing,
**Start Bridge / Stop Bridge** controls, and a per-project auto-start checkbox. Changing
auto-start affects the next project launch; start/stop affects only the local bridge.
The panel never displays authentication tokens.

The current Windows development package for the installed UE 5.6.1 engine is available
locally at `Artifacts/ForgeMCP-development-0.2.0-UE5.6.1-Win64.zip`. Its Unreal plugin
descriptor and editor panel use the **ForgeMCP** display name. Save your work and close
the target project's Unreal editor before replacing its loaded plugin binaries. To install
or update this project's plugin:

```powershell
.\scripts\Install-ForgeUnreal.ps1
```

To install into another UE 5.6 project using this engine build:

```powershell
.\scripts\Install-ForgeUnreal.ps1 -ProjectFile 'G:\YourProject\YourProject.uproject'
```

The installer copies `Artifacts/ForgeMCP-development-0.2.0/MajesticForge` into the selected project's
`Plugins/MajesticForge`, enables its descriptor entry, and preserves unrelated plugin
entries. Existing plugin files and the project descriptor are backed up. It refuses
to replace a plugin while that project's editor is running. You can also extract the
ZIP's `MajesticForge` folder into your project's `Plugins` folder, then enable it in
**Edit > Plugins** and reopen the editor. Other engine versions/builds need a matching
plugin build. The package is a local installation artifact, not a public release.

The Blender installer copies the add-on into the selected version's user scripts
directory, backing up an existing different file. In Blender, enable **ForgeMCP**
under **Preferences > Add-ons**. The installer does not rewrite preferences or
modify the open scene.

Blender add-on version 0.1.1 adds a visible **ForgeMCP** tab in the 3D Viewport
sidebar: hover over the viewport and press **N**. The **ForgeMCP Connection** panel
shows whether the bridge is running, its local endpoint and session ID, and the time
since its last authenticated request. **Start Bridge** and **Stop Bridge** control the
connection without editing the scene. The auto-start setting is also available in
the add-on's Preferences entry. It takes effect when the add-on is next enabled;
save Blender preferences if you want to persist that choice. The panel never displays
authentication tokens.

After installing an update, save your work and restart Blender, or disable and enable
the add-on so Blender reloads its changed module. Updating the file on disk does not
replace the module already loaded in an open application.

To launch a separate Blender session with the source add-on enabled:

```powershell
& 'E:\SteamLibrary\steamapps\common\Blender\blender.exe' --python "$PWD\scripts\blender_bootstrap.py"
```

That enables the add-on for the new session without persisting a preference change.
Change the executable path for your installation. Save preferences yourself if you
want the add-on enabled on future starts.

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
