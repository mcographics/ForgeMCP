import json
from types import SimpleNamespace

import pytest

from server import ui_transfer


class Client:
    def __init__(self, targets=None, preview_error=None):
        self.calls = []
        self.targets = targets or []
        self.preview_error = preview_error

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if name == "forge_list_sessions":
            value = {"ok": True, "data": {"sessions": self.targets}}
        elif name in {"forge_preview_transfer", "forge_preview_send_to_blender"}:
            value = self.preview_error or {"ok": True, "data": {"preview_id": "a" * 32,
                "operation_id": "a" * 32, "changes": args["request"]}}
        else:
            value = {"ok": True, "data": {"state": "completed"}}
        return SimpleNamespace(isError=False, structuredContent=value)


def test_async_worker_exception_groups_classify_leaves_without_exposing_messages():
    assert ui_transfer.known_worker_error(ExceptionGroup("private", [
        ExceptionGroup("private", [OSError("private")]), ValueError("private")]))
    assert not ui_transfer.known_worker_error(ExceptionGroup("private", [
        ValueError("private"), RuntimeError("private")]))


def intent(target="unreal-123"):
    return {"source_session_id": "blender-456", "source_object": "Cube",
            "target_session_id": target, "target_asset_path": "/Game/Test/SM_Cube",
            "save_assets": True, "place": True, "location": [0.0, 0.0, 0.0]}


@pytest.mark.asyncio
async def test_apply_requires_matching_preview_confirmation(capsys):
    client = Client()
    async def confirm():
        assert [name for name, _ in client.calls] == ["forge_preview_transfer"]
        return {"confirmation": "a" * 32}
    await ui_transfer.transfer(client, intent(), confirm)
    assert [name for name, _ in client.calls] == ["forge_preview_transfer", "forge_apply_transfer"]
    assert client.calls[-1][1] == {"preview_id": "a" * 32, "confirmation": "a" * 32}
    assert [json.loads(line)["state"] for line in capsys.readouterr().out.splitlines()] == ["preview", "applying", "completed"]


@pytest.mark.asyncio
@pytest.mark.parametrize("confirmation", [{}, {"confirmation": "b" * 32}, {"confirmation": "a" * 32, "extra": True}])
async def test_cancel_or_wrong_confirmation_never_applies(confirmation):
    client = Client()
    async def confirm():
        return confirmation
    await ui_transfer.transfer(client, intent(), confirm)
    assert all(name != "forge_apply_transfer" for name, _ in client.calls)


@pytest.mark.asyncio
async def test_multiple_live_targets_require_explicit_selection(capsys):
    client = Client([{"kind": "unreal", "connected": True, "session_id": f"unreal-{pid}"} for pid in (12, 34)])
    async def confirm():
        raise AssertionError("No preview should be created")
    await ui_transfer.transfer(client, intent(""), confirm)
    assert [name for name, _ in client.calls] == ["forge_list_sessions"]
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "ambiguous_session"


@pytest.mark.asyncio
async def test_unique_live_target_ignores_closed_registrations():
    client = Client([{"kind": "unreal", "connected": True, "session_id": "unreal-12"},
                     {"kind": "unreal", "connected": False, "session_id": "unreal-34"}])
    async def confirm():
        return {}
    await ui_transfer.transfer(client, intent(""), confirm)
    assert client.calls[1][1]["request"]["target_session_id"] == "unreal-12"


@pytest.mark.asyncio
async def test_material_failure_cannot_apply(capsys):
    client = Client(preview_error={"ok": False, "error": {"code": "unsupported_material_surface"}})
    async def confirm():
        raise AssertionError("No preview should be created")
    await ui_transfer.transfer(client, intent(), confirm)
    assert len(client.calls) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "unsupported_material_surface"


@pytest.mark.asyncio
async def test_unknown_request_fields_rejected():
    client = Client()
    async def confirm():
        return {}
    with pytest.raises(ValueError, match="invalid_panel_request"):
        await ui_transfer.transfer(client, {**intent(), "execute_python": "anything"}, confirm)
    assert not client.calls


@pytest.mark.asyncio
async def test_send_to_blender_uses_reverse_preview_apply(capsys):
    client = Client([{"kind": "blender", "connected": True, "session_id": "blender-456"}])
    async def confirm():
        return {"confirmation": "a" * 32}
    await ui_transfer.transfer(client, {"mode": "send_to_blender", "source_session_id": "unreal-123",
        "source_asset_path": "/Game/Test/SM_Cube.SM_Cube", "target_session_id": "", "target_object": "Editable"}, confirm)
    assert [name for name, _ in client.calls] == ["forge_list_sessions", "forge_preview_send_to_blender", "forge_apply_send_to_blender"]
    assert client.calls[1][1]["request"]["target_session_id"] == "blender-456"
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["state"] == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value,code", [
    ("source_asset_path", "C:/private/secret.fbx", "invalid_source_asset_path"),
    ("target_object", "../Cube", "invalid_target_object_name"),
])
async def test_reverse_panel_invalid_input_is_reported_before_mcp_task_group_exit(capsys, field, value, code):
    client = Client()
    async def confirm():
        raise AssertionError("Invalid input must not reach confirmation")
    request = {"mode": "send_to_blender", "source_session_id": "unreal-123",
               "source_asset_path": "/Game/Test/SM_Cube.SM_Cube",
               "target_session_id": "blender-456", "target_object": "Editable", field: value}
    await ui_transfer.transfer(client, request, confirm)
    result = capsys.readouterr().out
    assert json.loads(result) == {"state": "failed", "error": {"code": code}}
    assert value not in result
    assert client.calls == []


@pytest.mark.asyncio
async def test_import_from_blender_resolves_source_not_unreal_destination():
    client = Client([{"kind": "blender", "connected": True, "session_id": "blender-456"}])
    async def confirm():
        return {}
    await ui_transfer.transfer(client, {**intent("unreal-123"), "mode": "import_from_blender", "source_session_id": ""}, confirm)
    request = client.calls[1][1]["request"]
    assert request["source_session_id"] == "blender-456"
    assert request["target_session_id"] == "unreal-123"
    assert all(name != "forge_apply_transfer" for name, _ in client.calls)


@pytest.mark.asyncio
async def test_import_worker_preserves_explicit_replacement_choice():
    client = Client()
    async def confirm():
        return {}
    await ui_transfer.transfer(client, {**intent("unreal-123"), "mode": "import_from_blender",
        "source_session_id": "blender-456", "replace_existing": True, "place": False}, confirm)
    request = client.calls[0][1]["request"]
    assert request["replace_existing"] is True
    assert request["place"] is False
