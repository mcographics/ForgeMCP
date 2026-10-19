# UE 5.6 alpha.3 Blender handoff UX

The live Unreal project already contained `/Game/ForgeMCP/Returns/SM_Return`.
The import preflight returned `destination_exists` to prevent an overwrite.

Alpha.3 explained the collision. A short-lived server 0.3.9 follow-up selected
an `SM_`-prefixed free path and appended suffixes on collisions. That naming
policy was superseded by alpha.4 at the user's direction: transferred meshes
retain the exact source name, use `/Game/Content/Returns/`, and report exact-name
collisions without silently renaming. See
[alpha.4 transfer-name acceptance](UE56_Alpha4_Transfer_Names_20261016.md).

The Blender object-name override on Unreal's Send to Blender panel now
starts blank. Blank preserves the source Unreal static mesh asset's object name;
an entered valid name overrides it. A name collision in Blender remains a
preflight failure and can be resolved by entering a different override.

The native panel source is kept in the engine installation, as requested. Before
editing it, the alpha.2 header, implementation and descriptor were copied to
`Engine/Saved/ForgeMCPDevelopmentBackups/TransferPanelFix-20261016-alpha2`.

The alpha.3 package is built and validated:

- The UE 5.6.1 editor-target build compiled 27 actions, including both ForgeMCP
  modules, in a fresh isolated host. Cargo was disabled for this invocation to
  avoid its unrelated missing KitBash3dUsdTools dependency.
- Python source compilation and Ruff passed. The editable MCP package was 0.3.8,
  and `pip check` found no broken requirements at alpha.3 installation time.
- The package loaded in a fresh disposable Blueprint-only project, reported
  alpha.3 health, matched the packaged DLL hash and exposed the 104-tool source
  MCP server through real stdio discovery.
- Archive: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.3-UE5.6.1-Win64.zip`
  (SHA-256 `200715a0523b92831f7dcd2c99be2c2c5f6e6276d6352034d8c0d2fde29a5ff5`).
- Acceptance record: `Saved/UnrealPackageAcceptance-bb6df2aed2ea4627894a6f865cd340f6/acceptance.json`.

The engine-wide installer replaced alpha.2 with alpha.3 after the user closed
the Editor. Its backup is
`Engine/Saved/ForgeMCPInstallBackups/cef11a5e92d94a129de2ce8b9176d516/MajesticForge`.
A fresh disposable project loaded the DLL from the Marketplace engine path; its
hash matched the packaged DLL. The acceptance record is
`Saved/UnrealPackageAcceptance-76f214dc3ff140e5b1f690dd333b1c71/acceptance.json`.
The user's Blender scene was not changed. ForgeMCPDev was reopened on alpha.3
and its live bridge reported UE 5.6.1, `/Game/Levels/TestArea.TestArea`, and PIE
stopped. A visible panel inspection could not be completed because the Windows
Computer Use helper reported its native pipe unavailable; package/build behavior
is validated separately from the live widget display.

