"""Acceptance tests — the full agent workflow as OpenClaw would execute it.

These tests prove the documented contract in docs/recipe-guide.md:
  1. Agent writes a YAML (or JSON) recipe file.
  2. Agent invokes the coord-smith CLI with --click-recipe.
  3. CLI exits 0.
  4. Artifacts directory contains the expected evidence files.
  5. Action-log JSONL records are valid and contain the required fields.

pyautogui is mocked at the OS level so the tests are deterministic and
require no macOS Accessibility / Screen Recording permission.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run, main


def _fake_screenshot() -> Image.Image:
    return Image.new("RGB", (800, 600), color="white")


_FakeSize = type("Point", (), {"width": 1920, "height": 1080})
_FakePos = type("Point", (), {"x": 400, "y": 300})

_COMMON_ARGV = [
    "--session-ref", "agent-acceptance-test",
    "--expected-auth-state", "authenticated",
    "--target-page-url", "https://tickets.interpark.com/goods/26003199",
    "--site-identity", "interpark",
]


def _find_action_log_dir(base_dir: Path) -> Path:
    """Locate the action-log directory inside the run artifact tree."""
    candidates = list(base_dir.glob("artifacts/runs/*/artifacts/action-log"))
    assert candidates, f"No action-log directory found under {base_dir}"
    return candidates[0]


def _read_last_jsonl(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])


@pytest.mark.asyncio
async def test_yaml_coord_recipe_exits_0_and_writes_artifacts(tmp_path: Path) -> None:
    """Agent writes a coord YAML recipe → CLI exits 0 → artifacts exist."""
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 400\n    y: 300\n",
        encoding="utf-8",
    )

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click"),
        patch("pyautogui.position", return_value=_FakePos()),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        exit_code = await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )

    assert exit_code == 0

    action_log = _find_action_log_dir(tmp_path)
    assert (action_log / "click-dispatched.jsonl").exists(), "click evidence missing"
    assert (action_log / "release-ceiling-stop.jsonl").exists(), "ceiling-stop proof missing"

    stop = _read_last_jsonl(action_log / "release-ceiling-stop.jsonl")
    assert stop["event"] == "release-ceiling-stop"
    assert stop["mission_name"] == "run_completion"
    assert isinstance(stop["ts"], str) and stop["ts"]


@pytest.mark.asyncio
async def test_yaml_recipe_screenshots_written_to_artifacts(tmp_path: Path) -> None:
    """Screenshots are written alongside action-logs for each mission."""
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 400\n    y: 300\n",
        encoding="utf-8",
    )

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click"),
        patch("pyautogui.position", return_value=_FakePos()),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )

    screenshots = list(tmp_path.glob("artifacts/runs/*/artifacts/screenshot/*.png"))
    assert screenshots, "no screenshots written to artifacts/"


@pytest.mark.asyncio
async def test_no_recipe_exits_0_no_click_dispatched(tmp_path: Path) -> None:
    """Omitting --click-recipe runs the pipeline without clicking."""
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click") as mock_click,
    ):
        exit_code = await _run(argv=_COMMON_ARGV, base_dir=tmp_path)

    assert exit_code == 0
    mock_click.assert_not_called()

    action_log = _find_action_log_dir(tmp_path)
    assert (action_log / "release-ceiling-stop.jsonl").exists()


def test_invalid_yaml_recipe_exits_3(tmp_path: Path) -> None:
    """A malformed YAML recipe must produce exit code 3 (ConfigError)."""
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text("missions: [\nunclosed", encoding="utf-8")

    exit_code = main(argv=["--click-recipe", str(recipe), *_COMMON_ARGV])

    assert exit_code == 3


def test_missing_recipe_file_exits_3(tmp_path: Path) -> None:
    """A non-existent recipe path must produce exit code 3 (ConfigError)."""
    missing = tmp_path / "ghost.yaml"

    exit_code = main(argv=["--click-recipe", str(missing), *_COMMON_ARGV])

    assert exit_code == 3


@pytest.mark.asyncio
async def test_action_log_jsonl_fields_are_complete(tmp_path: Path) -> None:
    """Every action-log record must contain ts, mission_name, and event fields."""
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 400\n    y: 300\n",
        encoding="utf-8",
    )

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click"),
        patch("pyautogui.position", return_value=_FakePos()),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )

    for jsonl_path in _find_action_log_dir(tmp_path).glob("*.jsonl"):
        record = _read_last_jsonl(jsonl_path)
        assert "ts" in record, f"{jsonl_path.name}: missing 'ts'"
        assert "mission_name" in record, f"{jsonl_path.name}: missing 'mission_name'"
        assert "event" in record, f"{jsonl_path.name}: missing 'event'"
