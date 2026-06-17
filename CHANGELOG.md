# Changelog

All notable changes to **coord-smith** are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security & supply chain
- **Pipeline hardening** — three new scanners wired into pre-commit
  and a CI `security` job:
  - **gitleaks** secret scan (`.gitleaks.toml` extends the upstream
    default ruleset + project allowlist). Pre-commit on staged
    changes; CI scans full history (`fetch-depth: 0`).
  - **trivy** CVE/secret scan of `uv.lock`, failing CI on any
    HIGH/CRITICAL.
  - **import-linter** layers contract (`graph > adapters > evidence
    > config > reporting > models > missions`) forbidding upward
    imports and inter-layer cycles. One `TYPE_CHECKING`-only back-edge
    is ignored with a documented reason.
- **Cleared 6 HIGH CVEs** by upgrading transitive deps:
  `langchain-core` 1.2.23 → 1.4.7 (CVE-2026-44843), `langsmith`
  0.7.22 → 0.8.16 (CVE-2026-45134), `pillow` 12.1.1 → 12.2.0
  (CVE-2026-40192 / -42311), `urllib3` 2.6.3 → 2.7.0
  (CVE-2026-44431 / -44432). Post-upgrade scan: 0 findings.

### Fixed — adversarial bug-hunt + usability pass
Findings from five independent adversarial review agents, each
verified before fixing and pinned by a regression test
(`tests/unit/test_adversarial_hardening.py`, +31 tests):
- **Path-traversal write (HIGH)** — `Step.name` flowed unvalidated
  into action-log JSONL filenames; a name with `../` or a leading
  `/` plus any per-step guard wrote JSONL outside the run root.
  Rejected at parse time + a defense-in-depth containment check in
  `ActionLogWriter.action_log_path`.
- **Lost failure evidence (HIGH)** — `ScreenCaptureUnavailable`
  during a `verify_transition` step bypassed the failure-evidence
  writer; now caught (permission errors still route to exit 2).
- **Coordinate priority level 1 (HIGH)** — ADR-003's
  `payload(x,y) > step.coord` override was documented but never
  implemented; `_execute_step_dispatch` now honors a payload override
  (both ints required; partial → `ConfigError`).
- **`change_ratio` correctness** — page-transition ratio measured
  bounding-box area, not changed-pixel fraction (scattered 1px
  changes falsely read as a full transition); now counts genuinely
  changed pixels.
- **Schema strictness** — recipe models are `extra="forbid"` (typo'd
  fields fail instead of silently defaulting); `region` requires
  positive width/height; `version` constrained to `Literal[1]`;
  `wait_for`/`post_click_signal` reject `interval > timeout`.
- **Missing-input exit code** — a missing required input now raises
  `ConfigError` → exit 3 (was a bare `ValueError` → exit 1,
  indistinguishable from a runtime click failure) with a message
  naming the flag + env var. `docs/recipe-guide.md` corrected.

### Changed — Clean Architecture follow-ups

- **B-CA-4 closure (three waves)** — `PyAutoGUIAdapter` reduced
  from **892 → 692 lines**, clearing the audit's `< 700` target.
  Three SRP-driven extractions, each shipped as a separate
  commit:
  - **Wave 1** (commit `4af25af`): step-level pre/post-click
    guards lifted into `adapters/step_guards.py`
    (`PhaseName` Literal type, `tag_phase` / `read_phase`
    helpers, `StepGuardCollaborator` Protocol,
    `run_pre_click_wait_for` and `run_post_click_signal` free
    functions). Adapter: 892 → 865 lines.
  - **Wave 2** (commit `67f3447`): click-coordinate resolver
    lifted into `adapters/coord_resolver.py`
    (`CoordResolverCollaborator` Protocol, `locate_image_target`,
    `locate_image_for_step`, `locate_image_or_none`,
    `coord_or_none`, `resolve_step_click_coords`). The
    `step.coord` vs `step.image` resolution chain
    (ADR-003 priority, prefer + fallback) is now an isolated
    module with its own Protocol-typed collaborator interface.
    Adapter: 865 → 722 lines.
  - **Wave 3** (commit `0aeb918`): dead 1-line delegate cleanup
    — four resolver delegates kept across wave 2 had no src or
    test callers (only `_resolve_step_click_coords` is still
    invoked, by `_dispatch_with_step` + tests). Dropped
    `_locate_image_target`, `_locate_image_or_none`,
    `_coord_or_none`, `_locate_image_for_step` and the matching
    `coord_resolver` / `MissionImageClick` imports. Adapter:
    722 → 692 lines.

  What remains in the adapter is now its irreducible core: the
  OS-touch primitives (preflight, screenshot, click), the
  evidence-gather pipeline, and the `_dispatch_with_step`
  orchestrator that threads them. Further extraction would be a
  cosmetic concern, not a correctness one.

- **B-CA-5 closure**: extracted run-summary lifecycle from
  `pyautogui_cli_entrypoint.py` into new
  `reporting/run_summary_lifecycle.py` (`RunSummaryLifecycle`
  context manager with `set_outcome(status, exit_code)`). The
  CLI's `main()` no longer hand-manages the
  `writer + status + exit_code + try/finally + flush` quartet —
  it uses `with RunSummaryLifecycle(...) as summary` and each
  branch calls `summary.set_outcome(...)`. Reporting concern is
  out of the CLI routing module.

7 new unit tests pin the lifecycle contract (writer creation,
default outcome, idempotent set_outcome, exceptions never
swallowed, flush failure isolated from caller). Test count: 360
→ 367.

---

## [0.1.1] — 2026-05-23 — audit-closure patch release

This release closes findings from two parallel 4-axis re-audits
(Clean Architecture / ROP / Production gaps / Industry hygiene)
of the v0.1.0 sweep. No new features — pure hygiene, bug fixes,
and documentation precision. Safe drop-in upgrade from 0.1.0.

### Fixed — caller-facing
- **docs/recipe-guide.md exit-code-1 row** branches on
  `run.json.status` instead of blindly directing callers to
  read the `failure` key (which is `null` on
  `status: interrupted` — previous wording misled literal
  readers on `KeyboardInterrupt`).
- **`--cleanup` doc carve-out**: docs/recipe-guide.md
  §Run Summary Schema and docs/architecture-boundaries.md
  §How callers should read a run result both clarify that
  `--cleanup` does NOT write `run.json`. Automation polling
  the file must skip cleanup invocations.
- **`run.json` on host_busy is locked by a regression test**
  — previously the exit-4 contract was tested but the
  artifact contract (`status: "host_busy"`, `exit_code: 4`)
  was not. Adding the assertion closes the silent-regression
  window.
- **Wrong GitHub org URLs** corrected in pyproject.toml
  `[project.urls]`, README CI badges, and README clone
  snippets (was `coord-smith/coord-smith` placeholder; now
  `jazz1x/coord-smith`).
- **`run.json.failure` phantom field name** — text used to
  read as if `run.json.failure` were a file path; rewritten
  to "the `failure` key inside `run.json`".
- **CLAUDE.md exit_codes block** now includes exit 4 (host
  busy). Agent reading CLAUDE.md first will apply the
  back-off strategy instead of treating it as an opaque
  runtime error.
- **`run.json.step_count` on dry-run** matches the log line
  ("preflight passed, N step(s) resolved"). Previously was 0
  because the empirical recovery from action-log JSONL files
  ran before any file existed.

### Changed — parse-don't-validate finishing touches
- `validate_execution_mission_name` trusts the `MissionName`
  brand and only checks `mission_is_browser_facing` (was
  re-running 5 shape checks upstream of the parser).
- `validate_action_log_artifacts_contain_ref_events` accepts
  `MissionName` instead of `str`; drops the same shape
  ladder. Caller `execute_within_scope` typed end-to-end.
- `run_released_scope_via_langgraph` takes typed identifiers
  directly; single parse boundary lives in
  `released_cli_shim.resolve_released_scope_inputs`. Removed
  the in-function double-parse.

### Changed — Clean Architecture polish
- `_FALLBACK_REFS` duplicate dict-comprehension removed —
  both `pyautogui_adapter.py` and `action_log_writer.py`
  import `MISSION_FALLBACK_REFS` from
  `missions.evidence_specs`.
- `graph/run_summary.py` moved to `reporting/run_summary.py`
  (zero graph imports — pure infrastructure).
- `adapters/execution/execution.py` vestigial double-shim
  deleted.
- `reporting/summary.py` (unused, layer-inverted) deleted.
- `_payload_json_default` removed from `client.py.__all__`.
- `artifact_io._require_run_root_dir` promoted to public
  `require_run_root_dir`; `client.execute_within_scope`
  imports it at module top (no more lazy function-body
  import).
- `PyAutoGUIAdapter._assert_template_exists` helper
  deduplicates 3 image-template existence-check sites.

### Changed — packaging / CI
- `[project]` uses `dynamic = ["version"]` +
  `[tool.hatch.version]` reading `src/coord_smith/__init__.py`.
  Single source of truth for the version string.
- `.pre-commit-config.yaml` local hooks switched from
  hardcoded `.venv/bin/python` to `uv run --frozen --`.
  Portable across fresh clones, CI runners, Windows, and
  non-uv setups.
- `[tool.hatch.build.targets.wheel] include` entry removed
  (redundant — hatchling auto-bundles `packages`).
- CHANGELOG compare-URL footers added (Keep-a-Changelog
  convention).
- `.github/workflows/ci.yml` matrix pin to py3.14
  documented as intentional; new
  `workflow_dispatch.inputs.python_smoke` + `smoke-py` job
  (continue-on-error) provide a future-minor smoke path.

### Changed — production safety
- `--cleanup` acquires the per-host advisory lock before
  pruning — a concurrent dispatch run cannot have its dir
  removed mid-flight.
- `--cleanup` with click-related flags emits a WARNING
  (cleanup still runs; operator notified the click flags
  were ignored).
- `--cleanup` returns exit 1 when `CleanupReport.errors > 0`.
  Cron-based callers detect partial failures.
- `_read_failure_record` logs a WARNING on JSON parse
  failure instead of silently returning `None`.

### Industry hygiene
- `SECURITY.md` "email the maintainers (placeholder)" →
  GitHub private vulnerability reporting URL.
- README install sections lead with
  `uv pip install coord-smith` / `pip install coord-smith`
  before the source-checkout instructions.

### Deferred (P3 backlog)
- B-CA-4 step-guard extraction (adapter still 892 lines).
- B-CA-5 run-summary lifecycle context manager.
- B-POLISH-3 PyPI version + downloads badges (post-publish).

### Test count
- Tests: **360 passing**, 4 deselected (real-binary).
- ruff: clean · mypy strict: clean · pre-commit: clean.

---

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

## [0.0.1] — initial scaffold

Pre-public scaffold release. Tracked here only as a baseline.

<!--
Compare-URL footers (Keep-a-Changelog convention). Each version
heading is a clickable diff once the corresponding tag exists on
github.com/jazz1x/coord-smith.
-->

[Unreleased]: https://github.com/jazz1x/coord-smith/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/jazz1x/coord-smith/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/jazz1x/coord-smith/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/jazz1x/coord-smith/releases/tag/v0.0.1
