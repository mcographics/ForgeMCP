# Dependencies and ownership

The ForgeMCP server routing, application adapters, inspection commands, and
bridge protocol were authored for Majestic Creations in this checkout. No gimmeDG
Unreal MCP or third-party Blender MCP implementation was copied or required.

The server depends on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
tested here at version 1.30.0 on its supported 1.x line, under its upstream MIT license.
Dependency versions used during validation are recorded in `requirements-lock.txt`.
Transitive dependencies retain their upstream licenses. Unreal Engine and Blender
remain separately installed applications governed by their respective licenses.

All original ForgeMCP source and original documentation are released under the
[MIT license](LICENSE), copyright 2026 Majestic Creations. This includes the
Unreal plugin, separate external server and original Blender add-on source. The
project is free to download, use and modify; no ForgeMCP purchase or paid API is
required. MIT permits commercial reuse and redistribution under its notice terms.

This grant does not relicense Unreal Engine, Blender, dependency code, trademarks,
or other upstream material. Unreal Engine's EULA and Blender's GPL remain applicable
to those applications. The Blender Extensions website has its own submission
licensing requirements; this repository is not a listing on that platform.

The command-signature reference catalog under `Documentation/Reference_Audits`
was extracted from [aadeshrao123/Unreal-MCP](https://github.com/aadeshrao123/Unreal-MCP)
at commit `dadf24f460da4249ce7d94ee23a025b0b6e5cdff`. It is attribution/reference
material, not a runtime dependency or copied implementation. Upstream is MPL-2.0;
its pinned license is retained in `LICENSES/Unreal-MCP-reference-license.txt`.
Upstream-derived catalog material retains its upstream terms, rather than being
relicensed by ForgeMCP's MIT grant. Pinned source links accompany the catalog.

Python dependencies are installed separately, not bundled in the source-only
Blender ZIP. Their validated versions appear in `requirements-lock.txt`; they
retain their individual licenses. See [the metadata inventory](THIRD_PARTY_NOTICES.md).
Earlier commits contain Unreal-generated development-host scaffolding with Epic
copyright notices; those upstream notices remain applicable to that material.
Generated source-only packages include the
ForgeMCP MIT notice. No Unreal Engine binaries, Blender binaries or third-party
Marketplace plugins are included in this Git repository.
