# UE 5.6 alpha.8 — connection indicator and Unreal-to-Blender send

## Changes

- Plugin `0.2.13-alpha.8` adds a status lamp beside the connection text in the
  Unreal ForgeMCP panel. Green pulses while a fresh authenticated heartbeat is
  present, yellow marks an interrupted/stale heartbeat, and red means the bridge
  is stopped or has not authenticated a ForgeMCP client yet.
- MCP server `0.3.13` deduplicates physical registration directories before
  selecting the Blender artifact staging root. Unreal and Blender can register
  under the same engine-wide user directory, which appears twice in the manager's
  configured root list. Counting list entries instead of unique folders caused
  the staging step to fail with `session_registration_unavailable`.

## Diagnosis evidence

The retained Unreal-to-Blender OBJ and FBX receipts show native export completed
with valid geometry and artifact hashes. Both then failed before import, at
`staging`, with `session_registration_unavailable`. No Blender object was
created by those failed attempts. Fresh FBX and OBJ previews both succeeded
against the current live Unreal and Blender sessions.

## Validation

- `tests/test_roundtrip.py` and `tests/test_ui_transfer.py`: 33 passed after the
  root-deduplication change.
- Full Python suite: 353 passed.
- Isolated UE 5.6.1 editor target build: passed (28 UBT actions).
- Alpha.8 archive package check and clean-project plugin load: passed.
- Package: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.8-UE5.6.1-Win64.zip`.
  SHA256: `b73a19c12f05c8a07816ef0c9beb9ca07c7167c2f8104078a8b98c90b962efc8`.
- Disposable Unreal and Blender end-to-end panel-worker transfer: FBX and OBJ
  both passed, including native export, staged artifact integrity, Blender import
  and geometry verification. User app sessions and scenes were not used.
- Alpha.8 installed engine-wide at
  `G:\Program Files\EpicGames\UE_5.6\Engine\Plugins\Marketplace\Forge` after
  the user confirmed Unreal was closed. The descriptor reports `0.2.13-alpha.8`
  (version 23); the installer preserved a reversible backup and modified no
  project files. Interactive visual verification of the lamp is pending the next
  Unreal launch.
