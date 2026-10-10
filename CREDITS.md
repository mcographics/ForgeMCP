# Dependencies and ownership

The ForgeMCP server routing, application adapters, inspection commands, and
bridge protocol were authored for Majestic Creations in this checkout. No gimmeDG
Unreal MCP or third-party Blender MCP implementation was copied or required.

The server depends on the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
tested here at version 1.30.0 on its supported 1.x line, under its upstream MIT license.
Dependency versions used during validation are recorded in `requirements-lock.txt`.
Transitive dependencies retain their upstream licenses. Unreal Engine and Blender
remain separately installed applications governed by their respective licenses.

No distribution license has been selected for ForgeMCP source yet. Determine
that before publishing or redistributing; this file does not grant a license to the
project source or change Unreal Engine or Blender licensing.
