"""Unit tests for ActionLogWriter (extracted from PyAutoGUIAdapter)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from coord_smith.adapters.action_log_writer import ActionLogWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# action_key_for_mission
# ---------------------------------------------------------------------------

def test_action_key_known_mission_returns_canonical_key(tmp_path: Path) -> None:
    """Known missions map to past-tense action keys from MISSION_EVIDENCE_SPECS."""
    writer = ActionLogWriter(tmp_path)
    key = writer.action_key_for_mission("step_dispatch")
    # MISSION_EVIDENCE_SPECS declares action-log ref for step_dispatch as
    # evidence://action-log/step-dispatched (verified via grep of evidence_specs.py)
    assert key == "step-dispatched"


def test_action_key_unknown_mission_falls_back_to_hyphen_substitution(
    tmp_path: Path,
) -> None:
    """Missions absent from the table get underscores replaced with hyphens."""
    writer = ActionLogWriter(tmp_path)
    assert writer.action_key_for_mission("my_custom_mission") == "my-custom-mission"


# ---------------------------------------------------------------------------
# write_action_log
# ---------------------------------------------------------------------------

def test_write_action_log_appends_to_correct_path(tmp_path: Path) -> None:
    writer = ActionLogWriter(tmp_path)
    writer.write_action_log(key="some-event", mission_name="my_mission")

    log_path = tmp_path / "artifacts" / "action-log" / "some-event.jsonl"
    assert log_path.exists()
    records = _read_jsonl(log_path)
    assert len(records) == 1
    record = records[0]
    assert record["mission_name"] == "my_mission"
    assert record["event"] == "some-event"
    assert "ts" in record


def test_write_action_log_multiple_calls_append(tmp_path: Path) -> None:
    """Each call appends a new line; the file is never overwritten."""
    writer = ActionLogWriter(tmp_path)
    writer.write_action_log(key="step-done", mission_name="m")
    writer.write_action_log(key="step-done", mission_name="m")

    log_path = tmp_path / "artifacts" / "action-log" / "step-done.jsonl"
    records = _read_jsonl(log_path)
    assert len(records) == 2


# ---------------------------------------------------------------------------
# write_image_match
# ---------------------------------------------------------------------------

def test_write_image_match_produces_image_template_key(tmp_path: Path) -> None:
    writer = ActionLogWriter(tmp_path)
    writer.write_image_match(
        mission="my_mission",
        template="templates/btn.png",
        confidence=0.9,
        x=100,
        y=200,
    )
    key = writer.action_key_for_mission("my_mission")
    log_path = tmp_path / "artifacts" / "action-log" / f"{key}.jsonl"
    records = _read_jsonl(log_path)
    assert len(records) == 1
    r = records[0]
    assert r["image_template"] == "templates/btn.png"
    assert r["match_confidence"] == pytest.approx(0.9)
    assert r["match_x"] == 100
    assert r["match_y"] == 200
    assert r["event"] == key


# ---------------------------------------------------------------------------
# write_signal
# ---------------------------------------------------------------------------

def test_write_signal_produces_post_click_signal_keys(tmp_path: Path) -> None:
    writer = ActionLogWriter(tmp_path)
    writer.write_signal(
        mission="my_mission",
        template="templates/toast.png",
        confidence=0.85,
        elapsed=1.23,
        x=50,
        y=75,
    )
    key = writer.action_key_for_mission("my_mission")
    log_path = tmp_path / "artifacts" / "action-log" / f"{key}.jsonl"
    records = _read_jsonl(log_path)
    assert len(records) == 1
    r = records[0]
    assert r["post_click_signal_template"] == "templates/toast.png"
    assert r["post_click_signal_confidence"] == pytest.approx(0.85)
    assert r["post_click_signal_elapsed_seconds"] == pytest.approx(1.23)
    assert r["post_click_signal_x"] == 50
    assert r["post_click_signal_y"] == 75


# ---------------------------------------------------------------------------
# write_wait_for
# ---------------------------------------------------------------------------

def test_write_wait_for_produces_wait_for_template_key(tmp_path: Path) -> None:
    writer = ActionLogWriter(tmp_path)
    writer.write_wait_for(
        mission="my_mission",
        template="templates/anchor.png",
        confidence=0.9,
        elapsed=0.5,
        x=10,
        y=20,
    )
    key = writer.action_key_for_mission("my_mission")
    log_path = tmp_path / "artifacts" / "action-log" / f"{key}.jsonl"
    records = _read_jsonl(log_path)
    assert len(records) == 1
    r = records[0]
    assert r["wait_for_template"] == "templates/anchor.png"
    assert r["wait_for_confidence"] == pytest.approx(0.9)
    assert r["wait_for_elapsed_seconds"] == pytest.approx(0.5)
    assert r["wait_for_x"] == 10
    assert r["wait_for_y"] == 20


# ---------------------------------------------------------------------------
# with_run_root
# ---------------------------------------------------------------------------

def test_with_run_root_returns_new_instance_with_different_path(
    tmp_path: Path,
) -> None:
    root_a = tmp_path / "run_a"
    root_b = tmp_path / "run_b"
    writer = ActionLogWriter(root_a)
    writer_b = writer.with_run_root(root_b)

    writer_b.write_action_log(key="ev", mission_name="m")
    assert (root_b / "artifacts" / "action-log" / "ev.jsonl").exists()
    assert not (root_a / "artifacts" / "action-log" / "ev.jsonl").exists()
