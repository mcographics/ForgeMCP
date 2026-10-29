# ForgeMCP Blender Integration Rules

This reference adapts the upstream workflow guidance to ForgeMCP. For all scene
access, follow [`forgemcp-blender`](../forgemcp-blender/SKILL.md) and the
[capability map](forgemcp-capability-map.md). Do not use instructions for another
Blender MCP server as a ForgeMCP tool contract.

## Execution order

1. Discover sessions with `forge_list_sessions`; rediscover with
   `forge_ensure_connected` when needed.
2. Select an explicit Blender session when ambiguous and verify its scene/file with
   `blender_scene_info`.
3. Inspect the relevant objects and data using ForgeMCP's typed read-only tools.
4. Plan production phases and match each intended native change to a supported tool
   schema.
5. Call the applicable preview tool. Review its exact returned changes.
6. Apply only user-authorized preview IDs, then inspect the affected data again.
7. Report persistence, export, render, and visual-review evidence as separate gates.

## Visual and persistence limits

ForgeMCP has no viewport screenshot tool. A scene read-back is not visual approval.
The render workflow runs from a saved snapshot and status can confirm process/file
metadata, but appearance needs an actually viewable render for human or visual review.
The scene recipe apply path does not save the active `.blend`; the `save_copy` creative
action writes a new file and rejects overwrites. Do not claim in-place save or reload
verification.

## Unsupported operation handoff

Never run `bpy`, `execute_blender_code`, arbitrary scripts, or a catalog entry marked
`discovery_only`. If ForgeMCP does not expose a needed operation, explain the exact
unsupported phase and give a useful specification or manual acceptance handoff.
