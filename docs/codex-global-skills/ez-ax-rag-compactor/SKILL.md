---
name: ez-ax-rag-compactor
description: Update and compress ez-ax self-RAG after one autonomous task. Use when a task is closed and work-rag needs one new checkpoint, current-state refresh, history trimming, or a lesson-promotion decision.
---

# EZ-AX RAG Compactor

Use this skill at task close, after validation and before commit.

## Read First

Always read:

1. `docs/product/work-rag.json`
2. `docs/product/rag.json`
3. `docs/product/prd-python-rag-operations.md`

## Rules

- Keep `work-rag.json` current short and single-threaded.
- Add exactly one new checkpoint for the closed task.
- Compact same-scope checkpoints when they become noisy.
- Do not duplicate step logs into `rag.json`.
- Promote only durable lessons.
- Tag new lessons with `active-implementation` or `historical-cutover`.
- Prefer `active-implementation` lessons for the current coding loop.

## Output

Return exactly:

- updated current state summary
- whether one history entry should be added
- whether history should be compacted
- whether a lesson should be promoted
- lesson tag recommendation if promoted
