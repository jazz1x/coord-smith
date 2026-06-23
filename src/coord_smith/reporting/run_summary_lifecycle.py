"""Run-summary lifecycle context manager — extracted from CLI main (B-CA-5).

The CLI entrypoint's ``main()`` had a 60-line scaffold that:

1. Created a ``RunSummaryWriter`` bound to the resolved base_dir.
2. Initialised ``exit_code: int = 1`` and ``status: RunStatus = "failure"``
   as mutable scope variables.
3. Wrapped the entire ``asyncio.run(_run(...))`` call in try/except/finally.
4. Each except branch reassigned ``(status, exit_code)`` before
   returning.
5. The ``finally`` flushed ``run.json`` with whatever those
   variables ended up being.

C19 Clean Architecture pass #2 finding CA-A3 (MED) flagged this
as "hybrid CLI router + reporting driver" — main() had two
concerns (route the CLI command + drive the run-summary lifecycle)
that should be separable.

This module owns the lifecycle. ``RunSummaryLifecycle`` is a
context manager that:

- Constructs the ``RunSummaryWriter`` on ``__enter__``.
- Exposes the writer for handoff into ``_run`` (so the dry-run
  step-count override path still works).
- Exposes ``set_outcome(status, exit_code)`` so each branch in
  main's try/except can declare its result without managing the
  writer directly.
- Calls ``writer.flush(...)`` on ``__exit__`` regardless of
  exception, with whatever outcome the inner code declared.
  Default outcome — set when no branch called ``set_outcome``
  — is ``("failure", 1)`` so a path that forgets to declare
  still produces a sensible run.json instead of silent zero.

The CM does NOT swallow exceptions; it returns ``False`` from
``__exit__`` so caller-side exception handling stays in
``main()``. The CM only owns the lifecycle; routing decisions
stay where they belong.
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Literal, Self

from coord_smith.reporting.run_summary import RunStatus, RunSummary, RunSummaryWriter


class RunSummaryLifecycle:
    """Context manager that brackets a coord-smith dispatch run.

    Usage in ``main()``::

        with RunSummaryLifecycle(base_dir=base_dir) as summary:
            try:
                exit_code = asyncio.run(_run(
                    argv=argv_list,
                    base_dir=base_dir,
                    summary_writer=summary.writer,
                ))
                summary.set_outcome(
                    status="success" if exit_code == 0 else "failure",
                    exit_code=exit_code,
                )
                return exit_code
            except KeyboardInterrupt:
                summary.set_outcome(status="interrupted", exit_code=1)
                return 1
            # ... etc

    On context exit the writer flushes ``run.json`` with the last
    outcome the inner code declared. If no ``set_outcome`` call
    fired (e.g. a branch returned without recording one), the
    default ``("failure", 1)`` is written — same "fail-safe"
    behaviour the old inline pattern had.
    """

    def __init__(self, *, base_dir: Path) -> None:
        self._base_dir = base_dir
        self.writer: RunSummaryWriter
        self._status: RunStatus = "failure"
        self._exit_code: int = 1
        self.last_summary_path: Path | None = None
        self.last_summary: RunSummary | None = None

    def __enter__(self) -> Self:
        """Create the writer; return self so callers reach
        ``self.writer`` and ``self.set_outcome``."""
        self.writer = RunSummaryWriter(base_dir=self._base_dir)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        """Flush ``run.json`` with the recorded outcome.

        Always returns ``Literal[False]`` — the CM **never** swallows
        exceptions. Exception routing stays in ``main()``; the
        CM only owns the run-summary write. ``Literal[False]``
        (rather than ``bool``) makes the contract explicit to
        mypy.
        """
        # Best-effort: a writer failure must not mask the
        # caller's exit code. The writer itself logs and
        # returns the intended path without raising (see
        # ``RunSummaryWriter._atomic_write_json``); we still
        # wrap in try/except as defense-in-depth.
        try:
            path, summary = self.writer.flush(
                status=self._status, exit_code=self._exit_code
            )
            self.last_summary_path = path
            self.last_summary = summary
        except Exception:  # noqa: BLE001 — lifecycle exit must not raise
            pass
        return False

    def set_outcome(self, *, status: RunStatus, exit_code: int) -> None:
        """Record the outcome the next ``__exit__`` will flush.

        Idempotent — calling it multiple times overwrites; the last
        call wins. Each except branch in ``main()`` calls this
        exactly once before returning.
        """
        self._status = status
        self._exit_code = exit_code
