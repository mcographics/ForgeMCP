"""Typed, bounded requests for read-only native Unreal collision queries."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_COLLISION_QUERIES = 32
MAX_IGNORED_ACTORS = 16
MAX_QUERY_DISTANCE_CM = 100_000.0
MAX_COORDINATE_CM = 10_000_000.0
MAX_SWEEP_RADIUS_CM = 5_000.0
MAX_CAPSULE_HALF_HEIGHT_CM = 10_000.0

CollisionCoordinate = Annotated[
    float,
    Field(strict=True, ge=-MAX_COORDINATE_CM, le=MAX_COORDINATE_CM),
]
WorldVector = tuple[CollisionCoordinate, CollisionCoordinate, CollisionCoordinate]


class CollisionQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    shape: Literal["line", "sphere", "capsule"]
    start_cm: WorldVector
    end_cm: WorldVector
    channel_name: str = Field(min_length=1, max_length=64)
    radius_cm: float | None = Field(default=None, strict=True, gt=0, le=MAX_SWEEP_RADIUS_CM)
    half_height_cm: float | None = Field(
        default=None, strict=True, gt=0, le=MAX_CAPSULE_HALF_HEIGHT_CM
    )
    trace_complex: bool = Field(default=True, strict=True)
    ignored_actor_paths: list[str] = Field(default_factory=list, max_length=MAX_IGNORED_ACTORS)

    @model_validator(mode="after")
    def validate_shape_and_ignores(self) -> CollisionQuery:
        if self.channel_name.strip() != self.channel_name:
            raise ValueError("channel_name must not include leading or trailing whitespace")
        if self.shape == "line" and (self.radius_cm is not None or self.half_height_cm is not None):
            raise ValueError("line queries do not accept radius_cm or half_height_cm")
        if self.shape == "sphere" and (
            self.radius_cm is None or self.half_height_cm is not None
        ):
            raise ValueError("sphere queries require radius_cm and do not accept half_height_cm")
        if self.shape == "capsule":
            if self.radius_cm is None or self.half_height_cm is None:
                raise ValueError("capsule queries require radius_cm and half_height_cm")
            if self.half_height_cm < self.radius_cm:
                raise ValueError("capsule half_height_cm must be at least radius_cm")
        if any(not path or len(path) > 512 for path in self.ignored_actor_paths):
            raise ValueError("ignored_actor_paths entries must be nonempty paths up to 512 characters")
        if len(set(self.ignored_actor_paths)) != len(self.ignored_actor_paths):
            raise ValueError("ignored_actor_paths must not contain duplicates")
        return self


class CollisionQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    queries: list[CollisionQuery] = Field(min_length=1, max_length=MAX_COLLISION_QUERIES)
    max_query_distance_cm: float = Field(
        default=MAX_QUERY_DISTANCE_CM,
        strict=True,
        gt=0,
        le=MAX_QUERY_DISTANCE_CM,
    )

    @model_validator(mode="after")
    def validate_distances(self) -> CollisionQueryRequest:
        for index, query in enumerate(self.queries):
            distance = math.dist(query.start_cm, query.end_cm)
            if distance > self.max_query_distance_cm:
                raise ValueError(
                    f"queries[{index}] length {distance:.3f} cm exceeds "
                    f"max_query_distance_cm {self.max_query_distance_cm:.3f} cm"
                )
        return self
