import pytest
from pydantic import ValidationError

from server.core.recipes import BlueprintEditRecipe, BlueprintRecipe


def test_existing_graph_and_spaced_member_references_reach_native_validation():
    recipe = BlueprintEditRecipe(
        asset_path="/Game/Nav/Component",
        nodes=[{"id": "radius", "kind": "variable_get", "name": "Scale Radius",
                "graph": "RefreshNav"},
               {"id": "interval", "kind": "variable_get", "name": "NavRefreshInterval",
                "graph": "Widget Setup"}],
        connections=[{"graph": "Widget Setup", "from_node": "interval",
                      "from_pin": "NavRefreshInterval", "to_node": "ABC123", "to_pin": "Time"}],
    )
    assert recipe.nodes[0].name == "Scale Radius"
    assert recipe.connections[0].graph == "Widget Setup"


@pytest.mark.parametrize("name", ["Scale\nRadius", "Scale\tRadius", "Scale Radius ",
                                  "Scale/Radius", "Scale;Radius", "X" * 65])
def test_member_reference_rejects_control_characters_and_unbounded_names(name):
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Component", nodes=[
            {"id": "radius", "kind": "variable_get", "name": name},
        ])


def test_function_identifiers_and_new_member_identifiers_remain_strict():
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Component", nodes=[
            {"id": "call", "kind": "call_function", "name": "Bad Function"},
        ])
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Component", variables=[
            {"name": "New Member", "type": "float"},
        ])
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Component", nodes=[
            {"id": "entry", "kind": "function_entry", "name": "Entry", "graph": "RefreshNav"},
        ])


def test_new_blueprint_still_rejects_undeclared_function_graphs():
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path="/Game/Nav/New", nodes=[
            {"id": "radius", "kind": "variable_get", "name": "Scale Radius",
             "graph": "RefreshNav"},
        ])


def test_blueprint_component_settings_are_typed_and_bounded():
    recipe = BlueprintEditRecipe(asset_path="/Game/Space/BP_Sky", component_settings=[
        {"component_name": "SkySphereMesh", "mobility": "Movable", "material_slots": [
            {"index": 0, "material_path": "/Game/Space/Materials/MI_Spacebox_Stars.MI_Spacebox_Stars"}
        ]}
    ])
    assert recipe.component_settings[0].mobility == "Movable"
    assert recipe.component_settings[0].material_slots[0].index == 0


@pytest.mark.parametrize("settings", [
    [{"component_name": "SkySphereMesh", "mobility": "Dynamic"}],
    [{"component_name": "SkySphereMesh", "material_slots": [
        {"index": 32, "material_path": "/Game/Space/M.M"}
    ]}],
    [{"component_name": "SkySphereMesh", "material_slots": [
        {"index": 0, "material_path": "C:/temp/M.uasset"}
    ]}],
    [{"component_name": "SkySphereMesh", "mobility": "Movable", "unexpected": True}],
])
def test_blueprint_component_settings_reject_unsupported_or_unbounded_values(settings):
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Space/BP_Sky", component_settings=settings)
