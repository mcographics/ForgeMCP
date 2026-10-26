import pytest
from pydantic import ValidationError

from server.core.blueprint_inspection import (
    BlueprintExecutionTraceRequest,
    BlueprintGraphListRequest,
    BlueprintGraphPageRequest,
    BlueprintNodeInspectRequest,
)
from server.core.connections import COMMANDS

ASSET = "/Game/ForgeMCPTests/BP_LargeGraph"
GUID = "01234567-89ab-cdef-0123-456789abcdef"


def test_graph_inspection_requests_are_exact_bounded_and_reject_extra_fields():
    assert BlueprintGraphListRequest(asset_path=ASSET).asset_path == ASSET
    page = BlueprintGraphPageRequest(asset_path=ASSET, graph_name="EventGraph", node_guid=GUID)
    assert page.model_dump(exclude_none=True)["page_size"] == 32
    for fields in (
        {"asset_path": "/Engine/BP_Test"},
        {"asset_path": ASSET + ".BP_LargeGraph"},
        {"asset_path": ASSET, "page_size": 0},
        {"asset_path": ASSET, "page_size": 65},
        {"asset_path": ASSET, "node_guid": "node index 12"},
        {"asset_path": ASSET, "cursor": "p" + "a" * 32 + ":64"},
        {"asset_path": ASSET, "title_contains": "x" * 257},
        {"asset_path": ASSET, "script": "anything"},
    ):
        with pytest.raises(ValidationError):
            BlueprintGraphPageRequest(graph_name="EventGraph", **fields)


def test_pin_and_execution_requests_bound_cursor_kind_and_traversal():
    base = {"asset_path": ASSET, "graph_name": "EventGraph"}
    node = BlueprintNodeInspectRequest(**base, node_guid=GUID, pin_page_size=128)
    assert node.pin_page_size == 128
    for fields in (
        {"pin_page_size": 129},
        {"pin_cursor": "g" + "a" * 32 + ":1"},
    ):
        with pytest.raises(ValidationError):
            BlueprintNodeInspectRequest(**base, node_guid=GUID, **fields)
    trace = BlueprintExecutionTraceRequest(**base, start_node_guid=GUID, direction="both")
    assert trace.direction == "both"
    for fields in ({"depth": 33}, {"depth": -1}, {"node_limit": 513}, {"direction": "all"}):
        with pytest.raises(ValidationError):
            BlueprintExecutionTraceRequest(**base, start_node_guid=GUID, **fields)


@pytest.mark.asyncio
async def test_inspection_tools_dispatch_typed_read_only_requests(monkeypatch):
    from server import main

    calls = []

    async def dispatch(kind, command, session_id, args):
        calls.append((kind, command, session_id, args))
        return {"test_dispatch": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    await main.unreal_blueprint_capabilities("unreal-test")
    await main.unreal_list_blueprint_graphs(BlueprintGraphListRequest(asset_path=ASSET), "unreal-test")
    await main.unreal_page_blueprint_graph(
        BlueprintGraphPageRequest(asset_path=ASSET, graph_name="EventGraph"), "unreal-test"
    )
    await main.unreal_inspect_blueprint_node(
        BlueprintNodeInspectRequest(asset_path=ASSET, graph_name="EventGraph", node_guid=GUID),
        "unreal-test",
    )
    await main.unreal_trace_blueprint_execution(
        BlueprintExecutionTraceRequest(asset_path=ASSET, graph_name="EventGraph", start_node_guid=GUID),
        "unreal-test",
    )
    assert [call[1] for call in calls] == [
        "blueprint_capabilities", "blueprint_graph_list", "blueprint_graph_page",
        "blueprint_node_inspect", "blueprint_graph_trace",
    ]
    assert all(call[0] == "unreal" and call[2] == "unreal-test" for call in calls)
    assert all(call[1] in COMMANDS["unreal"] for call in calls)
    assert "cursor" not in calls[2][3]
    assert "pin_cursor" not in calls[3][3]
