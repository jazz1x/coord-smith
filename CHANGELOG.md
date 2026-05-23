# Changelog

All notable changes to **coord-smith** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-13 — productization milestone

This is the first release that an external orchestrator (OpenClaw,
Hermes, or any agent following the same CLI contract) can integrate
against without bespoke patches. The headline change set:

### Added — caller integration surface
- `coord-smith --recipe-schema` flag — emits the Pydantic JSON
  Schema for `ClickRecipe` to stdout. Designed for autonomous
  agents that attach the schema to their prompt without spawning
  a Python interpreter.
- `coord-smith --cleanup --max-runs N --max-age-days N` —
  operator command to prune `artifacts/runs/`. Run roots with a
  `.keep` sentinel file are never removed. Exit code 3 on
  invalid bounds; exit 0 with a summary log line on success.
- `--verbose / -v` and `--quiet / -q` flags, plus
  `COORDSMITH_LOG_LEVEL` env var. Diagnostic output now flows
  through the `coord_smith` logger with format
  `coord-smith: <LEVEL>: <message>` — callers (orchestrators,
  pytest's `caplog`) can intercept records via the root logger.
- `run.json` envelope written on every exit path (success,
  failure, interrupted, host_busy). Single-file outcome contract
  for callers; schema documented in
  `docs/recipe-guide.md §Run Summary Schema`.
- Per-step `Step.wait_for` (pre-click anchor poll) and
  `Step.settle_ms` (configurable post-click pause, default 300 ms).
- `failure.jsonl.phase` field (`pre_click` / `dispatch` /
  `post_click`) disambiguating same-class errors from different
  step sub-phases.
- `--target-window NAME` / `COORDSMITH_TARGET_WINDOW` for macOS
  one-shot AppleScript activation before preflight.
- Per-host advisory lock (`fcntl.flock` on
  `<base_dir>/artifacts/.coord-smith.lock`). New CLI exit code
  **4** ("host busy") when a parallel invocation cannot acquire
  the lock — caller back-off signal.
- `KeyboardInterrupt` handler — Ctrl-C / SIGINT now produces
  deterministic exit 1 + a `run.json` with `status: interrupted`
  + a stderr log record, replacing Python's silent exit 130.

### Added — durable architecture decisions (`adr/`)
- ADR-001 LLM-free runtime + browser-internals forbidden
- ADR-002 Multi-step recipe DSL (`steps:` canonical)
- ADR-003 Coordinate priority (`payload → step.coord → step.image
  → no-click`)
- ADR-004 Failure evidence policy (phase-tagged `failure.jsonl`)
- ADR-005 Per-host advisory lock
- ADR-006 `run.json` envelope as caller outcome contract

### Added — packaging & community
- `LICENSE` (MIT) at repo root + `pyproject.toml` `license` field.
- PEP 561 `py.typed` marker so downstream `mypy`/`pyright`
  consumers see the package as typed.
- `pyproject.toml` metadata: classifiers (10), keywords (8),
  authors, `project.urls`.
- `CONTRIBUTING.md`, `SECURITY.md`, `.github/PULL_REQUEST_TEMPLATE.md`,
  `.github/dependabot.yml`.
- `.github/workflows/ci.yml` — Ubuntu + Python 3.14 + xvfb +
  ruff + mypy strict + pytest + a separate pre-commit job. CI
  runs on every push to `main` and every PR.

### Changed — internal architecture cleanups
- **Mission graph consolidated** from the legacy 12-mission flat
  pipeline to 6 missions (3 per-run + 3 per-step, repeated per
  recipe step). Modeled tier permanently removed.
- **Per-mission evidence manifest unified** into a single
  `MISSION_EVIDENCE_SPECS` table at
  `src/coord_smith/missions/evidence_specs.py`. Both the adapter
  (producer) and the validator (consumer) now read from it —
  renaming an evidence ref is a one-file edit (B-CA-3).
- **`adapters/execution/client.py` split** from 738 lines into
  focused modules: `contracts.py` (5 symbols),
  `validation.py` (10 symbols), `artifact_io.py` (7 public
  symbols), `client.py` (~150 lines of orchestration +
  re-exports). Public import surface unchanged (B-CA-1).
- **`ActionLogWriter` extracted** from `PyAutoGUIAdapter`. Five
  per-mission JSON-line writers + the action-key derivation
  helper now live in
  `src/coord_smith/adapters/action_log_writer.py` — testable
  without `patch("pyautogui.*")` (B-CA-2).
- **NewType identifiers** (`MissionName`, `SessionRef`,
  `ExpectedAuthState`, `TargetPageUrl`, `SiteIdentity`,
  `ResolvedImagePath`) with parser functions in
  `src/coord_smith/models/identifiers.py`. Parse-once at the
  CLI boundary; internal call sites receive the typed alias
  (B-ROP-1, B-ROP-3).
- **Result-style dual-target fallback** in
  `_resolve_step_click_coords`. Replaced exception-as-control-flow
  + re-run trick with explicit `_locate_image_or_none(step) →
  (coords | None, error | None)`. Lazy evaluation preserved
  (image matcher only runs when needed). Original error
  instance re-raised on dual-failure (no re-run, no traceback
  loss) (B-ROP-2).
- **CLI exit-code categorisation** corrected — only true
  permission failures map to exit 2; other dispatch failures
  map to exit 1.
- **CLAUDE.md recipe example** modernised — canonical `steps:`
  shape; the deprecated `missions:` shape is documented as
  legacy only.
- **Step name uniqueness** enforced at recipe parse time —
  duplicates collide on action-log JSONL file names.
- **Test pyramid hygiene** — four adapter-instantiating
  "unit" tests moved to `tests/integration/` (B-PROD-4).

### Removed
- `playwright` from dev dependencies — violated the
  "Browser-internals forbidden" invariant and was unused.
- The false "GitHub Actions CI configured" claim from README
  — real CI now exists (see Added).
- Legacy 12-mission flat graph (subsumed by 6-mission graph).

### Test count
- Tests: **354 passing**, 4 deselected (real-binary).
- ruff: clean · mypy strict: clean · pre-commit: clean.

---

## [Unreleased]

Nothing yet — the next batch lives in `docs/backlog.md`.

---

## [0.0.1] — initial scaffold

Pre-public scaffold release. Tracked here only as a baseline.

<!--
Compare-URL footers (Keep-a-Changelog convention). Each version
heading is a clickable diff once the corresponding tag exists on
github.com/jazz1x/coord-smith.
-->

[Unreleased]: https://github.com/jazz1x/coord-smith/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jazz1x/coord-smith/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/jazz1x/coord-smith/releases/tag/v0.0.1
