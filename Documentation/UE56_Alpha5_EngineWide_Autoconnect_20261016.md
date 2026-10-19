# UE 5.6 alpha.5 — engine-wide live session discovery

Plugin package `0.2.13-alpha.5` moves Unreal bridge registration out of each
project's `Saved/MajesticForge` folder and into the current user's
`%LOCALAPPDATA%\MajesticForge\sessions` folder. The engine plugin is enabled by
default, and the bridge starts when its editor module loads. The MCP server
discovers live sessions from the shared folder and checks the responding process;
it does not choose a project from a previous session. The current project path is
read from the live editor only when a project identity operation is requested.

The Codex ForgeMCP environment no longer sets a project-specific Unreal session
directory. Blender and Unreal use the shared session folder by default. A user can
set `FORGE_SESSION_DIR` for a deliberate shared override; the app-specific variables
remain available for isolated testing and private deployments.

## Validation

- Python suite: 349 passed.
- Ruff and Python bytecode compilation: passed.
- UE 5.6.1 isolated `UnrealEditor` Development target: 29 actions passed, including
  both ForgeMCP modules. The build disabled only the unrelated Cargo plugin because
  its installed `KitBash3dUsdTools` module definition is missing.
- Package: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.5-UE5.6.1-Win64.zip`,
  SHA-256 `08727410482f5d156f3aeaf834e232eea36c883ad39d58ad3d90ede1d22a83b9`.
- The packaged plugin loaded in a disposable UE project and registered to the
  shared user session folder. The isolated MCP subprocess found and authenticated
  its live session, `forge_ensure_connected` selected it explicitly, and the
  returned project identity matched the disposable test project.

## Installation and live-editor acceptance

The engine package is staged but not installed yet. The user's UE 5.6 editor has
the existing ForgeMCP module DLL loaded, so the engine installer must wait until
that editor closes. After installation, start Unreal without a project first to
verify that the engine plugin registers on editor launch; choosing a project later
must not change the session discovery root. Restart the Codex MCP host after the
configuration edit so it loads the current server source, which includes
`forge_ensure_connected`.

The source and package build do not prove successful engine installation, a
projectless visible Editor UI, or live auto-connection in the user's current app;
those gates remain pending.
