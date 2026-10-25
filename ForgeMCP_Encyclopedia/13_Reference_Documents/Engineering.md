# Native engineering interfaces — current development source

ForgeMCP retains its five foundation inspection tools and adds seventeen native
engineering tools plus one local API retrieval tool. Inspect session identity and the
project/scene first. All engineering calls require an explicit session ID. Natural
language is interpreted by the MCP client (Codex or another authorized agent), which
constructs the typed recipe; the application adapters contain no model/provider logic.

## Gameplay Ability System inspection and setup

`unreal_inspect_gas(actor_path, session_id)` reads GAS state from one exact actor in
the current idle editor world. It returns bounded AbilitySystemComponent identity,
replication mode, owner/avatar identity, initialized actor-info state, finite base and
current attribute values, owned tags, granted ability classes/levels/input IDs/active
state, and active GameplayEffect classes/levels/stacks/durations. Component, attribute,
tag, ability, and effect arrays include counts and truncation flags. It does not
activate abilities, apply effects, or change the actor.

New Blueprint recipes can add a replicated `AbilitySystemComponent` with an explicit
`minimal`, `mixed`, or `full` effect-replication mode. Minimal and mixed modes require
a matching ForgeMCP startup component. Unreal does not serialize the base ASC
replication-mode field into Blueprint component templates, so ForgeMCP stores that
requested mode in the startup component's typed Blueprint properties. It applies the
mode when the component registers and again before startup configuration at BeginPlay.
Blueprint inspection reports the configured mode separately from the ASC template
default. The startup component can also name AttributeSet, ability, and GameplayEffect
classes and applies those gameplay changes on the authoritative actor at BeginPlay.
This is a starting-configuration path, not full GAS authoring: creating/editing
GameplayAbility, AttributeSet or GameplayEffect assets, tag requirements, cues,
network behavior and gameplay execution remain incomplete and need project-specific
acceptance.

## Unreal Blueprint construction

`unreal_class_info` returns native reflected property types and Blueprint-callable
function signatures. `recipe_supported` identifies functions currently permitted in
graph recipes. Inspection is broader than executable recipe capabilities.

`unreal_preview_blueprint` validates a new `/Game` package path, a concrete native
actor parent, unique variables/components/functions, node IDs and graph references.
It returns an expiring session-local preview ID and the reviewed changes. No existing
asset can be overwritten. `unreal_apply_blueprint` requires `confirmation` equal to
that ID and a user task authorizing the exact changes. A preview is consumed once.

Recipes can add primitive variables, native actor components, void functions,
overridden parent events, custom events, variable get/set nodes and approved native
function calls. Branch, Sequence, Self and Reroute are also supported. Sequence
`execution_outputs` accepts 2–16 and creates `then_0`, `then_1`, etc. Other node kinds
use the default value of two without additional execution pins. Native schema links
propagate reroute types. Boolean pin defaults accept true/false/0/1; invalid defaults
discard the scratch Blueprint rather than silently retaining a different value.
Pin defaults and connections use native graph schemas. Apply compiles
the Blueprint and returns compiler errors/warnings, diagnostics, graph/pin inspection,
operation state and affected paths. `save` and `place` are explicit flags, both false
by default. `location` uses Unreal centimeters. Placement does not save the level.

Pin/compile failures discard the newly created scratch asset before any save.
Requested save/placement failures report `partial`; inspect `saved`, `placed`, and
diagnostics. A successful transport response is not proof that the operation state
is `completed`. `unreal_inspect_blueprint` returns variables, components, graphs,
node IDs, pin types/defaults/links, compilation status and truncation indicators.

The current function set covers approved actor transforms/visibility, pure native
math/string functions, and PrintString/PrintText/IsValid. It excludes arbitrary Python,
console execution, and editor scripting escape routes. Broader existing Blueprint
editing, arbitrary node families, component property assignment, GAS and UMG are still
being developed. This version does not expose every Unreal operation.

## Blender scene recipes

`blender_inspect_object` returns transforms, mesh counts, materials, modifiers,
collections and Action identity. `blender_inspect_rig` reads an explicit armature's
bone hierarchy and related meshes; optional skin-weight summaries are capped at
256 bones, 32 related meshes, 100000 total vertices, and 2 million vertex-group
assignments per query. `blender_preview_scene`
accepts 1–32 typed operations:

- `create_mesh`: bounded vertices/faces, optional collection and transforms.
- `set_vertices`: matching vertex-count edits; copies existing mesh data first.
- `set_transform`: location, Euler rotation in radians, and nonzero scale.
- `create_material` / `assign_material`: RGBA base color and mesh material assignment.
- `create_collection`: adds a new collection to the active scene.
- `keyframe`: location, rotation_euler or scale at an explicit frame.
- `bone_keyframe`: location, Euler rotation, normalized quaternion rotation, or scale
  keyframes on an exact pose bone in an armature. Euler/quaternion mode must match the
  bone's current rotation mode; scale components cannot be zero.
- `scene_settings`: FPS, frame start and frame end.
- `set_material_input`: bounded numeric/vector/RGBA input defaults on approved native
  nodes in an existing local material; preview reports shared object users.
- `duplicate_object`: new named copy of a local mesh/empty, with independent mesh and
  Action data; optional destination collection and local transforms. Mesh duplication
  is bounded at 100000 vertices. Source geometry/animation changes invalidate previews.

Apply requires the reviewed preview ID as confirmation. It rechecks the scene
fingerprint and rejects stale or replayed plans. Existing mesh and Action datablocks
are preserved through copies before editing. Failed batches restore object and pose-bone
state, material defaults, and scene timing and remove only newly created datablocks;
rollback failures report
`partial`. Results name preserved datablocks. The tool does not save a `.blend` file.
There is no raw Python execution endpoint. Large mesh transfer, rig construction and
weight editing, modifiers, existing material graph editing, and export/import remain
in development.

### Shader graph creation and inspection

`create_material` can provide `shader_nodes` (at most 32) and `shader_links` (at most
64). Graphs are built only on a newly created material. Node IDs are unique identifiers;
each custom graph has exactly one material output. Links name their source/target node
and socket identifier or unique socket label. Repeated socket labels require identifiers,
which the inspector returns. Cycles, duplicate targets and nonallowlisted node types
are rejected. Structural checks happen at preview; native socket/type/default validation
happens during apply and any failure invokes whole-batch rollback.

The native node allowlist contains Material Output, Principled BSDF, RGB, Value,
Math, Mix RGB, Noise Texture, Texture Coordinate, Mapping, Bump, Vector Math, Separate
XYZ and Combine XYZ. Numeric input defaults are bounded and dimensions must match
native sockets. RGB and Value nodes accept `outputs` defaults for their native
constant sockets, so constants can feed color/scalar graph connections. Other node
types cannot set output defaults. Math/vector/blend operations use explicit allowlists. Script nodes,
external file inputs and arbitrary properties are absent. Existing material input
defaults can be edited; adding/removing existing nodes and links remains unsupported.

`blender_inspect_material` returns node types/IDs/positions, input/output socket
identifiers/types/defaults, link endpoints/validity and material identity. It caps
inspection at 64 nodes, 32 sockets per direction per node, and 128 links, with counts
and truncation flags. Apply returns the resulting new material graph inspection.

## Unreal Asset Registry queries

`unreal_search_assets` queries native registry metadata on the editor game thread.
It accepts a content directory (default `/Game`), an exact native `/Script/` class
filter, case-insensitive name substring, recursive path flag, limit (1–200) and offset
(0–100000). Results are sorted by object path and report total count, next offset,
truncation and registry-loading state. Changes to the live registry between pages
can shift results. Registry loading can make any query incomplete.

`unreal_inspect_asset` accepts a package path or object path and returns registry
metadata, at most 64 tags (values capped at 512 characters), and bounded package
dependencies and referencers. These are registry package references, not live UObject
references or editable property values. Neither command loads, compiles, saves or
changes assets. Native requests reject unknown fields and require exact JSON types.

## Unreal actor recipes

`unreal_inspect_actor` resolves an exact actor path in the loaded editor world and
returns GUID, class, label, world transform and game-hidden state. It does not expose
arbitrary editable UObject properties. `unreal_preview_actors` accepts 1–32 operations;
`unreal_apply_actors` consumes its session-local ten-minute preview with matching
confirmation. It rejects changed target/world state and editor PIE contexts.

- `spawn`: native StaticMeshActor, PointLight, SpotLight, DirectionalLight or
  CameraActor, with optional label, world transform and game-hidden state.
- `transform`: changes an exact existing actor path's location, rotation and/or scale.
- `visibility`: changes `hidden` (game-hidden state, not editor viewport visibility).

Location uses centimeters, rotation is `[pitch, yaw, roll]` in degrees, and scale
must be nonzero. Existing actor edits require a root component and no attach parent.
Native transactions support editor undo. Failed batches restore recorded transforms
and hidden state and remove newly spawned actors; rollback status is explicit. No
level is saved and no deletion, arbitrary class execution or generic property setter
is exposed. Rollback of values does not promise to reverse external side effects of
an existing actor's editor callbacks. Inspect returned state and actor facts.

## Version-aware API retrieval

`forge_search_api_docs(application, version, query, limit)` retrieves local reference
chunks for an exact major.minor.patch version. It uses SQLite FTS5 lexical retrieval
for client-side RAG, without cloud APIs or embeddings. Unreal indexing reads the
installed official Python stub as text and never imports it. Blender export reads RNA
and Python API reference metadata in a separate factory-startup process. Source text
is reference data, never an instruction or permission to execute code.

```powershell
& 'E:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python "$PWD\scripts\blender_export_api_docs.py" -- "$PWD\Saved\Knowledge\blender-5.2.2.jsonl"
.\.venv\Scripts\python.exe scripts\index_api_docs.py --unreal-engine 'G:\Program Files\EpicGames\UE_5.6' --blender-jsonl Saved\Knowledge\blender-5.2.2.jsonl
```

The index is project-local under `Saved/Knowledge`, excluded from Git and plugin ZIPs.
Wrong-version searches return no results; there is no silent version fallback. An API
appearing in documentation does not grant an adapter capability. Verify actual native
support before constructing a recipe. Generated references retain upstream ownership.

## Recovery and validation

Requests remain bounded at 16 KiB. Split overly large tasks into supported operations;
there is no silent truncation of mutations. Apply exchanges allow 60 seconds; a timeout
reports `outcome_unknown`. Inspect before retrying because the preview may be consumed
and the application may have completed the change. Inspection exchanges remain 10 sec.

Native tests use isolated projects and factory scenes. Run `verify_blender_recipes.py`
in background factory Blender, and `verify_engineering_live.py` only with its guarded
`Saved/Milestone2/HostProject` sessions. Evidence and current gaps are recorded in
[Development_Status.md](Development_Status.md). No visual panel click-through or
gameplay execution claim follows merely from successful compilation and placement.

## Existing Blueprint graph edits

`unreal_preview_blueprint_edits` and `unreal_apply_blueprint_edits` edit an existing,
successfully compiled normal `/Game` Blueprint in an idle editor. Recipes can add
bounded primitive variables and native ActorComponents, plus allowlisted event, custom
event, variable get/set, branch, sequence, self, reroute and
native function nodes, then wire those nodes by temporary recipe IDs. Operations can
also move approved existing nodes, set validated input defaults, and connect/disconnect
inspected pins. Results return native node GUIDs for follow-up edits. The tools do not
add/delete existing variables, components, functions or arbitrary node families.

Preview records graph state, compilation status, dirty state and editor identity;
changes to that recorded state invalidate apply. It does not fingerprint every
Blueprint property or component default. Apply requires the one-use matching preview
confirmation, writes a bounded Blueprint-state recovery journal under the project
Saved directory, performs a native transaction, and compiles the result. Failed
batches restore recorded graph state and recompile; recovery failures report partial.
Schema-generated conversion nodes are removed during recovery. The journal is not a
full binary asset backup. Existing asset files are never saved by these edit tools.
Interactive editor Undo and runtime Blueprint behavior require separate validation.

Existing Blender material input edits report shared object users before apply and
restore input defaults after a failed batch. Material graph inspection and the edited
socket values participate in preview staleness checks; not every shader property is
fingerprinted. No material render or saved-file acceptance is implied.
