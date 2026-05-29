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

### B-CA-4 · ✅ CLOSED — PyAutoGUIAdapter under audit's <700 target

**Status (2026-05-24)**: Three waves shipped. `PyAutoGUIAdapter`
went 892 → 692 lines — under the audit's `< 700` target. Closure
log moved to `CHANGELOG.md [Unreleased]`. Summary:

- Wave 1 (`4af25af`): `adapters/step_guards.py` (phase tagging
  + pre/post-click guard runners). 892 → 865.
- Wave 2 (`67f3447`): `adapters/coord_resolver.py` (image-match
  + coord-fallback chain). 865 → 722.
- Wave 3 (`0aeb918`): dead 1-line delegate cleanup. 722 → 692.

What remains in the adapter is the irreducible OS-touch core:
preflight, screenshot, click, evidence pipeline, and the
`_dispatch_with_step` orchestrator that threads them. The
adapter is now "thin enough" by the audit's own criterion.

A future cosmetic pass could lift `_dispatch_with_step` to a
`StepDispatchOrchestrator` class, but it is not required for
closure — the audit gate was the line count, not the method
count, and that is met.

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

### B-DX-1 · MCP server wrapper (opt-in) — ✗ REJECTED (forki 2026-05-29)

**Status (2026-05-29)**: Closed via a forki decision —
**pure CLI forever; no MCP facade pursued.** The reduced
question was *"who owns how an external agent discovers +
invokes coord-smith — the caller (writes subprocess glue) or
coord-smith (ships an MCP facade)?"* On the
maintenance-simplicity ↔ external-discoverability axis the
maintainer chose simplicity: the permanent upkeep + dependency
surface of a facade package outweighs sparing callers their
subprocess glue. PRD's "MCP transport adoption — permanently
out of scope" stands unchanged; ADR-001 stands. Re-open only if
a real caller demands MCP discovery. Rationale + the
primary-source re-verification that surfaced it:
`docs/reports/2026-05-29-strategic-direction-check.md` §부록 A.

Original (rejected) proposal, kept for the record: a thin MCP
server exposing `--dry-run` / `--recipe-schema` + a `run-recipe`
tool wrapping the CLI, in a separate `coord-smith-mcp/` package
so the core wheel stays dependency-light.

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
