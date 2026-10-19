import pytest
from pydantic import ValidationError

from server.core.actors import ActorDeletePreview, ActorPropertyEdit


def test_actor_property_edit_accepts_exact_world_actor_path_and_native_text():
    request = ActorPropertyEdit.model_validate({
        "actor_path": "/Game/Maps/Test.Test:PersistentLevel.PointLight_0",
        "property_name": "InitialLifeSpan",
        "property_value": "2.0",
    })
    assert request.property_value == "2.0"


def test_actor_delete_preview_requires_one_exact_actor_path():
    request = ActorDeletePreview.model_validate({
        "actor_path": "/Game/Maps/Test.Test:PersistentLevel.Manager_0",
    })
    assert request.actor_path.endswith("Manager_0")
    with pytest.raises(ValidationError):
        ActorDeletePreview.model_validate({"actor_path": "/Game/Map.Actor", "recursive": True})


@pytest.mark.parametrize("values", [
    {"actor_path": "", "property_name": "InitialLifeSpan", "property_value": "2"},
    {"actor_path": "/Game/Map.Map:Actor", "property_name": "../Location", "property_value": "2"},
    {"actor_path": "/Game/Map.Map:Actor", "property_name": "InitialLifeSpan", "property_value": "2", "execute": "x"},
    {"actor_path": "/Game/Map.Map:Actor", "property_name": "InitialLifeSpan", "property_value": "x" * 513},
])
def test_actor_property_edit_rejects_bad_paths_identifiers_and_extra_fields(values):
    with pytest.raises(ValidationError):
        ActorPropertyEdit.model_validate(values)
