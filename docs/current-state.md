# ez-ax Current State

## Purpose

This document is the current implementation snapshot for low-attention
continuation.

It is intentionally changeable and subordinate to:

- `docs/prd.md`
- `docs/core-loop.md` (quick operating reference)
- `docs/execution-model.md` (detailed rules — read only for exhaustion/stop decisions)
- the active product PRD set under `docs/product/`

## Current Phase Snapshot

- phase: `Phase R63 — heuristic gap scan and released-path E2E scaffold hardening`
- milestone: `Phase R63 initial synthetic E2E verification complete`
- anchor: `r63ReleasedPathE2E`
- invariant: `ez-ax` runtime graph contains no LLM inference. `ez-ax` remains orchestration-centric. The execution backend is PyAutoGUI (OS-level coordinate click). Browser-internal tools (Playwright, CDP) are forbidden as execution backend. The released ceiling expands from pageReadyObserved to runCompletion. Canonical continuation memory remains two-tiered: `work-rag` for current state, `rag` for durable lessons. OpenClaw is the external caller; ez-ax owns the CUA engine (PyAutoGUI).

## Current Interpretation

Phase R65 complete. Phase transition in progress: `Phase R66 heuristic gap scan` is the active task.

## What Is Already Established

All 60 coverage-ledger families complete and verified (59 covered + 1 excluded). Phase R60 comprehensive verification confirms all released-scope clauses have dedicated tests. Historical summary:

- Phases R3-R6 (6 families): Core runtime foundations
  1. test fixture module importability (verified)
  2. released-scope integration test (verified)
  3. console-script entry validation (verified)
  4. openclaw request validation completeness (verified)
  5. evidence artifact loading and verification (verified)
  6. release-ceiling stop proof construction (verified)

- Phases R7-R13 (7 families): Runtime graph, evidence envelope, mission specification
  7. runtime graph plan building and transitions (12 unit tests)
  8. evidence envelope functions (17 unit tests)
  9. forward transition evaluation (4 unit tests)
  10. EvidenceEnvelope dataclass (4 unit tests)
  11. evidence truth model constraints (3 unit tests: reject screenshot/coordinate-only)
  12. released missions specification (4 unit tests: tuple, count, boundary, separation)
  13. runtime LLM-free invariant (3 unit tests: determinism, PyAutoGUI-only, no LLM calls)

- Phases R14-R18 (5 families): Memory, stack, evidence typing, truth priority, browser boundary
  14. canonical memory model (1 unit test: two-tier only, no third layer)
  15. canonical stack specification (5 unit tests: Python 3.12+, LangGraph, LangChain, Pydantic v2, tools)
  16. typed evidence requirement (2 unit tests: typed evidence, primary types in decisions)
  17. truth priority order specification (1 unit test: dom > text > clock > action-log > screenshot > coordinate)
  18. browser control library boundary (4 unit tests: no Playwright/CDP/Chromium imports)

## Architecture Decisions (2026-03-26)

### Runtime engine is LLM-free

The ez-ax runtime graph contains no LLM inference at execution time.
Each LangGraph node is deterministic: state setup, adapter call, evidence
collection. The adapter implementation (PyAutoGUI) is also deterministic.
This is now documented in `docs/prd.md` System Boundary — Runtime inference
boundary block.

### OpenClaw CUA replaced by PyAutoGUI

`src/ez_ax/adapters/pyautogui_adapter.py` implements `OpenClawAdapter.execute()`
using `pyautogui.click(x, y)` and `pyautogui.screenshot()` exclusively.
No LLM calls. Wired to the released-scope graph via
`src/ez_ax/graph/pyautogui_cli_entrypoint.py` (`ez-ax` console script).

### Browser-internal tools forbidden

Playwright, CDP, and similar browser-internal access tools are forbidden as
the execution backend. Only OS-level coordinate interaction is permitted.

### Autoloop orchestration vs coding separation

`autoloop_runner.py` now calls `run_validation_gate()` (pytest/mypy/ruff via
direct subprocess) before each claude cycle. LLM is asked only to write
code; all validation is owned by the Python harness.

## Scope Snapshot

Carried forward from Phase R3:

- released-scope graph and entrypoint wiring up to `pageReadyObserved`
- released-scope adapter boundary and response validation
- released-scope evidence envelope, checkpoint comparability, and reporting
- current-memory and durable-lesson RAG helpers
- typed error hierarchy and mission anchor mapping

Phase R4 complete:

- PyAutoGUI adapter implementing `OpenClawAdapter` protocol (covered)
- PRD invariant update for LLM-free runtime (covered)
- Autoloop runner deterministic orchestration / validation gate (covered)
- `ez-ax` and `ez-ax-autoloop` console scripts registered in `pyproject.toml` (covered)

Phase R5 complete:

- test fixture module importability (covered)
- released-scope integration test (covered)
- console-script entry validation (covered)

Phase R6 complete:

- openclaw request validation completeness (covered)
- evidence artifact loading and verification (covered)
- release-ceiling stop proof construction (covered)

## Current Continuation State

The canonical current-tense continuation state lives in
`docs/product/work-rag.json`.

The current next action is: `Phase R66 heuristic gap scan`

## Active Anchor Coverage Ledger

Canonical machine-readable ledger:

- `docs/llm/low-attention-execution-contract.json`
- `docs/llm/low-attention-coverage-ledger.json`

**Status: All 60 families complete (59 covered + 1 excluded) — FINAL_STOP reached**

All coverage-ledger families are complete and verified:
- Phases R1-R2: Foundation bootstrap phases
- Phases R3-R6 (6 families): Core runtime foundations
- Phases R7-R13 (7 families): Runtime graph, evidence envelope, mission specification
- Phases R14-R20 (7 families): Memory, stack, evidence typing, truth priority, browser boundary, OpenClaw abstraction, orchestration-centric
- Phases R21-R26 (6 families): Released scope structures and specifications
- Phases R27-R41 (15 families): Purpose clauses, release boundary, evidence handling, boundary enforcement
- Phases R42-R48 (7 families): Comprehensive heuristic gap scans confirming all clauses covered
- Phase R49 (1 family): Final heuristic gap scan verification — all PRD clauses have dedicated tests
- Phase R50 (1 family): Bounded resume-search and final gap verification — all 50 families confirmed complete
- Phase R51 (1 family): Released-scope enforcement verification — all 4 missions, ceiling-stop proof, enforcement confirmed
- Phase R52 (1 family): Final comprehensive verification — all 52 families verified complete
- Phase R53 (1 family): Final comprehensive heuristic gap scan — all 37+ PRD clauses below pageReadyObserved verified covered
- Phases R54-R58 (5 families): Extended heuristic gap scans confirming no new uncovered clauses emerged
- Phase R59 (1 family): Comprehensive PRD clause verification — all 8 sections, all 4 missions, all boundaries, all constraints verified covered
- Phase R60 (1 family): Final verification — all released-scope implementation clauses have dedicated unit test coverage; no uncovered clauses remain
- Phase R61 (1 family): Excluded — FINAL_STOP reached; continuation not required

## Source Of Ongoing Truth

This document is a readable summary.

For actual continuation, the agent must still defer to:

- `docs/product/work-rag.json` for the active next action
- `docs/product/rag.json` for durable lessons
- the product PRD set for domain-specific contracts
