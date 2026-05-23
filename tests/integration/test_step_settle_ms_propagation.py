"""Tests that ``Step.settle_ms`` actually drives the post-click pause.

The schema-level tests in ``test_step_dsl.py`` only check that the field
exists and validates. These tests verify the value reaches
``asyncio.sleep`` via the adapter so a recipe author's choice has real
runtime effect.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord


class _StationaryCursor:
    """Stand-in that makes pyautogui.position match the last click target.

    ``_verified_click`` raises ``ClickExecutionUnverified`` if cursor
    position ≠ click target; tests need the fake to "move" so the verify
    path lets the click succeed.
    """

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


@pytest.mark.asyncio
async def test_verified_click_default_uses_legacy_50ms(tmp_path: Path) -> None:
    """When no settle is passed, _verified_click sleeps the legacy 50 ms.

    Preflight and ad-hoc callers depend on the default; only step-driven
    clicks override it.
    """
    adapter = _make_adapter(tmp_path)
    cursor = _StationaryCursor()

    with (
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await adapter._verified_click(100, 200)

    mock_sleep.assert_called_once()
    (delay,), _ = mock_sleep.call_args
    assert delay == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_verified_click_honors_explicit_settle_seconds(tmp_path: Path) -> None:
    """A caller-supplied settle_seconds replaces the 50 ms default verbatim."""
    adapter = _make_adapter(tmp_path)
    cursor = _StationaryCursor()

    with (
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await adapter._verified_click(100, 200, settle_seconds=0.8)

    mock_sleep.assert_called_once()
    (delay,), _ = mock_sleep.call_args
    assert delay == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_verified_click_settle_zero_skips_sleep(tmp_path: Path) -> None:
    """settle_seconds=0 must not call asyncio.sleep at all — every microsecond
    counts for native UI tests."""
    adapter = _make_adapter(tmp_path)
    cursor = _StationaryCursor()

    with (
        patch("pyautogui.click", side_effect=cursor.click),
        patch("pyautogui.position", side_effect=cursor.position),
        patch(
            "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await adapter._verified_click(100, 200, settle_seconds=0.0)

    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_with_step_passes_settle_ms_as_seconds(
    tmp_path: Path,
) -> None:
    """``_dispatch_with_step`` must translate Step.settle_ms (int ms) into
    seconds when calling ``_verified_click``."""
    adapter = _make_adapter(tmp_path)
    step = Step(name="click", coord=StepCoord(x=10, y=20), settle_ms=750)

    with (
        patch.object(
            PyAutoGUIAdapter, "_validate_bounds"
        ),
        patch.object(
            PyAutoGUIAdapter,
            "_verified_click",
            new_callable=AsyncMock,
        ) as mock_verified,
    ):
        await adapter._dispatch_with_step(step)

    mock_verified.assert_called_once()
    _, kwargs = mock_verified.call_args
    assert kwargs.get("settle_seconds") == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_dispatch_with_step_default_settle_is_300ms(tmp_path: Path) -> None:
    """When the recipe omits settle_ms, the 300 ms schema default flows through."""
    adapter = _make_adapter(tmp_path)
    step = Step(name="click", coord=StepCoord(x=10, y=20))  # settle_ms defaulted

    with (
        patch.object(PyAutoGUIAdapter, "_validate_bounds"),
        patch.object(
            PyAutoGUIAdapter,
            "_verified_click",
            new_callable=AsyncMock,
        ) as mock_verified,
    ):
        await adapter._dispatch_with_step(step)

    _, kwargs = mock_verified.call_args
    assert kwargs.get("settle_seconds") == pytest.approx(0.3)
