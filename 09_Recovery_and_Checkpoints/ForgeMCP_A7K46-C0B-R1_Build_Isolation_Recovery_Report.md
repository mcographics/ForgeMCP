# ForgeMCP Stage A7K46-C0B-R1 — Build Isolation Recovery

Date: 2026-10-22  
Engine target: Unreal Engine 5.6.1  
Disposition: **BLOCKED. Cargo was safely excluded and UBT log routing into the C0B root was verified, but the build used Unreal Build Accelerator and wrote runtime state outside the approved root. A StageA7G UBT run marker was also written outside the root. No complete native compile was produced. No Editor, ForgeMCP host, A7K41 project, or production project was launched or contacted.**

## Result

The missing `KitBash3dUsdTools` module comes from the Unreal Engine Cargo plugin, not ForgeMCP. The candidate project can exclude Cargo for its own build: `-DisablePlugin=Cargo` let UBT proceed beyond the original plugin-resolution failure. The disposable `.uproject` already pins its project-local `MajesticForge` plugin at descriptor version `30` so it wins over the older `0.2.13-alpha.9` plugin present in the StageA7G engine.

UBT’s `-Log=<path>` option routes its primary log to an explicit path, and a no-build `Query Capabilities` probe demonstrated that the global and per-mode logs can be kept under the C0B runtime root. That did not contain all UBT side effects. A first target build failed on paths longer than 260 characters. A retry using a temporary `R:` alias got past that check, then UBT started Unreal Build Accelerator (UBA), whose log reported a listener on `0.0.0.0:1345` and a root under `C:\ProgramData\Epic\UnrealBuildAccelerator`. UBT also wrote a 36-byte run marker under the StageA7G engine’s `Engine\Intermediate\UbtRuns` directory. Those effects are outside the approved C0B root. I interrupted that build and stopped further UBT work as required by the isolation boundary.

The `R:` alias has been removed, the build process exited, and a passive port check found no remaining listener on 1345. The out-of-root marker and UBA directory were left untouched. The marker’s unique name and timestamp match the retry, but there was no pre-build snapshot for that exact path; its prior existence is therefore unverified. The UBA `sessions` directory has no files after the interruption, but its prior existence is also unverified.

## Environment and source integrity

The exact path written in the request, `G:\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1`, is absent. The existing C0B environment shown by the IDE and filesystem is `G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1`; that existing environment was reused. No new Unreal installation or large development workspace was created.

The source-copy manifest remains SHA-256 `FDFC716DCC2B4A6D083E9307A0F354F6120216D44E9ECD0B931250FD266AB643` and describes the original 355-file, 8,214,630-byte source copy. Seven previously modified tracked source files still match the original repository’s manifest hashes. The C0B candidate source contains the seven intended modifications plus the two new `ForgeWorldSaveScope.cpp/.h` files. Current `.pytest_cache`, `.ruff_cache`, and Python bytecode files are local validation artifacts. The project-local Forge plugin source remains synchronized with the candidate source: 61 files checked, zero hash mismatches.

No ForgeMCP source file or plugin binary was changed during R1. The disposable project descriptor already contains the `MajesticForge` version pin; its current SHA-256 is `EA8FAFB37836F21FCC7A166C9C11231BD5D41B66DAEB699564792C104CF4830C`. The project-local plugin descriptor is `0.2.16-alpha.1`, numeric version 30. The StageA7G engine-level plugin is the older `0.2.13-alpha.9`, numeric version 24.

## Dependency and log-routing findings

The official UE 5.6 installation’s `Engine\Plugins\Marketplace\Cargo\Cargo.uplugin` enables Cargo by default and declares the Editor modules `KitBash3dUsdTools` and `KitBash3dUsdImporter`. The first C0B build failure named `KitBash3dUsdTools` through `Cargo.uplugin`. ForgeMCP’s descriptor and `MajesticForge.Build.cs` do not depend on Cargo or either KitBash module. Cargo can therefore be excluded for this isolated target without changing the engine plugin or any shared project configuration. The StageA7G UE 5.6.1 engine used for R1 has no Cargo plugin directory; the target invocation still included the scoped `-DisablePlugin=Cargo` flag.

Local UE 5.6 UBT source declares `-Log` as a global option and supports explicit XML configuration-cache input. The existing C0B `XmlConfigCache.bin` was passed with `-XmlConfigCache`; it remained unchanged at 354 bytes, SHA-256 `0CB1ADE885A5010A5E1C938D6BCBEFF5F50D4B9101A8FACC9252C8B51C6BAB93`. The bounded no-build query proved these log files stayed under C0B:

| Log | Size | SHA-256 |
|---|---:|---|
| `runtime\logs\ubt\C0B-R1-UBT-query-global.log` | 2,480 bytes | `4F3B5B4AB276D2B74796AE42DB9D5817E105676EFBC1DEC90C7F4205BC38521D` |
| `runtime\logs\ubt\query-mode-r1\Log_Capabilities.txt` | 423 bytes | `BB4833405C0D5BBF0CBDFBA01CE41F2D981F2E2E31812EAFB27E69ADA7AC3240` |

This validates explicit log paths for the tested query mode only. It does not control UBA’s root or UBT’s engine-side run-marker directory.

## Build attempts and outputs

The target was `A7K46C0B_ReadOnlyInspectorEditor Win64 Development`, using the existing StageA7G UE 5.6.1 engine at `G:\ForgeMCP-StageA7G-UE56\UE_5.6`, the disposable C0B project, `-DisablePlugin=Cargo`, the private `-Log` path, the existing project XML cache, and `-NoHotReloadFromIDE -WaitMutex`. The official UE installation was not used for the R1 compile.

| Attempt | Result | Evidence |
|---|---|---|
| Initial long-path invocation | **FAIL**; UBT exit 6 after 169.34 seconds | UHT generated headers and UBT reached target/action planning, then rejected action paths longer than 260 characters. The primary log is `runtime\logs\ubt\C0B-R1-EditorBuild.log` (248,448 bytes, SHA-256 `2C970EB1A08631E1D068103FE2AE7BD54CB13503F8910F5F8F6D007F3BBF1E1A`). |
| Temporary `R:` alias retry | **INTERRUPTED / FAIL** | UHT wrote six generated outputs; UBT announced 40 actions and started UBA. The log showed `UbaServer - Listening on 0.0.0.0:1345` and `RootDir C:\ProgramData\Epic\UnrealBuildAccelerator`. After identifying the external boundary, the build was interrupted. UBT exited 1; the temporary alias was removed. Log: `runtime\logs\ubt\C0B-R1-EditorBuild-shortpath.log` (285,063 bytes, SHA-256 `0E141136BC480DE77CBD43E55C51C5D9A8CE686B690BDE3AD7C5D8C479945800`). |

No ForgeMCP DLL, runtime DLL, object file, or Editor target binary was produced. The only `.dll`/`.pdb` files found in the disposable project are the generated C# target module-rules assembly and symbols under `Intermediate\Build\BuildRules`; these are not a native plugin compile. The candidate plugin `Binaries\Win64` directory exists but contains no binary files.

The write audit `runtime\logs\ubt\C0B-R1-build-write-audit.json` has SHA-256 `C17C9EA7EE7E46A8F86D0C9A2BE5FF8D565C75C234FAEEAB9415BBFC95808254`. It records the file-level deltas and external guards. Relative to the initial C0B snapshot, the first attempt created 115 files and changed three existing project BuildRules files; no original files were missing. Relative to the snapshot taken before the short-path retry, the retry created 66 files and changed 68; no original files were missing. Those C0B-root outputs are confined to the disposable project’s `Intermediate` trees and the private `runtime\logs\ubt` area. They have not been cleaned or removed.

### Out-of-root effects

- `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\UbtRuns\38968_d0acf73a0a5904967b907cc59ad5ded9`: 36 bytes, last write `2026-10-22T02:06:14.1130324Z`, SHA-256 `28C62DE59A7126E0D38D4243365F5CEAE90EAC31ADCC5CCDFE6922F76AF7D73F`. Its contents are `C:\Program Files\dotnet\dotnet.exe`. It was not removed or changed after discovery.
- `C:\ProgramData\Epic\UnrealBuildAccelerator\sessions`: present after the attempt, last write `2026-10-22T02:06:40.5525316Z`, zero files. No pre-run baseline exists to establish whether it was newly created or touched.
- TCP listener `0.0.0.0:1345`: shown in the UBT log while the build was active. A later passive check found no listener on that port. No firewall rule was inspected or changed.
- The previously observed user-profile UBT log at `C:\Users\Kenne\AppData\Local\UnrealBuildTool\Log.txt` remained unchanged: 9,391 bytes, SHA-256 `21C6BEB97F3FF7B7292AF1130AEB7E36C95B1790549EA9B7FCEF41F331F22AEC`.
- The guarded official-engine plugin/version files, StageA7G engine Forge plugin files, and StageA7G precompiled BuildRules files matched their pre-build hashes. No plugin binary was deployed or replaced.

## StageA7G storage inventory and retention

A prior read-only list-only inventory of the existing StageA7G UE 5.6.1 development engine measured these major directories. These values are directory totals, not a full-volume usage report; `Engine\Intermediate` now also contains the 36-byte UBT run marker listed above.

| Directory | Measured bytes |
|---|---:|
| `Engine\Plugins` | 65,723,639,039 |
| `Engine\Binaries` | 23,367,847,613 |
| `Engine\Source` | 1,802,026,324 |
| `Engine\DerivedDataCache` | 1,415,777,017 |
| `Engine\Content` | 1,206,652,001 |
| `Engine\Intermediate` before the R1 marker | 109,151,850 |
| `FeaturePacks` | 372,477 |
| **Sum of measured directories** | **93,625,466,321** |

The largest consumers are Plugins and Binaries. Retain the StageA7G engine, its engine-level ForgeMCP `0.2.13-alpha.9` plugin copy, existing StageA7G projects, historical acceptance evidence, and the C0B source/project/log outputs. No cleanup or movement was performed. `DerivedDataCache` and `Intermediate` are possible future cleanup candidates only after project/build references and current processes are checked; this report does not authorize deleting them.

Historical A7K41 records point to the official `G:\Program Files\EpicGames\UE_5.6` engine and a project-local Forge plugin. There is no demonstrated A7K41 dependency on the StageA7G engine in the available records. Current A7K41 state was not checked or contacted.

G: had 102,724,100,096 bytes free at the final check.

## Gate results

| Gate | Status | Finding |
|---|---|---|
| Reuse existing C0B development root | **PASS** | Reused the existing root under `G:\ForgeMCP\Saved`; no second workspace or engine was created. |
| Identify missing dependency | **PASS** | Cargo declares the missing KitBash modules; they are not ForgeMCP dependencies. |
| Exclude Cargo for disposable target | **PASS** | Target-specific `-DisablePlugin=Cargo` got past the dependency-resolution blocker. |
| Verify private UBT logs | **PASS, bounded** | `-Log` and the tested query-mode log landed inside C0B; this did not contain all build side effects. |
| Preserve plugin version selection | **PASS** | Disposable project pins local plugin numeric version 30; StageA7G engine copy is numeric version 24. |
| Native Editor target compilation | **FAIL / INCOMPLETE** | Long-path attempt failed; short-path attempt was interrupted before a complete compile. No plugin or Editor binaries were produced. |
| Keep all generated output in C0B root | **FAIL** | UBT wrote/updated an engine run marker outside the root and started UBA with an external root and wildcard listener. |
| Official Engine/plugin integrity | **PASS for guarded files** | Official engine version and Forge plugin hashes matched the pre-build snapshot; the official engine was not invoked for compilation. |
| A7K41 / production protection | **PASS** | No A7K41 or production connection, process action, project read, or asset write occurred. |
| StageA7G storage inventory | **PASS, read-only** | Major existing directory consumers and retention candidates are documented; nothing was deleted, moved, or cleaned. |

## Remaining blockers and next bounded stage

C0B-R1 stops here. No candidate is ready, and the isolated native inspector source remains uncompiled and untested. The next stage must use offline UE 5.6.1 UBT source/config review to determine whether UBA can be disabled or rooted under the C0B directory and whether the `Engine\Intermediate\UbtRuns` marker can be redirected or avoided. Any option must also prevent wildcard listener exposure or prove the build helper is constrained to the approved local scope. Do not run another build until both external effects are bounded before launch.

If supported UBT controls cannot keep every generated file and temporary listener within the approved boundary, stop and request a revised build-isolation scope. Do not delete the UBA session directory or UBT run marker as cleanup. Do not deploy the candidate, launch Unreal or a ForgeMCP host, connect to A7K41, or modify production projects.

**Final disposition: dependency recovery PASS; private log routing PASS only for explicitly routed logs; build isolation FAIL; native compile FAIL / incomplete; candidate NOT READY. Production Phase 6C remains NO-GO.**