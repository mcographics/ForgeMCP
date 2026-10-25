# ForgeMCP persistent Codex connection correction

Date: October 22, 2026 (America/Toronto)  
**Verdict: Configuration correction applied and validated; persistent actual-client connection and idle-green behavior NOT YET VERIFIED. Client extension refresh required.**

## Effective configuration finding

The project configuration `G:\ForgeMCP\.codex\config.toml` overrides the user entry. Reading only `C:\Users\Kenne\.codex\config.toml` in the earlier investigation missed that override. The installed owning Codex executable's `mcp get forgemcp --json` confirmed the effective configuration already had:

- Existing venv Python command, `-m server.main`.
- Explicit `cwd = "G:/ForgeMCP"`.
- Startup timeout 20 seconds and tool timeout 30 seconds.
- An unrelated **COSMOS** path in `FORGE_UNREAL_SESSION_DIR`.

Codex supports cwd directly; no shell wrapper, PYTHONPATH workaround or new environment is needed. [Official MCP configuration reference](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) documents the cwd setting and extension refresh.

## Authorized correction

Backed up the project configuration before editing:

`G:\ForgeMCP\.codex\config.toml.forgemcp-backup-20261023T014816Z`

Backup SHA-256: `25DADCF2F4BA86081B5EC0EBA0F5EEFBCEF2F2A4DFC0DB92988C4EC707478EDD`.

Changed **only** the existing entry's session-directory value:

```toml
FORGE_UNREAL_SESSION_DIR = "C:/Users/Kenne/AppData/Local/MajesticForge/sessions"
```

That directory contains the verified unreal-18588 registration. Command, arguments, cwd, timeouts and authentication/authorization settings were unchanged. TOML parsed successfully; an object comparison checked that only the intended setting changed. The installed Codex executable now reports the corrected effective value. Updated file SHA-256: `3BF71C3E212E228BF7FB409F97B68C8A7342FC644CB2AE6A246F4A068B4E22FD`.

The foreign override was a concrete configuration mismatch, **not a proven cause of the earlier MCP handshake timeout**. ConnectionManager also searches its other configured discovery root, so this correction must not be described as a verified timeout fix.

## Actual client and idle behavior

No standard server.main host was running before or after the edit, and this actual chat still exposes no ForgeMCP tools. Configuration validation with `codex mcp get` does not launch or test the client connection. No standalone MCP client/surrogate host was started. Both Editors, PIDs 5028 and 18588, remain running.

The indicator does **not** track an indefinitely connected socket: native requests use short-lived exchanges. Source makes it green when a listener exists and the last authenticated request is at most six seconds old; yellow means older activity. The existing Python host already performs authenticated periodic health checks, sleeping two seconds after each cycle. A healthy running host can therefore keep it green during user idle without added traffic, but slow/failed cycles can exceed six seconds. No heartbeat or UI-code change is currently justified.

**Actual rendered idle-green behavior: NOT OBSERVED.** No additional keepalive requests were sent. Without a retained client-owned host, persistent green cannot be accepted.

## Exact remaining action

In the owning Codex IDE extension, open **gear → MCP servers**, leave the existing forgemcp entry unchanged, and select **Restart extension**. If that action is unavailable, use VS Code **Ctrl+Shift+P → Developer: Reload Window**, then resume this thread. This transport refresh cannot be invoked through any tool exposed to the agent; editing config did not hot-reload the current connection.

After refresh, verify tools from this actual Codex client against **unreal-18588**, then observe normal idle behavior without artificial requests. If the same startup timeout recurs, preserve its new startup error and stop; do not infer this correction solved it or increase timeouts speculatively.

No rebuild, Editor termination/restart, asset/level edit, security-policy change, surrogate host or indicator change occurred. SlateCore was deliberately left outside this task. **Persistent connection restoration remains incomplete pending the owning-client refresh and acceptance.**

## October 23 follow-up — repeated reload failure and targeted import correction

The advice above to reload VS Code is superseded by this follow-up. The owner had already done so repeatedly. The actual extension logged another `forgemcp` handshake timeout at **2026-10-23 00:09:53 EDT**, after the project entry had been switched to `server.bootstrap`. No ForgeMCP tools appeared in that chat, and no persistent Python host was observed. Reloading alone did not repair the connection.

The bootstrap was extended to record PID and monotonic phase markers in a stage-owned file under `Saved`. Controlled starts through the installed Codex CLI then reached `python_entry` but failed to finish `import server.main` even with a temporary 60-second startup override and a turn kept alive long enough to reach that limit. Temporary Python stack dumps repeatedly showed `importlib` reading module data while importing the MCP SDK and Pydantic. This establishes an import/read delay in that Codex child; it does not identify a particular disk, antivirus, package, or scheduler as the underlying cause. The temporary stack-dump code was removed after this observation; the sanitized bootstrap markers remain.

One controlled Codex CLI run used `-B -m server.bootstrap` with a 60-second startup override. Its child recorded `tool_registry_constructed` **18,625 ms** after `python_entry`, and its host log recorded a real `ListToolsRequest`. No handshake timeout was logged during that held-open run. This supports the combined launch correction in that bounded run, but does not prove indefinite host lifetime or the VS Code extension's current tool attachment. A later short CLI turn finished before the child completed imports and could not call `forge_status`; it is not a persistence acceptance result.

The existing project MCP entry now has only two changes relative to the pre-correction backup: `args = ["-B", "-m", "server.bootstrap"]` and `startup_timeout_sec = 60`. `tool_timeout_sec`, cwd, interpreter, session directory, and security settings are unchanged. Backup: `.codex/config.toml.pre-import-fix-20261023T002714.bak`. The updated TOML parsed, and Ruff and compileall passed for the touched Python entry files. The previous stdio regression suite passed 2/2 after the bootstrap was first added; the final `-B` Codex CLI run supplied the relevant startup/tool-discovery check.

**Current disposition:** a specific Codex startup/import bottleneck was observed and the bounded `-B`/60-second correction was applied, but **persistent connection from the owning VS Code Codex session remains unverified**. No authenticated Unreal request, idle indicator observation, Editor action, asset change, native rebuild, token change, or Landscape operation occurred in this follow-up. Do not treat another VS Code reload by itself as a remedy. The next acceptance must show this chat's ForgeMCP namespace, a client-owned host surviving normal idle, and an authenticated read-only request to a freshly verified Unreal session.
