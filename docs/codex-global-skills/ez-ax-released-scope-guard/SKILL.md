---
name: ez-ax-released-scope-guard
description: Check whether a proposed ez-ax task stays within the released autonomous implementation boundary. Use when a task is about to start and you need a clear in-bounds or out-of-bounds decision under prepareSession or pageReadyObserved.
---

# EZ-AX Released Scope Guard

Use this skill before implementation if the task boundary is even slightly
unclear.

## Read First

Always read:

1. `docs/product/prd-e2e-orchestration.md`
2. `docs/product/work-rag.json`
3. `docs/product/rag.json`

## Scope Rules

- Released ceiling is `pageReadyObserved`.
- Released anchors are `prepareSession` and `pageReadyObserved`.
- Modeled stages must not be implemented as released behavior.
- Stop if the proposed task would cross above the released ceiling or blur the
  released versus modeled boundary.

## Output

Return exactly:

- `in-bounds` or `out-of-bounds`
- target anchor
- one-sentence reason
- stop reason if out-of-bounds
