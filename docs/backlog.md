# coord-smith Productization Backlog

This file lists post-v0.1.0 work not yet undertaken. Each entry is
sized for a self-contained PRD: a single owner concern, clear
acceptance criteria, severable from the others. Do not silently
fold these into unrelated PRs.

The v0.1.0 productization sweep (2026-05-13) closed **9 of the 13
items** that were listed here previously. See `CHANGELOG.md
[0.1.0]` for the rolled-up summary. What remains:

## P3 — Polish

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
