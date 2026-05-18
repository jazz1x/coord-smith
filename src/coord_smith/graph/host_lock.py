"""Per-host advisory lock to prevent concurrent coord-smith invocations.

PyAutoGUI is process-global on a given host: there is exactly one
cursor and one screen for the entire OS, and every running pyautogui
client shares them. Two coord-smith processes running simultaneously
would interleave clicks, race on the preflight cursor probe, and
produce screenshots that capture each other's mid-flight cursor
positions — silent corruption with no diagnostic path.

This module implements a single-process gate via ``fcntl.flock`` on
a well-known path. The lock is advisory (cooperating processes
respect it; uncooperative software still wins) which is exactly the
right semantics: we want OpenClaw and other coord-smith invocations
to coordinate, not to defend against malicious neighbours.

Behaviour:

- ``acquire_host_lock(base_dir, timeout=...)`` returns a context
  manager. On entry it tries to grab the lock at
  ``base_dir/artifacts/.coord-smith.lock``. If the lock is taken,
  it retries every 100 ms until ``timeout`` elapses, then raises
  :class:`HostBusyError`.
- On exit (normal or exceptional) the lock is released. The lock
  file itself is left behind — it has no meaningful contents, only
  the OS-level lock state matters.
- Non-Unix platforms: ``fcntl`` is Unix-only. On platforms that
  don't expose it, the lock becomes a no-op with a single stderr
  warning the first time it is requested. coord-smith targets
  macOS today; the no-op keeps the path callable for future
  Linux work without a hard import error and explicitly tells the
  operator there is no concurrency guarantee.

The lock is per ``base_dir``, not per host strictly — if a caller
runs coord-smith against two different ``base_dir`` arguments
concurrently, they will NOT contend. This is intentional: a
``base_dir`` change usually means the caller wants isolation
(separate workspaces, separate tests). The real-world enemy is
two callers using the *same* artifact tree, which is exactly the
case the lock catches.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl

    _HAVE_FCNTL = True
except ImportError:  # pragma: no cover — Windows / niche platforms
    _HAVE_FCNTL = False


_LOCK_FILENAME = ".coord-smith.lock"
_DEFAULT_TIMEOUT_SECONDS = 10.0
_POLL_INTERVAL_SECONDS = 0.1

_warned_no_fcntl = False


class HostBusyError(RuntimeError):
    """Another coord-smith process holds the per-host lock.

    The CLI maps this to exit code 4 so the caller (e.g. OpenClaw)
    can back off and retry. The error message names the lock path
    so operators can investigate stuck locks.
    """


@contextmanager
def acquire_host_lock(
    *,
    base_dir: Path,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Generator[Path]:
    """Acquire (or fail) the per-host advisory lock for ``base_dir``.

    Yields the lock file path on success so callers can include it
    in diagnostics. Raises :class:`HostBusyError` after
    ``timeout_seconds`` if the lock cannot be obtained.

    On non-Unix hosts where ``fcntl`` is unavailable, this is a
    no-op (with a one-shot stderr warning) — the path is yielded
    immediately and no real lock is taken.
    """
    lock_dir = base_dir / "artifacts"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / _LOCK_FILENAME

    if not _HAVE_FCNTL:
        global _warned_no_fcntl
        if not _warned_no_fcntl:
            print(
                "coord-smith: warning — fcntl unavailable on this platform; "
                "host-lock is a no-op. Concurrent invocations are NOT "
                "prevented.",
                file=sys.stderr,
            )
            _warned_no_fcntl = True
        yield lock_path
        return

    # Open in append mode so we don't truncate the previous holder's
    # bookkeeping if any. The file's *contents* are irrelevant; only
    # the OS-level lock matters.
    fd = lock_path.open("a")
    deadline = time.monotonic() + timeout_seconds
    try:
        while True:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break  # got it
            except OSError:
                if time.monotonic() >= deadline:
                    raise HostBusyError(
                        f"another coord-smith process holds the host lock "
                        f"at {lock_path} (waited {timeout_seconds:.1f}s). "
                        "PyAutoGUI is process-global on this host; running "
                        "two coord-smith invocations at once would interleave "
                        "clicks and screenshots. Wait for the other run to "
                        "finish, or split work across separate base-dir "
                        "trees if isolation is acceptable."
                    ) from None
                time.sleep(_POLL_INTERVAL_SECONDS)
        try:
            yield lock_path
        finally:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                # Best-effort release; the OS will reclaim the lock
                # when the fd closes anyway.
                pass
    finally:
        fd.close()
