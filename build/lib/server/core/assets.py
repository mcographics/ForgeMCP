# SPDX-License-Identifier: MIT
"""Typed request models for bounded Unreal asset operations."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

AssetPath = Annotated[
    str,
    Field(
        pattern=r"^/(?:Game|JasperPrism)/(?:[A-Za-z_][A-Za-z0-9_]*/)*[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$",
        max_length=240,
    ),
]


class AssetPropertyEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_path: AssetPath
    property_name: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")]
    # Unreal's native property text format is parsed by the native property type.
    property_value: Annotated[str, Field(max_length=512)]
