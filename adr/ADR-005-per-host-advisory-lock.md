# ADR-005 — Per-host advisory lock for `pyautogui` process-globals

- **Status**: Accepted (2026-05-13)
- **Date**: 2026-05-13
- **Deciders**: coord-smith core
- **Tags**: concurrency, safety, contract

## Context

`pyautogui` is process-global on a given host: there is exactly **one
cursor** and **one screen** for the entire OS, shared across every
running `pyautogui` client. Two `coord-smith` processes invoked at the
same time would:

- Race on the preflight cursor probe (each process's `moveTo` competes
  with the other's `click`).
- Interleave clicks within their own `_dispatch_with_step` windows —
  step A in process 1 firing while process 2's cursor is at the wrong
  coordinate.
- Capture screenshots that include the other process's mid-flight
  cursor / overlay state, breaking image-template matching with
  invisible, hard-to-reproduce errors.

There is no `pyautogui` API to detect this — it is a property of the
OS, not a property of the library. The production-gaps audit
(2026-05-13) flagged the absence of any guard as a P0 silent failure:
zero diagnostic path, zero documented constraint, zero guard rail.

A queue / scheduler at the caller side could solve it, but
*requiring* the caller to schedule transfers all of the safety burden
to the orchestrator. Worse: nothing prevents a misconfigured caller
from violating the constraint silently.

## Decision

`coord-smith` enforces single-active-invocation per artifact tree via
an advisory `fcntl.flock` on
`<base_dir>/artifacts/.coord-smith.lock`. The lock is acquired in
`_run` **before** preflight and released at the end of the same
`with` block. A second invocation that cannot acquire the lock within
10 seconds raises `HostBusyError`, which the CLI maps to a new exit
code **4** (`host busy`).

Semantics:

- **Per artifact tree, not strictly per host.** Two callers using
  *different* `base_dir` paths can run in parallel — they will not
  contend on the lock. The lock catches the real-world enemy: two
  callers using the *same* artifact tree.
- **Advisory.** Cooperating processes respect it; uncooperative
  software (or a caller that manually deletes the lock file) still
  wins. We do not defend against adversarial neighbours.
- **No fcntl → no-op + stderr warning.** On platforms that do not
  expose `fcntl` (Windows, niche Unixes), the lock degrades to a
  no-op AND emits a one-shot stderr warning so the operator knows
  the concurrency guarantee is absent. macOS (the supported
  platform) always has `fcntl`.
- **Exit code 4 is documented as "back off and retry"**, not
  "permanent failure". Callers should treat it as a transient signal.

## Consequences

- **Positive.** Concurrent invocations against the same tree no
  longer corrupt each other silently. The failure surface becomes a
  clean exit code with an actionable message.
- **Positive.** The base-dir scoping lets multi-tenant or multi-session
  scenarios isolate workspaces without contention, at the cost of
  the operator choosing physically separate hosts (since the screen
  is still shared).
- **Positive.** No new runtime dependency — `fcntl` is stdlib.
- **Negative.** A caller that crashes while holding the lock will
  have the OS release the lock when the file descriptor closes
  (immediate cleanup in practice), but a stuck process — interactive
  debugger, blocked on input — can hold the lock indefinitely.
  Operators must `kill` the stuck process to recover.
- **Open.** Cross-host scheduling (when an orchestrator targets a
  fleet of Mac mini hosts) remains the caller's responsibility.
  Adding a network-level lock is out of scope.

## References

- `src/coord_smith/graph/host_lock.py` — implementation
- `src/coord_smith/graph/pyautogui_cli_entrypoint.py` — call site
  inside `_run`; exit-code-4 handler in `main`
- `docs/architecture-boundaries.md` §Host Exclusivity (caller
  contract)
- `tests/unit/test_host_lock.py` — contention, release-on-exception,
  no-fcntl fallback, exit-code-4 mapping
