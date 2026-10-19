# Installation from source

For the UE 5.6.1 Win64 engine-wide alpha, see [UE 5.6 alpha](UE56_Alpha.md).

ForgeMCP's integration is free. Python 3.11+, Unreal Engine and Blender must be
installed separately. Validated native development versions are Windows, Unreal
5.6.1 and Blender 5.2.2; this is not a claim of compatibility with every version.
The core has no paid API or cloud-service requirement. Your chosen MCP client has
its own installation, account and pricing terms.

## External MCP server

Current component versions: server source **0.3.11**, Blender add-on
**0.2.35-alpha.6** (Blender numeric metadata **0.2.35**). After updating
source/installing the Blender add-on, save open scene
work and reload Blender's add-on (or restart Blender), then restart the MCP server
connection in the client so its tool registry refreshes. Verify both versions and
the nine tools described in [Blender creative automation](Blender_Creative_Automation.md).
Copying installed files does not refresh a running Python module or MCP process.

Clone this repository into a directory of your choice, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]' -c requirements-lock.txt
```

Configure your MCP client to launch the absolute path to `.venv\Scripts\python.exe`
with arguments `-m server.main` and this checkout as its working directory.
Set `FORGE_PROJECT_ROOT` to the checkout. The engine-wide Unreal plugin and Blender
add-on register live sessions in `%LOCALAPPDATA%\MajesticForge\sessions`, allowing
the MCP server to discover whichever applications are currently running without
binding discovery to an Unreal project or the last project opened. Use
`FORGE_SESSION_DIR` only when deliberately choosing a shared private session root;
app-specific `FORGE_UNREAL_SESSION_DIR` and `FORGE_BLENDER_SESSION_DIR` overrides
remain available for isolated tests and deployments. Never upload registration
files: they contain credentials.

For Codex, `scripts/configure_codex.py` creates a local configuration. Do not set a
project-specific Unreal session-directory override for engine-wide use. Other MCP
clients can use the same stdio command.

## Unreal plugin

Copy `Plugins/Forge` into your own project's `Plugins` directory. The directory is
named `Forge`; keep the `MajesticForge.uplugin` descriptor filename and internal
module IDs for compatibility. Build the project using Unreal's supported C++
toolchain; source-only clones do not include compiled DLLs. Enable **ForgeMCP** in
**Edit > Plugins** and open **Window > ForgeMCP**. Save and close the relevant editor
before replacing a loaded plugin. Unreal Engine's own license still applies.

Unreal's standard plugin packaging command is an alternative to building in your
own C++ project (set the engine path to your installation):

```powershell
$EngineRoot = 'C:\Program Files\Epic Games\UE_5.6'
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildPlugin "-Plugin=$PWD\Plugins\Forge\MajesticForge.uplugin" "-Package=$PWD\Artifacts\UnrealPlugin" -TargetPlatforms=Win64
```

This invokes Unreal's native build tooling and requires its supported compiler.
It is a source build instruction, not a claim that every engine target/version has
been validated. Install the resulting plugin into a closed target project.

For a separate test host without personal settings or Marketplace dependencies:

```powershell
.\.venv\Scripts\python.exe scripts/create_unreal_host.py --destination 'D:\ForgeMCPTestHost'
```

The generator refuses existing directories. Open the generated `.uproject` with
your matching engine and build its plugin. It does not replace the local development
project. `scripts/Build-ForgePlugin.ps1` is a machine-specific development workaround;
it is not a portable substitute for Unreal's normal build toolchain.

## Blender add-on

Build an installable source ZIP:

```powershell
.\.venv\Scripts\python.exe scripts/package_blender_addon.py
```

In Blender, use **Preferences > Add-ons > Install from Disk**, select the generated
`Artifacts/ForgeMCP-Blender-Addon-<version>.zip`, then enable **ForgeMCP**. Open the
3D Viewport sidebar with **N** and select **ForgeMCP**. The add-on uses Blender's
Python runtime; the external server runs in the repository's separate environment.

For **Send to Unreal**, set **ForgeMCP folder** to your actual checkout. Start
Blender with `FORGE_UNREAL_SESSION_DIR` pointing to the target project's private
registration directory so the external worker can discover it. Select explicit
session IDs when multiple sessions exist. Review the destination, saves and
placement in the preview before confirming. Unsupported sources are rejected;
current transfer support is static meshes, not rigged character or animation export.

## Validation and support limits

Run Python regression checks using the commands in `CONTRIBUTING.md`. Native
verification scripts must use disposable projects/profiles. Automated checks do not
establish visible UI acceptance or general production readiness. Read the current
capability record in `Documentation/Active_Development_Plan.md` before relying on
an operation. Save your work before updating application adapters.
