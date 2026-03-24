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

## Anchor Contract Table

The active phase must define which surface families are expected below the
current anchor before true stop is admissible.

### `Phase R3 — Fresh Python Bootstrap`

### Anchor `pythonRuntimeBootstrapCreated`

Required surface families:

- released graph wiring and call-sites
- released input-resolution and CLI entry surfaces
- released MCP/OpenClaw adapter and response validation surfaces
- released evidence, reporting, and comparability surfaces
- typed mission/error/memory helpers needed for low-attention continuation
- modeled helper entrypoints that still stop at `pageReadyObserved`
- docs-sufficiency surfaces required so a lower-capacity agent can name the
  next one-commit slice from canonical sources alone

Completion expectation:

- the active queue, heuristic catalog, and continuation-seeding pass must all
  be interpreted as mechanisms for covering these families
- true stop is invalid while one family still lacks a deterministic search rule
  or deterministic next-slice naming path
- true stop is also invalid while a family lacks an explicit coverage status:
  `covered`, `excluded`, or `pending`

### Coverage Ledger Rule

The active anchor must maintain one explicit coverage ledger in canonical
sources.

Canonical machine-readable ledger path for the active phase:

- `docs/llm/low-attention-coverage-ledger.json`

Required ledger fields per family:

- `family`
- `status`
- `evidence_or_reason`
- `next_slice_hint`

Allowed statuses:

- `covered`
- `excluded`
- `pending`

Ledger rule:

- `covered` means one queue, heuristic, or seeded slice closed honestly with
  attributable evidence
- `excluded` means one exact PRD clause rules out further work for that family
- `pending` means the family still requires one deterministic next slice
- lower-capacity agents must prefer the earliest `pending` family over generic
  exhaustion wording
- when the machine-readable ledger and readable summary disagree, the
  machine-readable ledger is the source of truth for next-slice selection

## Milestone Completion Table

The active milestone is complete only when its continuation contract is
exhausted, not merely when the current queue ends.

### Milestone `Low-attention autonomous continuation remains unambiguous under the Python-first PRD contract`

Done when all are true:

- every required anchor surface family below `pageReadyObserved` has either:
  - one completed queue slice history, or
  - one explicit PRD-backed exclusion from further work
- every required anchor surface family also has an explicit coverage-ledger
  status of `covered` or `excluded`
- the queue, bounded resume-search, heuristic catalog, and continuation-seeding
  pass are all exhausted honestly for the current cycle
- canonical sources are sufficient for a lower-capacity agent to name the next
  slice or conclude exhaustion without operator interpretation
- `work-rag.json` and `current-state.md` agree on whether continuation still
  exists

Not done when any are true:

- a surface family is still described only implicitly
- a surface family is still marked `pending`
- the next slice can be inferred from phase / milestone / anchor context but is
  not yet documented
- stop depends on remembering prior operator intent rather than on canonical
  sources alone

## Low-Attention Loop

Autonomous work is phase-driven and queue-backed rather than open-ended search.

Loop:

1. read canonical inputs
2. restate phase, milestone, anchor, invariant, and next action
3. confirm the documented queue position
4. execute one task only
5. run honest focused validation (`pytest`, `mypy`, `ruff check`)
6. update `docs/product/work-rag.json`
7. promote to `docs/product/rag.json` only when a lesson is truly durable
8. create one commit
9. immediately select the next documented in-bounds action and continue the
   loop when one still exists
10. if no documented action remains but the phase and milestone are still
    active, run continuation seeding instead of accepting stop by default

Continuous-loop rule:

- one task per commit remains mandatory
- a successful task close should normally hand off directly to the next
  documented queue item, failing artifact, clause gap, or heuristic candidate
- documented queue exhaustion is not by itself a valid reason to stop while the
  current phase and milestone still authorize low-attention continuation
- do not pause merely because one bounded task finished cleanly
- pause only when scope is blocked, validation is blocked, or the full
  exhaustion protocol is honestly complete

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
6. one continuation-seeding slice for the active phase / milestone / anchor

## Heuristic Family Table

When the queue is clean for the current cycle, heuristic expansion must still
follow the active anchor's family map.

Family order for `pythonRuntimeBootstrapCreated`:

1. same-file failing validation artifact
2. same module's exact PRD-backed unenforced clause
3. same directory support module imported by the just-closed slice
4. same helper family variant:
   `*_entrypoint.py`, `*_cli_entrypoint.py`, `*_argv.py`, `*_argv_env.py`
5. same validation family:
   colocated unit or contract tests already exercising the same path
6. same-anchor config/settings/reporting/comparability helper
7. docs-sufficiency source that prevents the next lower-capacity slice from
   being named deterministically

Heuristic-family rule:

- the agent must climb this family ladder in order
- each family must point to one exact PRD clause and one focused validation
  command before implementation begins
- if a family yields one valid slice, the cycle closes that slice before
  searching further
- if no family yields a slice but the coverage ledger still contains one
  `pending` family, continuation seeding must target that `pending` family
  rather than accepting stop

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
- doc-only rewrites whose only purpose is to restate, align, or justify
  `FINAL_STOP`

Continuation-seeding tasks are valid only when all are true:

- the documented queue and bounded heuristic surfaces are exhausted for the
  current cycle
- the current phase, milestone, and anchor still authorize continuation below
  `pageReadyObserved`
- the task produces exactly one new deterministic next slice for a
  lower-capacity agent
- the task updates canonical sources so the next cycle can name one exact
  follow-on implementation or validation slice without guesswork

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

## Post-Commit Continuation Rule

After each honest one-commit task close, the agent must try to keep momentum in
the same session.

Post-commit order:

1. rewrite `work-rag.json` `current.next_action` to the next exact documented
   queue item, heuristic candidate, or continuation-seeded slice
2. restate the new `phase / milestone / anchor / invariant / next_action`
3. continue into the next bounded slice without waiting for a new user prompt
4. stop only if the next bounded slice would violate scope, lacks an honest
   validation path, or the full exhaustion protocol is complete

Post-commit guard:

- "task closed successfully" is not by itself a valid stopping reason
- if the next exact slice can already be named from documented queue order,
  resume-search order, heuristic catalog, or continuation-seeding output,
  continuation should proceed
- doc-only stop-state alignment is not a valid follow-on slice unless the user
  explicitly asked for stop-state cleanup

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
4. one continuation-seeding pass
5. one stop-state consistency gate

If no valid in-bounds PRD clause gap remains, final stop stands.

Final-stop alignment guard:

- aligning docs to an already-claimed `FINAL_STOP` is not itself evidence that
  the exhaustion protocol was correct
- a lower-capacity agent must prefer one implementation-bearing or
  validation-bearing documented slice over a docs-only stop-confirmation edit
- if a released-scope support surface is still omitted from the documented
  queue but is directly backed by an exact PRD clause and focused validation can
  be named honestly, the agent should document and execute that slice before
  accepting `FINAL_STOP`
- if the current phase and milestone still define continuation work below
  `pageReadyObserved`, the agent must prefer one continuation-seeding slice
  over immediate final stop

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
- one heuristic pass may inspect every documented heuristic candidate in order,
  but may propose or start exactly one new queue item total
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
- the candidate already exists in the repository and remains on the active
  Python-first path
- the candidate is directly adjacent to an exhausted queue item by import,
  validation target, or released-scope runtime wiring
- the candidate remains below `pageReadyObserved`
- one exact governing PRD clause can be named before implementation begins
- one focused validation command can be named before implementation begins
- a focused validation target already exists or can be named deterministically
- the slice remains one-task-per-commit safe

### Heuristic Pass Implementation Guide

Interpret "one heuristic pass" as one bounded sweep across the documented
candidate ladder, not as permission to inspect only one arbitrary candidate.

Canonical heuristic sweep order:

1. same-directory support modules imported by the exhausted released-scope file
   group
2. released-scope config or settings helpers that feed the same execution path
3. released-scope assembly or injection tests that already exercise the same
   path
4. reporting, comparability, or evidence helpers that directly consume the same
   released artifacts

Per-candidate sweep steps:

1. confirm the file is in the documented heuristic catalog
2. run the candidate's first focused validation command
3. if that validation fails, the failing artifact becomes the next one-commit
   task
4. if validation passes, run the narrowest focused mypy target when typing is
   relevant
5. if typing passes, run the narrowest focused ruff check
6. if focused validation is clean, read one governing PRD and try to name one
   exact unenforced clause tied to that candidate
7. if an exact gap is found, emit one new queue item and stop the sweep
8. if no exact gap is found honestly, continue to the next documented heuristic
   candidate

Heuristic output contract:

- a successful heuristic pass must produce one new queue item with:
  - one primary file group
  - one first PRD
  - one first focused validation command
  - one sentence explaining why the candidate is still below
    `pageReadyObserved`
- a failed heuristic pass must explicitly state that every documented heuristic
  candidate was inspected in order and yielded neither a focused failing
  artifact nor an exact PRD-backed clause gap

Heuristic-stop guard:

- final stop is invalid while any documented heuristic candidate remains
  uninspected for the active exhaustion cycle
- "single heuristic pass exhausted" means the documented candidate ladder was
  traversed completely, not that only one candidate was sampled

## Continuation Seeding

When the documented queue, bounded resume-search pass, and heuristic catalog are
all exhausted for the active cycle, the agent must run exactly one
continuation-seeding pass before honoring `FINAL_STOP`.

Purpose:

- keep low-attention autonomous implementation moving by converting active
  phase / milestone / anchor context into one new deterministic one-commit
  slice

Continuation-seeding rule:

- this pass is mandatory while the current phase and milestone remain active
- the pass may seed at most one new slice per exhaustion cycle
- the seeded slice must remain below `pageReadyObserved`
- the seeded slice must be one-task-per-commit safe
- the seeded slice must either:
  - add one new queue item for an omitted in-bounds surface already present in
    the repo, or
  - add one docs-sufficiency improvement that makes the next implementation
    slice deterministically nameable from canonical sources

Canonical seeding inputs:

1. current `phase / milestone / anchor / invariant`
2. `docs/current-state.md`
3. `docs/product/work-rag.json`
4. `docs/product/rag.json`
5. the governing PRD for the most recently closed queue item or helper family

Seed candidate priority:

1. omitted same-family helper or validation surfaces already on disk
2. omitted same-anchor support modules already imported by active queue items
3. docs-sufficiency gaps that prevent a lower-capacity agent from naming the
   next one-commit slice even though the phase remains active

## Seeding Rule Table

Continuation seeding must convert phase / milestone / anchor context into one
deterministic next slice rather than a vague search instruction.

Allowed seeded slice kinds:

- omitted queue item for an existing source file
- omitted queue item for an existing focused test surface
- docs-sufficiency slice that introduces one explicit search rule, family map,
  or completion rule needed by the next lower-capacity implementation slice

Required seeded outputs:

- one target path or file group
- one governing PRD
- one first validation command
- one `done_when`
- one `next_if_clean`
- one `next_if_fail`

Forbidden seeded outputs:

- generic advice to "look for the next gap"
- multiple competing next actions
- broad roadmap rewrites with no immediate one-commit consumer
- stop-state cleanup presented as continuation

Seeding output contract:

- one seeded slice must name:
  - `file_group`
  - `first_prd`
  - `first_validation`
  - `done_when`
  - `next_if_clean`
  - `next_if_fail`
- if the seeded slice is docs-sufficiency only, it must also name the exact
  implementation or validation slice it is making possible next
- after seeding, `docs/current-state.md`, `docs/product/work-rag.json`, and any
  queue-bearing source must be updated in the same task close
- after seeding, the active coverage ledger must also be updated in the same
  task close

Seeding-stop guard:

- `FINAL_STOP` is invalid if continuation seeding has not yet run for the
  current exhaustion cycle
- `FINAL_STOP` is invalid if continuation seeding can still name one exact
  one-commit slice without guesswork
- `FINAL_STOP` is invalid if any required family remains `pending` in the
  active coverage ledger

## Stop-State Consistency Gate

Before honoring `FINAL_STOP`, the agent must verify that the repository's
current-tense continuation surfaces still agree.

Required consistency checks:

1. `docs/current-state.md`
2. `docs/product/work-rag.json`
3. `docs/product/prd-low-attention-implementation-queue.md`
4. `docs/llm/repo-autonomous-loop-adapter.yaml`

Consistency rule:

- `FINAL_STOP` is invalid if any of the sources above still names a concrete
  next slice, stale queue boundary, or omitted continuation surface below
  `pageReadyObserved`
- a lower-capacity agent must prefer a reopened documented queue item over a
  previously recorded stop string
- if the queue PRD and repo adapter disagree about the tail of the queue, the
  stop is stale until the discrepancy is resolved
- if `current-state.md` still describes continuation-bearing modeled or
  released-scope helper surfaces, the stop is stale until those surfaces are
  either documented as queue items or explicitly ruled out by an exact PRD
  clause

### Adjacent-Surface Completion Check

As part of the stop-state consistency gate, the agent must run one bounded
adjacent-surface completion check before accepting `FINAL_STOP`.

Purpose:

- catch small omitted surfaces that belong to the same deterministic helper or
  entrypoint family as the most recently closed queue item

Allowed adjacent families:

1. `*_entrypoint.py`
2. `*_cli_entrypoint.py`
3. `*_argv.py`
4. `*_argv_env.py`
5. colocated focused tests that already exercise one of those helpers

Adjacent-surface rules:

- the candidate must already exist on disk
- the candidate must share the same module family or validation family as the
  last documented queue item or heuristic candidate
- one governing PRD clause must be namable before implementation begins
- one focused validation command must already exist or be derivable
  mechanically from an existing colocated test file
- this check may reopen at most one new queue item per exhaustion cycle
- if one valid adjacent candidate exists, the agent must document it as the
  next queue item instead of accepting `FINAL_STOP`
- if no valid adjacent candidate exists honestly, the stop-state consistency
  gate may complete

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
- one continuation-seeding pass for the exhaustion cycle is exhausted
- one stop-state consistency gate is exhausted
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
