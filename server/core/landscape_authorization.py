"""Default-deny, host-owned authorization for existing-world Landscape edits."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

AUTHORIZATION_ENV = "FORGE_LANDSCAPE_EXISTING_WORLD_AUTHORIZATION"
MAX_GRANT_LIFETIME_SECONDS = 24 * 60 * 60
LANDSCAPE_OPERATIONS = frozenset(
    {
        "create_in_place",
        "generate",
        "apply_heightmap",
        "raise",
        "lower",
        "flatten",
        "smooth",
        "coastline",
        "frame",
        "save",
    }
)
_SESSION_ID = re.compile(r"unreal-[1-9][0-9]{0,9}\Z")
_AUTHORIZATION_ID = re.compile(r"[0-9a-f]{32}\Z")
_WORLD_PACKAGE = re.compile(r"/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\Z")


class LandscapeAuthorizationError(ValueError):
    """An explicit existing-world grant is absent, invalid, or out of scope."""


@dataclass(frozen=True)
class ExistingWorldLandscapeGrant:
    authorization_id: str
    session_id: str
    project_file: str
    world_path: str
    actions: frozenset[str]
    expires_at_unix: int

    def native_payload(self) -> dict[str, object]:
        """Return the private server-generated claim injected into native args."""
        return {
            "authorization_id": self.authorization_id,
            "session_id": self.session_id,
            "project_file": self.project_file,
            "world_path": self.world_path,
            "actions": sorted(self.actions),
            "expires_at_unix": self.expires_at_unix,
        }


def _parse_grant(raw: str, now: datetime) -> ExistingWorldLandscapeGrant:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, RecursionError):
        raise LandscapeAuthorizationError("Existing-world Landscape authorization is invalid.") from None
    required = {"authorization_id", "session_id", "project_file", "world_path", "actions", "expires_at_utc"}
    if not isinstance(value, dict) or set(value) != required:
        raise LandscapeAuthorizationError("Existing-world Landscape authorization has an invalid schema.")

    authorization_id = value["authorization_id"]
    session_id = value["session_id"]
    project_file = value["project_file"]
    world_path = value["world_path"]
    actions = value["actions"]
    expires_at_utc = value["expires_at_utc"]
    if not isinstance(authorization_id, str) or not _AUTHORIZATION_ID.fullmatch(authorization_id):
        raise LandscapeAuthorizationError("Existing-world Landscape authorization ID is invalid.")
    if not isinstance(session_id, str) or not _SESSION_ID.fullmatch(session_id):
        raise LandscapeAuthorizationError("Existing-world Landscape session scope is invalid.")
    if not isinstance(project_file, str) or len(project_file) > 1024 or not Path(project_file).is_absolute():
        raise LandscapeAuthorizationError("Existing-world Landscape project path must be absolute.")
    if not isinstance(world_path, str) or not _WORLD_PACKAGE.fullmatch(world_path):
        raise LandscapeAuthorizationError("Existing-world Landscape world must be one exact /Game package path.")
    if (
        not isinstance(actions, list)
        or not actions
        or len(actions) > len(LANDSCAPE_OPERATIONS)
        or any(not isinstance(action, str) or action not in LANDSCAPE_OPERATIONS for action in actions)
        or len(set(actions)) != len(actions)
        or "create_in_place" not in actions
    ):
        raise LandscapeAuthorizationError("Existing-world Landscape operation scope is invalid.")
    if not isinstance(expires_at_utc, str) or len(expires_at_utc) > 40:
        raise LandscapeAuthorizationError("Existing-world Landscape authorization expiry is invalid.")
    try:
        expiry = datetime.fromisoformat(expires_at_utc.replace("Z", "+00:00"))
    except ValueError:
        raise LandscapeAuthorizationError("Existing-world Landscape authorization expiry is invalid.") from None
    if expiry.tzinfo is None or expiry.utcoffset() != timezone.utc.utcoffset(expiry):
        raise LandscapeAuthorizationError("Existing-world Landscape authorization expiry must be UTC.")
    remaining = (expiry - now).total_seconds()
    if remaining <= 0 or remaining > MAX_GRANT_LIFETIME_SECONDS:
        raise LandscapeAuthorizationError("Existing-world Landscape authorization is expired or exceeds 24 hours.")

    return ExistingWorldLandscapeGrant(
        authorization_id=authorization_id,
        session_id=session_id,
        project_file=str(Path(project_file).resolve(strict=False)),
        world_path=world_path,
        actions=frozenset(actions),
        expires_at_unix=int(expiry.timestamp()),
    )


def existing_world_landscape_authorization(
    session_id: str,
    action: str | None = None,
    world_path: str | None = None,
    *,
    required: bool = False,
    env: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, object] | None:
    """Resolve a private host-startup grant; caller data can never create one.

    The MCP schema has no authorization field. This function reads only the
    host process environment, binds the requested session/action/world to the
    grant, and returns the internal claim that the tool wrapper injects.
    """
    source = os.environ if env is None else env
    raw = source.get(AUTHORIZATION_ENV)
    if not raw:
        if required:
            raise LandscapeAuthorizationError("An explicit existing-world Landscape grant is required.")
        return None
    grant = _parse_grant(raw, now or datetime.now(timezone.utc))
    matches = grant.session_id == session_id
    matches = matches and (action is None or action in grant.actions)
    matches = matches and (world_path is None or world_path == grant.world_path)
    if not matches:
        if required:
            raise LandscapeAuthorizationError("The existing-world Landscape grant does not match this session, action, and world.")
        return None
    return grant.native_payload()
