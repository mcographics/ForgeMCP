# SPDX-License-Identifier: MIT
"""Reviewed native creation of a disposable Empty Open World map."""

import re
import time

from pydantic import BaseModel, ConfigDict, Field

from server.core.connections import BridgeError
from server.core.levels import inspect_map_file
from server.core.workflow_journal import LEVEL_CREATE_STAGES, JournalError
from server.core.workflows import WorkflowError


class EmptyOpenWorldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    map_path: str = Field(
        pattern=r"^/Game/ForgeMCPTests/EmptyOpenWorld/[A-Za-z][A-Za-z0-9_]{0,63}$",
        max_length=160,
    )


class EmptyOpenWorldCreations:
    """Preview/apply coordinator with session binding and no native replay."""

    def __init__(self, transfers):
        self.transfers = transfers
        self.journal = transfers.journal
        self.previews = {}

    async def preview(self, request: EmptyOpenWorldRequest, session_id: str):
        target = self.transfers.session("unreal", session_id)
        context = await self.transfers.target_context(target)
        if context.get("play_in_editor") is True:
            raise WorkflowError("editor_world_required")
        native = await self.transfers.connections.request(
            target, "level_create_preview", {"map_path": request.map_path},
        )
        native_id = native.get("preview_id")
        if (
            not isinstance(native_id, str)
            or not re.fullmatch(r"[0-9a-fA-F]{32}", native_id)
            or native.get("map_path") != request.map_path
            or native.get("source_world") != context.get("level")
            or native.get("template") != "Empty Open World"
            or native.get("world_partition_requested") is not True
            or native.get("overwrites_existing") is not False
        ):
            raise WorkflowError("invalid_native_result")
        preview_id = native_id.lower()
        now = time.monotonic()
        self.previews = {key: plan for key, plan in self.previews.items() if plan["expires"] > now}
        if len(self.previews) >= 16:
            raise WorkflowError("preview_limit")
        self.previews[preview_id] = {
            "native_preview_id": native_id,
            "map_path": request.map_path,
            "session_id": session_id,
            "context": context,
            "binding": self.transfers.binding(target),
            "expires": now + 300,
        }
        return {
            **native,
            "preview_id": preview_id,
            "operation_id": preview_id,
            "durable_receipt_on_apply": True,
            "automatic_native_replay_allowed": False,
        }

    async def apply(self, preview_id: str, confirmation: str, session_id: str):
        if preview_id != confirmation:
            raise WorkflowError("confirmation_required")
        plan = self.previews.get(preview_id)
        if plan is None or plan["expires"] <= time.monotonic():
            self.previews.pop(preview_id, None)
            raise WorkflowError("preview_not_found")
        if session_id != plan["session_id"]:
            raise WorkflowError("wrong_target_session")
        self.previews.pop(preview_id)
        target = self.transfers.session("unreal", session_id)
        if (
            self.transfers.binding(target) != plan["binding"]
            or await self.transfers.target_context(target) != plan["context"]
        ):
            raise WorkflowError("stale_preview")
        record = self.journal.create(preview_id, {
            "workflow_kind": "empty_open_world_creation",
            "native_operation_id": plan["native_preview_id"],
            "target_session_id": session_id,
            "target": plan["context"],
            "map_path": plan["map_path"],
        }, stages=LEVEL_CREATE_STAGES)
        self.transfers.active.add(preview_id)
        try:
            record = self.journal.transition(
                preview_id, record["revision"], "level_create", "started",
            )
            native = await self.transfers.connections.request(target, "level_create_apply", {
                "preview_id": plan["native_preview_id"],
                "confirmation": plan["native_preview_id"],
            })
            if (
                native.get("operation_id") != plan["native_preview_id"]
                or native.get("map_path") != plan["map_path"]
                or native.get("state") not in {"saved", "partial", "outcome_unknown"}
            ):
                raise BridgeError("invalid_response", "Invalid native level creation result")
            if native["state"] == "saved":
                expected_world = f"{plan['map_path']}.{plan['map_path'].rsplit('/', 1)[1]}"
                if (
                    native.get("world") != expected_world
                    or native.get("world_partition_enabled") is not True
                    or native.get("partition_initialized") is not True
                    or native.get("partition_subsystem_available") is not True
                    or native.get("landscape_actor_count") != 0
                ):
                    raise BridgeError("invalid_response", "Native level creation did not verify the requested world")
                native["saved_map_file"] = inspect_map_file(plan["context"], plan["map_path"])
                if not native["saved_map_file"].get("exists"):
                    raise BridgeError("invalid_response", "Native saved map is absent")
                current = await self.transfers.target_context(target)
                if current.get("level") != expected_world:
                    raise WorkflowError("created_world_not_current")
            outcome = "completed" if native["state"] == "saved" else (
                "outcome_unknown" if native["state"] == "outcome_unknown" else "partial"
            )
            record = self.journal.transition(preview_id, record["revision"], "level_create", outcome, native)
            return {
                **native,
                "operation_id": preview_id,
                "native_operation_id": plan["native_preview_id"],
                "receipt": record,
            }
        except (JournalError, OSError) as error:
            return {
                "operation_id": preview_id,
                "state": "outcome_unknown",
                "diagnostic_code": "receipt_unavailable",
                "storage_error_code": error.code if isinstance(error, JournalError) else f"os_error_{error.errno or 0}",
                "automatic_native_replay_allowed": False,
            }
        except (BridgeError, WorkflowError) as error:
            uncertain = isinstance(error, WorkflowError) or error.code in {
                "timeout", "disconnected", "invalid_response", "outcome_unknown",
            }
            outcome = "outcome_unknown" if uncertain else "failed"
            try:
                record = self.journal.transition(
                    preview_id, record["revision"], "level_create", outcome,
                    {"diagnostic_code": error.code},
                )
            except (JournalError, OSError):
                outcome = "outcome_unknown"
            return {
                "operation_id": preview_id,
                "state": outcome,
                "diagnostic_code": error.code,
                "automatic_native_replay_allowed": False,
            }
        finally:
            self.transfers.active.discard(preview_id)
