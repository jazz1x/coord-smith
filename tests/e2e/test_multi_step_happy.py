"""End-to-end happy path for a multi-step recipe.

Validates that an N-step recipe runs through the released-scope graph and
produces one set of artifacts per step, all under the same run root. The
underlying ``pyautogui`` calls are mocked so the test is deterministic and
requires no macOS Accessibility / Screen Recording permission.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run


def _fake_screenshot() -> Image.Image:
    return Image.new("RGB", (800, 600), color="white")


_FakeSize = type("Point", (), {"width": 1920, "height": 1080})


class _MovingCursor:
    """Tracks the last pyautogui.click target and reports it as cursor position.

    The adapter's ``_verified_click`` cross-checks ``pyautogui.position`` after
    each click; the fake position must match the click target or the adapter
    raises ``ClickExecutionUnverified``. This stand-in lets per-step tests
    declare arbitrary distinct click coordinates without per-test patches.
    """

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
    "--session-ref", "multi-step-happy",
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
async def test_three_step_recipe_runs_each_step_in_order(tmp_path: Path) -> None:
    """A 3-step coord recipe produces 3 dispatched clicks in declaration order."""
    recipe = tmp_path / "flow.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: open-buy\n"
        "    coord: { x: 100, y: 100 }\n"
        "  - name: select-seat\n"
        "    coord: { x: 200, y: 200 }\n"
        "  - name: confirm\n"
        "    coord: { x: 300, y: 300 }\n",
        encoding="utf-8",
    )

    cursor = _MovingCursor()
    click_calls: list[tuple[int, int]] = []

    def capture_click(x: object, y: object) -> None:
        cursor.click(x, y)
        click_calls.append((cursor.x, cursor.y))

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click", side_effect=capture_click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        exit_code = await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )

    assert exit_code == 0
    assert click_calls == [(100, 100), (200, 200), (300, 300)], (
        f"Expected three clicks in declaration order, got {click_calls}"
    )


@pytest.mark.asyncio
async def test_three_step_recipe_writes_step_artifacts_for_each_step(
    tmp_path: Path,
) -> None:
    """Each step's evidence (action-log + screenshot) is recorded once per step."""
    recipe = tmp_path / "flow.yaml"
    recipe.write_text(
        "version: 1\n"
        "steps:\n"
        "  - name: a\n"
        "    coord: { x: 10, y: 10 }\n"
        "  - name: b\n"
        "    coord: { x: 20, y: 20 }\n"
        "  - name: c\n"
        "    coord: { x: 30, y: 30 }\n",
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
        exit_code = await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )
    assert exit_code == 0

    action_log = _find_action_log_dir(tmp_path)
    # Each step mission appends two records per invocation: one from the
    # call-site seed (carries step_idx + step_name) and one from the
    # adapter's _gather_evidence pass. With N=3 steps that's 6 records per
    # step-* file. Filter to the seed records to verify per-step ordering.
    observed_seeds = [
        r
        for r in _read_jsonl_lines(action_log / "step-observed.jsonl")
        if "step_idx" in r
    ]
    dispatched_seeds = [
        r
        for r in _read_jsonl_lines(action_log / "step-dispatched.jsonl")
        if "step_idx" in r
    ]
    captured_seeds = [
        r
        for r in _read_jsonl_lines(action_log / "step-captured.jsonl")
        if "step_idx" in r
    ]
    assert len(observed_seeds) == 3
    assert len(dispatched_seeds) == 3
    assert len(captured_seeds) == 3

    # step_idx + step_name are recorded in declaration order.
    assert [r["step_idx"] for r in dispatched_seeds] == [0, 1, 2]
    assert [r["step_name"] for r in dispatched_seeds] == ["a", "b", "c"]

    # Sealed exit proof exists.
    assert (action_log / "release-ceiling-stop.jsonl").exists()


@pytest.mark.asyncio
async def test_zero_step_recipe_runs_smoke_target_without_clicks(
    tmp_path: Path,
) -> None:
    """A recipe with empty steps: [] runs setup/teardown but no clicks."""
    recipe = tmp_path / "smoke.yaml"
    recipe.write_text("version: 1\nsteps: []\n", encoding="utf-8")

    click_calls: list[tuple[int, int]] = []
    cursor = _MovingCursor()

    def capture_click(x: object, y: object) -> None:
        cursor.click(x, y)
        click_calls.append((cursor.x, cursor.y))

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=_fake_screenshot),
        patch("pyautogui.click", side_effect=capture_click),
        patch("pyautogui.moveTo", side_effect=cursor.move_to),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
    ):
        exit_code = await _run(
            argv=["--click-recipe", str(recipe), *_COMMON_ARGV],
            base_dir=tmp_path,
        )

    assert exit_code == 0
    assert click_calls == [], "smoke target must not click"

    action_log = _find_action_log_dir(tmp_path)
    # Per-run setup/teardown still write their evidence.
    assert (action_log / "attach-session.jsonl").exists()
    assert (action_log / "prepare-session.jsonl").exists()
    assert (action_log / "release-ceiling-stop.jsonl").exists()
    # Per-step files are absent (no step nodes ran).
    assert not (action_log / "step-dispatched.jsonl").exists()
