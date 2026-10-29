# ForgeMCP Codex Blender Skills Integration

Date: October 29, 2026
Status: Repository skill and documentation integration; Blender runtime unchanged.

## Source and author credit

The integration incorporates the 94-skill Blender Skills pack by **Arjun Shukla**
([GitHub `@arjun988`](https://github.com/arjun988), [original repository](https://github.com/arjun988/blender-skills)).
The imported snapshot is commit
[`8f778d2405a214b508d4c7d80742be8e43acdd52`](https://github.com/arjun988/blender-skills/commit/8f778d2405a214b508d4c7d80742be8e43acdd52).
The upstream MIT license is preserved in `LICENSES/blender-skills-MIT.txt`, with
attribution details in `LICENSES/blender-skills-notice.md`.

## What changed

- Added all 94 upstream specialist skills and their shared reference material under
  `.agents/skills`, the repository-local Codex skills directory.
- Added the ForgeMCP `forgemcp-blender` skill and a current capability map for session
  discovery, scene inspection, supported typed recipes, creative previews, static-mesh
  transfer, render jobs, and evidence limits.
- Adapted the upstream MCP execution and tool references to ForgeMCP. The instructions
  now route Blender work through ForgeMCP's native preview/apply tools and prohibit
  using an unrelated MCP adapter or arbitrary `bpy` execution.
- Updated the ForgeMCP `AGENTS.md`, README, and encyclopedia indexes to route future
  Blender work through the bridge skill and record this integration.

The active Codex skill inventory lists the repository-local skill directory and the
ForgeMCP bridge skill, confirming project skill discovery.

## Acceptance and limits

Structural validation found 95 skill manifests total: all 94 upstream skills and one
ForgeMCP skill. Names are unique and match their directories; all relative Markdown
links resolve; the vendored MIT license is byte-identical to the upstream license.
No Python host, Blender add-on, Unreal plugin, or MCP adapter code changed. This
integration does not add Blender operations or claim support for every workflow in the
production skills. Python tests and an Unreal target build were not relevant to this
documentation-only change.

The ForgeMCP bridge preserves its existing evidence boundaries: scene apply does not
save the active `.blend`; a render-job result does not establish visual approval; and a
static-mesh export is not proof of Unreal import. Unsupported workflow phases remain
explicit and require separate acceptance.
