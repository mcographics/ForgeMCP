import pytest
from pydantic import ValidationError

from server.core.recipes import ActorRecipe, BlueprintEditRecipe, BlueprintRecipe, SceneRecipe


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

    with pytest.raises(ValidationError, match="only in new Blueprint recipes"):
        BlueprintEditRecipe(asset_path="/Game/Existing", nodes=[
            {"id": "entry", "kind": "function_entry", "name": "Entry",
             "graph": "Compute"},
        ])


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
