# ez-ax Current State

## Purpose

This document is the current implementation snapshot for low-attention
continuation.

It is intentionally changeable and subordinate to:

- `docs/prd.md`
- `docs/execution-model.md`
- the active product PRD set under `docs/product/`

## Current Phase Snapshot

- phase: `Phase R3 — Fresh Python Bootstrap`
- milestone: `Low-attention autonomous continuation remains unambiguous under the Python-first PRD contract`
- anchor: `pythonRuntimeBootstrapCreated`
- invariant: `OpenClaw` remains the only browser-facing actor, `ez-ax` remains orchestration-centric, the released ceiling remains `pageReadyObserved`, and canonical continuation memory remains two-tiered: `work-rag` for current state and `rag` for durable lessons

## Current Interpretation

The project is in execution-scaffold hardening below the released ceiling.

This is not:

- full browser automation release
- modeled-stage implementation
- release-ceiling expansion

This is:

- Python-first scaffold hardening
- released-scope contract enforcement
- typed validation tightening
- graph-transition and comparability hardening
- low-attention continuation stabilization

## What Is Already Established

The repository already has the following foundations in place:

- OpenClaw boundary contract definition
- released-scope evidence contract
- release-ceiling stop proof contract
- `evidence_refs` schema and released minimums
- typed error hierarchy
- MCP-backed adapter direction and acquisition contract
- Python-first runtime path
- two-tier memory operation with `work-rag.json` and `rag.json`
- low-attention autonomous loop rules
- documented low-attention implementation queue

## Scope Snapshot

Implemented and hardened for the current released ceiling:

- released-scope graph and entrypoint wiring up to `pageReadyObserved`
- released-scope OpenClaw adapter, MCP acquisition, and response validation
- released-scope evidence envelope, checkpoint comparability, and reporting
- current-memory and durable-lesson RAG helpers
- typed error hierarchy and mission anchor mapping needed below the released
  ceiling

Already present but still modeled-only or released-scope-adjacent:

- MCP-backed modeled helper entrypoints that still stop at
  `pageReadyObserved`
- modeled mission and node definitions above the current released ceiling
- post-ready workflow stages such as `sync_observation`, `armed_state_entry`,
  `trigger_wait`, `click_dispatch`, and `success_observation`

## Current Goal

Keep the Python-first released-scope scaffold hard enough that a lower-capacity
agent can continue across consecutive one-commit slices without crossing above
`pageReadyObserved`.

Current cycle decision question:

- does any exact PRD-backed contract gap still exist at or below
  `pageReadyObserved`?

## Current Continuation State

The canonical current-tense continuation state lives in
`docs/product/work-rag.json`.

The current continuation state should prefer an immediately resumable next slice
over a paused stop-like state whenever one documented in-bounds action still
exists.

When that happens, the execution model now allows one bounded resume-search
pass across the released-scope file groups listed in `docs/execution-model.md`
and then one full documented heuristic-catalog sweep before accepting final
stop.

At the current state snapshot, the documented queue has already closed through
Item 25, but one exact PRD-backed in-bounds surface was omitted from the
documented continuation path.

The next continuation step is therefore:

- reopen the queue with Item 26 for
  `src/ez_ax/config/mcp_stdio.py` using
  `tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
- treat this as an in-bounds continuation-seeding slice for the explicit MCP
  client acquisition contract feeding released-graph injection

## Consultation Context

When asking another agent for help, the useful question is not “what feature
should be built next?” but:

- is there one more valid in-bounds surface below `pageReadyObserved`?
- if so, can it be expressed as one new queue item?
- if not, is the current stop the correct final low-attention endpoint?

Any proposed continuation must remain:

- below `pageReadyObserved`
- Python-first
- OpenClaw-boundary preserving
- one-task-per-commit
- multi-commit continuation friendly
- verifiable with focused validation

## Source Of Ongoing Truth

This document is a readable summary.

For actual continuation, the agent must still defer to:

- `docs/product/work-rag.json` for the active next action
- `docs/product/rag.json` for durable lessons
- the product PRD set for domain-specific contracts
