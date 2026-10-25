# UE 5.6 alpha.4 transfer names and destination

The engine-wide ForgeMCP plugin is **0.2.13-alpha.4** (descriptor version 19)
for UE 5.6.1 Win64. The external MCP server source is **0.3.10**.

Blender-to-Unreal transfers use `/Game/Content/Returns/` as the default
destination folder. ForgeMCP appends the exact Blender source object name to that
folder, without an `SM_` prefix, generated replacement name, or numeric suffix.
The preview shows the final asset path. If that exact path already exists, the
workflow returns `destination_exists`; it never invents another name. The apply
step rechecks the destination before export. If a source name cannot be used as a
valid Unreal package name, the workflow asks for the source to be renamed instead
of silently changing it.

Unreal-to-Blender continues to leave the optional Blender object-name override
blank by default. The source Unreal asset name is retained. The field label now
states that it is an optional override. The import button reads **Send to Unreal
(from Blender)**, and the destination field is labeled as a folder.

## Validation

- The UE 5.6.1 isolated host compiled both plugin modules and completed its
  28-action UnrealEditor target build successfully.
- The 50-file alpha archive passed package integrity checks and loaded in a clean
  Blueprint-only project with real stdio MCP discovery. The engine-wide package
  verification also passed, loaded the exact DLL from the Marketplace plugin
  folder, and reported health version `0.2.13-alpha.4`.
- Archive: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.4-UE5.6.1-Win64.zip`,
  SHA-256 `814c8c6bf87d6a4f6d2709525d252f497090df9e9643cab785f91b3ad05a3823`.
- The engine-wide installer updated the plugin and retained alpha.3 at
  `Engine/Saved/ForgeMCPInstallBackups/0966d6d9a60444d0a10cbe2942ba3f09/MajesticForge`.
  It did not modify project files.
- Python regression suite: **345 passed**. Ruff, Python source compilation,
  `pip check`, and `git diff --check` passed.

At verification time, no Unreal or Blender bridge sessions were connected. The
disposable editor/package checks validate the compiled plugin and MCP contract;
the changed panel has not yet been visually inspected inside the user's project,
and no real two-application transfer was applied. The Blender scene and project
assets were not modified during acceptance.
