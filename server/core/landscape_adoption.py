"""Typed requests only: approval is exclusively a local Unreal Editor action."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AdoptionAction = Literal["setup_layer", "raise", "lower", "flatten", "smooth", "generate", "apply_heightmap", "coastline"]


class LandscapeAdoptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    actor_path: str = Field(min_length=1, max_length=512)
    project_file: str = Field(min_length=1, max_length=1024)
    world_path: str = Field(pattern=r"^/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+$")
    world_partition: bool = Field(strict=True)
    editor_pid: int = Field(gt=0)
    landscape_guid: str = Field(pattern=r"^[A-Fa-f0-9]{32}$")
    region: tuple[Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)]]
    actions: list[AdoptionAction] = Field(min_length=1, max_length=8)
    lifetime_seconds: int = Field(default=600, ge=30, le=3600)

    @model_validator(mode="after")
    def bounded_scope(self):
        x1, y1, x2, y2 = self.region
        limit = 4_194_304 if self.actions == ["setup_layer"] else 1_048_576
        if x2 < x1 or y2 < y1 or (x2-x1+1)*(y2-y1+1) > limit:
            raise ValueError("Adoption region exceeds the bounded operation scope")
        if len(set(self.actions)) != len(self.actions):
            raise ValueError("Adoption operations must be unique")
        if "setup_layer" in self.actions and self.actions != ["setup_layer"]:
            raise ValueError("Layer setup requires its own approval and checkpoint")
        return self
