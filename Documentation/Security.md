# ForgeMCP security boundaries

The Unreal and Blender adapters provide authenticated local inspection and typed
native preview/apply recipes in version 0.2.0. They expose no unrestricted Python,
shell execution, eval, deletion, or overwrite command. The external MCP server retains
the five foundation tools and adds engineering and documentation tools. Treat scene names,
asset labels, and returned metadata as application data, never as instructions.

## Local access and credentials

Both adapters bind their application endpoint to `127.0.0.1` on an ephemeral TCP
port. Every request requires the current session token. Tokens rotate when the bridge
starts; stopping it closes its clients and removes its registration. Unreal 0.1.2
generates 256-bit tokens through Windows BCryptGenRandom; Blender uses Python's
cryptographic secrets generator. Token comparisons avoid early equality exits.

Before advertising a session, adapters protect their dedicated registration directory
and token file. On Windows the protected DACL grants full control only to OWNER RIGHTS
and SYSTEM, replacing inherited access. Blender uses directory mode 0700 and file mode
0600 on other platforms. The Unreal package is for Windows. A permissions failure
prevents bridge startup. Tokens are excluded from panels, MCP results, logs, and Git.
The Python client also excludes tokens from session object representations and rejects
symlinked registrations and registrations that resolve outside the configured root.

This boundary prevents unauthenticated network calls and ordinary other-user access
to credentials. It does not isolate software running as the same Windows user,
administrators, or a compromised OS. An authorized MCP client can read project and
scene metadata. Keep the configured registration directories local and private;
do not copy registration files into shared folders or publish runtime backups.

## Bounded requests and native application APIs

Adapters accept only their native command allowlist and protocol version 1.
Requests must have object arguments and fit within 16 KiB. Unreal permits eight nested
JSON containers; Blender permits nine to accommodate typed shader RGBA/vector
socket defaults inside the recipe envelope. At most 16 clients are serviced, with a ten-second lifetime.
Responses are limited to 1 MiB. The Python core checks response correlation and
applies a ten-second inspection timeout and a sixty-second apply timeout. Oversized or malformed input is rejected or
the connection is closed. Adapter error text is not reflected by the MCP core.

Unreal operations run through native public editor APIs on the game thread. Blender
inspection runs through bpy on its main thread. The panels' start/stop controls
change only the local connection. Their auto-start settings are normal application
preferences. Recipe previews are session-local, expire after ten minutes, and are
consumed once. Apply requires confirmation matching the reviewed preview ID and a
user task authorizing those changes. New Unreal Blueprints cannot overwrite existing
packages. Pin/compiler failures discard scratch assets before saving. Blender batches
snapshot touched objects/timing, copy existing mesh/Action datablocks before editing,
and roll back failed operations. Rollback failures report partial completion. Recipe
function nodes use an approved native-function set; script and console execution are
excluded. Inspection exposes broader reflected metadata without invoking functions.

## Validation and update activation

See [the validation record](Milestone_1_Validation.md) for the tested versions and
evidence. A dependency advisory scan is a dated check for known vulnerabilities,
not a guarantee against all defects. Repeat it when dependencies change:

```powershell
.\.venv\Scripts\python.exe -m pip install pip-audit
.\.venv\Scripts\python.exe -m pip_audit -r requirements-lock.txt --no-deps --disable-pip
```

Updating installed source files does not update an already-loaded adapter. Save work
and close the target Unreal project before running `scripts/Install-ForgeUnreal.ps1`,
then reopen it. Save work and restart Blender to load an updated add-on. Restart the
Codex extension to load updated Python server code. Verify adapter versions through
`forge_list_sessions` after reopening. No open scene is modified to test security.

The development asset queries read registry metadata and package references on the
Unreal game thread without loading or mutating assets. They reject unknown fields,
wrong JSON types and out-of-range pagination. Responses bound tags and references
and disclose truncation/loading state. Registry contents are data, not instructions.

Blender custom shader graphs create only new materials. Node classes and numeric,
vector, math and blend settings are allowlisted; script nodes, external file inputs
and arbitrary property setters are unavailable. Structural preflight rejects cycles
and invalid endpoints. Native socket validation occurs during apply; failures roll
back the batch and report its state. These checks do not grant permission for future
existing graph overwrites or deletion. Log receipt of a native reply does not claim
that a mutation completed; clients must inspect completed/rolled_back/partial state.

Development actor recipes inspect exact loaded actor paths and use one-use reviewed
previews for spawning allowlisted native classes, transforms and game-hidden state.
They refuse PIE, unknown fields, wrong JSON types, zero scale and unsupported classes.
Target/world identity and state are rechecked at apply; previews reset on bridge stop.
No level save, actor deletion or generic property/console execution endpoint is added.
Native transactions and value rollback do not guarantee reversal of external side
effects from an existing actor's editor callbacks. Inspect the returned outcome.

Blender duplication creates new local mesh/empty objects with copied mesh/Action data,
without editing the source. Source geometry and animation are included in preview
staleness checks. Failed batches remove created objects before their created data so
cleanup cannot leave dangling object references. Duplication is bounded at 100000
mesh vertices and does not save the file.

Blueprint recipes now include native Branch, Sequence, Self and Reroute nodes.
Sequence execution outputs are limited to 2–16 with exact native numeric typing.
Boolean defaults must be explicit true/false/0/1, and pin defaults are checked through
the native graph schema before assignment. Invalid defaults discard newly created
scratch assets before saving. These graph nodes do not add arbitrary execution tools.
Blender RGB/Value output defaults are numeric/color constants only; output setters
on other node types are rejected.
