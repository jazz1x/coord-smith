"""Tests for graph.run_cleanup — disk rotation policy."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from coord_smith.graph.run_cleanup import (
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MAX_RUNS,
    KEEP_SENTINEL,
    cleanup_runs,
)


def _make_run(
    base_dir: Path, name: str, *, age_days: float = 0.0
) -> Path:
    """Create a fake run root with optional backdated mtime."""
    run_root = base_dir / "artifacts" / "runs" / name
    run_root.mkdir(parents=True)
    # Drop a small file inside so size accounting is non-zero.
    (run_root / "marker.txt").write_text("x" * 100, encoding="utf-8")
    if age_days > 0:
        target_mtime = time.time() - age_days * 24 * 3600
        os.utime(run_root, (target_mtime, target_mtime))
    return run_root


# ---- Empty / missing tree --------------------------------------


def test_cleanup_returns_zero_report_when_no_runs_dir(tmp_path: Path) -> None:
    """A base_dir without artifacts/runs/ is a no-op, not an error."""
    report = cleanup_runs(base_dir=tmp_path)
    assert report.scanned == 0
    assert report.removed == 0


def test_cleanup_returns_zero_report_when_runs_dir_empty(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "runs").mkdir(parents=True)
    report = cleanup_runs(base_dir=tmp_path)
    assert report.scanned == 0


# ---- Max-runs bound ---------------------------------------------


def test_cleanup_keeps_newest_max_runs(tmp_path: Path) -> None:
    """When max_runs=3 and 5 runs exist, the 2 oldest are pruned."""
    # Create with explicit increasing mtime via small sleeps so the
    # "newest" ordering is deterministic.
    paths = []
    now = time.time()
    for i in range(5):
        p = _make_run(tmp_path, f"run-{i}", age_days=0)
        # Force monotonically increasing mtime.
        mtime = now - (5 - i)
        os.utime(p, (mtime, mtime))
        paths.append(p)

    report = cleanup_runs(base_dir=tmp_path, max_runs=3, max_age_days=999)
    assert report.removed == 2
    assert report.kept == 3
    # The two oldest are gone.
    assert not paths[0].exists()
    assert not paths[1].exists()
    # The three newest remain.
    assert paths[2].exists()
    assert paths[3].exists()
    assert paths[4].exists()


# ---- Max-age bound ----------------------------------------------


def test_cleanup_prunes_old_runs(tmp_path: Path) -> None:
    """Runs older than max_age_days are removed even when under
    max_runs cap."""
    fresh = _make_run(tmp_path, "fresh", age_days=0)
    old = _make_run(tmp_path, "old", age_days=30)

    report = cleanup_runs(
        base_dir=tmp_path, max_runs=999, max_age_days=14
    )
    assert report.removed == 1
    assert fresh.exists()
    assert not old.exists()


# ---- Both bounds apply ------------------------------------------


def test_cleanup_combines_both_bounds(tmp_path: Path) -> None:
    """A run kept by max_runs but failing max_age_days is still
    removed — both bounds must be satisfied to retain."""
    new = _make_run(tmp_path, "new", age_days=0)
    too_old = _make_run(tmp_path, "too-old", age_days=60)

    report = cleanup_runs(
        base_dir=tmp_path, max_runs=10, max_age_days=14
    )
    assert too_old not in [p for p in (tmp_path / "artifacts" / "runs").iterdir()]
    assert new.exists()
    assert report.removed == 1


# ---- .keep sentinel ---------------------------------------------


def test_cleanup_never_removes_pinned_run(tmp_path: Path) -> None:
    """A `.keep` file inside a run root pins it from removal even
    when it violates both bounds."""
    pinned = _make_run(tmp_path, "pinned", age_days=999)
    (pinned / KEEP_SENTINEL).write_text("", encoding="utf-8")

    report = cleanup_runs(
        base_dir=tmp_path, max_runs=0, max_age_days=1
    )
    assert pinned.exists()
    assert report.removed == 0
    assert report.skipped == 1


# ---- Report fields ----------------------------------------------


def test_cleanup_report_counts_bytes_freed(tmp_path: Path) -> None:
    """The report records bytes freed for operator visibility."""
    old = _make_run(tmp_path, "old", age_days=0)
    # Drop a bigger file so the count is non-trivial. Backdate AFTER
    # the write so the file modification doesn't advance the dir mtime.
    (old / "screenshot.png").write_bytes(b"x" * 50_000)
    target_mtime = time.time() - 30 * 24 * 3600
    os.utime(old, (target_mtime, target_mtime))

    report = cleanup_runs(
        base_dir=tmp_path, max_runs=999, max_age_days=14
    )
    assert report.removed == 1
    assert report.bytes_freed >= 50_000


def test_cleanup_report_summary_line_format(tmp_path: Path) -> None:
    """summary_line emits the expected key=value contract."""
    report = cleanup_runs(base_dir=tmp_path)
    line = report.summary_line()
    for key in ("scanned=", "removed=", "kept=", "skipped=", "errors=", "freed="):
        assert key in line


# ---- Error handling --------------------------------------------


def test_cleanup_swallows_rmtree_failure(tmp_path: Path) -> None:
    """An OSError on a single rmtree must not abort the whole pass —
    other runs still get pruned."""
    a = _make_run(tmp_path, "a", age_days=30)
    b = _make_run(tmp_path, "b", age_days=30)

    real_rmtree = __import__("shutil").rmtree

    def flaky(path: object, *args: object, **kwargs: object) -> None:
        if str(path).endswith("a"):
            raise OSError("simulated")
        real_rmtree(path, *args, **kwargs)

    with patch("coord_smith.graph.run_cleanup.shutil.rmtree", side_effect=flaky):
        report = cleanup_runs(
            base_dir=tmp_path, max_runs=999, max_age_days=14
        )

    assert report.errors == 1
    assert report.removed == 1
    assert a.exists()  # the one that errored
    assert not b.exists()  # the other one is gone


# ---- CLI integration -------------------------------------------


def test_cli_cleanup_flag_invokes_cleanup_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``coord-smith --cleanup`` short-circuits the normal run path
    and emits a summary line at INFO level."""
    import logging

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    # Set up a sandboxed cwd so main()'s Path(".").resolve() lands
    # inside the test tmp_path.
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    _make_run(tmp_path, "stale", age_days=60)
    try:
        with caplog.at_level(logging.INFO, logger="coord_smith.cleanup"):
            exit_code = main(argv=["--cleanup", "--max-age-days", "14"])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    summary_records = [
        r for r in caplog.records if "cleanup:" in r.getMessage()
    ]
    assert summary_records, "expected at least one cleanup summary record"


def test_cli_cleanup_rejects_negative_bounds(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A negative bound is operator nonsense — exit code 3 (config error)."""
    import logging

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.ERROR, logger="coord_smith.cli"):
            exit_code = main(argv=["--cleanup", "--max-runs", "-1"])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 3
    assert any(
        "must be >= 0" in record.getMessage() for record in caplog.records
    )


def test_cli_cleanup_uses_documented_defaults() -> None:
    """The CLI defaults match the documented values (--help, ADR text)."""
    assert DEFAULT_MAX_AGE_DAYS == 14
    assert DEFAULT_MAX_RUNS == 100
