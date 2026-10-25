# OnTheGoNav repair — October 12, 2026

The user authorized repairs following a read-only analysis of the live OnTheGoNav
project. The existing Unreal 0.2.8 bridge was used through a fresh source MCP stdio
subprocess, targeting explicit session `unreal-5396`. No native plugin changes or
Editor rebuild were required for this repair.

## Navigation repair

The existing `/Game/OnTheGoNAV/OnTheGoNav_Component` Blueprint was backed up before
mutation to the project's `Saved/ForgeRepairs/OnTheGoNav-20261012/` directory. The
backup SHA-256 matched the original package:
`c567dc7fa4498bd05e58ddd92004c7fa3613010b0998d4f12c1118d875ec49f5`.

Reviewed native graph edits replaced `RefreshNav` input links from uninitialized
underscore-named duplicates with the configured `Scale Radius`, `Min Width`,
`Max Width`, `Min Height` and `Max Height` members. Radius passes through native
`FMax(Scale Radius, 1.0)` before division. Existing duplicate members and nodes
were preserved; their replaced data links are no longer used by this calculation.

Two new configuration variables feed the existing timer node:
`NavRefreshInterval = 0.0333333333333333` seconds and
`NavRefreshMaxOncePerFrame = true`. This replaces the effective 0.005-second input
with approximately 30 Hz and prevents more than one callback per rendered frame.
Native apply completed with zero compiler errors and warnings. All eight reviewed
connections were verified in both directions by inspecting their native pin links.

The user saved the Blueprint manually because the current edit tool does not save
existing assets, and Windows screenshot capture failed. The saved package hash is
`760dcca9397273886bce7d3cb653477e6e0f46ad08e303a02ad8fe16d73f1b21`.
The user then operated PIE for 12.254 seconds. That run's log contained zero
divide-by-zero warnings, zero Accessed None warnings and zero new handled ensures.
It did contain the missing tutorial-media error, before the file restoration below.
This is user-operated runtime log evidence; no automatic visual acceptance or
fresh-process Blueprint reopen was performed during this repair.

## Tutorial media restoration

The matching original videos were available in the user's separate SuperheroFlight
project. Seven MP4 files were restored to OnTheGoNav's
`Content/SuperheroFlight/Movies` folder and its project-relative compatibility folder
`SuperheroFlight/Movies`. Both locations matter here: native FileMediaSource resolves
Content first, while the running Editor had cached a project-relative fallback for
the missing ToggleFlightMode file. Each restored file was checked against its source
SHA-256; existing different files were never overwritten. Video playback and packaged
media cooking remain unverified after restoration.

## Server validation repair

Server source 0.3.2 accepts bounded exact names for existing Blueprint member
references containing spaces and existing function/collapsed graph names. Native
preview still resolves the exact graph/member against the actual asset. New variable,
function and callable names retain identifier constraints, and function-entry/result
nodes still require a function declared by the recipe. New Blueprint creation still
rejects undeclared graphs. Regression coverage includes control characters, bounds,
strict new-member/callable names and function-terminator restrictions.

The full Python suite passed: **297 tests**. Full Ruff checks passed. The source
subprocess exercised the repaired schemas against the existing Editor bridge. The
already running Codex host must reload before its advertised schema/version reflects
the server source change; no host refresh is claimed.

## Retained evidence and remaining issues

Token-free recipe, preview, apply, before/after graph inspection, saved read-back,
verification and movie checksum records are in `G:/ForgeMCP/Saved/OnTheGoNavRepair/`.
The original binary backup is inside the OnTheGoNav project Saved directory.

Extreme planet transforms and the earlier GPU precision ensure were not repaired:
changing the astronomical representation requires an intentional scene/rendering
design, rather than silently moving or shrinking the user's planet. Off-screen and
behind-camera marker behavior also remains open; this change fixes scaling and
refresh scheduling, not marker visibility policy. No world actor or level was edited.
