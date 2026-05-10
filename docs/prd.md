# coord-smith PRD

## Purpose

`coord-smith` is a Python-first orchestration runtime.

Its purpose is to:

- orchestrate execution through `OpenClaw`
- manage graph-based state transitions
- normalize and validate typed evidence
- enforce released execution boundaries
- preserve comparability and verifiability of runs

It is not a browser automation engine.

## System Boundary

- `OpenClaw` is the only browser-facing execution actor
- `coord-smith` is orchestration-centric
- `coord-smith` must not become browser-facing
- `coord-smith` must not treat OpenClaw internals as architecture truth
- `coord-smith` is not a Playwright, CDP, or Chromium control runtime

Authority boundary:

- `OpenClaw` owns browser-facing execution
- `coord-smith` owns orchestration, validation, stopping, and reasoning

Runtime inference boundary:

- The `coord-smith` runtime must not invoke any LLM inference at execution time
- All graph traversal, evidence validation, and stopping decisions are
  deterministic Python; no model calls are made during a run
- `PyAutoGUIAdapter` is the sole execution backend: coordinate-click and
  screenshot only, no LLM calls

## Release Boundary

Current released ceiling:

- `runCompletion`

Released implementation scope:

- attach
- prepareSession
- benchmark validation
- pageReadyObserved
- syncObservation
- targetActionabilityObservation
- armedStateEntry
- triggerWait
- clickDispatch
- clickCompletion
- successObservation
- runCompletion
- intentional stop at the released ceiling

No missions are currently modeled-only. All stages are released.

## Evidence Truth Model

Truth priority:

1. `dom`
2. `text`
3. `clock`
4. `action-log`

Fallback only:

- `screenshot`
- `vision`

Last-resort execution primitive only:

- `coordinate`

Rules:

- truth must not be derived from vision or coordinates alone
- typed evidence is required for released-scope decisions

## Release-Ceiling Stop Proof

Stopping at `runCompletion` must be provable by typed action-log evidence.

Required evidence ref:

- `evidence://action-log/release-ceiling-stop`

Expected artifact example:

- `artifacts/action-log/release-ceiling-stop.jsonl`

Required typed fields:

- `event`
- `mission_name`
- `ts`

If this artifact cannot be resolved or the typed fields are missing, the system
must not claim a correct released-ceiling stop.

## Canonical Stack

The canonical implementation path is Python-first.

Expected stack direction:

- Python runtime
- LangGraph
- LangChain-core
- Pydantic v2
- pytest
- ruff
- mypy

## Non-Goals And Forbidden Directions

The following are not in scope for casual change:

- `coord-smith` becoming browser-facing
- replacing `OpenClaw`
- direct Playwright, CDP, or Chromium control as product architecture
- release-ceiling expansion above `runCompletion` without explicit PRD
  change
- presenting modeled behavior as released behavior
- TypeScript runtime revival under the active runtime path
- Bun-first canonical runtime or validation direction
- MCP transport adoption — permanently out of scope. The active transport
  between `OpenClaw` and `coord-smith` is CLI subprocess (`coord-smith --click-recipe`
  → exit code + `artifacts/`). Prior `mcp_stdio` scaffold modules were
  removed; reviving MCP requires a new PRD that supersedes this decision.
- Stateful long-running session — permanently out of scope. `coord-smith`
  is invoked, runs to `runCompletion`, and exits. There is no persistent
  process accepting click-at-a-time over stdin or socket. Multi-step
  flows are expressed declaratively as a step list inside a single
  invocation; orchestrators that need mid-flow reasoning split steps
  across multiple invocations (stateless chain). Reviving a stateful
  daemon mode requires a new PRD that supersedes this decision.
- Modeled missions beyond `runCompletion` — permanently out of scope.
  The seven control-tier missions that previously sat above the released
  ceiling (`release_gate_evaluation`, `retry_or_stop_decision`,
  `work_rag_update`, `work_rag_compression`, `lesson_promotion`,
  `e2e_replay_or_comparison`, `python_validation_execution`) plus
  `benchmark_validation` are removed. `ALL_MISSIONS` equals
  `RELEASED_MISSIONS`. Reviving any of them requires a new PRD that
  supersedes this decision.

## Invariant Reading

This document defines durable system truth only.

Current implementation progress, current phase interpretation, and immediate
continuation context belong to `docs/current-state.md`.
