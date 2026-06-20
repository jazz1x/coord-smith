"""Regression tests for adversarial hardening CYCLE 6.

Cycle 6 (multi-agent, 19 hunted / 15 confirmed, 0 HIGH/CRITICAL) focused on the
evidence/CLI boundary:

- missing-input-masked-by-preflight: on the real-run path, a missing required
  input was reported as exit 2 ("grant Accessibility") instead of exit 3
  ("supply --session-ref") because preflight ran before input validation. Now
  inputs are validated first, before adapter/lock/preflight.
- failure-evidence-mission-phase-misattribution: a screenshot/evidence-gather
  failure in step_observe/step_capture was recorded as step_dispatch /
  phase=dispatch. Now self-describes (step-observe-failed/pre_click,
  step-capture-failed/post_click).
- action-log-ensure-ascii-inconsistency: action-log writers now serialize with
  ensure_ascii=False, matching the sibling producers.
- legacy-deprecation-warning-swallowed-on-cli: the missions:-shape deprecation
  now emits a WARNING log line (visible on the CLI), not only a
  DeprecationWarning the default filter hides.

See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from unittest.mock import patch

from coord_smith.adapters.action_log_writer import ActionLogWriter
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import load_click_recipe
from coord_smith.graph.pyautogui_cli_entrypoint import main
from coord_smith.models.errors import ImageMatchConfidenceLow, ScreenCaptureUnavailable

# ---------------------------------------------------------------------------
# missing-input-masked-by-preflight — exit 3 BEFORE preflight on the real run
# ---------------------------------------------------------------------------


def test_missing_input_exits_3_before_preflight_on_real_run(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.chdir(tmp_path)
    recipe = tmp_path / "r.yaml"
    recipe.write_text(
        "version: 1\nsteps:\n  - name: s\n    coord: {x: 1, y: 2}\n",
        encoding="utf-8",
    )
    for k in (
        "COORDSMITH_SESSION_REF", "COORDSMITH_EXPECTED_AUTH_STATE",
        "COORDSMITH_TARGET_PAGE_URL", "COORDSMITH_SITE_IDENTITY",
    ):
        monkeypatch.delenv(k, raising=False)
    # preflight raising proves the exit-3 comes from input validation, not a
    # permission failure (exit 2). This is the REAL-run path (no --dry-run).
    with patch.object(
        PyAutoGUIAdapter, "preflight",
        side_effect=AssertionError("preflight must NOT run before input validation"),
    ):
        code = main(argv=["--click-recipe", str(recipe)])
    assert code == 3


# ---------------------------------------------------------------------------
# failure-evidence-mission-phase-misattribution — observe/capture self-describe
# ---------------------------------------------------------------------------


def _read_failure(tmp_path: Path) -> dict[str, object]:
    log = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    return json.loads(log.read_text(encoding="utf-8").splitlines()[0])


def test_observe_gather_failure_attributed_to_observe(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    adapter._capture_failure_evidence(
        step_idx=0,
        step_name="open-buy",
        error=ScreenCaptureUnavailable("disk full"),
        mission="step_observe",
        phase="pre_click",
    )
    rec = _read_failure(tmp_path)
    assert rec["mission_name"] == "step_observe"
    assert rec["event"] == "step-observe-failed"
    assert rec["phase"] == "pre_click"
    assert rec["step_name"] == "open-buy"


def test_capture_gather_failure_attributed_to_capture(tmp_path: Path) -> None:
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    adapter._capture_failure_evidence(
        step_idx=2,
        step_name="confirm",
        error=ScreenCaptureUnavailable("x"),
        mission="step_capture",
        phase="post_click",
    )
    rec = _read_failure(tmp_path)
    assert rec["mission_name"] == "step_capture"
    assert rec["event"] == "step-capture-failed"
    assert rec["phase"] == "post_click"


def test_dispatch_failure_attribution_unchanged(tmp_path: Path) -> None:
    # The default (no mission/phase passed) must stay step_dispatch / dispatch
    # so the existing dispatch contract is untouched.
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    adapter._capture_failure_evidence(
        step_idx=1, step_name="y", error=ImageMatchConfidenceLow("no match")
    )
    rec = _read_failure(tmp_path)
    assert rec["mission_name"] == "step_dispatch"
    assert rec["event"] == "step-dispatch-failed"
    assert rec["phase"] == "dispatch"


# ---------------------------------------------------------------------------
# action-log-ensure-ascii-inconsistency — unicode step names written as UTF-8
# ---------------------------------------------------------------------------


def test_action_log_writes_unicode_step_name_raw_utf8(tmp_path: Path) -> None:
    writer = ActionLogWriter(run_root=tmp_path)
    writer.write_image_match(
        mission="구매-확인", template="t.png", confidence=0.9, x=1, y=2
    )
    raw = (tmp_path / "artifacts" / "action-log" / "구매-확인.jsonl").read_bytes()
    assert "구매-확인".encode() in raw, "step name must be raw UTF-8"
    assert b"\\u" not in raw, "must not be \\uXXXX ascii-escaped"


# ---------------------------------------------------------------------------
# legacy-deprecation-warning-swallowed-on-cli — emits a WARNING log line
# ---------------------------------------------------------------------------


def test_legacy_missions_recipe_emits_warning_log(
    tmp_path: Path, caplog
) -> None:  # type: ignore[no-untyped-def]
    recipe = tmp_path / "legacy.yaml"
    recipe.write_text(
        "version: 1\nmissions:\n  click_dispatch:\n    x: 150\n    y: 250\n",
        encoding="utf-8",
    )
    with (
        caplog.at_level(logging.WARNING, logger="coord_smith.click_recipe"),
        warnings.catch_warnings(),
    ):
        warnings.simplefilter("ignore", DeprecationWarning)
        load_click_recipe(recipe)
    assert any(
        "deprecated" in r.getMessage().lower() and "missions" in r.getMessage().lower()
        for r in caplog.records
    ), "legacy missions recipe must emit a WARNING log line for CLI visibility"
