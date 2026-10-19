# ForgeMCP Unreal Engine 5.6 alpha

The current engine-wide alpha is plugin **0.2.13-alpha.9**, for **UE 5.6.1 / Win64
Development Editor**. The external MCP server source is **0.3.13**. Server feature
work continues in the checkout. Native source stays with the engine plugin;
build changes in an isolated host and update installed binaries deliberately. This is
an internal alpha, not a production release or universal Unreal automation.

## Install once for the engine

From the ForgeMCP checkout, after creating the package:

```powershell
.\scripts\Install-ForgeUnrealEngine.ps1 `
  -EngineRoot 'G:\Program Files\EpicGames\UE_5.6' `
  -PackageArchive '.\Artifacts\ForgeMCP-Unreal-Alpha-0.2.13-alpha.9-UE5.6.1-Win64.zip'
```

The destination is `<EngineRoot>\Engine\Plugins\Marketplace\Forge`.
The installer validates archive checksums, native module names and the exact
engine BuildId before installation. It rejects other engine versions, duplicate
engine copies and linked destinations. Installing requires write access to the
engine folder. It does not edit projects or remove project-local plugin copies.

ForgeMCP is enabled by default for projects using this engine installation. On
editor startup, the plugin auto-starts its bridge and writes a live registration
to `%LOCALAPPDATA%\MajesticForge\sessions`; no project path is used for discovery.
The MCP server authenticates registered sessions at startup and checks their
health every two seconds while its client session is active. The responding editor
reports whichever project is open at that moment. If multiple Unreal editors
respond, select an explicit live session ID. If the MCP client/server is stopped,
the engine bridge remains available locally but cannot show an authenticated
client connection until that server starts.
The alpha.8-and-later panel shows a colored status dot beside this text: pulsing green means
the authenticated heartbeat is current, yellow means it became stale after a prior
connection, and red means the bridge is stopped or has not authenticated yet.

A project-local `Plugins\Forge` can take precedence over the engine
installation. Preserve that copy as a backup outside all plugin search folders
before migrating a project to the engine copy. This checkout currently has no
project-local plugin copy, following the user's engine-wide source preference.
Do not remove a plugin while its editor is running.

## MCP connection

The plugin and external Python MCP server are separate components. Keep launching
the server from this checkout's `.venv` as described in [Installation](Installation.md).
The server's default session directory is the same user-wide location as the
plugin's. Do not configure a project-specific `FORGE_UNREAL_SESSION_DIR` for normal
engine-wide use. Read live project identity before edits. Registration files contain
credentials; never share them.

## Build the next alpha

The Unreal tab uses a local React frontend inside UE's WebBrowser widget. Build and
copy the frontend before creating the isolated Unreal host:

```powershell
Push-Location .\web-ui
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe .\Scripts\build_unreal_tab_ui.py
```

React and all panel assets ship inside the plugin. The interface uses a restrictive
content security policy, no remote assets, and a native C++ allowlist for actions.

Native source is currently kept in the engine installation, per the user's
preference. Use that explicit source location and a new disposable host:

```powershell
.\.venv\Scripts\python.exe scripts/create_unreal_host.py --destination Saved/AlphaValidation-NEXT/HostProject --plugin-source 'G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge'
.\scripts\Build-ForgePlugin.ps1 -ProjectFile "$PWD\Saved\AlphaValidation-NEXT\HostProject\ForgeMCPDev.uproject"
.\.venv\Scripts\python.exe scripts/package_unreal_plugin.py --host Saved/AlphaValidation-NEXT/HostProject --source 'G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge' --engine 'G:\Program Files\EpicGames\UE_5.6' --channel alpha
```

The build helper is specific to this machine's verified MSVC/SDK setup. Standard
Unreal BuildPlugin remains the portable build route. The local build helper always
excludes the unrelated installed Cargo plugin, whose `KitBash3dUsdTools` module is
missing on this machine. This changes only the build invocation, not the engine
plugin installation. ForgeMCP's
development and package-verification projects disable engine plugins by default,
then enable only their declared dependencies, including MetaSound and the Plugin
Browser. This prevents installed Marketplace plugins such as Cargo from loading
in ForgeMCP validation sessions while retaining the expected editor menu.
The helper uses up to four concurrent compiler jobs; use `-CompileJobs 1` on a
memory-constrained machine or for serial diagnostics.

Increase the descriptor version for subsequent alphas. Packaging requires byte
equality between current source and the isolated build, matching engine BuildId,
and module binaries newer than their source. The ZIP includes source, native DLLs,
resources, existing license notice and a SHA-256 manifest. It excludes session
credentials, project assets, Intermediate files and debug symbols. Runtime game
packaging, Shipping builds, other platforms and other 5.6 patch builds have not
been accepted for this alpha.

Close editors using this engine before updating, then repeat the install command
with `-Update`. Previous files are moved into
`<EngineRoot>\Engine\Saved\ForgeMCPInstallBackups\<unique-id>\MajesticForge`.
Installation failure restores the previous folder. To roll back manually, close
editors, move the current plugin outside plugin search folders, and restore the
backup to the installation path. To uninstall, close editors and move the plugin
outside `Engine\Plugins`; project-local copies are independent.

## Acceptance

Run Python regression tests/lint, compile the isolated editor target, package,
install and verify a fresh Blueprint-only project with no project plugin copy:

```powershell
.\.venv\Scripts\python.exe scripts/verify_unreal_package.py --archive Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.9-UE5.6.1-Win64.zip --editor 'G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe' --engine-plugin 'G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge'
```

This verifies authenticated bridge health, project identity and the actual loaded
DLL path in a disposable NullRHI editor, plus real stdio MCP discovery and project
inspection. It does not establish visible panel,
viewport, all-feature or performance acceptance. See the alpha build's evidence
record and [Development Status](Development_Status.md) for actual results.

The React tab UI is documented in [October 16 alpha.9 UI acceptance](UE56_Alpha9_React_Tab_UI_20261016.md), with the [white-tab fix](UE56_Alpha9_White_Tab_Fix_20261016.md), [official application logo update](UE56_Alpha9_Official_Partner_Logos_20261016.md), and [compact layout refinement](UE56_Alpha9_Compact_Layout_20261016.md). The alpha.8 connection indicator and FBX/OBJ handoff fix are documented in [October 16 alpha.8 acceptance](UE56_Alpha8_Connection_And_Send_20261016.md). Earlier authenticated startup behavior is documented in [October 16 alpha.7 acceptance](UE56_Alpha7_Authenticated_Startup_20261016.md). The alpha.6 plugin-folder migration is documented in [October 16 alpha.6 acceptance](UE56_Alpha6_Plugin_Folder_20261016.md). The alpha.5 engine-wide session discovery is documented in [October 16 alpha.5 acceptance](UE56_Alpha5_EngineWide_Autoconnect_20261016.md). The first alpha's results are recorded in [October 16 acceptance](UE56_Alpha_Acceptance_20261016.md).
The exact transfer-name and destination-folder behavior is recorded in
[alpha.4 acceptance](UE56_Alpha4_Transfer_Names_20261016.md); alpha.2 and alpha.3
fix history remains in their respective acceptance records.
