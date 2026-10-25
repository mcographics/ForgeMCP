"""Owner-approved, process-local Landscape editing sessions; no remote approval API."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.core.landscape_adoption import LandscapeAdoptionRequest

SculptAction = Literal[
    "raise", "lower", "flatten", "smooth", "generate", "apply_heightmap", "coastline",
]


class LandscapeEditSessionRequest(LandscapeAdoptionRequest):
    """The inclusive authorization region must include each operation's normal halo."""

    layer_name: Literal["ForgeTerrain"] = "ForgeTerrain"
    layer_guid: str = Field(pattern=r"^[A-Fa-f0-9]{32}$")
    actions: list[SculptAction] = Field(min_length=1, max_length=7)
    lifetime_seconds: int = Field(default=7200, ge=60, le=86400, strict=True)
    region_scope: Literal["bounded", "entire_landscape"] = "bounded"

    @model_validator(mode="after")
    def bounded_scope(self):
        # Override the one-operation request budget, not the per-operation limits.
        x1, y1, x2, y2 = self.region
        limit = 4_194_304 if self.region_scope == "entire_landscape" else 1_048_576
        if x2 < x1 or y2 < y1 or (x2 - x1 + 1) * (y2 - y1 + 1) > limit:
            raise ValueError("Editing session region exceeds its explicit scope budget")
        if len(set(self.actions)) != len(self.actions):
            raise ValueError("Editing session operations must be unique")
        return self


class LandscapeEditSessionReference(BaseModel):
    # Keep control messages separate: callers cannot patch an existing grant.
    model_config = ConfigDict(extra="forbid")
    edit_session_id: str = Field(pattern=r"^[A-Fa-f0-9]{32}$")


class LandscapeHeightRegionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor_path: str = Field(min_length=1, max_length=512)
    layer_guid: str = Field(pattern=r"^[A-Fa-f0-9]{32}$")
    region: tuple[Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)]]

    @model_validator(mode="after")
    def bounded_read(self):
        x1, y1, x2, y2 = self.region
        if x2 < x1 or y2 < y1 or (x2 - x1 + 1) * (y2 - y1 + 1) > 32_768:
            raise ValueError("Height readback is limited to 32,768 ordered samples")
        return self
