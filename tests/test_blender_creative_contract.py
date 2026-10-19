import pytest
from pydantic import ValidationError

from server.core.blender_creative import BlenderCreativeRequest, BlenderTarget


def test_native_creation_parameters_survive_typed_contract():
    value = BlenderCreativeRequest(
        action="create_object",
        name="Sun",
        type="mesh.primitive_uv_sphere_add",
        parameters={"segments": 128, "ring_count": 64, "radius": 1.0},
    )
    assert value.model_dump()["parameters"]["segments"] == 128


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "eval", "code": "1+1"},
        {"action": "render", "frame_start": 5, "frame_end": 1},
        {"action": "render", "frame_start": 1, "frame_end": 1001},
        {"action": "save_copy", "path": "x.blend", "overwrite": True},
        {"action": "render", "frame_start": True},
    ],
)
def test_invalid_outer_requests_rejected(payload):
    with pytest.raises(ValidationError):
        BlenderCreativeRequest(**payload)


@pytest.mark.parametrize(
    "target",
    [
        {"kind": "python", "name": "bpy"},
        {"kind": "object", "name": "Cube", "expression": '__import__("os")'},
    ],
)
def test_no_arbitrary_target_traversal(target):
    with pytest.raises(ValidationError):
        BlenderTarget(**target)
