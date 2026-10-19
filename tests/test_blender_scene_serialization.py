import pytest

from server import main
from server.core.recipes import SceneRecipe


@pytest.mark.asyncio
async def test_scene_preview_omits_unrequested_optional_operations(monkeypatch):
    sent = {}

    async def dispatch(kind, command, session_id, args):
        sent.update(kind=kind, command=command, session_id=session_id, args=args)
        return {"ok": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    operation = {"op": "assign_material", "name": "Sun", "material": "Photosphere"}
    await main.blender_preview_scene(SceneRecipe(operations=[operation]), "blender-test")
    assert sent["args"] == {"recipe": {"operations": [operation]}}
    assert sent["command"] == "scene_preview"
