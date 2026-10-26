# SPDX-License-Identifier: MIT
"""Bounded, read-only request models for native Blueprint graph inspection."""

from typing import Annotated, Literal

from pydantic import Field

from server.core.recipes import RecipeModel

BlueprintAssetPath = Annotated[
    str,
    Field(pattern=r"^/Game/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+$", min_length=7, max_length=240),
]
BlueprintGraphName = Annotated[str, Field(min_length=1, max_length=128)]
BlueprintNodeGuid = Annotated[
    str,
    Field(pattern=r"^(?:[0-9A-Fa-f]{32}|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})$"),
]
BlueprintGraphCursor = Annotated[str, Field(pattern=r"^g[0-9A-Fa-f]{32}:[0-9]{1,10}$", max_length=64)]
BlueprintPinCursor = Annotated[str, Field(pattern=r"^p[0-9A-Fa-f]{32}:[0-9]{1,10}$", max_length=64)]


class BlueprintGraphListRequest(RecipeModel):
    asset_path: BlueprintAssetPath


class BlueprintGraphPageRequest(RecipeModel):
    asset_path: BlueprintAssetPath
    graph_name: BlueprintGraphName
    page_size: Annotated[int, Field(ge=1, le=64)] = 32
    cursor: BlueprintGraphCursor | None = None
    node_guid: BlueprintNodeGuid | None = None
    class_path: Annotated[str, Field(max_length=512)] | None = None
    title_contains: Annotated[str, Field(max_length=256)] | None = None
    function_name: Annotated[str, Field(max_length=128)] | None = None
    comment_contains: Annotated[str, Field(max_length=256)] | None = None


class BlueprintNodeInspectRequest(RecipeModel):
    asset_path: BlueprintAssetPath
    graph_name: BlueprintGraphName
    node_guid: BlueprintNodeGuid
    pin_page_size: Annotated[int, Field(ge=1, le=128)] = 32
    pin_cursor: BlueprintPinCursor | None = None


class BlueprintExecutionTraceRequest(RecipeModel):
    asset_path: BlueprintAssetPath
    graph_name: BlueprintGraphName
    start_node_guid: BlueprintNodeGuid
    direction: Literal["forward", "backward", "both"] = "forward"
    depth: Annotated[int, Field(ge=0, le=32)] = 4
    node_limit: Annotated[int, Field(ge=1, le=512)] = 256
