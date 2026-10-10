# SPDX-License-Identifier: MIT
"""Reviewed level saving with private durable intent receipts and no replay."""

import hashlib
import os
import re
import stat
import time
from pathlib import Path

from server.core.connections import BridgeError
from server.core.workflow_journal import LEVEL_STAGES, JournalError
from server.core.workflows import WorkflowError


def inspect_map_file(context, asset_path):
    """Bounded read of a derived project map path; never use a response's filename."""
    if not isinstance(asset_path, str) or not re.fullmatch(
            r"/Game/(?:[A-Za-z][A-Za-z0-9_]*/)+[A-Za-z][A-Za-z0-9_]*", asset_path) or len(asset_path) > 200:
        raise WorkflowError("invalid_map_path")
    path = Path(context["project_file"]).absolute().parent / "Content" / (asset_path[6:] + ".umap")
    try:
        for ancestor in reversed((path, *path.parents)):
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise WorkflowError("unsafe_map_path")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 128 * 1024 * 1024:
            raise WorkflowError("map_file_limit")
        def identity(item):
            return (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_nlink)
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if identity(before) != identity(info):
                raise WorkflowError("map_file_changed")
            digest = hashlib.sha256()
            total = 0
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > info.st_size:
                    raise WorkflowError("map_file_changed")
                digest.update(chunk)
            if (identity(os.fstat(stream.fileno())) != identity(info)
                    or identity(path.lstat()) != identity(info) or total != info.st_size):
                raise WorkflowError("map_file_changed")
        return {"exists": True, "bytes": total, "sha256": digest.hexdigest()}
    except FileNotFoundError:
        return {"exists": False}
    except OSError:
        raise WorkflowError("map_file_unavailable") from None


class LevelSaves:
    def __init__(self, transfers):
        self.transfers = transfers
        self.journal = transfers.journal
        self.previews = {}

    async def preview(self, asset_path, session_id):
        target = self.transfers.session("unreal", session_id)
        context = await self.transfers.target_context(target)
        native = await self.transfers.connections.request(target, "level_save_preview", {"asset_path": asset_path})
        if "dependencies" not in native:
            raise WorkflowError("adapter_upgrade_required")
        dependencies = native["dependencies"]
        if (not isinstance(dependencies, list) or len(dependencies) > 256
                or any(not isinstance(item, dict) or not isinstance(item.get("package"), str)
                       or any(type(item.get(key)) is not bool for key in
                              ("dirty", "disk_package_present", "requires_separate_save"))
                       or item["requires_separate_save"] != (item["dirty"] or not item["disk_package_present"])
                       for item in dependencies)):
            raise WorkflowError("invalid_native_result")
        native["dependency_scan_scope"] = "loaded_hard_references"
        native["soft_references_verified"] = False
        native["dependency_saved_contents_verified"] = False
        if any(item["requires_separate_save"] for item in dependencies) and native.get("state") != "blocked":
            raise WorkflowError("invalid_native_result")
        if native.get("state") == "blocked" and native.get("diagnostic_code") == "unsaved_dependencies":
            if (native.get("preview_created") is not False or "preview_id" in native
                    or native.get("source_world") != context["level"] or native.get("asset_path") != asset_path):
                raise WorkflowError("invalid_native_result")
            return native
        native_id = native["preview_id"]
        if (not isinstance(native_id, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", native_id)
                or native.get("asset_path") != asset_path or native.get("source_world") != context["level"]):
            raise WorkflowError("invalid_native_result")
        preview_id = native_id.lower()
        now = time.monotonic()
        self.previews = {key: plan for key, plan in self.previews.items() if plan["expires"] > now}
        if len(self.previews) >= 32:
            raise WorkflowError("preview_limit")
        self.previews[preview_id] = {"target_session_id": session_id, "asset_path": asset_path,
            "native_preview_id": native_id,
            "context": context, "binding": self.transfers.binding(target), "expires": now + 300}
        return {**native, "preview_id": preview_id, "operation_id": preview_id, "durable_receipt_on_apply": True}

    async def apply(self, preview_id, confirmation, session_id):
        if preview_id != confirmation:
            raise WorkflowError("confirmation_required")
        plan = self.previews.get(preview_id)
        if plan is None or plan["expires"] <= time.monotonic():
            self.previews.pop(preview_id, None)
            raise WorkflowError("preview_not_found")
        if session_id != plan["target_session_id"]:
            raise WorkflowError("wrong_target_session")
        self.previews.pop(preview_id)
        target = self.transfers.session("unreal", session_id)
        if (self.transfers.binding(target) != plan["binding"]
                or await self.transfers.target_context(target) != plan["context"]):
            raise WorkflowError("stale_preview")
        record = self.journal.create(preview_id, {"workflow_kind": "level_save",
            "native_operation_id": plan["native_preview_id"],
            "target_session_id": session_id, "target": plan["context"], "asset_path": plan["asset_path"]},
            stages=LEVEL_STAGES)
        self.transfers.active.add(preview_id)
        try:
            record = self.journal.transition(preview_id, record["revision"], "level_save", "started")
            native = await self.transfers.connections.request(target, "level_save_apply", {
                "preview_id": plan["native_preview_id"], "confirmation": plan["native_preview_id"]})
            if (native.get("operation_id") != plan["native_preview_id"] or native.get("asset_path") != plan["asset_path"]
                    or native.get("state") not in {"saved", "partial", "outcome_unknown"}
                    or (native["state"] == "saved" and native.get("saved") is not True)):
                raise BridgeError("invalid_response", "Invalid native save result")
            if native["state"] == "saved":
                native["saved_map_file"] = inspect_map_file(plan["context"], plan["asset_path"])
                if not native["saved_map_file"]["exists"]:
                    raise BridgeError("invalid_response", "Native saved map is absent")
            outcome = "completed" if native["state"] == "saved" else native["state"]
            record = self.journal.transition(preview_id, record["revision"], "level_save", outcome, native)
            return {**native, "operation_id": preview_id, "native_operation_id": plan["native_preview_id"], "receipt": record}
        except (JournalError, OSError) as error:
            return {"operation_id": preview_id, "state": "outcome_unknown", "diagnostic_code": "receipt_unavailable",
                "storage_error_code": error.code if isinstance(error, JournalError) else f"os_error_{error.errno or 0}",
                "automatic_native_replay_allowed": False}
        except (BridgeError, WorkflowError) as error:
            # File validation follows the native call, so its failure cannot prove
            # that saving had no effect.
            uncertain = isinstance(error, WorkflowError)
            outcome = "outcome_unknown" if uncertain or error.code in {"timeout", "disconnected", "invalid_response", "outcome_unknown"} else "failed"
            try:
                record = self.journal.transition(preview_id, record["revision"], "level_save", outcome,
                                                 {"diagnostic_code": error.code})
            except (JournalError, OSError):
                outcome = "outcome_unknown"
            return {"operation_id": preview_id, "state": outcome, "diagnostic_code": error.code,
                    "automatic_native_replay_allowed": False}
        finally:
            self.transfers.active.discard(preview_id)

    async def reconcile(self, operation_id, session_id):
        inspected = self.journal.inspect(operation_id, active=operation_id in self.transfers.active)
        record = inspected["record"]
        plan = record["plan"]
        if plan.get("workflow_kind") != "level_save":
            raise WorkflowError("wrong_workflow_kind")
        if operation_id in self.transfers.active:
            raise WorkflowError("operation_active")
        target = self.transfers.session("unreal", session_id)
        context = await self.transfers.target_context(target)
        if Path(context["project_file"]).resolve() != Path(plan["target"]["project_file"]).resolve():
            raise WorkflowError("wrong_target_project")
        current = inspect_map_file(context, plan["asset_path"])
        completed = [e["evidence"] for e in record["events"]
                     if e["stage"] == "level_save" and e["outcome"] == "completed"]
        saved = completed[-1].get("saved_map_file") if completed else None
        expected_world = plan["asset_path"] + "." + plan["asset_path"].rsplit("/", 1)[1]
        return {"operation_id": operation_id, "recorded_state": inspected["effective_state"],
            "target_session_id": session_id, "current_world": context["level"],
            "matching_world_loaded": context["level"] == expected_world,
            "map_file": current, "matches_recorded_saved_checksum": current == saved if saved is not None else None,
            "runtime_world_identity_verified": True, "native_map_contents_verified": False,
            "unsaved_world_changes_checked": False, "receipt_modified": False,
            "recovery_completed": False, "automatic_native_replay_allowed": False}
