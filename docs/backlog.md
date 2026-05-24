# coord-smith Productization Backlog

This file lists post-v0.1.0 work not yet undertaken. Each entry is
sized for a self-contained PRD: a single owner concern, clear
acceptance criteria, severable from the others. Do not silently
fold these into unrelated PRs.

The v0.1.0 productization sweep (2026-05-13) closed **9 of the 13
items** that were listed here previously. See `CHANGELOG.md
[0.1.0]` for the rolled-up summary. The v0.1.1 audit-closure
sweep (2026-05-23) added 3 deferred items below (B-CA-4 / B-CA-5 /
B-POLISH-3). What remains:

## P3 — Architectural refactors (Clean Arch pass #2 deferred)

### B-CA-4 · Continue PyAutoGUIAdapter slimming (PARTIAL — waves 1 + 2 shipped, 22 lines from target)

**Status (2026-05-24)**: Two waves landed. `PyAutoGUIAdapter`
went 892 → 722 lines.

- **Wave 1** (commit `4af25af`): `adapters/step_guards.py` owns
  the phase tagging (`PhaseName` Literal, `tag_phase` /
  `read_phase` helpers, `PHASE_PRE_CLICK` / `PHASE_DISPATCH` /
  `PHASE_POST_CLICK` constants) and the pre/post-click guard
  runners (`run_pre_click_wait_for`, `run_post_click_signal`),
  connected to the adapter via the `StepGuardCollaborator`
  Protocol. Adapter: 892 → 865 lines.

- **Wave 2** (commit `67f3447`): `adapters/coord_resolver.py`
  owns the click-coordinate resolution chain
  (`locate_image_target`, `locate_image_for_step`,
  `locate_image_or_none`, `coord_or_none`,
  `resolve_step_click_coords`), connected via the
  `CoordResolverCollaborator` Protocol. The five adapter
  methods are now 1-line delegates. Adapter: 865 → 722 lines.

**Remaining (22 lines from target)**: one extractable cluster
left:

- `_dispatch_with_step` body — the orchestration that threads
  preflight + image-match + click + verify_transition + signal
  + failure-capture. Could lift to a `StepDispatchOrchestrator`
  class. This is the largest remaining method and the only one
  that still genuinely needs the full adapter context (lock +
  log + screenshot + capture + clock all participate).

Acceptance for full closure: adapter < 700 lines AND the
dispatch orchestrator has dedicated unit-level tests. The
current 722-line adapter is **practically clean** — what
remains is the core OS-touch primitives (preflight, screenshot,
click, run-id wiring) plus the dispatch orchestrator. Further
extraction is a polish concern, not a correctness one.

### B-CA-5 · ✅ CLOSED in commit `858b1d5` — run-summary lifecycle CM

Extracted to `reporting/run_summary_lifecycle.py`
(`RunSummaryLifecycle` context manager with
`set_outcome(status, exit_code)`). CLI `main()` no longer
hand-manages the writer + outcome + try/finally + flush
quartet — one `with` block + per-branch `set_outcome` call.
7 unit tests pin the contract.

## P3 — Polish

### B-POLISH-3 · PyPI version + downloads badges (post-publish)

Add `[![PyPI](https://img.shields.io/pypi/v/coord-smith)]`
and `[![Downloads](https://img.shields.io/pypi/dm/coord-smith)]`
shields to README.md / README.ko.md once a wheel is actually
on PyPI. Cosmetic; cannot land before the first PyPI push.

### B-POLISH-1.5 · Remaining community files

- `CODE_OF_CONDUCT.md` — Contributor Covenant boilerplate.
- `.github/ISSUE_TEMPLATE/bug_report.md` and
  `.github/ISSUE_TEMPLATE/feature_request.md`.
- `.github/FUNDING.yml` (only if we accept sponsorship — defer
  the decision).

Cost: tiny. Defer until the project receives external contributions.

## P3 — Operational

### B-PROD-1.5 · Opportunistic post-run auto-cleanup

`coord-smith --cleanup` already exists. The opportunistic variant
would have `_run` call `cleanup_runs` (with the same default
bounds) after a successful run, so artifact-tree growth stays
bounded without an operator cron job. Defer until usage data
shows real bloat — most callers may prefer running `--cleanup`
explicitly to keep failure runs around for diagnosis.

### B-PROD-2.5 · CI: matrix expansion + macOS smoke job

`.github/workflows/ci.yml` runs on Ubuntu + Python 3.14. Once we
have a real macOS runner with Accessibility permission granted,
add a `-m real` job that exercises the pyautogui real-binary
tests. Until then the `-m real` tests are dev-laptop only.

### B-PROD-2.6 · Release workflow

Tag-driven release that builds the wheel + sdist via `uv build`
and uploads to PyPI via `twine` (or `uv publish` once stable).
Today versioning is manual (edit `pyproject.toml` + `__init__.py`
in lockstep). Decide later whether to adopt `hatch` dynamic
versioning or `commitizen` `cz bump`.

## P3 — DX / agent integration

### B-DX-1 · MCP server wrapper (opt-in)

A thin MCP server that exposes `coord-smith --dry-run` and
`coord-smith --recipe-schema` as tools, plus a `run-recipe`
tool that wraps the standard CLI invocation. Lets an LLM-host
discover and call coord-smith without writing subprocess code.
PRD must:

- Pin that the MCP wrapper does NOT extend the runtime contract
  (ADR-001 stays intact — wrapper is an MCP veneer, not new
  runtime behaviour).
- Decide where the wrapper lives (separate sibling package
  `coord-smith-mcp/`? same wheel with `[mcp]` extra? sibling
  project entirely?). The audit recommendation is "separate
  package" so the core wheel stays dependency-light.

### B-DX-2 · Telemetry / structured events stream

`run.json` is the post-run envelope. A streaming-events variant
(NDJSON to stdout? UDS socket?) would let a live dashboard
watch a long flow without polling the disk. Defer until a
caller asks for it; right now the file-tail pattern is
sufficient.

## Recently closed (in v0.1.0)

For reference, the following backlog items shipped in 0.1.0 and
are tracked in `CHANGELOG.md`:

- B-CA-1 split `adapters/execution/client.py`
- B-CA-2 extract `ActionLogWriter`
- B-CA-3 unify `_FALLBACK_REFS` ↔ `validate_execution_result`
  evidence manifest
- B-ROP-1 NewType identifiers
- B-ROP-2 Result-style dual-target fallback
- B-ROP-3 `ResolvedImagePath` NewType
- B-PROD-1 disk rotation `--cleanup` (manual sub-command;
  opportunistic auto-cleanup is P3 / B-PROD-1.5)
- B-PROD-2 CI workflow (ubuntu / py 3.14; matrix expansion is
  P3 / B-PROD-2.5)
- B-PROD-3 stdlib logging
- B-PROD-4 test pyramid hygiene
- B-POLISH-1 (community files — most landed: PR template,
  dependabot, CONTRIBUTING, SECURITY; remaining cluster moved
  to B-POLISH-1.5)
- B-POLISH-2 `--cleanup` CLI sub-command
- B-POLISH-3 `--recipe-schema` flag

---

Entries get **removed** from this file when shipped (and added to
`CHANGELOG.md` instead). Adding work here should be done sparingly —
prefer closing the existing list before adding new items.
