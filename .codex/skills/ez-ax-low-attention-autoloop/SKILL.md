---
name: ez-ax-low-attention-autoloop
description: Run the ez-ax low-attention autonomous implementation loop end-to-end using repo adapters and wrapper skills until one exact in-bounds PRD gap is closed per commit or FINAL_STOP is reached with explicit grounds.
---

# EZ-AX Low-Attention AutoLoop

Use this as the single entry skill when a lower-capacity model should continue
implementation safely without re-reading long operator prompts every cycle.

## Mission

Execute bounded autonomous continuation under the active PRD contract:

- never cross above `pageReadyObserved`
- never violate OpenClaw-only browser boundary
- never do speculative expansion
- enforce one-task-per-commit
- stop honestly with `FINAL_STOP` when gap-free

## Read First (Every Cycle)

1. `AGENTS.md`
2. `docs/prd.md`
3. `docs/execution-model.md`
4. `docs/current-state.md`
5. `docs/product/work-rag.json`
6. `docs/product/rag.json`
7. `docs/llm/repo-autonomous-loop-adapter.yaml`

## Required Wrapper Chain

Use these wrappers in order. They are execution aids; PRD remains the authority.

1. `ez-ax-loop-released-scope-guard-wrapper`
2. `ez-ax-loop-task-slicer-wrapper`
3. `ez-ax-loop-validation-picker-wrapper`
4. implementation step (single smallest safe slice)
5. `ez-ax-loop-rag-compaction-wrapper`

## Loop Mode

Default mode is continuous guarded looping:

1. quote the exact on-disk `docs/product/work-rag.json` `current.next_action`
   verbatim, then restate `phase / milestone / anchor / invariant / next_action`
2. run scope guard
3. if out-of-bounds: stop immediately and report reason
4. pick exactly one task candidate
5. run focused validation floor (`pytest`, `mypy`, `ruff check`)
6. if failing artifact exists, fix one smallest safe slice in the selected file group
7. if focused validation is clean, scan one exact PRD clause gap
8. if exact gap exists, implement one smallest safe one-commit fix
9. update `docs/product/work-rag.json` with exactly one meaningful history entry
10. promote to `docs/product/rag.json` only if lesson is durable
11. commit exactly once for the task
12. immediately rewrite `next_action` to the next exact documented slice and
    re-enter the loop in the same session whenever one documented in-bounds
    next action remains

Continuous-loop bias:

- one-task-per-commit does not mean one-task-per-session
- after each successful commit, prefer continuing into the next documented
  queue item, resume-search file group, or heuristic candidate
- do not stop just because one bounded task closed cleanly
- `FINAL_STOP` is a last-resort exhaustion result, not the default closeout
- doc-only edits whose only purpose is to align or restate `FINAL_STOP` are not
  valid continuation slices unless the user explicitly requested stop-state
  cleanup
- if the exact quoted on-disk `next_action` names a concrete slice, do not
  output `FINAL_STOP`
- if the quoted `next_action` says `FINAL_STOP`, first run the stop-state
  consistency gate across `docs/current-state.md`,
  `docs/product/work-rag.json`,
  `docs/product/prd-low-attention-implementation-queue.md`, and
  `docs/llm/repo-autonomous-loop-adapter.yaml`
- as part of that gate, run one bounded adjacent-surface completion check for
  same-family helper surfaces such as `*_entrypoint.py`,
  `*_cli_entrypoint.py`, `*_argv.py`, and `*_argv_env.py`
- declare `FINAL_STOP` directly only after the documented exhaustion protocol
  and the stop-state consistency gate both fail to reopen one exact slice; do
  not switch to `blocked` or ask for operator confirmation

## Exhaustion and Stop Protocol

When queue appears exhausted, enforce this exact order:

1. one bounded resume-search pass
2. one queue-extension heuristic pass (max one new task from the documented catalog)
3. one final exact gap re-evaluation pass
4. one stop-state consistency gate

Declare `FINAL_STOP` only when all are true:

- queue exhausted
- resume-search exhausted
- queue-extension heuristic pass exhausted
- stop-state consistency gate exhausted
- no exact PRD-backed in-bounds gap remains

## Failure Taxonomy Guard

Invalidate the active task and stop if any appears:

- boundary violation
- release ceiling breach
- evidence hierarchy violation
- speculative task creation
- over-implementation
- infinite loop without exact PRD-backed gap

## Output Contract (Every Cycle)

Always report in this compact shape:

- `phase`
- `milestone`
- `anchor`
- `invariant`
- `next_action`
- `selected_prd_clause` (or `none`)
- `single_task`
- `validation_evidence`
- `memory_updates`
- `commit_hash` (or `none`)
- `status`: `continue` | `FINAL_STOP` | `blocked`
- `stop_grounds` (required when `FINAL_STOP`)

## Starter Invocation Prompt

Use this short prompt in a new session:

`Use $ez-ax-low-attention-autoloop. First quote the exact on-disk \`docs/product/work-rag.json\` \`current.next_action\` verbatim. If it names a concrete slice, execute that slice and do not output FINAL_STOP. If it says FINAL_STOP, do not stop immediately: first run the documented stop-state consistency gate across \`docs/current-state.md\`, \`docs/product/work-rag.json\`, \`docs/product/prd-low-attention-implementation-queue.md\`, and \`docs/llm/repo-autonomous-loop-adapter.yaml\`, including one bounded adjacent-surface completion check for same-family helper surfaces. Then run autonomous continuation in continuous guarded looping mode across consecutive one-commit slices. Treat FINAL_STOP as valid only as a last resort after the documented queue, bounded resume-search, full heuristic-catalog sweep, final exact gap re-evaluation, and stop-state consistency gate are all exhausted and you still cannot honestly name one exact next one-commit slice below pageReadyObserved.`
