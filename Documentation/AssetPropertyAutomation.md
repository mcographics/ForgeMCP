# Unreal asset property operations

ForgeMCP exposes bounded inspection and reviewed in-memory edits for assets under
`/Game` and `/JasperPrism`. These operations run on the Unreal Editor game thread.
Loading the selected asset may load its normal dependencies. ForgeMCP does not walk
object references or inspect container contents through these commands.

## Inspect

`unreal_inspect_asset_properties` returns simple reflected values for one exact asset:
booleans, numeric values, enums, names, bounded strings and display text, `FVector`,
`FRotator`, `FLinearColor`, and `FColor`. Each value includes its reflected C++ type
and editor editability flag. Complex structs, arrays, maps, sets, object references,
transient fields, and fixed arrays are omitted and counted. Results are limited to
200 entries; integer values are decimal strings so 64-bit values remain exact.

## Review and apply one edit

`unreal_preview_asset_property_edit` takes an exact asset path, reflected property
name, and a value string in Unreal's native property text syntax. The property must
be a single editable instance property of a supported type. The native adapter parses
the proposed value using the selected property's own `FProperty`, rejects non-finite
numeric/vector/color values, and returns normalized current and proposed values.

Example:

```json
{
  "session_id": "unreal-12345",
  "request": {
    "asset_path": "/Game/Props/SM_Rock.SM_Rock",
    "property_name": "LightMapResolution",
    "property_value": "128"
  }
}
```

Pass the returned `preview_id` as both `preview_id` and `confirmation` to
`unreal_apply_asset_property_edit`. The preview expires after five minutes and is
single-use. It binds the loaded object identity, class, property and current value.
Apply rejects stale previews, dirty packages, properties that are no longer editable,
and assets that cannot participate in an Unreal editor transaction. The apply enables
`RF_Transactional` on the loaded object when needed, records an Editor transaction,
sets the property, calls Unreal's edit notifications, and verifies the normalized
result. The transaction flag remains on that loaded object. The adapter reports that
it recorded a transaction; interactive Undo behavior is a separate acceptance check.

The command changes memory only and reports `package_dirty: true` and `saved: false`.
It never saves or overwrites the asset package. Inspect the result, then save through
the Editor when the user authorizes persistence. Saving, disk backups, complex
property editing, object-reference assignment, and batch edits are not implemented.

The property acceptance fixture uses a disposable UE 5.6.1 project and real MCP
stdio. It verifies a `StaticMesh` integer edit, reinspection, native transaction
tracking, invalid and non-finite values, confirmation, replay, stale-preview and
dirty-package rejection. The user's JasperPrism project was not used for mutation.
