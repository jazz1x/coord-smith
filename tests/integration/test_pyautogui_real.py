"""Real-binary integration tests for PyAutoGUIAdapter.

These tests invoke pyautogui without mocks. They require:
- macOS Accessibility permission for the host terminal app (mouse control)
- macOS Screen Recording permission for the host terminal app (screenshot)
- A real display (not headless CI)

Marker: `real`. Default pytest invocation skips them (`addopts = -m 'not real'`
in pyproject.toml). Run with `uv run pytest -m real` on a permission-granted
local machine.
"""
from __future__ import annotations

from pathlib import Path

import pyautogui
import pytest

from ez_ax.adapters.execution.client import ExecutionRequest
from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.config.click_recipe import ClickRecipe

pytestmark = pytest.mark.real


def test_preflight_succeeds_on_permission_granted_host() -> None:
    """preflight() must return without raising when permissions are granted."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        adapter = PyAutoGUIAdapter(run_root=Path(tmp))
        adapter.preflight()  # raises on permission failure; silence = pass


def test_screenshot_produces_real_png_file(tmp_path: Path) -> None:
    """_capture_screenshot must write a valid PNG (magic bytes 89 50 4e 47)."""
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    adapter._capture_screenshot("real-integration-smoke")

    path = tmp_path / "artifacts" / "screenshot" / "real-integration-smoke.png"
    assert path.is_file(), f"screenshot not written at {path}"
    assert path.stat().st_size > 1000, "screenshot suspiciously small"
    with path.open("rb") as f:
        magic = f.read(8)
    assert magic == b"\x89PNG\r\n\x1a\n", f"not a valid PNG: {magic.hex()}"


async def test_adapter_executes_real_click_from_recipe(tmp_path: Path) -> None:
    """Recipe-provided coords produce an actual pyautogui.click at the target.

    Uses the cursor's current position as the click target so the test does
    not drag the cursor around or risk hitting a sensitive UI element. The
    adapter's post-click verification still runs end-to-end against the real
    pyautogui binary.
    """
    start = pyautogui.position()
    recipe = ClickRecipe.model_validate(
        {"missions": {"click_dispatch": {"x": int(start.x), "y": int(start.y)}}}
    )
    adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)

    # Execute just the click_dispatch mission; the adapter will real-click
    # at the recipe coords, capture screenshots, and write the action-log.
    await adapter.execute(ExecutionRequest(mission_name="click_dispatch", payload={}))

    # Evidence must be physically present on disk.
    action_log = tmp_path / "artifacts" / "action-log" / "click-dispatched.jsonl"
    assert action_log.is_file(), "click-dispatched action log missing"
    screenshot = (
        tmp_path / "artifacts" / "screenshot" / "click-dispatched-fallback.png"
    )
    assert screenshot.is_file(), "click_dispatch screenshot missing"
    assert screenshot.stat().st_size > 1000, "screenshot suspiciously small"
