# SPDX-License-Identifier: MIT
"""Private, durable transfer receipts; never replay native operations on restart.

Write a started receipt before every native side effect. A restarted coordinator
must treat an unfinished receipt as uncertain and inspect the application first.
This store records evidence; it does not prove current native state by itself.
"""

import json
import math
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from server.core.security import protect_path

MAX_RECORD_BYTES = 256 * 1024
STAGES = ("export", "staging", "import", "verification", "placement")
RECOVERY_STAGES = STAGES[1:4]
LEVEL_STAGES = ("level_save",)
ALL_STAGES = STAGES + LEVEL_STAGES
TERMINAL = {"completed", "failed", "partial", "outcome_unknown", "rolled_back"}


class JournalError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _safe(path):
    info = path.lstat()
    if (
        stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
        or (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)
    ):
        raise JournalError("unsafe_record_path")
    return info


def _validate_data(value, depth=0):
    if depth > 12:
        raise JournalError("record_limit")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise JournalError("invalid_record")
            name = key.casefold().replace("-", "_")
            if name in {"token", "password", "secret", "api_key", "authorization", "credentials", "private_key"} or name.endswith(("_token", "_password", "_secret", "_key")):
                raise JournalError("credential_field_rejected")
            _validate_data(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_data(child, depth + 1)
    elif type(value) is float:
        if not math.isfinite(value):
            raise JournalError("invalid_record")
    elif value is not None and type(value) not in (str, int, bool):
        raise JournalError("invalid_record")


def _encode(record):
    _validate_data(record)
    try:
        data = json.dumps(record, allow_nan=False, indent=2).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise JournalError("invalid_record") from error
    if len(data) > MAX_RECORD_BYTES:
        raise JournalError("record_limit")
    return data


def _now():
    return datetime.now(timezone.utc).isoformat()


class WorkflowJournal:
    def __init__(self, root):
        self.root = Path(root).absolute()

    def _directory(self, operation_id):
        if not isinstance(operation_id, str) or not re.fullmatch(r"[0-9a-f]{32}", operation_id):
            raise JournalError("invalid_operation_id")
        directory = self.root / operation_id
        for path in (directory, *directory.parents):
            if path.exists() or path.is_symlink():
                _safe(path)
        return directory

    @contextmanager
    def _locked(self, directory):
        path = directory / "record.lock"
        if path.exists() or path.is_symlink():
            _safe(path)
        with path.open("a+b") as stream:
            protect_path(path)
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise JournalError("record_busy") from error
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def _write(self, directory, record):
        data = _encode(record)
        destination = directory / "record.json"
        if destination.exists() or destination.is_symlink():
            _safe(destination)
        temporary = directory / ("record-" + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("xb") as stream:
                protect_path(temporary)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(destination)
        finally:
            # Only this writer's generated temporary file is eligible for cleanup.
            if temporary.exists():
                _safe(temporary)
                temporary.unlink()

    def create(self, operation_id, plan, *, stages=STAGES):
        directory = self._directory(operation_id)
        if not isinstance(plan, dict) or tuple(stages) not in (STAGES, STAGES[:-1], RECOVERY_STAGES, LEVEL_STAGES):
            raise JournalError("invalid_plan")
        timestamp = _now()
        record = {
            "schema_version": 1, "operation_id": operation_id, "revision": 0,
            "state": "prepared", "active_stage": None, "completed_stages": [],
            "planned_stages": list(stages), "created_at": timestamp, "updated_at": timestamp,
            "plan": plan, "events": [],
        }
        _encode(record)  # Reject credentials/limits before creating any storage.
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            protect_path(self.root)
            directory.mkdir(exist_ok=False)
            protect_path(directory)
            with self._locked(directory):
                self._write(directory, record)
        except FileExistsError as error:
            raise JournalError("operation_exists") from error
        return record

    def read(self, operation_id):
        directory = self._directory(operation_id)
        path = directory / "record.json"
        info = _safe(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_RECORD_BYTES:
            raise JournalError("record_limit")
        try:
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise JournalError("record_changed")
                data = stream.read(MAX_RECORD_BYTES + 1)
                if len(data) > MAX_RECORD_BYTES:
                    raise JournalError("record_limit")
            record = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError) as error:
            raise JournalError("invalid_record") from error
        _encode(record)
        required = {"schema_version", "operation_id", "revision", "state", "active_stage",
                    "completed_stages", "planned_stages", "created_at", "updated_at", "plan", "events"}
        if (
            not isinstance(record, dict) or set(record) != required
            or type(record["schema_version"]) is not int or record["schema_version"] != 1
            or record["operation_id"] != operation_id
            or type(record["revision"]) is not int or not 0 <= record["revision"] <= 64
            or not isinstance(record["state"], str) or record["state"] not in {"prepared", "running", *TERMINAL}
            or record["planned_stages"] not in (list(STAGES), list(STAGES[:-1]), list(RECOVERY_STAGES), list(LEVEL_STAGES))
            or not isinstance(record["completed_stages"], list)
            or record["completed_stages"] != record["planned_stages"][:len(record["completed_stages"])]
            or record["active_stage"] not in (None, *ALL_STAGES)
            or not isinstance(record["events"], list) or len(record["events"]) > 64
            or record["revision"] != len(record["events"])
            or not isinstance(record["plan"], dict)
            or not isinstance(record["created_at"], str) or not isinstance(record["updated_at"], str)
        ):
            raise JournalError("invalid_record")
        next_index = len(record["completed_stages"])
        if (
            (record["active_stage"] is not None and (next_index >= len(record["planned_stages"]) or record["active_stage"] != record["planned_stages"][next_index]))
            or (record["state"] == "completed" and (next_index != len(record["planned_stages"]) or record["active_stage"] is not None))
            or (record["state"] == "prepared" and (record["revision"] != 0 or next_index != 0 or record["active_stage"] is not None))
        ):
            raise JournalError("invalid_record")
        derived_state, derived_active, derived_completed = "prepared", None, []
        for event in record["events"]:
            if (
                not isinstance(event, dict) or set(event) != {"stage", "outcome", "at", "evidence"}
                or event["stage"] not in ALL_STAGES or not isinstance(event["outcome"], str)
                or event["outcome"] not in {"started", *TERMINAL}
                or not isinstance(event["at"], str) or not isinstance(event["evidence"], dict)
            ):
                raise JournalError("invalid_record")
            if derived_state in TERMINAL:
                raise JournalError("invalid_record")
            stage, outcome = event["stage"], event["outcome"]
            if outcome == "started":
                index = len(derived_completed)
                if (derived_active is not None or index >= len(record["planned_stages"])
                        or stage != record["planned_stages"][index]):
                    raise JournalError("invalid_record")
                derived_state, derived_active = "running", stage
            else:
                if derived_active != stage:
                    raise JournalError("invalid_record")
                if outcome == "completed":
                    derived_completed.append(stage)
                    derived_active = None
                    if derived_completed == record["planned_stages"]:
                        derived_state = "completed"
                else:
                    derived_state = outcome
        if (derived_state != record["state"] or derived_active != record["active_stage"]
                or derived_completed != record["completed_stages"]):
            raise JournalError("invalid_record")
        return record

    def transition(self, operation_id, revision, stage, outcome, evidence=None):
        if type(revision) is not int or stage not in ALL_STAGES or outcome not in {"started", *TERMINAL}:
            raise JournalError("invalid_transition")
        evidence = {} if evidence is None else evidence
        if not isinstance(evidence, dict):
            raise JournalError("invalid_record")
        _encode(evidence)
        directory = self._directory(operation_id)
        with self._locked(directory):
            record = self.read(operation_id)
            if record["revision"] != revision:
                raise JournalError("revision_conflict")
            if record["state"] in TERMINAL:
                raise JournalError("operation_terminal")
            if outcome == "started":
                index = len(record["completed_stages"])
                if record["active_stage"] is not None or index >= len(record["planned_stages"]) or record["planned_stages"][index] != stage:
                    raise JournalError("stage_order")
                record.update(state="running", active_stage=stage)
            else:
                if record["active_stage"] != stage:
                    raise JournalError("stage_not_started")
                if outcome == "completed":
                    record["completed_stages"].append(stage)
                    record["active_stage"] = None
                    if record["completed_stages"] == record["planned_stages"]:
                        record["state"] = "completed"
                else:
                    record["state"] = outcome
            record["revision"] += 1
            record["updated_at"] = _now()
            record["events"].append({"stage": stage, "outcome": outcome,
                                     "at": record["updated_at"], "evidence": evidence})
            self._write(directory, record)
            return record

    def inspect(self, operation_id, *, active=False):
        record = self.read(operation_id)
        effective = record["state"]
        if effective == "running" and not active:
            effective = "outcome_unknown" if record["active_stage"] is not None else "interrupted"
        return {"record": record, "effective_state": effective,
                "runtime_state_verified": False, "automatic_native_replay_allowed": False}
