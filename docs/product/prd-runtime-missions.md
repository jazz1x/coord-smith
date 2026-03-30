# PRD — Runtime Missions

## Purpose

This PRD defines every runtime-critical mission in the Python-first `ez-ax`
runtime.

It exists so an autonomous agent can determine:

- what missions exist
- what each mission is trying to achieve
- what inputs and outputs each mission requires
- what evidence is expected
- what counts as done
- when a mission must stop
- whether a mission is released or modeled

This PRD should be read beneath:

1. [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
2. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
3. [`prd-python-runtime-reset.md`](./prd-python-runtime-reset.md)

Precedence rule:

- if a mission in this PRD appears to widen the benchmark released ceiling, the
  benchmark PRD wins
- if a mission in this PRD conflicts with the Python-first ownership model, the
  Python runtime PRD wins

## Mission Rules

Every mission must have:

- a stable mission name
- a goal
- required inputs
- produced outputs
- required evidence
- a done-when condition
- a stop condition
- a lifecycle status

Mission rule:

- no runtime-critical behavior may remain implied once this PRD is complete

Lifecycle-status rule:

- `released` means the mission is inside the current benchmark release ceiling
- `modeled` means the mission is intentionally specified but not yet released
- `control` means the mission governs validation, gating, retry, or memory
  behavior rather than product-stage progression

Lifecycle-status mechanics:

- treat a mission as `released` only when it appears in the "Released Path Missions"
  list and its outcome does not require any anchor above `runCompletion`
- treat a mission as `modeled` when it appears in the "Modeled Path Missions" list
  or would require any anchor above `runCompletion` to complete
- treat a mission as `control` only when it does not advance the product-stage
  path and instead gates, validates, retries, or records evidence about other
  missions
- if a mission name or outcome would imply a higher anchor than the benchmark PRD
  allows, classify it as `modeled` even if the implementation exists in code
- all 12 path missions from `attach_session` through `run_completion` are now
  released

## Mission Groups

The mission set is grouped into:

- released path missions
- modeled path missions
- control missions
- RAG missions
- validation missions

## Released Path Missions

### Mission: `attach_session`

Goal:

- attach `ez-ax` orchestration to the intended OpenClaw-managed authenticated
  session

Required input:

- target session identifier
- expected authentication state

Produced output:

- attached session reference
- typed attach checkpoint

Required evidence:

- session attachment confirmation
- authentication-state confirmation

Done when:

- the intended session is attached and confirmed authenticated

Stop condition:

- target session cannot be found
- attached session is not authenticated

Lifecycle status:

- released

### Mission: `prepare_session`

Goal:

- validate that the attached session can safely begin the released benchmark path

Required input:

- attached session reference
- target site and page

OpenClaw interface:

- request payload conventions for released scope are defined in
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
  under "OpenClaw Interface Contract (Released Scope)"
- released-scope payload keys:
  - `target_page_url`
  - `site_identity`

Produced output:

- prepared session state
- typed preparation checkpoint

Required evidence:

- target page intent
- session viability confirmation

Done when:

- the session is stable enough to continue to target-page entry

Stop condition:

- target page is rejected
- session is invalid for benchmark entry

Lifecycle status:

- released

### Mission: `benchmark_validation`

Goal:

- enter the target page and validate the released benchmark path before the
  workflow ceiling

Required input:

- prepared session state
- target page reference

OpenClaw interface:

- request payload conventions for released scope are defined in
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
  under "OpenClaw Interface Contract (Released Scope)"
- released-scope payload keys:
  - `target_page_url`

Produced output:

- benchmark entry state
- typed benchmark checkpoint

Required evidence:

- target-page entry observation
- typed observation boundary confirmation

Done when:

- the target page has been entered through a typed observation path

Stop condition:

- target-page entry cannot be observed

Lifecycle status:

- released

### Mission: `page_ready_observation`

Goal:

- validate page-shell readiness and stop cleanly at the released ceiling

Required input:

- benchmark entry state

OpenClaw interface:

- released-scope conventions are defined in
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
  under "OpenClaw Interface Contract (Released Scope)"
- payload may be empty for this mission in released scope

Produced output:

- released pre-workflow-ready state
- typed page-ready checkpoint

Required evidence:

- page-shell readiness confirmation
- release-ceiling stop confirmation
- release-ceiling stop failures must reference `artifacts/action-log/release-ceiling-stop.jsonl`, the typed fields (`event`, `mission_name`, `ts`), and the release-ceiling PRD bundle (`docs/product/prd-openclaw-e2e-validation.md`, `docs/product/prd-openclaw-computer-use-runtime.md`, `docs/product/prd-openclaw-evidence-model.md`, `docs/product/prd-python-validation-contract.md`) before declaring the ceiling stop observed

Done when:

- `pageReadyObserved` is reached with typed evidence

Stop condition:

- page-shell readiness cannot be established
- a later workflow stage would be required to continue

Lifecycle status:

- released

### Mission: `sync_observation`

Goal:

- observe server time and normalize timing before trigger preparation

Required input:

- released pre-workflow-ready state

Produced output:

- sync-established state
- normalized timing artifact

Required evidence:

- server-time observation
- timing normalization record

Done when:

- sync is typed, stable, and comparable

Stop condition:

- time source is unavailable
- timing cannot be normalized without ambiguity

Lifecycle status:

- released

### Mission: `target_actionability_observation`

Goal:

- determine whether the target action is actionable

Required input:

- sync-established state
- target interaction context

Produced output:

- actionability state
- typed actionability checkpoint

Required evidence:

- typed actionability signal
- fallback evidence if primary signals are insufficient

Done when:

- target actionability is explicit and typed

Stop condition:

- actionability cannot be determined without ambiguity

Lifecycle status:

- released

### Mission: `armed_state_entry`

Goal:

- enter an explicit armed pre-click state

Required input:

- actionability state

Produced output:

- armed state
- typed armed checkpoint

Required evidence:

- armed-state confirmation

Done when:

- the runtime is explicitly armed for trigger waiting

Stop condition:

- armed state cannot be established deterministically

Lifecycle status:

- released

### Mission: `trigger_wait`

Goal:

- wait for the trigger boundary without leaving a deterministic evidence trail

Required input:

- armed state
- trigger timing context

Produced output:

- trigger-reached state
- typed trigger checkpoint

Required evidence:

- timing or event-based trigger observation

Done when:

- the trigger boundary is reached with typed evidence

Stop condition:

- trigger timing becomes ambiguous
- waiting would require intuition rather than evidence

Lifecycle status:

- released

### Mission: `click_dispatch`

Goal:

- dispatch the click through OpenClaw

Required input:

- trigger-reached state
- targeting evidence

Produced output:

- click-dispatched state
- typed dispatch checkpoint

Required evidence:

- targeting confirmation
- dispatch action log

Done when:

- the click is dispatched through OpenClaw with supporting evidence

Stop condition:

- target cannot be determined confidently enough
- dispatch cannot be attributed to OpenClaw

Lifecycle status:

- released

### Mission: `click_completion`

Goal:

- confirm that the dispatched click completed as expected

Required input:

- click-dispatched state

Produced output:

- click-completed state
- typed completion checkpoint

Required evidence:

- post-dispatch observation
- click-completion confirmation

Done when:

- click completion is typed and comparable

Stop condition:

- completion cannot be observed
- dispatch outcome remains ambiguous

Lifecycle status:

- released

### Mission: `success_observation`

Goal:

- observe the configured success surface and classify the run

Required input:

- click-completed state
- success surface definition

Produced output:

- success-observed state
- success classification artifact

Required evidence:

- success surface observation
- machine-verifiable classification evidence

Done when:

- success or failure classification is machine-verifiable and comparable

Stop condition:

- success surface cannot be determined
- classification remains ambiguous

Lifecycle status:

- released

### Mission: `run_completion`

Goal:

- finalize the run into comparable outputs

Required input:

- success-observed state

Produced output:

- final run artifact bundle
- run-completed checkpoint

Required evidence:

- final comparable output set
- retained classification

Done when:

- the run can be compared against other runs without hidden context

Stop condition:

- outputs are incomplete or not comparable

Lifecycle status:

- released

## Modeled Path Missions

No missions are currently modeled. All 12 path missions from `attach_session`
through `run_completion` have been released.

## Control Missions

### Mission: `release_gate_evaluation`

Goal:

- determine whether the current run qualifies for a release-grade claim

Required input:

- mission artifacts
- validation results

Produced output:

- release-gate decision
- typed gate report

Required evidence:

- validation results
- stop reasons
- artifact comparison context

Done when:

- release decision can be explained without operator intuition

Stop condition:

- gate decision would require an undocumented assumption

Lifecycle status:

- control

### Mission: `retry_or_stop_decision`

Goal:

- decide whether the runtime should retry, stop, or escalate

Required input:

- latest stop reason
- retry policy

Produced output:

- retry, stop, or escalate decision

Required evidence:

- typed failure or ambiguity evidence

Done when:

- the decision path is explicit and reproducible

Stop condition:

- policy is insufficient to decide honestly

Lifecycle status:

- control

## RAG Missions

### Mission: `work_rag_update`

Goal:

- keep the canonical current-tense work record accurate

Required input:

- latest task result

Produced output:

- updated `work-rag.json`

Required evidence:

- task result summary
- current phase, milestone, anchor, invariant, next action

Done when:

- `work-rag.json` accurately reflects the current mission state

Stop condition:

- the task result cannot be summarized honestly

Lifecycle status:

- control

### Mission: `work_rag_compression`

Goal:

- compress current work memory at milestone and phase boundaries

Required input:

- completed milestone or phase context

Produced output:

- compressed `work-rag.json` history record

Required evidence:

- boundary summary
- evidence references

Done when:

- future continuation no longer depends on transient step-by-step memory

Stop condition:

- compression would remove facts still needed for continuation

Lifecycle status:

- control

### Mission: `lesson_promotion`

Goal:

- promote reusable mistakes or heuristics into `rag.json`

Required input:

- repeated issue or durable lesson

Produced output:

- lesson entry in `rag.json`

Required evidence:

- evidence references
- lesson summary
- reuse justification

Done when:

- a future agent could benefit from the promoted lesson

Stop condition:

- the lesson is still only transient work state

Lifecycle status:

- control

## Validation Missions

### Mission: `e2e_replay_or_comparison`

Goal:

- compare the current run against a prior run or replay baseline

Required input:

- current artifact bundle
- prior artifact bundle or replay reference

Produced output:

- comparison result
- repeatability note

Required evidence:

- artifact diff or comparison summary

Done when:

- the run can be discussed in repeatability terms rather than intuition

Stop condition:

- no trustworthy comparison is possible

Lifecycle status:

- control

### Mission: `python_validation_execution`

Goal:

- execute the smallest trustworthy Python validation set for the current task

Required input:

- changed scope
- applicable validation policy

Produced output:

- validation result
- skipped-validation explanation when necessary

Required evidence:

- test output
- lint/type output
- explicit skip reason if anything is not run

Done when:

- the task has the minimum trustworthy validation required by its scope

Stop condition:

- no honest validation or substitute evidence exists

Lifecycle status:

- control

## Mission Ordering Rules

Released-path ordering:

- `attach_session`
- `prepare_session`
- `benchmark_validation`
- `page_ready_observation`
- `sync_observation`
- `target_actionability_observation`
- `armed_state_entry`
- `trigger_wait`
- `click_dispatch`
- `click_completion`
- `success_observation`
- `run_completion`

Modeled-path ordering:

- (none -- all path missions are released)

Control rule:

- control, RAG, and validation missions may wrap or close other missions, but
  they must not silently widen the released path
- a mission may depend on hybrid evidence rules, but screenshot fallback or
  coordinate execution must not overrule typed primary signals by themselves

## Completeness

This mission map is complete only when:

- every runtime-critical mission is named
- every mission has a done-when and stop condition
- released versus modeled status is explicit for every mission
- later PRDs can reference missions without inventing them

## Immediate Next Action

The next document to write after this PRD is:

- `docs/product/prd-langgraph-state-model.md`

Reason:

- once missions are explicit, the next highest-value task is to define how they
  are represented as graph state and transitions
