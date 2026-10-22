# SPDX-License-Identifier: MIT
"""Typed outer contracts; native RNA performs version-specific parameter validation."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class BlenderTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal[
        "scene",
        "render",
        "image_settings",
        "view_settings",
        "cycles",
        "eevee",
        "world",
        "object",
        "mesh",
        "camera",
        "light",
        "material",
        "node",
        "socket",
        "modifier",
        "constraint",
    ]
    name: Annotated[str, Field(max_length=256)] = ""
    component: Annotated[str, Field(max_length=256)] = ""
    socket: Annotated[str, Field(max_length=128)] = ""


class BlenderCreativeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal[
        "create_object",
        "edit_properties",
        "create_material_graph",
        "keyframe",
        "mesh_operator",
        "create_modifier",
        "create_constraint",
        "save_copy",
        "render",
    ]
    name: Annotated[str, Field(max_length=256)] = ""
    target: BlenderTarget | None = None
    type: Annotated[str, Field(max_length=128)] = ""
    properties: Annotated[dict[str, JsonValue], Field(max_length=64)] = Field(default_factory=dict)
    parameters: Annotated[dict[str, JsonValue], Field(max_length=32)] = Field(default_factory=dict)
    nodes: Annotated[list[dict[str, JsonValue]], Field(max_length=128)] = Field(
        default_factory=list
    )
    links: Annotated[list[dict[str, str]], Field(max_length=256)] = Field(default_factory=list)
    keyframes: Annotated[list[dict[str, JsonValue]], Field(max_length=256)] = Field(
        default_factory=list
    )
    path: Annotated[str, Field(max_length=1024)] = ""
    frame_start: Annotated[int, Field(ge=-100000, le=100000)] = 1
    frame_end: Annotated[int, Field(ge=-100000, le=100000)] = 1
    assign_to: Annotated[str, Field(max_length=256)] = ""
    make_active: bool = False

    @model_validator(mode="after")
    def check_render_range(self):
        if self.action == "render" and not 1 <= self.frame_end - self.frame_start + 1 <= 1000:
            raise ValueError("Render jobs require an ascending range of at most 1000 frames")
        return self
