"""Hardening cycle 11 — adversarial SOLO sweep regression tests.

Cycle 11 re-swept the whole core after the cycles 9–10 + gap-fill refactors.
The gate was clean (446 tests, mypy/ruff/import-linter all green) and the sweep
surfaced exactly one LOW usability gap:

    ``--max-runs`` / ``--max-age-days`` are accepted as known flags (so
    ``_reject_unknown_flags`` does not reject them) but only take effect under
    ``--cleanup``. On a normal dispatch run the released-input shim drops them
    silently via ``parse_known_args`` — a confusing no-op that violates the
    project's loud-on-misuse ethos (recipe ``extra="forbid"``,
    ``_reject_unknown_flags``, hard-fail ``--target-window``) and was asymmetric
    with ``_run_cleanup``'s existing co-flag warning for the reverse misuse.

main() now warns when those bounds appear without ``--cleanup``. These tests pin
the warning, its absence on the legitimate ``--cleanup`` path, and the detector.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from coord_smith.graph.pyautogui_cli_entrypoint import (
    _cleanup_only_flags_present,
    main,
)

_INPUTS = [
    "--session-ref", "s",
    "--expected-auth-state", "a",
    "--target-page-url", "https://example.com",
    "--site-identity", "example",
]


def test_max_runs_without_cleanup_warns_on_dispatch_run(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """--max-runs on a normal run is inert; main() must warn, not silently drop.

    Uses --dry-run so the run validates and exits 0 WITHOUT preflight (no OS
    permissions needed): the warning fires in main() before _run, so a dry-run
    is a sufficient and permission-free vehicle to observe it.
    """
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger="coord_smith.cli"):
            exit_code = main(argv=["--dry-run", "--max-runs", "5", *_INPUTS])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    assert any(
        "only take effect with --cleanup" in record.getMessage()
        for record in caplog.records
    )


def test_max_age_days_equals_spelling_also_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The ``--flag=value`` spelling is detected too (split on '=')."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger="coord_smith.cli"):
            exit_code = main(argv=["--dry-run", "--max-age-days=7", *_INPUTS])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    assert any(
        "only take effect with --cleanup" in record.getMessage()
        for record in caplog.records
    )


def test_cleanup_with_max_runs_does_not_emit_stray_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The legitimate ``--cleanup --max-runs`` use must NOT trip the warning.

    --cleanup short-circuits in main() before the stray-flag check, so the
    bound is consumed normally. Guards the new warning against false positives
    on its own happy path.
    """
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger="coord_smith.cli"):
            exit_code = main(argv=["--cleanup", "--max-runs", "5"])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    assert not any(
        "only take effect with --cleanup" in record.getMessage()
        for record in caplog.records
    )


def test_normal_run_without_bounds_does_not_warn(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A dispatch run that passes neither bound stays silent (no false positive)."""
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with caplog.at_level(logging.WARNING, logger="coord_smith.cli"):
            exit_code = main(argv=["--dry-run", *_INPUTS])
    finally:
        os.chdir(old_cwd)

    assert exit_code == 0
    assert not any(
        "only take effect with --cleanup" in record.getMessage()
        for record in caplog.records
    )


def test_cleanup_only_flags_present_detects_both_spellings() -> None:
    """Unit-level: detector finds both ``--flag value`` and ``--flag=value``."""
    assert _cleanup_only_flags_present(["--max-runs", "5"]) == ["--max-runs"]
    assert _cleanup_only_flags_present(["--max-age-days=7"]) == ["--max-age-days=7"]
    assert _cleanup_only_flags_present(
        ["--max-runs", "5", "--max-age-days", "7"]
    ) == ["--max-runs", "--max-age-days"]


def test_cleanup_only_flags_present_ignores_unrelated_flags() -> None:
    """Detector does not flag the bound *values* or unrelated flags."""
    assert _cleanup_only_flags_present(["--session-ref", "s", "5", "7"]) == []
    assert _cleanup_only_flags_present(["--dry-run", "--target-page-url", "u"]) == []
