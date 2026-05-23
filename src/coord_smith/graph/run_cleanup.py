"""Disk rotation for ``artifacts/runs/`` — bounded by age and count.

Each coord-smith invocation produces a fresh ``artifacts/runs/<run_id>/``
directory containing screenshots (~5–10 MB each on a Retina display)
plus action-log JSONL files. Without rotation, 100 invocations per
day fill a developer laptop's disk within days. The
production-gaps audit (Theme C) tagged this as a P1 ops gap.

This module implements a simple retention helper:

- ``max_age_days``: prune runs older than N days (by mtime of the run
  root directory). Default ``14``.
- ``max_runs``: keep at most N most-recent runs; older ones are
  pruned. Default ``100``.

Both bounds apply: a run is kept ONLY if it satisfies both
(under-N-days AND in-the-newest-K). Pruning is best-effort —
unreadable directories are skipped with a log warning, not raised.

The helper is exposed via:

- ``coord-smith --cleanup`` — manual one-shot invocation. Reads
  ``--max-runs`` / ``--max-age-days`` flags, with sensible defaults.
- Future: opportunistic auto-cleanup after a successful run
  (deferred until usage data justifies the call-site complexity).

The helper does NOT touch:

- ``artifacts/runs/`` itself (only its children).
- The host lock file (``artifacts/.coord-smith.lock``) — it lives
  outside ``runs/`` and is created fresh each invocation.
- Run roots that include a ``.keep`` sentinel file (operator
  pin — useful when investigating a specific failed run).
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from coord_smith.cli_logging import get_logger

_log = get_logger("cleanup")

DEFAULT_MAX_AGE_DAYS = 14
DEFAULT_MAX_RUNS = 100
KEEP_SENTINEL = ".keep"

# Run-root names follow ``YYYYMMDD-HHMMSS-<uuid8>``; the prefix sorts
# chronologically so name-based ordering is equivalent to mtime in
# the absence of clock skew. We still use mtime as the source of
# truth (handles imported / hand-edited dirs).


@dataclass(frozen=True, slots=True)
class CleanupReport:
    """Summary of a cleanup pass.

    Caller (CLI or future auto-cleanup) prints this so operators
    have a record of what was removed.
    """

    scanned: int
    removed: int
    kept: int
    skipped: int  # protected by ``.keep`` sentinel
    errors: int
    bytes_freed: int

    def summary_line(self) -> str:
        return (
            f"scanned={self.scanned} removed={self.removed} "
            f"kept={self.kept} skipped={self.skipped} "
            f"errors={self.errors} "
            f"freed={self.bytes_freed / (1024 * 1024):.1f} MiB"
        )


def _dir_size_bytes(path: Path) -> int:
    """Best-effort recursive size in bytes. Returns 0 on any I/O
    error — sizing is reporting-only, never gating."""
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _has_keep_sentinel(run_root: Path) -> bool:
    """Operators can pin a run by touching ``.keep`` inside it.
    Cleanup never removes pinned runs."""
    return (run_root / KEEP_SENTINEL).is_file()


def cleanup_runs(
    *,
    base_dir: Path,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    max_runs: int = DEFAULT_MAX_RUNS,
    now_seconds: float | None = None,
) -> CleanupReport:
    """Prune ``base_dir/artifacts/runs/`` to fit the bounds.

    Rules:

    1. A run with a ``.keep`` file in its root is never removed.
    2. Otherwise, a run is removed if either:
       - it is older than ``max_age_days`` (by mtime), OR
       - it is not among the ``max_runs`` most recent runs.

    Both checks are inclusive of the boundary — exactly N runs and
    exactly N days old are kept.

    ``now_seconds`` lets tests inject a deterministic clock.
    """
    runs_dir = base_dir / "artifacts" / "runs"
    if not runs_dir.is_dir():
        return CleanupReport(0, 0, 0, 0, 0, 0)

    candidates: list[tuple[Path, float]] = []
    skipped = 0
    errors = 0
    try:
        for entry in runs_dir.iterdir():
            if not entry.is_dir():
                continue
            if _has_keep_sentinel(entry):
                skipped += 1
                continue
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                errors += 1
                continue
            candidates.append((entry, mtime))
    except OSError as exc:
        _log.warning("cleanup: failed to list %s: %s", runs_dir, exc)
        return CleanupReport(0, 0, 0, skipped, 1, 0)

    # Sort newest first so the count-based cutoff is easy.
    candidates.sort(key=lambda pair: pair[1], reverse=True)

    now = now_seconds if now_seconds is not None else time.time()
    age_cutoff = now - max_age_days * 24 * 3600

    to_remove: list[Path] = []
    kept_count = 0
    for idx, (path, mtime) in enumerate(candidates):
        over_count = idx >= max_runs
        too_old = mtime < age_cutoff
        if over_count or too_old:
            to_remove.append(path)
        else:
            kept_count += 1

    bytes_freed = 0
    removed = 0
    for path in to_remove:
        size = _dir_size_bytes(path)
        try:
            shutil.rmtree(path)
            removed += 1
            bytes_freed += size
        except OSError as exc:
            _log.warning("cleanup: failed to remove %s: %s", path, exc)
            errors += 1

    scanned = len(candidates) + skipped
    return CleanupReport(
        scanned=scanned,
        removed=removed,
        kept=kept_count,
        skipped=skipped,
        errors=errors,
        bytes_freed=bytes_freed,
    )
