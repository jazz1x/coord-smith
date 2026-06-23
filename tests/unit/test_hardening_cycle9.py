"""Regression tests for adversarial hardening CYCLE 9.

Cycle 9 ran on the post-cleanup codebase and surfaced issues 8 prior cycles
missed (convergence was premature). Most important: a CONCURRENT run.json
clobber — the residual hole in cycle-5's name-snapshot fix. The writer now uses
an ownership model (set_own_run_root) instead of resolving a root by mtime.

See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from coord_smith.config.click_recipe import load_click_recipe
from coord_smith.graph.released_run_root import generate_run_id
from coord_smith.reporting.run_summary import RunSummaryWriter

_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# run-json-concurrent-root-clobber — a host-busy invocation must not overwrite
# a CONCURRENT lock-holder's run.json (root created AFTER the host-busy writer
# started — the case the old newest-by-mtime + name-snapshot heuristic missed).
# ---------------------------------------------------------------------------


def test_host_busy_does_not_clobber_concurrent_lock_holders_root(
    tmp_path: Path,
) -> None:
    # Invocation B's writer starts FIRST (before lock-holder A's root exists).
    writer_b = RunSummaryWriter(base_dir=tmp_path)

    # Concurrent A then creates its root and writes its own success run.json.
    a_root = tmp_path / "artifacts" / "runs" / "20260101-000000-aaaaaaaa"
    a_root.mkdir(parents=True)
    a_summary = a_root / "run.json"
    a_summary.write_text(
        json.dumps(
            {"run_id": a_root.name, "status": "success", "exit_code": 0}
        ),
        encoding="utf-8",
    )

    # B times out on the lock -> host_busy flush. B never claimed a root.
    target_b, _ = writer_b.flush(status="host_busy", exit_code=4)

    # B writes a degenerate base_dir/run.json, NOT into A's root.
    assert target_b == tmp_path / "run.json"
    assert target_b != a_summary
    # A's success outcome survives intact (not clobbered with host_busy/exit 4).
    a_record = json.loads(a_summary.read_text(encoding="utf-8"))
    assert a_record["status"] == "success"
    assert a_record["exit_code"] == 0
    assert a_record["run_id"] == a_root.name


# ---------------------------------------------------------------------------
# run-id-timezone-vs-utc-summary — run_id timestamp prefix must be UTC, the
# same time base as run.json started_at/ended_at and all action-log ts fields.
# ---------------------------------------------------------------------------


def test_run_id_prefix_is_utc() -> None:
    from datetime import UTC, datetime

    run_id = generate_run_id()
    # run_id is "<YYYYMMDD>-<HHMMSS>-<suffix>"; the date+time prefix must match
    # UTC now to the minute (avoids a flaky second-boundary race).
    prefix = "-".join(run_id.split("-")[:2])
    now_utc = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M")
    assert prefix.startswith(now_utc), (
        f"run_id prefix {prefix!r} must be UTC (~{now_utc}), not host-local"
    )


# ---------------------------------------------------------------------------
# broken-sample-recipes-missing-templates — pin the DOCUMENTED behavior of the
# docs/recipes samples on the real load_click_recipe() path (the suite
# previously only model_validate'd them, never resolving templates on disk).
# ---------------------------------------------------------------------------


def test_coord_sample_recipe_loads() -> None:
    """coord-click.yaml is self-contained (pure coords) and loads end-to-end."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)  # legacy missions: shape
        recipe = load_click_recipe(
            _REPO_ROOT / "docs" / "recipes" / "coord-click.yaml"
        )
    assert recipe.steps


@pytest.mark.parametrize(
    "sample",
    [
        "multi-step-flow.yaml",
        "multi-step-with-fallback.yaml",
        "multi-step-with-wait-for.yaml",
        "datepicker-pattern.yaml",
        "image-click.yaml",
        "image-click-with-signal.yaml",
    ],
)
def test_image_sample_recipes_load_with_placeholders(sample: str) -> None:
    """The image samples ship placeholder templates under docs/recipes/templates/
    so that `--dry-run` validation succeeds out of the box. load_click_recipe must
    resolve those templates and produce a non-empty step list."""
    path = _REPO_ROOT / "docs" / "recipes" / sample
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        recipe = load_click_recipe(path)
    assert recipe.steps
