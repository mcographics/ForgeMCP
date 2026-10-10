import copy
import hashlib

import pytest

from server.core.connections import BridgeError, Session
from server.core.recovery import AssetRecovery
from server.core.transfer import FBX_BINARY_HEADER, TransferArtifactError
from server.core.workflow_journal import JournalError, WorkflowJournal
from server.core.workflows import TransferCoordinator, TransferRequest, WorkflowError, converted


class NativeFixture:
    """Protocol fixture for control-flow tests, not proof of native application behavior."""

    def __init__(self, tmp_path):
        self.roots = [tmp_path / "blender"]
        self.roots[0].mkdir()
        (self.roots[0] / "blender-123.json").write_text("{}")
        self.sessions = [Session("blender-123", "blender", 1, "a" * 64, 123),
                         Session("unreal-456", "unreal", 2, "b" * 64, 456)]
        self.project = tmp_path / "Host.uproject"
        self.project.write_text("{}")
        self.calls = []
        self.failure = None
        self.bad_geometry = False
        self.source_changed = False
        self.target_level = "/Temp/TestWorld"
        self.bytes = FBX_BINARY_HEADER + b"protocol fixture only"
        self.vertices = [[x, y, z] for x in (-2, 2) for y in (-3, 3) for z in (-1, 1)]
        self.metadata = {
            "source_object": "Cube", "source_session_id": "blender-123",
            "source_snapshot_sha256": "c" * 64, "source_bounds_min": [-2, -3, -1],
            "source_bounds_max": [2, 3, 1], "source_world_bounds_min": [-2, -3, -1],
            "source_world_bounds_max": [2, 3, 1], "source_world_vertices": self.vertices,
            "world_vertices_truncated": False, "vertex_count": 8, "triangle_count": 12,
            "meters_per_source_unit": 1.0, "materials": [],
        }
        self.transfer_id = "d" * 32
        self.asset_path = "/Game/ForgeTransfer/SM_Cube.SM_Cube"

    def discover(self):
        return self.sessions

    async def request(self, session, command, args=None):
        self.calls.append(command)
        if self.failure == command:
            raise BridgeError("outcome_unknown", "injected native timeout")
        if command == "health":
            return {"transfer_contract_version": 1}
        if command == "project_info":
            return {"project_file": str(self.project), "level": self.target_level, "play_in_editor": False}
        if command == "asset_info":
            raise BridgeError("asset_not_found", "not present")
        if command == "export_preview":
            return {"preview_id": self.transfer_id, **copy.deepcopy(self.metadata)}
        if command == "export_apply":
            root = self.roots[0] / "transfers" / session.session_id / self.transfer_id
            root.mkdir(parents=True)
            (root / "mesh.fbx").write_bytes(self.bytes)
            data = copy.deepcopy(self.metadata)
            if self.source_changed:
                data["source_snapshot_sha256"] = "e" * 64
            return {"status": "exported", "transfer_id": self.transfer_id, **data,
                    "artifact_sha256": hashlib.sha256(self.bytes).hexdigest(), "artifact_bytes": len(self.bytes)}
        if command in {"mesh_import_preview", "actor_preview"}:
            return {"preview_id": "f" * 32}
        if command == "mesh_info" and getattr(self, "mesh_missing", False):
            raise BridgeError("mesh_not_loaded", "not loaded")
        if command in {"mesh_import_apply", "mesh_info"}:
            return {"state": "imported", "asset_path": self.asset_path,
                    "class_path": "/Script/Engine.StaticMesh", "vertex_count": 8, "triangle_count": 12,
                    "bounds_min_cm": [-300, -200, -100], "bounds_max_cm": [300, 200, 100],
                    "vertices_truncated": False, "vertex_positions_cm": [converted(p, 1) for p in self.vertices],
                    "saved": True, "materials": [],
                    **({"vertex_count": 7} if self.bad_geometry else {})}
        if command == "actor_apply":
            self.actor = {"path": "/Temp/TestWorld.Actor", "static_mesh": self.asset_path,
                          "location": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1],
                          "material_assets": []}
            return {"state": "completed", "actors": [self.actor], "saved": False}
        if command == "actor_info":
            return {"actor": self.actor}
        raise AssertionError(command)


def fixture(tmp_path, **request_options):
    native = NativeFixture(tmp_path)
    journal = WorkflowJournal(tmp_path / "receipts")
    coordinator = TransferCoordinator(native, journal)
    request = TransferRequest(source_session_id="blender-123", target_session_id="unreal-456",
                              source_object="Cube", target_asset_path="/Game/ForgeTransfer/SM_Cube",
                              **request_options)
    return native, journal, coordinator, request


async def test_reviewed_workflow_orders_stages_and_retains_results(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    assert not journal.root.exists()
    assert "export_apply" not in native.calls
    operation_id = preview["operation_id"]
    result = await coordinator.apply(operation_id, operation_id)
    assert result["state"] == "completed"
    record = journal.read(operation_id)
    assert record["completed_stages"] == ["export", "staging", "import", "verification", "placement"]
    assert record["events"][7]["evidence"]["complete_vertex_positions_verified"] is True
    assert record["events"][-1]["evidence"]["level_saved"] is False
    assert (native.project.parent / "Saved" / "ForgeTransfers" / native.transfer_id / "manifest.json").is_file()
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await coordinator.apply(operation_id, operation_id)


async def test_wrong_confirmation_does_not_consume_preview(tmp_path):
    native, _, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    with pytest.raises(WorkflowError, match="confirmation_required"):
        await coordinator.apply(preview["operation_id"], "wrong")
    assert "export_apply" not in native.calls
    assert preview["operation_id"] in coordinator.previews


async def test_changed_target_aborts_before_export_and_storage(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    native.target_level = "/Temp/OtherWorld"
    with pytest.raises(WorkflowError, match="stale_preview"):
        await coordinator.apply(preview["operation_id"], preview["operation_id"])
    assert not journal.root.exists()
    assert "export_apply" not in native.calls


@pytest.mark.parametrize("command,stage", [("export_apply", "export"), ("mesh_import_apply", "import"),
                                           ("actor_apply", "placement")])
async def test_native_timeouts_preserve_uncertain_stage_without_replay(tmp_path, command, stage):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    native.failure = command
    operation_id = preview["operation_id"]
    result = await coordinator.apply(operation_id, operation_id)
    assert result["state"] == "outcome_unknown"
    record = journal.read(operation_id)
    assert record["active_stage"] == stage
    assert record["state"] == "outcome_unknown"
    assert record["events"][-1]["evidence"]["diagnostic_code"] == "outcome_unknown"
    assert native.calls.count(command) == 1


async def test_geometry_mismatch_keeps_import_receipt_and_blocks_placement(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    native.bad_geometry = True
    operation_id = preview["operation_id"]
    result = await coordinator.apply(operation_id, operation_id)
    assert result["state"] == "partial"
    assert result["diagnostic_code"] == "import_verification_failed"
    assert "actor_apply" not in native.calls
    assert journal.read(operation_id)["active_stage"] == "verification"


async def test_changed_export_metadata_cannot_reach_import(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    native.source_changed = True
    operation_id = preview["operation_id"]
    result = await coordinator.apply(operation_id, operation_id)
    assert result["state"] == "failed"
    assert "mesh_import_apply" not in native.calls
    assert journal.read(operation_id)["events"][-1]["evidence"]["diagnostic_code"] == "source_changed"


async def test_asset_only_mode_completes_without_placing_actor(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path, place=False)
    preview = await coordinator.preview(request)
    operation_id = preview["operation_id"]
    result = await coordinator.apply(operation_id, operation_id)
    assert result["state"] == "completed"
    assert "actor_apply" not in native.calls
    assert journal.read(operation_id)["completed_stages"][-1] == "verification"


async def test_reconcile_checks_loaded_mesh_without_changing_receipt_or_replaying(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    plan = await coordinator.preview(request)
    operation = plan["operation_id"]
    await coordinator.apply(operation, operation)
    before = journal.read(operation)
    native.calls.clear()
    result = await coordinator.reconcile(operation, "unreal-456")
    assert result["geometry_and_materials_verified"] is True
    assert result["recovery_completed"] is False
    assert native.calls == ["health", "project_info", "mesh_info"]
    assert journal.read(operation) == before


async def test_reconcile_rejects_wrong_project_before_asset_inspection(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    plan = await coordinator.preview(request)
    operation = plan["operation_id"]
    await coordinator.apply(operation, operation)
    before = journal.read(operation)
    native.project = tmp_path / "Other.uproject"
    native.calls.clear()
    with pytest.raises(WorkflowError, match="wrong_target_project"):
        await coordinator.reconcile(operation, "unreal-456")
    assert native.calls == ["health", "project_info"]
    assert journal.read(operation) == before


async def test_reconcile_missing_loaded_mesh_does_not_claim_absence_or_retry(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    plan = await coordinator.preview(request)
    operation = plan["operation_id"]
    await coordinator.apply(operation, operation)
    before = journal.read(operation)
    native.mesh_missing = True
    native.calls.clear()
    result = await coordinator.reconcile(operation, "unreal-456")
    assert result["mesh_loaded"] is False and result["registry_asset"] is None
    assert result["saved_contents_verified"] is False
    assert native.calls == ["health", "project_info", "mesh_info", "asset_info"]
    assert journal.read(operation) == before


@pytest.mark.parametrize("stage,last_command,blocked_command", [
    ("export", "export_apply", "mesh_import_preview"),
    ("staging", "export_apply", "mesh_import_preview"),
    ("import", "mesh_import_apply", "actor_preview"),
    ("placement", "actor_apply", None),
])
@pytest.mark.parametrize("error", [PermissionError(13, "private filesystem detail"), JournalError("record_busy")])
async def test_completion_receipt_failure_stops_without_replay(
    tmp_path, monkeypatch, stage, last_command, blocked_command, error
):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    operation = preview["operation_id"]
    original_transition = journal.transition

    def fail_completion(operation_id, revision, requested_stage, outcome, evidence=None):
        if requested_stage == stage and outcome == "completed":
            raise error
        return original_transition(operation_id, revision, requested_stage, outcome, evidence)

    monkeypatch.setattr(journal, "transition", fail_completion)
    result = await coordinator.apply(operation, operation)
    assert result["state"] == "outcome_unknown"
    assert result["diagnostic_code"] == "receipt_unavailable"
    assert result["storage_error_code"] == ("record_busy" if isinstance(error, JournalError) else "os_error_13")
    assert "private filesystem detail" not in str(result)
    assert result["automatic_native_replay_allowed"] is False
    assert native.calls.count(last_command) == 1
    if blocked_command:
        assert blocked_command not in native.calls
    retained = journal.read(operation)
    assert retained["active_stage"] == stage and retained["state"] == "running"
    assert retained["events"][-1]["outcome"] == "started"
    assert journal.inspect(operation)["effective_state"] == "outcome_unknown"
    assert operation not in coordinator.active
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await coordinator.apply(operation, operation)
    assert native.calls.count(last_command) == 1


@pytest.mark.parametrize("stage,blocked_command", [("export", "export_apply"),
    ("import", "mesh_import_preview"), ("placement", "actor_preview")])
async def test_started_receipt_failure_prevents_native_side_effect(tmp_path, monkeypatch, stage, blocked_command):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    operation = preview["operation_id"]
    original_transition = journal.transition

    def fail_start(operation_id, revision, requested_stage, outcome, evidence=None):
        if requested_stage == stage and outcome == "started":
            raise PermissionError(13, "private filesystem detail")
        return original_transition(operation_id, revision, requested_stage, outcome, evidence)

    monkeypatch.setattr(journal, "transition", fail_start)
    result = await coordinator.apply(operation, operation)
    assert result["state"] == "outcome_unknown"
    assert blocked_command not in native.calls
    assert journal.read(operation)["active_stage"] is None
    assert operation not in coordinator.active


async def recovery_fixture(tmp_path):
    native, journal, coordinator, request = fixture(tmp_path)
    preview = await coordinator.preview(request)
    operation = preview["operation_id"]
    native.failure = "actor_apply"
    result = await coordinator.apply(operation, operation)
    assert result["state"] == "outcome_unknown"
    native.failure = None
    return native, journal, coordinator, operation, AssetRecovery(coordinator)


async def test_recovery_restores_new_assets_without_blender_or_original_replay(tmp_path):
    native, journal, coordinator, original, recovery = await recovery_fixture(tmp_path)
    before = journal.read(original)
    native.sessions = [session for session in native.sessions if session.kind == "unreal"]
    native.calls.clear()
    plan = await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")
    assert "export_apply" not in native.calls
    native.asset_path = "/Game/Recovered/SM_Cube.SM_Cube"
    result = await recovery.apply(plan["preview_id"], plan["preview_id"])
    assert result["state"] == "completed"
    assert journal.read(original) == before
    assert journal.read(plan["preview_id"])["completed_stages"] == ["staging", "import", "verification"]
    assert "export_apply" not in native.calls and "actor_apply" not in native.calls
    assert (await coordinator.reconcile(plan["preview_id"], "unreal-456"))["geometry_and_materials_verified"]
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await recovery.apply(plan["preview_id"], plan["preview_id"])


async def test_recovery_requires_a_different_destination(tmp_path):
    _, _, _, original, recovery = await recovery_fixture(tmp_path)
    with pytest.raises(WorkflowError, match="new_destination_required"):
        await recovery.preview(original, "unreal-456", "/Game/ForgeTransfer/SM_Cube")


async def test_recovery_stale_context_stops_before_staging(tmp_path):
    native, journal, _, original, recovery = await recovery_fixture(tmp_path)
    plan = await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")
    native.target_level = "/Temp/ChangedWorld"
    with pytest.raises(WorkflowError, match="stale_preview"):
        await recovery.apply(plan["preview_id"], plan["preview_id"])
    assert not (journal.root / plan["preview_id"]).exists()


async def test_recovery_confirmation_must_match_before_consuming_preview(tmp_path):
    _, _, _, original, recovery = await recovery_fixture(tmp_path)
    plan = await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")
    with pytest.raises(WorkflowError, match="confirmation_required"):
        await recovery.apply(plan["preview_id"], "wrong")
    assert plan["preview_id"] in recovery.previews


async def test_recovery_changed_backup_stops_before_new_receipt_or_import(tmp_path):
    native, journal, _, original, recovery = await recovery_fixture(tmp_path)
    plan = await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")
    backup = native.project.parent / "Saved" / "ForgeTransfers" / native.transfer_id / "mesh.fbx"
    backup.write_bytes(backup.read_bytes() + b"changed")
    native.calls.clear()
    with pytest.raises(TransferArtifactError):
        await recovery.apply(plan["preview_id"], plan["preview_id"])
    assert not (journal.root / plan["preview_id"]).exists()
    assert "mesh_import_preview" not in native.calls


async def test_recovery_wrong_project_rejected_before_staging(tmp_path):
    native, _, _, original, recovery = await recovery_fixture(tmp_path)
    native.project = tmp_path / "Other.uproject"
    with pytest.raises(WorkflowError, match="wrong_target_project"):
        await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")


async def test_recovery_active_original_cannot_be_restored(tmp_path):
    _, _, coordinator, original, recovery = await recovery_fixture(tmp_path)
    coordinator.active.add(original)
    with pytest.raises(WorkflowError, match="operation_active"):
        await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_Cube")


async def interrupted_recovery_fixture(tmp_path):
    native, journal, coordinator, original, recovery = await recovery_fixture(tmp_path)
    first = await recovery.preview(original, "unreal-456", "/Game/Recovered/SM_First")
    native.failure = "mesh_import_apply"
    result = await recovery.apply(first["preview_id"], first["preview_id"])
    assert result["state"] == "outcome_unknown"
    native.failure = None
    return native, journal, coordinator, original, first["preview_id"]


async def test_interrupted_recovery_can_restore_again_after_server_restart(tmp_path):
    native, journal, _, original, interrupted = await interrupted_recovery_fixture(tmp_path)
    before = {operation: journal.read(operation) for operation in (original, interrupted)}
    native.sessions = [session for session in native.sessions if session.kind == "unreal"]
    native.calls.clear()
    restarted = TransferCoordinator(native, WorkflowJournal(journal.root))
    recovery = AssetRecovery(restarted)
    preview = await recovery.preview(interrupted, "unreal-456", "/Game/Recovered/SM_Second")
    native.asset_path = "/Game/Recovered/SM_Second.SM_Second"
    result = await recovery.apply(preview["preview_id"], preview["preview_id"])
    assert result["state"] == "completed"
    assert result["original_operation_id"] == interrupted
    assert journal.read(preview["preview_id"])["completed_stages"] == ["staging", "import", "verification"]
    assert all(journal.read(operation) == record for operation, record in before.items())
    assert "export_apply" not in native.calls and "actor_apply" not in native.calls
    assert (await restarted.reconcile(preview["preview_id"], "unreal-456"))["geometry_and_materials_verified"]


async def test_interrupted_recovery_rejects_changed_own_retained_artifact(tmp_path):
    native, journal, coordinator, _, interrupted = await interrupted_recovery_fixture(tmp_path)
    backup = native.project.parent / "Saved" / "ForgeTransfers" / interrupted / "mesh.fbx"
    backup.write_bytes(backup.read_bytes() + b"changed")
    native.calls.clear()
    with pytest.raises(TransferArtifactError):
        await AssetRecovery(coordinator).preview(interrupted, "unreal-456", "/Game/Recovered/SM_Second")
    assert "mesh_import_preview" not in native.calls
    assert journal.read(interrupted)["state"] == "outcome_unknown"
