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

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pyautogui
import pytest
from PIL import Image

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import ClickRecipe, Step
from coord_smith.config.released_inputs import resolve_released_scope_inputs
from coord_smith.models.errors import ConfigError, ImageMatchConfidenceLow


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


# ---------------------------------------------------------------------------
# failure-screenshot-partial-write — a save that fails mid-write must report
# screenshot=null, never a truncated path that .exists() would accept.
# ---------------------------------------------------------------------------


def test_failure_screenshot_save_failure_reports_null_not_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.screenshot",
        lambda: Image.new("RGB", (4, 4)),
    )
    with patch.object(Image.Image, "save", side_effect=OSError("No space left")):
        adapter._capture_failure_evidence(
            step_idx=0, step_name="x", error=ImageMatchConfidenceLow("no match")
        )
    rec = json.loads(
        (tmp_path / "artifacts" / "action-log" / "failure.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert rec["screenshot"] is None  # not a truncated path
    failure_dir = tmp_path / "artifacts" / "failure"
    # No half-written .png and no orphan .tmp left behind.
    assert not list(failure_dir.glob("*.png"))
    assert not list(failure_dir.glob("*.tmp"))


# ---------------------------------------------------------------------------
# missing-inputs-reported-one-at-a-time — all absent inputs named in ONE error.
# ---------------------------------------------------------------------------


def test_missing_inputs_reported_all_at_once() -> None:
    with pytest.raises(ConfigError) as ei:
        resolve_released_scope_inputs(argv=["--session-ref", "s"], env={})
    msg = str(ei.value)
    assert "expected_auth_state" in msg
    assert "target_page_url" in msg
    assert "site_identity" in msg


# ---------------------------------------------------------------------------
# missions-deprecation-not-machine-readable — JSON Schema flags missions.
# ---------------------------------------------------------------------------


def test_missions_field_marked_deprecated_in_schema() -> None:
    schema = ClickRecipe.model_json_schema()
    assert schema["properties"]["missions"].get("deprecated") is True


# ---------------------------------------------------------------------------
# post-click-signal-interval-timeout-untested — pin the PostClickSignal
# interval>timeout branch (byte-identical to WaitFor's, but previously only
# WaitFor's copy was tested).
# ---------------------------------------------------------------------------


def test_post_click_signal_rejects_interval_exceeding_timeout() -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step.model_validate(
            {
                "name": "x",
                "coord": {"x": 1, "y": 1},
                "post_click_signal": {
                    "image": "s.png",
                    "timeout": 1.0,
                    "interval": 99.0,
                },
            }
        )
