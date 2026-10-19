import base64

import pytest
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import TextContent

from server import main


@pytest.mark.asyncio
async def test_unreal_screenshot_returns_an_mcp_image_without_file_or_window_claim(monkeypatch):
    async def dispatch(kind, command, session_id, args=None):
        assert (kind, command, session_id, args) == ("unreal", "capture_screenshot", "session-1", None)
        return {"ok": True, "data": {
            "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg").decode(),
            "width": 640, "height": 360, "capture_frame_number": 120,
            "rendered_frames_since_request": 1,
        }}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    content = await main.unreal_capture_screenshot("session-1")
    assert isinstance(content[0], TextContent)
    assert "window was not resized" in content[0].text
    assert "editor frame 120" in content[0].text
    assert "after 1 rendered frame" in content[0].text
    assert isinstance(content[1], Image)
    assert content[1].to_image_content().mimeType == "image/jpeg"
    assert base64.b64decode(content[1].to_image_content().data) == b"jpeg"


@pytest.mark.asyncio
async def test_unreal_screenshot_rejects_oversized_or_invalid_native_payload(monkeypatch):
    async def dispatch(*args, **kwargs):
        return {"ok": True, "data": {
            "mime_type": "image/jpeg", "image_base64": "!invalid!", "width": 640, "height": 360,
        }}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    result = await main.unreal_capture_screenshot("session-1")
    assert result["error"]["code"] == "invalid_screenshot_response"


@pytest.mark.asyncio
async def test_unreal_screenshot_propagates_bridge_errors(monkeypatch):
    async def dispatch(*args, **kwargs):
        return {"ok": False, "error": {"code": "viewport_unavailable", "message": "No viewport."}}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    result = await main.unreal_capture_screenshot("session-1")
    assert result["error"]["code"] == "viewport_unavailable"
