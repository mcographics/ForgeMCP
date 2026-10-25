"""Host-owned existing-world Landscape grant validation."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from server.core.landscape_authorization import (
    AUTHORIZATION_ENV,
    LandscapeAuthorizationError,
    existing_world_landscape_authorization,
)


def grant_json(**overrides):
    now = datetime.now(timezone.utc)
    value = {
        "authorization_id": "a" * 32,
        "session_id": "unreal-13432",
        "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
        "world_path": "/Game/Levels/L_City_World_Master",
        "actions": ["create_in_place", "generate", "apply_heightmap", "raise", "lower", "flatten", "smooth", "coastline", "frame", "save"],
        "expires_at_utc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
    }
    value.update(overrides)
    return json.dumps(value)


def test_grant_is_host_owned_exact_and_returns_native_claim():
    claim = existing_world_landscape_authorization(
        "unreal-13432",
        "create_in_place",
        "/Game/Levels/L_City_World_Master",
        env={AUTHORIZATION_ENV: grant_json()},
    )
    assert claim is not None
    assert claim["session_id"] == "unreal-13432"
    assert claim["world_path"] == "/Game/Levels/L_City_World_Master"
    assert "token" not in claim
    assert "actions" in claim


@pytest.mark.parametrize(
    ("session_id", "action", "world_path"),
    [
        ("unreal-9", "create_in_place", "/Game/Levels/L_City_World_Master"),
        ("unreal-13432", "save", "/Game/Levels/Other"),
        ("unreal-13432", "reload", "/Game/Levels/L_City_World_Master"),
    ],
)
def test_grant_rejects_wrong_session_world_or_action(session_id, action, world_path):
    assert existing_world_landscape_authorization(
        session_id, action, world_path,
        env={AUTHORIZATION_ENV: grant_json()},
    ) is None


def test_grant_is_default_deny_and_required_creation_fails_without_it():
    assert existing_world_landscape_authorization(
        "unreal-13432", "generate", env={}
    ) is None
    with pytest.raises(LandscapeAuthorizationError):
        existing_world_landscape_authorization(
            "unreal-13432", "create_in_place", "/Game/Levels/L_City_World_Master",
            required=True, env={},
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"world_path": "/Game/Levels/Other.Actor"},
        {"session_id": "unreal-13432-other"},
        {"actions": ["create_in_place", "eval"]},
        {"actions": ["generate"]},
        {"authorization_id": "not-an-id"},
        {"unexpected": True},
    ],
)
def test_malformed_or_overbroad_grant_fails_closed(overrides):
    with pytest.raises(LandscapeAuthorizationError):
        existing_world_landscape_authorization(
            "unreal-13432", "create_in_place", "/Game/Levels/L_City_World_Master",
            required=True, env={AUTHORIZATION_ENV: grant_json(**overrides)},
        )


def test_expired_or_long_lived_grant_fails_closed():
    now = datetime.now(timezone.utc)
    for expiry in (now - timedelta(seconds=1), now + timedelta(hours=25)):
        with pytest.raises(LandscapeAuthorizationError):
            existing_world_landscape_authorization(
                "unreal-13432", "create_in_place", "/Game/Levels/L_City_World_Master",
                required=True,
                env={AUTHORIZATION_ENV: grant_json(expires_at_utc=expiry.isoformat().replace("+00:00", "Z"))},
                now=now,
            )
