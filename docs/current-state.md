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
- transport-agnostic OpenClaw adapter boundary contract
- optional MCP-backed adapter reference contract
- Python-first runtime path
- two-tier memory operation with `work-rag.json` and `rag.json`
- low-attention autonomous loop rules
- documented low-attention implementation queue
- skill-first executable autoloop entrypoint for operators

## Scope Snapshot

Implemented and hardened for the current released ceiling:

- released-scope graph and entrypoint wiring up to `pageReadyObserved`
- released-scope OpenClaw adapter boundary and response validation
- optional MCP-backed acquisition scaffold
- released-scope evidence envelope, checkpoint comparability, and reporting
- current-memory and durable-lesson RAG helpers
- typed error hierarchy and mission anchor mapping needed below the released
  ceiling

Already present but still modeled-only or released-scope-adjacent:

- modeled helper entrypoints, including MCP-backed reference helpers, that still stop at
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

At the current state snapshot, the mandatory self-seeding contract slice has
now closed honestly.

The documented next continuation step is now one mandatory
continuation-seeding pass driven by the loop itself rather than `FINAL_STOP`
review.

That pass must read the machine-readable execution contract and coverage
ledger first, then seed exactly one deterministic next slice if canonical
sources can still name one honestly.

## Active Anchor Coverage Ledger

Canonical machine-readable ledger:

- `docs/llm/low-attention-execution-contract.json`
- `docs/llm/low-attention-coverage-ledger.json`

| Family | Status | Evidence Or Reason | Next Slice Hint |
| --- | --- | --- | --- |
| released graph wiring and call-sites | covered | released graph call-site and run-root surfaces already have queue and resume-search coverage evidence | none |
| released entrypoint / CLI / input family | covered | released entrypoint, CLI shim, and released input resolution already closed as queue slices | none |
| released OpenClaw transport-boundary family | covered | the canonical OpenClaw adapter contract now exposes an explicit transport-neutral injected boundary protocol in `src/ez_ax/adapters/openclaw/client.py`, and the focused Item 27 validation bundle stayed green | none |
| released evidence / reporting / comparability family | covered | evidence envelope, reporting summary, and checkpoint comparability already closed as in-bounds slices | none |
| typed mission / error / memory helper family | covered | mission mapping, typed errors, and RAG path helper surfaces already closed as queue slices | none |
| modeled helper entrypoint family | covered | modeled MCP helper, CLI summary helper, argv helper, argv+env helper, and follow-on config support surfaces already have closure evidence | none |
| docs-sufficiency family for lower-capacity continuation | covered | canonical current state now rewrites queue-tail exhaustion into one mandatory continuation-seeding pass, so lower-capacity agents do not treat queue exhaustion as terminal before the loop seeds its own next slice | none |

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
