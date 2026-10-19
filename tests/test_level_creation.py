from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from server.core.connections import BridgeError
from server.core.level_creation import EmptyOpenWorldCreations, EmptyOpenWorldRequest
from server.core.workflow_journal import WorkflowJournal
from server.core.workflows import WorkflowError

MAP_PATH = "/Game/ForgeMCPTests/EmptyOpenWorld/Phase6C_EmptyOpenWorld"
PREVIEW_ID = "d" * 32


class NativeCreationFixture:
    """Protocol fixture only; it does not validate Unreal runtime behavior."""

    def __init__(self, root):
        self.journal = WorkflowJournal(root / "Saved" / "ForgeWorkflows")
        self.active = set()
        self.connections = self
        self.context = {
            "project_file": str(root / "Host.uproject"),
            "level": "/Game/ForgeMCPTests/Source/Source.Source",
            "play_in_editor": False,
        }
        self.token = "private-session-token"
        self.calls = []
        self.failure = None
        self.partition_enabled = True

    def session(self, kind, session_id):
        assert kind == "unreal"
        return SimpleNamespace(session_id=session_id, token=self.token)

    def binding(self, target):
        return target.token

    async def target_context(self, target):
        return dict(self.context)

    async def request(self, target, command, args):
        self.calls.append(command)
        if self.failure:
            raise BridgeError(self.failure, "private native detail")
        if command == "level_create_preview":
            return {
                "preview_id": PREVIEW_ID,
                "map_path": args["map_path"],
                "source_world": self.context["level"],
                "template": "Empty Open World",
                "world_partition_requested": True,
                "overwrites_existing": False,
            }
        assert command == "level_create_apply"
        assert args["preview_id"] == PREVIEW_ID
        assert self.journal.read(PREVIEW_ID)["active_stage"] == "level_create"
        path = self.context["project_file"]
        map_file = Path(path).parent / "Content" / "ForgeMCPTests" / "EmptyOpenWorld" / "Phase6C_EmptyOpenWorld.umap"
        map_file.parent.mkdir(parents=True, exist_ok=True)
        map_file.write_bytes(b"fixture only, not an Unreal map")
        world = f"{MAP_PATH}.{MAP_PATH.rsplit('/', 1)[1]}"
        self.context["level"] = world
        return {
            "operation_id": PREVIEW_ID,
            "state": "saved",
            "saved": True,
            "map_path": MAP_PATH,
            "world": world,
            "world_partition_enabled": self.partition_enabled,
            "partition_initialized": True,
            "partition_subsystem_available": True,
            "landscape_actor_count": 0,
        }


@pytest.fixture
def creation_request():
    return EmptyOpenWorldRequest(map_path=MAP_PATH)


@pytest.fixture
def coordinator(tmp_path):
    native = NativeCreationFixture(tmp_path)
    return native, EmptyOpenWorldCreations(native)


@pytest.mark.asyncio
async def test_empty_open_world_apply_verifies_saved_map_and_current_world(coordinator, creation_request):
    native, creations = coordinator
    preview = await creations.preview(creation_request, "unreal-123")
    result = await creations.apply(preview["preview_id"], preview["preview_id"], "unreal-123")

    assert result["state"] == "saved"
    assert result["world_partition_enabled"] is True
    assert result["partition_initialized"] is True
    assert result["saved_map_file"]["exists"] is True
    assert result["receipt"]["completed_stages"] == ["level_create"]
    assert native.calls == ["level_create_preview", "level_create_apply"]
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await creations.apply(preview["preview_id"], preview["preview_id"], "unreal-123")


@pytest.mark.asyncio
async def test_stale_editor_context_blocks_apply_without_native_transition(coordinator, creation_request):
    native, creations = coordinator
    preview = await creations.preview(creation_request, "unreal-123")
    native.context["level"] = "/Game/ForgeMCPTests/Changed/Changed.Changed"

    with pytest.raises(WorkflowError, match="stale_preview"):
        await creations.apply(preview["preview_id"], preview["preview_id"], "unreal-123")
    assert native.calls == ["level_create_preview"]


@pytest.mark.asyncio
async def test_wrong_confirmation_never_calls_native_apply(coordinator, creation_request):
    native, creations = coordinator
    preview = await creations.preview(creation_request, "unreal-123")

    with pytest.raises(WorkflowError, match="confirmation_required"):
        await creations.apply(preview["preview_id"], "wrong", "unreal-123")
    assert native.calls == ["level_create_preview"]


@pytest.mark.asyncio
async def test_timeout_is_uncertain_and_native_creation_is_not_replayed(coordinator, creation_request):
    native, creations = coordinator
    preview = await creations.preview(creation_request, "unreal-123")
    native.failure = "timeout"

    result = await creations.apply(preview["preview_id"], preview["preview_id"], "unreal-123")
    assert result["state"] == "outcome_unknown"
    assert result["automatic_native_replay_allowed"] is False
    assert native.calls.count("level_create_apply") == 1


@pytest.mark.asyncio
async def test_false_partition_result_is_not_accepted(coordinator, creation_request):
    native, creations = coordinator
    native.partition_enabled = False
    preview = await creations.preview(creation_request, "unreal-123")

    result = await creations.apply(preview["preview_id"], preview["preview_id"], "unreal-123")
    assert result["state"] == "outcome_unknown"
    assert result["diagnostic_code"] == "invalid_response"
    assert "saved_map_file" not in result


def test_request_rejects_non_test_or_nested_destinations():
    with pytest.raises(ValidationError):
        EmptyOpenWorldRequest(map_path="/Game/Levels/Production")
    with pytest.raises(ValidationError):
        EmptyOpenWorldRequest(map_path="/Game/ForgeMCPTests/EmptyOpenWorld/Nested/Map")
