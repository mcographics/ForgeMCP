"""MCP wrappers inject only host-owned Landscape authorization claims."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from server import main
from server.core.landscape import LandscapeRequest
from server.core.landscape_authorization import AUTHORIZATION_ENV


def _grant():
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    return json.dumps({
        "authorization_id": "b" * 32,
        "session_id": "unreal-13432",
        "project_file": "G:/ForgeMCP/ForgeMCPDev.uproject",
        "world_path": "/Game/Levels/L_City_World_Master",
        "actions": ["create_in_place", "raise", "generate", "apply_heightmap", "lower", "flatten", "smooth", "coastline", "frame", "save"],
        "expires_at_utc": expiry,
    })


@pytest.mark.asyncio
async def test_preview_injects_exact_host_grant_not_caller_data(monkeypatch):
    monkeypatch.setenv(AUTHORIZATION_ENV, _grant())
    captured = {}

    async def dispatch(kind, command, session_id, args):
        captured.update(kind=kind, command=command, session_id=session_id, args=args)
        return {"ok": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    request = LandscapeRequest(
        action="create_in_place", map_path="/Game/Levels/L_City_World_Master", world_partition=True,
    )
    await main.unreal_preview_landscape(request, "unreal-13432")
    assert captured["session_id"] == "unreal-13432"
    claim = captured["args"]["_forge_landscape_authorization"]
    assert claim["session_id"] == "unreal-13432"
    assert claim["world_path"] == request.map_path
    assert "token" not in claim
    assert "authorization" not in request.model_dump()


@pytest.mark.asyncio
async def test_preview_rejects_wrong_session_before_dispatch(monkeypatch):
    monkeypatch.setenv(AUTHORIZATION_ENV, _grant())

    async def dispatch(*args, **kwargs):
        pytest.fail("unauthorized existing-world request must stop before native dispatch")

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    request = LandscapeRequest(
        action="create_in_place", map_path="/Game/Levels/L_City_World_Master", world_partition=True,
    )
    with pytest.raises(ValueError, match="does not match"):
        await main.unreal_preview_landscape(request, "unreal-9")


def test_caller_cannot_supply_authorization_fields_in_typed_request():
    with pytest.raises(ValidationError):
        LandscapeRequest.model_validate({
            "action": "create_in_place",
            "map_path": "/Game/Levels/L_City_World_Master",
            "world_partition": True,
            "authorization_id": "a" * 32,
        })
