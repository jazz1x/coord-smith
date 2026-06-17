"""Tests for ``Step.wait_for`` adapter wire-up — pre-click image guard.

These tests verify that a Step with a populated ``wait_for`` field:

1. Polls the configured image before any click is dispatched.
2. Writes a ``wait_for_*`` action-log entry on success.
3. Raises ``ImageWaitTimeout`` when the template never appears, and the
   click is NOT attempted in that case.
4. Raises ``ImageTemplateNotFound`` when the template file is missing.
5. Forwards the optional ``region`` to ``locateCenterOnScreen``.

The schema-level test ``test_step_with_wait_for_pre_click_guard`` covers
that the field validates; this file covers that the adapter actually
honors it.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord, WaitFor
from coord_smith.models.errors import ImageTemplateNotFound, ImageWaitTimeout


class _StationaryCursor:
    """Cursor stub that mirrors the last click target so _verified_click passes."""

    def __init__(self) -> None:
        self.x = 0
        self.y = 0

    def click(self, x: object, y: object) -> None:
        self.x = int(x)  # type: ignore[arg-type]
        self.y = int(y)  # type: ignore[arg-type]

    def position(self) -> _StationaryCursor:
        return self


_FakeSize = type("Size", (), {"width": 1920, "height": 1080})


def _make_adapter(tmp_path: Path) -> PyAutoGUIAdapter:
    return PyAutoGUIAdapter(run_root=tmp_path)


def _write_template(tmp_path: Path, name: str = "anchor.png") -> Path:
    path = tmp_path / name
    Image.new("RGB", (8, 8), color="black").save(path)
    return path


# ---- Happy path -----------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_runs_before_click_and_logs(tmp_path: Path) -> None:
    """A step.wait_for must poll BEFORE the click and log a wait_for record."""
    template = _write_template(tmp_path, "panel-loaded.png")
    cursor = _StationaryCursor()
    call_order: list[str] = []

    def fake_locate(*args: object, **kwargs: object) -> object:
        call_order.append("locate")
        return type("L", (), {"x": 50, "y": 60})()

    def fake_click(x: object, y: object) -> None:
        call_order.append("click")
        cursor.click(x, y)

    adapter = _make_adapter(tmp_path)
    step = Step(
        name="seat-pick",
        coord=StepCoord(x=200, y=300),
        wait_for=WaitFor(image=str(template), timeout=0.5, interval=0.05),
    )

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            side_effect=fake_locate,
        ),
        patch("pyautogui.click", side_effect=fake_click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await adapter._dispatch_with_step(step)

    # The wait_for poll must precede the click.
    assert call_order[0] == "locate"
    assert "click" in call_order
    assert call_order.index("locate") < call_order.index("click")

    # And a wait_for_* action-log entry must exist for the step. The
    # log file is named after the step (mirroring _write_signal_log /
    # _write_image_match_log convention) so per-step audit reads
    # the same key as other per-step events.
    log_file = tmp_path / "artifacts" / "action-log" / "seat-pick.jsonl"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "wait_for_template" in contents
    assert "wait_for_elapsed_seconds" in contents


# ---- Timeout path: click must NOT fire -----------------------------


@pytest.mark.asyncio
async def test_wait_for_timeout_blocks_click(tmp_path: Path) -> None:
    """If wait_for never matches, ImageWaitTimeout fires and click is skipped."""
    template = _write_template(tmp_path, "never-shows.png")
    clicks: list[tuple[int, int]] = []

    def never_locates(*args: object, **kwargs: object) -> None:
        return None  # template never appears

    adapter = _make_adapter(tmp_path)
    step = Step(
        name="blocked-step",
        coord=StepCoord(x=10, y=20),
        wait_for=WaitFor(image=str(template), timeout=0.1, interval=0.01),
    )

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            side_effect=never_locates,
        ),
        patch(
            "pyautogui.click",
            side_effect=lambda x, y: clicks.append((int(x), int(y))),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._dispatch_with_step(step)

    assert clicks == [], (
        "click must not fire when the pre-click wait_for guard times out"
    )


# ---- Missing template ----------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_missing_template_raises_typed_error(
    tmp_path: Path,
) -> None:
    """A nonexistent wait_for template path raises ImageTemplateNotFound."""
    adapter = _make_adapter(tmp_path)
    missing = tmp_path / "does-not-exist.png"
    step = Step(
        name="bad-anchor",
        coord=StepCoord(x=1, y=2),
        wait_for=WaitFor(image=str(missing), timeout=0.1),
    )
    with pytest.raises(ImageTemplateNotFound) as exc_info:
        await adapter._dispatch_with_step(step)
    assert "pre-click wait_for template not found" in str(exc_info.value)


# ---- Region forwarding ---------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_forwards_region_to_locator(tmp_path: Path) -> None:
    """WaitFor.region must reach pyautogui.locateCenterOnScreen verbatim."""
    template = _write_template(tmp_path, "anchor.png")
    cursor = _StationaryCursor()
    seen_regions: list[object] = []

    def capture_region(*args: object, **kwargs: object) -> object:
        seen_regions.append(kwargs.get("region"))
        return type("L", (), {"x": 5, "y": 6})()

    adapter = _make_adapter(tmp_path)
    step = Step(
        name="scoped-anchor",
        coord=StepCoord(x=100, y=100),
        wait_for=WaitFor(
            image=str(template),
            timeout=0.5,
            interval=0.05,
            region=(40, 50, 600, 400),
        ),
    )

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            side_effect=capture_region,
        ),
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch("pyautogui.size", return_value=_FakeSize()),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await adapter._dispatch_with_step(step)

    assert (40, 50, 600, 400) in seen_regions


# ---- Failure-capture wrapper integration ---------------------------


@pytest.mark.asyncio
async def test_wait_for_timeout_triggers_failure_evidence(
    tmp_path: Path,
) -> None:
    """When wait_for times out via _execute_step_dispatch, a failure png
    + failure.jsonl entry are written before the exception propagates."""
    template = _write_template(tmp_path, "never.png")
    adapter = _make_adapter(tmp_path)
    step = Step(
        name="timeout-step",
        coord=StepCoord(x=10, y=20),
        wait_for=WaitFor(image=str(template), timeout=0.05, interval=0.01),
    )
    payload = {"step": step.model_dump(), "step_idx": 0}

    with (
        patch(
            "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
            return_value=None,
        ),
        patch(
            "pyautogui.screenshot",
            return_value=Image.new("RGB", (100, 100), color="white"),
        ),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ImageWaitTimeout):
            await adapter._execute_step_dispatch(payload)

    failure_dir = tmp_path / "artifacts" / "failure"
    assert failure_dir.exists()
    assert any(p.suffix == ".png" for p in failure_dir.iterdir())
    failure_log = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    assert failure_log.exists()
    assert "ImageWaitTimeout" in failure_log.read_text(encoding="utf-8")
