---
name: ez-ax-task-slicer
description: Slice the next ez-ax autonomous implementation task into one smallest safe 1-commit unit. Use when work-rag next_action is broad, when task selection is ambiguous, or when a lower-capacity model needs a single in-bounds task under prepareSession or pageReadyObserved.
---

# EZ-AX Task Slicer

Use this skill to choose exactly one smallest safe implementation task for the
current loop.

## Read First

Always read:

1. `AGENTS.md`
2. `docs/product/prd-e2e-orchestration.md`
3. `docs/product/work-rag.json`
4. `docs/product/rag.json`

Read additional runtime PRDs only if the candidate task touches that domain.

## Repository Invariants

- `OpenClaw` is the only browser-facing actor.
- Python-first is the canonical path.
- Released ceiling is `pageReadyObserved`.
- Do not treat modeled behavior as released.
- Do not reintroduce TypeScript or Bun runtime paths.
- Prefer `active-implementation` lessons over `historical-cutover` lessons.

## Task Selection Rules

- Prefer `work-rag.json` `current.next_action` if it is already a one-commit
  task.
- Otherwise choose one smallest in-bounds implementation or test-hardening
  slice.
- Prefer work under `prepareSession` or `pageReadyObserved`.
- Prefer one file group and one focused validation target.
- Reject tasks that span multiple milestones, require broad validation, or mix
  runtime behavior change with a large docs rewrite.
- If no safe task exists, stop rather than widening scope.

## Output

Return exactly:

- `phase / milestone / anchor / invariant / next action`
- chosen task
- why this is the smallest safe task
- primary file group
- focused validation target
- stop reason if no safe task exists
