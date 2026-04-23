"""Tests for click-recipe model and loader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ez_ax.config.click_recipe import ClickRecipe, load_click_recipe
from ez_ax.models.errors import ConfigError


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
    with pytest.raises(ConfigError) as exc_info:
        load_click_recipe(path)
    assert "not valid JSON" in str(exc_info.value)


def test_load_click_recipe_wrong_schema_raises_config_error(tmp_path: Path) -> None:
    path = tmp_path / "recipe.json"
    path.write_text(
        json.dumps({"missions": {"click_dispatch": {"x": "not-an-int", "y": 200}}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as exc_info:
        load_click_recipe(path)
    assert "does not match schema" in str(exc_info.value)
