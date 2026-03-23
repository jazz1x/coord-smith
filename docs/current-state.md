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

At the current state snapshot, the documented queue has been exhausted through
Item 19 after continuous released-scope hardening.

The next continuation step is therefore:

- honor the documented exhaustion: the full heuristic catalog sweep completed
  cleanly with no focused failing artifact and no exact PRD-backed clause gap
  below `pageReadyObserved`
- accept `FINAL_STOP` as the current continuation state until a newly
  documented in-bounds next slice appears

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
