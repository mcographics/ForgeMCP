# Installation from source

ForgeMCP's integration is free. Python 3.11+, Unreal Engine and Blender must be
installed separately. Validated native development versions are Windows, Unreal
5.6.1 and Blender 5.2.2; this is not a claim of compatibility with every version.
The core has no paid API or cloud-service requirement. Your chosen MCP client has
its own installation, account and pricing terms.

## External MCP server

Clone this repository into a directory of your choice, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]' -c requirements-lock.txt
```

Configure your MCP client to launch the absolute path to `.venv\Scripts\python.exe`
with arguments `-m server.main` and this checkout as its working directory.
Set `FORGE_PROJECT_ROOT` to the checkout. Set `FORGE_UNREAL_SESSION_DIR` to your
Unreal project's `Saved\MajesticForge` directory. The Blender adapter advertises
sessions in `%LOCALAPPDATA%\MajesticForge\sessions` by default; override this with
`FORGE_BLENDER_SESSION_DIR` when deliberately using a separate private session root.
Never upload those registration files: they contain credentials.

For Codex, `scripts/configure_codex.py` creates a local configuration. Add the
explicit Unreal session-directory override to its MCP environment when the Unreal
project is outside the checkout. Other MCP clients can use the same stdio command.

## Unreal plugin

Copy `Plugins/MajesticForge` into your own project's `Plugins` directory. Keep its
internal folder/module names. Build the project using Unreal's supported C++
toolchain; source-only clones do not include compiled DLLs. Enable **ForgeMCP** in
**Edit > Plugins** and open **Window > ForgeMCP**. Save and close the relevant editor
before replacing a loaded plugin. Unreal Engine's own license still applies.

Unreal's standard plugin packaging command is an alternative to building in your
own C++ project (set the engine path to your installation):

```powershell
$EngineRoot = 'C:\Program Files\Epic Games\UE_5.6'
& "$EngineRoot\Engine\Build\BatchFiles\RunUAT.bat" BuildPlugin "-Plugin=$PWD\Plugins\MajesticForge\MajesticForge.uplugin" "-Package=$PWD\Artifacts\UnrealPlugin" -TargetPlatforms=Win64
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

For **Export to Unreal**, set **ForgeMCP folder** to your actual checkout. Start
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
