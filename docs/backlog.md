# coord-smith Productization Backlog

This file is the agreed list of post-hardening refactor / productization
work not yet undertaken. It is the residue of the parallel audit
sweep (Clean Architecture / ROP-parse-don't-validate / Industry
conventions / Production gaps) once the P0 + P1 items had been
closed. Each entry is sized for a self-contained PRD: it has a
single owner concern, clear acceptance criteria, and is severable
from the others.

Do not silently fold these into unrelated PRs. Each gets its own
PRD + commit chain.

## P2 — Architectural refactors

### B-CA-1 · Split `adapters/execution/client.py`

**Why.** The file is 738 lines and mixes: contract types
(`ExecutionRequest` / `ExecutionResult` / `ExecutionAdapter`),
request validation, result validation, roundtrip validation,
scope-ceiling enforcement, filesystem artifact path
construction, JSONL schema validation, and the
`execute_within_scope` orchestration wrapper. Any evidence-shape
change touches one giant file. SRP violation surfaced by the
Clean Architecture audit.

**Target shape.**
- `adapters/execution/contracts.py` — `ExecutionRequest`,
  `ExecutionResult`, `ExecutionAdapter` Protocol only.
- `adapters/execution/validation.py` — all `validate_*` and
  `build_execution_request_*` functions.
- `adapters/execution/artifact_io.py` — action-log path helpers
  + JSONL schema checks.
- `client.py` becomes the orchestration wrapper
  (`execute_within_scope`) and re-exports the public types.

**Acceptance.** All current imports keep working; mypy strict
clean; no test source needs to change.

### B-CA-2 · Extract `ActionLogWriter` from `PyAutoGUIAdapter`

**Why.** The adapter is 867 lines. Five `_write_*_log` methods
plus `_action_key_for_mission` are an obvious responsibility
cluster that does not need any pyautogui state. Lifting them
into an `ActionLogWriter` class:
- halves the effective size of the adapter,
- makes the writer unit-testable without `patch("pyautogui...")`,
- positions the writer for a future async / queued mode (write
  burst at end of run instead of per-event).

**Target shape.** New `adapters/action_log_writer.py` with one
class plus the four typed log record dataclasses. Adapter
delegates: `self._log = ActionLogWriter(run_root)`.

**Acceptance.** Existing failure-capture and per-step JSONL
contracts unchanged. Tests for writers move from adapter-level
to writer-unit.

### B-CA-3 · Unify `_FALLBACK_REFS` ↔ `validate_execution_result` evidence table

**Why.** Two parallel per-mission evidence ref tables exist:
- `_FALLBACK_REFS` in `pyautogui_adapter.py` (producer-side)
- inline dict inside `validate_execution_result` in
  `adapters/execution/client.py` (consumer-side)

Any rename of an evidence ref or addition of a mission requires
synchronized edits to BOTH. The single biggest cross-file
coupling hotspot in the repo.

**Target shape.** New `missions/evidence_specs.py` with a
`dict[str, MissionEvidenceSpec]` (action-log refs, screenshot
refs, optional/required flags). Both sites read from this single
manifest. Schema covered by a contract test that imports the
manifest and asserts each released mission appears with the
expected ref set.

**Acceptance.** Renaming an evidence ref requires editing
exactly one file. Adding a mission requires editing the
manifest + `missions/names.py`.

## P2 — ROP / parse-don't-validate

### B-ROP-1 · NewType-ify `mission_name` / `session_ref` / `site_identity`

**Why.** Primitive `str` flows through ~10 call sites with
inconsistent re-validation. Identified by the ROP audit
(parse-don't-validate violation, HIGH severity). The
`_require_released_*_inputs` triple call was already closed in
the audit-batch commits, but the underlying type is still a
bare string downstream.

**Target shape.**
```python
SessionRef = NewType("SessionRef", str)
SiteIdentity = NewType("SiteIdentity", str)
ExpectedAuthState = NewType("ExpectedAuthState", str)
TargetPageUrl = NewType("TargetPageUrl", str)
MissionName = NewType("MissionName", str)
```
Parsed once at the CLI boundary; passed through the graph as
NewTypes. `MissionName` covers `mission_name` across
`RuntimeState`, `ExecutionRequest`, `_action_log_path`, etc.

**Acceptance.** Internal call sites that take `mission_name: str`
flip to `mission_name: MissionName`. mypy catches any path that
forgets to parse.

### B-ROP-2 · Result-style dual-target fallback

**Why.** `_resolve_step_click_coords` (the dual-target
fallback) currently catches typed exceptions inside
`_try_image()`, falls through to coord, and — if coord also
fails — re-runs the failing call to re-surface the exception.
Adhoc ROP via exception suppression. Identified by the ROP
audit as the highest-leverage refactor toward explicit
railway flow.

**Target shape.** Introduce a small `Result[T, E]` (or use
the `result` package) for `_locate_image_or_none(step)`.
Top-level dual-target combinator becomes:
```python
match image_result, coord_result:
    case (Ok(c), _): return c
    case (_, Ok(c)): return c
    case (Err(e1), Err(e2)): raise PrimaryFailureWithFallbackContext(e1, e2)
```

**Acceptance.** No `try/except` inside the resolver besides
the boundary translators. Re-run trick gone.

### B-ROP-3 · `Step.image` / `WaitFor.image` typed as `ResolvedImagePath`

**Why.** `load_click_recipe` resolves and existence-checks
every image path, but downstream code receives a bare `str`.
A `NewType("ResolvedImagePath", str)` would make "this path
was verified at load time" part of the type signature.

**Target shape.** Resolver produces `ResolvedImagePath`;
consumers (adapter, signals, wait_for) accept that NewType.

**Acceptance.** Mistakenly passing an unresolved string fails
mypy.

## P2 — Production hardening

### B-PROD-1 · Disk / run rotation policy

**Why.** Each step writes a full-screen PNG (Retina 5K ~5–10
MB). 100 runs/day on a real Mac fills the disk in days.
Currently zero TTL, zero rotation. Identified by the
production-gaps audit (Theme C, P1).

**Target shape.** Config option (env or recipe-level) for
`max_age_days` and/or `max_runs` to cap retained runs. A
`coord-smith --cleanup` sub-command (or opportunistic cleanup
after each run) prunes older trees. Consider JPEG quality 85
for non-failure screenshots (matches OpenCV template inputs
fine, ~10x smaller).

**Acceptance.** Documented retention policy; default that
fits on a developer laptop without intervention.

### B-PROD-2 · CI workflow (`.github/workflows/ci.yml`)

**Why.** The README previously claimed CI existed; the false
claim was corrected, but the actual CI gap remains.

**Target shape.** GitHub Actions on Ubuntu (xvfb for the
pyautogui import smoke), Python 3.14 only, running
`uv sync --extra dev`, `ruff check`, `mypy`, `pytest -q`.
Coverage with `pytest-cov` + `--cov-fail-under` gate. Separate
pre-commit job using `pre-commit/action@v3.0.1`.

**Acceptance.** Every PR shows green checks. Coverage badge in
README is real, not placeholder.

### B-PROD-3 · Replace `print(stderr)` with `logging`

**Why.** All CLI diagnostics go through bare `print(...,
file=sys.stderr)`. Acceptable for 0.0.1 but blocks any
orchestrator that wants to set log levels, route to syslog,
or filter by severity. Industry-conventions audit
(Operational Hygiene, LOW today, MED at 0.1.0).

**Target shape.** Single `logging.getLogger("coord_smith")`
with a `StreamHandler(sys.stderr)`. `--verbose` /
`--quiet` / `COORDSMITH_LOG_LEVEL` knobs.

**Acceptance.** No `print(..., file=sys.stderr)` in src/.

### B-PROD-4 · Test pyramid hygiene

**Why.** Several files under `tests/unit/` instantiate
`PyAutoGUIAdapter` with mocked pyautogui — that's integration
testing by behavior, not unit testing. Audit B(F).

**Target shape.** Move adapter-pinning tests to
`tests/integration/` and add a shared
`tests/integration/conftest.py` that patches `pyautogui`
once at session scope.

**Acceptance.** `tests/unit/` files are pure-Python unit
tests (no `pyautogui.*` mocks). Integration files share
the conftest harness.

## P3 — Polish

### B-POLISH-1 · Community health files

- `CONTRIBUTING.md` — branch/PR conventions, test setup, how
  to add a recipe field.
- `SECURITY.md` — disclosure contact.
- `.github/PULL_REQUEST_TEMPLATE.md` — checklist (tests,
  invariant changes, recipe-schema backward compat).
- `CODE_OF_CONDUCT.md` — Contributor Covenant boilerplate.

### B-POLISH-2 · `--cleanup` sub-command CLI (depends on B-PROD-1)

Once retention policy lands, expose a manual operator command.

### B-POLISH-3 · `coord-smith --recipe-schema` flag

Emit the Pydantic JSON schema for `ClickRecipe` so agents can
attach it to their prompts without invoking Python. Replaces
the current `python -c "..."` recipe printed in CLAUDE.md.

---

Entries get **removed** from this file when shipped (and added to
`CHANGELOG.md` instead). Adding work here should be done sparingly —
prefer closing the existing list before adding new items.
