"""Regression tests for adversarial hardening CYCLE 3.

Cycle 3 (multi-agent fan-out, 17 hunted / 16 confirmed) hardened the FAILSAFE
evidence path, CLI typo rejection, dry-run input validation, and message
labelling. See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pyautogui
import pytest

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import Step, StepCoord
from coord_smith.graph.pyautogui_cli_entrypoint import (
    _is_negative_number,
    _reject_unknown_flags,
    main,
)
from coord_smith.models.errors import ConfigError

# ---------------------------------------------------------------------------
# failsafe-escapes-failure-evidence-net — FailSafeException now writes evidence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failsafe_abort_writes_failure_evidence(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="abort-step", coord=StepCoord(x=10, y=20))

    async def _raise_failsafe(*a: object, **k: object) -> None:
        raise pyautogui.FailSafeException("corner abort")

    with (
        patch.object(PyAutoGUIAdapter, "_validate_bounds"),
        patch.object(PyAutoGUIAdapter, "_verified_click", side_effect=_raise_failsafe),
        pytest.raises(pyautogui.FailSafeException),
    ):
        await adapter._execute_step_dispatch({"step": step, "step_idx": 0})

    # failure.jsonl must exist with the FailSafe attribution.
    failure_log = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    assert failure_log.is_file()
    content = failure_log.read_text(encoding="utf-8")
    assert "FailSafeException" in content
    assert "abort-step" in content


# ---------------------------------------------------------------------------
# typo-cli-flag-silent-noop — unknown flags rejected (exit 3), values allowed
# ---------------------------------------------------------------------------


def test_reject_unknown_flag_raises() -> None:
    with pytest.raises(ConfigError, match="unknown flag"):
        _reject_unknown_flags(["--click-recipie", "/tmp/x.yaml"])


def test_reject_unknown_flags_allows_known() -> None:
    # Known flags + their values + negative numeric values must pass.
    _reject_unknown_flags(
        ["--click-recipe", "/tmp/x.yaml", "--session-ref", "s",
         "--max-runs", "-1", "--dry-run"]
    )


@pytest.mark.parametrize("tok,expected", [
    ("-1", True), ("-3.5", True), ("--session-ref", False),
    ("-x", False), ("positional", False),
])
def test_is_negative_number(tok: str, expected: bool) -> None:
    assert _is_negative_number(tok) is expected


def test_main_rejects_typo_flag_exit_3(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    code = main(argv=["--click-recipie", "/tmp/x.yaml", "--session-ref", "s"])
    assert code == 3


# ---------------------------------------------------------------------------
# dry-run-skips-required-inputs — --dry-run now validates required inputs
# ---------------------------------------------------------------------------


def test_dry_run_missing_inputs_exits_3(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    # Clear env so no COORDSMITH_* inputs leak in.
    for k in (
        "COORDSMITH_SESSION_REF", "COORDSMITH_EXPECTED_AUTH_STATE",
        "COORDSMITH_TARGET_PAGE_URL", "COORDSMITH_SITE_IDENTITY",
    ):
        monkeypatch.delenv(k, raising=False)
    with patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock):
        code = main(argv=["--dry-run"])
    assert code == 3


# ---------------------------------------------------------------------------
# wait-for-timeout-message-mislabel — pre-click timeout names its own role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_image_role_in_timeout_message(tmp_path: Path) -> None:
    from coord_smith.models.errors import ImageWaitTimeout

    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    with patch("pyautogui.locateCenterOnScreen", return_value=None):
        with pytest.raises(ImageWaitTimeout) as exc_info:
            await adapter.wait_for_image(
                path="/tmp/anchor.png",
                timeout=0.01,
                interval=0.005,
                role="pre-click wait_for anchor",
            )
    assert "pre-click wait_for anchor" in str(exc_info.value)
    assert "post-click signal" not in str(exc_info.value)
