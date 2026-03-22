---
name: ez-ax-loop-validation-picker-wrapper
description: Repo-local wrapper for ez-ax validation picking. Use when a task is chosen and the repo adapter should drive the minimum honest validation bundle before using the global validation logic.
---

# EZ-AX Loop Validation Picker Wrapper

## Read First

1. `docs/llm/repo-autonomous-loop-adapter.yaml`
2. `docs/product/prd-python-validation-contract.md`
3. `docs/product/work-rag.json`

## Use With

- global skill: `ez-ax-validation-picker`
- recommended model: `gpt-5.4-mini`

## Wrapper Inputs

- validation floor from the adapter
- active scope boundary from the adapter
- one-task-per-commit and validation-first rules from the adapter

## Wrapper Rule

- keep repo-specific validation commands and floor rules in the adapter
- do not duplicate generic validation-picking logic here
