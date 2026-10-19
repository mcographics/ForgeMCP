# Repository layout and local development host

ForgeMCP contains three separately running components:

| Directory | Purpose |
| --- | --- |
| `Plugins/Forge` | Unreal plugin source and descriptor; displayed as ForgeMCP |
| `blender-addon/majestic_forge` | Blender add-on source; displayed as ForgeMCP |
| `server` | External authenticated MCP server and shared workflow coordination |
| `scripts` | Setup, packaging, installation, host creation and native verification |
| `tests` | Python unit and MCP subprocess regression tests |
| `Documentation` | Installation, security, capability evidence and original roadmap |

The on-disk Unreal plugin directory is `Forge`. Its descriptor filename,
`MajesticForge` Unreal module IDs and `majestic_forge` Python package name remain
stable for existing project and add-on compatibility. The shared session folder
also remains `%LOCALAPPDATA%/MajesticForge/sessions`.

The working `ForgeMCPDev.uproject`, root `Source`, `Config`, `Content`, build outputs
and application state remain local. They are ignored by Git and are not removed
from disk. This preserves ongoing development without publishing local scenes,
credentials, personal settings or unrelated Marketplace plugin requirements.

Use `scripts/create_unreal_host.py` to create a separate minimal development host
from the published plugin source. The generator refuses an existing destination.
Unreal Engine must be installed separately. Historical commits may contain the
earlier minimal development-host scaffold; the current checkout excludes it.

Generated ZIPs, Unreal binaries, Python environments, local API indexes and private
session registrations are excluded from source control. Build/install packages
locally; no proprietary engine binaries or third-party Marketplace plugins are
included in this source repository.
