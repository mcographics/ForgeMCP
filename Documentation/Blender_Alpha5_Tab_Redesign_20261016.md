# Blender alpha.5 sidebar redesign — October 16, 2026

The Blender add-on advances to **0.2.35-alpha.5** and restyles its native 3D
Viewport `ForgeMCP` sidebar around the supplied reference. A logo/version card and
Bridge Status card sit above a grouped Send to Unreal panel. The panels expose the
current bridge state, loopback endpoint, session, last authenticated request,
auto-start option, ForgeMCP path, optional Unreal session, asset path, save/place
options, placement coordinates and transfer status/preview.

The existing native Blender controls, local authenticated bridge, exact source-name
behavior, `/Game/Content/Returns/` default and reviewed preview/confirm/cancel
workflow remain in use. No scene objects, preferences, or project files were
changed. Blender numeric metadata remains `(0, 2, 35)`.

Validation on Blender 5.2.2 LTS:

- The headless sidebar draw probe registers the add-on, exercises both panel draw
  methods, checks the visible sections and transfer properties, and confirms the
  default asset path while the startup scene remains unchanged.
- Source branding verification passed.
- The alpha.5 ZIP passed the existing clean-profile install and layered native
  add-on acceptance suite.
- The updated user add-on was installed at
  `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\majestic_forge`;
  installed `__init__.py`, `transfer_ui.py` and logo bytes match the source hashes.
- A fresh headless Blender process imported, registered and unregistered the
  installed add-on and reported alpha.5.
- No interactive Blender window was open, so final visual review of spacing and
  colors in the live sidebar remains unverified.

Package: `Artifacts/ForgeMCP-Blender-Addon-0.2.35-alpha.5.zip`  
SHA-256: `8d4e752f8e004768a9cabdb7c422e76a65a09a600870f863859ee203301b00b4`
