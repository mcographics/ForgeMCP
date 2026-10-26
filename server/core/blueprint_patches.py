"""Typed existing-graph patches. Structural adapters are added independently."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from server.core.blueprint_inspection import (
    BlueprintAssetPath,
    BlueprintGraphName,
    BlueprintNodeGuid,
)


class BlueprintPatchModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class BlueprintMoveNode(BlueprintPatchModel):
    op: Literal["move_node"]
    node_guid: BlueprintNodeGuid
    x: Annotated[int, Field(ge=-100000, le=100000)]
    y: Annotated[int, Field(ge=-100000, le=100000)]


class BlueprintSetPinDefault(BlueprintPatchModel):
    op: Literal["set_pin_default"]
    node_guid: BlueprintNodeGuid
    pin_id: BlueprintNodeGuid
    value: Annotated[str, Field(max_length=4096)]


class BlueprintConnectPins(BlueprintPatchModel):
    op: Literal["connect_pins", "disconnect_pins"]
    from_node_guid: BlueprintNodeGuid
    from_pin_id: BlueprintNodeGuid
    to_node_guid: BlueprintNodeGuid
    to_pin_id: BlueprintNodeGuid


BlueprintPatchOperation = Annotated[
    BlueprintMoveNode | BlueprintSetPinDefault | BlueprintConnectPins,
    Field(discriminator="op"),
]


class BlueprintGraphPatchRequest(BlueprintPatchModel):
    asset_path: BlueprintAssetPath
    graph_name: BlueprintGraphName
    operations: Annotated[list[BlueprintPatchOperation], Field(min_length=1, max_length=32)]
