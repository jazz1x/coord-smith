---
name: ez-ax-executable-autoloop
description: Run the ez-ax low-attention autonomous implementation loop as the single skill-first operator entrypoint. Use when the user wants continuous autonomous implementation to start from one skill contract rather than from prompts or scripts.
---

# EZ-AX Executable AutoLoop

Use this as the single user-facing execution skill.

## Mission

Launch continuous low-attention autonomous implementation from canonical repo
state without asking the operator to assemble prompts, scripts, or runner
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
10. `docs/llm/low-attention-slice-templates.json`
11. `.codex/skills/ez-ax-low-attention-autoloop/SKILL.md`

## User-Facing Rule

Treat this skill as the primary operator entrypoint for continuous autonomous
implementation.

Do not tell the operator to manually compose prompts or invoke runner scripts
when this skill is available.

## Execution Contract

1. Read canonical inputs in order.
2. Build the next prompt plan from canonical structured state.
3. Execute the low-attention loop in continuous cycles under this skill
   contract.
4. Stop only when:
   - canonical state honestly reaches final-stop review, or
   - repeated no-progress signatures appear in canonical continuation state, or
   - the configured cycle limit is reached.

## Output Contract

After invocation, report:

- `phase`
- `milestone`
- `anchor`
- `invariant`
- `next_action`
- whether the loop continued or stopped
- the latest canonical continuation state from `docs/product/work-rag.json`
