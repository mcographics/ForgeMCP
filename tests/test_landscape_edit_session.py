"""Editing-session schemas, control-plane boundaries and MCP discovery (no live Editor)."""
import pytest
from pydantic import ValidationError

from server import main
from server.core.landscape import LandscapeRequest
from server.core.landscape_edit_session import (
    LandscapeEditSessionReference,
    LandscapeEditSessionRequest,
    LandscapeHeightRegionRequest,
)


def request(**changes):
    values = dict(actor_path="/Game/World.World:PersistentLevel.Landscape",
                  project_file="G:/Test/Game.uproject", world_path="/Game/World",
                  editor_pid=123, world_partition=True, landscape_guid="a" * 32,
                  layer_guid="b" * 32, region=[0, 0, 63, 63], actions=["raise", "apply_heightmap"])
    return LandscapeEditSessionRequest(**(values | changes))


def test_two_hour_default_and_explicit_whole_landscape():
    assert request().lifetime_seconds == 7200
    assert request(region_scope="entire_landscape", region=[0, 0, 2040, 2040])
    with pytest.raises(ValidationError):
        request(region=[0, 0, 2040, 2040])


@pytest.mark.parametrize("change", [
    {"actions": ["setup_layer"]}, {"actions": ["save"]}, {"actions": ["reload"]},
    {"actions": ["raise", "raise"]}, {"actions": []}, {"approved": True},
    {"layer_name": "Layer"}, {"layer_guid": "invalid"}, {"lifetime_seconds": 59},
    {"lifetime_seconds": 86401}, {"lifetime_seconds": True}, {"lifetime_seconds": "7200"},
    {"region": [3, 0, 2, 1]}, {"region_scope": "automatic"}, {"editor_pid": 0},
    {"world_partition": "true"}, {"backup_root": "spoof"},
])
def test_no_remote_approval_or_silent_scope_expansion(change):
    with pytest.raises(ValidationError):
        request(**change)


def test_editing_reference_is_distinct_and_sculpt_only():
    assert LandscapeRequest(action="raise", actor_path="Landscape", edit_session_id="A" * 32)
    for changes in [dict(adoption_id="b" * 32), dict(action="setup_layer"), dict(action="save")]:
        values = dict(action="raise", actor_path="Landscape", edit_session_id="a" * 32)
        with pytest.raises(ValidationError):
            LandscapeRequest(**(values | changes))
    with pytest.raises(ValidationError):
        LandscapeEditSessionReference(edit_session_id="a" * 32, region=[0, 0, 10, 10])


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "command", "control"), [
    ("unreal_landscape_edit_session_preflight", "landscape_edit_session_preflight", False),
    ("unreal_request_landscape_edit_session", "landscape_edit_session_request", False),
    ("unreal_landscape_edit_session_status", "landscape_edit_session_status", True),
    ("unreal_revoke_landscape_edit_session", "landscape_edit_session_revoke", True),
])
async def test_exact_dispatch_and_session_binding(monkeypatch, name, command, control):
    calls = []

    async def dispatch(*args):
        calls.append(args)
        return {"ok": True, "data": {"state": "pending_local_approval"}}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    typed = LandscapeEditSessionReference(edit_session_id="a" * 32) if control else request()
    await getattr(main, name)(typed, "unreal-123")
    expected = typed.model_dump() if control else {"request": typed.model_dump()}
    assert calls == [("unreal", command, "unreal-123", expected)]


@pytest.mark.asyncio
async def test_discovery_has_permission_reduction_but_no_remote_approval():
    tools = {t.name: t for t in await main.mcp.list_tools()}
    assert tools["unreal_landscape_edit_session_preflight"].annotations.readOnlyHint
    assert tools["unreal_landscape_edit_session_status"].annotations.readOnlyHint
    assert not tools["unreal_revoke_landscape_edit_session"].annotations.readOnlyHint
    assert not any("approve_landscape_edit" in name for name in tools)


def test_height_region_read_is_bounded_and_cannot_write():
    assert LandscapeHeightRegionRequest(actor_path="Actor", layer_guid="a" * 32,
                                       region=[0, 0, 127, 255])
    for region in ([0, 0, 128, 255], [1, 0, 0, 1]):
        with pytest.raises(ValidationError):
            LandscapeHeightRegionRequest(actor_path="Actor", layer_guid="a" * 32, region=region)
    with pytest.raises(ValidationError):
        LandscapeHeightRegionRequest(actor_path="Actor", layer_guid="a" * 32,
                                     region=[0, 0, 1, 1], samples_cm=[100])


@pytest.mark.asyncio
async def test_height_read_dispatch(monkeypatch):
    captured = []

    async def dispatch(*args):
        captured.append(args)
        return {"ok": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    typed = LandscapeHeightRegionRequest(actor_path="Actor", layer_guid="a" * 32,
                                         region=[0, 0, 1, 1])
    await main.unreal_read_landscape_height_region(typed, "unreal-123")
    assert captured == [("unreal", "landscape_read_region", "unreal-123",
                         {"request": typed.model_dump()})]
