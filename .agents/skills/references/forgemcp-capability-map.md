# ForgeMCP Blender Capability Map

This is the current agent-facing map of ForgeMCP's Blender adapter. MCP tool schemas
and live responses are authoritative. Recheck them after adapter changes; this page
does not promise support for all of Blender or for every workflow in the specialist
skills.

## Session identity

Use `forge_status` and `forge_list_sessions` to inspect host and adapter state. Use
`forge_ensure_connected` to rediscover connections when needed. Select one explicit
Blender `session_id` if sessions are ambiguous, then verify that same session with
`blender_scene_info`. Confirm the loaded `.blend` path, active scene, version, mode,
and target inventory before planning changes.

## Read-only inspection

| Tool | Evidence |
| --- | --- |
| `blender_scene_info` | Active scene, file, version, mode, object inventory, units, timeline and frame rate |
| `blender_inspect_object` | Exact object summary |
| `blender_inspect_mesh_geometry` | Bounded vertex and face pages |
| `blender_inspect_mesh_edges` | Bounded edge pages |
| `blender_inspect_mesh_uvs` | Bounded UV-layer loop pages |
| `blender_inspect_material` | Material node and input summary |
| `blender_inspect_properties` | Supported typed target's properties and editability |
| `blender_inspect_animation` | Active Action curves and keyframes in bounded pages |
| `blender_inspect_rig` | Armature hierarchy, constraints, optional weights/evaluated data |
| `blender_inspect_skin` | Bounded vertex weight pages |
| `blender_inspect_mesh_binding` | Static-mesh transfer binding and revisions |
| `forge_search_api_docs` | Version-specific local Blender API documentation; documentation only, never execution permission |

Use each tool's current schema for parameters, paging, and limits. Inspection does not
authorize an edit.

## Typed scene recipes

`blender_preview_scene` accepts bounded operations from the current `SceneOperation`
allowlist:

`create_mesh`, `set_vertices`, `set_mesh_geometry`, `set_uv_coordinates`,
`create_uv_layer`, `smart_uv_project`, `unwrap_uv`, `pack_uv_islands`,
`set_mesh_edge_seams`, `set_transform`, `create_material`, `assign_material`,
`create_collection`, `keyframe`, `set_keyframe`, `scene_settings`,
`duplicate_object`, `set_material_input`, `edit_material_graph`, `create_armature`,
`bone_keyframe`, `bind_mesh`, `reweight_mesh`, `auto_bind_mesh`,
`patch_skin_weights`, `create_ik_constraint`, `create_empty`, `set_frame`,
`add_modifier`, and `set_modifier_settings`.

These operation names are not unbounded Blender features. The schema imposes limits on
geometry, names, values, node graphs, rig data, UV pages, modifiers, and other inputs.
Preview first, review the native plan, apply only authorized changes, and read the
affected data back. Apply does not save the active `.blend`.

## RNA-driven creative previews

`blender_preview_creative` supports one reviewed operation per transaction. Actions
currently include:

- `create_object`: reviewed primitives and supported camera, light, empty, or world
  creation.
- `edit_properties`: allowlisted typed RNA properties on supported targets.
- `create_material_graph`: a bounded material node graph using native RNA validation.
- `keyframe`: explicit numeric keys on supported animatable properties.
- `mesh_operator`: operators from ForgeMCP's audited mesh-operation allowlist on
  eligible local meshes.
- `create_modifier` and `create_constraint`: native types subject to the adapter's
  validation; simulation and Geometry Nodes modifier types are rejected.
- `save_copy`: create a new `.blend` copy at an approved, protected path; overwrite is
  rejected.
- `render`: run a bounded PNG render job from a saved snapshot in a separate process.

Use `blender_list_commands`, `blender_inspect_command`, `blender_list_rna_types`,
`blender_inspect_rna_type`, and `blender_inspect_properties` for native discovery.
Catalog presence is not execution permission; `discovery_only` entries cannot be
applied. The typed schemas and preview response are the operation gate.

For renders, poll `blender_render_job_status`. It reports process completion and file
metadata, including dimensions and output paths; it does not inspect image appearance.
`blender_cancel_render_job` is an explicit mutation and requires its job ID confirmation.

## Asset transfer

`blender_preview_export` and `blender_apply_export` support reviewed export of eligible
static meshes into private transfer staging. They do not save the `.blend` and do not
complete Unreal import. Blender-to-Unreal and Unreal-to-Blender transfer tools are
separate preview/apply workflows: inspect both explicit sessions and the target before
using them, and report each stage separately.

## Not exposed by the current adapter

- Arbitrary Python, `bpy`, `eval`, shell-to-Blender execution, or execution of any
  unreviewed Blender operator.
- Viewport screenshot capture or an MCP operation that proves visual appearance.
- Saving the currently open `.blend` in place, overwriting an existing file, or
  deleting arbitrary scene data.
- General-purpose geometry-node authoring, cloth/hair/soft-body/fluid simulation,
  arbitrary texture painting, or arbitrary third-party generator integrations.
- General export of every format or automatic engine import/placement as part of the
  Blender export operation.

When a request needs one of these, keep the supported work bounded and report the
remaining operation as unsupported or awaiting separate visual/manual acceptance.
