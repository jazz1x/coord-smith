"""Tests that ``failure.jsonl`` records the correct phase per origin.

The same typed exception class (notably ``ImageWaitTimeout``) can be
raised by multiple guards in a step's dispatch — pre-click ``wait_for``
or post-click ``post_click_signal``. Callers need ``record["phase"]``
to tell them apart for diagnostic branching. These tests verify the
phase tag is correct for each guard origin.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import (
    PostClickSignal,
    Step,
    StepCoord,
    WaitFor,
)
from coord_smith.models.errors import (
    ClickCoordinatesOutOfBounds,
    ImageWaitTimeout,
    PageTransitionNotDetected,
)


class _StationaryCursor:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0

    def click(self, x: object, y: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def position(self) -> _StationaryCursor:
        return self


_FakeSize = type("Size", (), {"width": 1280, "height": 800})


def _read_failure_record(run_root: Path) -> dict[str, object]:
    log = run_root / "artifacts" / "action-log" / "failure.jsonl"
    return json.loads(log.read_text(encoding="utf-8").strip())


def _make_template(tmp_path: Path, name: str = "x.png") -> Path:
    p = tmp_path / name
    Image.new("RGB", (8, 8), color="black").save(p)
    return p


@pytest.mark.asyncio
async def test_phase_pre_click_when_wait_for_times_out(tmp_path: Path) -> None:
    """Step with wait_for that never matches → phase=pre_click."""
    tmpl = _make_template(tmp_path, "anchor.png")
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="seat",
        coord=StepCoord(x=10, y=20),
        wait_for=WaitFor(image=str(tmpl), timeout=0.05, interval=0.01),
    )
    payload = {"step": step.model_dump(), "step_idx": 0}

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            return_value=None,
        ),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (50, 50), color="gray"),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._execute_step_dispatch(payload)

    record = _read_failure_record(tmp_path)
    assert record["phase"] == "pre_click", (
        f"wait_for timeout must produce phase=pre_click, got {record['phase']}"
    )
    assert record["error_class"] == "ImageWaitTimeout"


@pytest.mark.asyncio
async def test_phase_dispatch_when_coord_out_of_bounds(tmp_path: Path) -> None:
    """A coord beyond the screen bounds → phase=dispatch."""
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    # Step with coord far past the fake 1280x800 screen.
    step = Step(name="far-away", coord=StepCoord(x=10_000, y=10_000))
    payload = {"step": step.model_dump(), "step_idx": 0}

    with (
        patch("pyautogui.size", return_value=_FakeSize()),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (50, 50), color="gray"),
        ),
    ):
        with pytest.raises(ClickCoordinatesOutOfBounds):
            await adapter._execute_step_dispatch(payload)

    record = _read_failure_record(tmp_path)
    assert record["phase"] == "dispatch", (
        f"out-of-bounds must produce phase=dispatch, got {record['phase']}"
    )
    assert record["error_class"] == "ClickCoordinatesOutOfBounds"


@pytest.mark.asyncio
async def test_phase_post_click_when_verify_transition_fails(
    tmp_path: Path,
) -> None:
    """verify_transition raising PageTransitionNotDetected → phase=post_click."""
    cursor = _StationaryCursor()
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="changes-nothing",
        coord=StepCoord(x=10, y=20),
        verify_transition=True,
        transition_threshold=0.99,  # impossibly high → guaranteed miss
        settle_ms=0,
    )
    payload = {"step": step.model_dump(), "step_idx": 0}

    # screenshot returns the SAME image both pre- and post-click so diff
    # is zero. That falls under the high threshold and raises the
    # post-click verifier.
    same_frame = Image.new("RGB", (200, 200), color="white")

    with (
        patch("pyautogui.size", return_value=_FakeSize()),
        patch("pyautogui.screenshot", return_value=same_frame),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(PageTransitionNotDetected):
            await adapter._execute_step_dispatch(payload)

    record = _read_failure_record(tmp_path)
    assert record["phase"] == "post_click", (
        f"verify_transition failure must produce phase=post_click, "
        f"got {record['phase']}"
    )
    assert record["error_class"] == "PageTransitionNotDetected"


@pytest.mark.asyncio
async def test_phase_post_click_when_transition_region_offscreen(
    tmp_path: Path,
) -> None:
    """A positive-extent but fully off-screen ``transition_region`` makes the
    verifier raise ValueError; the adapter remaps it to a typed,
    phase-tagged PageTransitionNotDetected ("could not run") instead of letting
    a raw ValueError escape as an unattributed crash. Step validation accepts
    an off-screen positive box (it only rejects non-positive extents), so this
    branch is reachable from a real recipe — pin it.
    """
    cursor = _StationaryCursor()
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="offscreen-region",
        coord=StepCoord(x=10, y=20),
        verify_transition=True,
        # positive extent (passes _validate_region) but fully off the frame
        transition_region=(5000, 5000, 50, 50),
        settle_ms=0,
    )
    payload = {"step": step.model_dump(), "step_idx": 0}
    same_frame = Image.new("RGB", (200, 200), color="white")

    with (
        patch("pyautogui.size", return_value=_FakeSize()),
        patch("pyautogui.screenshot", return_value=same_frame),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(PageTransitionNotDetected),
    ):
        await adapter._execute_step_dispatch(payload)

    record = _read_failure_record(tmp_path)
    assert record["phase"] == "post_click"
    assert record["error_class"] == "PageTransitionNotDetected"


@pytest.mark.asyncio
async def test_phase_post_click_when_post_click_signal_times_out(
    tmp_path: Path,
) -> None:
    """post_click_signal poll that never matches → phase=post_click.

    Confirms the *same* ImageWaitTimeout class disambiguates between
    pre_click (wait_for) and post_click (post_click_signal) via phase.
    """
    signal_tmpl = _make_template(tmp_path, "toast.png")
    cursor = _StationaryCursor()
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(
        name="confirms-nothing",
        coord=StepCoord(x=10, y=20),
        post_click_signal=PostClickSignal(
            image=str(signal_tmpl), timeout=0.05, interval=0.01
        ),
        settle_ms=0,
    )
    payload = {"step": step.model_dump(), "step_idx": 0}

    with (
        patch("pyautogui.size", return_value=_FakeSize()),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (50, 50), color="gray"),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            return_value=None,
        ),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._execute_step_dispatch(payload)

    record = _read_failure_record(tmp_path)
    assert record["phase"] == "post_click", (
        "post_click_signal timeout must produce phase=post_click — that's "
        "what disambiguates it from a pre_click wait_for timeout, even "
        "though both raise ImageWaitTimeout. "
        f"Got {record['phase']}"
    )
    assert record["error_class"] == "ImageWaitTimeout"
