"""Authenticate registered application bridges while the MCP host is active."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from server.core.connections import BridgeError, ConnectionManager

log = logging.getLogger("majestic_forge.autoconnect")
HEALTH_INTERVAL_SECONDS = 2.0


async def _authenticate_registered_sessions(connections: ConnectionManager) -> None:
    """Send a bounded authenticated health probe to every registered local bridge."""
    while True:
        if connections.isolated_config is not None:
            if connections.isolated_identity_busy:
                await asyncio.sleep(HEALTH_INTERVAL_SECONDS)
                continue
            # The ID comes from the isolated host's explicit allowlist. No registry
            # discovery fallback is used by this background probe.
            result = await connections.dispatch(
                "unreal", "health", connections.isolated_config.allowed_session_id
            )
            if not result.get("ok"):
                log.debug("Isolated bridge health check failed: %s", result.get("error", {}).get("code", "bridge_error"))
            await asyncio.sleep(HEALTH_INTERVAL_SECONDS)
            continue
        sessions = connections.discover()

        async def probe(session) -> None:
            try:
                health = await connections.request(session, "health")
                expected = "ForgeMCP Unreal" if session.kind == "unreal" else "ForgeMCP Blender"
                if health.get("adapter") != expected:
                    log.warning("Bridge identity check failed for %s", session.session_id)
            except BridgeError as error:
                log.debug("Bridge health check failed for %s: %s", session.session_id, error.code)

        if sessions:
            await asyncio.gather(*(probe(session) for session in sessions))
        await asyncio.sleep(HEALTH_INTERVAL_SECONDS)


@asynccontextmanager
async def connection_monitor_lifespan(_server) -> AsyncIterator[dict]:
    """Keep engine-started bridges freshly authenticated for the MCP host lifetime."""
    if _server is None:
        connections = ConnectionManager.configured()
    else:
        # The tool handlers and lifespan must supervise the same worker.
        from server.main import connections
    worker = getattr(connections.process_identity_probe, "worker", None)
    if connections.isolated_config is not None and worker is not None:
        try:
            await asyncio.to_thread(worker.start)
        except Exception as exc:
            raise RuntimeError("Dedicated isolated listener worker failed to start.") from exc
    try:
        async with _isolated_monitor_body(connections):
            yield {}
    finally:
        if worker is not None:
            await asyncio.to_thread(worker.close)


@asynccontextmanager
async def _isolated_monitor_body(connections: ConnectionManager) -> AsyncIterator[dict]:
    if connections.isolated_config is not None:
        session_id = connections.isolated_config.allowed_session_id
        result = await connections.dispatch("unreal", "health", session_id)
        health = result.get("data", {}) if result.get("ok") else {}
        if not result.get("ok") or health.get("adapter") != "ForgeMCP Unreal":
            # Fail before serving tools if the private registration is absent,
            # unauthorized, stale, or authenticated as a different adapter.
            code = result.get("error", {}).get("code", "invalid_identity")
            raise RuntimeError(
                f"Dedicated isolated ForgeMCP authentication failed ({code})."
            )
        project_result = await connections.dispatch("unreal", "project_info", session_id)
        project_info = project_result.get("data", {}) if project_result.get("ok") else {}
        try:
            if not project_result.get("ok"):
                raise ValueError("Editor identity request failed")
            connections.isolated_config.validate_project_info(project_info)
        except ValueError:
            raise RuntimeError("Dedicated isolated ForgeMCP project identity preflight failed.") from None
    task = asyncio.create_task(_authenticate_registered_sessions(connections))
    try:
        yield {}
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
