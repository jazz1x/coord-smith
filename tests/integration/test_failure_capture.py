"""Integration tests — typed dispatch failures emit failure evidence.

When a step's dispatch hits a typed adapter exception (image-not-matched,
out-of-bounds, click-unverified, transition-not-detected, signal-timeout),
the adapter writes:

* ``runs/<id>/artifacts/failure/<idx>-<step>-<error_class>.png`` —
  screenshot of the screen at the moment of failure.
* ``runs/<id>/artifacts/action-log/failure.jsonl`` — structured
  diagnostic record (timestamp, step idx/name, error class, error
  message, screenshot path).

Earlier steps' artifacts are preserved because the failure evidence is
written before the exception propagates and aborts the run.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pyautogui as pag
import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run

DEMO_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "demo"

_FakeSize = type("Size", (), {"width": 1280, "height": 800})


def _fake_screenshot() -> Image.Image:
    return Image.open(DEMO_DIR / "state-buy.png").copy()


class _MovingCursor:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0

    def click(self, x: object, y: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def move_to(self, x: object, y: object, *_: object, **__: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def position(self) -> _MovingCursor:
        return self


_COMMON = [
    "--session-ref", "fail-test",
    "--expected-auth-state", "authenticated",
    "--target-page-url", "file://demo",
    "--site-identity", "demo",
]


def _find_run_root(base: Path) -> Path:
    runs = list(base.glob("artifacts/runs/*"))
    assert runs, f"no run root under {base}"
    return runs[0]


@pytest.mark.asyncio
async def test_image_match_failure_writes_failure_screenshot_and_log(
    tmp_path: Path,
) -> None:
    """Step 1's image template is missing on the synthesized screen → adapter
    raises ImageMatchConfidenceLow. Failure dir contains a screenshot named
    after the step + error class, and failure.jsonl records the diagnostic."""

    # Create a recipe whose template exists on disk but cannot be matched
    # against the screen surrogate (we serve state-buy.png as the screen
    # but use a template cropped from a *different* state).
    recipe = tmp_path / "fail.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: missing-target\n"
        f"    image: {DEMO_DIR / 'templates' / 'panel-success.png'}\n"
        "    confidence: 0.9\n",
        encoding="utf-8",
    )

    cursor = _MovingCursor()

    def patched_locate_center(image: object, **kwargs: object) -> object:
        # Match against state-buy.png — panel-success template will not
        # appear there, so this returns None (image not matched).
        located = pag.locate(image, _fake_screenshot(), **kwargs)
        if located is None:
            return None
        cx = located.left + located.width / 2
        cy = located.top + located.height / 2
        Pt = type("Pt", (), {"x": cx, "y": cy})
        return Pt()

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch(
            "pyautogui.locateCenterOnScreen", side_effect=patched_locate_center
        ),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        # _run propagates ImageMatchConfidenceLow; main() would map to exit 1.
        from coord_smith.models.errors import ImageMatchConfidenceLow

        with pytest.raises(ImageMatchConfidenceLow):
            await _run(
                argv=["--click-recipe", str(recipe), *_COMMON],
                base_dir=tmp_path,
            )

    run_root = _find_run_root(tmp_path)
    failure_dir = run_root / "artifacts" / "failure"
    assert failure_dir.is_dir(), "failure/ directory must exist on dispatch failure"
    failure_pngs = list(failure_dir.glob("*.png"))
    assert len(failure_pngs) == 1, (
        f"exactly one failure screenshot expected, got {failure_pngs}"
    )
    name = failure_pngs[0].name
    assert "missing-target" in name
    assert "ImageMatchConfidenceLow" in name

    failure_log = run_root / "artifacts" / "action-log" / "failure.jsonl"
    assert failure_log.is_file()
    record = json.loads(failure_log.read_text(encoding="utf-8").strip())
    assert record["error_class"] == "ImageMatchConfidenceLow"
    assert record["step_name"] == "missing-target"
    assert record["step_idx"] == 0
    assert record["screenshot"] is not None


@pytest.mark.asyncio
async def test_image_match_failure_in_step_2_preserves_step_1_artifacts(
    tmp_path: Path,
) -> None:
    """A multi-step recipe whose step 0 succeeds and step 1 fails leaves the
    first step's evidence intact alongside the failure record."""

    # Step 0: image of buy button on state-buy.png — succeeds.
    # Step 1: image of panel-success — never appears on state-buy.png so
    # it fails (image not matched).
    recipe = tmp_path / "partial.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: open-buy\n"
        f"    image: {DEMO_DIR / 'templates' / 'buy-button.png'}\n"
        "    confidence: 0.9\n"
        "  - name: never-appears\n"
        f"    image: {DEMO_DIR / 'templates' / 'panel-success.png'}\n"
        "    confidence: 0.9\n",
        encoding="utf-8",
    )

    cursor = _MovingCursor()

    def patched_locate_center(image: object, **kwargs: object) -> object:
        located = pag.locate(image, _fake_screenshot(), **kwargs)
        if located is None:
            return None
        cx = located.left + located.width / 2
        cy = located.top + located.height / 2
        Pt = type("Pt", (), {"x": cx, "y": cy})
        return Pt()

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch(
            "pyautogui.locateCenterOnScreen", side_effect=patched_locate_center
        ),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        from coord_smith.models.errors import ImageMatchConfidenceLow

        with pytest.raises(ImageMatchConfidenceLow):
            await _run(
                argv=["--click-recipe", str(recipe), *_COMMON],
                base_dir=tmp_path,
            )

    run_root = _find_run_root(tmp_path)

    # Step 0's evidence is preserved.
    step_dispatched = run_root / "artifacts" / "action-log" / "step-dispatched.jsonl"
    assert step_dispatched.is_file()
    lines = step_dispatched.read_text(encoding="utf-8").strip().splitlines()
    seeds = [json.loads(line) for line in lines if "step_idx" in line]
    step_0_seeds = [r for r in seeds if r["step_idx"] == 0]
    assert step_0_seeds, "step 0 evidence must be preserved despite step 1 failure"
    assert step_0_seeds[0]["step_name"] == "open-buy"

    # Failure record points at step 1.
    failure_log = run_root / "artifacts" / "action-log" / "failure.jsonl"
    record = json.loads(failure_log.read_text(encoding="utf-8").strip())
    assert record["step_idx"] == 1
    assert record["step_name"] == "never-appears"
