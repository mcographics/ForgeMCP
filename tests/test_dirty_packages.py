from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from server.core.connections import ConnectionManager, Session
from server.core.dirty_packages import DirtyPackageInspectionRequest


def test_dirty_package_request_defaults_to_first_bounded_page() -> None:
    request = DirtyPackageInspectionRequest.model_validate({})

    assert request.offset == 0
    assert request.limit == 50
    assert request.snapshot_id is None
    assert request.target_map_path is None


def test_dirty_package_target_map_context_is_optional_and_bounded() -> None:
    request = DirtyPackageInspectionRequest.model_validate({
        "target_map_path": "/Game/ForgeMCPTests/Landscape/L_A7K37_Scope",
    })

    assert request.offset == 0
    assert request.snapshot_id is None
    assert request.target_map_path.endswith("L_A7K37_Scope")

    with pytest.raises(ValidationError, match="target_map_path"):
        DirtyPackageInspectionRequest.model_validate({"target_map_path": "/Game/City/L_City"})


@pytest.mark.parametrize(
    "payload",
    [
        {"offset": -1},
        {"offset": 50_001},
        {"limit": 0},
        {"limit": 51},
        {"limit": True},
        {"snapshot_id": "invalid"},
        {"unexpected": True},
    ],
)
def test_dirty_package_request_rejects_out_of_bounds_or_untyped_values(payload: dict) -> None:
    with pytest.raises(ValidationError):
        DirtyPackageInspectionRequest.model_validate(payload)


def test_dirty_package_followup_page_requires_snapshot_id() -> None:
    with pytest.raises(ValidationError, match="snapshot_id is required"):
        DirtyPackageInspectionRequest.model_validate({"offset": 1})


@pytest.mark.asyncio
async def test_mcp_tool_routes_dirty_package_request_to_explicit_session(monkeypatch) -> None:
    from server import main

    dispatch = AsyncMock(return_value={
        "ok": True,
        "session_id": "unreal-16436",
        "data": {"inventory_id": "a" * 32, "packages": []},
    })
    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    request = DirtyPackageInspectionRequest(offset=10, limit=25, snapshot_id="a" * 32)

    result = await main.unreal_inspect_dirty_packages(request, "unreal-16436")

    dispatch.assert_awaited_once_with(
        "unreal",
        "inspect_dirty_packages",
        "unreal-16436",
        {"offset": 10, "limit": 25, "snapshot_id": "a" * 32},
    )
    assert result["session_id"] == "unreal-16436"
    assert result["data"]["snapshot_id"] == "a" * 32
    assert result["data"]["inventory_id"] == "a" * 32


@pytest.mark.asyncio
async def test_mcp_tool_routes_proposed_target_map_in_snapshot_context(monkeypatch) -> None:
    from server import main

    dispatch = AsyncMock(return_value={
        "ok": True,
        "session_id": "unreal-16436",
        "data": {"inventory_id": "e" * 32, "packages": []},
    })
    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    request = DirtyPackageInspectionRequest(
        limit=25,
        target_map_path="/Game/ForgeMCPTests/Landscape/L_A7K37_Target",
    )

    await main.unreal_inspect_dirty_packages(request, "unreal-16436")

    dispatch.assert_awaited_once_with(
        "unreal",
        "inspect_dirty_packages",
        "unreal-16436",
        {"offset": 0, "limit": 25,
         "target_map_path": "/Game/ForgeMCPTests/Landscape/L_A7K37_Target"},
    )


@pytest.mark.asyncio
async def test_dirty_package_multipage_requests_keep_snapshot_and_unresolved_rows(monkeypatch) -> None:
    from server import main

    snapshot_id = "b" * 32
    unresolved_row = {
        "package_name": "/Script/SlateCore",
        "dirty": True,
        "classification_complete": False,
        "classification": "other",
    }
    dispatch = AsyncMock(side_effect=[
        {
            "ok": True,
            "session_id": "unreal-16436",
            "data": {
                "inventory_id": snapshot_id,
                "offset": 0,
                "next_offset": 1,
                "has_more_observed_results": True,
                "packages": [unresolved_row],
            },
        },
        {
            "ok": True,
            "session_id": "unreal-16436",
            "data": {
                "inventory_id": snapshot_id,
                "offset": 1,
                "next_offset": None,
                "has_more_observed_results": False,
                "packages": [],
            },
        },
    ])
    monkeypatch.setattr(main.connections, "dispatch", dispatch)

    first = await main.unreal_inspect_dirty_packages(
        DirtyPackageInspectionRequest(limit=1), "unreal-16436"
    )
    second = await main.unreal_inspect_dirty_packages(
        DirtyPackageInspectionRequest(limit=1, offset=1, snapshot_id=snapshot_id),
        "unreal-16436",
    )

    assert first["data"]["snapshot_id"] == snapshot_id
    assert first["data"]["packages"] == [unresolved_row]
    assert first["data"]["packages"][0]["classification_complete"] is False
    assert second["data"]["snapshot_id"] == snapshot_id
    assert second["data"]["inventory_id"] == snapshot_id
    calls = dispatch.await_args_list
    assert calls[0].args == (
        "unreal", "inspect_dirty_packages", "unreal-16436", {"offset": 0, "limit": 1}
    )
    assert calls[1].args == (
        "unreal", "inspect_dirty_packages", "unreal-16436",
        {"offset": 1, "limit": 1, "snapshot_id": snapshot_id},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["unknown", "expired"])
async def test_unknown_or_expired_snapshot_errors_are_not_hidden(monkeypatch, case: str) -> None:
    from server import main

    snapshot_id = "c" * 32 if case == "unknown" else "d" * 32
    dispatch = AsyncMock(return_value={
        "ok": False,
        "error": {"code": "snapshot_expired", "message": f"{case} snapshot"},
    })
    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    result = await main.unreal_inspect_dirty_packages(
        DirtyPackageInspectionRequest(offset=1, snapshot_id=snapshot_id), "unreal-16436"
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "snapshot_expired"
    assert result["error"]["message"] == f"{case} snapshot"


@pytest.mark.asyncio
async def test_dirty_package_command_is_allowlisted_and_keeps_session_explicit(monkeypatch) -> None:
    manager = ConnectionManager([])
    session = Session("unreal-16436", "unreal", 64763, "t" * 40, 16436)
    request = AsyncMock(return_value={"packages_inspected": 1})
    monkeypatch.setattr(manager, "discover", lambda: [session])
    monkeypatch.setattr(manager, "request", request)

    result = await manager.dispatch(
        "unreal", "inspect_dirty_packages", "unreal-16436", {"offset": 0, "limit": 50}
    )

    request.assert_awaited_once_with(
        session, "inspect_dirty_packages", {"offset": 0, "limit": 50}
    )
    assert result["session_id"] == "unreal-16436"
