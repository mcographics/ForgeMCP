# ForgeMCP 0.2.17 — TedsOutliner without an Engine copy

Checked October 24, 2026. **Finding: a project-local copy of the complete `EditorDataStorageFeatures` plugin has a source-supported discovery and load route in installed UE 5.6.1; the particular patched binary has not been built or loaded.** This is an offline implementation proposal, not Stage 2E acceptance or permission to build or launch. The earlier feasibility report's statement that duplicate-name selection was unverified is superseded by the source findings below. No patch, build, Editor launch, installed-Engine change, project-asset change, or Trello update occurred.

## Discovery, dependency, and module selection

- Runtime `Engine/Source/Runtime/Projects/Private/PluginManager.cpp` reads Engine plugin descriptors before project descriptors (approximately lines 809–832). `CreatePluginObject` (1234–1260) expressly allows an Engine/project duplicate and favors the project plugin when the Engine version has not already been enabled. An already enabled plugin wins, so placement must precede startup; hot substitution is not supported by this finding. `AdditionalPluginDirectories` have different `External` classification and are unnecessary here.
- UBT `Engine/Source/Programs/UnrealBuildTool/System/Plugins.cs` (`PluginType`, `ToFilteredDictionary`, approximately lines 31–45 and 272–299) also assigns the project copy precedence over the same-named Engine copy. This is an implemented rule, not an undocumented duplicate-name trick. A clone-local `Plugins/EditorDataStorageFeatures/EditorDataStorageFeatures.uplugin` retains the **same** plugin and module names; renaming would break dependency resolution.
- Enabled runtime plugins add the **selected descriptor's** `Binaries/Win64` directory to ModuleManager (`PluginManager.cpp` approximately 1810–1823). ModuleManager scans the Engine manifest first, then enabled Engine plugin directories, then project plugin directories; `FindModulePathsInDirectory` adds module-name/path mappings, with later valid project entries replacing earlier mappings (`ModuleManager.cpp` approximately 1563–1693). Its manifest gate requires the Editor BuildId, currently **43139311**. Thus source predicts the project copy's `UnrealEditor-TedsOutliner.dll` path if its manifest is valid. Actual module path and binary hash must still be measured in a future isolated process; a successful startup or plugin mount message alone is insufficient.
- The production `.uproject` explicitly enables Fab. Installed `Engine/Plugins/Fab/Fab.uplugin` explicitly depends on `EditorDataStorageFeatures`; keeping the original descriptor/module names lets that dependency resolve to the selected project copy at runtime. Keep all ten Editor modules and Fab enabled. Fab behavior with a rebuilt copy remains a runtime test.

There is a **build-system qualification**: UBT's `UEBuildTarget.ValidateModule` (approximately 1518–1530) rejects an Engine binary's direct dependency on a project-scoped module, except two unrelated exceptions. If compiling the full isolated project target brings Fab's Engine module and the project-overridden TEDS module into the same validated graph, that build may fail. `BuildPlugin` uses a temporary host project enabling only the foreign plugin and does not require compiling Fab; this is the narrower proposed build step. A future full clone-project rebuild is **not** assumed to pass. Precompiled installed Fab may load against the unchanged TEDS public ABI, but that is not yet verified.

## Smallest proposed build and isolated deployment

Use a new disposable root outside both production project and installed Engine, for example `G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Teds_NoEngineCopy_<new-id>/`:

```text
plugin_source/EditorDataStorageFeatures/       physical copy of installed plugin
plugin_package/EditorDataStorageFeatures/      new empty BuildPlugin output
isolated_project/Plugins/EditorDataStorageFeatures/  packaged project plugin
logs/, private_ddc/, private_user/              isolated test evidence/state
```

The implementation sequence, **only after separate approval**, is:

1. Create a physical disposable copy of the complete installed plugin. Exclude copied `Binaries` and `Intermediate` from the build-source copy so stale Engine binaries cannot masquerade as outputs; preserve `Source`, `Content`, descriptor and other required plugin files. Record source hashes and a manifest. Copy the already prepared isolated project separately; preserve its private DDC, registration, controller and production-preservation gates. No symlinks, junctions, or hardlinks to production/Engine writable files.
2. Apply the existing reviewed diff **only** to the disposable plugin source. Recheck it against the exact copied UE 5.6.1 files. Keep the plugin descriptor and all ten module names, including `TedsOutliner`, unchanged.
3. Proposed Win64 Editor-only packaging command (PowerShell syntax, not executed):

   ```powershell
   & 'G:/Program Files/EpicGames/UE_5.6/Engine/Build/BatchFiles/RunUAT.bat' BuildPlugin -Plugin='G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Teds_NoEngineCopy_<new-id>/plugin_source/EditorDataStorageFeatures/EditorDataStorageFeatures.uplugin' -Package='G:/ForgeMCP_Recovery_Checkpoints/Stage2E_Teds_NoEngineCopy_<new-id>/plugin_package/EditorDataStorageFeatures' -HostPlatforms=Win64 -NoTargetPlatforms
   ```

   Installed `BuildPluginCommand.Automation.cs` defines these parameters and builds `UnrealEditor` Development for host platforms, then packages the plugin. It may create `Config/FilterPlugin.ini` **inside its source plugin directory** and clears an existing package directory. Never pass the installed Engine plugin as `-Plugin`; require a new empty disposable package directory. BuildPlugin uses the installed Engine/UBT as a dependency; installed-Engine write freedom must be audited by before/after file hashes and generated-output paths during an authorized build. The static source does not prove zero incidental Engine writes.
4. Verify packaged DLL/PDB and `UnrealEditor.modules` entries for **all ten modules**, with BuildId exactly `43139311`, target/architecture and unchanged public interface. Check that no packaged file points back to the source or installed Engine via a link. Copy the package into only the isolated project's `Plugins/EditorDataStorageFeatures`; check that the isolated `.uproject` still enables Fab and ForgeMCP and that no other clone-local same-name copy exists.
5. Before any separately authorized isolated launch, audit production and clone hashes, private DDC and child-only environment, process identity and shutdown plan. In the disposable Editor, require the duplicate-selection log, an actual loaded-module path for `TedsOutliner` under the isolated project, its SHA-256 equal to the packaged binary, matching BuildId, and Fab/ForgeMCP operation. Then test LevelEditor startup/tab lifecycle. Only after independent target-map authentication can Stage 2E read-only Landscape persistence checks begin. Stop on any ambiguous selection or module incompatibility; do not substitute an Engine DLL or repair the installed Engine.

Installed `BuildPlugin` deliberately compiles the plugin's Editor modules as a package, not just one DLL. The installed plugin currently measures **282 files / 176,936,553 bytes** (~169 MiB); a physical source copy can be smaller after excluding generated binaries/intermediates, but build outputs, host project, PDBs, private DDC and shader growth are not yet measured. Current G: free space is **157,995,282,432 bytes** (~147.14 GiB); current free physical memory is **18,930,760 KiB** (~18.05 GiB). The no-Engine-copy route avoids the ~84.3 GiB installed Engine copy. Establish a bounded reserve from the actual authorized build before any launch.

## Project-local startup-order alternative

A new earlier-loading project plugin that merely calls `LoadModuleChecked("LevelEditor")` is not a proven correction. Phase ordering, LevelEditor initialization and tab-manager readiness would still need to be established, and forcing a core Editor module early could create a different lifecycle failure. The `.uproject` plugin reference does not provide a supported per-module `LoadingPhase` override. A project-local **same-name full plugin copy with the proposed deferred-registration patch** is the smallest source-backed route found that keeps Fab, TEDS and ForgeMCP intact. A single renamed shim or a copied TedsOutliner DLL alone has no verified dependency or module-selection route.

## Acceptance boundary

**Static route established; compilation, installed-Engine write scope, binary compatibility, runtime selection, Fab integration and Landscape reload remain unverified.** The strongest remaining blocker to implementation approval is whether the copied plugin builds against this installed Engine without unexpected Engine writes and yields a matching BuildId. The exact project-local override is source-supported, but no patched DLL exists and no runtime path evidence can honestly be reported yet. No previous isolated-launch approval carries forward. Stage 2E and Phase 6C remain blocked pending a separately authorized build, independently reviewed test plan, and a later separately authorized isolated Editor launch.
