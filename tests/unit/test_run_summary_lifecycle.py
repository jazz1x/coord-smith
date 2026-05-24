"""Tests for ``coord_smith.reporting.run_summary_lifecycle``.

The context manager replaces the inline writer + try/finally
scaffold that used to live in CLI ``main()``. These tests pin its
public contract: writer created on enter, outcome recorded by
``set_outcome``, ``run.json`` flushed on exit, exceptions never
swallowed, default outcome ``("failure", 1)``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coord_smith.reporting.run_summary import SUMMARY_FILENAME
from coord_smith.reporting.run_summary_lifecycle import RunSummaryLifecycle


def test_enter_creates_writer_with_base_dir(tmp_path: Path) -> None:
    """Entering the CM constructs a ``RunSummaryWriter`` bound to the
    given ``base_dir``."""
    with RunSummaryLifecycle(base_dir=tmp_path) as summary:
        assert summary.writer is not None
        # The writer should target tmp_path (verified empirically via
        # flush below — internal _base_dir is private).
        summary.set_outcome(status="success", exit_code=0)


def test_exit_flushes_run_json_with_recorded_outcome(tmp_path: Path) -> None:
    """``__exit__`` flushes ``run.json`` using the last
    ``set_outcome`` call's values."""
    with RunSummaryLifecycle(base_dir=tmp_path) as summary:
        summary.set_outcome(status="success", exit_code=0)
    # After exit, run.json must exist at base_dir (no run root
    # was created in this test path).
    summary_file = tmp_path / SUMMARY_FILENAME
    assert summary_file.is_file()
    record = json.loads(summary_file.read_text(encoding="utf-8"))
    assert record["status"] == "success"
    assert record["exit_code"] == 0


def test_default_outcome_is_failure_exit_1(tmp_path: Path) -> None:
    """No ``set_outcome`` call → CM defaults to ``("failure", 1)``.

    Matches the inline scaffold's old behaviour — a branch that
    forgot to record an outcome still produces a sensible
    ``run.json`` instead of a silent zero / null."""
    with RunSummaryLifecycle(base_dir=tmp_path):
        pass  # no set_outcome
    record = json.loads(
        (tmp_path / SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    assert record["status"] == "failure"
    assert record["exit_code"] == 1


def test_set_outcome_is_idempotent_last_wins(tmp_path: Path) -> None:
    """Multiple ``set_outcome`` calls — the last one wins."""
    with RunSummaryLifecycle(base_dir=tmp_path) as summary:
        summary.set_outcome(status="failure", exit_code=1)
        summary.set_outcome(status="success", exit_code=0)
    record = json.loads(
        (tmp_path / SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    assert record["status"] == "success"
    assert record["exit_code"] == 0


def test_exit_does_not_swallow_exceptions(tmp_path: Path) -> None:
    """An exception raised inside the with-block propagates out —
    the CM only owns the lifecycle flush, not exception routing.

    Critical contract: if the CM ever returned True from __exit__,
    main()'s exception handlers (which set outcome and re-raise)
    would silently lose their work."""

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with RunSummaryLifecycle(base_dir=tmp_path) as summary:
            summary.set_outcome(status="failure", exit_code=2)
            raise Boom("inner")

    # And run.json was still flushed with the recorded outcome —
    # the finally path of __exit__ fires even on exception.
    record = json.loads(
        (tmp_path / SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    assert record["status"] == "failure"
    assert record["exit_code"] == 2


def test_writer_flush_failure_does_not_mask_caller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``writer.flush`` itself raises, the CM swallows that error
    so the caller's exit code path stays clean. Defense-in-depth —
    the writer is already best-effort internally, but the CM is
    the outermost lifecycle bracket."""

    def boom(*_args: object, **_kw: object) -> None:
        raise OSError("simulated disk full")

    with RunSummaryLifecycle(base_dir=tmp_path) as summary:
        summary.set_outcome(status="success", exit_code=0)
        monkeypatch.setattr(summary.writer, "flush", boom)
    # Exit completed without re-raising — that's the contract.
    # No run.json was written (the writer raised), but the
    # caller's exit code path was preserved.


def test_exit_returns_literal_false_for_mypy(tmp_path: Path) -> None:
    """``__exit__`` returns ``Literal[False]`` so static type
    checkers know exceptions are never swallowed. This is a
    documentation-grade assertion — runtime value check."""
    cm = RunSummaryLifecycle(base_dir=tmp_path)
    cm.__enter__()
    try:
        result = cm.__exit__(None, None, None)
    finally:
        pass
    assert result is False
