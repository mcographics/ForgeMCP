# Blender alpha.6 tab visual refinement — October 16, 2026

The first alpha.5 layout did not match the supplied reference closely enough: the
logo was left-aligned, status controls were compact, and the transfer section
repeated its title inside the native Blender panel. Alpha.6 corrects those
differences with a centered, larger logo above `ForgeMCP` and its version, a taller
bridge action button, one transfer heading, and individual X/Y/Z placement rows.

The layout uses Blender's native panel and `UILayout` controls. These respect the
active Blender theme and cannot provide arbitrary CSS backgrounds, gradients, or
per-widget button colors. The card hierarchy, logo placement, information order,
and control proportions follow the reference; exact pixel styling is not available
through this native UI layer.

The transfer behavior is unchanged: default asset folder
`/Game/Content/Returns/`, reviewed preview before confirmation, and cancellation
before apply. The user's open scene is the default startup scene with two default
objects and no active object. No scene changes were made.

Validation uses Blender 5.2.2 LTS:

- Headless draw probe covers the centered logo, connection status, transfer
  settings, X/Y/Z placement fields and default destination.
- Existing clean-profile package validation passes.
- The installed alpha.5 Blender session is still open and has the add-on loaded in
  memory. Updating the installed alpha.6 files does not live-reload that Python
  module; the user must reload the add-on or restart Blender to see this pass.

Package: `Artifacts/ForgeMCP-Blender-Addon-0.2.35-alpha.6.zip`  
SHA-256: `cb549d7bf910030813f9fdd6a39b886ef6a30af1f2306ea40d8147787c144fc4`
