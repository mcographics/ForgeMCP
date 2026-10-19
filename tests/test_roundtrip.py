import hashlib
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from server.core.connections import BridgeError
from server.core.roundtrip import (
    CompareMeshBindingRequest,
    RoundtripCoordinator,
    SendToBlenderRequest,
    stage_fbx,
)
from server.core.transfer import FBX_BINARY_HEADER
from server.core.workflow_journal import WorkflowJournal
from server.core.workflows import TransferCoordinator, WorkflowError


def request(**overrides):
    return SendToBlenderRequest.model_validate({"source_session_id": "unreal-12", "target_session_id": "blender-34",
        "source_asset_path": "/Game/Test/SM_Mesh.SM_Mesh", "target_object": "EditableMesh", **overrides})


class Connections:
    def __init__(self, root):
        self.root = root
        self.roots = [root / "sessions"]
        self.roots[0].mkdir()
        (self.roots[0] / "blender-34.json").write_text("{}")
        self.sessions = [SimpleNamespace(kind="unreal", session_id="unreal-12", token="source"),
                         SimpleNamespace(kind="blender", session_id="blender-34", token="target")]
        self.calls = []
        self.changed = False
        self.disconnect_import = False
        self.binding_id = None
        self.binding_state = {
            "binding_id": "f" * 32,
            "unreal_binding_id": "f" * 32,
            "blender_revision": "a" * 64,
            "blender_baseline": "a" * 64,
            "unreal_revision": "b" * 64,
            "source_revision": "a" * 64,
            "target_revision": "b" * 64,
        }
        self.id = "a"*32
        self.data = FBX_BINARY_HEADER + b"test native artifact"

    def discover(self):
        return self.sessions

    async def request(self, session, command, args=None):
        self.calls.append((session.kind, command, args))
        if command == "health":
            return {"transfer_contract_version": 1, "capabilities": ["mesh_export_preview", "import_preview", "binding_info", "mesh_binding_info"]}
        if command == "project_info":
            return {"project_file": str(self.root / "Host.uproject"), "level": "NewLevel" if self.changed else "Level", "play_in_editor": False}
        if command == "scene_info":
            return {"mode": "OBJECT", "objects": [], "file": "", "scene_name": "Scene"}
        if command == "binding_info":
            state = self.binding_state
            return {"name": (args or {}).get("name"), "binding_id": state["binding_id"],
                "source_revision_sha256": state["blender_revision"],
                "baseline_revision_sha256": state["blender_baseline"]}
        if command == "mesh_binding_info":
            state = self.binding_state
            return {"asset_path": (args or {}).get("asset_path"), "binding_id": state["unreal_binding_id"],
                "source_snapshot_sha256": state["unreal_revision"],
                "source_revision_sha256": state["source_revision"],
                "target_revision_sha256": state["target_revision"]}
        if command == "mesh_export_preview":
            return {"preview_id": self.id, "source_snapshot_sha256": "b"*64,
                "triangle_count": 12, "vertex_count": 8}
        if command == "mesh_export_apply":
            format_ = (args or {}).get("format", "fbx")
            path = self.root / "Saved/ForgeExports" / self.id / f"mesh.{format_}"
            path.parent.mkdir(parents=True)
            path.write_bytes(self.data)
            return {"status": "exported", "transfer_id": self.id, "source_snapshot_sha256": "b"*64,
                "artifact_bytes": len(self.data), "artifact_sha256": hashlib.sha256(self.data).hexdigest(),
                "triangle_count": 12, "format": format_, "artifact_name": f"mesh.{format_}"}
        if command == "import_preview":
            self.binding_id = (args or {}).get("binding_id")
            return {"preview_id": "c"*32}
        if command == "import_apply":
            if self.disconnect_import:
                raise BridgeError("disconnected", "connection lost")
            return {"state": "imported", "triangle_count": 12, "binding_id": self.binding_id}
        if command == "object_info":
            return {"name": "EditableMesh", "type": "MESH"}
        raise AssertionError(command)


@pytest.mark.asyncio
async def test_roundtrip_preview_no_writes_and_single_apply(tmp_path):
    c = Connections(tmp_path)
    t = TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts"))
    r = RoundtripCoordinator(t)
    plan = await r.preview(request())
    assert not (tmp_path / "Saved").exists()
    assert not (tmp_path / "receipts").exists()
    id_ = plan["preview_id"]
    with pytest.raises(WorkflowError, match="confirmation_required"):
        await r.apply(id_, "wrong")
    result = await r.apply(id_, id_)
    assert result["state"] == "completed"
    assert t.journal.read(id_)["state"] == "completed"
    assert (c.roots[0] / "transfers/blender-34/incoming" / c.id / "mesh.fbx").read_bytes() == c.data
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await r.apply(id_, id_)
    assert sum(command == "import_apply" for _, command, _ in c.calls) == 1


def test_shared_session_registration_root_is_counted_once(tmp_path):
    c = Connections(tmp_path)
    c.roots.append(c.roots[0])
    r = RoundtripCoordinator(TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts")))
    assert r.registration_root(c.sessions[1]) == c.roots[0].resolve()


def test_distinct_duplicate_session_registration_roots_remain_ambiguous(tmp_path):
    c = Connections(tmp_path)
    duplicate = tmp_path / "another-sessions"
    duplicate.mkdir()
    (duplicate / "blender-34.json").write_text("{}")
    c.roots.append(duplicate)
    r = RoundtripCoordinator(TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts")))
    with pytest.raises(WorkflowError, match="session_registration_unavailable"):
        r.registration_root(c.sessions[1])


async def test_blank_blender_name_override_preserves_unreal_source_name(tmp_path):
    c = Connections(tmp_path)
    t = TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts"))
    r = RoundtripCoordinator(t)
    plan = await r.preview(request(source_asset_path="/Game/Test/Tree_Original.Tree_Original",
                                   target_object=""))
    assert plan["changes"]["target_object"] == "Tree_Original"
    assert "mesh_export_apply" not in [command for _, command, _ in c.calls]


@pytest.mark.asyncio
@pytest.mark.parametrize(("blender_changed", "unreal_changed", "expected"), [
    (False, False, "synchronized"), (True, False, "blender_changed"),
    (False, True, "unreal_changed"), (True, True, "both_changed_conflict"),
])
async def test_binding_comparison_reports_revision_state_without_mutation(
    tmp_path, blender_changed, unreal_changed, expected
):
    c = Connections(tmp_path)
    t = TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts"))
    comparator = RoundtripCoordinator(t)
    state = c.binding_state
    if blender_changed:
        state["blender_revision"] = "c" * 64
    if unreal_changed:
        state["unreal_revision"] = "d" * 64
    request = CompareMeshBindingRequest.model_validate({
        "source_session_id": "blender-34", "target_session_id": "unreal-12",
        "source_object": "EditableMesh", "target_asset_path": "/Game/Test/SM_Mesh.SM_Mesh",
    })
    result = await comparator.compare_binding(request)
    assert result["state"] == expected
    assert result["mutated"] is False and result["saved"] is False
    assert [name for _, name, _ in c.calls] == ["health", "health", "binding_info", "mesh_binding_info"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("mutation", "expected"), [
    ("unbound", "unbound"), ("mismatch", "binding_mismatch"),
    ("no_baseline", "baseline_unavailable"),
])
async def test_binding_comparison_reports_missing_or_mismatched_identity(tmp_path, mutation, expected):
    c = Connections(tmp_path)
    t = TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts"))
    comparator = RoundtripCoordinator(t)
    if mutation == "unbound":
        c.binding_state["binding_id"] = None
    elif mutation == "mismatch":
        c.binding_state["unreal_binding_id"] = "e" * 32
    else:
        c.binding_state["blender_baseline"] = None
        c.binding_state["source_revision"] = None
    request = CompareMeshBindingRequest.model_validate({
        "source_session_id": "blender-34", "target_session_id": "unreal-12",
        "source_object": "EditableMesh", "target_asset_path": "/Game/Test/SM_Mesh.SM_Mesh",
    })
    result = await comparator.compare_binding(request)
    assert result["state"] == expected
    assert result["mutated"] is False and result["saved"] is False


@pytest.mark.asyncio
async def test_changed_project_rejects_before_export(tmp_path):
    c = Connections(tmp_path)
    r = RoundtripCoordinator(TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts")))
    plan = await r.preview(request())
    c.changed = True
    with pytest.raises(WorkflowError, match="stale_preview"):
        await r.apply(plan["preview_id"], plan["preview_id"])
    assert all(command != "mesh_export_apply" for _, command, _ in c.calls)


@pytest.mark.asyncio
async def test_import_disconnect_retains_unknown_receipt_no_replay(tmp_path):
    c = Connections(tmp_path)
    c.disconnect_import = True
    t = TransferCoordinator(c, WorkflowJournal(tmp_path / "receipts"))
    r = RoundtripCoordinator(t)
    p = await r.preview(request())
    result = await r.apply(p["preview_id"], p["preview_id"])
    assert result["state"] == "outcome_unknown"
    assert t.journal.read(p["preview_id"])["state"] == "outcome_unknown"
    assert result["automatic_native_replay_allowed"] is False


@pytest.mark.parametrize("field,value", [("target_object", "../Cube"), ("source_asset_path", "C:/mesh.fbx"), ("source_session_id", "blender-12"), ("target_session_id", "unreal-34")])
def test_direction_and_destinations_are_typed(field, value):
    with pytest.raises(ValidationError):
        request(**{field: value})


def test_engine_asset_is_export_source_only():
    assert request(source_asset_path="/Engine/BasicShapes/Sphere.Sphere").source_asset_path.startswith("/Engine/")
    with pytest.raises(ValidationError):
        CompareMeshBindingRequest(source_session_id="blender-34", target_session_id="unreal-12",
            source_object="Sphere", target_asset_path="/Engine/BasicShapes/Sphere.Sphere")


def test_staging_checksum_and_no_overwrite(tmp_path):
    source = tmp_path / "source.fbx"
    data = FBX_BINARY_HEADER+b"data"
    source.write_bytes(data)
    destination = tmp_path / "incoming/new/mesh.fbx"
    with pytest.raises(WorkflowError, match="artifact_changed"):
        stage_fbx(source, destination, len(data), "0"*64)
    assert not destination.parent.exists()
    digest = hashlib.sha256(data).hexdigest()
    stage_fbx(source, destination, len(data), digest)
    with pytest.raises(FileExistsError):
        stage_fbx(source, destination, len(data), digest)
    assert destination.read_bytes() == data
