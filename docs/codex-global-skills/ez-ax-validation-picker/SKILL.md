---
name: ez-ax-validation-picker
description: Pick the smallest honest validation bundle for the current ez-ax task. Use when a task is selected and you need the minimum focused checks that still satisfy the repository validation floor.
---

# EZ-AX Validation Picker

Use this skill after the task is chosen and before final reporting.

## Read First

Always read:

1. `docs/product/prd-python-validation-contract.md`
2. `docs/product/prd-e2e-orchestration.md`
3. `docs/product/work-rag.json`

## Validation Rules

- Docs-only: validate changed structured artifacts and run `git diff --check`.
- Test-only: run the changed test target directly.
- Behavior or contract change: run one focused test plus the narrowest
  applicable lint or type check.
- Mixed docs and behavior: treat it as behavior or contract change.
- Never go below the repository validation floor.
- If no honest validation path exists, stop.

## Output

Return exactly:

- validation commands
- why these are the minimum honest checks
- what was intentionally not run
- stop reason if validation cannot be chosen honestly
