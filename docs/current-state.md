# coord-smith Current State

## Purpose

This document is the current implementation snapshot. It is intentionally
changeable and subordinate to `docs/prd.md`.

## Snapshot

- Python 3.14 pinned (`requires-python = ">=3.14,<3.15"`).
- Released ceiling: `runCompletion`. Six released missions (3 per-run +
  3 per-step): `attach_session` · `prepare_session` · `step_observe` ·
  `step_dispatch` · `step_capture` · `run_completion`. Modeled tier
  permanently removed.
- Test count: 354 passing, 4 deselected (`-m real`).
- Static checks: ruff clean, mypy strict clean, pre-commit clean.
- Platform: macOS (Accessibility + Screen Recording permissions). Linux
  / Windows preflight not implemented.
- Operator ergonomics: `--target-window NAME` /
  `COORDSMITH_TARGET_WINDOW` runs a one-shot AppleScript activate
  before preflight + dispatch on macOS. Per-step `settle_ms`
  (default 300 ms) drives the post-click pause used by
  `verify_transition`.

## Architecture

- **LLM-free runtime.** The coord-smith runtime graph contains no LLM inference.
  Each LangGraph node is deterministic: state setup, adapter call, evidence
  collection.
- **Multi-step flow.** `ClickRecipe.steps: list[Step]` declares an N-step
  click sequence. The graph topology is built statically per recipe
  (per-run setup → N×(observe → dispatch → capture) → run_completion).
  Legacy single-mission `missions:` recipes auto-normalize to a
  one-step recipe with a deprecation warning.
- **CUA engine.** `src/coord_smith/adapters/pyautogui_adapter.py` implements
  `ExecutionAdapter.execute()` using `pyautogui.click()` /
  `pyautogui.screenshot()` only. Wired via
  `src/coord_smith/graph/pyautogui_cli_entrypoint.py` (`coord-smith` console script).
- **Browser-internals forbidden.** Playwright, CDP, and similar drivers are
  not part of the execution backend. OS-level coordinates and pixels only.
- **Visual click verification.** Image-template click via OpenCV,
  optional pre/post page-transition diff via `PIL.ImageChops`, optional
  post-click signal polling via `pyautogui.locateCenterOnScreen`,
  optional pre-click `wait_for` guard (polled with the same primitive,
  scoped by `WaitFor.region`). All four are deterministic and
  default-off in click recipes. The `wait_for` poll precedes coord
  resolution; on success a `wait_for_*` action-log entry is recorded
  under the step's name.
- **Failure evidence.** Typed dispatch failures
  (`ImageMatchConfidenceLow` / `ClickCoordinatesOutOfBounds` /
  `ClickExecutionUnverified` / `PageTransitionNotDetected` /
  `ImageWaitTimeout` / `ImageTemplateNotFound`) write a screenshot to
  `runs/<id>/artifacts/failure/<idx>-<step>-<error>.png` and a
  structured record to `action-log/failure.jsonl` before propagating.
  Earlier steps' artifacts are preserved.
- **Fail-fast multi-step contract.** A typed dispatch failure on step
  `k` aborts the run: steps `k+1..N-1` do not execute and
  `run_completion` is not reached (no `release-ceiling-stop.jsonl`).
  Callers diagnosing a failed run can rely on the absence of
  `release-ceiling-stop.jsonl` to detect an aborted run without
  parsing exit codes.
- **CLI exit code mapping.** `0` clean, `1` runtime dispatch error
  (any non-permission `ExecutionTransportError` — image match, page
  transition, click verification, etc., plus caught
  `KeyboardInterrupt`), `2` permission preflight failed (only
  `AccessibilityPermissionDenied` / `ScreenCapturePermissionDenied`),
  `3` recipe load or schema error, `4` host busy (another
  coord-smith process holds the per-host advisory lock).
- **Per-host advisory lock.** Acquired in ``_run`` before preflight
  via ``graph.host_lock``; the lock guards the process-global
  pyautogui state (cursor + screen). A second invocation that
  cannot acquire the lock within 10 s exits with code 4 and a
  named error so callers can back off + retry. See
  ``docs/architecture-boundaries.md §Host Exclusivity``.
- **Top-level `run.json` envelope.** Every invocation writes a
  single summary file at ``runs/<run_id>/run.json`` (or
  ``base_dir/run.json`` when no run root was created) describing
  status / exit_code / elapsed / step_count / failure block. See
  ``docs/recipe-guide.md §Run Summary Schema``.

## Scope

Released:

- Released-scope graph and entrypoint wiring up to `runCompletion`.
- `ExecutionAdapter` protocol with `PyAutoGUIAdapter` as the sole
  implementation in the released path.
- Evidence envelope, checkpoint comparability, transition reporting.
- Typed error hierarchy and mission anchor mapping.
- `coord-smith` console script registered in `pyproject.toml`.

## Source of ongoing truth

For domain-specific contracts, defer to source code under `src/coord_smith/`.
Repository base config (`pyproject.toml`, `.pre-commit-config.yaml`) is
authoritative for tooling.
