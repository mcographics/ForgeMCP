import math

import pytest

from scripts.reference_city_regions import (
    CHUNK_PIXELS,
    DISTRICTS,
    IMAGE,
    City,
    area,
    clip_rect,
    region_bounds,
    region_for,
    road_clearance,
    triangulate,
    unreal_position,
)


def test_numbered_regions_cover_reference_without_gaps():
    assert [region_for(x,y) for y in (100,600,1100) for x in (100,600,1100)]==list(range(1,10))
    assert region_for(IMAGE,IMAGE)==9
    assert region_for(-1,0) is None
    assert sum((b[2]-b[0])*(b[3]-b[1]) for b in map(region_bounds,range(1,10)))==IMAGE**2
    assert unreal_position(IMAGE/2,IMAGE/2)==[0,0,0]


@pytest.mark.parametrize('name,polygon',DISTRICTS)
def test_shoreline_triangulation_and_region_clipping_preserve_area(name,polygon):
    triangles=triangulate(polygon)
    expected=abs(area(polygon))
    assert math.isclose(sum(abs(area(t)) for t in triangles),expected,rel_tol=1e-9),name
    pieces=[clip_rect(t,region_bounds(r)) for t in triangles for r in range(1,10)]
    assert math.isclose(sum(abs(area(p)) for p in pieces if len(p)>=3),expected,rel_tol=1e-9),name


def test_road_segments_are_local_and_region_boundary_ownership_is_unique():
    city=City()
    city.line((0,418),(1254,418),4,20,2,3)
    assert city.chunks
    for ch in city.chunks.values():
        assert ch['region'] in (4,5,6)
        points=ch['vertices']
        span=max(v[0] for v in points)-min(v[0] for v in points)
        assert span <= CHUNK_PIXELS*3+100
        assert max(v[2] for v in points)==22


def test_major_road_corridors_exclude_building_footprints():
    assert road_clearance(88,307)<0
    assert road_clearance(0,0)>6
