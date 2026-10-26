import pytest
from pydantic import ValidationError

from server.core.blueprint_patches import BlueprintGraphPatchRequest

ASSET = "/Game/ForgeMCPTests/BlueprintPatches/BP_Scoped"
NODE = "01234567-89ab-cdef-0123-456789abcdef"
PIN = "fedcba98-7654-3210-fedc-ba9876543210"


def request(operations):
    return BlueprintGraphPatchRequest(asset_path=ASSET, graph_name="EventGraph", operations=operations)


def test_patch_schema_is_strict_and_rejects_unbounded_or_unknown_mutation():
    move = {"op": "move_node", "node_guid": NODE, "x": 8, "y": -9}
    assert request([move]).operations[0].x == 8
    invalid = [
        [], [move] * 33,
        [{**move, "x": True}], [{**move, "x": 100001}],
        [{**move, "x": "8"}], [{**move, "node_guid": "index-12"}],
        [{**move, "script": "arbitrary code"}],
        [{"op": "delete_asset", "node_guid": NODE}],
        [{"op": "set_pin_default", "node_guid": NODE, "pin_id": PIN, "value": "x" * 4097}],
    ]
    for operations in invalid:
        with pytest.raises(ValidationError):
            request(operations)
    with pytest.raises(ValidationError):
        BlueprintGraphPatchRequest(asset_path=ASSET + ".BP_Scoped", graph_name="EventGraph", operations=[move])


def test_link_patch_uses_exact_endpoint_ids_and_an_explicit_operation_sequence():
    disconnect = {
        "op": "disconnect_pins", "from_node_guid": NODE, "from_pin_id": PIN,
        "to_node_guid": PIN, "to_pin_id": NODE,
    }
    connect = {**disconnect, "op": "connect_pins"}
    patch = request([disconnect, connect])
    assert [operation.op for operation in patch.operations] == ["disconnect_pins", "connect_pins"]
    with pytest.raises(ValidationError):
        request([{**connect, "to_pin_id": "friendly pin title"}])


@pytest.mark.asyncio
async def test_patch_tools_send_the_typed_request_and_exact_review_confirmation(monkeypatch):
    from server import main

    calls = []

    async def dispatch(kind, command, session_id, args):
        calls.append((kind, command, session_id, args))
        return {"test_dispatch": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    patch = request([{"op": "move_node", "node_guid": NODE, "x": 1, "y": 2}])
    await main.unreal_preview_blueprint_graph_patch(patch, "unreal-test")
    await main.unreal_apply_blueprint_graph_patch("a" * 32, "a" * 32, "unreal-test")
    assert calls[0] == ("unreal", "blueprint_patch_preview", "unreal-test", {"request": patch.model_dump()})
    assert calls[1] == (
        "unreal", "blueprint_patch_apply", "unreal-test",
        {"preview_id": "a" * 32, "confirmation": "a" * 32},
    )
