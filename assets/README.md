# ForgeMCP branding

`logo.png` is the user-selected ForgeMCP identification artwork. Preserve its
design and colours when updating application branding.

The same PNG is distributed at:

- `blender-addon/majestic_forge/resources/logo.png` for the sidebar and add-on preferences.
- `Plugins/MajesticForge/Resources/Icon128.png` for the Unreal Plugins browser,
  connection panel, Window menu and tab icon.

If the master changes, update both copies before packaging. Blender's preview
collection is created on enable and released on disable. Unreal's Slate style
is registered at editor module startup and released at shutdown.

Application UI changes require installing the updated Blender ZIP or rebuilding
and restarting the Unreal editor after saving work. Source edits do not update
an already running application automatically.

Validation for this integration: 196 Python tests and Ruff passed; Blender 5.2.2
clean-profile ZIP installation, preview-resource enable/disable lifecycle, and
bridge/export checks passed. Unreal 5.6.1 isolated editor target compiled and the
development plugin ZIP loaded and answered MCP requests in a disposable project.
These checks do not establish interactive visual verification of the logo.
