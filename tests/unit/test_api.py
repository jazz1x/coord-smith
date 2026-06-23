"""Unit tests for the public Python API (coord_smith.run_click_recipe)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from coord_smith import run_click_recipe_sync
from coord_smith.config.click_recipe import ClickRecipe, Step, StepCoord

# ---------------------------------------------------------------------------
# dry-run paths: no OS permissions required
# ---------------------------------------------------------------------------


def test_api_dry_run_with_dict_recipe(tmp_path: Path) -> None:
    recipe = {
        "version": 1,
        "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}],
    }
    result = run_click_recipe_sync(
        recipe=recipe,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.status == "success"
    assert result.step_count == 1
    assert result.run_id is None  # dry-run creates no run root
    assert result.run_json_path.exists()
    data = json.loads(result.run_json_path.read_text(encoding="utf-8"))
    assert data["status"] == "success"
    assert data["exit_code"] == 0
    assert data["step_count"] == 1
    assert data["failure"] is None


def test_api_dry_run_with_yaml_string(tmp_path: Path) -> None:
    recipe_yaml = yaml.safe_dump(
        {
            "version": 1,
            "steps": [{"name": "click-buy", "coord": {"x": 100, "y": 200}}],
        }
    )
    result = run_click_recipe_sync(
        recipe=recipe_yaml,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.status == "success"
    assert result.step_count == 1


def test_api_dry_run_with_click_recipe_model(tmp_path: Path) -> None:
    recipe = ClickRecipe(
        steps=[Step(name="click-buy", coord=StepCoord(x=300, y=400))]
    )
    result = run_click_recipe_sync(
        recipe=recipe,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.status == "success"
    assert result.step_count == 1


def test_api_dry_run_with_recipe_file(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "steps": [{"name": "click-buy", "coord": {"x": 500, "y": 600}}],
            }
        ),
        encoding="utf-8",
    )
    result = run_click_recipe_sync(
        recipe=recipe_path,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 0
    assert result.step_count == 1


def test_api_dry_run_invalid_input_returns_exit_3(tmp_path: Path) -> None:
    recipe = {
        "version": 1,
        "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}],
    }
    result = run_click_recipe_sync(
        recipe=recipe,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="",  # invalid
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 3
    assert result.status == "failure"
    assert result.run_json_path.exists()


def test_api_dry_run_invalid_recipe_returns_exit_3(tmp_path: Path) -> None:
    recipe = {"version": 1, "steps": [{"name": "click-buy"}]}  # no target
    result = run_click_recipe_sync(
        recipe=recipe,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    assert result.exit_code == 3
    assert result.status == "failure"


def test_api_run_result_to_dict_matches_run_json(tmp_path: Path) -> None:
    recipe = {
        "version": 1,
        "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}],
    }
    result = run_click_recipe_sync(
        recipe=recipe,
        session_ref="demo",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        dry_run=True,
        base_dir=tmp_path,
    )
    disk = json.loads(result.run_json_path.read_text(encoding="utf-8"))
    assert result.to_dict() == disk
