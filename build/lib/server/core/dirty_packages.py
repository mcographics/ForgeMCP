"""Typed, bounded requests for loaded Unreal package dirty-state inspection."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_DIRTY_PACKAGE_PAGE_SIZE = 50
MAX_DIRTY_PACKAGE_OFFSET = 50_000


class DirtyPackageInspectionRequest(BaseModel):
    """Page through a native snapshot of dirty packages currently loaded in one Editor."""

    model_config = ConfigDict(extra="forbid", strict=True)

    offset: int = Field(default=0, ge=0, le=MAX_DIRTY_PACKAGE_OFFSET)
    limit: int = Field(default=MAX_DIRTY_PACKAGE_PAGE_SIZE, ge=1, le=MAX_DIRTY_PACKAGE_PAGE_SIZE)
    snapshot_id: str | None = Field(default=None, min_length=32, max_length=32, pattern=r"^[A-Fa-f0-9]{32}$")
    target_map_path: str | None = Field(default=None, min_length=1, max_length=160)

    @model_validator(mode="after")
    def require_snapshot_for_followup_page(self) -> DirtyPackageInspectionRequest:
        if self.offset > 0 and self.snapshot_id is None:
            raise ValueError("snapshot_id is required when offset is greater than zero")
        if self.target_map_path is not None:
            import re
            if not re.fullmatch(r"/Game/ForgeMCPTests/Landscape/[A-Za-z][A-Za-z0-9_]{0,63}",
                                self.target_map_path):
                raise ValueError("target_map_path must be a disposable Landscape test package path")
        return self
