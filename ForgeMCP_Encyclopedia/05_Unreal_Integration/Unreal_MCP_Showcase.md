# Live Unreal MCP showcase — October 11–12, 2026

The authorized demonstration creates one separate Blueprint asset in ForgeMCPDev.
It demonstrates native Blueprint authoring through the connected Codex MCP host,
with reviewed preview/apply, compilation, saving, native read-back and editor opening.
It does not place an actor or save/change the open TestArea world.

## Inspect in Unreal

The host confirmed the asset editor opened for
`/Game/ForgeMCP_Demos/BP_MCP_Showcase_20261011`.
Find it under **Content → ForgeMCP_Demos** if the tab is closed.

- **Components:** `DemoMesh`, a native StaticMeshComponent (no mesh assigned).
- **Variables:** `DemoEnabled = true`, `DemoLabel = Created through ForgeMCP`.
- **Function:** `EchoValue`, a pure function with float `InputValue` and `OutputValue`.
  The input is wired directly to the return output; this is a graph-authoring example.
- **Compilation:** native apply reported zero compiler errors and zero warnings.

The host rejected a wrong preview confirmation, replay of the consumed preview and
duplicate creation at the same package path. It also inspected the existing wooden
box and sphere transforms and the wooden-box component's static-mesh reference.
Those world actors were read only.

## Repeat the read-only acceptance

Rediscover sessions first and substitute the current explicit session ID. Process
IDs are temporary. The verifier requires the exact local ForgeMCPDev project and
the previously saved showcase asset. It never creates, compiles or saves content.

```powershell
.\.venv\Scripts\python.exe scripts/verify_unreal_showcase_mcp.py --session-id unreal-27496
```

Use `--report Saved/ForgeMCPShowcase/<new-name>.json` to retain a new token-free
report. Existing reports are never overwritten. Failed checks exit unsuccessfully.

The verifier launches a fresh source MCP stdio subprocess, discovers the tool
registry and checks exact project identity, initialized variables, component class,
both sides of the function pin link, native Asset Registry presence, unchanged
project/world context and unchanged package checksum. The October 11 run found 85
tools and verified the 31,863-byte package with SHA-256
`7e8d94f63008e238e5c687931c3da13788fe8e044ff0b10f4b475b9dfbad34f1`.

## Evidence and limits

- `Saved/ForgeMCPShowcase/20261011-connected-host.json`: connected-host creation,
  compiler/inspection result, recipe and guard-check results.
- `Saved/ForgeMCPShowcase/20261011-readback.json`: independent source stdio read-back.
- Full Python regression suite: **288 passed**; Ruff: **passed**.
- `Saved/ForgeMCPShowcase/20261012-editor-build.log`: successful full
  ForgeMCPDevEditor build after the user saved/closed the Editor. Project/runtime
  DLLs linked and target metadata completed. The initial open-editor attempt
  failed with LNK1104; the closed-editor retry succeeded.
- `Saved/ForgeMCPShowcase/20261012-fresh-editor-readback.json`: all seven read-back
  checks passed after reopening Unreal in a fresh process, with the same package
  checksum and saved graph. Windows module enumeration also confirmed the fresh
  Editor loaded the rebuilt plugin DLL from this checkout.

The native response confirms asset opening; no screenshot or interactive visual QA
was performed. PIE execution and calling the function in gameplay remain
unverified. Saved-package loading in a fresh Editor process passed. Discovery of 85 tools does not
prove every operation works. Material, GAS, DataAsset, transfer and broader roadmap
workflows retain their separate acceptance gates. No distribution or release is implied.
