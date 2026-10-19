import pytest
from pydantic import ValidationError

from server.core.materials import (
    FORGE_TEST_MATERIAL,
    FORGE_TEST_MATERIAL_PERMISSION,
    JASPER_MATERIAL,
    JASPER_PERMISSION,
    MaterialRecipe,
)


def authorized_contrast_recipe():
    return {
        "asset_path": JASPER_MATERIAL,
        "development_authorization": {
            "asset_path": JASPER_MATERIAL,
            "permission": JASPER_PERMISSION,
            "expected_state_id": "149AAA3B44ABF59654A9A09E800196C5",
        },
        "nodes": [{"id": "contrast_add", "type": "Add", "parameters": {"const_b": 0.5}}],
        "connections": [
            {
                "from_node": "D9AF96894C1AA1C1DA0FF88CFDCE842F",
                "to_node": "contrast_add",
                "to_input": "A",
            }
        ],
        "properties": [{"from_node": "contrast_add", "property": "EmissiveColor"}],
    }


def authorized_test_material_recipe():
    return {
        "asset_path": FORGE_TEST_MATERIAL,
        "creation_authorization": {
            "asset_path": FORGE_TEST_MATERIAL,
            "permission": FORGE_TEST_MATERIAL_PERMISSION,
            "expected_state": "absent",
        },
        "nodes": [
            {"id": "scene", "type": "SceneTexture", "parameters": {"scene_texture_id": "PostProcessInput0"}},
            {"id": "subtract", "type": "Subtract", "parameters": {"const_b": 0.5}},
            {"id": "multiply", "type": "Multiply", "parameters": {"const_b": 1.08}},
            {"id": "add", "type": "Add", "parameters": {"const_b": 0.5}},
        ],
        "connections": [
            {"from_node": "scene", "from_output": "Color", "to_node": "subtract", "to_input": "A"},
            {"from_node": "subtract", "to_node": "multiply", "to_input": "A"},
            {"from_node": "multiply", "to_node": "add", "to_input": "A"},
        ],
        "properties": [{"from_node": "add", "property": "EmissiveColor"}],
    }


def test_scoped_contrast_authorization_and_compile():
    data = authorized_contrast_recipe()
    assert MaterialRecipe(**data).nodes[0].type == "Add"
    compile_data = {k: data[k] for k in ("asset_path", "development_authorization")}
    assert MaterialRecipe(**compile_data, action="compile").action == "compile"
    with pytest.raises(ValidationError, match="saving"):
        MaterialRecipe(**compile_data, action="save")


@pytest.mark.parametrize(
    "mutation",
    [
        "no_consent",
        "bad_consent",
        "different_target",
        "different_auth_target",
        "path_case",
        "object_path",
        "invalid_state",
        "extra_authorization",
        "extra_recipe",
        "extra_node",
        "wrong_constant",
        "wrong_type",
        "wrong_alias",
        "wrong_source_guid",
        "wrong_pin",
        "wrong_output",
        "wrong_property_source",
        "extra_connection",
        "extra_parameter",
        "update",
    ],
)
def test_development_authorization_rejects_scope_expansion(mutation):
    data = authorized_contrast_recipe()
    auth = data["development_authorization"]
    if mutation == "no_consent":
        data.pop("development_authorization")
    elif mutation == "bad_consent":
        auth["permission"] = "yes"
    elif mutation == "different_target":
        data["asset_path"] = "/Game/Other"
    elif mutation == "different_auth_target":
        auth["asset_path"] = "/Game/Other"
    elif mutation == "path_case":
        data["asset_path"] = JASPER_MATERIAL.lower()
    elif mutation == "object_path":
        data["asset_path"] += ".M_JasperPrism_PP"
    elif mutation == "invalid_state":
        auth["expected_state_id"] = "stale"
    elif mutation == "extra_authorization":
        auth["global_bypass"] = True
    elif mutation == "extra_recipe":
        data["delete"] = True
    elif mutation == "extra_node":
        data["nodes"].append({"id": "extra", "type": "Add"})
    elif mutation == "wrong_constant":
        data["nodes"][0]["parameters"]["const_b"] = 0.6
    elif mutation == "wrong_type":
        data["nodes"][0]["type"] = "Multiply"
    elif mutation == "wrong_alias":
        data["nodes"][0]["id"] = "arbitrary"
    elif mutation == "wrong_source_guid":
        data["connections"][0]["from_node"] = "alias"
    elif mutation == "wrong_pin":
        data["connections"][0]["to_input"] = "B"
    elif mutation == "wrong_output":
        data["connections"][0]["from_output"] = "Color"
    elif mutation == "wrong_property_source":
        data["properties"][0]["from_node"] = "other"
    elif mutation == "extra_connection":
        data["connections"].append(data["connections"][0].copy())
    elif mutation == "extra_parameter":
        data["nodes"][0]["parameters"]["const_a"] = 1.0
    elif mutation == "update":
        data["updates"] = [
            {"node_id": "existing", "type": "Multiply", "parameters": {"const_b": 2.0}}
        ]
    with pytest.raises(ValidationError):
        MaterialRecipe(**data)


async def test_authorization_creation_denied_without_dispatch(monkeypatch):
    import server.main as main

    async def forbidden_dispatch(*args):
        pytest.fail("Creation authorization must not reach native dispatch")

    monkeypatch.setattr(main.connections, "dispatch", forbidden_dispatch)
    with pytest.raises(ValueError, match="cannot create or replace"):
        await main.unreal_preview_material(
            MaterialRecipe(**authorized_contrast_recipe()), "unreal-1"
        )


async def test_authorization_is_bound_into_edit_preview(monkeypatch):
    import server.main as main

    calls = []

    async def dispatch(kind, command, session, args):
        calls.append((command, args))
        return {"ok": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    await main.unreal_preview_material_edits(
        MaterialRecipe(**authorized_contrast_recipe()), "unreal-1"
    )
    assert calls[0][0] == "material_edit_preview"
    assert calls[0][1]["recipe"]["development_authorization"]["permission"] == JASPER_PERMISSION


def test_test_material_creation_authorization_is_exact_and_disjoint():
    recipe = MaterialRecipe(**authorized_test_material_recipe())
    assert recipe.creation_authorization.asset_path == FORGE_TEST_MATERIAL
    assert recipe.model_dump()["creation_authorization"]["expected_state"] == "absent"


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_target",
        "wrong_path_case",
        "wrong_permission",
        "destination_present",
        "existing_material_target",
        "unrelated_target",
        "compile_action",
        "save_action",
        "both_authorizations",
        "unknown_auth_field",
        "update_existing_node",
    ],
)
def test_test_material_creation_authorization_rejects_scope_expansion(mutation):
    data = authorized_test_material_recipe()
    auth = data["creation_authorization"]
    if mutation == "wrong_target":
        data["asset_path"] = "/Game/Other"
    elif mutation == "wrong_path_case":
        data["asset_path"] = FORGE_TEST_MATERIAL.lower()
        auth["asset_path"] = data["asset_path"]
    elif mutation == "wrong_permission":
        auth["permission"] = "authorize anything"
    elif mutation == "destination_present":
        auth["expected_state"] = "present"
    elif mutation == "existing_material_target":
        data["asset_path"] = JASPER_MATERIAL
        auth["asset_path"] = JASPER_MATERIAL
    elif mutation == "unrelated_target":
        data["asset_path"] = "/JasperPrism/Materials/M_Other"
        auth["asset_path"] = data["asset_path"]
    elif mutation == "compile_action":
        data["action"] = "compile"
    elif mutation == "save_action":
        data["action"] = "save"
    elif mutation == "both_authorizations":
        data["development_authorization"] = authorized_contrast_recipe()["development_authorization"]
    elif mutation == "unknown_auth_field":
        auth["global_bypass"] = True
    elif mutation == "update_existing_node":
        data["updates"] = [{"node_id": "old", "type": "Add", "parameters": {"const_b": 1.0}}]
    with pytest.raises(ValidationError):
        MaterialRecipe(**data)


async def test_authorized_test_material_preview_dispatches_bound_consent(monkeypatch):
    import server.main as main

    calls = []

    async def dispatch(kind, command, session, args):
        calls.append((command, args))
        return {"ok": True}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    await main.unreal_preview_material(MaterialRecipe(**authorized_test_material_recipe()), "unreal-1")
    assert calls[0][0] == "material_preview"
    assert calls[0][1]["recipe"]["creation_authorization"]["permission"] == FORGE_TEST_MATERIAL_PERMISSION


async def test_unauthorized_test_material_preview_never_reaches_native_dispatch(monkeypatch):
    import server.main as main

    async def forbidden_dispatch(*args):
        pytest.fail("Test-material creation without exact authorization must not reach native dispatch")

    monkeypatch.setattr(main.connections, "dispatch", forbidden_dispatch)
    data = authorized_test_material_recipe()
    data.pop("creation_authorization")
    recipe = MaterialRecipe(**data)
    with pytest.raises(ValueError, match="requires explicit creation authorization"):
        await main.unreal_preview_material(recipe, "unreal-1")


async def test_creation_authorization_cannot_reach_existing_material_edit_dispatch(monkeypatch):
    import server.main as main

    async def forbidden_dispatch(*args):
        pytest.fail("Creation authorization must not reach the existing-material edit route")

    monkeypatch.setattr(main.connections, "dispatch", forbidden_dispatch)
    with pytest.raises(ValueError, match="cannot modify an existing material"):
        await main.unreal_preview_material_edits(
            MaterialRecipe(**authorized_test_material_recipe()), "unreal-1"
        )


def test_material_safety_rejections():
    for path in (
        "/Engine/M",
        "/OtherPlugin/M",
        "/Game/../M",
        "/Game/M.M",
        "/JasperPrism/Materials/M_JasperPrism_PP",
        "/Game/Bad Name",
    ):
        with pytest.raises(ValidationError):
            MaterialRecipe(asset_path=path)
    for node in (
        {"id": "n", "type": "Custom", "parameters": {"code": "arbitrary"}},
        {"id": "n", "type": "Constant", "parameters": {"value": float("nan")}},
        {"id": "n", "type": "Constant", "parameters": {"value": True}},
        {"id": "n", "type": "Add", "parameters": {"const_b": "0.5"}},
        {"id": "n", "type": "VectorParameter", "parameters": {"default_value": [0, 1, 2]}},
        {"id": "n", "type": "SceneTexture", "parameters": {"scene_texture_id": "SceneDepth"}},
        {"id": "n", "type": "SceneTexture", "parameters": {"filtered": 1}},
    ):
        with pytest.raises(ValidationError):
            MaterialRecipe(asset_path="/Game/M", nodes=[node])
    with pytest.raises(ValidationError):
        MaterialRecipe(asset_path="/Game/M", action="save", nodes=[{"id": "n", "type": "Add"}])


def test_material_graph_rejects_cycles_and_occupied_duplicate_targets():
    links = [
        {"from_node": "a", "to_node": "b", "to_input": "A"},
        {"from_node": "b", "to_node": "a", "to_input": "A"},
    ]
    with pytest.raises(ValidationError, match="cycles"):
        MaterialRecipe(asset_path="/Game/M", connections=links)
    with pytest.raises(ValidationError, match="Duplicate destination"):
        MaterialRecipe(asset_path="/Game/M", connections=[links[0], links[0]])


def test_scalar_vector_parameter_recipes_keep_typed_values():
    recipe = MaterialRecipe(
        asset_path="/JasperPrism/Materials/M_ForgeMCP_Test",
        nodes=[
            {
                "id": "contrast",
                "type": "ScalarParameter",
                "parameters": {"parameter_name": "Contrast", "default_value": 1.08},
            },
            {
                "id": "tint",
                "type": "VectorParameter",
                "parameters": {"parameter_name": "Tint", "default_value": [1.0, 0.5, 0.25, 1.0]},
            },
        ],
    )
    data = recipe.model_dump()
    assert data["nodes"][0]["parameters"]["default_value"] == 1.08
    assert data["nodes"][1]["parameters"]["default_value"] == [1.0, 0.5, 0.25, 1.0]


def test_native_material_commands_extend_allowlist_without_arbitrary_execution():
    from server.core.connections import COMMANDS

    assert {
        "material_graph_info",
        "material_preview",
        "material_apply",
        "material_edit_preview",
        "material_edit_apply",
    } <= COMMANDS["unreal"]
    assert {
        "project_info",
        "blueprint_preview",
        "blueprint_apply",
        "actor_info",
        "mesh_import_preview",
        "mesh_import_apply",
        "asset_search",
    } <= COMMANDS["unreal"]
    assert not {"python", "eval", "execute", "material_delete"} & COMMANDS["unreal"]


async def test_compile_save_are_explicit_apply_and_do_not_accept_recipe(monkeypatch):
    import server.main as main

    calls = []

    async def dispatch(kind, command, session, args):
        calls.append((kind, command, session, args))
        return {"ok": True, "data": {}}

    monkeypatch.setattr(main.connections, "dispatch", dispatch)
    await main.unreal_preview_material_compile("/Game/M", "unreal-1")
    await main.unreal_compile_material("reviewed", "reviewed", "unreal-1")
    await main.unreal_preview_material_save("/Game/M", "unreal-1")
    await main.unreal_save_material("reviewed", "reviewed", "unreal-1")
    assert [c[1] for c in calls] == [
        "material_edit_preview",
        "material_edit_apply",
        "material_edit_preview",
        "material_edit_apply",
    ]
    assert calls[0][3]["recipe"]["action"] == "compile"
    assert calls[1][3] == {
        "preview_id": "reviewed",
        "confirmation": "reviewed",
        "expected_action": "compile",
    }
    assert calls[2][3]["recipe"]["action"] == "save"
    assert calls[3][3]["expected_action"] == "save"
