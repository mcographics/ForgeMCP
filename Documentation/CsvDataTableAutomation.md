# CSV to User Defined Struct and DataTable

ForgeMCP exposes `unreal_preview_csv_import` and `unreal_apply_csv_import` for a
connected Unreal Editor session. The preview reads a CSV through the native
Editor bridge, reports inferred field types and row count, and creates a
single-use, five-minute plan. Apply requires the same `preview_id` as
`confirmation`.

The native adapter accepts `.csv` files within the active Unreal project, up to
128 MiB, 200,000 data rows, and 256 columns. Headers must be unique Unreal
identifiers. The selected row-key column must be nonempty and unique. CSV
contents are fingerprinted at preview and rechecked at apply. Data Table
creation uses Unreal's CSV importer and fails if it reports import problems or
the resulting row count differs from the preview.

The operation creates a new DataTable. The User Defined Struct can either be
created at a new path or updated at an existing `/Game/` path. For an existing
struct, preview marks each CSV field as `preserve`, `add`, or `row_key`, and
records the exact struct schema. Apply refuses to proceed if that schema has
changed since preview. Existing members are preserved; missing CSV fields are
added. A same-named member with a different or unsupported type is a blocking
conflict. Existing member types are never changed, and additional existing
members are retained. The row-key column becomes DataTable row names and is not
added as a member. Other CSV columns retain their header names as variable
display names. Type overrides can select `string`, `name`, `bool`, `int`,
`int64`, or `double`. Without overrides, the preview scans every value:
boolean text maps to Boolean, integral values to Integer or Integer64 based on
range, other numeric values to Double, and mixed or empty columns to String.
Inferred values are suggestions; callers should review astronomical
measurements and identifier fields before applying.
The row-key column is not a struct field, so type overrides for that column are
rejected.

The destination DataTable must be new. Before changing an existing struct, the
adapter snapshots its member definitions and saved package bytes. It compiles
and validates the updated struct before importing the CSV; if import or save
fails, it attempts to restore the original in-memory schema and package. A
rollback failure is reported as `rollback_failed` and requires inspection in
the Editor before further work. Successful schema additions can affect assets
that use the struct, so preview results must be reviewed before apply.

Example preview request:

```json
{
  "session_id": "unreal-12345",
  "request": {
    "csv_path": "G:/Project/Dataset/bodies.csv",
    "struct_path": "/Game/Space/Blueprints/ST_CelestialBodyData",
    "data_table_path": "/Game/Data/DT_CelestialBodies",
    "row_key_column": "id",
    "type_overrides": {
      "distance": "double",
      "catalog_id": "string"
    }
  }
}
```

The apply result reports both asset paths, total struct field count, added
field names, DataTable row count, and whether an existing struct was updated.
The adapter never evaluates CSV content as code.
