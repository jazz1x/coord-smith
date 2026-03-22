---
name: ez-ax-loop-task-slicer-wrapper
description: Repo-local wrapper for ez-ax autonomous task slicing. Use when choosing the next one-commit implementation slice and load the repo adapter before relying on the global task-slicer behavior.
---

# EZ-AX Loop Task Slicer Wrapper

This wrapper keeps repo-specific execution inputs local while delegating generic
loop behavior to the global task-slicing skill.

## Read First

1. `docs/llm/repo-autonomous-loop-adapter.yaml`
2. `docs/product/work-rag.json`
3. `docs/product/rag.json`

## Use With

- global skill: `ez-ax-task-slicer`
- recommended model: `gpt-5.4-mini`

## Wrapper Inputs

- active scope boundary from the adapter
- released anchors from the adapter
- authority boundary from the adapter
- validation-first and one-task-per-commit rules from the adapter
- lesson priority tags from the adapter

## Wrapper Rule

- do not duplicate generic task-slicing logic here
- use this wrapper to feed adapter inputs into the global skill behavior
