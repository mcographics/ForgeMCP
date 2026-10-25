# Blender creative automation — October 13, 2026

Server source **0.3.6**, Blender adapter **0.2.33**. This increment adds nine MCP
tools and retains existing inspection, scene recipe, rig, skin, UV and transfer tools.
The source stdio registry contains **104 tools** across both applications.

## Discovery and execution are separate

`blender_list_commands` searches **every registered `bpy.ops` identifier** in the
selected session. `blender_inspect_command` returns native RNA parameter schemas,
ranges, enums, descriptions and the current context poll result. Catalog entries
report `create_object`, `mesh_operator`, or `discovery_only` explicitly. A successful
poll is not authorization, nor evidence that an execution adapter exists.

The Blender 5.2.2 factory-profile audit contains **2,499 operators**, including **21
primitive creation operators** and **44 registered audited mesh operators** with
execution adapters. The isolated source adapter registers five additional panel
operators, yielding **2,504** discoverable operators. Installed add-ons can change
these counts. The factory profile also exposes **4,012 RNA types**.

- `blender_list_rna_types` searches registered RNA types, including shader nodes,
  cameras, lights, modifiers, constraints, scenes and render settings.
- `blender_inspect_rna_type` returns native type properties.
- `blender_inspect_properties` returns values and per-property bridge editability
  for an explicit existing target. Use socket identifiers where names repeat.

Read the exported [operator coverage](Reference_Audits/Blender_MCP_Commands.csv)
or [JSON catalog](Reference_Audits/Blender_MCP_Commands.json). These files report
factory-profile coverage rather than pretending every discovered command executes.

## Reviewed creative operations

Call `blender_preview_creative` with one request and an exact `session_id`, review
the returned change, and call `blender_apply_creative` with both `preview_id` and
`confirmation` equal to that reviewed ID. Previews expire after 600 seconds, are
single-use, and reject changes to the captured scene content. Never replay an
apply timeout: inspect the target and retained outputs first.

Supported request actions:

| Action | Behavior |
| --- | --- |
| `create_object` | Native mesh, curve and NURBS primitives; cameras; Point, Sun, Spot and Area lights; Empty objects; worlds. Exact new names, bounded native parameters. `make_active` activates a new camera/world. |
| `edit_properties` | Native numeric, boolean and enum properties on supported scene/render/image/color-management/Cycles/Eevee, object/data, node/socket, modifier and constraint targets. Pointer/collection/path and unrestricted attribute traversal are excluded. |
| `create_material_graph` | A new material with up to 128 built-in shader nodes, 256 links, native settings and socket defaults, explicit color ramps, and optional assignment to a local mesh. Includes Blackbody, Emission, Voronoi, Noise, Vector Rotate, Layer Weight and Map Range rather than the old small node list. |
| `keyframe` | Explicit native numeric keys for objects, cameras/lights, settings or shader sockets. Copies an existing Action, preserves the original datablock, and reevaluates the current frame. |
| `mesh_operator` | An audited native mesh edit in Edit Mode on a copied plain mesh, selecting the full mesh. The original mesh datablock is retained; user context is restored. Shape keys, linked data and unsupported parameter types are rejected. |
| `create_modifier` | Native non-simulation modifiers with numeric/enum settings. Existing modifier properties can be edited through `edit_properties`. |
| `create_constraint` | Native object constraints with numeric/enum settings and optional exact `assign_to` target binding. Existing constraint properties can be inspected/edited. |
| `save_copy` | Saves a new absolute `.blend` in an existing non-link directory, verifies file header/size/hash and preserves the active file path. Existing destinations are rejected. Reopening is separate validation. |
| `render` | Saves a snapshot and launches a separate native Blender worker; produces a private PNG frame sequence without changing the interactive file, frame or render output path. |

Property edits apply to the exact resolved datablock, including its other users if
it is shared. Creation/mesh/keyframe workflows protect their original data as
described above. All creative edits require Object Mode and run on Blender's main
thread. Failures restore touched values and remove created data; rollback failure
is reported explicitly. None of these operations imports anything into Unreal.

### Example: native high-resolution sphere

```json
{
  "action": "create_object",
  "name": "Sun_Photosphere",
  "type": "mesh.primitive_uv_sphere_add",
  "parameters": {"segments": 128, "ring_count": 64, "radius": 1.0}
}
```

Create an active camera with `type: "CAMERA"`, `make_active: true` and object
`properties` such as `location`. Inspect its `camera` target before editing lens,
projection, clipping or orthographic scale. Camera orientation uses native Euler
rotation in radians; it does not assume a viewing direction from a target name.

### Example: 4K render settings

```json
{
  "action": "edit_properties",
  "target": {"kind": "render"},
  "properties": {
    "engine": "CYCLES",
    "resolution_x": 4096,
    "resolution_y": 2304,
    "resolution_percentage": 100,
    "fps": 24
  }
}
```

Set the `image_settings` target to PNG first. A render request supplies
`frame_start` and `frame_end`. Rendering returns `state: running` and a `job_id`;
it never reports the started process as completed rendering.

`blender_render_job_status` checks worker exit, expected frame count and PNG
headers/dimensions. `completed` requires exit code zero and all expected outputs.
Full PNG decoding, visual checks and artistic approval remain separate. The
bridge stays responsive while rendering. `blender_cancel_render_job` requires
confirmation equal to the inspected job ID, terminates only that worker, and keeps
the snapshot, log and partial frames. Poll a `cancelling` job until terminal state.

Job output is retained in the private Blender session root under
`renders/<session_id>/<job_id>`. At most two workers run concurrently; ranges are
limited to 1,000 frames and dimensions to 8,192 pixels per axis. External texture
resources are not automatically packed. Job ownership lasts for the current adapter
lifetime; adapter restart does not replay or resume uncertain work.

## Remaining adapters

Discovery is broad; execution is deliberately described by tested workflow.
Unrestricted Python/eval and arbitrary operator execution are not exposed. Scene
loading/replacement, deletion, existing-file overwrite, preferences/add-on changes,
file/network import operators, script nodes, Geometry Nodes/group and compositor
graph authoring, simulations/cache baking, and specialized context-dependent
editors still need dedicated reviewed adapters. Several existing rig/UV/transfer
operations remain available through their original tools.

## Verification and activation

- Full Python suite: **330 passed**.
- Disposable native Blender 5.2.2 test: **39 checks passed**, including wrong
  confirmation, replay, stale camera state, graph rollback, original mesh/Action
  preservation, native save-copy reopening and a real 4096 × 2304 render.
- Real stdio MCP + disposable authenticated Blender: tool discovery, property
  schemas, sphere/camera/shader/key authoring, save-copy, two 4K animated frames,
  full PNG CRC/decompression checks, differing animated output, and cancellation.
- Clean ZIP installation/activation/removal, cached-module reload and existing
  transfer/native tests passed in an isolated profile.

Evidence lives in `Saved/creative-acceptance.json`,
`Saved/creative-mcp-acceptance.json` and `Saved/BlenderPackageAcceptance-*`.
These tests do not establish interactive viewport QA or universal Blender control.

Installer: `scripts/Install-ForgeBlender.ps1`; package:
`Artifacts/ForgeMCP-Blender-Addon-0.2.33.zip`. The installer preserves previous module
bytes with timestamped backups and does not edit preferences or reload the running
Blender process. Save any scene work before restarting Blender or toggling the
add-on. Restart the ForgeMCP server/client connection to refresh the tool registry;
verify server **0.3.6**, adapter **0.2.33**, and all nine new tools before continuing.
