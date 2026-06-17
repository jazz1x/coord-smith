# ADR-004 — Failure evidence policy: phase-tagged `failure.jsonl` + diagnostic screenshot

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: evidence, contract, caller-integration

## Context

When a step dispatch fails (image not matched, click cursor not moved,
page transition not detected, etc.), the orchestrator (OpenClaw) needs
enough information to **decide what to do next** — retry with adjusted
confidence, re-crop the template, escalate to a human, or move on.

Earlier behavior: the runtime raised a typed exception and exited
non-zero. The caller saw an exit code and a stderr line but had to
guess at the screen state at the moment of failure. Worse: the same
exception class (`ImageWaitTimeout`) could originate from two different
sub-phases of a step (pre-click `wait_for` versus post-click
`post_click_signal`) — indistinguishable in the audit trail.

We needed a contract that:

1. Always captures a screenshot at the moment of failure (best-effort
   — a permission revocation mid-run must not stall everything).
2. Names which sub-phase produced the failure so the caller can
   branch on remediation strategy.
3. Preserves earlier successful steps' evidence so partial-progress
   diagnosis is possible.

## Decision

Every typed dispatch failure produces, **before** the exception
propagates to the caller:

1. A diagnostic screenshot at
   `runs/<run_id>/artifacts/failure/<NN>-<step_name>-<error_class>.png`.
   The capture is best-effort: if `pyautogui.screenshot()` itself
   raises (e.g. permission revoked), the path is recorded as `null`
   and the run still emits its log entry.
2. A structured record appended to
   `runs/<run_id>/artifacts/action-log/failure.jsonl`. The schema is
   public contract (documented in `docs/recipe-guide.md §Failure
   Artifacts` and pinned by `tests/contract/test_failure_jsonl_schema.py`):

```jsonc
{
  "ts": "<ISO 8601 UTC>",
  "mission_name": "step_dispatch",
  "event": "step-dispatch-failed",
  "step_idx": <int>,
  "step_name": "<step name>",
  "phase": "pre_click" | "dispatch" | "post_click",
  "error_class": "<exception class name>",
  "error_message": "<exception message>",
  "screenshot": "<absolute path or null>"
}
```

3. Earlier steps' per-step artifacts
   (`step-observed.jsonl` / `step-dispatched.jsonl` / `step-captured.jsonl`)
   are preserved untouched. The graph is fail-fast: steps after the
   failing one do not execute, and `run_completion` is NOT reached
   (no `release-ceiling-stop.jsonl`).

The phase tag is the disambiguator: `ImageWaitTimeout` from
`Step.wait_for` is `phase: pre_click`; the same class from
`post_click_signal` is `phase: post_click`. Callers branch on phase
before branching on error class.

## Consequences

- **Positive.** OpenClaw can read `failure.jsonl` + look at the
  `screenshot` path and immediately have everything needed to
  diagnose. No grepping the per-step JSONLs for context.
- **Positive.** The schema is contract-pinned. Adding a new key
  requires a docs update *and* a test update — no silent fields.
- **Positive.** Fail-fast keeps the run model simple: one failure =
  one diagnosis, no cascade of confused secondary errors.
- **Negative.** A flow that *could* recover at step k+1 without
  step k's success is not expressible as a single recipe. Callers
  needing partial recovery must split the flow across multiple
  invocations.
- **Open.** When run.json was added (ADR-006), it duplicated the
  failure summary inline. The duplication is intentional: `run.json`
  is "read first to branch"; `failure.jsonl` is "read for full
  diagnostic".

## References

- `src/coord_smith/adapters/pyautogui_adapter.py` —
  `_capture_failure_evidence`, `_dispatch_with_step` (phase-tagging
  via `_tag_phase`)
- `docs/recipe-guide.md` §Failure Artifacts
- `tests/contract/test_failure_jsonl_schema.py` — schema lock
- `tests/unit/test_failure_phase_tagging.py` — phase mapping tests
- `tests/integration/test_failure_capture.py` — fail-fast contract +
  partial-success preservation
