"""Bounded UE 5.6 Landscape recipes; heights are actor-local centimetres."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_EDIT_REGION_SAMPLES = 1_048_576
MAX_HEIGHTMAP_CHUNK_SAMPLES = 32_768


class LandscapeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    action: Literal["create", "create_in_place", "raise", "lower", "flatten", "smooth", "generate",
                    "apply_heightmap", "coastline", "frame", "save", "reload",
                    "load_region", "unload_region"]
    actor_path: str = Field(default="", max_length=512)
    map_path: str = Field(default="", max_length=160)
    partition_loader_id: str = Field(default="", max_length=64)
    components_x: int = Field(default=1, ge=1, le=256)
    components_y: int = Field(default=1, ge=1, le=256)
    quads_per_section: Literal[7, 15, 31, 63, 127, 255] = 63
    sections_per_component: Literal[1, 2] = 1
    world_partition: bool = False
    partition_grid_size_components: int = Field(default=2, ge=1, le=256)
    use_engine_basic_landscape_material: bool = Field(default=False, strict=True)
    xy_scale_cm: float = Field(default=100, ge=1, le=1000)
    z_scale: float = Field(default=100, ge=1, le=1000)
    region: tuple[Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)],
                  Annotated[int, Field(ge=0, le=8191)]] = (0, 0, 63, 63)
    operation_region: tuple[Annotated[int, Field(ge=0, le=8191)],
                            Annotated[int, Field(ge=0, le=8191)],
                            Annotated[int, Field(ge=0, le=8191)],
                            Annotated[int, Field(ge=0, le=8191)]] | None = None
    height_cm: float = Field(default=1000, ge=-100000, le=100000)
    strength: float = Field(default=0.5, ge=0, le=1)
    wavelength_vertices: float = Field(default=32, ge=2, le=8192)
    samples_cm: list[Annotated[float, Field(ge=-100000, le=100000)]] = Field(
        default_factory=list, max_length=MAX_HEIGHTMAP_CHUNK_SAMPLES)
    rows_per_stage: int = Field(default=4, ge=1, le=8)
    stage_interval_seconds: float = Field(default=0.3, ge=0.1, le=2)

    @model_validator(mode="after")
    def validate_operation(self):
        x1, y1, x2, y2 = self.region
        if x2 < x1 or y2 < y1:
            raise ValueError("Region must have ordered inclusive bounds")
        region_samples = (x2 - x1 + 1) * (y2 - y1 + 1)
        if self.action not in {"create", "create_in_place", "load_region", "unload_region", "frame", "save", "reload"} \
                and region_samples > MAX_EDIT_REGION_SAMPLES:
            raise ValueError("A terrain edit chunk is limited to 1,048,576 region samples")
        if self.action in {"create", "create_in_place"}:
            import re
            if self.action == "create":
                if not re.fullmatch(r"/Game/ForgeMCPTests/Landscape/[A-Za-z][A-Za-z0-9_]{0,63}",
                                    self.map_path):
                    raise ValueError("Creation requires a fresh disposable Landscape test map")
            elif self.map_path or not self.world_partition:
                raise ValueError("create_in_place requires the approved existing World Partition test world and no map_path")
            if self.actor_path:
                raise ValueError("Landscape creation does not accept actor_path")
            component_count = self.components_x * self.components_y
            component_quads = self.quads_per_section * self.sections_per_component
            width = self.components_x * component_quads + 1
            height = self.components_y * component_quads + 1
            if component_count > 1024:
                raise ValueError("Landscape creation is limited to 1,024 components per map")
            if width > 8192 or height > 8192 or width * height > 4_194_304:
                raise ValueError("Landscape creation exceeds the validated 4,194,304-vertex resource budget")
        elif not self.actor_path:
            raise ValueError("An inspected actor_path is required")
        elif self.model_fields_set & {
            "components_x", "components_y", "quads_per_section", "sections_per_component",
            "world_partition", "partition_grid_size_components", "use_engine_basic_landscape_material",
        }:
            raise ValueError("Landscape topology and World Partition settings are only valid for create")
        if self.action == "unload_region":
            if not self.partition_loader_id:
                raise ValueError("unload_region requires a loader_id returned by load_region")
        elif self.partition_loader_id:
            raise ValueError("partition_loader_id is only accepted for unload_region")
        if self.action == "load_region" and region_samples > 1_048_576:
            raise ValueError("World Partition region loading is limited to 1,048,576 sample cells")
        if self.action in {"load_region", "unload_region"} and self.samples_cm:
            raise ValueError("World Partition region operations do not accept height samples")
        if self.action == "apply_heightmap":
            if region_samples > MAX_HEIGHTMAP_CHUNK_SAMPLES:
                raise ValueError("A heightmap input chunk is limited to 32,768 samples")
            if len(self.samples_cm) != (x2-x1+1)*(y2-y1+1):
                raise ValueError("Heightmap sample count must match the region")
        elif self.samples_cm:
            raise ValueError("Samples are only accepted for apply_heightmap")
        if self.operation_region is not None:
            if self.action not in {"raise", "lower", "coastline"}:
                raise ValueError("operation_region is only supported for chunked raise, lower, or coastline edits")
            ox1, oy1, ox2, oy2 = self.operation_region
            if ox2 < ox1 or oy2 < oy1:
                raise ValueError("operation_region must have ordered inclusive bounds")
            if not (ox1 <= x1 <= x2 <= ox2 and oy1 <= y1 <= y2 <= oy2):
                raise ValueError("The edit chunk must be contained by operation_region")
        return self
