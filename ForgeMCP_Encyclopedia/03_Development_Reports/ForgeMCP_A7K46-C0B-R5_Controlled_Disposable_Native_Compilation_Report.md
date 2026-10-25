# ForgeMCP Stage A7K46-C0B-R5 — Controlled Disposable Native Compilation Report

Date: 2026-10-22 (UTC)  
Engine target: Unreal Engine 5.6.1, changelist 44394996  
Workspace: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1  
Project: disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject  
Disposition: **The one authorized build was attempted and failed at C++ compilation (UBT exit code 6). No retry, source repair, Editor launch, host launch, deployment, or cleanup was performed. No unexpected external changes were detected by the bounded metadata/hash audit.**

## 1. Outcome

R5 reused the existing C0B workspace and performed one native build of A7K46C0B_ReadOnlyInspectorEditor Win64 Development with Unreal Engine 5.6.1. UBT reached compilation and used its local Parallel executor. The plugin Editor module did not compile: 16 compiler diagnostics were reported across ForgeMeshImport.cpp and ForgeWorldSaveScope.cpp. The build exited with code 6.

The build produced a partial Runtime plugin module and project target binaries, but not the UnrealEditor-MajesticForge.dll Editor module. The partial binaries are build outputs only. They are not a usable plugin candidate and were not loaded or deployed.

The in-root file audit recorded 107 created files, 1 changed file, and 0 deleted files. The changed file is the project-local Intermediate\Build\SourceFileCache.bin. The external post-build audit recorded zero unexpected external changes across its monitored locations. The six approved external file effects and two approved DependencyCache directory creations were not changed or created. Because R5 did not run WPR, this metadata/hash audit cannot exclude transient or unobserved writes outside the monitored locations.

No A7K41 Editor, production project, Blender session, ForgeMCP host, or persistent service was contacted. No WPR session was started.

## 2. Workspace and pre-build verification

The existing C0B root and disposable project were reused. The R5 runner recorded Preflight: PASS. R4 baseline hashes were rechecked immediately before preparing this report and still match:

| Input | SHA-256 | Result |
|---|---|---|
| source-copy-manifest.json | FDFC716DCC2B4A6D083E9307A0F354F6120216D44E9ECD0B931250FD266AB643 | Match |
| Disposable .uproject | EA8FAFB37836F21FCC7A166C9C11231BD5D41B66DAEB699564792C104CF4830C | Match |
| Project-local MajesticForge.uplugin | 55D4EFF55FFB42139F2A0A728AFC46B623B3AE8AC428C31D82317848C7558F07 | Match |
| ForgeMeshImport.cpp | 5AF48A84CADFA998FBB0AB9C61B98A257C65C65E0912BB0F4F2C12FA4E3D3BD1 | Match |
| MajesticForgeModule.cpp | 07C6EF7D0C0A6187D518D1D789D9E52175591A2787728E5D29667703F3399067 | Match |
| ForgeWorldSaveScope.cpp | 86369AB27CC83FEE6E35BF4449E195C6599010DC17FF9672F98EE8C41A9C1708 | Match |
| ForgeWorldSaveScope.h | 1AE8483C108A371B9B6D2BA1CF60FE2C95D066E1D4FF4EAFE2B493E86EDB7834 | Match |
| Existing XmlConfigCache.bin | 0CB1ADE885A5010A5E1C938D6BCBEFF5F50D4B9101A8FACC9252C8B51C6BAB93 | Match |

The four native source hashes also match in the project-local plugin source used by this build. The plugin descriptor identifies version 0.2.16-alpha.1 (numeric descriptor version 30). Cargo was disabled for this target only; no official Engine plugin or shared configuration was changed.

The build used the short-path R: mapping to the C0B root. The mapping was absent after the build and was removed only after the build process exited. The existing R1 output manifest remained unchanged at SHA-256 302C9E62B50FCDCC252893B0A4DE8F6E8F268A5F156FB7C6BCB6113CDA1ED156.

## 3. Build invocation and execution

Engine executable tree:

G:\ForgeMCP-StageA7G-UE56\UE_5.6

The recorded command was:

    G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Build\BatchFiles\Build.bat A7K46C0B_ReadOnlyInspectorEditor Win64 Development -Project=R:\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject -DisablePlugin=Cargo -NoUBA -NoXGE -NoSNDBS -NoFASTBuild -NoHotReloadFromIDE -WaitMutex -Log=R:\runtime\logs\ubt\C0B-R5-EditorBuild.log -XmlConfigCache=R:\disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\XmlConfigCache.bin

- Start: 2026-10-22T04:51:16.4845691Z
- End: 2026-10-22T05:00:39.9835771Z
- UBT exit code: 6
- UBT log: runtime\logs\ubt\C0B-R5-EditorBuild.log, 36,869 bytes, SHA-256 0F2AC82F64B7521CBF927413160F46BDFF9FD0E2CDD9C2B31BD9430418FC193B
- Captured stdout/stderr: runtime\logs\ubt\C0B-R5-EditorBuild-stdout.txt, 9,833 bytes, SHA-256 145CDDF58A16FAFD2C0C0449FF40D72024A18C436CAF9F744F2CF4347D288E3A
- UBT log states it used the Parallel executor for 40 actions. The command disabled UBA, XGE, SN-DBS, and FASTBuild; no UBA process or listener on TCP 1345 remained afterward.
- No Editor or ForgeMCP host was launched.

## 4. Compile result

**Native compile gate: FAIL.** The log contains 16 compiler diagnostics:

| Source location | Compiler diagnostic |
|---|---|
| ForgeMeshImport.cpp:637 | C2662: FMeshDescriptionBulkData::GetBulkDataSize() is non-const but is called through a const FMeshDescriptionBulkData. |
| ForgeWorldSaveScope.cpp:259 | C4018: signed/unsigned comparison. |
| ForgeWorldSaveScope.cpp:332 | C2039: ULevelStreaming::GetShouldBeLoaded is not a member. |
| ForgeWorldSaveScope.cpp:332 | C2661: FJsonObject::SetBoolField has no overload taking one argument. |
| ForgeWorldSaveScope.cpp:416 | C3861: FullPath identifier not found. |
| ForgeWorldSaveScope.cpp:487 | C3861: StringValue identifier not found. |
| ForgeWorldSaveScope.cpp:490 | C3861: StringValue identifier not found. |
| ForgeWorldSaveScope.cpp:528 | C3861: StringValue identifier not found. |
| ForgeWorldSaveScope.cpp:535 | C3861: PackageFile identifier not found. |
| ForgeWorldSaveScope.cpp:539 | C3861: FullPath identifier not found. |
| ForgeWorldSaveScope.cpp:540 | C2039/C3861: IsWithinProjectContent is not a member/visible identifier. |
| ForgeWorldSaveScope.cpp:551 | C3861: PackageFile identifier not found. |
| ForgeWorldSaveScope.cpp:552 | C3861: FullPath identifier not found. |
| ForgeWorldSaveScope.cpp:564 | C3861: StringValue identifier not found. |
| ForgeWorldSaveScope.cpp:595 | C3861: StringValue identifier not found. |

These diagnostics identify compile-time API/implementation issues in the isolated candidate. No source patch was authorized or applied, and the failed build was not retried.

## 5. Build products and in-root write audit

The complete diff record is runtime\logs\ubt\C0B-R5-file-diff.json, SHA-256 014ECA723FD6B6A8300A3DF5DE8536DF66F8FE89B761104413705C27A992A045. It records:

- 107 created files
- 1 changed file
- 0 deleted files
- 644 files in the comparison baseline and 751 in the post-build snapshot

The R5 pre-build manifest separately records 643 files before writing its own manifest; the diff comparison includes that manifest, which accounts for the one-file count difference. The post-build manifest is runtime\logs\ubt\C0B-R5-postbuild-manifest.json, SHA-256 77671CFA26FC7ADDE1DC5B999B99120B6EA740687C887A6B3C991AC10AC7318F. The pre-build manifest is runtime\logs\ubt\C0B-R5-prebuild-manifest.json, SHA-256 DA16FEE77A52927A33F617218EDFCAF7C35B9C3A8C3B088FB87CDC0872AB4A90. The diff excludes the post-build manifest and its own self-referential diff file. This report was created after those snapshots and is not included in the recorded counts.

The sole changed in-root file was:

| File | Before | After |
|---|---|---|
| disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\SourceFileCache.bin | 4,622,780 bytes; SHA-256 130D155B15829896F09C435801BB1CBFCB5409357D8C2F77A30EBE52DF30FE40 | 4,627,498 bytes; SHA-256 FED58D50575C9B84C24C1B6E151626E0FF952758A05B978215F891BAA395C45B |

Native outputs that exist:

| Output | Size | SHA-256 |
|---|---:|---|
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.dll | 114,688 bytes | 2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F |
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.pdb | 60,387,328 bytes | 962DE8CEF6BFCB28D74FCAA58845A82A2F518E5CFEB186A31DB78D66254095FE |
| Binaries\Win64\UnrealEditor-A7K46C0B_ReadOnlyInspector.dll | 52,224 bytes | E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7 |
| Binaries\Win64\UnrealEditor-A7K46C0B_ReadOnlyInspector.pdb | 57,995,264 bytes | C0A530C6FDB2EABE46BBC6C3440968C38C5452CAF7534F6A6C5979A660EC1E6F |

Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.dll was not produced. The listed DLLs are partial build outputs only; do not load or deploy them.

## 6. Approved external write boundary and observed results

The R5 authorization covered the six precise external file effects previously reconciled in R4 and the two missing DependencyCache directories. The external audit record is runtime\logs\ubt\C0B-R5-external-postbuild.json, SHA-256 0B66B32EE2FE1451362A911623363817A8F9F97E655B0C9B0EDDFCA226FB3338. It reports UnexpectedExternalChanges: [].

| Approved effect | Post-build finding |
|---|---|
| Dynamic Engine Engine\Intermediate\UbtRuns\<PID>_d0acf73a0a5904967b907cc59ad5ded9 run marker | No new marker remained; historical marker hashes were unchanged. Since no event trace was run, a temporary create/delete during the build cannot be independently confirmed or excluded. |
| Engine Engine\Intermediate\Build\SourceFileCache.bin | Absent after the build. |
| %LOCALAPPDATA%\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.dll | Unchanged: 42,496 bytes; SHA-256 D3A86F776B072A3E415964827A25066A09BC751D8D57655AAC8D678685F573D4. |
| Adjacent MarketplaceRules.pdb | Unchanged: 130,560 bytes; SHA-256 2BC29E64A9C55C71503E14A8A934D81F9CAA3711B6847B83A5D73EAEEC810563. |
| Adjacent MarketplaceRulesManifest.json | Unchanged: 8,879 bytes; SHA-256 C530FAA3B6207C0433624A273C57547BAAC1AE95E77A6B41996746D86CEB461B. |
| %LOCALAPPDATA%\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\DependencyCache.bin | Absent after the build. |
| Its two authorized missing directories: ...\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor and ...\Development | Both remain absent. |

The approved list contains six file effects: the dynamic marker, SourceFileCache, MarketplaceRules DLL, PDB, DependencyCache, and MarketplaceRules manifest. The MarketplaceRules DLL/PDB/manifest hashes and sizes did not change. The two DependencyCache parent directories were not created.

The active LocalAppData UnrealBuildTool environment XML and the existing default UBT log were unchanged in the external audit. UBA ProgramData records showed no changes. The audit used before/after metadata and hashes, not WPR. It does not provide a complete system-wide write trace and cannot rule out short-lived or unobserved writes outside the monitored paths.

## 7. Cleanup and preservation

- The R: alias was absent after the build.
- No UnrealBuildTool, compiler, linker, or UbaServer process remained in the post-run check; no TCP 1345 listener was present.
- No new UBT run marker remained; the recorded historical marker set was unchanged.
- Existing R1/R2/R3 reports and evidence were not edited or removed.
- No cleanup or rollback was performed. All build outputs and diagnostics remain in the disposable C0B environment.
- No project source, plugin descriptor, Engine source/configuration, or shared plugin binary was modified.
- No A7K41 or production asset, project, or service was accessed.

## 8. Validation gates

| Gate | Result |
|---|---|
| Reuse exact C0B workspace and project | **PASS** |
| R4 source/project/plugin/XML cache baselines | **PASS** |
| One bounded native build attempted | **PASS — one attempt only** |
| Local executor selected; UBA disabled | **PASS** |
| UBT primary logs routed to C0B | **PASS** |
| C0B post-build file inventory completed | **PASS, with manifest self-count convention documented** |
| Approved external effects reconciled | **PASS — no approved target changed or was created** |
| Unexpected external changes in monitored locations | **NONE DETECTED** |
| Full system-wide trace containment | **UNKNOWN — no WPR trace** |
| Native Editor/plugin compilation | **FAIL — exit code 6; 16 diagnostics** |
| Complete MajesticForge Editor module binary | **FAIL — not produced** |
| Runtime/editor load validation | **NOT RUN** |
| Isolated host/authenticated MCP validation | **NOT RUN** |
| WPR trace | **NOT RUN** |
| A7K41, production, Blender, or persistent services contacted | **PASS — none contacted** |

## 9. Remaining blockers and next stage

The native candidate is not buildable as recorded. The next action is a separately authorized, isolated source-correction stage in the existing C0B copy: review and fix the reported C++ errors, run targeted offline/static checks, then obtain a new explicit authorization before any additional UBT attempt. R5 authorized one build attempt and that authorization has been consumed. Do not rebuild, load, or deploy the partial outputs under R5.

After a successful full compile, the candidate would still need separate disposable runtime/Editor loading, native inspection side-effect tests, and authenticated host validation. None of those are established by this report.

**Final verdict:** R5 preflight and bounded artifact audit passed; the one native build failed. No unexpected change was found in the monitored external locations, but complete system-wide trace containment remains unproven. No candidate is ready. A7K41 remains protected, and Production Phase 6C remains **NO-GO**.
