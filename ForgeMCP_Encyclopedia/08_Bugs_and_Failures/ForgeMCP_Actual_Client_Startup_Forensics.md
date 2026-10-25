# ForgeMCP — Actual-Client Startup Forensics

Date: 2026-10-22 (America/Toronto; log timestamps are local EDT unless marked UTC)  
Scope: read-only review of existing Codex, VS Code, ForgeMCP, source, and installed MCP SDK files  
**Verdict: The client did not complete the MCP handshake. One ForgeMCP process reached `server.main` logging setup, but available evidence cannot identify which overlapping attempt owned it or establish what happened at the stdio handshake boundary. No corrective code or configuration change is justified by this evidence.**

## Startup timeline

The Codex extension log is `C:\Users\Kenne\AppData\Roaming\Code\logs\20261022T220018\window1\exthost\openai.chatgpt\Codex.log`. It records these ForgeMCP errors:

| Timeout logged | Reported wait | Approximate wait start, derived from the log | Evidence |
|---|---:|---:|---|
| 22:04:18.463 | 30.0 s | 22:03:48.463 | `timed out handshaking with MCP server` |
| 22:07:04.014 | 20.0 s | 22:06:44.014 | Same error, 20 s |
| 22:10:58.726 | 30.0 s | 22:10:28.726 | Same error, 30 s |
| 22:11:02.818 | 20.0 s | 22:10:42.818 | Same error, 20 s |

The derived start times are arithmetic from the error timestamps and durations, not recorded process-start events. The last two handshake wait windows overlap by about 15.9 seconds on that assumption. This proves overlapping waits at the Codex error-reporting layer; it does not prove that two Python children were simultaneously alive.

For the final pair, VS Code logged extension host PID **37844** exiting at 22:09:10 and a new extension host PID **11628** starting at 22:09:15. The Codex extension log recorded `Spawning codex app-server` at 22:09:39 and its own `Initialize received id=1` at 22:09:42. A process snapshot showed `Code.exe` PID 11628 and its `codex.exe` child PID **28556**; the child command line identifies it as an app-server. Its process creation timestamp (22:09:31) precedes the log's “Spawning” timestamp by eight seconds, so the records do not provide an exact event-to-process correlation. The extension's `cli:` warnings at 22:10:58 and 22:11:02 report the two ForgeMCP errors. The log does not attach a distinct request ID or Python child PID to either failure, so attribution to the extension's app-server channel is strong but per-attempt causality is not fully recorded.

The project config `G:\ForgeMCP\.codex\config.toml` was last written at 21:48:16, before the final attempts. Its ForgeMCP entry specifies `G:\ForgeMCP\.venv\Scripts\python.exe`, arguments `-m server.main`, cwd `G:\ForgeMCP`, `startup_timeout_sec = 20`, and `tool_timeout_sec = 30`. It sets `FORGE_PROJECT_ROOT=G:\ForgeMCP` and `FORGE_UNREAL_SESSION_DIR=C:/Users/Kenne/AppData/Local/MajesticForge/sessions`; it does not set `FORGE_HOST_MODE`. No secret values were read. The successful earlier CLI config read reported this same effective project entry. Codex documents `startup_timeout_sec` as an MCP server option, with a default of 10 seconds, and supports `cwd` for stdio servers ([Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp#connect-codex-to-an-mcp-server)).

The 20-second error is consistent with the configured value. The 30-second error is inconsistent with that single configured value. The Codex log calls both a **handshaking** timeout and does not record resolved configuration or timer ownership per attempt. The reason the reported durations differ is **unknown**; no particular Codex setting is assigned as the cause.

## Child-process evidence

An empty file named `C:\Users\Kenne\AppData\Local\MajesticForge\MajesticForgeLogs\server-17560.log` was created at **22:10:57 EDT / 2026-10-23 02:10:57 UTC**. In the current `server.main`, `RotatingFileHandler` creates `server-<PID>.log` in `main()` after the module imports and top-level tool registration, immediately before `mcp.run(transport="stdio")` ([server/main.py](../server/main.py#L1674)). This is direct evidence that a Python process with PID **17560** executed through that logging setup. The timestamp is close to the 30-second failure and falls inside both derived wait windows; it cannot be matched to either one from available records.

The process-creation Security log query was denied because the session is not elevated. No VS Code/Codex startup or process-lifecycle entry correlates PID 17560 to a parent, executable path, exit code, stderr, or kill/reap event. A later reasoning-summary line mentions that PID while describing this investigation, but it is not process evidence. PID 17560 was absent from the later passive process snapshot; that does not establish whether it exited before the timeout, was stopped at timeout, or exited afterward. The empty host log contains no Python exception or application-level diagnostic. Thus a ForgeMCP process likely ran for at least one attempt, but the configured executable/parent mapping and lifetime are not independently confirmed.

## Startup path inspected

`python -m server.main` imports FastMCP, Pydantic and ForgeMCP modules, constructs `ConnectionManager`, constructs the workflow coordinators, and registers tools through module decorators before `main()` is entered. `main()` performs isolated-only setup if enabled, creates the log directory/handler, then calls FastMCP's synchronous `run("stdio")`.

The configured entry has no `FORGE_HOST_MODE`. Under the code's default production mode, `ConnectionManager.configured()` reads environment values and constructs registration-root paths; it does not discover sessions. The lifespan does not await Unreal authentication in production: it schedules the periodic monitor and yields. The monitor then performs `connections.discover()` synchronously inside its background task before its first network await. That local directory scan could briefly contend with protocol handling if the registry filesystem were unusually slow, but there is no measurement supporting a long stall. Production native health uses asynchronous loopback socket I/O; no awaited Unreal request is part of the production lifespan gate. By contrast, isolated mode does perform worker startup, authenticated `health`, and `project_info` before yielding, but there is no configured `FORGE_HOST_MODE` value or log evidence that the failed Codex process used isolated mode.

The tool decorators build the catalog at import time. There is no explicit network call or lock wait in the normal production top-level setup. Python imports and tool registration remain possible sources of delay because the log file is created only after they complete; no timings were recorded for them. A `RotatingFileHandler` and `logging.StreamHandler()` are configured before stdio starts. Python's default stream handler writes to stderr. A source search found no `print()` in `server.main` or its regular import path; the `print()` calls found are in separate helper/UI entry points. The MCP SDK's stdio transport reads stdin and writes protocol messages to stdout ([installed FastMCP `run_stdio_async`](../.venv/Lib/site-packages/mcp/server/fastmcp/server.py#L769), [installed stdio transport](../.venv/Lib/site-packages/mcp/server/stdio.py#L34)). No evidence of stdout contamination was found.

The installed SDK's `Server.run()` enters the configured lifespan before it starts consuming MCP messages ([installed low-level server](../.venv/Lib/site-packages/mcp/server/lowlevel/server.py#L646)). In the expected production branch that lifespan yields without awaiting discovery or native authentication, but its scheduled task can begin once the event loop yields. Exact runtime branch selection and scheduling for the failed process were not logged.

## Handshake boundary

| Stage | Verdict | Basis |
|---|---|---|
| 1. Codex requested process startup | **VERIFIED** | Codex reports ForgeMCP startup failures; the extension created an app-server session. Individual request call IDs are absent. |
| 2. OS created the ForgeMCP host process | **VERIFIED for one executing PID; exact spawn mapping UNKNOWN** | The process-specific `server-17560.log` was created by `server.main`; no process-creation event or parent/PID correlation is available. |
| 3. Python entered ForgeMCP entry point | **VERIFIED for PID 17560** | `main()` creates that PID-named log after imports and tool registration. |
| 4. MCP stdio transport began serving | **UNKNOWN** | Source calls `mcp.run()` immediately after log setup; there is no transport-ready marker or captured host stderr. |
| 5. Codex sent an MCP `initialize` request | **UNKNOWN** | The logged `Initialize received id=1` belongs to the extension↔Codex app-server setup; it is not evidence of an MCP initialize message. No stdio trace exists. |
| 6. ForgeMCP produced a valid initialize response | **UNKNOWN** | No host protocol output or response capture exists. |
| 7. Codex accepted the handshake | **FAILED** | Both attempts ended with Codex's `timed out handshaking with MCP server` error. |

The first demonstrable failure is therefore at the **Codex handshake deadline**, after at least one Python process had reached `main()` logging setup. The exact last successful protocol stage is not observable.

## Comparison with the successful bounded client test

The earlier report, `Saved/ForgeMCP_Updated_Host_Engine_Connection_Verification_Report.md`, records a real MCP SDK stdio client using the existing venv interpreter, `-B -m server.main`, cwd `G:\ForgeMCP`, and `FORGE_PROJECT_ROOT=G:\ForgeMCP`. It completed initialization in 3.5 seconds, listed 114 tools, and made authenticated Unreal requests. Its bounded client context later exited normally. No equivalent process trace or complete inherited environment snapshot was retained.

Known similarities: venv interpreter, module entry point, source working directory, stdio transport, and ForgeMCP project root. Known or possible differences: the actual Codex config omits the test's `-B`; Codex's MCP client implementation and startup orchestration differ from the SDK client; the actual process inherits environment beyond the explicit config values, and that inherited environment was not captured. Both attempts appear to use the same corrected project config, but per-attempt resolved config is absent. None of these differences is proven causal.

## Cause and next action

**Most likely failure point: before Codex received an accepted MCP initialize response. Confidence: high for the boundary, low for the underlying cause.** The PID 17560 log creation near the timeout is consistent with a long import/setup delay for one attempt, but the two windows overlap and the PID cannot be assigned to either. Slow imports/tool registration, early event-loop scheduling of the background registry scan, and client-side startup orchestration remain hypotheses. A stdout protocol violation is not supported by source inspection, and an Unreal authentication delay is not part of the normal production lifespan path.

No evidence-based code or configuration correction is established. Keep the current timeout and security settings. If a future startup trace is separately authorized, the smallest useful evidence is a single non-overlapping actual-client attempt correlated to the Python child PID, parent PID, executable, process-start time, stderr, exit status, and whether an MCP initialize request/response crossed stdio. This report initiated no such attempt.

No Editor was queried or interacted with. No host/client was launched, no configuration/source was changed, and no credentials or tokens were exposed. SlateCore and Unreal assets were not inspected or modified.
