# Changelog

All notable changes to **coord-smith** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Per-host advisory lock** preventing two coord-smith processes from
  racing on the process-global pyautogui cursor/screen. Lock is
  acquired before preflight (``coord_smith.graph.host_lock``). A
  second invocation that cannot acquire the lock within 10 s exits
  with new **exit code 4** (`host busy`). See
  `docs/architecture-boundaries.md §Host Exclusivity`.
- **Top-level `run.json` summary** envelope written on every exit
  path (success / failure / interrupted / host_busy). Schema
  v1: `status`, `exit_code`, timing, `step_count`, compact
  `failure` block with `phase` + screenshot pointer. Caller can
  read outcome from a single file. See
  `docs/recipe-guide.md §Run Summary Schema`.
- **`--target-window NAME` / `COORDSMITH_TARGET_WINDOW`** option
  (macOS only) — one-shot AppleScript `activate` before preflight
  so the target app is front-most at screenshot time. CLI flag
  wins over env.
- **`Step.settle_ms`** (default 300 ms, range 0–10000) — per-step
  post-click pause that the `verify_transition` baseline / cursor
  verification uses before reading the post-click frame. Replaces
  the prior hard-coded 50 ms; configurable for native vs heavy
  SPA scenarios.
- **`Step.wait_for`** — pre-click image guard that polls for an
  anchor template before dispatching the click. Region-scoped
  search supported. Subsumes the legacy `trigger_wait` mission.
- **`failure.jsonl.phase`** field — `pre_click` / `dispatch` /
  `post_click` — disambiguates same-class errors that originate
  from different sub-phases (e.g. `ImageWaitTimeout` from
  `wait_for` vs `post_click_signal`).
- **Step name uniqueness validation** at recipe parse time —
  duplicate `step.name` values would silently collide on action-log
  JSONL files. Now rejected with an actionable error.
- **KeyboardInterrupt handler** in the CLI — Ctrl-C / SIGINT now
  produces a deterministic exit 1 with a stderr line and a
  `run.json` summary, instead of Python's default exit 130 with a
  traceback and no artifacts.
- **PEP 561 `py.typed` marker** so downstream `mypy`/`pyright`
  consumers see coord-smith as a typed package.
- **LICENSE** file (MIT) at repo root.
- **pyproject.toml metadata**: classifiers, keywords, authors,
  project URLs, real description.
- **Multi-step example recipe with `wait_for`** at
  `docs/recipes/multi-step-with-wait-for.yaml`.
- **Contract tests** for `failure.jsonl` schema and the CLAUDE.md
  recipe example, plus phase-tagging unit tests, host-lock unit
  tests, run-summary unit tests, fail-fast contract integration
  tests.

### Changed

- **Mission graph consolidation** — 12 per-run missions folded into
  6 (3 per-run + 3 per-step, repeated N times per recipe step).
  Modeled tier permanently removed.
- **CLI exit code mapping** — image-match / page-transition / etc.
  dispatch failures now map to **exit 1** (not 2). Only true
  permission failures (`AccessibilityPermissionDenied`,
  `ScreenCapturePermissionDenied`) keep the exit-2 + permission-hint
  path.
- **CLAUDE.md recipe example** — switched from legacy `missions:`
  shape to canonical `steps:` so agent-generated recipes inherit
  the modern shape and don't trigger `DeprecationWarning`.
- **Documentation truth-up** — PRD `§Released scope` and
  `current-state.md` updated to match the actual 6-mission code.
- **README CI claim** corrected — the original "GitHub Actions
  runs Python 3.14 + xvfb…" text was aspirational; CI is not
  wired yet (pre-commit hooks are the gate).
- **ROP refactor** — eliminated the in-process `Step` dict
  round-trip (producer passes the Step instance; payload-JSON
  contract preserved via a `default=` callback). Deduplicated
  triple-validation of attach/prepare inputs.

### Removed

- **`playwright`** from dev deps — violated the documented
  "Browser-internals forbidden" invariant and was unused by any
  source or test.
- **Stale test-count badges** (721 passing → current).

### Security

- No new security surface. The MIT LICENSE file makes the existing
  permission grant explicit; previously implicit in the README
  badge.

---

## [0.0.1] — initial scaffold

Pre-public scaffold release. Tracked here only as a baseline.
