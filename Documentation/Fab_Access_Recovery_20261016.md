# Fab access recovery

The installed UE 5.6 Fab plugin exists at
`G:/Program Files/EpicGames/UE_5.6/Engine/Plugins/Fab/Fab.uplugin`, with its
`UnrealEditor-Fab.dll` present. Its descriptor enables it by default, but this
project sets `DisableEnginePluginsByDefault=true` and did not explicitly list Fab.
The active Editor log has no Fab plugin mount/startup entry.

Added an explicit enabled `Fab` entry to `ForgeMCPDev.uproject`, limited to Editor
targets. All previous plugin entries and other descriptor fields compare
unchanged. Backup: `Saved/FabRecovery_20261016/ForgeMCPDev.before-fab.uproject`.
JSON parsing and the preservation comparison passed. No native source changed.

This configuration fix requires restarting the Editor. It does not prove live
Fab activation, Epic account authentication, network connectivity, entitlement
visibility or downloads. Save the active regional city work before restarting.
After restart, verify `Window > Fab` and sign in as needed. Do not delete web
caches or reset account state without a demonstrated need.

The user explicitly paused city placement to prioritize Fab. A final guarded
checkpoint succeeded before restart: operation
`35a8d9f64a03c24810fb22a43f908290`, with saved-package file verification recorded
in `Saved/FabRecovery_20261016/pre_restart_city_checkpoint.json`. No city
installation or import process remains running. Fab's declared Interchange,
EditorDataStorageFeatures, EditorScriptingUtilities and EOSShared plugin
descriptors were also found in this engine installation. Restart and live store
verification remain pending.

Official reference:
https://dev.epicgames.com/documentation/en-us/unreal-engine/fab-window-in-unreal-engine
