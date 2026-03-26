# ez-ax PRD

## Purpose

`ez-ax` is a Python-first orchestration runtime.

Its purpose is to:

- orchestrate execution through `OpenClaw`
- manage graph-based state transitions
- normalize and validate typed evidence
- enforce released execution boundaries
- preserve comparability and verifiability of runs

It is not a browser automation engine.

## System Boundary

- `OpenClaw` is the only browser-facing execution actor
- `ez-ax` is orchestration-centric
- `ez-ax` must not become browser-facing
- `ez-ax` must not treat OpenClaw internals as architecture truth
- `ez-ax` is not a Playwright, CDP, or Chromium control runtime

Authority boundary:

- `OpenClaw` owns browser-facing execution
- `ez-ax` owns orchestration, validation, stopping, and reasoning

Runtime inference boundary:

- The `ez-ax` runtime must not invoke any LLM inference at execution time
- All graph traversal, evidence validation, and stopping decisions are
  deterministic Python; no model calls are made during a run
- `PyAutoGUIAdapter` is the sole execution backend: coordinate-click and
  screenshot only, no LLM calls
- LLM inference is restricted to the offline autoloop harness
  (`ez-ax-autoloop`) that generates implementation; it is not part of the
  runtime path

## Release Boundary

Current released ceiling:

- `pageReadyObserved`

Released implementation scope:

- attach
- prepareSession
- benchmark validation
- pageReadyObserved
- intentional stop at the released ceiling

Anything above `pageReadyObserved` is modeled-only and must not be treated as
released behavior.

Examples of modeled-only stages:

- `syncToServerTime`
- armed state
- trigger wait
- click dispatch
- success completion
- post-ready workflow stages

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

Stopping at `pageReadyObserved` must be provable by typed action-log evidence.

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

## Canonical Memory Model

Only two canonical memory layers exist.

Current-state memory:

- `docs/product/work-rag.json`

Durable lesson memory:

- `docs/product/rag.json`

No third canonical memory layer exists.

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

- `ez-ax` becoming browser-facing
- replacing `OpenClaw`
- direct Playwright, CDP, or Chromium control as product architecture
- release-ceiling expansion above `pageReadyObserved` without explicit PRD
  change
- presenting modeled behavior as released behavior
- TypeScript runtime revival under the active runtime path
- Bun-first canonical runtime or validation direction

## Invariant Reading

This document defines durable system truth only.

Operational loop rules, queue behavior, validation flow, and stop mechanics
belong to the execution model.

Current implementation progress, current phase interpretation, and immediate
continuation context belong to the current-state document.
