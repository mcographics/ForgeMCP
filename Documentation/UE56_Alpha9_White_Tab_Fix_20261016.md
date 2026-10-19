# UE 5.6 alpha.9 — Unreal tab white-screen fix

## Cause and correction

The Unreal tab loaded Vite's external JavaScript module and stylesheet from a
`file:///` URL. Chromium's module loading rules require CORS for external module
fetches; in the bundled WebBrowser environment this left the React root blank.
The failure was reproduced with the old page in Chromium. A self-contained
single-file bundle rendered the ForgeMCP interface in the same test.

The engine-wide plugin now loads a generated `Resources/ReactUI/index.html` with
its production JavaScript and CSS embedded. Its content-security policy pins the
inline module to the generated SHA-256 hash and keeps network connections disabled.
A visible loading message remains in the page if React fails to mount in a future
build. The old installed page and old package are retained in the project backup
folder; the engine install receipt records the rebuilt package and UI hash.

## Validation

- Vite production build completed successfully.
- Static bundle verifier passed: one embedded module and stylesheet, valid CSP
  hash, React mount point, embedded logo, and no external resource dependencies.
- Chromium headless loaded the built local page and found the rendered React UI;
  the previous external-module page did not mount React.
- UE 5.6.1 isolated clean-project package acceptance passed, including plugin load,
  live plugin health, and MCP project identity checks.
- Engine-wide installed UI SHA-256:
  `64116ca7d26460ccdb8ea8d93f4c488d28ef16ca5e1ccd57b5d250c8b2929079` (includes
  the official application marks and compact layout documented in the [logo update](UE56_Alpha9_Official_Partner_Logos_20261016.md) and [layout update](UE56_Alpha9_Compact_Layout_20261016.md)).
- Reissued alpha.9 archive SHA-256:
  `d953539b7dac9c505962af85e7594b95d8edc1a65049f557e4bc479dbc85da3c`.

The running Unreal editor may still have the earlier page loaded in its WebBrowser
widget. Close and reopen the ForgeMCP tab (or restart the editor) to load the new
page. Rendering inside the user's desktop Unreal WebBrowser and interaction with
the panel controls remain to be visually confirmed there.
