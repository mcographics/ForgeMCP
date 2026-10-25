# UE 5.6 alpha.6 — Forge plugin directory

Alpha.6 installs the engine plugin at
`<EngineRoot>/Engine/Plugins/Marketplace/Forge`. The package and project-local
plugin folder use the same `Forge` directory name. The descriptor filename
`MajesticForge.uplugin`, editor/runtime module IDs, DLL names, Blueprint class paths
and the `%LOCALAPPDATA%/MajesticForge/sessions` registration path stay unchanged;
they continue to identify existing Unreal projects and assets.

The engine installer treats `Marketplace/MajesticForge` as the previous install
location. With `-Update`, it moves the old directory into the normal rollback
backup and installs the new package in `Marketplace/Forge`. If both folders exist,
it stops and asks for manual inspection rather than guessing which copy is active.

## Validation

- Installer and safe-extraction tests: passed, including migration backup from the
  old engine directory name.
- UE 5.6.1 isolated editor target: 29 actions passed with the plugin under
  `Plugins/Forge` and the legacy descriptor/module identifiers retained.
- Package `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.6-UE5.6.1-Win64.zip`;
  SHA-256 `2b21295fc6c1fdd37810f03b2bca7db3d7f0d7f788f32e4c86acdf052b14fe95`.
- Disposable editor loaded the packaged DLL from
  `Plugins/Forge/Binaries/Win64/UnrealEditor-MajesticForge.dll`; the authenticated
  MCP subprocess discovered the editor and verified its live project identity.

The engine-wide folder move is staged but has not been installed because the user's
UE 5.6 editor still has the previous plugin DLL loaded. The installer blocks the
move while an editor from this engine is running. After that editor closes, install
with `-Update`, then verify the loaded DLL under `Marketplace/Forge`.
