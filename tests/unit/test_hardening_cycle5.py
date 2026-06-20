"""Regression tests for adversarial hardening CYCLE 5.

Cycle 5 (multi-agent, 14 hunted / 13 confirmed, 0 HIGH/CRITICAL) closed three
real defects and added two drift guards:

- A step named ``failure`` could write guard logs into the reserved
  ``failure.jsonl`` and shadow the real failure record in run.json — a gap in
  cycle-4's reserved-key guard (it omitted ``failure``, the one key that
  collides with run_summary's own source file).
- An early-exit invocation (host-busy / config / permission / interrupt) that
  created no run root of its own could overwrite a PRIOR run's run.json via the
  newest-by-mtime lookup. Now gated by a preexisting-root-name snapshot.
- A ``prefer: image`` step that silently rode its coord fallback (drifted
  template) left zero evidence; now emits an ``image_fallback_used`` record.

Plus: an equivalence guard pinning ``_RESERVED_ACTION_LOG_KEYS`` against the
keys derived from the mission evidence specs, and a unit test locking the
dormant scope-ceiling index comparison.

See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

import coord_smith.models.runtime as rt
from coord_smith.adapters.action_log_writer import ActionLogWriter
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.config.click_recipe import (
    _RESERVED_ACTION_LOG_KEYS,
    Step,
    StepCoord,
)
from coord_smith.missions.names import RELEASED_MISSIONS
from coord_smith.reporting.run_summary import RunSummaryWriter

# ---------------------------------------------------------------------------
# failure-step-name-contaminates-run-json — 'failure' is a reserved key
# ---------------------------------------------------------------------------


def test_step_name_rejects_failure_reserved_key() -> None:
    with pytest.raises(ValueError, match="reserved action-log key"):
        Step(name="failure", coord=StepCoord(x=1, y=1))


# ---------------------------------------------------------------------------
# reserved-action-log-keys-duplicated-ssot — pin the literal set against the
# keys derived from the mission evidence specs so a future rename fails CI.
# ---------------------------------------------------------------------------


def test_reserved_action_log_keys_match_derived_mission_keys() -> None:
    # action_key_for_mission is pure key derivation (no I/O), so a dummy
    # run_root is fine — we never touch the filesystem here.
    writer = ActionLogWriter(run_root=Path("/nonexistent"))
    derived = {writer.action_key_for_mission(m) for m in RELEASED_MISSIONS}
    # The reserved set is exactly the derived mission keys plus the
    # failure-evidence artifact name (the only non-mission reserved key).
    assert _RESERVED_ACTION_LOG_KEYS == derived | {"failure"}, (
        "reserved set drifted from the mission-derived keys; update "
        "_RESERVED_ACTION_LOG_KEYS to match missions.evidence_specs"
    )


# ---------------------------------------------------------------------------
# run-json-prior-root-misattribution — early exit must not overwrite a prior
# run's run.json; a root created by THIS invocation is still attributed.
# ---------------------------------------------------------------------------


def test_early_exit_does_not_overwrite_prior_run_root(tmp_path: Path) -> None:
    runs = tmp_path / "artifacts" / "runs"
    prior = runs / "20260101-000000-aaaaaaaa"
    prior.mkdir(parents=True)
    prior_summary = prior / "run.json"
    prior_summary.write_text(
        json.dumps({"run_id": "20260101-000000-aaaaaaaa", "status": "success"}),
        encoding="utf-8",
    )

    # The writer never claims a run root (set_own_run_root not called — a
    # host-busy invocation creates none), so it must NOT attribute the prior
    # root and must write a degenerate base_dir/run.json. (Cycle 9 replaced the
    # name-snapshot heuristic with this ownership model.)
    writer = RunSummaryWriter(base_dir=tmp_path)
    target = writer.flush(status="host_busy", exit_code=4)

    # Degenerate write lands under base_dir, NOT inside the prior root.
    assert target == tmp_path / "run.json"
    assert target != prior_summary
    # Prior run's outcome envelope is untouched.
    assert json.loads(prior_summary.read_text(encoding="utf-8"))["status"] == (
        "success"
    )


def test_flush_attributes_claimed_run_root(tmp_path: Path) -> None:
    # THIS invocation creates and CLAIMS its root (set_own_run_root, as the
    # graph does via on_run_root_created); flush writes into the claimed root.
    writer = RunSummaryWriter(base_dir=tmp_path)
    own = tmp_path / "artifacts" / "runs" / "20260101-000000-bbbbbbbb"
    own.mkdir(parents=True)
    writer.set_own_run_root(own)

    target = writer.flush(status="success", exit_code=0)

    assert target == own / "run.json"
    assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == own.name


# ---------------------------------------------------------------------------
# silent-image-fallback-no-evidence — image miss + coord fallback emits a record
# ---------------------------------------------------------------------------


def _write_template(tmp_path: Path, name: str = "btn.png") -> Path:
    path = tmp_path / name
    Image.new("RGB", (10, 10), color="black").save(path)
    return path


def test_image_fallback_writes_evidence_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = _write_template(tmp_path)
    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        lambda *a, **k: None,  # image miss
    )
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="buy", image=str(template), coord=StepCoord(x=42, y=99))

    assert adapter._resolve_step_click_coords(step) == (42, 99)

    log = tmp_path / "artifacts" / "action-log" / "buy.jsonl"
    assert log.is_file(), "silent coord fallback must emit an action-log record"
    records = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fallbacks = [r for r in records if r.get("image_fallback_used")]
    assert len(fallbacks) == 1
    assert fallbacks[0]["image_fallback_x"] == 42
    assert fallbacks[0]["image_fallback_y"] == 99
    assert fallbacks[0]["mission_name"] == "buy"
    assert fallbacks[0]["image_fallback_template"] == str(template)


def test_clean_image_match_writes_no_fallback_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = _write_template(tmp_path)

    def fake_locate(*args: object, **kwargs: object) -> object:
        return type("L", (), {"x": 5, "y": 6})()

    monkeypatch.setattr(
        "coord_smith.adapters.pyautogui_adapter.pyautogui.locateCenterOnScreen",
        fake_locate,
    )
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    step = Step(name="buy", image=str(template), coord=StepCoord(x=42, y=99))

    assert adapter._resolve_step_click_coords(step) == (5, 6)

    log = tmp_path / "artifacts" / "action-log" / "buy.jsonl"
    records = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert not any(r.get("image_fallback_used") for r in records), (
        "a clean image match must NOT emit a fallback record"
    )


# ---------------------------------------------------------------------------
# scope-ceiling-check-constant-true-dormant — lock the index comparison branch
# ---------------------------------------------------------------------------


def test_scope_ceiling_admits_every_released_mission_under_runcompletion() -> None:
    for mission in RELEASED_MISSIONS:
        assert (
            rt.mission_is_within_approved_scope(mission, "runCompletion") is True
        )


def test_scope_ceiling_index_rejects_missions_past_an_earlier_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The sole real ceiling maps to the LAST mission, so the index comparison
    # never rejects today (dormant by design — a hook for future partial
    # scopes). Inject a hypothetical ceiling pinned at prepare_session and
    # assert later missions are refused, so a future off-by-one in the index
    # math fails CI instead of silently surfacing only when partial scopes
    # are reintroduced.
    early = "prepare_session"
    assert early in rt.RELEASED_MISSIONS
    monkeypatch.setattr(
        rt,
        "RELEASED_SCOPE_CEILINGS",
        (*rt.RELEASED_SCOPE_CEILINGS, "prepareOnly"),
    )
    monkeypatch.setattr(
        rt,
        "_CEILING_TERMINAL_MISSION",
        {**rt._CEILING_TERMINAL_MISSION, "prepareOnly": early},
    )

    assert rt.mission_is_within_approved_scope("attach_session", "prepareOnly")
    assert rt.mission_is_within_approved_scope("prepare_session", "prepareOnly")
    assert not rt.mission_is_within_approved_scope("step_observe", "prepareOnly")
    assert not rt.mission_is_within_approved_scope("run_completion", "prepareOnly")
