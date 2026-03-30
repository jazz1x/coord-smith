---
name: ez-ax-executable-autoloop
description: Run the ez-ax low-attention autonomous implementation loop as the single skill-first operator entrypoint. Use when the operator wants continuous autonomous implementation to start from one skill contract rather than assembling prompts manually.
---

# EZ-AX Executable AutoLoop

Single operator-facing entrypoint for continuous autonomous implementation.

## Mission

Launch continuous low-attention autonomous implementation from canonical repo
state without requiring the operator to assemble prompts, scripts, or runner
commands manually.

## Read First

1. `AGENTS.md`
2. `docs/prd.md`
3. `docs/execution-model.md`
4. `docs/current-state.md`
5. `docs/product/work-rag.json`
6. `docs/product/rag.json`
7. `docs/llm/repo-autonomous-loop-adapter.yaml`
8. `docs/llm/low-attention-execution-contract.json`
9. `docs/llm/low-attention-coverage-ledger.json`

## Operator Rule

Treat this skill as the primary operator entrypoint for continuous autonomous
implementation. Do not ask the operator to manually compose prompts or invoke
runner scripts when this skill is available.

## Execution Path

**To run autonomous implementation:**

```
ez-ax-autoloop [--model claude-haiku-4-5-20251001] [--max-cycles 25] [--dry-run]
```

This invokes the low-attention autonomous loop under the active PRD contract.
The loop will:
1. Generate a prompt plan from canonical sources
2. Run validation gate (pytest, mypy, ruff)
3. Invoke Claude to implement one bounded task
4. Commit and update work-rag.json
5. Loop until FINAL_STOP is reached

## Pre-Execution Checklist

Before running the autonomous loop, verify:
1. Read canonical inputs in order (listed in "Read First" section above)
2. Quote the exact on-disk `docs/product/work-rag.json` `current.next_action` verbatim
3. Understand the active phase / milestone / anchor / invariant
4. If `current.next_action` names a concrete slice, the loop will execute it
5. If `current.next_action` says `FINAL_STOP`, the loop will run the full exhaustion protocol before stopping

## Execution Contract

1. Run: `ez-ax-autoloop` CLI script
2. The script will execute the loop logic defined in `/ez-ax-autoloop`
3. Each cycle: generate prompt → validate → claude --print → commit → loop
4. Stop only when canonical state honestly reaches final-stop review after the
   full documented exhaustion protocol

## Output Contract

After invocation, report:

- `phase`
- `milestone`
- `anchor`
- `invariant`
- `next_action`
- Whether the loop continued or stopped
- Latest canonical continuation state from `docs/product/work-rag.json`
