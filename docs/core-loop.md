# ez-ax Core Loop (Low-Attention Quick Reference)

This is the minimal operating reference for low-attention autonomous
implementation. For detailed rules on heuristic sweeps, continuation seeding,
and exhaustion protocols, see `docs/execution-model.md`.

## Preflight

Before starting, verify from `docs/current-state.md`:

- phase / milestone / anchor / invariant / next action
- the task stays below `pageReadyObserved`
- the task is one-commit safe

If the working tree is dirty (uncommitted changes present):

- inspect with `git status`
- if the changes match the closed task in `work-rag.json`, validate and commit
  them before proceeding to `current.next_action`
- if the changes are unrelated or unknown, stop and record the situation in
  `work-rag.json` before continuing

## Loop

1. Read `work-rag.json` → `current.next_action`
2. Run focused `pytest` on the named test file
3. If pytest fails → fix the smallest safe slice → commit → go to 1
4. Run focused `mypy` on the named source files
5. If mypy fails → fix the smallest safe slice → commit → go to 1
6. Run focused `ruff check` on the named source files
7. If ruff fails → fix → commit → go to 1
8. If all clean → scan the named PRD for one exact unenforced clause
9. If a gap exists → implement one smallest safe slice → commit → go to 1
10. If no gap → move to `next_if_clean` from the queue item

## After Each Commit

1. Update `work-rag.json`:
   - set `current.next_action` to the next item
   - add one checkpoint to `history` with what was done and evidence
   - if `history` has more than 3 entries for the active phase-milestone,
     compress oldest into one summary (keep latest 2 raw checkpoints)
2. If the fix revealed a reusable lesson (not a transient step), promote to `rag.json`
3. Continue without waiting for a new prompt
4. Stop only when validation is blocked or scope would be violated

## On Failure

If validation fails and cannot be fixed in one commit:

1. Record the failure in `work-rag.json` as a checkpoint with the error detail
2. Set `current.next_action` to describe the exact remaining fix
3. Do NOT skip to the next queue item — stay on the current failure until fixed

## Rules

- One task per commit — no mixed-purpose commits
- Stay at or below `pageReadyObserved`
- OpenClaw is the only browser-facing actor
- Typed evidence required for released-scope decisions
- `work-rag.json` = current state, `rag.json` = durable lessons only

## Validation

A task is complete only when:

- focused pytest ran honestly
- focused mypy ran honestly
- focused ruff check ran honestly
- `work-rag.json` was updated
- one commit was created

## When to Stop

Stop autonomous implementation when:

- the documented queue is exhausted AND
- the bounded resume-search surfaces are exhausted AND
- the mandatory continuation-seeding pass found no omitted same-family slice AND
- the stop-state consistency gate reopened nothing

Then set `current.next_action` to `FINAL_STOP — <reason>`.
