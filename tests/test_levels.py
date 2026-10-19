import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.core.connections import BridgeError
from server.core.levels import CurrentLevelSaves, LevelSaves, inspect_project_package_file
from server.core.workflow_journal import WorkflowJournal
from server.core.workflows import WorkflowError


class NativeSaveFixture:
    """Protocol fault fixture; does not establish native Unreal saving."""

    def __init__(self, root):
        self.journal = WorkflowJournal(root / "Saved" / "ForgeWorkflows")
        self.active = set()
        self.connections = self
        self.context = {"project_file": str(root / "Host.uproject"), "level": "/Temp/Untitled.World"}
        self.calls = []
        self.failure = None
        self.token = "private-session-token"
        self.preview_id = "a" * 32

    def session(self, kind, session_id):
        return SimpleNamespace(session_id=session_id, token=self.token)

    def binding(self, target):
        return target.token

    async def target_context(self, target):
        return dict(self.context)

    async def request(self, target, command, args):
        self.calls.append(command)
        if self.failure:
            raise BridgeError(self.failure, "private native detail")
        if command == "current_level_save_preview":
            self.context["level"] = "/Game/Maps/Map.Map"
            self.current_level_package = "/Game/Maps/Map"
            self.current_packages = [
                ("/Game/Maps/Map", Path(self.context["project_file"]).parent / "Content" / "Maps" / "Map.umap", True),
                ("/Game/Maps/Map/ExternalActors/Actor_1", Path(self.context["project_file"]).parent / "Content" / "Maps" / "Map" / "ExternalActors" / "Actor_1.uasset", True),
            ]
            for package, path, _ in self.current_packages:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((package + "-before").encode())
            return {"preview_id": self.preview_id, "world": self.context["level"],
                    "level_package": self.current_level_package, "package_count": len(self.current_packages),
                    "packages": [{"package": package, "will_save": True, "file_existed_before": True,
                                  "before_sha1": hashlib.sha1(path.read_bytes()).hexdigest(),
                                  "before_bytes": path.stat().st_size}
                                 for package, path, _ in self.current_packages]}
        if command == "current_level_save_apply":
            assert self.journal.read(self.preview_id.lower())["active_stage"] == "level_save"
            saved = []
            for package, path, _ in self.current_packages:
                path.write_bytes((package + "-after-save").encode())
                content = path.read_bytes()
                saved.append({"package": package, "saved": True,
                              "sha1": hashlib.sha1(content).hexdigest().upper(),
                              "bytes": len(content)})
            return {"operation_id": self.preview_id, "state": "saved", "saved": True,
                    "level_package": self.current_level_package, "saved_packages": saved}
        if command == "level_save_preview":
            return {"preview_id": self.preview_id, "asset_path": args["asset_path"],
                    "source_world": self.context["level"], "dependencies": []}
        assert self.journal.read(self.preview_id.lower())["active_stage"] == "level_save"
        path = Path(self.context["project_file"]).parent / "Content" / "NewFolder" / "Map.umap"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"protocol-fixture-map-not-native-Unreal")
        self.context["level"] = "/Game/NewFolder/Map.Map"
        return {"operation_id": self.preview_id, "state": "saved", "saved": True,
                "asset_path": "/Game/NewFolder/Map"}


async def fixture(root):
    native = NativeSaveFixture(root)
    saves = LevelSaves(native)
    preview = await saves.preview("/Game/NewFolder/Map", "unreal-123")
    return native, saves, preview["preview_id"]


async def test_save_has_durable_intent_and_restart_readable_completion(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "saved"
    assert result["receipt"]["completed_stages"] == ["level_save"]
    fresh = WorkflowJournal(native.journal.root).inspect(operation)
    assert fresh["record"] == result["receipt"]
    assert fresh["runtime_state_verified"] is False
    assert native.token not in str(fresh)
    with pytest.raises(WorkflowError, match="preview_not_found"):
        await saves.apply(operation, operation, "unreal-123")


async def test_native_uppercase_guid_is_preserved_but_receipt_id_is_lowercase(tmp_path):
    native = NativeSaveFixture(tmp_path)
    native.preview_id = "AB" * 16
    saves = LevelSaves(native)
    preview = await saves.preview("/Game/NewFolder/Map", "unreal-123")
    operation = preview["preview_id"]
    assert operation == native.preview_id.lower()
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "saved"
    assert result["operation_id"] == operation and result["native_operation_id"] == native.preview_id
    assert native.journal.read(operation)["state"] == "completed"


async def test_level_reconciliation_reports_checksum_and_identity_without_mutation(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    await saves.apply(operation, operation, "unreal-123")
    before = native.journal.read(operation)
    native.calls.clear()
    result = await LevelSaves(native).reconcile(operation, "unreal-456")
    assert result["matches_recorded_saved_checksum"] is True
    assert result["matching_world_loaded"] is True
    assert result["native_map_contents_verified"] is False and result["recovery_completed"] is False
    assert result["receipt_modified"] is False and native.journal.read(operation) == before
    assert native.calls == []
    path = tmp_path / "Content" / "NewFolder" / "Map.umap"
    path.write_bytes(path.read_bytes() + b"changed")
    changed = await saves.reconcile(operation, "unreal-456")
    assert changed["matches_recorded_saved_checksum"] is False
    assert native.journal.read(operation) == before


async def test_uncertain_save_reconciliation_does_not_infer_success_from_absence(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    native.failure = "timeout"
    await saves.apply(operation, operation, "unreal-123")
    result = await LevelSaves(native).reconcile(operation, "unreal-456")
    assert result["recorded_state"] == "outcome_unknown"
    assert result["map_file"] == {"exists": False}
    assert result["matches_recorded_saved_checksum"] is None
    assert result["recovery_completed"] is False


async def test_current_world_partition_save_verifies_map_and_external_actor_packages(tmp_path):
    native = NativeSaveFixture(tmp_path)
    native.context["level"] = "/Game/Maps/Map.Map"
    saves = CurrentLevelSaves(native)
    preview = await saves.preview("unreal-123")
    assert preview["scope"] == "active persistent level and its loaded external-object packages"
    operation = preview["preview_id"]
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "saved"
    assert {item["package"] for item in result["saved_package_files"]} == {
        "/Game/Maps/Map", "/Game/Maps/Map/ExternalActors/Actor_1"}
    assert result["receipt"]["completed_stages"] == ["level_save"]
    observed = await CurrentLevelSaves(native).reconcile(operation, "unreal-123")
    assert observed["matching_saved_packages"] is True
    external = next(item for item in observed["saved_package_files"] if item["package"].endswith("Actor_1"))
    assert inspect_project_package_file(native.context, external["package"], "/Game/Maps/Map") == external


async def test_current_save_rejects_bad_confirmation_and_stale_session(tmp_path):
    native = NativeSaveFixture(tmp_path)
    native.context["level"] = "/Game/Maps/Map.Map"
    saves = CurrentLevelSaves(native)
    preview = await saves.preview("unreal-123")
    with pytest.raises(WorkflowError, match="confirmation_required"):
        await saves.apply(preview["preview_id"], "wrong", "unreal-123")
    with pytest.raises(WorkflowError, match="wrong_target_session"):
        await saves.apply(preview["preview_id"], preview["preview_id"], "unreal-456")
    assert "current_level_save_apply" not in native.calls


async def test_current_save_verifies_world_partition_actor_package_deletion(tmp_path, monkeypatch):
    native = NativeSaveFixture(tmp_path)
    native.context["level"] = "/Game/Maps/Map.Map"
    package = "/Game/Maps/Map"
    deleted_package = "/Game/__ExternalActors__/Maps/Map/ActorRemoved"
    map_path = tmp_path / "Content" / "Maps" / "Map.umap"
    deleted_path = tmp_path / "Content" / "__ExternalActors__" / "Maps" / "Map" / "ActorRemoved.uasset"
    map_path.parent.mkdir(parents=True)
    deleted_path.parent.mkdir(parents=True)
    map_path.write_bytes(b"map-before")
    deleted_path.write_bytes(b"external-actor-before")
    native.current_level_package = package
    saves = CurrentLevelSaves(native)

    async def request(target, command, args):
        native.calls.append(command)
        if command == "current_level_save_preview":
            return {
                "preview_id": native.preview_id, "world": native.context["level"],
                "level_package": package, "package_count": 2,
                "packages": [
                    {"package": package, "will_save": True, "will_delete": False,
                     "file_existed_before": True, "before_sha1": hashlib.sha1(map_path.read_bytes()).hexdigest(),
                     "before_bytes": map_path.stat().st_size},
                    {"package": deleted_package, "will_save": False, "will_delete": True,
                     "file_existed_before": True, "before_sha1": hashlib.sha1(deleted_path.read_bytes()).hexdigest(),
                     "before_bytes": deleted_path.stat().st_size},
                ],
            }
        assert command == "current_level_save_apply"
        map_path.write_bytes(b"map-after-save")
        deleted_path.unlink()
        return {
            "operation_id": native.preview_id, "state": "saved", "saved": True,
            "level_package": package,
            "saved_packages": [
                {"package": package, "saved": True,
                 "sha1": hashlib.sha1(map_path.read_bytes()).hexdigest().upper(),
                 "bytes": map_path.stat().st_size},
                {"package": deleted_package, "saved": False, "deleted": True},
            ],
        }

    monkeypatch.setattr(native, "request", request)
    preview = await saves.preview("unreal-123")
    result = await saves.apply(preview["preview_id"], preview["preview_id"], "unreal-123")
    assert result["state"] == "saved"
    assert not deleted_path.exists()
    observed = await saves.reconcile(preview["preview_id"], "unreal-123")
    assert observed["matching_saved_packages"] is True
    assert any(item == {"package": deleted_package, "exists": False}
               for item in observed["saved_package_files"])


async def test_current_save_accepts_verified_unchanged_packages(tmp_path, monkeypatch):
    native = NativeSaveFixture(tmp_path)
    native.context["level"] = "/Game/Maps/Map.Map"
    saves = CurrentLevelSaves(native)
    original_request = native.request

    async def request(target, command, args):
        if command == "current_level_save_preview":
            preview = await original_request(target, command, args)
            for item in preview["packages"]:
                item["will_save"] = False
                item["will_delete"] = False
            return preview
        native.calls.append(command)
        saved = []
        for package, path, _ in native.current_packages:
            content = path.read_bytes()
            saved.append({"package": package, "saved": False, "deleted": False,
                          "sha1": hashlib.sha1(content).hexdigest().upper(), "bytes": len(content)})
        return {"operation_id": native.preview_id, "state": "saved", "saved": True,
                "level_package": native.current_level_package, "saved_packages": saved}

    monkeypatch.setattr(native, "request", request)
    preview = await saves.preview("unreal-123")
    result = await saves.apply(preview["preview_id"], preview["preview_id"], "unreal-123")
    assert result["state"] == "saved"
    assert len(result["saved_package_files"]) == len(preview["packages"])
    assert all(item["exists"] for item in result["saved_package_files"])
    observed = await saves.reconcile(preview["preview_id"], "unreal-123")
    assert observed["matching_saved_packages"] is True


async def test_level_reconciliation_rejects_wrong_project_and_active_operation(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    await saves.apply(operation, operation, "unreal-123")
    before = native.journal.read(operation)
    native.active.add(operation)
    with pytest.raises(WorkflowError, match="operation_active"):
        await saves.reconcile(operation, "unreal-456")
    native.active.clear()
    native.context["project_file"] = str(tmp_path / "Another.uproject")
    with pytest.raises(WorkflowError, match="wrong_target_project"):
        await saves.reconcile(operation, "unreal-456")
    assert native.journal.read(operation) == before


async def test_level_reconciliation_rejects_hardlinked_map(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    await saves.apply(operation, operation, "unreal-123")
    path = tmp_path / "Content" / "NewFolder" / "Map.umap"
    (tmp_path / "alias.umap").hardlink_to(path)
    with pytest.raises(WorkflowError, match="map_file_limit"):
        await saves.reconcile(operation, "unreal-456")


async def test_saved_map_read_failure_retains_uncertainty_without_private_detail(tmp_path, monkeypatch):
    native, saves, operation = await fixture(tmp_path)
    original_open = Path.open

    def deny_map_read(path, mode="r", *args, **kwargs):
        if path.suffix == ".umap" and mode == "rb":
            raise PermissionError(13, "private filesystem detail")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_map_read)
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "outcome_unknown"
    assert result["diagnostic_code"] == "map_file_unavailable"
    assert native.calls.count("level_save_apply") == 1
    assert native.journal.read(operation)["state"] == "outcome_unknown"
    assert "private filesystem detail" not in str(result)


async def test_unsaved_dependency_preview_has_no_token_or_receipt(tmp_path, monkeypatch):
    native = NativeSaveFixture(tmp_path)
    saves = LevelSaves(native)

    async def blocked(target, command, args):
        return {"state": "blocked", "diagnostic_code": "unsaved_dependencies", "preview_created": False,
                "source_world": native.context["level"], "asset_path": args["asset_path"],
                "dependencies": [{"package": "/Game/Unsaved/Material", "dirty": True,
                                  "disk_package_present": False, "requires_separate_save": True}]}

    monkeypatch.setattr(native, "request", blocked)
    result = await saves.preview("/Game/NewFolder/Map", "unreal-123")
    assert result["state"] == "blocked" and "preview_id" not in result
    assert saves.previews == {} and not native.journal.root.exists()


async def test_older_adapter_without_dependency_guard_cannot_preview_save(tmp_path, monkeypatch):
    native = NativeSaveFixture(tmp_path)
    saves = LevelSaves(native)

    async def old_adapter(target, command, args):
        return {"preview_id": native.preview_id, "asset_path": args["asset_path"],
                "source_world": native.context["level"]}

    monkeypatch.setattr(native, "request", old_adapter)
    with pytest.raises(WorkflowError, match="adapter_upgrade_required"):
        await saves.preview("/Game/NewFolder/Map", "unreal-123")
    assert saves.previews == {} and not native.journal.root.exists()


@pytest.mark.parametrize("code", ["timeout", "disconnected", "invalid_response"])
async def test_uncertain_native_save_stops_without_retry(tmp_path, code):
    native, saves, operation = await fixture(tmp_path)
    native.failure = code
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "outcome_unknown"
    assert native.journal.inspect(operation)["effective_state"] == "outcome_unknown"
    assert native.journal.read(operation)["plan"]["native_operation_id"] == native.preview_id
    assert native.calls.count("level_save_apply") == 1
    assert operation not in native.active
    assert "private native detail" not in str(result)


@pytest.mark.parametrize("outcome", ["started", "completed"])
async def test_receipt_failure_blocks_or_marks_save_uncertain(tmp_path, monkeypatch, outcome):
    native, saves, operation = await fixture(tmp_path)
    transition = native.journal.transition

    def fail(operation_id, revision, stage, requested, evidence=None):
        if requested == outcome:
            raise PermissionError(13, "private filesystem detail")
        return transition(operation_id, revision, stage, requested, evidence)

    monkeypatch.setattr(native.journal, "transition", fail)
    result = await saves.apply(operation, operation, "unreal-123")
    assert result["state"] == "outcome_unknown" and result["storage_error_code"] == "os_error_13"
    assert native.calls.count("level_save_apply") == (0 if outcome == "started" else 1)
    assert "private filesystem detail" not in str(result)
    assert operation not in native.active


async def test_wrong_session_and_confirmation_preserve_preview_then_changed_binding_rejects(tmp_path):
    native, saves, operation = await fixture(tmp_path)
    with pytest.raises(WorkflowError, match="confirmation_required"):
        await saves.apply(operation, "wrong", "unreal-123")
    with pytest.raises(WorkflowError, match="wrong_target_session"):
        await saves.apply(operation, operation, "unreal-456")
    assert operation in saves.previews
    native.token = "different-session-token"
    with pytest.raises(WorkflowError, match="stale_preview"):
        await saves.apply(operation, operation, "unreal-123")
    assert "level_save_apply" not in native.calls
    assert not (native.journal.root / operation).exists()
