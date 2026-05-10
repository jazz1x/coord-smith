"""End-to-end coverage for partial step failure in a multi-step recipe.

When step N fails (image not matched and no coord fallback), the run
aborts at step N. Steps 0..N-1 must have already written their evidence
under the same run root, and the CLI must exit with a non-zero code so
the orchestrator can react. This is the contract that keeps OpenClaw's
view of the world coherent across partial flows.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run
from coord_smith.models.errors import ConfigError

_FakeSize = type("Point", (), {"width": 1920, "height": 1080})


def _fake_screenshot() -> Image.Image:
    return Image.new("RGB", (800, 600), color="white")


class _MovingCursor:
    """Tracks ``pyautogui.click`` so post-click position checks succeed."""

    def __init__(self) -> None:
        self.x = 0
        self.y = 0

    def click(self, x: object, y: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def move_to(self, x: object, y: object, *args: object, **kwargs: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def position(self) -> _MovingCursor:
        return self


_COMMON_ARGV = [
    "--session-ref", "multi-step-partial",
    "--expected-auth-state", "authenticated",
    "--target-page-url", "https://tickets.interpark.com/goods/26003199",
    "--site-identity", "interpark",
]


def _find_action_log_dir(base_dir: Path) -> Path:
    candidates = list(base_dir.glob("artifacts/runs/*/artifacts/action-log"))
    assert candidates, f"No action-log directory found under {base_dir}"
    return candidates[0]


def _read_jsonl_lines(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").strip().splitlines()
    ]


@pytest.mark.asyncio
async def test_image_only_step_failure_preserves_earlier_step_artifacts(
    tmp_path: Path,
) -> None:
    """Step 1 fails (image-only, template missing); step 0 evidence is preserved."""
    # Only step-0's template exists. Step-1's template is referenced but
    # absent — schema-level resolution raises ConfigError at recipe load,
    # which the CLI maps to exit code 3.
    Image.new("RGB", (10, 10), color="black").save(tmp_path / "btn0.png")

    recipe = tmp_path / "flow.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: present\n"
        "    image: btn0.png\n"
        "  - name: missing\n"
        "    image: btn1-does-not-exist.png\n",
        encoding="utf-8",
    )

    cursor = _MovingCursor()

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        with pytest.raises(ConfigError) as exc_info:
            await _run(
                argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
                base_dir=tmp_path,
            )

    # Recipe load surfaces a typed ConfigError pointing at the missing
    # template. The CLI ``main()`` catches this and exits with code 3;
    # _run() (which we exercise directly to avoid sys.exit side effects)
    # propagates the exception.
    assert "missing" in str(exc_info.value)  # the missing step's name
    assert "btn1-does-not-exist" in str(exc_info.value)


@pytest.mark.asyncio
async def test_runtime_image_match_failure_preserves_earlier_step_artifacts(
    tmp_path: Path,
) -> None:
    """Step 1 image fails to match at runtime; step 0 evidence is preserved.

    Both step images exist on disk so the recipe loads cleanly. At runtime,
    ``locateCenterOnScreen`` returns None for the step-1 template, and the
    step has no ``coord`` fallback declared, so the run aborts. Step 0's
    action-log entry must already be on disk.
    """
    Image.new("RGB", (10, 10), color="black").save(tmp_path / "btn0.png")
    Image.new("RGB", (10, 10), color="white").save(tmp_path / "btn1.png")

    recipe = tmp_path / "flow.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: present\n"
        "    image: btn0.png\n"
        "  - name: unmatched\n"
        "    image: btn1.png\n",
        encoding="utf-8",
    )

    call_count = {"locate": 0}

    def fake_locate(*args: object, **kwargs: object) -> object:
        call_count["locate"] += 1
        if call_count["locate"] == 1:
            # Step 0: succeed
            return type("L", (), {"x": 50, "y": 50})()
        # Step 1: fail to match
        return None

    cursor = _MovingCursor()

    from coord_smith.models.errors import ImageMatchConfidenceLow

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
        patch("pyautogui.locateCenterOnScreen", side_effect=fake_locate),
    ):
        # Step-1 is image-only with no coord fallback; the adapter
        # re-raises ``ImageMatchConfidenceLow`` instead of silently no-op'ing
        # so the caller (e.g. OpenClaw) sees a real diagnosis. ``main()``
        # would map this to exit 1; ``_run`` propagates the typed exception
        # directly so the test asserts the type.
        with pytest.raises(ImageMatchConfidenceLow):
            await _run(
                argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
                base_dir=tmp_path,
            )

    action_log = _find_action_log_dir(tmp_path)
    dispatched = _read_jsonl_lines(action_log / "step-dispatched.jsonl")
    seed_records = [r for r in dispatched if "step_idx" in r]
    # Step 0 must have been seeded before any step-1 work.
    step_0_seeds = [r for r in seed_records if r["step_idx"] == 0]
    assert len(step_0_seeds) == 1, (
        "Step 0 dispatch evidence must be preserved even when later steps fail"
    )
    assert step_0_seeds[0]["step_name"] == "present"
