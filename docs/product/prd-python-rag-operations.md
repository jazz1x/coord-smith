# PRD — Python RAG Operations

## Purpose

This PRD defines how `work-rag.json` and `rag.json` operate during the
Python-first runtime.

It exists so an autonomous agent can determine:

- what current work memory must contain
- what durable lesson memory must contain
- when each file is updated
- when compression happens
- when a lesson is promoted
- how graph nodes and runtime tasks close with durable memory

This PRD should be read beneath:

1. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
2. [`prd-runtime-missions.md`](./prd-runtime-missions.md)
3. [`prd-langgraph-state-model.md`](./prd-langgraph-state-model.md)
4. [`prd-python-validation-contract.md`](./prd-python-validation-contract.md)

Precedence rule:

- if a memory rule in this PRD conflicts with the runtime PRD's autonomous-work
  contract, the runtime PRD wins
- if a memory rule in this PRD conflicts with mission-level RAG duties, the
  mission map wins

## Canonical Memory Files

Current-tense work memory:

- `docs/product/work-rag.json`

Durable lesson memory:

- `docs/product/rag.json`

Canonical-memory rule:

- no hidden runtime memory should become necessary for task continuation

Repo-adapter discoverability rule:

- if a repo uses local adapter inputs for the autonomous loop, the adapter path
  should be discoverable from the normal continuation surface rather than hidden
  in side documentation only

## `work-rag.json` Role

`work-rag.json` exists to preserve:

- current goal
- current phase
- current milestone
- current anchor
- invariant
- next action
- approved scope ceiling
- recent checkpoint history needed for continuation

Work-RAG rule:

- `work-rag.json` is the canonical current-tense continuation surface

## `rag.json` Role

`rag.json` exists to preserve:

- repeated mistakes
- reusable heuristics
- flaky patterns
- false assumptions
- evidence-conflict lessons
- boundary-confusion lessons

Lesson-RAG rule:

- `rag.json` is for reuse across tasks, not for duplicating current step logs

Lesson-priority rule:

- lessons for the active Python-first implementation path should be easier to
  identify and read first than historical reset or cutover lessons
- tags should make it obvious whether a lesson is primarily for active
  implementation work or historical context

## Update Triggers

Update `work-rag.json` when:

- goal changes
- phase changes
- milestone changes
- anchor changes
- invariant changes
- next action changes
- meaningful evidence changes the continuation path

Update `rag.json` when:

- a lesson is durable
- a mistake is likely to repeat
- a failure pattern would help future judgment

Update-trigger rule:

- durable memory updates should happen during the same task closure that created
  the new knowledge

## Compression Policy

Compress `work-rag.json`:

- at every autonomous task close when a new checkpoint would otherwise extend
  low-value same-scope history
- at milestone completion
- at phase completion

Compression must:

- preserve facts needed for continuation
- discard low-value step noise
- add a checkpoint, milestone summary, or phase summary when appropriate

Active-history budget:

- prefer at most five raw checkpoints per active phase-milestone pair before
  compaction
- after compaction, prefer at most two raw checkpoints for the active
  phase-milestone pair plus the rolled-up milestone summary
- keep an older raw checkpoint only when it is uniquely required for safe
  continuation or attributable evidence

Compression rule:

- compression must reduce noise without deleting the active navigation surface

## Lesson Promotion Policy

Promote a lesson into `rag.json` when:

- the issue repeated
- the issue changed decision quality
- the issue exposed a boundary or guardrail weakness
- the issue would likely recur in later sessions

Do not promote when:

- the fact is only short-lived work state
- the lesson lacks attributable evidence

Promotion rule:

- a lesson should help a later agent judge better, not merely remember more

Tagging rule:

- every promoted lesson should include at least one context tag that signals its
  primary reuse surface
- prefer `active-implementation` for lessons that should influence the current
  coding loop
- prefer `historical-cutover` for lessons that mostly explain past migration or
  reset pitfalls
- a lesson may carry both when the historical mistake still directly protects
  the active implementation path

## Evidence Requirements

RAG updates should cite:

- active PRDs
- changed files
- validation outputs
- durable artifact references

Evidence-requirement rule:

- a memory claim without attributable evidence is incomplete

## Graph Integration

The runtime should route memory operations through:

- `work_rag_update`
- `work_rag_compression`
- `lesson_promotion`

Graph-integration rule:

- memory updates are explicit runtime duties, not optional narration

## Release-Ceiling Lessons

When a run claims the release ceiling was reached, durable memory must capture
the artifact-resolution behavior that justified the claim:

- record a checkpoint or lesson when `artifacts/action-log/release-ceiling-stop.jsonl`
  cannot be resolved or lacks typed `event`, `mission_name`, or `ts` entries
- tag the lesson `active-implementation` so future agents know the worry impacts
  the current enclosed ceiling (`runCompletion`)
- cross-reference the release-ceiling PRDs (`docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`,
  `docs/product/prd-python-validation-contract.md`)
  inside the lesson so it is easy to replay the typed reasoning
- when logging a release-ceiling failure, include the artifact path
  (`artifacts/action-log/release-ceiling-stop.jsonl`), the expected typed fields
  (`event`, `mission_name`, `ts`), and the relevant PRD references
  (`docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`,
  `docs/product/prd-python-validation-contract.md`) so the
  failure remains replayable without inferring the intent of the stop
- keep release-ceiling lessons small; focus on the missing artifact or failed
  typed field rather than re-describing coordination steps

Release-ceiling lesson rule:

- durable memory should keep track of visible release-ceiling failures so they
  cannot be swept under “general release lessons”; each such lesson should include
  the evidence ref and artifact path that failed

## Task Closure Rule

An autonomous task is complete only when:

1. the task result exists
2. `work-rag.json` is updated if required
3. same-scope checkpoint history is compacted if it crossed the active-history
   budget
4. `rag.json` is updated if warranted
5. applicable validation is recorded
6. the task is committed

Task-closure rule:

- if one of these steps cannot be completed honestly, the task is not fully
  closed

## Low-Attention Agent Guidance

To keep lower-capacity agents on the released path:

- always derive task selection from the benchmark PRD plus `work-rag.json`
  current state first
- consult `rag.json` for reusable guardrails and repeated mistakes before
  expanding scope
- read only the sub-PRDs required for the active task domain instead of
  reloading the full PRD set every time

Low-attention rule:

- minimizing non-canonical context is part of honest autonomous continuation,
  not an optimization preference

Low-attention current-state rule:

- `work-rag.json` current block should stay short enough that an agent can read
  it once and restate the phase, milestone, anchor, invariant, and next action
  without consulting older history first
- if the current block starts reading like a backlog or multi-task plan, it must
  be rewritten before more autonomous work continues

## Paused `next_action` Rule

When the repository is in a clean paused state, `work-rag.json` should still
preserve one deterministic restart action instead of only telling a future agent
to wait for human input.

Required paused-state `next_action` shape:

- name the bounded resume-search order
- prefer one focused validation artifact first
- then prefer one exact PRD clause plus one exact code location
- include the minimum honest validation command for the likely follow-on slice
- stop only if neither can be found honestly below the released ceiling

Paused-state rule:

- generic wording such as "stop and request the next gap" is incomplete unless
  it also states what autonomous search must be attempted before escalation
- a paused `next_action` must remain short enough for a lower-capacity agent to
  execute it as one discovery step without reading historical checkpoint prose
- if a paused state already knows the exact evidence or approval needed, that
  requirement should be named directly in `next_action`
- if a paused state already knows the exact validation command to rerun first,
  that command should be named directly in `next_action` rather than left
  implicit

Queued-paused-state rule:

- when paused-state search uses a documented file-group queue, `next_action`
  must point to the current queue item rather than collapse back to a generic
  stop message after one file group is exhausted
- if one queued file group yields no exact gap, `next_action` should be
  rewritten to the next queued file group in the same task close
- stop is valid only when the documented queue is exhausted or when the PRD
  explicitly forbids continuing to the next queued file group

Secondary-queue paused-state rule:

- if a documented secondary queue exists, `next_action` must advance into that
  queue before falling back to a generic stop message
- a paused-state stop is complete only when the active documented queue surface
  has been exhausted honestly and no secondary queue item remains

Final paused-stop rule:

- when both the documented primary and secondary queues are exhausted,
  `next_action` should record an explicit final low-attention stop message rather
  than imply that another autonomous queue will be discovered automatically
- reopening autonomous search after that point requires either:
  - one new explicit in-bounds contract gap, or
  - one explicit PRD update that extends the documented search boundary

## Docs-Only Reset Rule

Even if all code assets are removed:

- `work-rag.json`
- `rag.json`
- the active PRD set

must remain enough for a later agent to resume.

Docs-only-reset rule:

- RAG continuity is part of reset completeness, not a convenience

## Completeness

This RAG operations PRD is complete only when:

- future agents can continue from PRD and RAG alone
- current-tense and durable memory roles are distinct
- update, compression, and promotion triggers are explicit
- task closure includes memory discipline by rule rather than habit

## Immediate Next Action

The next action after this PRD is:

- assess whether the active PRD set is now sufficient for a docs-only reset and
  zero-code bootstrap

Reason:

- once memory operations are explicit, the Python-first PRD set should be
  complete enough to judge implementation readiness honestly
