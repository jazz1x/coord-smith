"""Tests for click-recipe model and loader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from coord_smith.config.click_recipe import (
    ClickRecipe,
    MissionClick,
    MissionImageClick,
    load_click_recipe,
)
from coord_smith.models.errors import ConfigError


def _make_template(path: Path, *, color: str = "red", size: tuple[int, int] = (32, 32)) -> Path:
    Image.new("RGB", size, color=color).save(path)
    return path


def test_click_recipe_coords_for_known_mission(tmp_path: Path) -> None:
    recipe = ClickRecipe.model_validate(
        {"version": 1, "missions": {"click_dispatch": {"x": 500, "y": 400}}}
    )
    assert recipe.coords_for("click_dispatch") == (500, 400)


def test_click_recipe_coords_for_unknown_mission_returns_none() -> None:
    recipe = ClickRecipe()
    assert recipe.coords_for("click_dispatch") is None


def test_load_click_recipe_from_json(tmp_path: Path) -> None:
    path = tmp_path / "recipe.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "missions": {
                    "click_dispatch": {"x": 100, "y": 200},
                    "success_observation": {"x": 300, "y": 400},
                },
            }
        ),
        encoding="utf-8",
    )
    recipe = load_click_recipe(path)
    assert recipe.coords_for("click_dispatch") == (100, 200)
    assert recipe.coords_for("success_observation") == (300, 400)


def test_load_click_recipe_missing_file_raises_config_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_click_recipe(tmp_path / "missing.json")
    assert "not found" in str(exc_info.value)


def test_load_click_recipe_invalid_json_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "recipe.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError, match="could not be parsed"):
        load_click_recipe(path)


def test_load_click_recipe_wrong_schema_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "recipe.json"
    path.write_text(
        json.dumps({"missions": {"click_dispatch": {"x": "not-an-int", "y": 200}}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc_info:
        load_click_recipe(path)
    assert "does not match schema" in str(exc_info.value)


def test_image_target_validates_with_defaults() -> None:
    target = MissionImageClick.model_validate({"image": "templates/buy.png"})
    assert target.image == "templates/buy.png"
    assert target.confidence == 0.9
    assert target.region is None
    assert target.grayscale is False


def test_image_target_rejects_confidence_above_one() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MissionImageClick.model_validate({"image": "x.png", "confidence": 1.5})


def test_image_target_rejects_negative_confidence() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MissionImageClick.model_validate({"image": "x.png", "confidence": -0.1})


def test_recipe_resolves_image_target_via_image_target_for(tmp_path: Path) -> None:
    template = _make_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "image": str(template),
                    "confidence": 0.85,
                    "grayscale": True,
                },
            },
        }
    )
    image_target = recipe.image_target_for("click_dispatch")
    assert image_target is not None
    assert image_target.image == str(template)
    assert image_target.confidence == 0.85
    assert image_target.grayscale is True
    # coord-only accessor returns None for an image target
    assert recipe.coords_for("click_dispatch") is None


def test_recipe_coord_target_does_not_match_image_accessor(tmp_path: Path) -> None:
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 100, "y": 200}}}
    )
    assert recipe.coords_for("click_dispatch") == (100, 200)
    assert recipe.image_target_for("click_dispatch") is None


def test_recipe_supports_mixed_coord_and_image_targets(tmp_path: Path) -> None:
    template = _make_template(tmp_path / "buy.png")
    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "armed_state_entry": {"x": 50, "y": 60},
                "click_dispatch": {"image": str(template)},
            },
        }
    )
    assert recipe.coords_for("armed_state_entry") == (50, 60)
    assert recipe.image_target_for("click_dispatch") is not None
    assert recipe.coords_for("click_dispatch") is None


def test_load_click_recipe_resolves_image_path_relative_to_recipe(
    tmp_path: Path,
) -> None:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template = _make_template(template_dir / "buy.png")
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "version": 1,
                "missions": {
                    "click_dispatch": {"image": "templates/buy.png"},
                },
            }
        ),
        encoding="utf-8",
    )
    recipe = load_click_recipe(recipe_path)
    image_target = recipe.image_target_for("click_dispatch")
    assert image_target is not None
    assert Path(image_target.image) == template.resolve()


def test_load_click_recipe_preserves_absolute_image_path(tmp_path: Path) -> None:
    template = _make_template(tmp_path / "buy.png").resolve()
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {"missions": {"click_dispatch": {"image": str(template)}}},
        ),
        encoding="utf-8",
    )
    recipe = load_click_recipe(recipe_path)
    image_target = recipe.image_target_for("click_dispatch")
    assert image_target is not None
    assert Path(image_target.image) == template


def test_load_click_recipe_raises_when_template_missing(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {"missions": {"click_dispatch": {"image": "templates/missing.png"}}}
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc_info:
        load_click_recipe(recipe_path)
    assert "missing click template" in str(exc_info.value)


def test_mission_click_remains_unaffected_by_union_resolution() -> None:
    """Coord target must resolve to MissionClick, not MissionImageClick."""
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": 1, "y": 2}}}
    )
    entry = recipe.missions["click_dispatch"]
    assert isinstance(entry, MissionClick)


def test_load_click_recipe_resolves_post_click_signal_path(tmp_path: Path) -> None:
    template = _make_template(tmp_path / "signal.png")
    click_template = _make_template(tmp_path / "buy.png")
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "missions": {
                    "click_dispatch": {
                        "image": "buy.png",
                        "post_click_signal": {"image": "signal.png", "timeout": 3.0},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    recipe = load_click_recipe(recipe_path)
    entry = recipe.image_target_for("click_dispatch")
    assert entry is not None
    assert Path(entry.image) == click_template.resolve()
    assert entry.post_click_signal is not None
    assert Path(entry.post_click_signal.image) == template.resolve()


def test_load_click_recipe_raises_when_post_click_signal_template_missing(
    tmp_path: Path,
) -> None:
    click_template = _make_template(tmp_path / "buy.png")
    recipe_path = tmp_path / "recipe.json"
    recipe_path.write_text(
        json.dumps(
            {
                "missions": {
                    "click_dispatch": {
                        "image": str(click_template),
                        "post_click_signal": {"image": "missing-signal.png"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="post-click signal"):
        load_click_recipe(recipe_path)


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def test_load_click_recipe_from_yaml_coord(tmp_path: Path) -> None:
    path = tmp_path / "recipe.yaml"
    path.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 150\n    y: 250\n",
        encoding="utf-8",
    )
    recipe = load_click_recipe(path)
    assert recipe.coords_for("click_dispatch") == (150, 250)


def test_load_click_recipe_from_yml_extension(tmp_path: Path) -> None:
    path = tmp_path / "recipe.yml"
    path.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 10\n    y: 20\n",
        encoding="utf-8",
    )
    recipe = load_click_recipe(path)
    assert recipe.coords_for("click_dispatch") == (10, 20)


def test_load_click_recipe_from_yaml_image(tmp_path: Path) -> None:
    template = _make_template(tmp_path / "btn.png")
    path = tmp_path / "recipe.yaml"
    path.write_text(
        f"version: 1\nmissions:\n  click_dispatch:\n    image: {template}\n    confidence: 0.85\n",
        encoding="utf-8",
    )
    recipe = load_click_recipe(path)
    target = recipe.image_target_for("click_dispatch")
    assert target is not None
    assert target.confidence == pytest.approx(0.85)


def test_load_click_recipe_invalid_yaml_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "recipe.yaml"
    path.write_text("missions: [\nunclosed bracket", encoding="utf-8")
    with pytest.raises(ConfigError, match="could not be parsed"):
        load_click_recipe(path)
