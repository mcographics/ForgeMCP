# Unreal actor and component property automation

ForgeMCP exposes three actor-property operations on a connected Unreal Editor:

- `unreal_inspect_actor_properties` reads bounded simple reflected values from one
  loaded level actor and reports whether each field is editable in the current
  Editor context.
- `unreal_preview_actor_property_edit` validates one proposed native property-text
  value and returns the current and proposed values.
- `unreal_apply_actor_property_edit` applies that single-use preview to the same
  actor and property after rechecking actor, class, world, current value and
  editability.

The component equivalents target one exact loaded actor component:

- `unreal_inspect_component_properties` returns a bounded page of simple
  reflected values and Editor editability metadata.
- `unreal_preview_component_property_edit` validates one proposed native
  property-text value and binds it to the exact component, owner, class, world
  and prior value.
- `unreal_apply_component_property_edit` applies the single-use preview after
  rechecking that identity and prior value.

Supported values are scalar numerics, booleans, byte/enums, names, strings, text,
vectors, rotators and colors. Arrays and nested objects are not traversed.
Property names are exact reflected identifiers; the adapter uses Unreal's own
`FProperty` parser and `CanEditChange` check. Apply records an Editor transaction,
emits property-change notifications, verifies the resulting value, marks the
level dirty and does not save it. Saving the level remains a separate, explicit
operation. Editability metadata does not guarantee every text representation is
accepted by Unreal's property parser; preview reports parser rejection before
mutation. Native bitfield booleans are handled through `FBoolProperty` and accept
`true`/`false` or `1`/`0`, then normalize to Unreal's lowercase boolean export.

Inspection and edit scope is the loaded actor instance in the current Editor
world. Play-in-Editor and stale actor/world/property previews are rejected. This
does not provide arbitrary UObject references, container traversal, batch edits,
disk backups or automatic level saving. Only components owned by actors in the
current loaded Editor world can be resolved.

The native MCP acceptance fixture uses an actor spawned only in a disposable UE
5.6.1 project. It queried the actual editable numeric fields, applied one property
change, read it back through MCP and rejected a competing stale preview. This is
headless native acceptance; interactive Details-panel refresh and actual Undo
behavior still need visible Editor verification.
