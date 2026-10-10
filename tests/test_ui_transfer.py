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
        elif name == "forge_preview_transfer":
            value = self.preview_error or {"ok": True, "data": {"preview_id": "a" * 32,
                "operation_id": "a" * 32, "changes": args["request"]}}
        else:
            value = {"ok": True, "data": {"state": "completed"}}
        return SimpleNamespace(isError=False, structuredContent=value)


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
