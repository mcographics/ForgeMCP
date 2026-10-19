"""Typed requests for bounded, reviewed Unreal actor property access."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ActorPropertyEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_path: Annotated[str, Field(min_length=1, max_length=512)]
    property_name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")]
    property_value: Annotated[str, Field(max_length=512)]


class ActorDeletePreview(BaseModel):
    """Preview deleting one exact actor from the current editor level."""

    model_config = ConfigDict(extra="forbid")
    actor_path: Annotated[str, Field(min_length=1, max_length=512)]
