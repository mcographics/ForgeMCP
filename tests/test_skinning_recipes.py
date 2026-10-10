import pytest
from pydantic import ValidationError

from server.core.recipes import SceneRecipe


def operation(weights):
    return {"op":"bind_mesh","name":"SkinCopy","source":"Cube","armature":"Rig","weights":weights}


def test_normalized_explicit_skin_recipe():
    recipe = SceneRecipe(operations=[operation([
        {"vertex":0,"bone":"Root","weight":0.75},
        {"vertex":0,"bone":"Child","weight":0.25},
    ])])
    assert recipe.operations[0].weights[1].weight == 0.25


def test_partial_skin_patch_supports_large_indices_with_bounded_edits():
    op = {**operation([{"vertex":300,"bone":"Root","weight":1.0}]),
          "op":"patch_skin_weights"}
    assert SceneRecipe(operations=[op]).operations[0].weights[0].vertex == 300
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{**op,"weights":[
            {"vertex":index,"bone":"Root","weight":1.0} for index in range(129)
        ]}])


def test_reviewed_ik_spec_requires_bounded_explicit_chain():
    op = {"op":"create_ik_constraint","name":"Rig","ik":{
        "bone":"Tip","constraint":"ForgeIK","target":"Target","chain_count":2}}
    assert SceneRecipe(operations=[op]).operations[0].ik.iterations == 64
    for spec in ({**op["ik"],"chain_count":True},{**op["ik"],"chain_count":0},
                 {**op["ik"],"chain_count":17},{**op["ik"],"iterations":257},
                 {**op["ik"],"target":"../Target"}):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[{**op,"ik":spec}])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op":"create_ik_constraint","name":"Rig"}])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{**op,"op":"set_transform"}])


def test_pole_ik_requires_distinct_control_finite_angle_and_chain():
    spec = {"bone":"Tip","constraint":"ForgeIK","target":"Target","chain_count":2,
            "pole_target":"Pole","pole_angle":0.5}
    op = {"op":"create_ik_constraint","name":"Rig","ik":spec}
    assert SceneRecipe(operations=[op]).operations[0].ik.pole_angle == 0.5
    for invalid in ({**spec,"pole_target":"Target"},{**spec,"chain_count":1},
                    {**spec,"pole_angle":True},{**spec,"pole_angle":float("nan")},
                    {**spec,"pole_angle":4.0},{**spec,"pole_target":None}):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[{**op,"ik":invalid}])


def test_timeline_frame_is_strict_bounded_and_scene_scoped():
    assert SceneRecipe(operations=[{"op":"set_frame","frame":20}]).operations[0].frame == 20
    for frame in (True,"20",20.5,100001,-100001):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[{"op":"set_frame","frame":frame}])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op":"set_frame","frame":20,"name":"Cube"}])


def test_object_keyframe_explicit_value_requires_valid_channel_vector():
    op = {"op":"keyframe","name":"Control","data_path":"location","frame":20,"value":[1,2,3]}
    assert SceneRecipe(operations=[op]).operations[0].value == [1,2,3]
    for invalid in ({**op,"value":1.0},{**op,"value":[1,2,3,4]},
                    {**op,"data_path":"scale","value":[1,0,1]}):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])


def test_reweight_recipe_uses_the_same_normalized_contract():
    op = {**operation([{"vertex":0,"bone":"Root","weight":1.0}]),"op":"reweight_mesh"}
    assert SceneRecipe(operations=[op]).operations[0].op == "reweight_mesh"
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{**op,"weights":[{"vertex":0,"bone":"Root","weight":0.5}]}])


@pytest.mark.parametrize("weights", [
    [], [{"vertex":0,"bone":"Root","weight":0.5}],
    [{"vertex":0,"bone":"Root","weight":0.5}]*2,
    [{"vertex":0,"bone":f"Bone{index}","weight":0.2} for index in range(5)],
    [{"vertex":True,"bone":"Root","weight":1}],
    [{"vertex":0,"bone":"Root","weight":True}],
    [{"vertex":128,"bone":"Root","weight":1}],
    [{"vertex":0,"bone":"Root","weight":float("nan")}],
])
def test_invalid_skin_recipe_rejected(weights):
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[operation(weights)])


def test_skin_fields_cannot_be_added_to_other_operations():
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{"op":"set_transform","name":"Cube","armature":"Rig"}])


def test_automatic_skinning_requires_explicit_method_and_no_weights():
    op = {"op":"auto_bind_mesh","name":"AutoSkin","source":"Sphere","armature":"Rig",
          "weight_method":"blender_heat_top4"}
    assert SceneRecipe(operations=[op]).operations[0].weight_method == "blender_heat_top4"
    for invalid in ({**op,"weight_method":""}, {**op,"weight_method":"execute_python"},
                    {**op,"weights":[{"vertex":0,"bone":"Root","weight":1.0}]}):
        with pytest.raises(ValidationError):
            SceneRecipe(operations=[invalid])
    with pytest.raises(ValidationError):
        SceneRecipe(operations=[{**op,"op":"bind_mesh"}])
