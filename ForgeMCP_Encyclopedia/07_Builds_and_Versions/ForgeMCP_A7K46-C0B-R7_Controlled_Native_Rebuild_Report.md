# ForgeMCP Stage A7K46-C0B-R7 — Controlled Native Rebuild Report

Date: 2026-10-22 (UTC)  
Engine: Unreal Engine 5.6.1, changelist 44394996  
Target: A7K46C0B_ReadOnlyInspectorEditor Win64 Development  
Development root: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1  
Disposition: **NATIVE COMPILE PASS. One build attempt; exit code 0. One unexpected in-root telemetry-file deletion remains unattributed. Runtime validation was not performed. Production Phase 6C remains NO-GO.**

## 1. Result

The single authorized native rebuild succeeded. UBT compiled both R6-corrected source files, linked the MajesticForge Editor module, and wrote target metadata. No new compiler errors or warnings were found in the captured compiler diagnostics. All three expected module DLLs and their PDBs exist. The Runtime module and project module were reused unchanged from R5; R7 newly produced the plugin Editor DLL/PDB. This is incremental target compilation success, not a claim that every translation unit was rebuilt.

The external metadata/hash audit detected zero unexpected changes at the monitored external paths. However, the in-root comparison found one pre-existing Visual Studio Application Insights telemetry file missing after the build. Its exact path and pre-build identity are recorded in section 6. No agent cleanup or rollback command was issued. Without an event trace, the responsible process and removal cause are UNKNOWN. The audit therefore has an open preservation exception even though compilation passed.

No Editor, ForgeMCP host, protected project connection, deployment, or additional build was performed. The R: mapping created for this stage was removed after build processes exited.

## 2. Preflight

The existing R5 and R6 reports were reviewed and their expected hashes verified. The existing root, disposable project, plugin descriptor, Engine Build.version, Build.bat, source-copy manifest, R1 manifest, unchanged native inputs, R6 correction hashes, and XML configuration cache passed the runner checks.

| Gate | Result |
|---|---|
| Existing C0B root/project | PASS; exact existing paths reused |
| Engine identity | PASS; 5.6.1 / 44394996 |
| Plugin descriptor | PASS; numeric version 30 / 0.2.16-alpha.1; enabled in disposable project |
| R6 source synchronization | PASS; exact hashes below in candidate and project-local copy |
| XML cache | PASS; 354 bytes; 0CB1ADE885A5010A5E1C938D6BCBEFF5F50D4B9101A8FACC9252C8B51C6BAB93 |
| Disk space | PASS; C: 30,481,960,960 bytes free (~28.4 GiB); G: 100,102,787,072 bytes (~93.2 GiB) at preflight |
| Conflicting build / UBA | PASS; none found by preflight |
| R: | PASS; unused before stage mapping |
| Prior report/evidence hashes | PASS for pinned R3/R4/R5/R6 reports, R1 manifest, R5 log/audit and R6 source audit; post-build file-loss exception described separately |

| Corrected file | Required/current SHA-256 in both source locations |
|---|---|
| ForgeMeshImport.cpp | 2389B7A9E09774D6DEC6B97E0A656DFA574F740AC14F1822BC72727E8B5D237F |
| ForgeWorldSaveScope.cpp | C4EAA7968ED917087DBC2780BBC36E7B2AEB6B25C5A315BC2FA99B267B20B613 |

The initial inherited blanket reparse-point check flagged R6 pytest evidence links before any build. Read-only metadata inspection found 41 pytest ...current directory symlinks, all below runtime\logs\C0B-R6\pytest-temp, with existing targets inside C0B. They do not redirect build inputs. The runner records these preserved links and does not follow directory symlinks in recursive snapshots; other build-tree redirection remains rejected. No links or test evidence were deleted. This resolved a non-build evidence classification issue before the material preflight passed; no UBT attempt was consumed by those checks.

## 3. Exact build command and configuration

Build Engine: G:\ForgeMCP-StageA7G-UE56\UE_5.6

Disposable project: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject

    G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Build\BatchFiles\Build.bat A7K46C0B_ReadOnlyInspectorEditor Win64 Development -Project=R:\disposable\A7K46C0B_ReadOnlyInspector\A7K46C0B_ReadOnlyInspector.uproject -DisablePlugin=Cargo -NoUBA -NoXGE -NoSNDBS -NoFASTBuild -NoHotReloadFromIDE -WaitMutex -Log=R:\runtime\logs\ubt\C0B-R7-EditorBuild.log -XmlConfigCache=R:\disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\XmlConfigCache.bin

The temporary R: alias pointed only to the exact C0B root. Process-scoped TEMP, TMP and UnrealBuildTool_TMP were set to R:\runtime\temp\C0B-R7-UBT, then restored for the runner. No global build settings were changed. Cargo was disabled for this target; UBA, XGE, SN-DBS and FASTBuild were disabled. The existing explicit XmlConfigCache was supplied.

- Start UTC: 2026-10-22T06:10:53.1864193Z
- End UTC: 2026-10-22T06:11:42.3936188Z
- UBT exit code: 0
- Captured UBT result: Succeeded
- Executor: local Parallel executor, five actions; 46.51 seconds in executor and 48.92 seconds reported total execution time.
- Toolchain: Visual Studio 2022 14.38.33145 (MSVC 14.38.33130), Windows SDK 10.0.22621.0.

## 4. R6 correction compilation and diagnostics

The five recorded actions were:

1. Compile ForgeWorldSaveScope.cpp.
2. Compile ForgeMeshImport.cpp.
3. Link UnrealEditor-MajesticForge.lib.
4. Link UnrealEditor-MajesticForge.dll.
5. WriteMetadata A7K46C0B_ReadOnlyInspectorEditor.target.

Both corrected translation units compiled successfully. None of the 16 R5 diagnostics recurred, and the captured compiler error/warning collection is empty. This verifies the corrected namespace resolution, supported ShouldBeLoaded getter/JSON expression, descriptor count comparison, and removal of the unsafe mesh bulk-size access at compilation level. Full logs are retained; no automatic source repair or second attempt occurred.

R6 source hashes were checked again after compilation and still match in both source locations. Geometry remains explicitly unavailable, dependencies remain incomplete, and Save As remains BLOCKED in source. Successful compilation does not validate runtime read-only behavior.

## 5. Native binary identities

Paths below are relative to disposable\A7K46C0B_ReadOnlyInspector. DLLs were inspected as file bytes, not loaded. All three DLL PE machine fields are AMD64 (0x8664). Project and plugin UnrealEditor.modules files both use BuildId 43139311, matching the build Engine UnrealEditor.modules BuildId.

| Output | Bytes | Last-write UTC | SHA-256 | R7 disposition |
|---|---:|---|---|---|
| Binaries\Win64\UnrealEditor-A7K46C0B_ReadOnlyInspector.dll | 52,224 | 2026-10-22T04:57:03.6334999Z | E618A09CA2CD04A31C8ED333774FBADB204D24E30A636B1AFE34AADD52DD21A7 | Reused unchanged from R5 |
| Binaries\Win64\UnrealEditor-A7K46C0B_ReadOnlyInspector.pdb | 57,995,264 | 2026-10-22T04:57:03.6945009Z | C0A530C6FDB2EABE46BBC6C3440968C38C5452CAF7534F6A6C5979A660EC1E6F | Reused unchanged from R5 |
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.dll | 2,728,960 | 2026-10-22T06:11:41.0972827Z | A79131D390DC7F5FAFFB37F964E5AD7687EF4AE3CD0BBF73A77D06DFA4C5EC37 | Newly linked |
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForge.pdb | 90,050,560 | 2026-10-22T06:11:41.1137815Z | D53CEC74D0CD903F2220F8202980F5CF272E70EBF07B419B3EFBA0D01C6D5404 | Newly linked |
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.dll | 114,688 | 2026-10-22T04:57:13.8055021Z | 2DB7050DBA230BC7E19987AF6030DC49F86043375EFD48BD599D299102FFC62F | Reused unchanged from R5 |
| Plugins\Forge\Binaries\Win64\UnrealEditor-MajesticForgeRuntime.pdb | 60,387,328 | 2026-10-22T04:57:13.8240016Z | 962DE8CEF6BFCB28D74FCAA58845A82A2F518E5CFEB186A31DB78D66254095FE | Reused unchanged from R5 |

- Native Editor module: **PASS**, newly compiled/linked and nonempty.
- Native Runtime module: **PASS for required output presence/identity**, reused from R5; not recompiled by R7.
- Disposable project module: **PASS for required output presence/identity**, reused from R5; not recompiled by R7.
- Complete target build: **PASS**, UBT exit code 0 and target/module metadata written.
- Runtime load or behavior: **UNKNOWN / NOT RUN**.

## 6. In-root filesystem audit and unexpected deletion

The bounded before/after snapshot records 16 created files, 3 changed files and 1 missing file. R7 evidence created after the snapshot (post-build manifest, diff, acceptance/final integrity records, and this report) is additional reporting metadata and is not included in those counts. The pre-build manifest excludes itself; the diff comparison includes it as a baseline file.

Created files comprise the two corrected object files, Editor plugin DLL/PDB/import library/export data, project/plugin module manifests and target receipt, project-local DependencyCache, R7 logs/audit records, and a C0B-local build lock file. The exact paths, sizes and hashes are in C0B-R7-file-diff.json.

Changed pre-existing files:

- disposable\A7K46C0B_ReadOnlyInspector\Plugins\Forge\Intermediate\Build\Win64\x64\UnrealEditor\Development\MajesticForge\ForgeWorldSaveScope.cpp.sarif; before SHA-256 C8093FC57FDB527CCE927234815807E5134F22A775C5A1ED9192CD161AE48F84; after 82FA5F5E0E126CFBC7227F1AD9B23A4A6CB22136E9ED3895CF7A161496F0F9DB.
- disposable\A7K46C0B_ReadOnlyInspector\Intermediate\Build\SourceFileCache.bin; before SHA-256 FED58D50575C9B84C24C1B6E151626E0FF952758A05B978215F891BAA395C45B; after 777BF802B1807124DD62AA4607A1D594E0694A797D059D7CE83880AEA27BC2DD.
- disposable\A7K46C0B_ReadOnlyInspector\Plugins\Forge\Intermediate\Build\Win64\x64\UnrealEditor\Development\MajesticForge\ForgeMeshImport.cpp.sarif; before SHA-256 471373D8675888F90A56CBEFD95F406084A226075CE40A7C5AB9BAC3DD9813F5; after 82FA5F5E0E126CFBC7227F1AD9B23A4A6CB22136E9ED3895CF7A161496F0F9DB.

**Unexpected in-root deletion / preservation exception:**

    G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1\runtime\profile\LocalAppData\Microsoft\VSApplicationInsights\vstelf3e86b4023cc43f0be495508d51f588a\20261022050037_a63240673cf946298a8a2bd5b9fcd241.trn

- Pre-build size: 1,531 bytes.
- Pre-build last-write UTC: 2026-10-22T05:00:37.5015018Z
- Pre-build SHA-256: B86CBA2D4E5DB305DA495128CFAB0B9A358F0056919473C86EB3EFA336860A81
- Post-build presence: absent.
- Known identity: a .trn file in the existing VSApplicationInsights telemetry directory.
- Removal cause/process: UNKNOWN. Its absence was observed after the build; no trace attributes the deletion to UBT, MSVC, a telemetry helper, or another concurrent process.
- No agent deletion, evidence cleanup, restoration, or rollback was issued. The missing bytes were not reconstructed.
- Remaining files were preserved. The anomaly is recorded rather than silently excluded from the audit.

R5 and R6 reports retain their expected hashes. The source/configuration files do not appear in the changed/deleted sets. Earlier generated SARIF files were updated by compilation; the original R5 build logs and reports remain available. No claim is made that every pre-existing C0B file survived unchanged.

## 7. Six external file effects and directory audit

The exact R5 policy was reused. Pre/post presence and named-file SHA-256 values are in C0B-R7-external-prebuild.json and C0B-R7-external-postbuild.json.

| Approved effect | Before / after result |
|---|---|
| One new PID-specific Engine\Intermediate\UbtRuns marker | No new marker remains; historical marker hashes unchanged. A transient marker create/delete is not independently observed without tracing. |
| G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine\Intermediate\Build\SourceFileCache.bin | Absent before and after |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.dll | Unchanged; 42,496 bytes; SHA-256 D3A86F776B072A3E415964827A25066A09BC751D8D57655AAC8D678685F573D4 |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRules.pdb | Unchanged; 130,560 bytes; SHA-256 2BC29E64A9C55C71503E14A8A934D81F9CAA3711B6847B83A5D73EAEEC810563 |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\Win64\x64\A7K46C0B_ReadOnlyInspectorEditor\Development\DependencyCache.bin | Absent before and after |
| C:\Users\Kenne\AppData\Local\UnrealEngine\Intermediate\Build\BuildRules\MarketplaceRulesManifest.json | Unchanged; 8,879 bytes; SHA-256 C530FAA3B6207C0433624A273C57547BAAC1AE95E77A6B41996746D86CEB461B |

The two approved LocalAppData DependencyCache parent directories, A7K46C0B_ReadOnlyInspectorEditor and its Development child under UnrealEngine\Intermediate\Build\Win64\x64, remain absent. The project-local DependencyCache created inside C0B is a separate file.

The monitored Engine Intermediate\Build tree, LocalAppData UnrealEngine Intermediate\Build tree, ProgramData UBA tree, default UBT log, and environment-configuration guard produced no unexpected external change. The historical UBT markers were retained.

**External audit result: zero unexpected changes detected at monitored locations.** It is a before/after metadata/hash audit with timestamp comparison normalized to UTC ticks. No WPR/system-wide trace ran. Unobserved transient or unmonitored writes cannot be conclusively excluded. This external result does not cancel the in-root telemetry-file deletion.

## 8. Process and alias completion

The build runner waited for build processes to exit, restored its process-scoped temporary variables and removed only the R: mapping it had created after verifying the mapping still pointed to C0B. Post-run audit found:

- No remaining identified UBT/MSBuild/compiler/linker process.
- No remaining UBA process or TCP 1345 listener.
- No R: substitution mapping.
- No new UBT marker remaining.
- No Editor or ForgeMCP host launch by this stage.
- No partial-output cleanup or rollback.

## 9. Evidence index

All following paths are beneath runtime\logs\ubt.

| Evidence | Bytes | SHA-256 |
|---|---:|---|
| C0B-R7-build-runner.ps1 | 24,160 | AB05C23A9AAA7852971F640BCB6B85F916B472B96AE5C1EFF551CC20510BE0E6 |
| C0B-R7-EditorBuild.log | 5,772 | 242D43FB5826AC8364D9CD7D87BD0CE7B94825EC6C1588F359CF8B28A7364584 |
| C0B-R7-EditorBuild-stdout.txt | 1,875 | B2E61725396CA6A339911CDB76D71120310479FAAD6B3327A7D9893BF79BDE45 |
| C0B-R7-run-summary.json | 2,089 | 846D018E90D6EF4B8DB7AE17B729108AE7AC95F02B17714C482B382A47886AC4 |
| C0B-R7-prebuild-manifest.json | 282,929 | 6AE95E01D45F268BD0799EEBF52CDCA6057624437E6142DE50E52F19B2FB5E5B |
| C0B-R7-postbuild-manifest.json | 268,476 | C9621A9B332AFC89AF67430D1D9A5503FD457769D6AED6E81E9BF06C9D3466B1 |
| C0B-R7-file-diff.json | 10,812 | 261D793C28DB50597F16A8357BC4A6A3F2CBCBEC86D790B5FC2279DF6FC89EEB |
| C0B-R7-external-prebuild.json | 1,145,926 | 7B5C7A012C92C42CDF693E764ED6F2114A12853BE5088A52A0D1EB214F848605 |
| C0B-R7-external-postbuild.json | 5,473 | 13D42FDD181F6B3C7E8B0B014A2B116B7C83F3F19C4A4E5614A474042EDDDCFB |
| C0B-R7-acceptance-audit.json | 2,816 | 71C7E731E4D55FD1E802D8D8C0288F7C101617364A1226E9B07CB89BA5599E09 |
| C0B-R7-final-integrity.json | 2,205 | E4A9464C4DC1F49DBF0F46F668014AF2D403381CC8536B9C7C600C283982D5FF |

## 10. Gate disposition and recommended next stage

| Gate | Disposition |
|---|---|
| Material preflight / R6 hashes / synchronization | **PASS** |
| Exactly one build | **PASS; authorization consumed by this attempt** |
| R6 corrected translation units compile | **PASS** |
| Complete native target build | **PASS; exit code 0** |
| Expected module DLL/PDB identities | **PASS; Editor module new, Runtime/project modules reused** |
| Unexpected monitored external writes | **NONE DETECTED; tracing limitation retained** |
| In-root write audit | **COMPLETED WITH EXCEPTION; one unexplained pre-existing telemetry-file deletion** |
| Build-process exit / alias removal | **PASS** |
| Runtime plugin loading / authenticated inspection | **NOT RUN / UNKNOWN** |
| Read-only runtime side-effect acceptance | **NOT RUN / UNKNOWN** |
| Production readiness | **NO-GO** |

The compiled candidate is technically available for a separately scoped disposable runtime-validation stage. First disposition the recorded telemetry-file loss; do not silently treat preservation as fully clean or initiate cleanup/recovery. No additional broad infrastructure investigation is required by this report. Any causal investigation should remain limited to this exact telemetry artifact and existing build evidence.

A later explicitly authorized disposable runtime stage can verify module loading, the four-tool preservation_readonly profile, authentication, and before/after package/file state without contacting A7K41. Geometry remains unavailable and Save As remains blocked. This successful build alone does not authorize those operations or establish native inspector side-effect safety.

No additional build, Editor/host launch, deployment, protected project connection, package save/discard, Landscape operation, or unrelated cleanup was performed. A7K41, ForgeMCPDev, production city, Blender, and shared plugins remain outside this stage.

**Final disposition: NATIVE COMPILE PASS; runtime UNVERIFIED; one in-root preservation anomaly remains open. Production Phase 6C remains NO-GO. Stop after reporting.**
