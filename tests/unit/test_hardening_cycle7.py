"""Regression tests for adversarial hardening CYCLE 7.

Cycle 7 (multi-agent; verify phase partly rate-limited, survivors verified by
hand) was a convergence cycle — all confirmed findings LOW. Two genuine
robustness fixes landed:

- per-run-mission-screenshot-failure-no-attribution: a screenshot/evidence-
  gather failure during a per-RUN mission (attach_session / prepare_session /
  run_completion, step_idx=None) was NOT wrapped in the failure-evidence net, so
  run.json reported status=failure with failure=null. Now symmetric with the
  per-step path: the failure self-describes (attach-session-failed, step_idx=-1).
- step-glob-name-coupling: step_count recovery globbed step-*.jsonl, which also
  matches a user step named "step-foo". Now reads only the 3 canonical per-step
  files, so a user step can never contaminate the count.

See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coord_smith.adapters.execution.contracts import ExecutionRequest
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.models.errors import ScreenCaptureUnavailable
from coord_smith.models.identifiers import MissionName
from coord_smith.reporting.run_summary import _step_count_from_recipe

# ---------------------------------------------------------------------------
# per-run-mission-screenshot-failure-no-attribution
# ---------------------------------------------------------------------------


async def test_per_run_mission_gather_failure_writes_failure_evidence(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    adapter = PyAutoGUIAdapter(run_root=tmp_path)

    def _raise(*_a: object, **_k: object) -> object:
        raise ScreenCaptureUnavailable("disk full")

    monkeypatch.setattr(adapter, "_gather_evidence", _raise)
    request = ExecutionRequest(
        mission_name=MissionName("attach_session"), payload={}
    )

    with pytest.raises(ScreenCaptureUnavailable):
        await adapter.execute(request)

    failure = tmp_path / "artifacts" / "action-log" / "failure.jsonl"
    assert failure.is_file(), (
        "a per-run mission gather failure must still write failure.jsonl"
    )
    rec = json.loads(failure.read_text(encoding="utf-8").splitlines()[0])
    assert rec["mission_name"] == "attach_session"
    assert rec["event"] == "attach-session-failed"
    assert rec["step_idx"] == -1
    assert rec["error_class"] == "ScreenCaptureUnavailable"


# ---------------------------------------------------------------------------
# step-glob-name-coupling — only the 3 canonical per-step files are counted
# ---------------------------------------------------------------------------


def test_step_count_ignores_user_named_step_files(tmp_path: Path) -> None:
    action_log = tmp_path / "artifacts" / "action-log"
    action_log.mkdir(parents=True)
    # Canonical per-step file with two distinct step_idx values.
    (action_log / "step-dispatched.jsonl").write_text(
        '{"step_idx": 0}\n{"step_idx": 1}\n', encoding="utf-8"
    )
    # A user step NAMED "step-foo" whose guard log (hypothetically) carries a
    # step_idx must NOT inflate the recovered count.
    (action_log / "step-foo.jsonl").write_text(
        '{"step_idx": 99}\n', encoding="utf-8"
    )

    assert _step_count_from_recipe(run_root=tmp_path) == 2


def test_step_count_reads_all_three_canonical_files(tmp_path: Path) -> None:
    action_log = tmp_path / "artifacts" / "action-log"
    action_log.mkdir(parents=True)
    (action_log / "step-observed.jsonl").write_text(
        '{"step_idx": 0}\n{"step_idx": 1}\n{"step_idx": 2}\n', encoding="utf-8"
    )
    (action_log / "step-dispatched.jsonl").write_text(
        '{"step_idx": 0}\n', encoding="utf-8"
    )
    # Union of distinct step_idx across canonical files = {0, 1, 2} = 3.
    assert _step_count_from_recipe(run_root=tmp_path) == 3
