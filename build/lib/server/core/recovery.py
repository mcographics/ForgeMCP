# SPDX-License-Identifier: MIT
"""Reviewed asset restoration from retained staging; no original-operation replay."""

import time
import uuid
from pathlib import Path

from server.core.connections import BridgeError
from server.core.transfer import (
    TransferArtifactError,
    stage_unreal_artifact,
    verify_staged_artifact,
)
from server.core.workflow_journal import RECOVERY_STAGES, JournalError
from server.core.workflows import TransferRequest, WorkflowError, verify_import


class AssetRecovery:
    def __init__(self, transfers):
        self.transfers = transfers
        self.journal = transfers.journal
        self.previews = {}

    async def preview(self, operation_id, session_id, asset_path):
        original = self.journal.inspect(operation_id, active=operation_id in self.transfers.active)
        if original["effective_state"] not in {"partial", "outcome_unknown", "interrupted"}:
            raise WorkflowError("operation_not_recoverable")
        record = original["record"]
        if operation_id in self.transfers.active:
            raise WorkflowError("operation_active")
        request = TransferRequest.model_validate(record["plan"]["request"])
        if asset_path == request.target_asset_path:
            raise WorkflowError("new_destination_required")
        target = self.transfers.session("unreal", session_id)
        context = await self.transfers.target_context(target)
        if Path(context["project_file"]).resolve() != Path(record["plan"]["target"]["project_file"]).resolve():
            raise WorkflowError("wrong_target_project")
        exports = [e["evidence"] for e in record["events"] if e["stage"] == "export" and e["outcome"] == "completed"]
        if not exports and record["plan"].get("workflow_kind") == "retained_export_recovery":
            retained = record["plan"].get("retained_export")
            if isinstance(retained, dict) and retained.get("transfer_id") == operation_id:
                exports = [retained]
        staged = any(e["stage"] == "staging" and e["outcome"] == "completed" for e in record["events"])
        if not exports or not staged:
            raise WorkflowError("retained_export_unavailable")
        exported = exports[-1]
        manifest = self.transfers.manifest(exported, request, record["plan"]["target"], exported["transfer_id"], exported=True)
        root = Path(context["project_file"]).parent / "Saved" / "ForgeTransfers" / manifest.transfer_id
        verify_staged_artifact(root, manifest)
        recovered_request = request.model_copy(update={"target_session_id": session_id,
            "target_asset_path": asset_path, "save_assets": True, "place": False})
        recovered_request = TransferRequest.model_validate(recovered_request.model_dump())
        await self._new_destination(target, asset_path)
        now = time.monotonic()
        self.previews = {key: plan for key, plan in self.previews.items() if plan["expires"] > now}
        if len(self.previews) >= 32:
            raise WorkflowError("preview_limit")
        preview_id = uuid.uuid4().hex
        self.previews[preview_id] = {"origin": operation_id, "origin_revision": record["revision"],
            "request": recovered_request, "manifest": manifest, "artifact_root": root,
            "export": exported, "context": context, "binding": self.transfers.binding(target), "expires": now + 300}
        return {"preview_id": preview_id, "operation_id": preview_id, "original_operation_id": operation_id,
                "changes": recovered_request.model_dump(), "expires_in_seconds": 300,
                "uses_retained_export": True, "requires_blender_session": False,
                "overwrites_assets": False, "modifies_original_receipt": False,
                "discards_partial_assets": False, "places_actor": False, "saves_level": False}

    async def _new_destination(self, target, asset_path):
        try:
            await self.transfers.connections.request(target, "asset_info", {"asset_path": asset_path})
        except BridgeError as error:
            if error.code != "asset_not_found":
                raise
        else:
            raise WorkflowError("destination_exists")

    async def apply(self, preview_id, confirmation):
        if preview_id != confirmation:
            raise WorkflowError("confirmation_required")
        plan = self.previews.pop(preview_id, None)
        if plan is None or plan["expires"] <= time.monotonic():
            raise WorkflowError("preview_not_found")
        request = plan["request"]
        target = self.transfers.session("unreal", request.target_session_id)
        if (self.transfers.binding(target) != plan["binding"] or
                await self.transfers.target_context(target) != plan["context"] or
                self.journal.read(plan["origin"])["revision"] != plan["origin_revision"]):
            raise WorkflowError("stale_preview")
        await self._new_destination(target, request.target_asset_path)
        verify_staged_artifact(plan["artifact_root"], plan["manifest"])
        values = plan["manifest"].model_dump()
        values.update(transfer_id=preview_id, target_session_id=request.target_session_id,
                      target_asset_path=request.target_asset_path)
        manifest = type(plan["manifest"]).model_validate(values)
        retained_export = {**plan["export"], "transfer_id": preview_id, "status": "retained_export_validated"}
        record = self.journal.create(preview_id, {"workflow_kind": "retained_export_recovery",
            "original_operation_id": plan["origin"], "request": request.model_dump(),
            "target": plan["context"], "retained_export": retained_export}, stages=RECOVERY_STAGES)
        self.transfers.active.add(preview_id)

        def receipt(stage, outcome, evidence=None):
            nonlocal record
            record = self.journal.transition(preview_id, record["revision"], stage, outcome, evidence)

        try:
            receipt("staging", "started")
            recipe = stage_unreal_artifact(plan["artifact_root"], manifest, save=True, transfer_materials=True)
            receipt("staging", "completed", {"recipe": recipe, "original_export_retained": True})
            receipt("import", "started")
            if await self.transfers.target_context(target) != plan["context"]:
                raise WorkflowError("stale_target")
            native_preview = await self.transfers.connections.request(target, "mesh_import_preview", {"recipe": recipe})
            imported = await self.transfers.connections.request(target, "mesh_import_apply", {
                "preview_id": native_preview["preview_id"], "confirmation": native_preview["preview_id"]})
            if imported.get("state") != "imported":
                state = imported.get("state")
                receipt("import", state if state in {"partial", "rolled_back", "outcome_unknown"} else "outcome_unknown", imported)
                return {"operation_id": preview_id, "state": record["state"], "receipt": record}
            receipt("import", "completed", imported)
            receipt("verification", "started")
            checks = verify_import(manifest, imported)
            if imported.get("saved") is not True or any(m.get("saved") is not True for m in imported.get("materials", [])):
                raise WorkflowError("save_verification_failed")
            receipt("verification", "completed", checks)
            return {"operation_id": preview_id, "state": "completed", "receipt": record,
                    "original_operation_id": plan["origin"], "partial_assets_preserved": True,
                    "actor_placement_performed": False}
        except (JournalError, OSError) as error:
            return {"operation_id": preview_id, "state": "outcome_unknown", "diagnostic_code": "receipt_unavailable",
                    "storage_error_code": error.code if isinstance(error, JournalError) else f"os_error_{error.errno or 0}",
                    "automatic_native_replay_allowed": False}
        except (BridgeError, WorkflowError, TransferArtifactError, ValueError, KeyError, TypeError) as error:
            code = getattr(error, "code", "invalid_native_result")
            state = "outcome_unknown" if code in {"outcome_unknown", "timeout", "disconnected", "invalid_response"} else "partial" if "import" in record["completed_stages"] else "failed"
            try:
                receipt(record["active_stage"], state, {"diagnostic_code": code})
            except (JournalError, OSError):
                state = "outcome_unknown"
            return {"operation_id": preview_id, "state": state, "diagnostic_code": code,
                    "automatic_native_replay_allowed": False}
        finally:
            self.transfers.active.discard(preview_id)
