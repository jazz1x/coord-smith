---
name: ez-ax-loop-released-scope-guard-wrapper
description: Repo-local wrapper for ez-ax released-scope guarding. Use when task scope is unclear and the repo adapter should drive the in-bounds or out-of-bounds decision before using the global scope guard behavior.
---

# EZ-AX Loop Released Scope Guard Wrapper

## Read First

1. `docs/llm/repo-autonomous-loop-adapter.yaml`
2. `docs/product/prd-e2e-orchestration.md`
3. `docs/product/work-rag.json`

## Use With

- global skill: `ez-ax-released-scope-guard`
- local prompt: `docs/llm/agents/contract-scope-guardian.md`
- recommended model: `gpt-5.4-mini`

## Wrapper Inputs

- active scope boundary from the adapter
- released anchors from the adapter
- authority boundary from the adapter

## Wrapper Rule

- keep repo-specific anchor and authority rules in the adapter
- do not duplicate generic scope-guard logic here
