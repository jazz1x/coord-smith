---
name: ez-ax-loop-rag-compaction-wrapper
description: Repo-local wrapper for ez-ax current-tense RAG compaction. Use when one task is closed and the repo adapter should drive work-rag update, history compaction, and durable lesson tagging before using the global compaction behavior.
---

# EZ-AX Loop RAG Compaction Wrapper

## Read First

1. `docs/llm/repo-autonomous-loop-adapter.yaml`
2. `docs/product/work-rag.json`
3. `docs/product/rag.json`

## Use With

- global skill: `ez-ax-rag-compactor`
- local prompt: `docs/llm/agents/assetization-pattern-promoter.md`
- recommended model: `gpt-5.4-nano`

## Wrapper Inputs

- continuation-memory path from the adapter
- reusable asset-memory path from the adapter
- compaction command from the adapter
- compaction limits from the adapter
- lesson tagging rules from the adapter

## Wrapper Rule

- keep repo-specific memory paths and limits in the adapter
- do not duplicate generic compaction logic here
