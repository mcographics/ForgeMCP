# UE 5.6 alpha.9 — official application marks in the transfer UI

ForgeMCP now uses the application marks directly on their corresponding
connection and transfer actions. The assets are embedded in the local React
bundle, so the editor tab makes no web requests to display them.

## Asset provenance

- `web-ui/src/assets/partner-logos/unreal-engine.svg` is copied unchanged from
  the UE 5.6 installation's `Engine/Content/Editor/Slate/About/UnrealLogo.svg`.
  Epic's current brand guidance is available on the [Unreal Engine branding
  page](https://www.unrealengine.com/en-US/branding).
- `web-ui/src/assets/partner-logos/blender.svg` is the Blender application mark
  copied unchanged from Blender's official source repository at
  [`release/freedesktop/icons/scalable/apps/blender.svg`](https://projects.blender.org/blender/blender/raw/branch/main/release/freedesktop/icons/scalable/apps/blender.svg).
  Blender's [logo page](https://www.blender.org/about/logo/) describes use of
  its logo and brand guidelines.

The Unreal mark is used in its supplied white-on-transparent treatment; the
Blender mark keeps its supplied orange, blue, and white colors. The React UI does
not recolor, crop, or redraw either logo. ForgeMCP remains identified as an
independent integration in the panel footer.

## Placement and validation

- Blender mark: Blender Connection heading and Send to Blender action.
- Unreal Engine mark: Transfer to Unreal heading and Send to Unreal action.
- Both SVGs are inlined into the single-file HTML bundle; CSP remains local-only.
- The Unreal package verifier checked the bundled page and passed a clean UE 5.6.1
  editor load, plugin health, and live MCP project identity verification.
- The layout refinement is recorded in the [compact reference-matched layout
  note](UE56_Alpha9_Compact_Layout_20261016.md).
- Chromium headless rendered the updated panel with both supplied marks visible.
- Installed UI SHA-256:
  `64116ca7d26460ccdb8ea8d93f4c488d28ef16ca5e1ccd57b5d250c8b2929079`.
- Alpha archive SHA-256:

The desktop Unreal WebBrowser panel still needs a visible refresh after the UI
bundle update. Close and reopen the ForgeMCP tab to load the latest local page.
