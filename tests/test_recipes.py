import pytest
from pydantic import ValidationError

from server.core.recipes import (
    ActorRecipe,
    BlueprintEditRecipe,
    BlueprintRecipe,
    CsvImportPreviewRequest,
    DataAssetCreateRequest,
    DataAssetPropertyEditRequest,
    SceneRecipe,
    StructTooltipsPreviewRequest,
)


def test_data_asset_create_request_is_exact_and_bounded():
    request = DataAssetCreateRequest(
        asset_path="/Game/Forge/DA_Weapon",
        class_path="/Script/Engine.PrimaryAssetLabel",
        properties=[{"name": "bIsRuntimeLabel", "value": "true"}],
        save=True,
    )
    assert request.properties[0].value == "true" and request.save
    invalid = [
        {"asset_path": "/Engine/DA_Weapon", "class_path": "/Script/Engine.PrimaryAssetLabel"},
        {"asset_path": "/Game/DA_Weapon.DA_Weapon", "class_path": "/Script/Engine.PrimaryAssetLabel"},
        {"asset_path": "/Game/DA_Weapon", "class_path": "/Script/Engine"},
        {"asset_path": "/Game/DA_Weapon", "class_path": "/Script/Engine.PrimaryAssetLabel",
         "properties": [{"name": "bIsRuntimeLabel", "value": "true"},
                        {"name": "bIsRuntimeLabel", "value": "false"}]},
        {"asset_path": "/Game/DA_Weapon", "class_path": "/Script/Engine.PrimaryAssetLabel", "save": "true"},
        {"asset_path": "/Game/DA_Weapon", "class_path": "/Script/Engine.PrimaryAssetLabel",
         "properties": [{"name": "bIsRuntimeLabel", "value": True}]},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            DataAssetCreateRequest(**values)


def test_csv_import_preview_is_project_asset_scoped_and_typed():
    request = CsvImportPreviewRequest(
        csv_path=r"G:\COSMOS\Dataset\bodies.csv",
        struct_path="/Game/Space/Blueprints/ST_CelestialBodyData",
        data_table_path="/Game/Data/DT_CelestialBodies",
        row_key_column="id",
        type_overrides={"hip": "string", "mass_kg": "double"},
    )
    assert request.row_key_column == "id"
    assert request.type_overrides["hip"] == "string"
    invalid = [
        {"csv_path": "x.csv", "struct_path": "/Engine/ST_X", "data_table_path": "/Game/DT_X", "row_key_column": "id"},
        {"csv_path": "x.csv", "struct_path": "/Game/ST_X.Other", "data_table_path": "/Game/DT_X", "row_key_column": "id"},
        {"csv_path": "x.csv", "struct_path": "/Game/ST_X", "data_table_path": "/Game/DT_X", "row_key_column": "id", "extra": True},
        {"csv_path": "x.csv", "struct_path": "/Game/ST_X", "data_table_path": "/Game/DT_X", "row_key_column": "id", "type_overrides": {"mass": "object"}},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            CsvImportPreviewRequest(**values)


def test_struct_tooltip_preview_request_is_bounded_and_exact():
    request = StructTooltipsPreviewRequest(
        struct_path="/Game/Space/Blueprints/ST_CelestialBodyData",
        tooltips={"ra": "Right ascension in hours.", "mean_radius_km": "Mean radius in kilometers."},
    )
    assert len(request.tooltips) == 2
    invalid = [
        {"struct_path": "/Engine/ST_X", "tooltips": {"ra": "Right ascension."}},
        {"struct_path": "/Game/ST_X.X", "tooltips": {"ra": "Right ascension."}},
        {"struct_path": "/Game/ST_X", "tooltips": {}},
        {"struct_path": "/Game/ST_X", "tooltips": {"../ra": "Right ascension."}},
        {"struct_path": "/Game/ST_X", "tooltips": {"ra": "x" * 1025}},
        {"struct_path": "/Game/ST_X", "tooltips": {"ra": "Right ascension."}, "extra": True},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            StructTooltipsPreviewRequest(**values)


def test_data_asset_property_edit_request_is_bounded_and_exact():
    request = DataAssetPropertyEditRequest(
        asset_path="/Game/Items/DA_Weapon.DA_Weapon",
        properties=[{"name": "bIsRuntimeLabel", "value": "true"},
                    {"name": "bIsEditorOnly", "value": "false"}],
        save=True,
    )
    assert len(request.properties) == 2 and request.save
    invalid = [
        {"asset_path": "/Engine/DA_Weapon", "properties": [{"name": "b", "value": "true"}]},
        {"asset_path": "/Game/Items/DA_Weapon.Other", "properties": [{"name": "b", "value": "true"}]},
        {"asset_path": "/Game/DA_Weapon", "properties": []},
        {"asset_path": "/Game/DA_Weapon", "properties": [{"name": "b", "value": "true"},
                                                             {"name": "B", "value": "false"}]},
        {"asset_path": "/Game/DA_Weapon", "properties": [{"name": "../b", "value": "true"}]},
        {"asset_path": "/Game/DA_Weapon", "properties": [{"name": "b", "value": "true"}], "save": "true"},
    ]
    for values in invalid:
        with pytest.raises(ValidationError):
            DataAssetPropertyEditRequest(**values)


def test_actor_mesh_placement_requires_exact_native_mesh_object_path():
    recipe = ActorRecipe(operations=[{
        "op": "spawn", "class_path": "/Script/Engine.StaticMeshActor",
        "mesh_path": "/Game/ForgeTransfer/SM_Cube.SM_Cube", "location": [100, 200, 300],
    }])
    assert recipe.operations[0].mesh_path == "/Game/ForgeTransfer/SM_Cube.SM_Cube"
    for mesh_path in (
        "/Engine/Cube.Cube", "/Game/../Cube.Cube", "/Game/Cube.Other",
        "/Game/Cube", "/Game/Cube.Cube:Component", "C:/Cube.fbx",
    ):
        with pytest.raises(ValidationError):
            ActorRecipe(operations=[{
                "op": "spawn", "class_path": "/Script/Engine.StaticMeshActor", "mesh_path": mesh_path,
            }])
    with pytest.raises(ValidationError, match="StaticMeshActor"):
        ActorRecipe(operations=[{
            "op": "spawn", "class_path": "/Script/Engine.PointLight",
            "mesh_path": "/Game/Cube.Cube",
        }])
    with pytest.raises(ValidationError, match="StaticMeshActor"):
        ActorRecipe(operations=[{
            "op": "transform", "actor_path": "Existing", "mesh_path": "/Game/Cube.Cube",
        }])


def test_actor_tags_are_bounded_unique_and_spawn_only():
    recipe = ActorRecipe(operations=[{
        "op": "spawn", "class_path": "/Script/Engine.PointLight",
        "tags": ["ForgeProbe", "Rendering"],
    }])
    assert recipe.operations[0].tags == ["ForgeProbe", "Rendering"]
    invalid = [
        {"op": "transform", "actor_path": "Existing", "tags": ["ForgeProbe"]},
        {"op": "spawn", "class_path": "/Script/Engine.PointLight", "tags": ["ForgeProbe", "forgeprobe"]},
        {"op": "spawn", "class_path": "/Script/Engine.PointLight", "tags": [" ForgeProbe"]},
        {"op": "spawn", "class_path": "/Script/Engine.PointLight", "tags": ["x" * 129]},
        {"op": "spawn", "class_path": "/Script/Engine.PointLight", "tags": [f"Tag{i}" for i in range(17)]},
    ]
    for operation in invalid:
        with pytest.raises(ValidationError):
            ActorRecipe(operations=[operation])


@pytest.mark.parametrize(
    "path", ["/Engine/BP", "/Game/../BP", "/Game/BP.BP", "C:/file", "/Game/Bad Name"]
)
def test_blueprint_writes_cannot_escape_game_packages(path):
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path=path)


def test_recipe_rejects_arbitrary_script_and_unbounded_numbers():
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path="/Game/BP", python="eval")
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op": "execute_python", "name": "x"}])
    with pytest.raises(ValidationError):
        SceneRecipe(
            operations=[{"op": "set_transform", "name": "x", "location": [float("nan"), 0, 0]}]
        )


def test_scene_recipe_supports_only_bounded_reviewed_modifier_operations():
    recipe = SceneRecipe(operations=[
        {"op": "add_modifier", "name": "Cube", "modifier_type": "SUBSURF",
         "modifier_name": "ForgeMCPSubdivision", "modifier_settings": {"levels": 2}},
        {"op": "set_modifier_settings", "name": "Cube", "modifier_name": "ExistingBevel",
         "modifier_settings": {"segments": 4}},
    ])
    assert recipe.operations[0].modifier_settings == {"levels": 2}
    assert recipe.operations[1].modifier_settings == {"segments": 4}
    for bad in (
        {"op": "add_modifier", "name": "Cube", "modifier_name": "Sub"},
        {"op": "add_modifier", "name": "Cube", "modifier_type": "NODES", "modifier_name": "Custom"},
        {"op": "add_modifier", "name": "Cube", "modifier_type": "SUBSURF", "modifier_name": "Bad Name"},
        {"op": "set_modifier_settings", "name": "Cube", "modifier_name": "ExistingBevel"},
        {"op": "set_modifier_settings", "name": "Cube", "modifier_settings": {"segments": 4}},
        {"op": "set_transform", "name": "Cube", "modifier_type": "SUBSURF", "modifier_name": "Sub"},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[bad])


def test_scene_recipe_accepts_bounded_mesh_topology_replacement_only():
    operation = {
        "op": "set_mesh_geometry", "name": "EditableMesh",
        "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
        "faces": [[0, 1, 2], [0, 2, 3]],
    }
    recipe = SceneRecipe(operations=[operation])
    assert recipe.operations[0].op == "set_mesh_geometry"
    assert recipe.operations[0].faces == [[0, 1, 2], [0, 2, 3]]
    for invalid in (
        {**operation, "faces": [[0, 1, 4]]},
        {**operation, "faces": [[0, 0, 1]]},
        {**operation, "vertices": [[0, 0, 0]] * 513, "faces": []},
        {**operation, "faces": [[True, 1, 2]]},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_uv_loop_edits_only():
    operation = {
        "op": "set_uv_coordinates", "name": "EditableMesh",
        "uv_layer": "UVMap", "uv_start": 2,
        "uv_values": [[0.25, 0.5], [-0.1, 1.2]],
    }
    recipe = SceneRecipe(operations=[operation])
    assert recipe.operations[0].uv_values == [[0.25, 0.5], [-0.1, 1.2]]
    for invalid in (
        {**operation, "uv_values": [[1.0]]},
        {**operation, "uv_values": [[1.0, float("inf")]]},
        {**operation, "uv_values": [[1.0, 1.0]] * 513},
        {"op": "set_transform", "name": "EditableMesh", "uv_layer": "UVMap"},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_uv_layer_creation():
    recipe = SceneRecipe(operations=[{
        "op": "create_uv_layer", "name": "EditableMesh", "uv_layer": "Lightmap UV",
        "uv_values": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
    }])
    assert recipe.operations[0].op == "create_uv_layer"
    assert SceneRecipe(operations=[{
        "op": "create_uv_layer", "name": "EditableMesh", "uv_layer": "UVMap",
    }]).operations[0].uv_values == []
    for invalid in (
        {"op": "create_uv_layer", "name": "EditableMesh"},
        {"op": "create_uv_layer", "name": "EditableMesh", "uv_layer": "UVMap", "uv_start": 1},
        {"op": "create_uv_layer", "name": "EditableMesh", "uv_layer": "UVMap", "uv_values": [[0, 0]] * 513},
        {"op": "set_transform", "name": "EditableMesh", "uv_layer": "UVMap"},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_smart_uv_projection():
    recipe = SceneRecipe(operations=[{
        "op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "GeneratedUV",
        "uv_angle_limit": 1.0, "uv_island_margin": 0.025,
    }])
    assert recipe.operations[0].uv_angle_limit == 1.0
    assert recipe.operations[0].uv_island_margin == 0.025
    assert SceneRecipe(operations=[{
        "op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "UVMap",
    }]).operations[0].uv_angle_limit > 0
    for invalid in (
        {"op": "smart_uv_project", "name": "EditableMesh"},
        {"op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "UVMap", "uv_angle_limit": 2.0},
        {"op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "UVMap", "uv_island_margin": 0.6},
        {"op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "UVMap", "uv_values": [[0, 0]]},
        {"op": "set_transform", "name": "EditableMesh", "uv_angle_limit": 0.5},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_seam_aware_uv_unwrap():
    recipe = SceneRecipe(operations=[{
        "op": "unwrap_uv", "name": "EditableMesh", "uv_layer": "UVMap",
        "uv_unwrap_method": "CONFORMAL", "uv_margin": 0.015,
    }])
    assert recipe.operations[0].uv_unwrap_method == "CONFORMAL"
    assert recipe.operations[0].uv_margin == 0.015
    assert SceneRecipe(operations=[{
        "op": "unwrap_uv", "name": "EditableMesh", "uv_layer": "UVMap",
    }]).operations[0].uv_unwrap_method == "ANGLE_BASED"
    for invalid in (
        {"op": "unwrap_uv", "name": "EditableMesh"},
        {"op": "unwrap_uv", "name": "EditableMesh", "uv_layer": "UVMap", "uv_unwrap_method": "SMART"},
        {"op": "unwrap_uv", "name": "EditableMesh", "uv_layer": "UVMap", "uv_margin": 0.6},
        {"op": "unwrap_uv", "name": "EditableMesh", "uv_layer": "UVMap", "uv_values": [[0, 0]]},
        {"op": "smart_uv_project", "name": "EditableMesh", "uv_layer": "UVMap", "uv_margin": 0.01},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_uv_island_packing():
    recipe = SceneRecipe(operations=[{
        "op": "pack_uv_islands", "name": "EditableMesh", "uv_layer": "UVMap", "uv_margin": 0.02,
    }])
    assert recipe.operations[0].uv_margin == 0.02
    for invalid in (
        {"op": "pack_uv_islands", "name": "EditableMesh"},
        {"op": "pack_uv_islands", "name": "EditableMesh", "uv_layer": "UVMap", "uv_margin": 0.6},
        {"op": "pack_uv_islands", "name": "EditableMesh", "uv_layer": "UVMap", "uv_values": [[0, 0]]},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_mesh_seam_edits():
    recipe = SceneRecipe(operations=[{
        "op": "set_mesh_edge_seams", "name": "EditableMesh",
        "edge_seams": [{"index": 0, "seam": True}, {"index": 7, "seam": False}],
    }])
    assert [item.index for item in recipe.operations[0].edge_seams] == [0, 7]
    for invalid in (
        {"op": "set_mesh_edge_seams", "name": "EditableMesh"},
        {"op": "set_mesh_edge_seams", "name": "EditableMesh", "edge_seams": [{"index": 0, "seam": 1}]},
        {"op": "set_mesh_edge_seams", "name": "EditableMesh", "edge_seams": [{"index": 0, "seam": True}] * 2},
        {"op": "set_transform", "name": "EditableMesh", "edge_seams": [{"index": 0, "seam": True}]},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_supports_typed_pose_bone_keyframes_and_rejects_invalid_rotations():
    recipe = SceneRecipe(operations=[{
        "op": "bone_keyframe",
        "name": "HeroRig",
        "bone": "upper_arm.L",
        "data_path": "rotation_euler",
        "value": [0.2, 0.0, -0.1],
        "frame": 12,
    }])
    assert recipe.operations[0].bone == "upper_arm.L"
    assert recipe.operations[0].frame == 12

    quaternion = SceneRecipe(operations=[{
        "op": "bone_keyframe",
        "name": "HeroRig",
        "bone": "Root",
        "data_path": "rotation_quaternion",
        "value": [1.0, 0.0, 0.0, 0.0],
    }])
    assert quaternion.operations[0].data_path == "rotation_quaternion"

    with pytest.raises(ValidationError, match="normalized"):
        SceneRecipe(operations=[{
            "op": "bone_keyframe",
            "name": "HeroRig",
            "bone": "Root",
            "data_path": "rotation_quaternion",
            "value": [2.0, 0.0, 0.0, 0.0],
        }])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{
            "op": "bone_keyframe",
            "name": "HeroRig",
            "bone": "Root",
            "data_path": "location",
            "value": [1.0, 2.0],
        }])
    with pytest.raises(ValidationError, match="zero scale"):
        SceneRecipe(operations=[{
            "op": "bone_keyframe",
            "name": "HeroRig",
            "bone": "Root",
            "data_path": "scale",
            "value": [1.0, 0.0, 1.0],
        }])


def test_scene_recipe_supports_bounded_existing_action_key_edits():
    edited = SceneRecipe(operations=[{
        "op": "set_keyframe", "name": "AnimatedMesh", "curve_index": 2,
        "keyframe_index": 1, "key_frame": 9.5, "key_value": -12.25,
    }]).operations[0]
    assert edited.curve_index == 2 and edited.keyframe_index == 1
    assert edited.key_frame == 9.5 and edited.key_value == -12.25

    for invalid in (
        {"op": "set_keyframe", "name": "AnimatedMesh", "curve_index": 0,
         "keyframe_index": 0, "key_frame": 1.0},
        {"op": "set_keyframe", "name": "AnimatedMesh", "curve_index": -1,
         "keyframe_index": 0, "key_frame": 1.0, "key_value": 0.0},
        {"op": "set_keyframe", "name": "AnimatedMesh", "curve_index": 0,
         "keyframe_index": 0, "key_frame": 1.0, "key_value": 0.0,
         "frame": 2},
        {"op": "keyframe", "name": "AnimatedMesh", "curve_index": 0},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_scene_recipe_accepts_bounded_armature_bones_and_parenting():
    recipe = SceneRecipe(operations=[{
        "op": "create_armature",
        "name": "ForgeMCP_Rig",
        "bones": [
            {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
            {"name": "Spine", "head": [0, 0, 1], "tail": [0, 0, 2],
             "parent": "Root", "connected": True},
            {"name": "Hand", "head": [0, 0, 2], "tail": [1, 0, 2],
             "parent": "Spine", "deform": False},
        ],
    }])
    assert len(recipe.operations[0].bones) == 3
    assert recipe.operations[0].bones[1].parent == "Root"
    assert recipe.operations[0].bones[1].connected
    assert not recipe.operations[0].bones[2].deform


def test_scene_recipe_rejects_invalid_armature_hierarchies():
    base = {"op": "create_armature", "name": "BadRig", "bones": [
        {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1]},
        {"name": "Child", "head": [0, 0, 1], "tail": [0, 0, 2], "parent": "Root"},
    ]}
    for change in (
        {"bones": [base["bones"][0], {**base["bones"][1], "parent": "Missing"}]},
        {"bones": [base["bones"][0], {**base["bones"][1], "head": [1, 0, 1], "connected": True}]},
        {"bones": [
            {"name": "Root", "head": [0, 0, 0], "tail": [0, 0, 1], "parent": "Child"},
            base["bones"][1],
        ]},
        {"bones": [base["bones"][0], {**base["bones"][1], "tail": [0, 0, 1]}]},
        {"bones": base["bones"] * 33},
    ):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[{**base, **change}])
    with pytest.raises(ValidationError, match="only for create_armature"):
        SceneRecipe(operations=[{"op": "create_mesh", "name": "Mesh",
                                "vertices": [[0, 0, 0]], "bones": base["bones"]}])


def test_automation_schemas_are_bounded_and_preserve_explicit_save_choice():
    recipe = BlueprintRecipe(
        asset_path="/Game/Forge/BP",
        variables=[{"name": "Speed", "type": "float", "default": "4.0"}],
    )
    assert not recipe.save and not recipe.place
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op": "scene_settings"}] * 33)


def test_shader_recipes_reject_script_nodes_and_unbounded_defaults():
    for kind in ("ShaderNodeScript", "GeometryNodeInputSceneTime", "execute_python"):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[{"op": "create_material", "name": "Material",
                                    "shader_nodes": [{"id": "node", "type": kind}]}])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op": "create_material", "name": "Material", "shader_nodes": [
            {"id": "surface", "type": "ShaderNodeBsdfPrincipled",
             "inputs": {"Metallic": float("inf")}}
        ]}])


def test_existing_material_graph_edits_are_additive_and_bounded():
    recipe = SceneRecipe(operations=[{
        "op": "edit_material_graph",
        "name": "Existing Material",
        "shader_nodes": [{
            "id": "ForgeRoughness",
            "type": "ShaderNodeValue",
            "outputs": {"Value": 0.35},
        }],
        "shader_links": [{
            "from_node": "ForgeRoughness", "from_socket": "Value",
            "to_node": "Principled BSDF", "to_socket": "Roughness",
        }],
    }])
    assert recipe.operations[0].shader_links[0].to_node == "Principled BSDF"

    existing_only = SceneRecipe(operations=[{
        "op": "edit_material_graph",
        "name": "Existing Material",
        "shader_links": [{
            "from_node": "Noise Texture", "from_socket": "Fac",
            "to_node": "Math", "to_socket": "Value",
        }],
    }])
    assert not existing_only.operations[0].shader_nodes

    edited = SceneRecipe(operations=[{
        "op": "edit_material_graph", "name": "Existing Material",
        "shader_node_edits": [{
            "id": "Noise Texture", "x": 280, "y": -120,
            "inputs": {"Scale": 3.25},
        }],
    }])
    assert edited.operations[0].shader_node_edits[0].inputs["Scale"] == 3.25


def test_existing_material_graph_edit_rejects_unsafe_recipes():
    valid_link = {"from_node": "Node", "from_socket": "Value",
                  "to_node": "Principled BSDF", "to_socket": "Roughness"}
    invalid_recipes = [
        {"op": "edit_material_graph", "name": "Material"},
        {"op": "edit_material_graph", "name": "Material", "shader_nodes": [
            {"id": "Output", "type": "ShaderNodeOutputMaterial"}]},
        {"op": "edit_material_graph", "name": "Material", "shader_nodes": [
            {"id": "Node", "type": "ShaderNodeScript"}]},
        {"op": "edit_material_graph", "name": "Material", "shader_nodes": [
            {"id": "Node", "type": "ShaderNodeValue"}], "shader_links": [
            valid_link, valid_link]},
        {"op": "set_transform", "name": "Object", "shader_nodes": [
            {"id": "Node", "type": "ShaderNodeValue"}]},
        {"op": "edit_material_graph", "name": "Material", "shader_node_edits": [
            {"id": "Math"}]},
        {"op": "edit_material_graph", "name": "Material", "shader_node_edits": [
            {"id": "Math", "x": 100001}]},
        {"op": "edit_material_graph", "name": "Material", "shader_node_edits": [
            {"id": "Math", "blend_type": "INVALID"}]},
        {"op": "set_transform", "name": "Object", "shader_node_edits": [
            {"id": "Math", "x": 10}]},
    ]
    for operation in invalid_recipes:
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[operation])


@pytest.mark.parametrize("operation", [
    {"op": "execute_python", "code": "unsafe"},
    {"op": "delete", "actor_path": "Actor"},
    {"op": "transform", "actor_path": "Actor", "location": [float("nan"), 0, 0]},
])
def test_actor_recipe_rejects_execution_deletion_and_nonfinite_transforms(operation):
    with pytest.raises(ValidationError):
        ActorRecipe(operations=[operation])


def test_blueprint_flow_schema_rejects_unbounded_sequences_and_arbitrary_nodes():
    for node in (
        {"id": "node", "kind": "sequence", "name": "Order", "execution_outputs": 17},
        {"id": "node", "kind": "execute_python", "name": "Unsafe"},
    ):
        with pytest.raises(ValidationError):
            BlueprintRecipe(asset_path="/Game/Flow", nodes=[node])


def test_blueprint_gas_component_requires_explicit_supported_replication_mode():
    component = {
        "name": "AbilitySystemComponent",
        "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
        "replication_mode": "mixed",
    }
    setup_component = {
        "name": "GASSetup",
        "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
        "gas_setup": {"ability_system_component": "AbilitySystemComponent"},
    }
    recipe = BlueprintRecipe(
        asset_path="/Game/GAS/BP_Character", components=[component, setup_component]
    )
    assert recipe.components[0].replication_mode == "mixed"
    assert recipe.components[1].gas_setup.replication_mode == "mixed"

    with pytest.raises(ValidationError, match="requires a matching ForgeGameplayAbilitySetupComponent"):
        BlueprintRecipe(asset_path="/Game/GAS/BP_NoPersistentMode", components=[component])

    with pytest.raises(ValidationError, match="requires an explicit replication_mode"):
        BlueprintRecipe(asset_path="/Game/GAS/BP_NoMode", components=[{
            "name": "AbilitySystemComponent",
            "class_path": component["class_path"],
        }])
    with pytest.raises(ValidationError, match="supported only on AbilitySystemComponent"):
        BlueprintRecipe(asset_path="/Game/GAS/BP_WrongComponent", components=[{
            "name": "Mesh",
            "class_path": "/Script/Engine.StaticMeshComponent",
            "replication_mode": "mixed",
        }])
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path="/Game/GAS/BP_BadMode", components=[{
            **component, "replication_mode": "automatic",
        }])


def test_blueprint_gas_startup_setup_is_typed_bounded_and_bound_to_named_asc():
    recipe = BlueprintRecipe(
        asset_path="/Game/GAS/BP_Character",
        components=[
            {
                "name": "ASC",
                "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                "replication_mode": "mixed",
            },
            {
                "name": "GASSetup",
                "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
                "gas_setup": {
                    "ability_system_component": "ASC",
                    "initialize_owner_as_avatar": True,
                    "attribute_sets": ["/Game/Attributes/AS_Player.AS_Player_C"],
                    "startup_abilities": [
                        {"class_path": "/Game/Abilities/GA_Dash.GA_Dash_C", "level": 2, "input_id": 3}
                    ],
                    "startup_effects": [
                        {"class_path": "/Game/Effects/GE_Starting.GE_Starting_C", "level": 1.5}
                    ],
                },
            },
        ],
    )
    setup = recipe.components[1].gas_setup
    assert setup is not None
    assert setup.ability_system_component == "ASC"
    assert setup.startup_abilities[0].input_id == 3
    assert setup.startup_effects[0].level == 1.5
    assert setup.replication_mode == "mixed"


def test_blueprint_gas_setup_rejects_replication_mode_mismatch():
    with pytest.raises(ValidationError, match="must match its AbilitySystemComponent"):
        BlueprintRecipe(asset_path="/Game/GAS/BP_MismatchedMode", components=[
            {
                "name": "ASC",
                "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                "replication_mode": "mixed",
            },
            {
                "name": "GASSetup",
                "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
                "gas_setup": {"ability_system_component": "ASC", "replication_mode": "full"},
            },
        ])


def test_existing_blueprint_component_edit_inherits_new_asc_replication_mode():
    recipe = BlueprintEditRecipe(
        asset_path="/Game/GAS/BP_Existing",
        components=[
            {
                "name": "ASC",
                "class_path": "/Script/GameplayAbilities.AbilitySystemComponent",
                "replication_mode": "minimal",
            },
            {
                "name": "GASSetup",
                "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
                "gas_setup": {"ability_system_component": "ASC"},
            },
        ],
    )
    assert recipe.components[1].gas_setup.replication_mode == "minimal"


def test_blueprint_gas_startup_setup_rejects_missing_asc_and_duplicate_classes():
    setup_component = {
        "name": "GASSetup",
        "class_path": "/Script/MajesticForgeRuntime.ForgeGameplayAbilitySetupComponent",
        "gas_setup": {
            "startup_abilities": [
                {"class_path": "/Game/Abilities/GA_Dash.GA_Dash_C"},
                {"class_path": "/Game/Abilities/ga_dash.GA_Dash_C"},
            ]
        },
    }
    with pytest.raises(ValidationError, match="class paths must be unique"):
        BlueprintRecipe(asset_path="/Game/GAS/BP_Duplicate", components=[setup_component])
    with pytest.raises(ValidationError, match="must name one AbilitySystemComponent"):
        BlueprintRecipe(
            asset_path="/Game/GAS/BP_NoASC",
            components=[{
                **setup_component,
                "gas_setup": {"ability_system_component": "Missing"},
            }],
        )
    with pytest.raises(ValidationError):
        BlueprintRecipe(
            asset_path="/Game/GAS/BP_BadPath",
            components=[{
                **setup_component,
                "gas_setup": {"startup_abilities": [{"class_path": "/Game/../GA_Bad.GA_Bad_C"}]},
            }],
        )


def test_blueprint_functions_accept_typed_signatures_and_explicit_graph_terminators():
    recipe = BlueprintRecipe(
        asset_path="/Game/Combat/BP_DamageMath",
        functions=[
            "LegacyEmptyFunction",
            {
                "name": "ComputeDamage",
                "inputs": [
                    {"name": "BaseDamage", "type": "float"},
                    {"name": "Multiplier", "type": "float"},
                ],
                "outputs": [{"name": "Damage", "type": "float"}],
                "pure": True,
            },
        ],
        nodes=[
            {"id": "entry", "kind": "function_entry", "name": "Entry",
             "graph": "ComputeDamage"},
            {"id": "return", "kind": "function_result", "name": "Return",
             "graph": "ComputeDamage"},
        ],
        connections=[
            {"graph": "ComputeDamage", "from_node": "entry", "from_pin": "BaseDamage",
             "to_node": "return", "to_pin": "Damage"},
        ],
    )

    assert recipe.functions[0] == "LegacyEmptyFunction"
    signature = recipe.functions[1]
    assert not isinstance(signature, str)
    assert signature.name == "ComputeDamage"
    assert signature.inputs[0].type == "float"
    assert signature.outputs[0].name == "Damage"
    assert signature.pure


def test_blueprint_function_signatures_reject_conflicts_and_unsafe_graph_references():
    with pytest.raises(ValidationError, match="parameter names must be unique"):
        BlueprintRecipe(asset_path="/Game/BadFunction", functions=[{
            "name": "Compute",
            "inputs": [{"name": "Value", "type": "float"}],
            "outputs": [{"name": "value", "type": "float"}],
        }])

    with pytest.raises(ValidationError, match="Function names must be unique"):
        BlueprintRecipe(asset_path="/Game/BadFunction", functions=[
            "Compute", {"name": "compute"},
        ])

    with pytest.raises(ValidationError, match="declared function graph"):
        BlueprintRecipe(asset_path="/Game/BadFunction", nodes=[
            {"id": "entry", "kind": "function_entry", "name": "Entry",
             "graph": "MissingFunction"},
        ])

    with pytest.raises(ValidationError, match="function added in this edit"):
        BlueprintEditRecipe(asset_path="/Game/Existing", nodes=[
            {"id": "entry", "kind": "function_entry", "name": "Entry",
             "graph": "Compute"},
        ])


def test_existing_blueprint_edit_accepts_new_typed_function_signatures():
    recipe = BlueprintEditRecipe(asset_path="/Game/Existing", functions=[{
        "name": "Compute",
        "inputs": [{"name": "Value", "type": "float"}],
        "outputs": [{"name": "Result", "type": "float"}],
        "pure": True,
    }], nodes=[
        {"id": "entry", "kind": "function_entry", "name": "Entry", "graph": "Compute"},
        {"id": "return", "kind": "function_result", "name": "Return", "graph": "Compute"},
    ], connections=[{
        "graph": "Compute", "from_node": "entry", "from_pin": "Value",
        "to_node": "return", "to_pin": "Result",
    }])
    assert recipe.functions[0].name == "Compute"
    assert len(recipe.nodes) == 2 and len(recipe.connections) == 1

    with pytest.raises(ValidationError, match="Function names must be unique"):
        BlueprintEditRecipe(asset_path="/Game/Existing", functions=[
            {"name": "Compute"}, {"name": "compute"},
        ])

    with pytest.raises(ValidationError, match="conflict with new variables"):
        BlueprintEditRecipe(asset_path="/Game/Existing", variables=[{
            "name": "Compute", "type": "float",
        }], functions=[{"name": "Compute"}])


def test_blueprint_function_signatures_are_bounded_and_typed():
    too_many_inputs = [{"name": f"Arg{index}", "type": "int"} for index in range(17)]
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path="/Game/TooManyPins", functions=[{
            "name": "Compute", "inputs": too_many_inputs,
        }])
    with pytest.raises(ValidationError):
        BlueprintRecipe(asset_path="/Game/BadPinType", functions=[{
            "name": "Compute", "inputs": [{"name": "Code", "type": "python"}],
        }])
    with pytest.raises(ValidationError, match="Pure functions must declare at least one output"):
        BlueprintRecipe(asset_path="/Game/PureWithoutOutput", functions=[{
            "name": "Compute", "inputs": [{"name": "Value", "type": "float"}],
            "pure": True,
        }])


def test_existing_blueprint_edit_can_add_and_wire_bounded_nodes_by_guid_or_recipe_id():
    recipe = BlueprintEditRecipe(
        asset_path="/Game/Flow",
        variables=[{"name": "Speed", "type": "float", "default": "2.5"}],
        components=[{"name": "Mesh", "class_path": "/Script/Engine.StaticMeshComponent"}],
        nodes=[{"id": "sequence", "kind": "sequence", "name": "Order",
                "execution_outputs": 3}],
        connections=[
            {"graph": "EventGraph", "from_node": "A1B2-C3D4", "from_pin": "then",
             "to_node": "sequence", "to_pin": "execute"},
        ],
    )
    assert recipe.nodes[0].execution_outputs == 3
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Flow")
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Flow", nodes=[
            {"id": "same", "kind": "branch", "name": "A"},
            {"id": "same", "kind": "branch", "name": "B"},
        ])
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Flow", variables=[
            {"name": "Speed", "type": "float"}, {"name": "Speed", "type": "int"},
        ])
