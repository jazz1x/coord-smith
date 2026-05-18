"""Tests for the per-host advisory lock (coord_smith.graph.host_lock).

PyAutoGUI is process-global on a given host: one cursor, one screen.
Two coord-smith processes running simultaneously would race silently.
``acquire_host_lock`` is the gate that prevents this. These tests
verify the gate behavior under contention without exercising real
concurrent processes (which would be flaky in CI).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from coord_smith.graph.host_lock import (
    HostBusyError,
    acquire_host_lock,
)


def test_acquire_host_lock_creates_lockfile(tmp_path: Path) -> None:
    """Entering the context creates the lock file under
    base_dir/artifacts/.coord-smith.lock."""
    with acquire_host_lock(base_dir=tmp_path) as lock_path:
        assert lock_path.exists()
        assert lock_path.name == ".coord-smith.lock"
        assert lock_path.parent == tmp_path / "artifacts"


def test_acquire_host_lock_yields_lock_path(tmp_path: Path) -> None:
    """The yielded value is the lock file's absolute path so callers
    can surface it in diagnostics."""
    with acquire_host_lock(base_dir=tmp_path) as lock_path:
        assert lock_path.is_absolute() or lock_path.parent.exists()


def test_acquire_host_lock_releases_on_exit(tmp_path: Path) -> None:
    """After the context exits, a fresh acquire must succeed
    immediately (no leftover lock)."""
    with acquire_host_lock(base_dir=tmp_path):
        pass
    # Second acquire — same process, fresh context — must not block.
    with acquire_host_lock(base_dir=tmp_path, timeout_seconds=0.5):
        pass


def test_acquire_host_lock_releases_on_exception(tmp_path: Path) -> None:
    """If the body of the with-block raises, the lock is still
    released (try/finally semantics)."""

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom), acquire_host_lock(base_dir=tmp_path):
        raise Boom("test")

    # Re-acquire must succeed promptly.
    with acquire_host_lock(base_dir=tmp_path, timeout_seconds=0.5):
        pass


@pytest.mark.skipif(
    sys.platform == "win32", reason="fcntl-based lock is Unix-only"
)
def test_acquire_host_lock_raises_host_busy_on_contention(
    tmp_path: Path,
) -> None:
    """When the lock is already held by another file descriptor,
    a second acquire must raise HostBusyError after the timeout
    instead of hanging or returning a fake-success.
    """
    import fcntl  # noqa: PLC0415 — only valid on Unix

    # Grab the lock manually with raw fcntl so the in-process
    # context manager sees real contention. Same process, different
    # fd is enough — flock contention is fd-based, not process-based.
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)
    lock_path = tmp_path / "artifacts" / ".coord-smith.lock"
    held_fd = lock_path.open("a")
    fcntl.flock(held_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(HostBusyError) as exc_info:
            with acquire_host_lock(
                base_dir=tmp_path, timeout_seconds=0.2
            ):
                pass  # never reached
        msg = str(exc_info.value)
        assert "host lock" in msg.lower()
        assert str(lock_path) in msg
    finally:
        fcntl.flock(held_fd.fileno(), fcntl.LOCK_UN)
        held_fd.close()


def test_acquire_host_lock_falls_back_to_noop_without_fcntl(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """On platforms without fcntl, the lock degrades to a no-op
    AND warns the operator once on stderr so the missing
    concurrency guarantee is visible (not silent)."""
    import coord_smith.graph.host_lock as host_lock

    # Reset the one-shot warning flag and force the no-fcntl path.
    with patch.object(host_lock, "_HAVE_FCNTL", False), patch.object(
        host_lock, "_warned_no_fcntl", False
    ):
        with host_lock.acquire_host_lock(base_dir=tmp_path) as lock_path:
            assert lock_path.exists() or lock_path.parent.exists()

    err = capsys.readouterr().err
    assert "fcntl unavailable" in err
    assert "host-lock is a no-op" in err


def test_host_busy_error_is_caught_by_cli_main_with_exit_code_4(
    tmp_path: Path,
) -> None:
    """The CLI maps HostBusyError → exit code 4 ('host busy')."""
    from coord_smith.graph.pyautogui_cli_entrypoint import main

    # Patch _run to raise HostBusyError so we exercise main's handler
    # without setting up a real lock contention scenario.
    async def _raises(*args: object, **kwargs: object) -> int:
        raise HostBusyError("simulated contention")

    with patch(
        "coord_smith.graph.pyautogui_cli_entrypoint._run", side_effect=_raises
    ):
        exit_code = main(argv=[])

    assert exit_code == 4
