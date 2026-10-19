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
    task = asyncio.create_task(_authenticate_registered_sessions(ConnectionManager.configured()))
    try:
        yield {}
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
