import pytest
from pydantic import ValidationError

from server.core.assets import AssetPropertyEdit


def test_asset_property_edit_accepts_exact_project_assets_and_native_text():
    request = AssetPropertyEdit.model_validate({
        "asset_path": "/JasperPrism/Materials/MI_Photo.MI_Photo",
        "property_name": "Roughness",
        "property_value": "0.35",
    })
    assert request.property_value == "0.35"
    empty_string = AssetPropertyEdit.model_validate({
        "asset_path": "/Game/Props/DA_Metadata",
        "property_name": "Description",
        "property_value": "",
    })
    assert empty_string.property_value == ""


@pytest.mark.parametrize("values", [
    {"asset_path": "/Engine/EngineMaterials/DefaultMaterial", "property_name": "b", "property_value": "true"},
    {"asset_path": "/Game/M/MI", "property_name": "../value", "property_value": "1"},
    {"asset_path": "/Game/M/MI", "property_name": "value", "property_value": "1", "execute": "x"},
])
def test_asset_property_edit_rejects_unsafe_paths_identifiers_and_extra_fields(values):
    with pytest.raises(ValidationError):
        AssetPropertyEdit.model_validate(values)
