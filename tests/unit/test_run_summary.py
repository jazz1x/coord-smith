"""Tests for the run.json summary writer.

External orchestrators (e.g. OpenClaw) read ``run.json`` as a
single-file envelope describing the outcome of a coord-smith
invocation. The schema and presence guarantees are public contract;
these tests pin them.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from coord_smith.graph.run_summary import (
    SCHEMA_VERSION,
    SUMMARY_FILENAME,
    RunSummaryWriter,
)


def test_run_summary_writes_success_envelope(tmp_path: Path) -> None:
    """A success flush writes run.json under the latest run root."""
    # Create a fake run root so the writer can locate it.
    run_root = tmp_path / "artifacts" / "runs" / "20260518-000000-test"
    run_root.mkdir(parents=True)

    writer = RunSummaryWriter(base_dir=tmp_path)
    path = writer.flush(status="success", exit_code=0)

    assert path == run_root / SUMMARY_FILENAME
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["schema_version"] == SCHEMA_VERSION
    assert record["status"] == "success"
    assert record["exit_code"] == 0
    assert record["run_id"] == run_root.name
    assert record["step_count"] == 0
    assert record["failure"] is None
    # Timing fields present and well-formed.
    assert "started_at" in record
    assert "ended_at" in record
    assert isinstance(record["elapsed_seconds"], (int, float))
    assert record["elapsed_seconds"] >= 0


def test_run_summary_writes_failure_envelope_with_failure_record(
    tmp_path: Path,
) -> None:
    """When status=failure, the writer reads failure.jsonl and
    surfaces a compact failure block in run.json."""
    run_root = tmp_path / "artifacts" / "runs" / "20260518-000001-fail"
    action_log = run_root / "artifacts" / "action-log"
    action_log.mkdir(parents=True)

    failure_record = {
        "ts": "2026-05-18T00:00:01+00:00",
        "mission_name": "step_dispatch",
        "event": "step-dispatch-failed",
        "step_idx": 1,
        "step_name": "confirm",
        "phase": "pre_click",
        "error_class": "ImageWaitTimeout",
        "error_message": "timed out",
        "screenshot": "/abs/path/01-confirm-ImageWaitTimeout.png",
    }
    (action_log / "failure.jsonl").write_text(
        json.dumps(failure_record) + "\n", encoding="utf-8"
    )

    writer = RunSummaryWriter(base_dir=tmp_path)
    path = writer.flush(status="failure", exit_code=1)

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["status"] == "failure"
    assert record["exit_code"] == 1
    assert record["failure"] is not None
    assert record["failure"]["step_idx"] == 1
    assert record["failure"]["step_name"] == "confirm"
    assert record["failure"]["phase"] == "pre_click"
    assert record["failure"]["error_class"] == "ImageWaitTimeout"
    assert record["failure"]["screenshot"] == failure_record["screenshot"]
    assert record["failure"]["failure_jsonl"].endswith("failure.jsonl")


def test_run_summary_writes_under_base_dir_when_no_run_root(
    tmp_path: Path,
) -> None:
    """When the graph never created a run root (host-busy / config
    error) the summary is written at base_dir/run.json so the
    caller still has a deterministic file to read."""
    writer = RunSummaryWriter(base_dir=tmp_path)
    path = writer.flush(status="host_busy", exit_code=4)

    assert path == tmp_path / SUMMARY_FILENAME
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["status"] == "host_busy"
    assert record["exit_code"] == 4
    assert record["run_id"] is None
    assert record["step_count"] == 0


def test_run_summary_atomic_write_no_partial_file(tmp_path: Path) -> None:
    """A successful flush leaves no .tmp files behind."""
    run_root = tmp_path / "artifacts" / "runs" / "20260518-000002-atomic"
    run_root.mkdir(parents=True)

    writer = RunSummaryWriter(base_dir=tmp_path)
    writer.flush(status="success", exit_code=0)

    leftover_tmps = list(run_root.glob(".run.json.*.tmp"))
    assert leftover_tmps == []


def test_run_summary_counts_step_idxs_from_action_log(tmp_path: Path) -> None:
    """step_count is recovered from distinct step_idx values in
    step-*.jsonl files (no recipe coupling required)."""
    run_root = tmp_path / "artifacts" / "runs" / "20260518-000003-count"
    action_log = run_root / "artifacts" / "action-log"
    action_log.mkdir(parents=True)
    (action_log / "step-dispatched.jsonl").write_text(
        '{"step_idx": 0, "step_name": "a"}\n'
        '{"step_idx": 1, "step_name": "b"}\n'
        '{"step_idx": 2, "step_name": "c"}\n',
        encoding="utf-8",
    )

    writer = RunSummaryWriter(base_dir=tmp_path)
    writer.flush(status="success", exit_code=0)
    record = json.loads(
        (run_root / SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    assert record["step_count"] == 3


def test_run_summary_writer_does_not_raise_when_target_unwritable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A writer failure must not mask the caller's exit code —
    the writer logs to stderr and returns the intended path."""
    writer = RunSummaryWriter(base_dir=tmp_path)
    with patch(
        "coord_smith.graph.run_summary._atomic_write_json",
        side_effect=OSError("disk full"),
    ):
        # Must not raise.
        path = writer.flush(status="success", exit_code=0)

    err = capsys.readouterr().err
    assert "run-summary write failed" in err
    assert path.name == SUMMARY_FILENAME


def test_main_writes_run_json_on_normal_exit(tmp_path: Path) -> None:
    """The CLI's main() flushes run.json regardless of exit path —
    here, the happy path."""
    # Drop us into tmp_path so main's base_dir is the test sandbox.
    import os

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with patch(
            "coord_smith.graph.pyautogui_cli_entrypoint._run",
            new_callable=AsyncMock,
            return_value=0,
        ):
            exit_code = main(argv=[])
        assert exit_code == 0
        assert (tmp_path / SUMMARY_FILENAME).is_file()
        record = json.loads(
            (tmp_path / SUMMARY_FILENAME).read_text(encoding="utf-8")
        )
        assert record["status"] == "success"
        assert record["exit_code"] == 0
    finally:
        os.chdir(cwd)


def test_main_writes_run_json_on_keyboard_interrupt(tmp_path: Path) -> None:
    """run.json must be written on Ctrl-C / SIGINT (try/finally)."""
    import os

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        async def _interrupt(*_a: object, **_kw: object) -> int:
            raise KeyboardInterrupt()

        with patch(
            "coord_smith.graph.pyautogui_cli_entrypoint._run",
            side_effect=_interrupt,
        ):
            exit_code = main(argv=[])
        assert exit_code == 1
        summary = json.loads(
            (tmp_path / SUMMARY_FILENAME).read_text(encoding="utf-8")
        )
        assert summary["status"] == "interrupted"
        assert summary["exit_code"] == 1
    finally:
        os.chdir(cwd)
