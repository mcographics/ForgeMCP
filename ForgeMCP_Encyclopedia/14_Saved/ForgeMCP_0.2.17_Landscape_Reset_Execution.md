# ForgeMCP 0.2.17 — Controlled Landscape Reset Execution

Checked October 24, 2026. **Reset applied; subsequent manual save evidence verified in the live Editor and on disk. Independent disk reload remains untested.**

## Identity and scope

The existing Editor is `unreal-33500` / PID 33500, UE 5.6.1, ForgeMCP 0.2.17-alpha.1, project `G:/ForgeMCP/ForgeMCPDev.uproject`, level `/Game/Levels/L_City_World_Master.L_City_World_Master`, with PIE stopped. Landscape GUID is `BD45FDD94EC2A29617B50794F2DE4E9D`; ForgeTerrain GUID is `2E6FC5F94C4EF704F700299B5D08C23B`; Original Layer GUID is `198824024FF8A77A01535B86021D9B34`.

The 23-file pre-change checkpoint at `G:/ForgeMCP_Recovery_Checkpoints/LandscapeReset_PreChange_20261024T_Delta` was verified before the reset: all source and backup files matched the manifest, whose SHA-256 was `41ad3a15a126a4b2a3abe95ec796fa215388fc317504b20703c6d2403395baf4`.

## Authorization, preview and apply

Native read-only preflight passed. The owner entered the local approval command for fresh editing request `C2AC53D747098AB032CCF7AC5C97E03C`, bound to this Editor, Landscape, ForgeTerrain layer, `apply_heightmap`, and authorization region `[1042,1065,1098,1075]`. Native status confirmed approval. Native backup manifest SHA-256 was `8943c984442b6f6acab969d724489bb129e6e7fa0dfacbea7bada552f8515271`, with all 23 native backup/source MD5 pairs matching.

The owner separately approved preview `8D9EF2C849E712341EE2058A45F97015`. It set the inclusive rectangle `[1043,1066,1097,1074]` to 0 local cm: 495 samples, including 197 negative-to-zero changes, with the surrounding guard ring left at zero. The 627-sample bounded MD5 changed from `0bce98df53283065e7a173d2d0c56d73` to `16146c02a58a89bdd7968848bbd0b8d6`. One native apply completed, all 9 rows succeeded, and native height readback validated the after hash. The editing session was then revoked before saving; status recorded one completed operation and no active operation.

Fresh post-apply bounded readback found 627/627 values at zero. ForgeTerrain full-height MD5 became `9f43572fbc2c06ef497da015879cdb23`; the Original Layer retained the same MD5. Landscape identity and topology remained 16 loaded / 0 unloaded streaming proxies, 64 registered Landscape components and 64 registered collision components. Layers were up to date.

## Save sequence and later recheck

The owner approved save preview `79983ddf41feddb61100c8a840dfe2a2`, which marked only two current-level external-actor packages for saving. Its single native apply returned `stale_preview` and a failed/uncertain receipt. Read-only reconciliation recorded `recorded_state=failed`, no saved-package receipt, `native_package_contents_verified=false`, and `automatic_native_replay_allowed=false`. No automatic retry occurred. Immediately afterward both packages remained dirty and their production disk bytes still matched the pre-change checkpoint.

A later fresh recheck shows the state changed. A complete native loaded-package inventory inspected 1,192 packages with no errors, no further pages, and only compiled-in `/Script/SlateCore` dirty. Zero production Content packages were dirty. The two affected production files exist and have October 24, 2026 06:50:06 UTC write timestamps. The Editor log records both production `LogSavePackage` output moves at 06:50:06, after the failed apply. The recheck does not attribute those writes to the failed MCP operation; they are consistent with a separate Editor save.

| Package suffix | Current size | Current SHA-256 | Comparison with pre-change |
|---|---:|---|---|
| `5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset` | 608,273 bytes | `9beb914c699e5d5bfd3e181ffa73275e93550953b578afef3c59382e0209c9a1` | Changed from 610,905 bytes / `40fe8daa2c0a88bbea0e9cc33a97ec639dc99b53a2c23d673febb46c0047fd3d` |
| `9/84/999V7M34APSAN5HR9UR7RT.uasset` | 5,063 bytes | `9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df` | Byte-identical to the pre-change file, although the Editor logged a rewrite |

Fresh live native Landscape inspection after these file writes reports the same GUIDs, both full-height layer MD5 values `9f43572fbc2c06ef497da015879cdb23`, both layer elevations 0/0 cm, Landscape clean, layers up to date, 16 loaded proxies, and 64/64 registered Landscape/collision components. Thus the intended reset remains present in the loaded Editor and the affected packages are currently clean. The changed proxy bytes and save log support serialization of the reset; no independent process has loaded the saved disk files to verify their height content.

## Verdict and boundary

**RESET COMPLETE AND SAVED — within live Editor, package-state, save-log, and disk-file evidence.** The earlier MCP save attempt failed; the subsequent production file writes occurred later. Independent disk-reload persistence, close-up visual review, and actual collision-height behavior remain separate acceptance gates. No repeat sculpt, save retry, Editor launch, terrain repair, checkpoint restoration, or plugin change was performed during the recheck.
