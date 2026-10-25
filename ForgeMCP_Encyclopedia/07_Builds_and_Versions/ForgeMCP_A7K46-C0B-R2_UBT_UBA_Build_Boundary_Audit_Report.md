# ForgeMCP Stage A7K46-C0B-R2 — UBT / UBA Build Boundary Audit

Date: 2026-10-21  
Engine: Unreal Engine 5.6.1, changelist 44394996  
Mode: Offline source, configuration, and existing-evidence audit  
Disposition: **No UBT/UBA process was launched. No source, project, engine, or previous evidence was modified. One future build is technically plan-able, but it is NO-GO under the C0B-only write boundary because UBT has unavoidable or conditional outputs outside C0B. Separate approval of the exact exceptions below is required before any build.**

## 1. Result

The existing C0B workspace and project were reused at the correct path:

~~~text
G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1
~~~

The historically mentioned drive-root substitute does not exist and was not used. The existing project, source copy, source-copy manifest, R1 report, and R1 write-audit file are present. The project and candidate source copy are non-reparse-point paths. The project descriptor still selects the project-local Forge plugin at numeric descriptor version 30 / version 0.2.16-alpha.1. The candidate ForgeWorldSaveScope.cpp is present and currently hash-identical between the source copy and the project-local plugin source.

The exact UE 5.6 UBT source supports -NoUBA. UBT’s executor selector checks bAllowUBAExecutor before constructing UBAExecutor; the command-line attribute maps -NoUBA to false, and command-line application follows XML-cache application. With the flag effective, UBT falls through to its local ParallelExecutor. The supported -NoXGE, -NoSNDBS, and -NoFASTBuild switches also disable the other remote executors, avoiding a fallback to those external build services.

This prevents UBT’s normal build path from constructing UBA’s server/session, starting its listener, or selecting its ProgramData storage root. -UBADisableRemote is not equivalent: it disables remote help inside an already selected UBA executor; that executor still creates its local server/session. The correct control for this task is -NoUBA.

That resolves the UBA part of R1, but not complete write containment. Source inspection found an unconditional best-effort UBT run marker under the StageA7G engine, plus engine and user-settings build caches that may be written by a successful compile. In addition, R1’s timestamped log shows that UBT rebuilt Marketplace rules DLL/PDB files in LocalAppData. The R1 external-write audit did not include those two files, so its “external guards unchanged” result did not cover all UBT writes.

## 2. Existing C0B environment and integrity

| Item | Current verification |
|---|---|
| Development root | Exact existing C0B path above; directory exists and is not a reparse point. |
| Disposable project | disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject exists; SHA-256 EA8FAFB37836F21FCC7A166C9C11231BD5D41B66DAEB699564792C104CF4830C. |
| Project-local plugin | disposable\A7K46C0B_ReadOnlyInspector\Plugins\Forge\MajesticForge.uplugin exists; version 30 / 0.2.16-alpha.1; SHA-256 55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07. |
| C0B source-copy manifest | Present; current SHA-256 FDFC716DCC2B4A6D083E9307A0F354F6120216D44E9ECD0B931250FD266AB643, matching the R1 report. |
| Native candidate source | source\Plugins\Forge\Source\MajesticForge\Private\ForgeWorldSaveScope.cpp exists; SHA-256 86369AB27CC83FEE6E35BF4449E195C6599010DC17FF9672F98EE8C41A9C1708. The project-local copy is the same size (24,898 bytes) and has the same hash. |
| R1 report / audit | R1 report hash AC6AFAE593A6A5B51658C848C63B6238C6D652C17F6E996CBF1CA6B976138442; audit hash C17C9EA7EE7E46A8F86D0C9A2BE5FF8D565C75C234FAEEAB9415BBFC95808254. |
| XML configuration cache | Existing project cache is 354 bytes; SHA-256 0CB1ADE885A5010A5E1C938D6BCBEFF5F50D4B9101A8FACC9252C8B51C6BAB93. It remains at disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\XmlConfigCache.bin. |
| Build entry point | StageA7G Engine\Build\BatchFiles\Build.bat exists. |
| Temporary R: alias | Not mapped at this R2 check. It was not created. A future stage must recheck immediately before use. |

No candidate plugin DLL or completed Editor target binary was produced by R1. R1’s two build attempts remain failed/incomplete evidence, not successful compilation evidence.

## 3. UBA control audit

UE 5.6 Configuration\BuildConfiguration.cs declares bAllowUBAExecutor, defaults it to true, exposes it to XML configuration, and maps -NoUBA to false. System\ActionGraph.cs selects UBAExecutor only when that field is true and UBA is available. Otherwise the selector continues through the configured executor priority and eventually returns the in-process local ParallelExecutor.

The command-line flags verified in this installed source are:

- -NoUBA — disables the UBA executor.
- -NoXGE — disables XGE.
- -NoSNDBS — disables SN-DBS.
- -NoFASTBuild — disables FASTBuild.

All four will be present in the proposed invocation. This keeps UBT’s executor selection local while preserving parallel local compile/link actions. It does not serialize the build to one action; it leaves the normal local parallel executor enabled.

The UBA implementation creates its server/session inside UBAExecutor.ExecuteActionsAsync. The UBA configuration source declares Host = "0.0.0.0" and port 1345 by default, and chooses UBA_ROOT, then BOX_ROOT, then CommonApplicationData\Epic\UnrealBuildAccelerator as the default root when no explicit root is supplied. With -NoUBA, UBT does not construct that executor, so those UBA server/root operations are not reached through the standard UE 5.6 build path. -UBADisableRemote alone would not prevent them.

**VERIFIED:** -NoUBA is the supported executor-level disable control. In the source call path, it prevents UBA executor construction and therefore UbaServer/session creation, the default wildcard listener, and ProgramData session writes.  
**UNKNOWN:** Arbitrary third-party build rules or compiler tools could perform their own writes or start their own helpers. The standard C0B target has no R2 runtime trace because no build was run.

## 4. Engine run-marker audit

UnrealBuildTool.cs attempts marker creation during UBT initialization, in a try block:

~~~text
<EngineDirectory>\Intermediate\UbtRuns\<PID>_<MD5-of-uppercase-UBT-main-module-path>
~~~

The code creates the directory and writes the absolute UBT main-module path into the marker. There is no configuration switch or command-line option in the inspected source to disable or redirect it. UBT records the path and attempts to delete the marker in its final cleanup block. A process interruption can leave it behind.

R1’s marker is still present and was not changed in R2:

~~~text
G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\UbtRuns\38968_d0acf73a0a5904967b907cc59ad5ded9
~~~

It is 36 bytes, SHA-256 28C62DE59A7126E0D38D4243365F5CEAE90EAC31ADCC5CCDFE6922F76AF7D73F; its content identifies C:\Program Files\dotnet\dotnet.exe. The existing R1 record says the marker was not removed or changed. The PID portion of a future marker will differ; the suffix is based on the same UBT main-module path only if that executable path remains unchanged.

**VERIFIED:** marker creation is attempted on every UBT run and deletion is only attempted during normal cleanup.  
**VERIFIED:** no supported marker redirection/disable setting was found in the inspected UE 5.6 UBT source.  
**PROPOSED EXCEPTION:** one dynamic marker file under G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\UbtRuns, plus directory creation only if absent. Its content is the UBT executable path; normal exit deletes it; an interrupted run may leave it. This engine-side write requires separate approval. Do not remove the old R1 marker.

## 5. Additional external build-cache effects

The StageA7G engine contains Engine\Build\InstalledBuild.txt. UE source therefore resolves Unreal.WritableEngineDirectory to the user settings path %LOCALAPPDATA%\UnrealEngine, not to C0B. Current LOCALAPPDATA is C:\Users\Kenne\AppData\Local.

| Potential output | Source behavior and current evidence | Boundary classification |
|---|---|---|
| G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\Build\SourceFileCache.bin | SourceFileMetadataCache mounts an engine cache at this exact path and saves modified caches in BuildMode cleanup. The file is absent now. No redirect or disable option was found in the inspected call path. | **PROPOSED EXCEPTION / CONDITIONAL** — one exact engine cache file may be created or updated by a successful build. |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\DependencyCache.bin | CppDependencyCache.Mount constructs the writable-engine cache path for this project target. BuildMode saves modified cache partitions. It is absent now; its exact contents/change depend on compile dependency data. | **PROPOSED EXCEPTION / CONDITIONAL** — one exact user-settings cache file may be created or updated. |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.dll | UBT source places Marketplace rules assemblies under Unreal.WritableEngineDirectory. The file currently exists, 42,496 bytes, SHA-256 D3A86F776B072A3E415964827A25066A09BC751D8D57655AAC8D678685F573D4; creation time predates R1, last write is 2026-10-22T02:01:54.5728454Z. The R1 build log says UBT was compiling this path. | **R1 EXTERNAL WRITE OBSERVED; FUTURE UPDATE CONDITIONAL.** Current hash is the new read-only comparison baseline. |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.pdb | Currently 130,560 bytes, SHA-256 2BC29E64A9C55C71503E14A8A934D81F9CAA3711B6847B83A5D73EAEEC810563; creation time predates R1 and last write is 2026-10-22T02:01:54.5713442Z. R1 log/compiler activity corresponds to this Marketplace rules assembly. | **R1 EXTERNAL WRITE OBSERVED; FUTURE UPDATE CONDITIONAL.** Current hash is the new read-only comparison baseline. |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\UnrealBuildTool.Env.BuildConfiguration.xml | This file currently exists. Source writes it only in the normal configuration-discovery branch. Supplying a valid -XmlConfigCache=<existing C0B cache> takes the forced-cache branch (“never rebuild the cache”) and skips that branch. | **EXPECTED NO WRITE**, provided the cache exists, its hash matches, and the command keeps -XmlConfigCache. Stop before UBT if any prerequisite fails. |
| C:\Users\Kenne\AppData\Local\UnrealBuildTool\Log.txt | R1’s guarded record says the default UBT user-profile log was unchanged. Explicit -Log=<C0B path> selects the primary build log. | **EXPECTED NO WRITE**, with explicit -Log; include it in the external pre/post guard. |
| C:\ProgramData\Epic\UnrealBuildAccelerator\... and TCP 1345 | R1 observed these when UBA ran. The source-supported -NoUBA path prevents normal UBA executor/session startup. | **AVOIDED BY VERIFIED SETTING**; still monitor the process tree and listener during the future run. |

The two Marketplace rules files were not present in the R1 audit’s 131 external guard rows. Their older creation times, R1-time last-write times, and the R1 log’s explicit “Compiling … MarketplaceRules.dll” entry establish that the prior audit omitted an external output. Their pre-R1 bytes are not available, so this report does not reconstruct the old hashes. The R1 external-output claim must be read as incomplete for this cache path.

Potential compiler/SDK transient writes beyond the redirected UBT temp directory are **UNKNOWN** until a future process-tree write trace. Setting TMP, TEMP, and UnrealBuildTool_TMP before launch constrains standard temp use, but does not prove that every third-party tool honors those variables.

## 6. Expected build outputs and boundary classification

The target is A7K46C0B_ReadOnlyInspectorEditor Win64 Development, selected from the existing project with project-local MajesticForge enabled. The following outputs are supported by the R1 action log/audit or the installed UBT target/source path rules.

| Output class | Expected path(s) / namespace | Classification |
|---|---|---|
| UHT manifests and generated headers | R:\disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\Win64\A7K46C0B_ReadOnlyInspectorEditor\Development\... | **APPROVED ROOT** — exact subtree within the existing disposable project. |
| Target makefiles and metadata | ...\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\Makefile.bin, TargetMetadata.dat, .deps, source-file cache and related metadata | **APPROVED ROOT** for project-local files. |
| Project/module BuildRules assembly | ...\Intermediate\Build\BuildRules\A7K46C0B_ReadOnlyInspectorModuleRules.dll/.pdb | **APPROVED ROOT** — project-local. |
| Module compile objects/response files/generated sources | ...\Plugins\Forge\Intermediate\Build\Win64\x64\UnrealEditor\Development\MajesticForge[Runtime]\... including .obj, .obj.rsp, .dll.rsp, .lib.rsp, generated Module.*.gen.cpp, and response-file .old snapshots | **APPROVED ROOT** — the set is generated from the project-local Forge source and remains beneath the project plugin’s Intermediate directory. |
| Native plugin binaries and symbols | R:\disposable\A7K46C0B_ReadOnlyInspector\Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.dll/.pdb and UnrealEditor-MajesticForgeRuntime.dll/.pdb | **APPROVED ROOT** — deterministic project-plugin destinations; none was produced by R1. |
| Project Editor target binary/symbols | R:\disposable\A7K46C0B_ReadOnlyInspector\Binaries\Win64\UnrealEditor-A7K46C0B_ReadOnlyInspector.dll/.pdb | **APPROVED ROOT** — deterministic project target path reported by the R1 action log; none was produced by R1. |
| Primary UBT log and captured process output | R:\runtime\logs\ubt\C0B-R2-EditorBuild.log and C0B-R2-EditorBuild-stdout.txt | **EXACT PATH / APPROVED ROOT**, after verifying both paths are absent. |
| UBT temporary files | Explicit process-scoped temp root R:\runtime\temp\C0B-R2-UBT\... | **APPROVED ROOT**, if the directory is created under C0B and all three temp variables are set before UBT starts. |
| Engine run marker | ...\Engine\Intermediate\UbtRuns\<future-UBT-PID>_d0acf73a0a5904967b907cc59ad5ded9 if the UBT main-module path remains C:\Program Files\dotnet\dotnet.exe | **PROPOSED EXCEPTION** — outside C0B, no supported redirect. |
| Engine source cache | ...\Engine\Intermediate\Build\SourceFileCache.bin | **PROPOSED EXCEPTION / CONDITIONAL** — exact path, no supported redirection identified. |
| Writable-engine rules/dependency caches | The exact LocalAppData paths listed in section 5 | **PROPOSED EXCEPTION / CONDITIONAL**, with hashes captured before and after. |
| Other compiler/SDK/third-party transient outputs | Not fully derivable from UBT source alone | **UNKNOWN / BLOCKED** until a future runtime write trace confirms they remain inside the approved project/temp roots or they receive a precise exception. |

R1’s audit recorded 115 files created and 3 changed on the first attempt, then 66 created and 68 changed during the short-path retry, under the C0B project and runtime roots. Those counts do not cover every external location; the Marketplace rules cache discovery demonstrates that limitation.

## 7. Short-path strategy and proposed single-build invocation

R1’s temporary R: alias shortened project/output paths enough to pass the earlier 260-character action-path check. R: is currently unmapped, but that is only a present observation. Reuse is safe only if a later authorized build stage rechecks all drive mappings immediately before use, verifies the exact C0B root is the only target, creates the alias itself, and removes it only after all build processes exit and only if it still resolves to that exact root. Do not use a pre-existing R: mapping or an alias that points elsewhere.

The following is a **proposal for a later separately authorized stage; it was not executed here**. Before it, create the named temp/log parent directories under C0B, verify the log paths are absent, verify the XML cache hash above, verify the allowed external exceptions, and capture all pre-run guards.

~~~powershell
# Preconditions: R: is absent; the exact C0B root and project are reverified.
subst R: "G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1"

# Verify the mapping resolves only to the exact C0B root, then set process-scoped temp paths.
$env:UnrealBuildTool_TMP = 'R:\runtime\temp\C0B-R2-UBT'
$env:TEMP = 'R:\runtime\temp\C0B-R2-UBT'
$env:TMP = 'R:\runtime\temp\C0B-R2-UBT'

& 'G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Build\BatchFiles\Build.bat' A7K46C0B_ReadOnlyInspectorEditor Win64 Development '-Project=R:\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject' '-DisablePlugin=Cargo' '-NoUBA' '-NoXGE' '-NoSNDBS' '-NoFASTBuild' '-Log=R:\runtime\logs\ubt\C0B-R2-EditorBuild.log' '-XmlConfigCache=R:\disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\XmlConfigCache.bin' '-NoHotReloadFromIDE' '-WaitMutex' *> 'R:\runtime\logs\ubt\C0B-R2-EditorBuild-stdout.txt'
~~~

The XML cache is intentionally passed as an existing read-only input; UBT source says the explicit cache is loaded without rebuilding it. The command-line -NoUBA is applied after cached XML settings, so it overrides any cached bAllowUBAExecutor=true. No project descriptor, engine configuration, or shared UBT XML file needs to be edited.

After the process tree exits, remove R: only after verifying that the alias still points to the C0B root and that this stage created it. Never run an unconditional subst R: /d.

## 8. Future output-boundary audit procedure

Before the build, record a read-only baseline manifest for the complete C0B root and the approved external guard paths, including current hashes for MarketplaceRules DLL/PDB, the existing UBT marker, engine plugin descriptors/binaries, the project plugin descriptor, XML cache, and default UBT log. The manifest must preserve pre-existing artifacts and mark the approved conditional cache destinations precisely.

During the build, observe the UBT process tree and file writes for the engine UbtRuns directory, engine SourceFileCache path, LocalAppData UnrealEngine cache paths, default UBT log, ProgramData UBA root, and the selected C0B temp/log directories. Confirm no UbaServer process/listener appears and no unrelated remote executor starts. The filesystem post-snapshot alone is insufficient because UBT normally deletes its run marker on clean exit.

Afterward, compare the full C0B pre/post manifest, external guards, and the runtime write trace. Any write outside C0B must match a separately approved exact exception. Record all created/changed files; do not delete outputs or attempt automatic rollback. If an unknown destination is written, stop the acceptance and retain the evidence.

The current plan does not prove that compiler/SDK tools honor the redirected temp variables or that all possible transient writes are observable. A build can only be called contained after a suitable process-tree file-write trace verifies that point.

## 9. Gate results

| Gate | Status | Result |
|---|---|---|
| Reuse exact existing C0B workspace | **PASS** | Existing root/project/source copy found at the correct G:\ForgeMCP\Saved path; no replacement workspace created. |
| Source/project baseline integrity | **PASS** | Manifest, project, plugin descriptor and candidate source hashes recorded; source/project copies match. |
| Cargo dependency remains target-scoped | **PASS** | R1 evidence and current project descriptor support retaining -DisablePlugin=Cargo; no shared config change. |
| Supported UBA disablement | **PASS** | Installed UE 5.6 UBT source verifies -NoUBA and local executor fallback. |
| Prevent standard UBA server/listener/ProgramData writes | **PASS, source-path bounded** | No UBA executor construction with -NoUBA; still require a future runtime process/listener check. |
| UBT primary log routing | **PASS, bounded** | -Log=<C0B path> is supported and R1 query/build logs landed under C0B. |
| XML cache handling | **PASS, conditional** | Existing 354-byte cache is verified. Explicit -XmlConfigCache skips cache rebuilding; future run must recheck its hash and keep the switch. |
| Engine UbtRuns containment | **FAIL** | An engine-side marker is attempted on every UBT run; no redirect/disable option found. |
| Engine/user-settings cache containment | **FAIL / CONDITIONAL** | SourceFileCache, DependencyCache and MarketplaceRules output paths can be outside C0B; MarketplaceRules DLL/PDB were modified during R1 and omitted from its external guard list. |
| All tool temp/transient writes contained | **UNKNOWN** | Environment redirection is source-supported for UBT temp, but compiler/SDK compliance requires runtime write tracing. |
| Native compilation | **NOT RUN in R2; R1 remains incomplete** | No complete plugin or Editor target binary exists. |
| A7K41, production, Editor/host, or firewall operations | **PASS** | None was contacted, launched, modified, or inspected during R2. |

## 10. Disposition and next bounded stage

**GO for the design of a single future build command; NO-GO to execute it under the current C0B-only write rule.** The supported -NoUBA setting removes the UBA listener/ProgramData blocker, and the R: strategy can be reused after a fresh collision check. However, UBT itself writes its engine run marker and its cache/build-rule paths extend into the StageA7G engine and the user’s LocalAppData UnrealEngine directory. The R1 MarketplaceRules write proves at least one external generated output was missed previously.

The smallest precisely defined exception proposal is limited to:

1. The one UBT run marker under the existing StageA7G Engine\Intermediate\UbtRuns directory.
2. Engine\Intermediate\Build\SourceFileCache.bin.
3. The exact LocalAppData MarketplaceRules.dll and .pdb files listed above, guarded by current hashes.
4. The exact LocalAppData target DependencyCache.bin listed above.

This exception set is **proposed, not authorized**. A future run must also use a write trace to detect unanticipated compiler/SDK writes; do not convert unknown paths into an open-ended exception. The next bounded stage should request explicit approval for those exact marker/cache effects, then perform one no-build read-only configuration check if needed, followed by one instrumented native build using the proposed command. If the write-trace tool cannot be used safely, keep the build NO-GO.

No R2 compilation, UBT/UBA launch, alias creation, source edit, configuration edit, engine edit, Editor/host launch, or A7K41/production access occurred. Only this new report is created. The existing R1 marker and all previous build/evidence artifacts were left untouched.

**Final disposition: UBA control PASS; log/config-cache controls PASS when supplied as shown; full build containment NO-GO pending approval of the precise engine/user-cache exceptions and a bounded runtime write trace. A7K41 remains protected. Production Phase 6C remains NO-GO.**


## 11. Source and evidence index

The source references below are from the installed StageA7G UE 5.6.1 tree inspected read-only. Hashes identify the exact source files inspected for this report.

| Source/evidence file | Relevant lines or records | SHA-256 / relevance |
|---|---|---|
| Engine\Source\Programs\UnrealBuildTool\Configuration\BuildConfiguration.cs | 42-88 | 675E9DE1886AAA056790715EC669F4810CF515F01398FAAB8F23BAAEEFBD953A — XML/CLI configuration for remote executor priority and NoUBA/NoXGE/NoSNDBS/NoFASTBuild flags. |
| Engine\Source\Programs\UnrealBuildTool\System\ActionGraph.cs | 400-437 | 334D69A061E329D7DCE90F9C58564EF628449F7EFC7875005CC15870772EA156 — UBA eligibility check and local ParallelExecutor fallback. |
| Engine\Source\Programs\UnrealBuildTool\Modes\BuildMode.cs | 149-151, 260-266 | AFE786787E444AC9AE7EF9BA0A5DE0D170EEC8349B3172B4F2EE9E6C333A55B2 — XML config is applied before command-line arguments; cache save calls run in cleanup. |
| Engine\Source\Programs\UnrealBuildTool\Executors\UnrealBuildAccelerator\UnrealBuildAcceleratorConfig.cs | 68-80, 145-165 | 936B2D6ACA50F88336FBCA1EDA7E2C18CB26385F1567A40AFAA2BE82F85EC240 — remote-disable semantics, default Host 0.0.0.0, port, and UBARootDir. |
| Engine\Source\Programs\UnrealBuildTool\Executors\UnrealBuildAccelerator\UBAExecutor.cs | 381-435, 478-495 | F027EC390A8786266EA18DB079961231E6AD4A12E18BE3DEDDD23A1FF7CA0622 — local/remote behavior, storage-root selection, and server/session creation. |
| Engine\Source\Programs\UnrealBuildTool\UnrealBuildTool.cs | 553-562, 570-603, 718-724 | 12DDCD42085663C243C334DF92C6BE10CBCE93DA12C93FBA32DC2FADFC697C44 — run marker create/delete lifecycle and temp-path handling. |
| Engine\Source\Programs\UnrealBuildTool\System\XmlConfig.cs | 88-133 | 9ABAF6713D9328847E5858C03E662DAA687D706FDAE0F453AA5EA20124F40730 — explicit cache is loaded without rebuild; normal branch writes environment configuration XML. |
| Engine\Source\Programs\UnrealBuildTool\System\CppDependencyCache.cs | 370-371, 407-414 | B4E0653F06F18CA31CB4ADD9B8EAFA36AA545C16B4BE770C88918BDE4D70DC45 — writable-engine dependency-cache path and conditional save behavior. |
| Engine\Source\Programs\UnrealBuildTool\System\SourceFileMetadataCache.cs | 522-529, 577 | BCCF1CB0E2DEC4F8F87ADD1D8BD65A4E00E6CDC6D981CA7FA14BFC9A1BBD3EC3 — engine/project source-cache destinations and save entry point. |
| Engine\Source\Programs\UnrealBuildTool\System\RulesCompiler.cs | 226 | 73044F264F0302563F9764C792A810592557FD085B5C387B288F7037A626C23A — MarketplaceRules assembly destination under WritableEngineDirectory. |
| Engine\Source\Programs\Shared\EpicGames.Build\Unreal.cs | 190, 468-486 | 5883A72F346596D1B720B1E7A8F21DDA3DA3B7BA3E46F12C63CD41ABC3E01059 — installed-build writable-engine directory resolution through LocalAppData. |
| R1 short-path build log | Line 21 contains the exact prior command; lines 5 and 25 record C0B temp routing and MarketplaceRules compilation. | R1 report records SHA-256 0E141136BC480DE77CBD43E55C51C5D9A8CE686B690BDE3AD7C5D8C479945800. |
| R1 external audit | external_guard_records count 131; no MarketplaceRules, SourceFileCache, DependencyCache, or UnrealBuildTool environment-cache entry. | Current audit SHA-256 C17C9EA7EE7E46A8F86D0C9A2BE5FF8D565C75C234FAEEAB9415BBFC95808254. |
