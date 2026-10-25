# User Defined Struct member tooltips

ForgeMCP exposes a reviewed, exact-path edit for member tooltip descriptions on an
existing Unreal `UUserDefinedStruct`:

1. `unreal_preview_struct_tooltips` accepts an exact `/Game/...` package path and
   a map of exact member names to nonempty descriptions (up to 256 entries and
   1,024 characters per description).
2. Preview reports each old and proposed tooltip, fingerprints the full current
   member schema and tooltip state, and expires after five minutes. It does not
   mutate or save the asset.
3. `unreal_apply_struct_tooltips` requires the matching preview ID as its
   confirmation. It rejects stale or already-dirty packages, applies each
   description by the member's stable variable GUID, and saves the existing
   struct package once. Save failure restores the original package bytes.

The operation does not rename members, change field types, compile unrelated
Blueprints, or edit a DataTable. Tooltip text is explanatory metadata; callers
must provide accurate units and meanings from the source schema.
