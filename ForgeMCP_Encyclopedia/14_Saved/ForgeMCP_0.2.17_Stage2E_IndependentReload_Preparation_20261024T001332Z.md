# ForgeMCP 0.2.17 — Stage 2E Independent Reload Preparation

Prepared: 2026-10-24 00:21 UTC  
Verdict: **PASS — PREPARED; NEW OWNER LAUNCH APPROVAL REQUIRED**  
Unreal Editor launches during this preparation: **0**  
Independent reload result: **NOT TESTED**

## 1. Production Editor identity

Fresh ForgeMCP discovery found one connected Unreal Editor: `unreal-43744`, PID `43744`. A fresh project read confirms `G:/ForgeMCP/ForgeMCPDev.uproject`, `/Game/Levels/L_City_World_Master.L_City_World_Master`, UE `5.6.1-44394996+++UE5+Release-5.6`, and PIE stopped. The native plugin health reports `0.2.17-alpha.1`. A targeted operating-system process query also confirms PID 43744 uses the installed UE 5.6.1 executable and the expected production project command line.

ForgeMCP's stdio host reports version `0.3.15`; that is the host server version. The Unreal adapter loaded in the Editor reports `0.2.17-alpha.1`.

## 2. Fresh Landscape and production package checks

The current native Landscape inspection reports:

| Check | Current read |
|---|---|
| Landscape GUID | `BD45FDD94EC2A29617B50794F2DE4E9D` |
| ForgeTerrain GUID / full-height MD5 | `2E6FC5F94C4EF704F700299B5D08C23B` / `08cbe382a59441d8148a674cf0d83851` |
| Original Layer GUID / full-height MD5 | `198824024FF8A77A01535B86021D9B34` / `9f43572fbc2c06ef497da015879cdb23` |
| ForgeTerrain depth | minimum `-100 cm`, maximum `0 cm` |
| Streaming proxies | 16 loaded, 0 unloaded |
| Registered Landscape / collision components | 64 / 64 |
| Landscape dirty / layers up to date | false / true |

A fresh bounded ForgeTerrain read of `[1042,1065,1098,1075]` returned 627 samples and MD5 `3817bd2c18535a9b4529387de493f2b9`. Every sample matched the prepared expected read. This read includes the two saved extensions: their 120 modified vertices match the expected values, and all 101 pre-existing carved vertices remain unchanged. This is fresh production readback; it is not evidence from an independent reload.

A fresh complete loaded-package inventory scanned 1,236 packages, with no errors or additional pages. It found no dirty project Content packages. The sole dirty package was compiled-in engine script `/Script/SlateCore`, classified outside production Content. Loaded-package inventory does not classify unloaded packages as clean.

The final production recheck is summarized in [production_readonly_verification.json](../ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/production_readonly_verification.json).

The two affected saved Landscape files retain their previously verified values:

| Source package | Bytes | SHA-256 |
|---|---:|---|
| `Content/__ExternalActors__/Levels/L_City_World_Master/5/K5/KSDE1ZCJBZNOS07IF93SI2.uasset` | 609,966 | `01bcd92c87e93b000811a863b88701ec845ff0e7487c868f0ccb92a46a955b61` |
| `Content/__ExternalActors__/Levels/L_City_World_Master/9/84/999V7M34APSAN5HR9UR7RT.uasset` | 5,063 | `9455276756f9b78c36e6c7fc732cadf4b3a486ab9d2237c81917d4677e3022df` |

The first is the streaming proxy package changed by the approved edit and owner save. The second is the Landscape root package, whose bytes matched its earlier baseline despite a recorded save rewrite.

## 3. Current source and historical checkpoint evidence

The new source manifest contains 1,745 files totaling 5,094,258,538 bytes across `Content`, `Config`, `Binaries`, `Plugins`, `Source`, and `ForgeMCPDev.uproject`. The copy-preparation script rehashed the source after copying and found it unchanged. Free space before the copy was 171,667,668,992 bytes; after it was 166,566,924,288 bytes. The pre-copy available physical memory reading was 19,757,168 KiB.

The six historical recovery manifest SHA-256 pins were freshly checked and match:

| Checkpoint | Manifest SHA-256 |
|---|---|
| Stage 1 | `d9de66d61745427b313c5ee7eb5a1f2238d8c76ca2dc5aa0cd277929bbac3388` |
| Native adoption | `e7e95ea63026d16a2c829a5cb9e90eda5633175f35e65075f84235604969123f` |
| Post adoption | `c3ec68f538425c600bc10981e0ad519d35371a3920839f2c722b1a3e1b861fc1` |
| First riverbed | `e48b4397d48971919004002b8ddfbaa7f62546b50ef243b46d921f17f229c0cc` |
| Approved multi sculpt | `f77b772e73774f1516b9fb94ecfd73584ccffa482ecabd92bc92e400a9181ed5` |
| Activation | `3f42b6a4243a0ef197417ab4ee7d13fa01cc68621ec7bf4779875fd305e29aa0` |

This verifies the preserved manifest pins. Historical checkpoint payloads were not restored or rewritten.

## 4. Fresh independent project copy

New test root:

`G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z`

Independent project:

`G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/isolated_project/ForgeMCPDev.uproject`

The new copy uses ordinary file copies. The preparation verified that source and destination files have different filesystem identities, each copied file has one link, and no symlinks, junctions or reparse points are present. Clone `Content` is read-only. Independent `Saved`, `Intermediate`, logs, temporary files, user data, local app data, private DDC, and private Unreal session registration paths were created under the new root. The private registration ACL has inheritance removed and grants access only to the current owner and SYSTEM.

The only source-to-clone changes are the two documented editor configuration files: `Config/DefaultEngine.ini` for private DDC and proxy loading, and `Config/DefaultEditorPerProjectUserSettings.ini` for autosave/tab restoration and Live Coding settings. Production files were not changed.

The final independent audit hashed all **1,745 source files and all 1,745 clone files**, with zero hash mismatches, additions or missing files. Results are in [final_readonly_manifest_audit.json](../ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/final_readonly_manifest_audit.json).

## 5. Engine, plugin, dependencies and private DDC

The installed UnrealEditor executable SHA-256 is `aa27ca8afea076e7310535c8a50d9f7589a2e011175e8ae1b73dff8766f53007`. The copied project and Forge module BuildIds are `43139311`, matching the installed Editor. The copied plugin descriptor identifies ForgeMCP `0.2.17-alpha.1`. All enabled project plugin descriptors and the required `WebBrowserWidget` dependency are available. The project has no `AdditionalPluginDirectories`.

The selected graph and both fallback sections resolve as:

```text
Root=(Type=Hierarchical,Inner=EngineReadPak,Inner=Stage2EAlphaLocal)
EngineReadPak=(Type=ReadPak,Filename="G:/Program Files/EpicGames/UE_5.6/Engine/DerivedDataCache/Compressed.ddp",Compressed=true)
Stage2EAlphaLocal=(Type=FileSystem,Path="G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/ddc",ReadOnly=false,DeleteOnly=false,Clean=false,Flush=false)
```

The selected `Stage2EAlphaPrivateDDC`, `InstalledDerivedDataBackendGraph`, and `DerivedDataBackendGraph` sections use that graph. No path override hooks, shared writable Zen/cloud backend, or writeable pak backend were found. The independent user, local app data, temp, registry and logs paths are under the new root. The installed engine runtime and read-only cache pak remain shared dependencies; this is an isolated project/cache setup, not a separate OS account or complete filesystem sandbox. Runtime DDC selection is not tested until an approved launch.

## 6. Hardened controller review and dry run

The revised controller is [run_revised_once.py](stage2e_controller_hardening/run_revised_once.py); the process observer is [worker_observer.py](stage2e_controller_hardening/worker_observer.py). The earlier broad repeated CIM worker query is removed. Worker polling uses a separate Toolhelp snapshot process with a three-second timeout; initial root command-line verification is a targeted PID query with a four-second timeout. The controller caches handles and creation identities, checks exact executable paths and parent ownership, excludes the current production PID, uses a 900-second startup limit and has no retry path. It verifies controller/observer file hashes and the new plan's source/clone manifest pins before a launch.

Before shutdown it takes another bounded worker snapshot. It stops the root only after checking the retained handle, creation identity, executable and exact isolated project command line; it stops workers only through retained handles after identity checks. It then performs a bounded post-shutdown snapshot. Any timeout, identity failure or surviving candidate is reported as incomplete. The controller never terminates by process name.

The initial command-line verification failure path remains intentionally fail closed. If that targeted four-second query cannot prove the root command line, the controller records the identity observation failure and refuses to terminate that process. Manual handling: preserve the controller and Editor logs and the reported PID; inspect that exact PID's executable path, creation time and full command line with a process inspection tool; terminate it only if it is conclusively the disposable clone process and its PID/creation identity match the launch evidence. If identity remains uncertain, leave it running and ask the owner to resolve it. Never use a name-wide `taskkill` command.

Offline verification completed:

- **17/17 synthetic tests passed**, including worker query timeout, PID reuse, exited or missing worker, multiple workers, wrong executable, wrong parent, exited parent, production PID as worker or root, wrong project command line, shutdown target selection and the 900-second deadline. No real process was terminated.
- Python AST parsing passed.
- The bounded Toolhelp helper completed a read-only snapshot within its limit.
- Running the controller without `--execute`, new plan root and new approval ID stopped at argument parsing before any Editor launch.

Individual test evidence is in [offline_test_results.json](stage2e_controller_hardening/offline_test_results.json). These tests do not prove live Unreal startup or runtime DDC behavior.

## 7. Exact pending launch plan

The complete machine-readable plan is [revised_launch_plan.json](../ForgeMCP_Recovery_Checkpoints/Stage2E_Alpha_20261024T001332Z/revised_launch_plan.json). Its SHA-256 is `a7b72ec6dcead47e5533dff2243cf4aefffc72e4004a0fa3dcffd661ed000635`. Source manifest SHA-256 is `6e05f0fde1dc4eabe61e0072086aa19b407949809006563cf232b9424a7062f0`; clone manifest SHA-256 is `046237058693c9aaabe22f9126ff4c13cd4fde42672a18cd0a1243896ef92cbd`. Revised controller SHA-256 is `fbd795703209642fefa9de50699da7ae0e281247da6f0aaf3838b20be55723cc`; worker observer SHA-256 is `d256a2b6372250184c49801f1dee9216888371dd1f11a53f4dc9ea148607dfa1`.

Exact Editor arguments prepared:

```text
"G:\Program Files\EpicGames\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe" "G:\ForgeMCP_Recovery_Checkpoints\Stage2E_Alpha_20261024T001332Z\isolated_project\ForgeMCPDev.uproject" /Game/Levels/L_City_World_Master -Unattended -SCCProvider=None -DDC=Stage2EAlphaPrivateDDC -UserDir=G:\ForgeMCP_Recovery_Checkpoints\Stage2E_Alpha_20261024T001332Z\user -abslog=G:\ForgeMCP_Recovery_Checkpoints\Stage2E_Alpha_20261024T001332Z\logs\UnrealEditor.log
```

The reviewed controller entry point, after a new owner approval is recorded in the new plan, will be:

```text
python -B G:\ForgeMCP\Saved\stage2e_controller_hardening\run_revised_once.py --execute --plan-root G:\ForgeMCP_Recovery_Checkpoints\Stage2E_Alpha_20261024T001332Z --approval-id <new-owner-approval-id>
```

One attempt maximum, 900-second startup limit, ordinary rendered startup, no automatic retry. The plan currently says `PREPARED_AWAITING_OWNER_APPROVAL`; its approval ID is null. No approval marker was created and no authorization was consumed. Immediately before any future launch, reauthenticate production and recheck the plan's PID, source and clone hashes, dirty inventory, Landscape state, DDC configuration and available resources. If any differ, stop and refresh the plan for review.

## 8. Preservation and remaining limits

Production remained connected and operational at the final check. Its Landscape and clean Content state still match the values above. Source-to-clone audit passed. This preparation made no production save, terrain operation, editing-session request, Editor launch, checkpoint restore or checkpoint cleanup. Historical checkpoints were left in place.

The following still require a separately approved isolated launch: runtime private DDC confirmation, target map load, independent disk-backed Landscape hash and exact sample verification, close-up visual connection review, and actual collision behavior. Stage 2E and Phase 6C acceptance remain unclaimed.

**Readiness: PASS — all preparation gates completed. Launch is awaiting new explicit owner authorization.**
