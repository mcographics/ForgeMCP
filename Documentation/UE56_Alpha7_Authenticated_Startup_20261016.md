# UE 5.6 alpha.7 — authenticated startup connection

Plugin package `0.2.13-alpha.7` changes the status from waiting for a first
request to an authenticated connection state once the MCP host heartbeat arrives.
Unreal starts the engine-wide loopback bridge on plugin module load regardless of
project presence or project-local AutoStart settings. The external MCP server
discovers registrations at startup and sends authenticated, read-only health probes
every two seconds while its MCP client session is alive. It stops the watcher when
that client disconnects. No persistent TCP socket is kept open.

The panel reports `Connected to ForgeMCP` while an authenticated health request is
recent, reports a missed heartbeat if the host stops responding, and distinguishes
that from an MCP host that has not authenticated yet. The engine bridge cannot
authenticate itself when its external MCP client/server is not running; it remains
available locally and is authenticated when the host starts.

## Validation

- Plugin version: `0.2.13-alpha.7`, descriptor version `22`.
- MCP source version: `0.3.12`.
- Isolated UE 5.6.1 Win64 Development Editor target: 28 actions passed.
- Package SHA-256: `8a4b8e8ceaaab79a04e02b80c98510192753e2318bc4b61370cb2577fdab19cd`.
- Python suite: 351 passed; Ruff and Python bytecode compilation passed.
- New stdio integration test confirmed that server initialization authenticates a
  registered Unreal bridge before any user tool call.
- Packaged plugin loaded and authenticated in a disposable UE project, and real
  MCP stdio discovery and project-identity checks passed.
- Engine-wide install and visible UI/engine-only startup validation remain pending;
  the user's ForgeMCPDev editor was open during this build and was left untouched.

## Evidence

- Host: `Saved/EngineWideAlpha7FixValidation/HostProject`.
- Package: `Artifacts/ForgeMCP-Unreal-Alpha-0.2.13-alpha.7-UE5.6.1-Win64.zip`.
- Isolated packaged-load evidence: `Saved/UnrealPackageAcceptance-8655d0aea97d47f5bf554288321d1a47`.

After installation, close/restart the current editor and restart the Codex MCP host
so it loads server version `0.3.12`. Then verify an engine-only launch registers
without selecting a project and changes the panel to `Connected to ForgeMCP` once
the MCP host is active. The live editor and MCP client must both be running for
authenticated connection status.
