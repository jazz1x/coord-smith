"""Unit tests for missions↔steps normalization + backwards-compat regression.

Validates the deprecation path documented in
docs/prd-multi-step-flow-recipe.md §2.4 D3:

* legacy ``missions: {name: target}`` recipes are still accepted and
  auto-normalize to ``steps: [Step]``;
* ``steps:`` recipes pass through unchanged;
* a recipe declaring both shapes warns and uses ``steps`` as truth;
* the three existing fixture recipes under ``docs/recipes/`` continue to
  load to a single-step recipe (N=1) without manual migration.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml

from coord_smith.config.click_recipe import (
    ClickRecipe,
    MissionClick,
    MissionImageClick,
    Step,
    StepCoord,
)

# ---- legacy shape: missions: {name: target} → auto-normalize to steps -----


def test_legacy_missions_dict_normalizes_to_steps() -> None:
    """A legacy recipe with one MissionClick produces one equivalent Step."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe(
            missions={"click_dispatch": MissionClick(x=400, y=300)}
        )
    assert recipe.steps is not None
    assert len(recipe.steps) == 1
    s = recipe.steps[0]
    assert s.name == "click_dispatch"
    assert s.coord == StepCoord(x=400, y=300)
    assert s.image is None
    assert s.prefer == "coord"


def test_legacy_image_mission_normalizes_to_image_step() -> None:
    """A legacy MissionImageClick translates to a Step with image fields preserved."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe(
            missions={
                "click_dispatch": MissionImageClick(
                    image="templates/buy.png",
                    confidence=0.85,
                    region=(0, 100, 1920, 800),
                    grayscale=True,
                )
            }
        )
    s = recipe.steps[0]
    assert s.image == "templates/buy.png"
    assert s.confidence == 0.85
    assert s.region == (0, 100, 1920, 800)
    assert s.grayscale is True
    assert s.prefer == "image"


def test_legacy_normalization_emits_deprecation_warning() -> None:
    """A legacy recipe emits exactly one DeprecationWarning on construction."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ClickRecipe(missions={"click_dispatch": MissionClick(x=1, y=2)})
        deprecation = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation) == 1
        assert "auto-normalizing to 'steps'" in str(deprecation[0].message)


def test_legacy_missions_remain_populated_after_normalize() -> None:
    """Backwards-compat: callers reading recipe.missions[name] keep working."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe(
            missions={"click_dispatch": MissionClick(x=10, y=20)}
        )
    assert recipe.missions is not None
    assert "click_dispatch" in recipe.missions
    assert recipe.missions["click_dispatch"].x == 10  # type: ignore[union-attr]


# ---- new shape: steps: [...] passes through ------------------------------


def test_steps_only_recipe_passes_through_unchanged() -> None:
    """A recipe declaring only steps does not trigger any deprecation warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        recipe = ClickRecipe(
            steps=[Step(name="click_dispatch", coord=StepCoord(x=1, y=2))]
        )
        deprecation = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation) == 0
    assert recipe.steps is not None
    assert len(recipe.steps) == 1
    assert recipe.missions == {}  # default empty


# ---- both shapes declared: warn + steps wins -----------------------------


def test_both_shapes_declared_warns_and_uses_steps() -> None:
    """A recipe with both steps and missions warns and treats steps as truth."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        recipe = ClickRecipe(
            steps=[Step(name="from_steps", coord=StepCoord(x=1, y=2))],
            missions={"from_missions": MissionClick(x=99, y=99)},
        )
        deprecation = [
            x for x in w if issubclass(x.category, DeprecationWarning)
        ]
        assert len(deprecation) == 1
        assert "'steps' is the source of truth" in str(deprecation[0].message)
    assert recipe.steps is not None
    assert recipe.steps[0].name == "from_steps"


# ---- empty recipe: no clicks, no error -----------------------------------


def test_empty_recipe_is_valid_no_click_smoke_target() -> None:
    """An empty ClickRecipe is a valid no-click smoke target (regression)."""
    recipe = ClickRecipe()
    assert recipe.steps is None
    assert recipe.missions == {}


# ---- backwards-compat: existing fixture recipes still load ---------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "coord-click.yaml",
        "image-click.yaml",
        "image-click-with-signal.yaml",
    ],
)
def test_existing_fixture_recipes_normalize_to_single_step(
    fixture_name: str,
) -> None:
    """Each existing docs/recipes/*.yaml normalizes to exactly one Step."""
    fixture = Path("docs/recipes") / fixture_name
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe.model_validate(data)
    assert recipe.steps is not None
    assert len(recipe.steps) == 1
    step = recipe.steps[0]
    assert step.name == "click_dispatch"
    # Must declare exactly one of image / coord (recipe authors haven't yet
    # adopted the dual-target multi-step shape).
    has_image = step.image is not None
    has_coord = step.coord is not None
    assert has_image ^ has_coord, (
        f"{fixture_name} step should declare exactly one target type"
    )


def test_coord_recipe_step_has_correct_coord() -> None:
    """coord-click.yaml carries (800, 500)."""
    fixture = Path("docs/recipes/coord-click.yaml")
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe.model_validate(data)
    step = recipe.steps[0]
    assert step.coord is not None
    assert (step.coord.x, step.coord.y) == (800, 500)


def test_image_with_signal_recipe_carries_post_click_signal() -> None:
    """image-click-with-signal.yaml propagates post_click_signal into the Step."""
    fixture = Path("docs/recipes/image-click-with-signal.yaml")
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe.model_validate(data)
    step = recipe.steps[0]
    assert step.post_click_signal is not None
    assert step.post_click_signal.image  # path resolution may not run on raw model_validate


# ---- multi-step example recipes: schema-smoke ----------------------------


@pytest.mark.parametrize(
    "fixture_name,expected_step_count",
    [
        ("multi-step-flow.yaml", 3),
        ("multi-step-with-fallback.yaml", None),  # count not pinned
        ("multi-step-with-wait-for.yaml", 3),
        ("datepicker-pattern.yaml", None),  # count not pinned
    ],
)
def test_multi_step_example_recipes_parse(
    fixture_name: str, expected_step_count: int | None
) -> None:
    """Each docs/recipes/multi-step*.yaml parses to a valid ClickRecipe.

    This guards against drift: a recipe checked into the public examples
    directory must remain a valid coord-smith recipe even as the schema
    evolves. The check is schema-only (no template-existence check) so
    the YAML files can reference symbolic paths.
    """
    fixture = Path("docs/recipes") / fixture_name
    assert fixture.is_file(), f"missing example recipe: {fixture}"
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe.model_validate(data)
    assert recipe.steps is not None and len(recipe.steps) > 0, (
        f"{fixture_name} must declare at least one step"
    )
    if expected_step_count is not None:
        assert len(recipe.steps) == expected_step_count


def test_wait_for_example_recipe_uses_wait_for_field() -> None:
    """multi-step-with-wait-for.yaml must actually exercise the wait_for
    field on at least one step — otherwise the example doesn't deliver
    on its filename promise."""
    fixture = Path("docs/recipes/multi-step-with-wait-for.yaml")
    data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe.model_validate(data)
    assert recipe.steps is not None
    assert any(step.wait_for is not None for step in recipe.steps), (
        "multi-step-with-wait-for.yaml must have at least one step with "
        "a populated wait_for field"
    )
    assert any(step.settle_ms != 300 for step in recipe.steps), (
        "multi-step-with-wait-for.yaml must demonstrate settle_ms tuning "
        "(at least one step overrides the 300 ms default) so readers see "
        "the knob in action"
    )


# ---- coords_for / image_target_for legacy helpers preserved --------------


def test_coords_for_returns_coord_for_step_with_coord() -> None:
    """The coords_for helper still works against the normalized step list."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe(
            missions={"click_dispatch": MissionClick(x=400, y=300)}
        )
    assert recipe.coords_for("click_dispatch") == (400, 300)
    assert recipe.coords_for("unknown") is None


def test_image_target_for_returns_image_config_for_image_step() -> None:
    """The image_target_for helper rebuilds a MissionImageClick from a Step."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = ClickRecipe(
            missions={
                "click_dispatch": MissionImageClick(
                    image="x.png",
                    confidence=0.8,
                    region=(0, 0, 100, 100),
                )
            }
        )
    target = recipe.image_target_for("click_dispatch")
    assert target is not None
    assert target.image == "x.png"
    assert target.confidence == 0.8
    assert target.region == (0, 0, 100, 100)
