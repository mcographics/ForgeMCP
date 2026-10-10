# ForgeMCP bridge protocol 1

The editor adapters use their own small local protocol; the external server translates
MCP calls into it. Only the Python server speaks MCP. No Codex-specific logic is built
into either application adapter.

Registration fields: `protocol_version: 1`, `session_id`, `kind` (`unreal` or `blender`),
`host: "127.0.0.1"`, integer `port`, integer `pid`, and a random session `token`.
Session registrations are runtime secrets, excluded from Git, MCP results, and logs.
An application owns its registration file and removes it on normal shutdown.
Version 0.1.2 protects Windows registration directories and files with an
owner-and-SYSTEM-only DACL before advertising a session; protection failures prevent
startup. Tokens use cryptographic randomness and rotate on bridge startup.

A connection carries one UTF-8 JSON object terminated by a newline:

```json
{"protocol_version":1,"request_id":"unique-id","token":"session-secret","command":"health","args":{}}
```

Success:

```json
{"request_id":"unique-id","ok":true,"data":{"read_only":true}}
```

Failure:

```json
{"request_id":"unique-id","ok":false,"error":{"code":"unauthorized","message":"Session authentication failed."}}
```

Malformed JSON has no recoverable correlation ID. The server rejects missing or
mismatched response IDs. Foundation commands are Unreal `health`, `project_info`,
`list_actors`, and Blender `health`, `scene_info`. Unreal actor limit is an integer
from 1 to 1000; its result includes `total_count` and `truncated`. The current editor
world is inspected, including loaded actors; unloaded World Partition content is not
enumerated. Blender reports `fps`, `fps_base`, and `effective_fps` separately.

Adapters cap requests at 16 KiB and 16 concurrent clients, with a ten-second client
lifetime. The core caps responses at 1 MiB, with a ten-second inspection exchange
timeout and sixty-second apply timeout. Outbound client lifetime resets after native
execution so a completed compilation can send its response.
JSON nesting is limited to eight containers and `args`, when supplied, must be an
object. Excessively large input closes the connection. The Python core rejects
linked/out-of-root registrations and does not reflect adapter-supplied error messages.
Sockets are nonblocking on application threads; partially received requests and
partially sent responses are buffered. There is no eval, arbitrary script execution,
unrestricted filesystem write, or asset import endpoint.

Version 0.2.0 adds Unreal `class_info`, `blueprint_info`, `blueprint_preview`, and
`blueprint_apply`, and Blender `object_info`, `scene_preview`, and `scene_apply`.
Preview arguments contain a typed `recipe`. Apply arguments contain `preview_id`
and matching `confirmation`. Previews are session-local, expire after ten minutes,
and are consumed once. Apply returns an explicit operation state (`completed`,
`rolled_back`, or `partial`); `ok: true` means a valid adapter response and must not
be substituted for checking that state. Blueprint save and placement are explicit
recipe flags. Blender recipes do not save the file. See [Engineering.md](Engineering.md).

The development registry also exposes Unreal `gas_info` for bounded read-only GAS
state inspection on one exact actor path in the idle editor world. The Blender scene
recipe allowlist includes reviewed pose-bone keyframes; neither operation executes
arbitrary application scripts.

Error codes include `invalid_request`, `invalid_arguments`, `unauthorized`,
`command_not_allowed`, `editor_not_ready`, `scene_not_ready`, `inspection_failed`,
`session_not_found`, `ambiguous_session`, `disconnected`, `timeout`, and
`invalid_response`. A disconnected registration does not prove its application is
currently running. Listing sessions performs an authenticated health check.
Engineering errors also include `invalid_recipe`, `confirmation_required`,
`preview_not_found`, `stale_preview`, `preview_limit`, `invalid_context`,
`asset_not_found`, `class_not_found`, and `object_not_found`. Apply timeouts report
`outcome_unknown`; inspect state before retrying.

See [Security.md](Security.md) for threat boundaries and update activation.
