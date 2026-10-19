"""Safety boundaries of the public Landscape MCP contract."""

import pytest
from pydantic import ValidationError

from server.core.landscape import (
    MAX_EDIT_REGION_SAMPLES,
    MAX_HEIGHTMAP_CHUNK_SAMPLES,
    LandscapeRequest,
)


@pytest.mark.parametrize("path", ["/Game/Levels/L_City_World_Master", "../City",
                                  "/Game/ForgeMCPTests/Landscape/../../City", ""])
def test_create_rejects_protected_or_ambiguous_destination(path):
    with pytest.raises(ValidationError):
        LandscapeRequest(action="create", map_path=path)


@pytest.mark.parametrize("field,value", [("height_cm", float("nan")),
                                         ("height_cm", float("inf")),
                                         ("region", [10, 0, 2, 5]),
                                         ("region", [-1, 0, 5, 5]),
                                         ("rows_per_stage", 1000),
                                         ("stage_interval_seconds", 0)])
def test_edit_rejects_unbounded_values(field, value):
    with pytest.raises(ValidationError):
        LandscapeRequest.model_validate({"action": "raise", "actor_path": "/Game/Test:Terrain",
                                         field: value})


def test_heightmap_requires_exact_bounded_samples():
    with pytest.raises(ValidationError):
        LandscapeRequest(action="apply_heightmap", actor_path="terrain", region=(0, 0, 1, 1),
                         samples_cm=[1, 2, 3])
    request = LandscapeRequest(action="apply_heightmap", actor_path="terrain",
                               region=(0, 0, 1, 1), samples_cm=[1, 2, 3, 4])
    assert len(request.samples_cm) == 4


def test_heightmap_chunks_allow_32768_samples_with_exact_dimensions():
    request = LandscapeRequest(
        action="apply_heightmap",
        actor_path="terrain",
        region=(0, 0, 255, 127),
        samples_cm=[0] * MAX_HEIGHTMAP_CHUNK_SAMPLES,
    )
    assert len(request.samples_cm) == 32_768
    assert request.model_dump()["region"] == (0, 0, 255, 127)

    with pytest.raises(ValidationError):
        LandscapeRequest(
            action="apply_heightmap",
            actor_path="terrain",
            region=(0, 0, 255, 128),
            samples_cm=[0] * (MAX_HEIGHTMAP_CHUNK_SAMPLES + 1),
        )


def test_bounded_edit_regions_support_1009_square_but_cap_chunks_at_one_million_samples():
    request = LandscapeRequest(
        action="coastline",
        actor_path="terrain",
        region=(0, 0, 1008, 1008),
    )
    assert (request.region[2] + 1) * (request.region[3] + 1) == 1_018_081
    assert MAX_EDIT_REGION_SAMPLES == 1_048_576

    with pytest.raises(ValidationError):
        LandscapeRequest(action="smooth", actor_path="terrain",
                         region=(0, 0, 1024, 1023))


def test_chunked_sculpting_keeps_one_global_operation_region_for_seam_free_falloff():
    left = LandscapeRequest(
        action="raise", actor_path="terrain", region=(0, 0, 255, 511),
        operation_region=(0, 0, 511, 511),
    )
    right = LandscapeRequest(
        action="raise", actor_path="terrain", region=(256, 0, 511, 511),
        operation_region=(0, 0, 511, 511),
    )
    assert left.operation_region == right.operation_region

    with pytest.raises(ValidationError):
        LandscapeRequest(action="coastline", actor_path="terrain",
                         region=(0, 0, 255, 511), operation_region=(0, 0, 127, 511))
    with pytest.raises(ValidationError):
        LandscapeRequest(action="smooth", actor_path="terrain",
                         operation_region=(0, 0, 100, 100))


def test_supported_landscape_topology_scales_within_native_resource_budget():
    request = LandscapeRequest(
        action="create",
        map_path="/Game/ForgeMCPTests/Landscape/LargeNative",
        components_x=4,
        components_y=4,
        quads_per_section=127,
        sections_per_component=2,
    )
    assert request.components_x * request.components_y == 16
    assert (request.components_x * 127 * 2 + 1) ** 2 == 1_034_289


def test_world_partition_test_creation_is_typed_and_bounded():
    request = LandscapeRequest(
        action="create",
        map_path="/Game/ForgeMCPTests/Landscape/Partitioned",
        components_x=4,
        components_y=4,
        world_partition=True,
        partition_grid_size_components=2,
    )
    assert request.world_partition
    assert request.partition_grid_size_components == 2


def test_in_place_world_partition_creation_is_typed_and_has_no_destination_map():
    request = LandscapeRequest(
        action="create_in_place",
        components_x=4,
        components_y=4,
        quads_per_section=63,
        sections_per_component=1,
        world_partition=True,
        partition_grid_size_components=2,
    )
    assert (request.components_x * 63 * request.sections_per_component + 1) == 253

    with pytest.raises(ValidationError):
        LandscapeRequest(action="create_in_place", world_partition=True,
                         map_path="/Game/ForgeMCPTests/Landscape/Elsewhere")
    with pytest.raises(ValidationError):
        LandscapeRequest(action="create_in_place")
    with pytest.raises(ValidationError):
        LandscapeRequest(action="create_in_place", world_partition=True,
                         actor_path="/Game/Test:Landscape")


def test_engine_basic_visual_material_is_an_explicit_create_only_option():
    request = LandscapeRequest(
        action="create",
        map_path="/Game/ForgeMCPTests/Landscape/VisualMaterial",
        use_engine_basic_landscape_material=True,
    )
    assert request.use_engine_basic_landscape_material is True

    with pytest.raises(ValidationError):
        LandscapeRequest(
            action="raise",
            actor_path="/Game/ForgeMCPTests/Landscape/VisualMaterial:Landscape_0",
            use_engine_basic_landscape_material=True,
        )


def test_maximum_sample_topology_fits_the_native_resource_budget():
    request = LandscapeRequest(
        action="create",
        map_path="/Game/ForgeMCPTests/Landscape/MaximumSamples",
        components_x=4,
        components_y=4,
        quads_per_section=255,
        sections_per_component=2,
    )
    assert (request.components_x * 510 + 1) ** 2 == 4_165_681


def test_world_partition_region_loader_operations_are_typed_and_bounded():
    request = LandscapeRequest(action="load_region", actor_path="/Game/Test:Terrain",
                               region=(120, 120, 140, 140))
    assert request.action == "load_region"
    unload = LandscapeRequest(action="unload_region", actor_path="/Game/Test:Terrain",
                              partition_loader_id="a" * 32)
    assert unload.partition_loader_id == "a" * 32
    with pytest.raises(ValidationError):
        LandscapeRequest(action="unload_region", actor_path="/Game/Test:Terrain")
    with pytest.raises(ValidationError):
        LandscapeRequest(action="load_region", actor_path="/Game/Test:Terrain",
                         region=(0, 0, 1024, 1024))


@pytest.mark.parametrize("components,quads,sections", [(18, 127, 2), (33, 63, 1), (5, 255, 2)])
def test_creation_rejects_topology_over_sample_budget(components, quads, sections):
    with pytest.raises(ValidationError):
        LandscapeRequest(
            action="create",
            map_path="/Game/ForgeMCPTests/Landscape/OverBudget",
            components_x=components,
            components_y=components,
            quads_per_section=quads,
            sections_per_component=sections,
        )


def test_proposed_4573_sample_topology_is_not_admitted_by_the_16_mib_creation_budget():
    width = 18 * 127 * 2 + 1
    assert width == 4_573
    assert width * width == 20_912_329
    assert width * width * 2 == 41_824_658
    with pytest.raises(ValidationError):
        LandscapeRequest(
            action="create",
            map_path="/Game/ForgeMCPTests/Landscape/Proposed4573",
            components_x=18,
            components_y=18,
            quads_per_section=127,
            sections_per_component=2,
        )


def test_unknown_fields_and_missing_target_fail_closed():
    with pytest.raises(ValidationError):
        LandscapeRequest(action="raise")
    with pytest.raises(ValidationError):
        LandscapeRequest(action="save", actor_path="terrain", execute="arbitrary")
