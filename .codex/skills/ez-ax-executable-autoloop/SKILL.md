---
name: ez-ax-executable-autoloop
description: Run the ez-ax low-attention autonomous implementation loop as a skill-first executable entrypoint. Use when the user wants continuous autonomous implementation to start from a skill contract rather than from a raw script command.
---

# EZ-AX Executable AutoLoop

Use this as the user-facing execution skill when the operator wants the
autonomous loop to feel like "run the skill" rather than "run a script."

This skill keeps the validated runner as an internal execution engine, but the
canonical entry contract is the skill itself.

## Mission

Launch continuous low-attention autonomous implementation from canonical repo
state without asking the operator to assemble prompts or commands manually.

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

Do not tell the operator to manually compose prompts when this skill is
available.

## Execution Contract

1. Read canonical inputs in order.
2. Build the next prompt plan from canonical structured state.
3. Execute the low-attention loop in continuous cycles using the validated repo
   runner.
4. Stop only when:
   - canonical state honestly reaches final-stop review, or
   - the runner detects repeated no-progress signatures, or
   - the configured cycle limit is reached.

## Internal Engine

The execution engine for this skill is:

- `scripts/run-low-attention-loop.sh`
- `src/ez_ax/rag/autoloop_runner.py`

These are implementation details behind the skill, not the primary user-facing
contract.

## Default Invocation

Internal default:

- `scripts/run-low-attention-loop.sh --model gpt-5.4-mini --max-cycles 25`

Dry-run check:

- `scripts/run-low-attention-loop.sh --dry-run --max-cycles 1`

## Output Contract

After invocation, report:

- `phase`
- `milestone`
- `anchor`
- `invariant`
- `next_action`
- whether the loop continued or stopped
- the path to the latest cycle message under `artifacts/autoloop/`

