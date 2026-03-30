---
name: ez-ax-autoloop
description: Core loop logic for the ez-ax low-attention autonomous implementation. Invoked automatically when the operator runs 'ez-ax-autoloop' CLI script. Executes continuous one-commit slices until FINAL_STOP is honestly reached.
---

# EZ-AX AutoLoop Logic

Core implementation logic for continuous autonomous continuation. This skill
defines the execution rules that govern each cycle when the operator has
invoked the `ez-ax-autoloop` CLI script.

## How This Skill Is Used

This skill is **NOT** manually invoked by the operator. Instead:

1. Operator runs: `ez-ax-autoloop` CLI script
2. The Python script (`autoloop_runner.py`) generates a prompt plan
3. The script invokes: `claude --print "prompt"` with `--allowedTools Edit,Write,Bash,Read,Glob,Grep`
4. Claude (this instance) reads this skill's rules to guide execution
5. Each cycle repeats until FINAL_STOP is reached

## Mission

Execute bounded autonomous continuation:

- never cross above `runCompletion`
- never violate OpenClaw-only browser boundary
- never do speculative expansion
- enforce one-task-per-commit
- stop honestly with `FINAL_STOP` only after continuation seeding is exhausted

## Read First (Every Cycle)

1. `AGENTS.md`
2. `docs/prd.md`
3. `docs/execution-model.md`
4. `docs/current-state.md`
5. `docs/product/work-rag.json`
6. `docs/product/rag.json`
7. `docs/llm/repo-autonomous-loop-adapter.yaml`
8. `docs/llm/low-attention-coverage-ledger.json`

## Loop Mode

Default mode is continuous guarded looping:

1. Quote the exact on-disk `docs/product/work-rag.json` `current.next_action`
   verbatim, then restate `phase / milestone / anchor / invariant / next_action`
2. Verify task is in-bounds (below `runCompletion`, no browser-internal tools)
3. If out-of-bounds: stop immediately and report reason
4. Pick exactly one task candidate
5. Run focused validation floor: `python -m pytest tests/unit/ -q`,
   `python -m mypy src/ez_ax/`, `python -m ruff check src/ez_ax/`
6. If failing artifact exists, fix one smallest safe slice in the selected file group
7. If focused validation is clean, scan one exact PRD clause gap
8. If exact gap exists, implement one smallest safe one-commit fix
9. Update `docs/product/work-rag.json` with exactly one meaningful history entry
10. Promote to `docs/product/rag.json` only if lesson is durable
11. Commit exactly once for the task
12. Immediately rewrite `next_action` to the next exact documented slice and
    re-enter the loop in the same session

Continuous-loop bias:

- One-task-per-commit does not mean one-task-per-session
- Do not stop just because one bounded task closed cleanly
- `FINAL_STOP` is a last-resort exhaustion result, not the default closeout
- Doc-only edits whose only purpose is to align or restate `FINAL_STOP` are not
  valid continuation slices unless the operator explicitly requested stop-state
  cleanup
- If the exact quoted on-disk `next_action` names a concrete slice, do not
  output `FINAL_STOP`
- If the quoted `next_action` says `FINAL_STOP`, first run the stop-state
  consistency gate across `docs/current-state.md`, `docs/product/work-rag.json`,
  `docs/product/prd-low-attention-implementation-queue.md`, and
  `docs/llm/repo-autonomous-loop-adapter.yaml`
- Before honoring `FINAL_STOP`, run one continuation-seeding pass for the
  active phase / milestone / anchor

## Heuristic Scan — When No Uncovered Clause Found

When the active family is a `heuristic gap scan` and you read `docs/prd.md`
but find no released-scope clause below `runCompletion` that lacks a
dedicated unit test, do **not** declare `FINAL_STOP` yet. Instead work
through this **Scope Extension Ladder** in order, stopping at the first
level that produces a concrete implementable task:

### Level 1 — Coverage Depth

Scan `tests/unit/` for released-scope test files that cover a module but
omit a documented edge case from `docs/prd.md` (e.g. evidence-priority
fallback, boundary rejection). If found, add the missing test, mark the
heuristic scan family covered, update `work-rag.json`, commit, continue.

### Level 2 — Untested Modeled Stage Boundary

Read the "Modeled-only stages" section of `docs/prd.md`. Take the **first**
modeled-only stage name. Add exactly **two** pending families to
`docs/llm/low-attention-coverage-ledger.json`:

1. `{stage} boundary rejection test` — verify the graph stops before entering
   that stage
2. `{stage} evidence absence test` — verify missing evidence for that stage
   is handled correctly

Update `docs/llm/low-attention-execution-contract.json` `active_phase` /
`active_milestone` / `active_anchor` to reflect the new stage.
Mark the heuristic scan family covered, set `work-rag.json`
`current.next_action` to the first new family, commit.

### Level 3 — Refactor Safety Net

Scan `src/ez_ax/` for a module that has no corresponding `test_` file in
`tests/unit/` (excluding `__init__.py`). Add a minimal smoke test (import +
instantiation). Mark the heuristic scan family covered, update
`work-rag.json`, commit.

### Level 4 — FINAL_STOP

Only declare `FINAL_STOP` if Levels 1–3 all produce nothing. Include
explicit evidence for each level: what you looked at, and why it produced
nothing.

## Exhaustion and Stop Protocol

When queue appears exhausted, enforce this exact order:

1. One bounded resume-search pass
2. One queue-extension heuristic pass (max one new task from the documented catalog)
3. One final exact gap re-evaluation pass
4. One continuation-seeding pass
5. Scope Extension Ladder (Levels 1–3 above) if active family is heuristic scan
6. One stop-state consistency gate

Declare `FINAL_STOP` only when all are true:

- Queue exhausted
- Resume-search exhausted
- Queue-extension heuristic pass exhausted
- Continuation-seeding pass exhausted
- Scope Extension Ladder exhausted (all 3 levels produced nothing)
- Stop-state consistency gate exhausted
- No exact PRD-backed in-bounds gap remains

## Failure Taxonomy Guard

Invalidate the active task and stop if any appears:

- Boundary violation
- Release ceiling breach
- Evidence hierarchy violation
- Speculative task creation
- Over-implementation
- Infinite loop without exact PRD-backed gap

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
