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

import time
from pathlib import Path

import pyautogui
import pytest

from ez_ax.adapters.execution.client import ExecutionRequest
from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.config.click_recipe import ClickRecipe

pytestmark = pytest.mark.real


@pytest.fixture(scope="module", autouse=True)
def _pyautogui_warmup() -> None:
    """Prime the CoreGraphics event pump before the first real test.

    The very first pyautogui.moveTo after a cold process import is
    occasionally dropped on macOS even when Accessibility permission is
    granted, producing flaky preflight failures when this file is the
    only test collected. A one-pixel nudge + restore warms the pump
    without moving the cursor on net.
    """
    start = pyautogui.position()
    pyautogui.moveTo(start.x + 1, start.y, duration=0)
    time.sleep(0.1)
    pyautogui.moveTo(start.x, start.y, duration=0)
    time.sleep(0.1)


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


async def test_adapter_locates_image_template_on_real_screen(tmp_path: Path) -> None:
    """Image-template recipe self-locates against the live screen.

    Captures a real screenshot, crops a small region from it as the template,
    and feeds that template back to the adapter. The matcher should locate
    the cropped region on the live screen and click its center. The cursor
    is then restored to its original position.
    """
    start = pyautogui.position()
    screen = pyautogui.screenshot()
    # Pull a 64x64 crop from a stable area near top-left to avoid menu bars.
    crop_box = (200, 200, 264, 264)
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    template_path = template_dir / "self-region.png"
    screen.crop(crop_box).save(template_path)

    recipe = ClickRecipe.model_validate(
        {
            "missions": {
                "click_dispatch": {
                    "image": str(template_path),
                    "confidence": 0.9,
                    "grayscale": True,
                },
            },
        }
    )
    adapter = PyAutoGUIAdapter(run_root=tmp_path, click_recipe=recipe)
    try:
        await adapter.execute(
            ExecutionRequest(mission_name="click_dispatch", payload={})
        )
    finally:
        # Always restore the cursor so a flaky run does not strand the user.
        pyautogui.moveTo(start.x, start.y, duration=0)

    action_log = tmp_path / "artifacts" / "action-log" / "click-dispatched.jsonl"
    assert action_log.is_file(), "click-dispatched action log missing"
    import json as _json

    lines = [
        _json.loads(line)
        for line in action_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    image_records = [line for line in lines if "image_template" in line]
    assert len(image_records) >= 1, "image-match record not written"
    record = image_records[0]
    assert record["image_template"] == str(template_path)
    assert record["match_confidence"] == 0.9
    # Matched coords should fall inside the crop region with some tolerance.
    assert 200 <= record["match_x"] <= 280
    assert 200 <= record["match_y"] <= 280
