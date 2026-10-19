from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from server.core.collision import CollisionQueryRequest


def test_collision_request_accepts_line_sphere_and_capsule_queries() -> None:
    request = CollisionQueryRequest.model_validate({
        "max_query_distance_cm": 2500,
        "queries": [
            {"shape": "line", "start_cm": [100, 200, 1000], "end_cm": [100, 200, -1000],
             "channel_name": "Visibility"},
            {"shape": "sphere", "start_cm": [100, 200, 1000], "end_cm": [100, 200, -1000],
             "channel_name": "Camera", "radius_cm": 50},
            {"shape": "capsule", "start_cm": [100, 200, 1000], "end_cm": [100, 200, -1000],
             "channel_name": "Visibility", "radius_cm": 30, "half_height_cm": 80,
             "ignored_actor_paths": ["/Game/Test.Test:PersistentLevel.Actor_0"]},
        ],
    })

    assert len(request.queries) == 3
    assert request.queries[2].trace_complex is True


@pytest.mark.parametrize("payload", [
    {"shape": "line", "start_cm": [0, 0, 0], "end_cm": [0, 0, 1],
     "channel_name": "Visibility", "radius_cm": 10},
    {"shape": "sphere", "start_cm": [0, 0, 0], "end_cm": [0, 0, 1],
     "channel_name": "Visibility"},
    {"shape": "capsule", "start_cm": [0, 0, 0], "end_cm": [0, 0, 1],
     "channel_name": "Visibility", "radius_cm": 30, "half_height_cm": 20},
    {"shape": "line", "start_cm": [0, 0, 0], "end_cm": [0, 0, 2000],
     "channel_name": "Visibility"},
    {"shape": "line", "start_cm": [0, 0, float("nan")], "end_cm": [0, 0, 1],
     "channel_name": "Visibility"},
    {"shape": "line", "start_cm": [0, 0, 0], "end_cm": [0, 0, 1],
     "channel_name": "Visibility", "unexpected": True},
])
def test_collision_request_rejects_invalid_shape_fields_and_distances(payload: dict) -> None:
    with pytest.raises(ValidationError):
        CollisionQueryRequest.model_validate({"queries": [payload], "max_query_distance_cm": 1000})


def test_collision_request_bounds_batch_and_ignored_actor_count() -> None:
    query = {"shape": "line", "start_cm": [0, 0, 0], "end_cm": [0, 0, 1],
             "channel_name": "Visibility"}
    with pytest.raises(ValidationError):
        CollisionQueryRequest.model_validate({"queries": [query] * 33})

    query["ignored_actor_paths"] = [f"/Game/Test.Test:PersistentLevel.Actor_{i}" for i in range(17)]
    with pytest.raises(ValidationError):
        CollisionQueryRequest.model_validate({"queries": [query]})


@pytest.mark.asyncio
async def test_mcp_tool_dispatches_collision_query_to_explicit_session(monkeypatch) -> None:
    from server import main

    dispatch = AsyncMock(return_value={"ok": True, "session_id": "unreal-16436", "data": {}})
    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    request = CollisionQueryRequest.model_validate({
        "queries": [{
            "shape": "line",
            "start_cm": [0, 0, 100],
            "end_cm": [0, 0, 0],
            "channel_name": "Visibility",
        }],
    })

    result = await main.unreal_query_collision(request, "unreal-16436")

    dispatch.assert_awaited_once_with(
        "unreal",
        "collision_query",
        "unreal-16436",
        {"request": request.model_dump(exclude_none=True)},
    )
    assert result["session_id"] == "unreal-16436"
