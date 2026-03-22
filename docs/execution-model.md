# ez-ax Execution Model

## Purpose

This document defines how low-attention autonomous implementation proceeds
safely below the released ceiling.

It is an operating model, not an architecture definition.

This operating model is mandatory for autonomous execution and must not be
weakened beneath the PRD invariants.

## Canonical Inputs

Before autonomous work begins, the agent reads:

- `AGENTS.md`
- `docs/prd.md`
- `docs/execution-model.md`
- `docs/current-state.md`
- `docs/product/work-rag.json`
- `docs/product/rag.json`

The agent reads additional domain PRDs only when the active queue item touches
that domain.

## Phase / Milestone / Anchor Preflight

Before any task execution, the agent must restate and verify:

- phase
- milestone
- anchor
- invariant
- next action

Preflight checks:

- the task is in `Phase R3 — Fresh Python Bootstrap`
- the task contributes to low-attention continuation stability, not feature
  expansion
- the task assumes `pythonRuntimeBootstrapCreated` or later
- the task preserves boundary, release ceiling, and evidence hierarchy

If any preflight check fails, task execution must stop.

## Low-Attention Loop

Autonomous work is queue-driven rather than open-ended search.

Loop:

1. read canonical inputs
2. restate phase, milestone, anchor, invariant, and next action
3. confirm the documented queue position
4. execute one task only
5. run honest focused validation (`pytest`, `mypy`, `ruff check`)
6. update `docs/product/work-rag.json`
7. promote to `docs/product/rag.json` only when a lesson is truly durable
8. create one commit

Continue only when a documented in-bounds next action remains.

## Queue-Driven Selection

The low-attention implementation queue is the approved task-selection surface.

Each queue item defines:

- `file_group`
- `tests`
- `first_prd`
- `first_validation`
- `done_when`
- `next_if_clean`
- `next_if_fail`

Queue rule:

- the agent must not invent new search surfaces when a documented queue item
  still exists
- the agent must not skip ahead unless the current queue item is honestly clean
  or honestly exhausted under its own `done_when`

Continue-priority ladder:

1. the current documented queue item
2. the current queue item's exact failing focused validation artifact
3. the current queue item's exact PRD-backed clause gap
4. the current queue item's `next_if_clean` successor
5. one canonical queue-extension heuristic pass for the current exhaustion
   cycle, only after documented exhaustion

## Task Generation Rules

A generated task is valid only when all are true:

- directly linked to one explicit PRD clause
- remains at or below `pageReadyObserved`
- can be validated deterministically (`pytest`, `mypy`, `ruff check`)
- is single-responsibility and one-commit safe

The following are forbidden:

- speculative tasks
- convenience or "nice-to-have" additions
- modeled-stage implementation
- refactors not required by an exact clause gap
- multi-task bundling

## Per-Item Execution Flow

For one queue item, the agent proceeds in this order:

1. run focused `pytest`
2. if `pytest` fails, fix exactly one smallest safe slice in the file group
3. run focused `mypy`
4. run focused `ruff check`
5. if validation is clean, scan the named PRD for one exact unenforced clause
6. if an exact gap exists, implement one smallest safe one-commit fix
7. if no exact gap exists honestly, move to `next_if_clean`

## Validation Protocol

A task is not complete unless:

- focused `pytest` was run honestly
- focused `mypy` was run honestly
- focused `ruff check` was run honestly
- the change stayed inside approved scope
- `docs/product/work-rag.json` was updated when meaningful work occurred
- one commit was created

Focused validation is preferred over broad cleanup.

Repo-wide cleanup is out of scope unless a queue item explicitly requires it.

## PRD-Clause Gap Checklist

Before and after each task, the agent must check:

1. release boundary check
2. boundary integrity check
3. evidence integrity check
4. contract coverage check
5. over-implementation check
6. validation completeness check
7. memory model check

Release boundary check:

- work must stay at or below `pageReadyObserved`

Boundary integrity check:

- `ez-ax` must not become browser-facing
- `OpenClaw` remains the only browser-facing actor

Evidence integrity check:

- evidence priority remains `dom > text > clock > action-log`
- `screenshot`/`vision` remain fallback only

Contract coverage check:

- any claimed gap must cite one explicit PRD clause

Over-implementation check:

- implementation must not exceed the exact clause requirement

Validation completeness check:

- completion means "proven PRD alignment", not only "works locally"

Memory model check:

- `work-rag.json` records current state
- `rag.json` stores durable lessons only

## Queue Exhaustion Protocol

When the queue is exhausted, follow this order:

1. one bounded resume-search pass
2. one queue-extension heuristic pass for this exhaustion cycle
3. one gap re-evaluation pass

If no valid in-bounds PRD clause gap remains, final stop stands.

### Stop-State Resume Search

When `docs/product/work-rag.json` records an explicit stop, the lower-capacity
agent may perform exactly one bounded in-bounds resume-search pass before
accepting final stop.

Resume-search rule:

- this pass is allowed only to find one concrete failing artifact or one exact
  unenforced clause below `pageReadyObserved`
- this pass must stay within explicitly named released-scope file groups
- if the pass finds one valid task, implement exactly one smallest safe
  one-commit slice and stop searching further
- if the pass finds no valid task, the stop stands honestly

Canonical bounded search order:

1. `src/ez_ax/graph/released_call_site.py`
2. `src/ez_ax/graph/released_run_root.py`
3. `src/ez_ax/graph/langgraph_released_execution.py`
4. `src/ez_ax/adapters/openclaw/client.py`
5. `src/ez_ax/adapters/openclaw/execution.py`
6. `src/ez_ax/adapters/openclaw/mcp_adapter.py`
7. `src/ez_ax/adapters/openclaw/mcp_stdio_client.py`

Per-file-group bounded search flow:

1. run focused `pytest` if a matching unit test exists
2. run focused `mypy`
3. run focused `ruff check`
4. only if focused validation is clean, scan the most specific PRD for one
   exact unenforced clause tied to that file group

Bounded-search constraint:

- this resume-search pass is not open-ended exploration
- the agent must not invent new file groups during the pass
- if all listed file groups are clean and no exact clause is found without
  guesswork, the result remains final stop

### Queue-Extension Heuristic

If the documented low-attention implementation queue is honestly exhausted, the
agent may perform exactly one canonical queue-extension heuristic pass for that
exhaustion cycle before accepting true final stop.

Queue-extension heuristic rule:

- this pass exists to keep lower-capacity implementation moving when a nearby
  released-scope support surface was omitted from the documented queue
- the pass may propose or start exactly one new queue item
- if no valid candidate exists without guesswork, final stop stands

Cycle-reset rule:

- if a heuristic pass yields a valid queue item and that queue item later
  closes honestly, a new exhaustion cycle begins
- each new honest exhaustion cycle reopens exactly one canonical queue-
  extension heuristic pass
- a cycle does not reset merely because validation was rerun; it resets only
  after meaningful work closes with validation, `work-rag` update, and commit

Allowed candidate families:

1. same-anchor supporting files
2. same released-scope validation files
3. same released-scope bootstrap or config files
4. same released-scope reporting or comparability files

Candidate validity requirements:

- the file already exists in the repository
- the file remains below `pageReadyObserved`
- a focused validation target already exists or can be named deterministically
- the governing PRD already contains one exact `must` or required clause for
  that surface
- the work can close in one task and one commit

Queue-extension output shape:

- `file_group`
- `first_prd`
- `first_validation`
- `done_when`
- `next_if_clean`
- `next_if_fail`

Queue-extension constraint:

- the agent must prefer the smallest exact candidate
- the agent must not generate multiple new queue items in one pass
- the agent must not use this pass to widen architecture, release scope, or
  modeled-stage behavior

## Final Stop Declaration

Declare final stop only when all are true:

- queue is exhausted
- one bounded resume-search pass is exhausted
- one queue-extension heuristic pass for the exhaustion cycle is exhausted
- no exact PRD-backed in-bounds clause gap remains

A final-stop report must explicitly state these grounds.

## Failure Taxonomy

Any one of the following invalidates the active task:

- boundary violation
- release ceiling breach
- evidence hierarchy violation
- speculative task creation
- over-implementation
- infinite continuation loop without an exact PRD-backed gap

## One-Task-Per-Commit Rule

Autonomous continuation must stay one-task-per-commit.

This means:

- one file group or one exact contract gap at a time
- no broad refactors
- no mixed-purpose commits
- no scope expansion by accumulation

## Task Closure

When meaningful work occurred, task closure must include:

- applicable validation evidence
- one `work-rag.json` update
- one new checkpoint or summary entry when warranted
- optional `rag.json` promotion only for durable lessons
- one commit

If validation or commit cannot be completed honestly, the task must not be
reported as complete.

## Operational Boundary

This document does not authorize:

- new product scope
- new released stages
- browser-facing behavior in `ez-ax`
- speculative implementation above `pageReadyObserved`

Those decisions remain in the PRD only.
