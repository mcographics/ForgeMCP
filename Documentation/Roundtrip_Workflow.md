# Unreal / Blender handoff

This implements the first manual round-trip stage of the original roadmap.
It is not real-time synchronization and does not replace existing assets.

## User controls

- **Blender: Send to Unreal** sends the active supported static mesh through the
  existing preview/apply FBX workflow. The old operator identifier is retained
  for compatibility, but the panel, button and confirmation use the new wording.
- **Unreal: Send to Blender** uses exactly one selected Content Browser static
  mesh, or one selected StaticMeshActor's mesh if no mesh asset is selected.
  The Blender object name starts blank and keeps the source static mesh asset's
  name. Enter a name to override it before sending. The handoff uses the mesh
  asset's geometry, not the selected actor's world transform.
- **Unreal: Import from Blender** pulls the named Blender source mesh, or its
  active object when the name is blank. Choose a new `/Game/.../SM_Name` asset
  path. An existing destination is preserved and rejected with an actionable
  message. This imports/saves new assets without placing an actor or saving a level.

Start both bridges first. With multiple Blender sessions, enter the intended
`blender-PID`; otherwise a single connected session is selected. The Unreal
panel passes its own project registration directory to its worker, independently
of the Codex client's session-discovery configuration.

Every button prepares a preview. Review the source, destination and limitations,
then confirm. Cancellation during preparation/preview applies no transfer.
Keep both applications open while an apply is running. An interrupted apply is
uncertain; inspect its receipt and target before trying anything again.

## Current supported payload

The Unreal-to-Blender route supports **binary FBX** and **OBJ** for loaded `/Game/`
or `/JasperPrism/` static mesh assets: one mesh, LOD0, at most 100,000 source
vertices, 200,000 triangles and 32 material slots. Separate high-resolution source
descriptions, skeletal meshes, animation, collisions and actor/world hierarchies are
excluded. OBJ also requires render LOD0 triangles to match the source mesh
description. The native UE OBJ exporter writes corner-expanded vertex records and
sidecars; only the main `.obj` is transferred. Blender welds exactly coincident
vertices while retaining per-loop UVs and face smoothing data.

Unreal material graphs are not portable Blender shaders. FBX transfers receive
editable opaque constant Principled placeholders. UE's OBJ exporter includes
triangulated positions and UV0 but omits normals and material data; the importer
recalculates geometry normals and assigns an editable placeholder. OBJ uses UE's
native X-forward/Y-up/Z-right basis and centimeter coordinates; import converts
to Blender -Y-forward/Z-up and the target scene's physical unit scale. These
An asymmetric disposable UE 5.6.1/Blender 5.2.2 MCP fixture verified the OBJ axis
and unit conversion against the full returned vertex set, bounds and triangle count.
The native importer must use a negative-X forward axis for this exporter convention;
the fixture caught and fixed the initial positive-X reflection. Visual/material
equivalence is not claimed.
The Blender return route retains its existing opaque constant-material contract:
textures, procedural graphs, modifiers, parented meshes and animation require
later transfer work and are rejected explicitly.

## Reviewed Blender modifier edits

`blender_preview_scene` now accepts a typed `set_modifier_settings` operation
for a supported existing modifier on a local mesh in Object Mode. It validates
the modifier and proposed settings, then verifies the applied values by reading
them back. A multi-operation recipe captures prior values and restores them if a
later operation fails. Modifier state participates in object fingerprints, so a
preview expires after a competing settings edit. Native MCP acceptance covered
successful read-back, injected failure with rollback, and stale-preview rejection.
This edits the Blender scene only; it does not make modifiers transferable in
the Blender-to-Unreal mesh payload.

## Stable mesh bindings

Each reviewed Blender export receives a stable 128-bit binding ID. The add-on
attaches it to the source object only after the confirmed export succeeds; the
`.blend` remains unsaved until the user saves it. Unreal imports retain that ID
and the Blender source snapshot SHA-256 in package metadata. Unreal sends reuse a
stored binding, or derive a stable ID from the project and asset path for an
unbound source. Blender stores the ID on the received object. A disposable native
MCP round trip verified the same binding through Blender → Unreal → Blender →
Unreal, then restarted the Editor and verified the ID after package reload.

The source snapshot SHA-256 fingerprints the transferable content (mesh topology,
geometry, supported attributes/material state, object identity, units and transform)
without process-local object addresses, so it remains comparable after reopening an
application. It records the Blender revision imported into that Unreal asset.

`forge_compare_mesh_binding` and the app-specific `blender_inspect_mesh_binding`
and `unreal_inspect_mesh_binding` tools compare the current revisions with the
recorded Blender and Unreal baselines. They report `synchronized`, `blender_changed`,
`unreal_changed`, `both_changed_conflict`, `binding_mismatch`, `unbound`, or
`baseline_unavailable`. These tools only inspect loaded application data and never
create an apply preview, edit, or save an asset. Unreal mesh/material-slot state is
fingerprinted; edits inside a referenced material graph are not currently included.
The MCP round-trip acceptance run observed `synchronized` on both an original and a
returned mesh, then observed `blender_changed` after a reviewed Blender transform.
The other report states are covered by coordinator tests; their native Editor cases
remain to be verified.

Successful import makes the received Blender mesh active for editing. It does
not save the `.blend` file. Source Unreal assets remain unchanged during the
initial import. For an existing bound mesh, the optional reviewed replacement
path can reimport Blender's changed static mesh into the same Unreal asset after
making and verifying a package backup and retaining existing material assignments.
The replacement preview becomes stale if either side changes before apply.

## Implementation boundaries

`forge_preview_send_to_blender` and `forge_apply_send_to_blender` coordinate
native Unreal `mesh_export_preview`/`mesh_export_apply` with Blender
`import_preview`/`import_apply`. Unreal uses native `UAssetExportTask` and
`UStaticMeshExporterFBX` or `UStaticMeshExporterOBJ` on the Editor game thread.
Blender imports through its native FBX or OBJ operator on its main thread. Neither adapter accepts arbitrary code
or caller-selected artifact paths.

The external panel worker uses these MCP tools for both Unreal buttons. Existing
Blender-to-Unreal MCP tools remain the implementation behind both Send to Unreal
and Import from Blender. Expiring previews bind source snapshots, session
authentication identities and application context. Applies are single-use.

Private generated staging retains the FBX or OBJ with size/SHA-256 verification.
OBJ validation rejects non-triangle faces and all MTL/sidecar directives, so the
importer never follows external paths.
The shared workflow journal records export, staging, import and verification.
Native import failure rolls back newly created Blender datablocks; successful
stages and uncertain outcomes retain receipts. Graph/asset recovery is not implied
by having a receipt. The receiving object stores its originating transfer ID,
and the receipt retains the source asset and destination identity.

## Loading the updated development build

The validated artifacts are
`Artifacts/ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip` and
`Artifacts/ForgeMCP-Blender-Addon-0.2.28.zip`. The Unreal package requires the
matching Unreal 5.6.1 Win64 build; another engine build needs a rebuild.

Save your work and close JasperPrismDev before replacing its native plugin DLL.
From PowerShell, install the prepared package with:

```powershell
& 'G:\ForgeMCP\scripts\Install-ForgeUnreal.ps1' `
    -ProjectFile 'G:\Unreal Engine Projects\JasperPrismDev\JasperPrismDev.uproject' `
    -PackageArchive 'G:\ForgeMCP\Artifacts\ForgeMCP-Unreal-Development-0.2.0-UE5.6.1-Win64.zip'
```

The installer preserves the existing plugin/project backup and refuses replacement
while that project is open. Save Blender work before closing Blender, then update
the add-on from the 0.2.28 ZIP through Preferences, or use the existing source
installer `scripts/Install-ForgeBlender.ps1 -BlenderVersion 5.2`. Reopen both apps,
enable ForgeMCP, start their bridges and reconnect Codex's ForgeMCP integration.
Open Unreal's **Window > ForgeMCP** and Blender's **ForgeMCP** sidebar. Choose the
ForgeMCP folder containing the `.venv` in each panel.

The packages and MCP workflow passed disposable native acceptance. They have not
been hot-replaced into the user's currently running applications. Interactive
panel clicks and rendered material appearance are separate acceptance checks.

## Next stages toward seamless editing

Stable identity, content fingerprints, read-only revision comparison and an
explicitly reviewed Blender-to-Unreal replacement path are implemented. The
replacement path was exercised through actual MCP stdio against disposable UE
5.6.1 and Blender processes. It verified a `.uasset` backup by SHA-256, preserved
the existing material assignment, compared the bindings as synchronized, and
reloaded the Editor to verify saved revision metadata. The fixture did not
exercise split package sidecars, forced reimport/save failures, rollback recovery,
or interactive Slate clicks; those remain open validation work.

Remaining stages:

1. Validate broader static mesh UVs, normals, material slots and non-default units.
2. Exercise replacement rollback/recovery failures and broader package sidecar cases.
3. Add change detection, debouncing, conflict handling, loop suppression and an
   explicit live-sync switch. A change originating in one application must not
   bounce back indefinitely or silently replace a user's concurrent edit.
4. Extend payloads, texture transfer, skeletal meshes and animation using
   separate versioned contracts and native acceptance tests.

The wider roadmap's PCG, comprehensive asset management, editor diagnostics and
advanced animation/retargeting work remain separate features. This handoff stage
does not mark the entire Unreal/Blender roadmap complete.
