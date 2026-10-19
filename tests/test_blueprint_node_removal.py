import pytest
from pydantic import ValidationError

from server.core.recipes import BlueprintEditRecipe


def test_exact_node_removal_reaches_native_preview():
    recipe = BlueprintEditRecipe(asset_path="/Game/Nav/Widget", operations=[
        {"op": "remove", "graph": "Get Distance Text", "node_id": "A" * 32},
    ])
    assert recipe.operations[0].op == "remove"


@pytest.mark.parametrize("op", ["delete_graph", "execute", "eval"])
def test_unknown_destructive_operations_are_rejected(op):
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Widget", operations=[
            {"op": op, "graph": "Get Distance Text", "node_id": "A" * 32},
        ])
