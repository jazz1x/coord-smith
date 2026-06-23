"""Top-level run.json — single-file summary of a coord-smith invocation.

External orchestrators (e.g. OpenClaw) need a fast way to determine
whether a coord-smith run succeeded or failed without grepping the
N+2 JSONL files under ``artifacts/action-log/``. ``run.json`` is the
contract for that: one file, atomic write, present on every exit
path (success, typed failure, KeyboardInterrupt, host-busy).

The schema is documented in ``docs/recipe-guide.md §Run summary``.
Public callers MUST treat ``schema_version`` as the only field that
gates compatibility — additions are non-breaking, removals are.

This module deliberately does not extend the LangGraph runner's
result type. The summary is written from the CLI boundary as a
post-hoc envelope so:

- The summary fires even when the graph itself crashed (try/finally
  in ``main()``).
- The graph's internal types stay decoupled from the on-disk
  envelope contract.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from coord_smith.cli_logging import get_logger

_log = get_logger("run_summary")

SUMMARY_FILENAME = "run.json"
SCHEMA_VERSION = 1

# Closed enum of run.json ``status`` values. Documented in
# docs/recipe-guide.md §Run Summary Schema and consumed by
# external orchestrators (e.g. OpenClaw) for branching logic.
# Adding a new value here is a public-contract change — keep the
# docs and the schema_version bumped in lockstep.
RunStatus = Literal["success", "failure", "interrupted", "host_busy"]


@dataclass(frozen=True, slots=True)
class RunSummary:
    """In-memory shape of run.json.

    Built incrementally by :class:`RunSummaryWriter` and serialized
    on flush. Frozen + slotted so a malformed mutation is caught at
    write time, not at read time by some downstream parser.
    """

    schema_version: int
    run_id: str | None
    status: RunStatus
    exit_code: int
    started_at: str  # ISO 8601 UTC
    ended_at: str  # ISO 8601 UTC
    elapsed_seconds: float
    step_count: int
    failure: dict[str, Any] | None

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "step_count": self.step_count,
            "failure": self.failure,
        }


def _read_failure_record(run_root: Path) -> dict[str, Any] | None:
    """Return the first failure record from ``failure.jsonl`` if any."""
    failure_log = run_root / "artifacts" / "action-log" / "failure.jsonl"
    if not failure_log.is_file():
        return None
    text = failure_log.read_text(encoding="utf-8").strip()
    if not text:
        return None
    first_line = text.splitlines()[0]
    try:
        record = json.loads(first_line)
    except json.JSONDecodeError as exc:
        # failure.jsonl is supposed to be well-formed JSONL written by
        # the adapter; if the first line is malformed, something
        # unusual happened (truncated write, concurrent edit, manual
        # tampering). The summary writer falls back to a null
        # failure block — but we log the parse error so the operator
        # has a breadcrumb. Silent return-None hides real bugs.
        _log.warning(
            "could not parse first line of failure.jsonl at %s: %s",
            failure_log,
            exc,
        )
        return None
    if not isinstance(record, dict):
        return None
    return record


# The canonical per-step action-log files seeded by the released graph. The
# step-count recovery reads ONLY these — not a ``step-*.jsonl`` wildcard — so a
# user step named e.g. ``step-foo`` (its guard logs land in step-foo.jsonl via
# the underscore->hyphen mission-key fallback) can never contaminate the count.
# Owning the namespace explicitly removes the accidental safety the wildcard
# relied on (that guard-log records happen to omit ``step_idx`` today).
_CANONICAL_STEP_LOGS: tuple[str, ...] = (
    "step-observed.jsonl",
    "step-dispatched.jsonl",
    "step-captured.jsonl",
)


def _step_count_from_recipe(*, run_root: Path | None) -> int:
    """Best-effort step count recovered from the action-log artifacts.

    We could thread the recipe step count down from ``_run`` instead,
    but that ties the summary writer to the graph internals. Counting
    distinct ``step_idx`` values across the canonical per-step files is
    cheap and works equally well for success and failure paths.
    """
    if run_root is None:
        return 0
    action_log = run_root / "artifacts" / "action-log"
    if not action_log.is_dir():
        return 0
    step_idxs: set[int] = set()
    for name in _CANONICAL_STEP_LOGS:
        jsonl = action_log / name
        if not jsonl.is_file():
            continue
        try:
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if isinstance(record, dict) and "step_idx" in record:
                    idx = record["step_idx"]
                    if isinstance(idx, int):
                        step_idxs.add(idx)
        except (json.JSONDecodeError, OSError):
            continue
    return len(step_idxs)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically via tmp+rename so partial reads are impossible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".run.json.", dir=str(path.parent), suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


class RunSummaryWriter:
    """Records the start time and flushes a ``run.json`` at exit.

    Production wiring lives in :class:`RunSummaryLifecycle`, which constructs
    the writer at invocation start, exposes ``set_outcome(status, exit_code)``
    for each branch of ``main()``'s try/except, and calls ``flush`` exactly
    once on ``__exit__``. Callers do not invoke ``flush`` per-branch directly.

    The writer learns its run root by being handed it (``set_own_run_root``,
    threaded into the graph as ``on_run_root_created``) the moment the graph
    creates it — it never scans for one by mtime. The writer is intentionally
    tolerant of being flushed before any run root exists (recipe-load error,
    missing input, host-busy on the first lock attempt, interrupt before the
    graph started): in those cases ``run.json`` is written under ``base_dir/``
    instead of inside a run root, so the caller still has a single
    deterministic file to read.
    """

    def __init__(self, *, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._started_at_iso = datetime.now(tz=UTC).isoformat()
        self._started_at_mono = time.monotonic()
        # The run root THIS invocation created, claimed via set_own_run_root
        # the moment create_run_root runs (threaded as the on_run_root_created
        # callback). run.json is written into this root; when it stays None
        # (the invocation exited before creating a root — host-busy,
        # config/permission error, interrupt-before-graph), run.json is written
        # to a degenerate base_dir/run.json. The writer NEVER guesses a root by
        # mtime — under a shared base_dir that could attribute a concurrent
        # lock-holder's root to a host-busy invocation and clobber that run's
        # run.json (the ADR-006 outcome contract).
        self._own_run_root: Path | None = None
        # Optional step count override that the dry-run path can
        # stash during ``_run`` execution. ``flush`` reads this if
        # no explicit ``step_count_override`` argument is passed.
        # See class docstring for the dry-run UX rationale.
        self._pending_step_count: int | None = None

    def set_own_run_root(self, run_root: Path) -> None:
        """Claim the run root this invocation created.

        Threaded into the graph as the ``on_run_root_created`` callback and
        invoked the moment ``create_run_root`` runs — before any node executes,
        so a graph that raises mid-run still attributes its failure run.json to
        its own root. This is the ONLY way the writer learns its run root; it
        never scans ``artifacts/runs`` by mtime (unsafe under concurrent
        invocations sharing a ``base_dir``).
        """
        self._own_run_root = run_root

    def set_pending_step_count(self, count: int) -> None:
        """Stash a step count for the upcoming flush.

        Used by the CLI dry-run path: the recipe step count is known
        before any run root is created, but the writer's empirical
        recovery from action-log files would return 0 because the
        graph never ran. Setting this lets the run.json reflect the
        validated step count.
        """
        self._pending_step_count = count

    def flush(
        self,
        *,
        status: RunStatus,
        exit_code: int,
        run_root: Path | None = None,
        step_count_override: int | None = None,
    ) -> tuple[Path, RunSummary]:
        """Write the summary and return the path and the in-memory summary.

        Best-effort: a failure inside the writer must not mask the
        caller's exit code. The writer logs the error to stderr but
        does not raise.

        Returns the written path and the :class:`RunSummary` that was
        serialized. Callers that need structured access to the summary
        (e.g. the programmatic Python API) can use the returned object
        instead of re-reading ``run.json`` from disk.

        ``step_count_override`` is a test/programmatic-only hook (priority #1).
        The CLI dry-run path does NOT use it — it stashes the count via
        ``set_pending_step_count`` (priority #2). Both exist because the
        graph never ran on a dry-run (no run root, no per-step JSONL files),
        so the empirical action-log recovery would return 0; supplying the
        validated count keeps run.json aligned with the "N step(s) resolved"
        log line.
        """
        # Resolve the run root: an explicit kwarg wins; otherwise use the root
        # THIS invocation claimed via set_own_run_root. If neither exists, the
        # invocation created no root (host-busy, config/permission error,
        # interrupt before the graph started) — write a degenerate
        # base_dir/run.json. The writer never guesses by mtime, which under a
        # shared base_dir could attribute a concurrent lock-holder's root to a
        # host-busy run and clobber that run's run.json.
        if run_root is None:
            run_root = self._own_run_root

        ended_iso = datetime.now(tz=UTC).isoformat()
        elapsed = time.monotonic() - self._started_at_mono

        run_id: str | None = run_root.name if run_root is not None else None
        # Step count resolution order (highest priority first):
        # 1. explicit step_count_override kwarg (test/programmatic)
        # 2. self._pending_step_count (CLI dry-run stash)
        # 3. empirical recovery from action-log JSONL files (run-then-flush)
        if step_count_override is not None:
            step_count = step_count_override
        elif self._pending_step_count is not None:
            step_count = self._pending_step_count
        else:
            step_count = _step_count_from_recipe(run_root=run_root)

        failure_record: dict[str, Any] | None = None
        if status == "failure" and run_root is not None:
            raw = _read_failure_record(run_root)
            if raw is not None:
                # Re-pack only the keys we promise in the summary.
                # Full diagnostic still lives in failure.jsonl.
                failure_record = {
                    "step_idx": raw.get("step_idx"),
                    "step_name": raw.get("step_name"),
                    "phase": raw.get("phase"),
                    "error_class": raw.get("error_class"),
                    "screenshot": raw.get("screenshot"),
                    "failure_jsonl": str(
                        run_root
                        / "artifacts"
                        / "action-log"
                        / "failure.jsonl"
                    ),
                }

        summary = RunSummary(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            status=status,
            exit_code=exit_code,
            started_at=self._started_at_iso,
            ended_at=ended_iso,
            elapsed_seconds=elapsed,
            step_count=step_count,
            failure=failure_record,
        )

        # Prefer writing inside the run root so the summary stays
        # collocated with the rest of the run's evidence. Fall back
        # to base_dir when there is no run root (host-busy or
        # recipe-load error before any run was created).
        if run_root is not None:
            target = run_root / SUMMARY_FILENAME
        else:
            target = self._base_dir / SUMMARY_FILENAME

        try:
            _atomic_write_json(target, summary.to_json())
        except Exception as exc:  # noqa: BLE001 — best-effort writer
            import sys

            print(
                f"coord-smith: run-summary write failed ({type(exc).__name__}): "
                f"{exc}",
                file=sys.stderr,
            )
        return target, summary
