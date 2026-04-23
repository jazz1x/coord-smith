# PRD — Phase 1 Server-Time-Synchronized Benchmark

> Legacy reference notice:
> This document remains a supporting reference document and is not the primary
> agent entrypoint.
> Agents must begin with the layered docs instead:
> [`docs/prd.md`](../prd.md),
> [`docs/execution-model.md`](../execution-model.md),
> [`docs/current-state.md`](../current-state.md).

## Purpose

This PRD defines the product requirements and autonomous-work contract for the current Phase 1 benchmark.

It should be sufficient for an agent to determine:

- what the product is trying to achieve
- what the current approved scope is
- which phase and milestone a task belongs to
- which anchor is currently allowed
- what evidence is required to consider work complete
- when work must stop rather than continue

## North Star

Build a deterministic benchmark orchestrator in which:

- `OpenClaw` is the only browser-facing execution actor
- `ez-ax` owns orchestration, timing, checkpoints, failure classification, and run comparability
- one narrow authenticated browser flow is prepared before a release/open moment
- comparable typed evidence is produced about readiness, timing, dispatch, and outcome

North-star rule:

- this is the full direction of Phase 1
- it is broader than the currently approved implementation ceiling
- autonomous work must move toward this north star without crossing the current approved boundary

## Product Requirements

The product must:

- use an OpenClaw-controlled authenticated browser session
- enter the target page before the release/open event
- use event-based waits whenever a typed observation boundary exists
- keep success conditions explicit and machine-verifiable
- keep timing checkpoints and artifacts comparable across repeated runs
- keep failure taxonomy typed and diagnosable
- keep execution ownership with `OpenClaw`
- keep orchestration ownership with `ez-ax`

The product must not:

- treat Playwright, Chromium, CDP, or similar mechanisms as ez-ax product-level architecture
- widen the runtime boundary without explicit stage release
- claim released workflow support beyond the currently approved path
- rely on operator intuition instead of typed evidence for release decisions
- introduce anti-detection logic

## Current Approved Scope

The current approved autonomous-work scope is:

`attach -> prepareSession -> benchmark validation -> pageReadyObserved`

Approved-scope rule:

- autonomous implementation may harden behavior only within this scope
- anything above `pageReadyObserved` is frozen for workflow-level execution
- no task may imply release of a later workflow stage merely because the repository contains types, checkpoints, or scaffolding for it
- current approved scope is the highest approved implementation boundary for autonomous work, not a claim about what code already exists today
- even from a zero-base implementation start, autonomous work must build phase by phase and stop at the current approved anchor unless the PRD is explicitly updated

## Modeled Versus Released

This PRD contains both modeled behavior and released behavior.

Definitions:

- modeled behavior:
  future-facing workflow shape, scenario scaffolding, or planned execution stages that may exist in contracts or docs
- released behavior:
  behavior currently approved for real-path execution or autonomous hardening without additional release approval

Released today:

- attach and session readiness
- `prepareSession` validation
- target-page entry
- page-shell readiness validation through `pageReadyObserved`
- stopping at `pageReadyObserved` as a validation-ceiling stop

## Released Ceiling Stop-Confirmation Evidence (Required)

The released ceiling (`runCompletion`) must be judged deterministically from
typed evidence, not inferred from an incomplete workflow. (The ceiling was
expanded from `pageReadyObserved` to `runCompletion` on 2026-03-26 alongside
the promotion of all 12 missions to released; cross-ref `docs/prd.md`.)

Rule:

- any run that claims it reached the released ceiling MUST include explicit
  stop-confirmation evidence that the system intentionally stopped at the
  ceiling boundary

Required evidence refs:

- `evidence://action-log/release-ceiling-stop`

- if the release-ceiling artifact cannot be resolved, the validator must record a typed failure
  referencing `artifacts/action-log/release-ceiling-stop.jsonl`, the expected fields (`event`,
  `mission_name`, `ts`), and the release-ceiling PRDs (
  `docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`,
  `docs/product/prd-python-validation-contract.md`) before concluding the ceiling stop was observed

Required readiness evidence refs:

- the run MUST include the released-scope minimum evidence keys for
  `page_ready_observation` defined in
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
  under "`evidence_refs` Schema (Released Scope)"

Validation rule:

- if stop-confirmation evidence is missing, the run is not considered to have
  stopped correctly at the released ceiling, even if later workflow actions did
  not occur

Scope rule:

- evidence contracts above `pageReadyObserved` remain frozen; do not treat the
  presence of modeled evidence keys as proof that later workflow stages are
  released

Modeled but not released today:

- `syncToServerTime`
- armed-state entry
- trigger waiting
- click dispatch
- success-condition execution

Interpretation rule:

- if a modeled stage conflicts with the current approved scope, the current approved scope wins

## Scope Lock

Current released product scope is intentionally narrow:

- one authenticated benchmark flow
- one execution actor: `OpenClaw`
- one orchestration engine: `ez-ax`
- one current runtime ceiling: `pageReadyObserved`

Not yet released in the current phase:

- generalized multi-site workflow execution
- broad multi-mode runtime coverage
- automatic login recovery as part of the approved benchmark path
- workflow execution above `pageReadyObserved`

## Released Path Identity

The current released benchmark path must be identifiable even when broader modeled examples exist.

Released-path identity for the current approved scope:

- site:
  Interpark
- flow:
  one narrow released benchmark flow on that site
- session mode:
  operator-prepared authenticated session attachment
- execution boundary:
  `OpenClaw` executes, `ez-ax` orchestrates
- runtime ceiling:
  `pageReadyObserved`

Released-path identity rule:

- autonomous work must preserve the currently released path even when the exact site/flow/config values are maintained elsewhere in repository configuration
- modeled site examples or future mode examples must not replace or redefine the released path identity
- if a task needs a concrete site or flow example for discussion, it must label that example as either `released-path reference` or `modeled example`
- unless the PRD is explicitly updated, Interpark remains the only released site identity for autonomous work

## Modeled Site And Mode Examples

The repository may use concrete site examples to discuss modeled future variation.

These examples are useful for scenario naming and contract discussion, but they do **not** by themselves release broader workflow coverage.

Modeled examples:

- A-mode example — Interpark:
  `https://tickets.interpark.com/goods/26003199`
- B-mode example — Ticketlink:
  `https://www.ticketlink.co.kr/product/61662`

Mode labels in this PRD mean:

- A-mode:
  a modeled variation label used for one example path family
- B-mode:
  a modeled variation label used for another example path family

Mode-label rule:

- A-mode and B-mode are discussion labels, not current release claims
- they do not by themselves define new approved runtime modes
- they are placeholders for future scenario variation unless explicitly promoted into released path identity

Example rule:

- these examples may be used to describe modeled site or mode differences
- they must not be interpreted as proof that multi-site or multi-mode workflow execution is currently released
- the current approved scope remains one narrow released benchmark path below `pageReadyObserved`
- a modeled example may become part of released path identity only after the relevant milestone and anchor are explicitly released by typed evidence under this PRD

## Primary Use Case

An operator prepares an authenticated browser session controlled by OpenClaw.
The system attaches to that prepared session, enters the target page, validates page readiness, and stops at the pre-workflow boundary with typed evidence that the run is ready for later staged release work.

## Phase Map

Phase 1 work is organized into these phases.

### Phase A — Attach And Session Readiness

Goal:

- attach to the intended OpenClaw-managed session
- validate session viability
- validate startup conditions

Primary milestone:

- session is attached and stable enough for benchmark validation

Primary anchor:

- `prepareSession`

Status:

- released for autonomous work

### Phase B — Prewarm Boundary

Goal:

- enter the target page
- validate page-shell readiness
- prove the run is ready at the pre-workflow boundary

Primary milestone:

- benchmark validation reaches the approved ceiling and stops cleanly

Primary anchor:

- `pageReadyObserved`

Status:

- released for autonomous work

### Phase C — Sync Boundary

Goal:

- observe server time
- normalize timing data
- establish sync before trigger preparation

Primary milestone:

- server-time synchronization is typed, stable, and diagnosable

Primary anchor:

- `syncEstablished`

Status:

- modeled
- frozen for workflow release

### Phase D — Armed Boundary

Goal:

- observe target-button actionability
- enter an explicit armed pre-click state

Primary milestone:

- target-button readiness is typed and arming is stable

Primary anchors:

- `targetButtonActionableObserved`
- `armedStateEntered`

Status:

- modeled
- frozen for workflow release

### Phase E — Trigger And Dispatch Boundary

Goal:

- wait at the trigger boundary
- dispatch the click through OpenClaw

Primary milestone:

- trigger waiting and click dispatch are typed, stable, and diagnosable

Primary anchors:

- `targetTimeReached`
- `clickDispatched`
- `clickCompleted`

Status:

- modeled
- frozen for workflow release

### Phase F — Success Boundary

Goal:

- observe success through the configured success surface
- classify the run
- finalize comparable outputs

Primary milestone:

- success observation is machine-verifiable and run outputs remain comparable

Primary anchors:

- `successConditionObserved`
- `runCompleted`

Status:

- modeled
- frozen for workflow release

## Milestone Map

Each phase has a milestone that defines the highest-value unit of progress.

### Milestone 1 — Attach Healthy

Phase:

- Phase A

Anchor:

- `prepareSession`

Done when:

- attach is healthy
- session remains valid
- startup diagnostics are coherent

### Milestone 2 — Prewarm Boundary Hardened

Phase:

- Phase B

Anchor:

- `pageReadyObserved`

Done when:

- target page is entered
- page-shell readiness is typed
- benchmark validation stops cleanly at the approved ceiling
- boundary stop is reported as expected behavior, not as partial workflow execution

### Milestone 3 — Sync Validation Released

Phase:

- Phase C

Anchor:

- `syncEstablished`

Done when:

- sync observation is typed
- normalized timing data is valid
- sync failures remain explicit and diagnosable
- repeated-run stability exists at the sync boundary

Status:

- frozen

### Milestone 4 — Armed Boundary Released

Phase:

- Phase D

Anchor:

- `armedStateEntered`

Done when:

- target-button readiness is explicit
- arming remains stable
- failures remain typed
- repeated-run stability exists at the armed boundary

Status:

- frozen

### Milestone 5 — Trigger And Dispatch Released

Phase:

- Phase E

Anchor:

- `clickDispatched`

Done when:

- trigger waiting is stable
- click dispatch occurs through `OpenClaw`
- dispatch failures remain classified
- repeated-run stability exists at the dispatch boundary

Status:

- frozen

### Milestone 6 — Success Boundary Released

Phase:

- Phase F

Anchor:

- `successConditionObserved`

Done when:

- success observation is typed
- success and failure are machine-verifiable
- run outputs remain comparable across repeated runs

Status:

- frozen

## Anchor Map

Anchors define the exact boundary a task changes or validates.

Released anchors:

- `prepareSession`
- `pageReadyObserved`

Frozen anchors:

- `syncEstablished`
- `targetButtonActionableObserved`
- `armedStateEntered`
- `targetTimeReached`
- `clickDispatched`
- `clickCompleted`
- `successConditionObserved`
- `runCompleted`

Anchor types:

- phase anchor:
  any named anchor used to locate work within a phase
- release gate anchor:
  the single anchor that currently defines the highest approved boundary for autonomous implementation

Current release gate anchor:

- `pageReadyObserved`

Release-gate rule:

- a phase may mention multiple phase anchors
- that does not mean each phase anchor is independently released
- only the current release gate anchor and earlier released anchors may be used as autonomous implementation targets
- later phase anchors remain planning or release-evidence anchors until explicitly promoted

Anchor rule:

- every runtime-affecting task must name exactly one current target anchor
- no task may silently cross from one anchor to a later anchor
- any task above `pageReadyObserved` requires explicit release approval

## Autonomous Task Selection Rule

When multiple safe tasks are available, choose exactly one next task in this order:

1. repair contradictions that blur the current approved boundary
2. strengthen typed diagnostics or failure taxonomy below the current ceiling
3. strengthen tests for approved stages, prioritizing edge, error, and chaos coverage
4. improve operator-facing reporting for approved stages
5. simplify contracts or docs that overstate modeled behavior as released behavior

Tie-breaker:

- prefer the smallest change that increases typed evidence without changing the current approved boundary
- if two candidate tasks are equally small, choose the one that improves typed diagnostics before the one that improves wording alone
- if two candidate tasks are equally diagnostic-heavy, choose the one attached to the earlier released anchor
- if a tie still remains, choose the task with the narrowest blast radius

Allowed-task examples within the current approved scope:

- clarify docs that blur `modeled` versus `released`
- harden attach or `prepareSession` diagnostics
- improve typed page-ready diagnostics at the prewarm boundary
- strengthen approved-stage checkpoint reporting
- add or tighten tests for attach, prewarm, page-ready validation, and validation-ceiling stop behavior
- improve operator-facing reporting that still stops at `pageReadyObserved`

Disallowed-task examples while the current boundary remains frozen:

- implementing real-path sync execution as released workflow behavior
- implementing armed-state runtime entry as released workflow behavior
- implementing trigger wait or click dispatch as released workflow behavior
- implementing success-condition execution as released workflow behavior
- changing reports or docs in a way that implies later anchors are already released

## Low-Attention Autonomous Contract

Lower-capacity autonomous agents must stay aligned to the released ceiling by
using the smallest canonical context first.

Required reading order:

1. `AGENTS.md`
2. this PRD
3. `docs/product/work-rag.json`
4. `docs/product/rag.json`

Additional PRD reading rule:

- read runtime, mission, state-model, validation, layout, and OpenClaw PRDs only
  when the current task touches those domains
- do not reload the full PRD set on every task by default

Single-task rule:

- each autonomous turn must choose exactly one in-bounds task
- that task must be small enough to validate and commit honestly before any
  follow-on task is considered
- if a candidate task would naturally split into two commits, it is not yet the
  right task slice for a lower-capacity agent

Task-close memory rule:

- update `docs/product/work-rag.json` current state at task close
- add exactly one new same-task checkpoint or summary entry when meaningful work
  occurred
- compact same-scope raw checkpoint history once it exceeds five entries
- after compaction, prefer keeping at most two raw checkpoints for the active
  phase-milestone pair plus the rolled-up summary
- promote only reusable lessons into `docs/product/rag.json`

Low-attention contract rule:

- reducing non-canonical context and step-log noise is part of released-scope
  safety, not an optional optimization

## Low-Attention Readiness Gate

Before starting any autonomous task, a lower-capacity agent must confirm all of
the following:

1. the current released ceiling is `runCompletion`
2. the current target anchor is named explicitly
3. the task fits in one honest commit
4. the task can be validated with a focused check or an explicit docs-only
   review path
5. the task does not require modeled-stage release judgment
6. the task does not require optional pattern memory to be understandable

Readiness-gate rule:

- if any checklist item is uncertain or false, stop and report rather than
  improvising
- lower-capacity autonomous work is approved only when the checklist is fully
  satisfied

## Autonomous Resume Search Order

When the latest concrete task is finished and `current.next_action` would
otherwise become "stop and ask for the next gap", a lower-capacity agent must
perform exactly one bounded resume-search pass before escalating for external
input.

Resume-search order:

1. look for one focused failing validation artifact on the current anchor
   surface
2. if focused validation is clean, read only the one additional PRD most
   relevant to the active anchor and identify one exact unenforced clause
3. if an unenforced clause is found, name one exact primary code location for
   the next one-commit hardening slice
4. stop and request external input only if neither a focused failing validation
   artifact nor an exact unenforced clause can be identified without guesswork

Focused validation priority:

- rerun the focused pytest target that exercises the current anchor or file
  group first
- if that test is clean, rerun the focused mypy/type check for the same file
  group before expanding the search
- if the typing check is also clean, rerun the focused ruff/lint target for
  that file group
- only after all three focused validation commands pass may the agent read
  another PRD clause or widen the search surface

Resume-search rule:

- "stop and ask for the next PRD-backed gap" is not a sufficient steady-state
  next action while unscanned in-bounds PRD surface still exists below
  `pageReadyObserved`
- the resume-search pass must stay below `pageReadyObserved` and must not widen
  into modeled-stage release judgment
- the resume-search pass is discovery only; it does not authorize bundling
  multiple fixes into one task
- once one failing artifact or one exact unenforced clause is found, the agent
  must return to the normal one-task-per-commit loop

Resume-search budget rule:

- the search pass must inspect at most one focused validation artifact class and
  at most one additional PRD beyond the base reading set
- the search pass must name one primary file group only
- if the search would require broad repo-wide cleanup or more than one primary
  file group to be understandable, it is not yet a valid lower-capacity next
  slice

Resume-search output rule:

- a successful resume-search pass must produce all of the following for the next
  task:
  - one exact failing validation command or one exact unenforced PRD clause
  - one exact primary code location
  - one minimum honest validation command for the follow-on task
- if the search result cannot be written in that shape, it is still too vague
  for a lower-capacity autonomous turn

File-group queue rule:

- when one file group completes its focused pytest -> mypy -> ruff -> clause-scan
  pass without yielding an exact in-bounds gap, the agent must advance to the
  next documented released-scope file group instead of stopping immediately
- the file-group queue must be explicit in `work-rag.json` current state or the
  repo adapter, not inferred from broad repository intuition
- stop is allowed only after the current file group has no exact gap and no
  further documented queued file group remains below `pageReadyObserved`

Secondary-queue rule:

- if the primary released-scope file-group queue is exhausted cleanly, a
  documented secondary queue may continue the same paused-state search on
  adjacent released-scope surfaces
- the secondary queue must still stay below `pageReadyObserved`
- the secondary queue may include released-scope CLI, config, graph-assembly, or
  reporting surfaces only when those surfaces are already part of the active
  Python-first runtime path
- stop is valid only when both the primary queue and any documented secondary
  queue are exhausted without an exact in-bounds gap

Auto-search boundary finalization rule:

- lower-capacity autonomous search must not invent a tertiary queue by default
- once the documented primary and secondary queues are exhausted, the resulting
  stop state is the canonical low-attention endpoint for the current released
  surface
- further automatic queue expansion requires an explicit PRD update rather than
  ad hoc continuation pressure from a prior stop

Queued-file-group rule:

- each queued file group must name:
  - one primary implementation file group
  - one primary PRD to scan first
  - one first focused validation command
- a lower-capacity agent must not invent a new queue ordering when one is
  already documented

Escalation rule:

- user escalation is valid only after one documented resume-search pass ends
  cleanly with no focused failing artifact and no exact unenforced clause below
  the released ceiling

## Task-Slice Rejection Rule

Reject the candidate task and reslice it before implementation when:

- the change touches more than one milestone on the critical path
- the change would require both runtime behavior edits and broad docs rewrites
  to be understandable
- the change cannot name one primary changed file group
- the change would need more than one focused validation target to establish
  basic trust
- the change is "clean up related items" rather than one attributable fix or
  hardening step

Task-slice rejection rule:

- reslicing to a smaller task is preferred over carrying uncertainty into
  validation or reporting
- if safe reslicing is not obvious, stop and report instead of widening scope

## Reporting Contract

Every autonomous task report must use this order:

- phase / milestone / anchor / invariant / next action
- changes made
- typed evidence
- commit hash
- checkpoint impact / failure-taxonomy impact

Reporting rule:

- the report must make it obvious which released anchor the task stayed under
- if validation was intentionally minimal because the change was docs-only, the
  typed evidence section must say so explicitly

## Completeness Rules

A task is complete only when all applicable checks are true:

- its phase is explicit
- its milestone is explicit
- its anchor is explicit
- its scope stays within the current approved boundary
- the execution boundary remains intact
- typed inputs and outputs remain valid
- failure taxonomy remains explicit
- checkpoint behavior remains coherent
- diagnostics remain useful
- documentation does not overstate released behavior

One-off plausibility is not enough.

## Evidence Standard

Typed evidence is required for any claim of progress or completeness.

Acceptable evidence includes:

- typed checkpoints
- typed success or failure classification
- schema-valid diagnostics
- schema-valid run outputs
- repeatable focused test results

Unacceptable evidence on its own:

- operator intuition
- one manual run that looked plausible
- presence of code without typed validation impact

## Self-RAG Rule

Autonomous work must maintain a self-RAG record as one continuous working record for the current thread of work.

Self-RAG record rule:

- use one canonical self-RAG document or record for the active work thread
- continue appending or updating that same record while the current phase remains active
- do not split the current working state across multiple competing self-RAG records

Required self-RAG sections:

- `anchor`
- `fact`
- `journal`

Required `anchor` fields:

- current phase
- current milestone
- current anchor
- current goal
- current invariant
- exactly one next action

Required `fact` behavior:

- each fact must be concrete
- each fact must point to evidence
- facts must only include information still needed for safe continuation

Required `journal` behavior:

- journal entries must record only the latest meaningful change or validation result
- journal entries must remain operational rather than narrative

Self-RAG continuity rule:

- while the work remains in the same phase, continue using the same self-RAG record
- update the current record rather than starting a fresh one for each small step

## Phase-End Compression Rule

When a phase ends, the self-RAG record must be compressed before work continues.

Compression must:

- preserve the new current phase
- preserve the new current milestone
- preserve the new current anchor
- preserve only the facts still needed for the next safe action
- collapse older journal history into a short carry-forward note when still relevant
- remove facts and notes tied only to the completed phase

Compression rule:

- do not carry the full earlier-phase history forward unchanged
- do not leave multiple stale next actions after compression
- after compression, the record must still support one safe next action

## Self-RAG Stop Record

When autonomous work stops, the self-RAG record must end with:

- current phase
- current milestone
- current anchor
- blocking reason
- next evidence or approval needed

## Definition Of Done By Work Type

Runtime behavior work is done when:

- the changed phase, milestone, and anchor are explicit
- the runtime behavior matches the current approved boundary
- typed evidence exists for the changed path
- failure taxonomy and checkpoint effects remain coherent
- focused tests for the changed approved-stage behavior pass when practical

Diagnostics or reporting work is done when:

- the report stays within the current approved boundary
- it improves operator or reviewer ability to classify the current state
- it does not imply release of a later stage
- the changed diagnostics or reporting surface is verified by a focused test or a schema-valid fixture when practical

Testing work is done when:

- the approved stage under test is explicit
- assertions check typed success, typed failure, or checkpoint coherence
- edge, error, or chaos behavior is strengthened when relevant
- the test is focused on the current approved boundary unless explicit release approval exists for a later stage

Focused test in this PRD means:

- the narrowest automated check that directly exercises the changed approved-stage behavior without requiring unrelated workflow stages to pass

Documentation work is done when:

- current scope, current ceiling, phase, milestone, and anchor are explicit
- modeled behavior and released behavior are separated clearly
- future work is not presented as implemented or approved
- the edited text is reviewed against the current approved scope and anchor map

## Minimum Validation Rule

Use the smallest validation step that can still produce trustworthy typed evidence for the task.

Minimum validation by work type:

- runtime behavior change:
  run at least one focused test that exercises the changed approved-stage behavior
- diagnostics or reporting change:
  run at least one focused test or fixture-backed check for the changed output shape when practical
- test-only change:
  run the changed test file or the narrowest relevant test target
- documentation-only change:
  review the changed text against current approved scope, milestone map, and anchor map

Escalation rule:

- if the blast radius clearly crosses multiple approved-stage surfaces, expand validation beyond the narrowest check
- if repository-wide validation is already known to be red for unrelated reasons, report that gap explicitly rather than claiming full green validation

Exception-reporting rule:

- if the minimum validation for a task cannot be run, the completion report must say exactly which validation was skipped, why it was skipped, and what evidence was used instead
- if no substitute evidence exists, the task must not be reported as complete

## Stop Rule

Autonomous work must stop when:

- the next action would cross above `pageReadyObserved`
- the next action would change a frozen milestone or anchor
- the next action requires release judgment rather than approved-boundary hardening
- evidence is too weak to judge completeness
- operator input is required for the approved path

When stopping, the report must state:

- current phase
- current milestone
- current anchor
- exact blocking reason
- next evidence or approval needed

## Completion Report Contract

Any autonomous task completed under this PRD must end with a report containing:

- current phase
- current milestone
- current anchor
- task goal
- invariant preserved
- files changed
- typed evidence used to judge completeness
- checkpoint or failure-taxonomy impact
- whether the next anchor is approved to proceed
- if not approved, the exact stop reason and next evidence or approval needed

## Success Criteria

Phase 1 is successful when:

- the orchestration remains deterministic
- the OpenClaw boundary remains intact
- the current benchmark path stays narrow and explicit
- typed readiness and failure evidence remain coherent
- repeated runs remain comparable
- later workflow release is justified only through typed evidence at named anchors

## Non-Goals

- anti-detection or evasion features
- full autonomous browser planning
- broad multi-site generalization in the current phase
- automatic release of later workflow stages without evidence
- treating modeled workflow stages as already released
