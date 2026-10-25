# ForgeMCP Stage A7K46-C0B-R3 — Controlled Native Build Recovery

Date: 2026-10-22 UTC  
Engine target: Unreal Engine 5.6.1, changelist 44394996  
Mode: Read-only preparation  
Disposition: **BLOCKED before UBT launch. The R3 instructions explicitly withhold external-write approval and one-build authorization. No trace was started, no alias was created, and no build was run.**

## 1. Result

The existing C0B workspace is present and reusable. The principal baseline hashes and the project-local native source inputs match the R1/R2 records. The staged build still cannot proceed: authorization is absent, the required file-write trace was not runtime-tested, and additional conditional external effects are outside the five proposed exception paths.

Only this report is created by R3. No editor, host, UBT, compiler, linker, production project, A7K41 process, or protected asset was accessed or launched.

## 2. Workspace and source baseline

Existing development root:

~~~text
G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1
~~~

The similarly named drive-root path `G:\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1` is absent. The workspace, source tree, and disposable project are non-reparse-point directories.

| Baseline item | Fresh read-only result |
|---|---|
| Source-copy manifest | 69,104 bytes; SHA-256 `FDFC716DCC2B4A6D083E9307A0F354F6120216D44E9ECD0B931250FD266AB643`, matching R1/R2. It contains 355 records; all 355 files still exist. |
| Initial-manifest comparison | 14 recorded files differ from their initial-copy hashes: seven intentionally changed source files documented by C0B, plus seven Python bytecode cache files produced by tests/compilation. There are 11 current files absent from the initial manifest: the two documented new `ForgeWorldSaveScope` C++ files and nine `.pytest_cache`/`.ruff_cache` files. No manifest-recorded source file is missing. |
| Disposable project | `disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject`; 487 bytes; SHA-256 `EA8FAFB37836F21FCC7A166C9C11231BD5D41B66DAEB699564792C104CF4830C`, matching R2. |
| Project plugin descriptor | `Plugins\Forge\MajesticForge.uplugin`; numeric version 30, VersionName `0.2.16-alpha.1`, EngineVersion `5.6.0`; SHA-256 `55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07`, matching R2. Runtime and Editor modules are declared. |
| Project-local native sources | The project copies of `ForgeMeshImport.cpp`, `MajesticForgeModule.cpp`, `ForgeWorldSaveScope.cpp`, and `ForgeWorldSaveScope.h` match the corresponding C0B candidate source hashes exactly. Their hashes are respectively `5AF48A84CADFA998FBB0AB9C61B98A257C65C65E0912BB0F4F2C12FA4E3D3BD1`, `07C6EF7D0C0A6187D518D1D789D9E52175591A2787728E5D29667703F3399067`, `86369AB27CC83FEE6E35BF4449E195C6599010DC17FF9672F98EE8C41A9C1708`, and `1AE8483C108A371B9B6D2BA1CF60FE2C95D066E1D4FF4EAFE2B493E86EDB7834`. |
| XML configuration cache | Existing project cache is 354 bytes; SHA-256 `0CB1ADE885A5010A5E1C938D6BCBEFF5F50D4B9101A8FACC9252C8B51C6BAB93`, matching R2. |
| Project build intermediates | `Intermediate` contains 85 files totaling 12,631,302 bytes. Project-local `SourceFileCache.bin` is 4,622,780 bytes, SHA-256 `130D155B15829896F09C435801BB1CBFCB5409357D8C2F77A30EBE52DF30FE40`. Project-local BuildRules DLL/PDB/manifest exist from the earlier incomplete attempts. These are retained; no cleanup was performed. |
| Candidate output binaries | The project and plugin `Binaries\Win64` directories exist and each contains zero files. No native ForgeMCP plugin DLL or project Editor target DLL is present. |

The initial manifest is a copy-time record, not an assertion that the later C0B draft remains byte-identical to its source snapshot. The intentional source changes and generated caches are disclosed above. No source file was edited during R3.

## 3. Engine and dependency selection

The configured build engine exists at `G:\ForgeMCP-StageA7G-UE56\UE_5.6`. Its `Engine\Build\Build.version` reports 5.6.1 / changelist 44394996; the file SHA-256 is `B6A16A262D0136D1812F134EBD83E81138546DCC705F5F088A96702C970D24A0`. The configured `Build.bat` exists and has SHA-256 `4F71B08EBC3FE2BA7918A5BE7A0B3F22CF7CE5530049873E9ECA8DF946BC1CB3`. The official UE installation is not the configured build engine.

The R1 record attributes the original missing `KitBash3dUsdTools` module to the unrelated Cargo plugin; it records that Cargo is not a ForgeMCP dependency and that target-specific `-DisablePlugin=Cargo` passed that dependency-resolution blocker. R2 retained that switch. R3 does not change engine files or project configuration. No UBT invocation was made to re-test dependency resolution.

The supported executor flags verified against UE 5.6 source by R2 remain `-NoUBA -NoXGE -NoSNDBS -NoFASTBuild`. R2 source analysis concluded that `-NoUBA` avoids UBA executor/server construction and the UBA ProgramData/listener path; the other switches disable XGE, SN-DBS, and FASTBuild selection. The intended command also retains `-DisablePlugin=Cargo`, `-NoHotReloadFromIDE`, `-WaitMutex`, explicit `-Log`, and the existing `-XmlConfigCache`. These are plan-only findings; the command was not run.

## 4. External-write baseline and scope gaps

The five external file exceptions proposed in R2 are still **not authorized**. Current observations:

| Path | Current state | Boundary result |
|---|---|---|
| `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\UbtRuns\<dynamic marker>` | Parent directory exists. The preserved R1 marker `38968_d0acf73a0a5904967b907cc59ad5ded9` remains 36 bytes with SHA-256 `28C62DE59A7126E0D38D4243365F5CEAE90EAC31ADCC5CCDFE6922F76AF7D73F`. | One new dynamic marker remains an external write requiring explicit approval. The R1 marker was not altered. |
| `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\Build\SourceFileCache.bin` | Absent. Its parent directory exists. | Exact conditional external cache path proposed in R2; not authorized. |
| `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.dll` | 42,496 bytes; SHA-256 `D3A86F776B072A3E415964827A25066A09BC751D8D57655AAC8D678685F573D4`. | Exact conditional external path proposed in R2; not authorized. |
| `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.pdb` | 130,560 bytes; SHA-256 `2BC29E64A9C55C71503E14A8A934D81F9CAA3711B6847B83A5D73EAEEC810563`. | Exact conditional external path proposed in R2; not authorized. |
| `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\DependencyCache.bin` | Absent. The `A7K46C0B_ReadOnlyInspectorEditor` and `Development` parent directories are also absent; `...\Win64\x64` exists. | The file is in the R2 proposed list, but creation of these two external directories is an additional effect that must be explicitly included or prevented before authorization. |
| `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRulesManifest.json` | Present; 8,879 bytes; SHA-256 `C530FAA3B6207C0433624A273C57547BAAC1AE95E77A6B41996746D86CEB461B`. | **Not in the five proposed exceptions.** UE source derives this manifest beside the MarketplaceRules assembly and writes it when that assembly is compiled. A conditional recompile could therefore modify this additional external file. R2 did not include it. Future preflight must prove no recompile is needed and guard it unchanged, or obtain explicit approval for this exact file. |
| `C:\Users\Kenne\AppData\Local\UnrealBuildTool\UnrealBuildTool.Env.BuildConfiguration.xml` | Absent at this check. | The valid explicit project XML cache remains available; preserve `-XmlConfigCache` and verify its hash before any future run. |
| `C:\Users\Kenne\AppData\Local\UnrealBuildTool\Log.txt` | Present; 9,391 bytes; SHA-256 `21C6BEB97F3FF7B7292AF1130AEB7E36C95B1790549EA9B7FCEF41F331F22AEC`; last write `2026-10-22T01:25:51.9043595Z`. | Keep the explicit C0B `-Log` argument. This prior user-profile log was read only and left unchanged by R3. |

The exact C0B R3 primary log and stdout paths are absent under the existing `runtime\logs\ubt` directory. The current `runtime\temp` directory exists; a future stage-specific temp directory can be created beneath C0B. The `R:` mapping is currently unused. No mapping was created. C: has 30,526,623,744 bytes free and G: has 102,709,161,984 bytes free; no minimum build-space requirement was specified, so capacity sufficiency is not certified.

UE source `DynamicCompilation.cs` forms the rules manifest as `<assembly basename>Manifest.json` in the assembly directory and writes it after compilation. Current source SHA-256: `0F67C9A79A5B7C578C26619332926EDE8DEB6F24D5A5B0A55F7932CE9E162701`. Current `RulesCompiler.cs` SHA-256: `73044F264F0302563F9764C792A810592557FD085B5C387B288F7037A626C23A`. This is the concrete reason the Marketplace rules manifest is called out as a conditional external write.

## 5. Process-tree file-write tracing

Windows Performance Recorder is already present at `C:\Windows\System32\wpr.exe`; it was not installed or started. Read-only `wpr -profiles` and `wpr -profiledetails FileIO` queries show a built-in File I/O profile with `FileIO`, `FileIOInit`, and process/thread events, plus file create, write, delete, rename, flush, close, and related stacks. Microsoft describes the built-in File I/O activity profile as recording all file I/O activity ([profile reference](https://learn.microsoft.com/windows-hardware/test/wpt/built-in-recording-profiles)); its command-line reference documents profile/status controls ([WPR command-line options](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options)).

The current WPR status is “not recording.” The current shell is not elevated; the user token has the enabled `Performance Log Users` group but does not list `SeSystemProfilePrivilege`. No start/stop trace probe was run because this stage authorizes read-only preparation only. Therefore the trace destination, process-tree correlation, start/stop behavior, and ability to save a complete trace within C0B remain **unverified**. The required “Tracing capability verified” gate is **BLOCKED**. Before a future build, a separately authorized no-build trace probe or equivalent supported verification must establish complete process and file-operation capture with the trace output under C0B. If that requires elevation, a service, or a new permission, stop and obtain the required authorization rather than proceeding.

## 6. Gate results

| Gate | Status | Evidence |
|---|---|---|
| Existing C0B workspace and disposable project | PASS | Exact G:\ForgeMCP\Saved path exists; no reparse points observed; no replacement workspace created. |
| Source-copy manifest baseline | PASS WITH DOCUMENTED DRIFT | Manifest hash matches R2; all 355 listed files exist. Differences and added draft/cache files are enumerated above. |
| Native source inputs | PASS | Four relevant project-local C++ inputs match their candidate source copies by SHA-256. |
| Correct engine and plugin selection | PASS | Configured engine is UE 5.6.1; project pins Forge plugin numeric version 30 / 0.2.16-alpha.1. |
| Existing intermediates and output baseline | PASS | 85 project Intermediate files inventoried; project/plugin binary output directories are empty. No cleanup occurred. |
| Disk-space sufficiency | UNKNOWN | Free space measured, but no safe minimum was specified. |
| External-write approval | BLOCKED | R3 explicitly says R2 exceptions were not approved; no separate approval was provided. |
| One-build authorization | BLOCKED | R3 explicitly withholds compilation authorization; no separate authorization was provided. |
| Tracing capability verified | BLOCKED | Built-in profile exists and describes required event classes, but no trace was started or saved; end-to-end process-tree coverage is unverified. |
| No unapproved external destination | BLOCKED | Conditional MarketplaceRules manifest output and two external dependency-cache directories are outside the five-file exception list. |
| Short-path strategy verified | BLOCKED | `R:` was absent at the check, but no alias was created or resolved because build authorization is absent. |
| Executor and logging configuration | PASS FOR PLAN ONLY | R2 source verified the switches; R3 output paths are absent; no command was executed. |
| XML cache | PASS FOR PLAN ONLY | Existing project cache hash matches R2; no shared configuration was touched. |
| Native compilation | NOT RUN | No UBT, compiler, linker, or build process was launched. |
| A7K41 / production protection | PASS FOR THIS STAGE | No A7K41 inspection, connection, Editor action, service operation, or production access occurred. |

## 7. Exact next authorization and recommended next gate

Before a future build, the project owner must separately authorize one instrumented build and the exact external effects. The current five proposed file exceptions are:

1. One dynamic marker beneath `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\UbtRuns`.
2. `G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\Build\SourceFileCache.bin`.
3. `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.dll`.
4. `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.pdb`.
5. `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\DependencyCache.bin`.

That authorization must also address whether to approve creation of `C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor` and its `Development` child, and the conditional `MarketplaceRulesManifest.json` write. Alternatively, a fresh read-only prebuild check may establish the manifest will not be recompiled, but the trace must still guard its hash.

The later authorized stage must first prove a WPR FileIO trace can start and stop with its output and temporary files contained within C0B. It must capture process/thread creation and file create/write/delete/rename activity before UBT starts and until the entire child process tree exits. Then revalidate every source/cache hash, drive mapping, path, and free-space condition immediately before one build. Use `-NoUBA -NoXGE -NoSNDBS -NoFASTBuild`, `-DisablePlugin=Cargo`, `-NoHotReloadFromIDE`, `-WaitMutex`, and explicit C0B `-Log`, `-XmlConfigCache`, `TEMP`, `TMP`, and `UnrealBuildTool_TMP` paths. Any new external destination remains a stop condition. Do not deploy the resulting binaries or launch an Editor/host.

## 8. Operations and final disposition

R3 performed only filesystem metadata/hash reads, bounded report/source inspection, `wpr -profiles`, `wpr -profiledetails FileIO`, `wpr -status`, and identity privilege/group inspection. It did not create the `R:` mapping, start WPR recording, invoke UBT, run tests, edit source/configuration, clean intermediates, or access A7K41 or production.

**Final disposition: read-only preparation complete; build authorization BLOCKED; tracing readiness BLOCKED; exact external write scope BLOCKED pending approval or exclusion. No native compilation occurred. Do not proceed to build until the owner explicitly authorizes one instrumented build and the complete exact write scope. Production Phase 6C remains NO-GO.**

## 9. Source references

- R1 report: `ForgeMCP_A7K46-C0B-R1_Build_Isolation_Recovery_Report.md`, SHA-256 `AC6AFAE593A6A5B51658C848C63B6238C6D652C17F6E996CBF1CA6B976138442`.
- R2 audit: `ForgeMCP_A7K46-C0B-R2_UBT_UBA_Build_Boundary_Audit_Report.md`, SHA-256 `A0BFC86389B06A00E31BCFD6C8996B0D8D79966B4018B0E12883345D919B75AB`.
- UE 5.6 `CppDependencyCache.cs`: SHA-256 `B4E0653F06F18CA31CB4ADD9B8EAFA36AA545C16B4BE770C88918BDE4D70DC45`.
- UE 5.6 `Unreal.cs`: SHA-256 `5883A72F346596D1B720B1E7A8F21DDA3DA3B7BA3E46F12C63CD41ABC3E01059`.
- UE 5.6 `XmlConfig.cs`: SHA-256 `9ABAF6713D9328847E5858C03E662DAA687D706FDAE0F453AA5EA20124F40730`.
- UE 5.6 `UnrealBuildTool.cs`: SHA-256 `12DDCD42085663C243C334DF92C6BE10CBCE93DA12C93FBA32DC2FADFC697C44`.
