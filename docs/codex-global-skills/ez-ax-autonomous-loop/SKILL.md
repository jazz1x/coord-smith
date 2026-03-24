---
name: ez-ax-autonomous-loop
description: Run the ez-ax autonomous implementation loop end to end for one bounded task. Use when a fresh session should read canonical sources, pick one smallest safe in-bounds task, validate honestly, update canonical RAG, and stop with a commit.
---

# EZ-AX Autonomous Loop

Use this skill to run one full autonomous implementation cycle without
reconstructing the repo rules from scratch.

## Read First

1. `AGENTS.md`
2. `docs/prd.md`
3. `docs/execution-model.md`
4. `docs/current-state.md`
5. `docs/product/work-rag.json`
6. `docs/product/rag.json`
7. `docs/llm/repo-autonomous-loop-adapter.yaml`

Read additional PRDs only when the chosen task touches that domain.

## Core Invariants

- `OpenClaw` is the only browser-facing actor.
- `ez-ax` remains orchestration-centric.
- Python-first is the canonical implementation path.
- Released ceiling is `pageReadyObserved`.
- Only `prepareSession` and `pageReadyObserved` are released anchors.
- Do not present scaffold hardening as released-path execution.

## Use With

- wrapper skill: `ez-ax-loop-task-slicer-wrapper`
- wrapper skill: `ez-ax-loop-released-scope-guard-wrapper`
- wrapper skill: `ez-ax-loop-validation-picker-wrapper`
- wrapper skill: `ez-ax-loop-rag-compaction-wrapper`

If the wrapper skills are unavailable, follow the same loop manually with the
canonical sources and adapter.

## Loop

1. State `phase / milestone / anchor / invariant / next action` from `docs/product/work-rag.json`.
2. Quote the exact on-disk `current.next_action` verbatim before interpreting it.
3. Decide whether `current.next_action` is already a one-commit task.
4. If the quoted `current.next_action` names a concrete documented queue item, one focused validation command, one PRD, and one file group, execute that slice and do not treat the repository as paused.
5. If `current.next_action` is a paused or stop-state instruction, run one bounded resume-search pass:
   - first identify one focused pytest target on the active anchor surface
   - if pytest is clean, identify one focused mypy target for the active file group when typing is part of the contract
   - if mypy is clean, identify one focused ruff check target for the active file group
   - if focused validation is clean, identify one exact unenforced PRD clause plus one exact primary code location
   - record one minimum honest validation command for the follow-on task
   - if no exact gap is found for the current file group, advance to the next documented queued file group
   - if the primary queue is exhausted cleanly, advance to the next documented secondary queued file group
   - only stop for external input if neither exists without guesswork and the documented queues are exhausted
6. If scope is even slightly unclear, use the released-scope guard wrapper before implementation.
7. Choose exactly one smallest safe in-bounds task under `prepareSession` or `pageReadyObserved`.
8. Implement only that task.
9. Choose the minimum honest validation bundle.
10. Run validation and stop if it fails.
11. Update `docs/product/work-rag.json` current state and add exactly one new same-task history entry.
12. Promote a lesson into `docs/product/rag.json` only if it is durable and reusable.
13. Commit the finished task before starting another loop.

## Stop Conditions

- The next task would cross above `pageReadyObserved`.
- The task would reintroduce TypeScript runtime or Bun-first canonical validation.
- The task would mix multiple implementation slices into one commit.
- No honest validation bundle can be chosen.
- The task would claim actual released-path execution where only scaffold hardening exists.
- The exact quoted on-disk `current.next_action` no longer names a concrete slice
  and the documented queue cannot be advanced honestly.
- One documented paused-state resume-search pass found neither a focused failing artifact nor an exact unenforced PRD clause below `pageReadyObserved`, and the documented primary plus secondary queues are exhausted.

## Output

Return exactly:

- `phase / milestone / anchor / invariant / next action`
- chosen task
- why it is the smallest safe task
- validation commands
- RAG update decision
- commit hash
- whether the result is scaffold hardening or actual released-path execution
