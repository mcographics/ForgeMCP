# ForgeMCP Blender Tool Reference

The MCP server's live tool schemas and returned previews are authoritative. This is a
workflow index, not a promise that Blender features outside the listed operations are
available.

## Discover and inspect

Start with `forge_status`, `forge_list_sessions`, and, if needed,
`forge_ensure_connected`. Verify the selected explicit session using
`blender_scene_info`. Inspect only the necessary target data with
`blender_inspect_object`, `blender_inspect_mesh_geometry`,
`blender_inspect_mesh_edges`, `blender_inspect_mesh_uvs`,
`blender_inspect_material`, `blender_inspect_properties`,
`blender_inspect_animation`, `blender_inspect_rig`, `blender_inspect_skin`, and
`blender_inspect_mesh_binding`.

## Scene edits

`blender_preview_scene` validates a bounded typed recipe. Its operation allowlist is
documented in [the ForgeMCP capability map](forgemcp-capability-map.md). Inspect its
returned changes before calling `blender_apply_scene` with the exact preview ID and
confirmation. Apply changes the open scene and does not save it.

## Property, material, mesh, render, and copy operations

Use `blender_list_commands` and `blender_inspect_command` to inspect native operator
schemas; use `blender_list_rna_types` and `blender_inspect_rna_type` for RNA discovery;
and `blender_inspect_properties` for a typed target. Discovery is read-only. A command
marked `discovery_only` is not authorized for execution.

`blender_preview_creative` and `blender_apply_creative` cover the reviewed actions
listed in the capability map. Every action is one transaction. Render jobs use
`blender_render_job_status` and optionally the explicit
`blender_cancel_render_job` operation. A new `.blend` copy uses `save_copy`; it is not
an in-place save.

## Static-mesh transfer

`blender_preview_export` / `blender_apply_export` export an eligible static mesh to
private staging. This does not save the `.blend` or import the mesh into Unreal.
Cross-engine transfers have their own preview/apply tools and require explicit
inspection of both sessions.

## Never assume these tools exist

ForgeMCP does not expose `execute_blender_code`, arbitrary `bpy` execution, viewport
screenshot capture, active-file save, arbitrary deletion, unrestricted operator
execution, or every format/simulation/export feature described in Blender production
guidance. Do not substitute an unrelated MCP implementation to obtain them.
