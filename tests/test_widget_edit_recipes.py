import pytest
from pydantic import ValidationError

from server.core.recipes import BlueprintEditRecipe


def test_exact_text_widget_hide_is_an_independent_bounded_edit():
    recipe = BlueprintEditRecipe(asset_path="/Game/Nav/Widget", widgets=[
        {"name": "LegacyDistanceText", "action": "hide_text"},
    ])
    assert recipe.widgets[0].action == "hide_text"


@pytest.mark.parametrize("widgets", [
    [{"name": "Text", "action": "delete"}],
    [{"name": "Text", "action": "hide_text", "script": "run"}],
    [{"name": "../Text", "action": "hide_text"}],
    [{"name": "Text", "action": "hide_text"}, {"name": "text", "action": "hide_text"}],
    [{"name": f"Text{i}", "action": "hide_text"} for i in range(33)],
])
def test_widget_edit_rejects_unknown_actions_fields_paths_duplicates_and_excess(widgets):
    with pytest.raises(ValidationError):
        BlueprintEditRecipe(asset_path="/Game/Nav/Widget", widgets=widgets)
