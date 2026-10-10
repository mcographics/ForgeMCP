# Repository layout and local development host

ForgeMCP contains three separately running components:

| Directory | Purpose |
| --- | --- |
| `Plugins/MajesticForge` | Unreal plugin source and descriptor; displayed as ForgeMCP |
| `blender-addon/majestic_forge` | Blender add-on source; displayed as ForgeMCP |
| `server` | External authenticated MCP server and shared workflow coordination |
| `scripts` | Setup, packaging, installation, host creation and native verification |
| `tests` | Python unit and MCP subprocess regression tests |
| `Documentation` | Installation, security, capability evidence and original roadmap |

The internal `MajesticForge` module and `majestic_forge` Python package names remain
stable for Unreal build compatibility and Blender updates. Product-facing names are
ForgeMCP. Renaming those identifiers is a separate migration, not a display change.

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
