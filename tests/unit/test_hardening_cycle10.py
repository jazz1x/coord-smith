"""Regression tests for adversarial hardening CYCLE 10.

Cycle 10 (the final confirmation cycle) still found 2 MEDIUM the prior 9 missed:
- preflight-failsafe-corner-exit1: a cursor parked at a FAILSAFE screen corner
  made preflight's warmup moveTo raise FailSafeException, misclassified as a
  generic exit-1 crash instead of the permission verdict preflight exists to
  give. Fixed by relocating the cursor inward (FAILSAFE momentarily off,
  restored True) so preflight succeeds on a permitted host.

See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pyautogui
import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter


def _pt(x: int, y: int) -> object:
    return type("P", (), {"x": x, "y": y})()


@pytest.mark.asyncio
async def test_preflight_relocates_cursor_off_failsafe_corner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)

    # position(): corner (start) -> centre (after relocate) -> probe target.
    positions = iter([_pt(0, 0), _pt(640, 400), _pt(650, 400)])
    monkeypatch.setattr(pyautogui, "position", lambda: next(positions))
    monkeypatch.setattr(
        pyautogui, "size", lambda: type("S", (), {"width": 1280, "height": 800})()
    )

    # moveTo raises FailSafeException on the FIRST (warmup) call only; the
    # relocate / probe / restore calls succeed.
    calls = {"n": 0}

    def fake_moveto(x: int, y: int, duration: float = 0) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise pyautogui.FailSafeException("cursor at corner")

    monkeypatch.setattr(pyautogui, "moveTo", fake_moveto)
    monkeypatch.setattr(pyautogui, "screenshot", lambda: Image.new("RGB", (4, 4)))
    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.asyncio.sleep",
        AsyncMock(),
    )

    pyautogui.FAILSAFE = True
    # Must NOT raise — the corner is relocated, not crashed on.
    await adapter.preflight()

    # FAILSAFE restored to True for all subsequent dispatch.
    assert pyautogui.FAILSAFE is True
    # The warmup raised, then relocate + probe + restore ran.
    assert calls["n"] >= 3
