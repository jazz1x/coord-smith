# ADR-006 — `run.json` envelope as the single-file caller outcome contract

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: contract, caller-integration, observability

## Context

Pre-2026-05-13, an orchestrator (OpenClaw) inferring a run's outcome
had to read several files:

- `release-ceiling-stop.jsonl` (present only on success) — implicit
  success signal by file presence.
- `failure.jsonl` (present only on failure) — explicit failure detail.
- `step-observed.jsonl` / `step-dispatched.jsonl` /
  `step-captured.jsonl` per-step files — for timing / counts.

This required `N + 2` reads per run, plus heuristic reasoning about
which file's presence implies which status. Edge cases —
host-busy before any run root existed, recipe-load failure exiting
with code 3 with zero artifacts — left the caller with only an exit
code and no structured artifact to point at.

The production-gaps audit flagged this as a P1 caller-UX gap: the
single-file contract was the missing piece that turned `coord-smith`
from "scriptable" into "easy to integrate by an autonomous agent".

## Decision

Every `coord-smith` invocation writes exactly one `run.json` summary
on **every** exit path — success, typed failure, KeyboardInterrupt,
host-busy, recipe-load error — via a `try/finally` in `main()`. The
schema is **public contract** (`schema_version: 1`) and lives in
`docs/recipe-guide.md §Run Summary Schema`. The writer is best-effort
(a write failure logs to stderr but never masks the caller's exit
code).

Location:

```
artifacts/runs/<run_id>/run.json     # normal case
<base_dir>/run.json                  # when no run root was created
                                     # (host_busy / pre-graph error)
```

Schema (`schema_version: 1`):

```jsonc
{
  "schema_version": 1,
  "run_id": "<run_id>" | null,
  "status": "success" | "failure" | "interrupted" | "host_busy",
  "exit_code": <int>,
  "started_at": "<ISO 8601 UTC>",
  "ended_at": "<ISO 8601 UTC>",
  "elapsed_seconds": <float>,
  "step_count": <int>,
  "failure": null | {
    "step_idx": <int>,
    "step_name": "<name>",
    "phase": "pre_click" | "dispatch" | "post_click",
    "error_class": "<class name>",
    "screenshot": "<absolute path or null>",
    "failure_jsonl": "<absolute path>"
  }
}
```

Caller decision tree (also in `docs/architecture-boundaries.md §How
callers should read a run result`):

```
1. Read run.json (single file, always present).
2. Branch on run.json.status:
   - "success"     → proceed.
   - "failure"     → read run.json.failure + drill into failure.jsonl.
   - "interrupted" → safe to retry.
   - "host_busy"   → back off 1–5 s and retry; exit_code = 4.
```

Atomic write (tmp + rename) prevents partial reads on concurrent
poll.

## Consequences

- **Positive.** OpenClaw reads exactly one file to determine outcome
  and branch. No grepping, no presence-of-file heuristics.
- **Positive.** The exit code stays the primary signal; `run.json`
  is its structured companion. The two cannot disagree because the
  same `main()` writes both.
- **Positive.** Schema_version makes future additions safe — fields
  can be added at the same version; only removals / renames bump.
- **Negative.** Slight duplication: `failure` block in `run.json`
  echoes the first record of `failure.jsonl`. Intentional — see
  ADR-004's "read first to branch" vs "read for full diagnostic"
  split.
- **Open.** No CHANGELOG / migration tooling on the schema yet. A
  future v2 schema would need a runner that can read v1 and v2
  side-by-side.

## References

- `src/coord_smith/graph/run_summary.py` — writer
- `src/coord_smith/graph/pyautogui_cli_entrypoint.py` — `main()`
  try/finally site
- `docs/recipe-guide.md` §Run Summary Schema
- `docs/architecture-boundaries.md` §How callers should read a run
  result
- `tests/unit/test_run_summary.py` — atomic write, schema, every
  exit path
