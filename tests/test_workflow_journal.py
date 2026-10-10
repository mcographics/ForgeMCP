import json
import os
import subprocess
import sys
import uuid

import pytest

from server.core.workflow_journal import STAGES, JournalError, WorkflowJournal


def fixture(tmp_path):
    store = WorkflowJournal(tmp_path / "receipts")
    operation_id = uuid.uuid4().hex
    record = store.create(operation_id, {
        "source_session_id": "blender-123", "target_session_id": "unreal-456",
        "target_asset_path": "/Game/ForgeTransfer/SM_Cube",
    })
    return store, operation_id, record


def test_receipts_complete_in_order_and_cannot_be_replayed(tmp_path):
    store, operation_id, record = fixture(tmp_path)
    for stage in STAGES:
        record = store.transition(operation_id, record["revision"], stage, "started")
        record = store.transition(operation_id, record["revision"], stage, "completed", {"native_state": "confirmed"})
    restarted = WorkflowJournal(store.root)
    assert restarted.read(operation_id) == record
    report = restarted.inspect(operation_id)
    assert report["effective_state"] == "completed"
    assert report["runtime_state_verified"] is False
    assert report["automatic_native_replay_allowed"] is False
    with pytest.raises(JournalError, match="operation_terminal"):
        restarted.transition(operation_id, record["revision"], "export", "started")
    with pytest.raises(JournalError, match="operation_exists"):
        restarted.create(operation_id, {})
    assert restarted.read(operation_id) == record


def test_restart_distinguishes_pending_native_effect_from_completed_step(tmp_path):
    store, operation_id, record = fixture(tmp_path)
    record = store.transition(operation_id, 0, "export", "started")
    assert store.inspect(operation_id, active=True)["effective_state"] == "running"
    assert WorkflowJournal(store.root).inspect(operation_id)["effective_state"] == "outcome_unknown"
    record = store.transition(operation_id, record["revision"], "export", "completed")
    assert WorkflowJournal(store.root).inspect(operation_id)["effective_state"] == "interrupted"


def test_stage_order_and_stale_revision_are_rejected(tmp_path):
    store, operation_id, _ = fixture(tmp_path)
    with pytest.raises(JournalError, match="stage_order"):
        store.transition(operation_id, 0, "import", "started")
    record = store.transition(operation_id, 0, "export", "started")
    with pytest.raises(JournalError, match="revision_conflict"):
        store.transition(operation_id, 0, "export", "completed")
    assert store.read(operation_id) == record


@pytest.mark.parametrize("state", ["failed", "partial", "outcome_unknown", "rolled_back"])
def test_failure_outcomes_are_retained_without_native_replay(tmp_path, state):
    store, operation_id, _ = fixture(tmp_path)
    store.transition(operation_id, 0, "export", "started")
    record = store.transition(operation_id, 1, "export", state, {"diagnostic_code": "native_failure"})
    assert WorkflowJournal(store.root).inspect(operation_id)["effective_state"] == state
    assert record["events"][-1]["evidence"] == {"diagnostic_code": "native_failure"}


def test_write_failure_leaves_started_intent_and_previous_revision(tmp_path, monkeypatch):
    import server.core.workflow_journal as journal

    store, operation_id, _ = fixture(tmp_path)
    started = store.transition(operation_id, 0, "export", "started")
    protect = journal.protect_path

    def fail_temporary(path):
        if path.suffix == ".tmp":
            raise OSError("injected write failure")
        return protect(path)

    monkeypatch.setattr(journal, "protect_path", fail_temporary)
    with pytest.raises(OSError, match="injected"):
        store.transition(operation_id, 1, "export", "completed")
    assert store.read(operation_id) == started
    assert store.inspect(operation_id)["effective_state"] == "outcome_unknown"
    assert not list((store.root / operation_id).glob("*.tmp"))


@pytest.mark.parametrize("plan", [
    {"token": "do-not-store"}, {"headers": {"Authorization": "do-not-store"}},
    {"session_password": "do-not-store"}, {"private_key": "do-not-store"},
    {"value": float("nan")}, {"value": "x" * (256 * 1024)},
])
def test_credentials_and_invalid_or_excessive_data_are_rejected_before_storage(tmp_path, plan):
    store = WorkflowJournal(tmp_path / "receipts")
    with pytest.raises(JournalError):
        store.create(uuid.uuid4().hex, plan)
    assert not store.root.exists()


def test_operation_paths_and_malformed_records_cannot_escape_store(tmp_path):
    store, operation_id, _ = fixture(tmp_path)
    with pytest.raises(JournalError, match="invalid_operation_id"):
        store.read("../outside")
    path = store.root / operation_id / "record.json"
    record = store.read(operation_id)
    record["state"] = []
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(JournalError, match="invalid_record"):
        store.read(operation_id)


def test_actual_file_lock_excludes_other_writers(tmp_path):
    store, operation_id, _ = fixture(tmp_path)
    with store._locked(store._directory(operation_id)):
        with pytest.raises(JournalError, match="record_busy"):
            store.transition(operation_id, 0, "export", "started")


def test_process_crash_releases_os_lock_without_deleting_receipt(tmp_path):
    store, operation_id, _ = fixture(tmp_path)
    store.transition(operation_id, 0, "export", "started")
    script = (
        "import os,sys; from server.core.workflow_journal import WorkflowJournal; "
        "s=WorkflowJournal(sys.argv[1]); "
        "lock=s._locked(s._directory(sys.argv[2])); lock.__enter__(); os._exit(0)"
    )
    result = subprocess.run([sys.executable, "-c", script, str(store.root), operation_id],
                            timeout=20, check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode()
    assert (store.root / operation_id / "record.lock").exists()
    assert store.inspect(operation_id)["effective_state"] == "outcome_unknown"
    record = store.transition(operation_id, 1, "export", "outcome_unknown")
    assert record["state"] == "outcome_unknown"


def test_hardlinked_record_is_rejected(tmp_path):
    store, operation_id, _ = fixture(tmp_path)
    path = store.root / operation_id / "record.json"
    os.link(path, tmp_path / "alias.json")
    with pytest.raises(JournalError, match="unsafe_record_path"):
        store.read(operation_id)


@pytest.mark.parametrize("case", ["completion_without_events", "finish_without_start",
                                 "skipped_stages", "duplicate_start", "events_after_terminal"])
def test_reported_state_must_match_ordered_event_history(tmp_path, case):
    store, operation_id, _ = fixture(tmp_path)
    record = store.read(operation_id)
    event = {"stage": "export", "outcome": "started", "at": record["created_at"], "evidence": {}}
    if case == "completion_without_events":
        record.update(state="completed", completed_stages=record["planned_stages"][:])
    elif case == "finish_without_start":
        record.update(state="running", completed_stages=["export"], events=[{**event, "outcome": "completed"}])
    elif case == "skipped_stages":
        record.update(state="running", active_stage="import", completed_stages=["export", "staging"],
                      events=[{**event, "stage": "import"}])
    elif case == "duplicate_start":
        record.update(state="running", active_stage="export", events=[event, event.copy()])
    else:
        record.update(state="running", active_stage="export", events=[event,
            {**event, "outcome": "failed"}, event.copy()])
    record["revision"] = len(record["events"])
    path = store.root / operation_id / "record.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(JournalError, match="invalid_record"):
        store.read(operation_id)
