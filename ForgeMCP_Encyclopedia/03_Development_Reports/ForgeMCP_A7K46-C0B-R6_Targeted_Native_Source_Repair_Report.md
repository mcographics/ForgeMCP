# ForgeMCP Stage A7K46-C0B-R6 — Targeted Native Source Repair

Date: 2026-10-22 (UTC)  
Engine: Unreal Engine 5.6.1, changelist 44394996  
Mode: Isolated source correction and offline validation  
Development root: G:\ForgeMCP\Saved\ForgeMCP-C0B-Dev-20261022T011443Z-7d4bd2d046f14a12a44e6b06a399cfc1  
Disposition: **SOURCE CORRECTED; STATIC CHECK PASSED; NATIVE COMPILE NOT YET VERIFIED.** No UBT, compiler, linker, Unreal Editor, or ForgeMCP host was launched. Production Phase 6C remains **NO-GO**.

## 1. Result

All 16 R5 diagnostics have a targeted source correction in the existing C0B candidate. Exactly two native source files were changed, and each was synchronized byte-for-byte into the existing disposable project's local Forge plugin. No header, Python implementation, authentication code, catalog definition, original repository source, Engine source, or shared plugin was edited.

The mesh preservation inspector now reports geometry unavailable rather than calling the non-const bulk-size accessor or using the unvalidated clone/deserialization path. Loaded identity, package state, material references, and existing incomplete preservation fields remain available. No geometry counts or bounds are fabricated.

The world inspector uses the installed UE streaming getter, bounds the signed descriptor budget before comparing it with UE's unsigned count, qualifies the existing namespace helpers, and replaces the nonexistent project-content predicate with the existing root-containment helper. Save As remains BLOCKED.

Offline validation passed: 96 focused Python tests, Ruff, Python compilation, seven source/catalog/API/evidence assertion groups, and inspection of the actual four-tool catalog and schemas in-process. These results do not establish native compilation or runtime side-effect acceptance.

## 2. Diagnosis and all 16 corrections

R5's existing report, C0B-R5-EditorBuild.log, and C0B-R5-EditorBuild-stdout.txt were reviewed. Original line numbers below refer to R5. Several diagnostics share one root cause.

| # | R5 location / error | Root-cause classification | Correction |
|---:|---|---|---|
| 1 | ForgeMeshImport.cpp:637, C2662, GetBulkDataSize | Const-correctness; unvalidated geometry access | Removed the bulk-size and clone-based geometry extraction from DescribePreservationMesh. Geometry is explicitly unavailable; no const_cast or lazy GetMeshDescription path was introduced. |
| 2 | ForgeWorldSaveScope.cpp:259, C4018 | Signed/unsigned comparison | Reject negative or over-budget TotalDescriptors before converting the remaining bounded budget to uint32 for comparison with GetActorDescInstanceCount(). |
| 3 | :332, C2039, GetShouldBeLoaded | Unreal API compatibility | Replaced the unavailable name with UE 5.6.1's public virtual bool ShouldBeLoaded() const. |
| 4 | :332, C2661, SetBoolField | Cascading expression diagnostic; JSON API review | The source already supplied a field name and value. Corrected the invalid getter in the second argument; the resulting call supplies the supported bool expression. No JSON signature was invented. Native confirmation of the cascade diagnosis awaits compilation. |
| 5 | :416, C3861, FullPath | Namespace visibility | Qualified the existing helper as ForgeWorldSaveScope::FullPath. |
| 6 | :487, C3861, StringValue | Namespace visibility | Qualified the existing helper as ForgeWorldSaveScope::StringValue. |
| 7 | :490, C3861, StringValue | Namespace visibility | Same qualification. |
| 8 | :528, C3861, StringValue | Namespace visibility | Same qualification. |
| 9 | :535, C3861, PackageFile | Namespace visibility | Qualified the existing helper as ForgeWorldSaveScope::PackageFile. |
| 10 | :539, C3861, FullPath | Namespace visibility | Qualified the existing helper. |
| 11 | :540, C2039, IsWithinProjectContent | Missing helper declaration/definition | Reused the existing IsWithinRoot helper with explicit FPaths::ProjectContentDir(). |
| 12 | :540, C3861, IsWithinProjectContent | Same missing helper; second diagnostic | Same correction; no permissive replacement predicate or new mount policy was added. |
| 13 | :551, C3861, PackageFile | Namespace visibility | Qualified the existing helper. |
| 14 | :552, C3861, FullPath | Namespace visibility | Qualified the existing helper. |
| 15 | :564, C3861, StringValue | Namespace visibility | Qualified the existing helper. |
| 16 | :595, C3861, StringValue | Namespace visibility | Qualified the existing helper. |

FullPath, StringValue, and PackageFile were already defined inside namespace ForgeWorldSaveScope before the global FForgeWorldSaveScope::Handle method. Their definitions were not absent; the global method's unqualified lookup was wrong. IsWithinProjectContent, in contrast, had no definition in that namespace. This distinction avoids adding duplicate helper implementations or a broad using directive.

## 3. Exact modified source instances and hashes

Candidate source directory:

source\Plugins\Forge\Source\MajesticForge\Private

Synchronized project-local directory:

disposable\A7K46C0B_ReadOnlyInspector\Plugins\Forge\Source\MajesticForge\Private

| File, in both directories | Before SHA-256 | After SHA-256 | Bytes before → after | Synchronization |
|---|---|---|---:|---|
| ForgeMeshImport.cpp | 5AF48A84CADFA998FBB0AB9C61B98A257C65C65E0912BB0F4F2C12FA4E3D3BD1 | 2389B7A9E09774D6DEC6B97E0A656DFA574F740AC14F1822BC72727E8B5D237F | 67,793 → 63,882 | Exact byte/hash match |
| ForgeWorldSaveScope.cpp | 86369AB27CC83FEE6E35BF4449E195C6599010DC17FF9672F98EE8C41A9C1708 | C4EAA7968ED917087DBC2780BBC36E7B2AEB6B25C5A315BC2FA99B267B20B613 | 24,898 → 25,210 | Exact byte/hash match |

The before hashes match the R5 baseline. Comparison with the R5 post-build manifest found exactly these four changed source instances across tracked .cpp, .h, .py, .uproject, and .uplugin inputs. All other tracked source/configuration instances in that comparison were unchanged.

Current correction locations include ForgeMeshImport.cpp:632 for disabled geometry extraction, and ForgeWorldSaveScope.cpp:259–260 for the bounded unsigned comparison, :333 for ShouldBeLoaded, :417 for the first qualified FullPath call, and :541 for the reused containment predicate. No native header was changed.

The source synchronization and before/after values are recorded in runtime\logs\C0B-R6\source-repair-audit.json.

## 4. Installed UE 5.6.1 API evidence

The following files were inspected read-only from G:\ForgeMCP-StageA7G-UE56\UE_5.6\Engine. No web documentation or guessed API name was substituted for the installed source.

| File / line | Verified declaration or implementation | SHA-256 |
|---|---|---|
| Source\Runtime\MeshDescription\Public\MeshDescription.h:1355 | int64 GetBulkDataSize() is non-const and calls BulkData.GetPayloadSize(). | 3375FC39DC1B8F531F6A872456A1BFB250F13831A00E463F79D1089FDD9ED2DD |
| Source\Runtime\Engine\Classes\Engine\LevelStreaming.h:532 | virtual bool ShouldBeLoaded() const. It reports desired streaming state; it is distinct from IsLevelLoaded(). | 3F62B2F607B44853E268899C3004A593ADDB446CE146F9E1967A393416E85CF1 |
| Source\Runtime\Engine\Public\WorldPartition\ActorDescContainerInstance.h:143 | uint32 GetActorDescInstanceCount() const. | 0E2EA33AA964F2B1EF5088D970A9D03CDB8D0974B35AA9230F4502FBF5CAE0FF |
| Source\Runtime\Json\Public\Dom\JsonObject.h:268 | SetBoolField(const FString& FieldName, bool InValue); the adjacent overload accepts FString&& and bool. | 994187B4DF8C40F811008A76D335BC97D96F84C6E600589FD52C21FF86E18AB1 |
| Source\Runtime\Engine\Private\StaticMeshSourceData.cpp:252 | FStaticMeshSourceModel::CloneMeshDescription falls back to LoadMeshDescription when no cached description exists. | 573CE84E276913D38C58B233BCF0DDACBE75822627462E09F190CC03CA4CF129 |

The clone implementation explains why merely changing the BulkData pointer type would be insufficient for this preservation inspector. A const-looking public operation can still deserialize source data; its side-effect and resource bounds were not validated in C0B. R6 therefore takes the explicitly permitted unavailable-data path.

## 5. Read-only safety assessment

The changed DescribePreservationMesh branch does not call GetBulkDataSize, CloneMeshDescription, GetMeshDescription, SavePackage, MarkPackageDirty, object/package loading, physics creation, or compilation. Geometry availability is false with a specific reason; inspection_complete remains false. Collision/body setup, full dependencies, external relationships, and preservation readiness retain their existing incomplete/unavailable results.

Other existing mesh import/replacement routines in ForgeMeshImport.cpp still contain their own operations; they were not changed or presented as read-only. The mesh_info dispatch returns from the preservation inspector branch before those unrelated routines. The four-tool profile does not expose their mutation tools.

The world inspector retains:

- Game-thread/Editor context checks.
- No SavePackage, dirty-flag mutation, package/actor loading, level transition, World Partition initialization, physics creation, or mesh compilation call in the inspected implementation.
- The existing limits of 128 streaming levels, 512 descriptors, depth 8, 512 directory entries, 128 reported package files, 0.5-second directory scans, and 256 dependency rows.
- Existing directory-containment and reparse-point rejection, collision reporting, and incomplete-observation indicators.
- Explicit false save_preflight_complete and save_as_prevention_ready values and BLOCKED save_readiness.
- Unknown serializer-generated effects and incomplete dependency evidence.

These are source-level findings. R6 did not execute either inspector in Unreal and does not establish runtime non-mutation, complete ownership evidence, or safe Save As behavior.

Authentication, process/session identity checks, host configuration, and the four-tool profile implementation were not edited. No package exception was added or broadened.

## 6. Offline validation

Validation used the existing G:\ForgeMCP\.venv\Scripts\python.exe against the isolated C0B source directory. The environment was not installed or upgraded. Tests used a C0B-local temporary directory.

| Validation | Exact result and limit |
|---|---|
| Focused regressions | **PASS: 96 passed in 5.65 seconds.** test_host_config.py, test_connections.py, test_security.py, test_dirty_packages.py, and test_native_plugin_contract.py; pytest-asyncio enabled explicitly. |
| Process-launch guard during tests | Actual subprocess.Popen construction was blocked. Unit tests used synthetic registrations/mocks and local protocol fixtures; no ForgeMCP host or Editor was launched. |
| Ruff | **PASS:** python -m ruff check server tests scripts; All checks passed. |
| Python compilation | **PASS:** python -m compileall -q server tests scripts; exit code 0. |
| Actual registration/schema inspection | **PASS, in-process:** restricted the actual FastMCP catalog to preservation_readonly and inspected list_tools without running a transport/lifespan or calling an Editor tool. All four tools retain readOnlyHint and a session_id schema field; world scope requires session_id and keeps destination_package optional. |
| Source/API assertions | **PASS:** seven groups cover prohibited calls, honest geometry unavailability, helper resolution, installed signatures, retained scan bounds/BLOCKED readiness, source change scope, and R5 report integrity. |
| Native C++ compilation | **NOT RUN / NOT YET VERIFIED.** No UBT or compiler invocation. |
| Native/runtime side-effect acceptance | **NOT RUN.** No Editor, host, bridge, or protected project access. |
| MCP subprocess tests | **NOT RUN:** test_mcp_stdio.py launches a host, which R6 prohibits. Its relevant registration/schema requirements were checked in-process instead. |

Two initial pytest harness attempts failed before tests ran because replacing subprocess.Popen with a function broke Windows/MCP imports. The final guard preserved its class interface and the 96-test run passed. Those failed harness logs remain as pytest.txt and pytest-offline.txt; the passing run is pytest-guarded.txt. Static-check harness assumptions were also corrected before its final successful result: asyncio's internal socketpair was initialized before blocking outbound connections, the mesh function slice was bounded after its definition, and optional legacy session schema fields were distinguished from the required world-scope session field. No implementation change was made to satisfy those harness corrections.

No full-suite or native compile PASS is claimed.

## 7. Evidence and preservation verification

R6 supporting records are under runtime\logs\C0B-R6:

| Record | SHA-256 |
|---|---|
| source-repair-audit.json | 467AEB973DB2C6E4D581778CD9559F9839D543887F033A117C6BE21CB4C2866C |
| static-validation.json | 5F44524F954FF31B6BC5CAFC254A7F0EDE662517002EEA48A443AEC6D6C2EA92 |
| schemas.json | 5FD384E29EF72FF90194176E20D962FF979BFC45DE837146B0A84CB9709FAB97 |
| pytest-guarded.txt | BA08E7FA2D31D59CEC283AE6803701FFB9CAD3100A25D8F1154CC6896DE92EF1 |
| ruff.txt | A4443AFDCFB6D7363ADB285762515CCF7CF50473B1A05C20C1A50F6BED4D26B0 |
| compileall.txt, empty output with exit code 0 | E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855 |
| prior-evidence-verification.json | 45E420961E42AB11E9EE2C40AE61FC5A5D6FADD00F3A378A0E97B8B755A4AA6A |

Thirty existing evidence/binary files selected from the R5 post-build manifest (prior root reports, UBT evidence, and Win64 DLL/PDB outputs) verified unchanged. The R5 final report also retains SHA-256 4FDF74F43D9D5BF92EC55B0E0F9CC1A36DF0F28AE1B28BBA979A7CC47D96CDEB. Existing partial outputs were retained. Python validation generated normal caches/test artifacts and R6 logs within the isolated source/validation areas. No cleanup or rollback occurred.

No new development workspace, project, Engine installation, backup, drive alias, WPR session, UBT invocation, deployment, or application connection was created.

## 8. Remaining concerns and rebuild readiness

**SOURCE CORRECTED:** the 16 recorded diagnostics have targeted source changes, with synchronized candidate/project-local copies.

**STATIC CHECK PASSED:** focused Python regression, lint, compilation, actual in-process schema/catalog inspection, installed API review, and bounded source assertions passed.

**NATIVE COMPILE NOT YET VERIFIED:** R5 remains the last native build and failed. C++ compilation can expose additional diagnostics after these corrections. Runtime plugin loading, inspector side-effect acceptance, bounded memory/time behavior, live authentication, and application data remain untested in R6.

Geometry intentionally remains unavailable until a separately authorized disposable side-effect test validates an acceptable bounded accessor. Full mesh/world preservation dependencies remain incomplete, Save As remains BLOCKED, and this stage does not authorize saving A7K41 packages or Landscape operations.

**Readiness:** GO to prepare/request one separately authorized controlled rebuild of this exact synchronized candidate, reusing the established C0B environment and build-boundary controls. **Execution under R6: NO-GO.** The R5 one-build authorization is consumed; no new build was attempted. A future build needs fresh hashes, disk-space/guard checks, and its own exact authorization. Runtime acceptance would remain a later independent gate.

A7K41, production, ForgeMCPDev, Blender, and existing services were not accessed. Production Phase 6C remains **NO-GO**. Stop after this report.
