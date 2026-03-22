# PRD — Python LangGraph Runtime

## Purpose

This PRD defines the canonical implementation path for the next stage of
`ez-ax`.

It exists so an autonomous agent can determine, from documentation alone:

- that Python is now the canonical implementation stack
- what `LangGraph` owns
- what `LangChain` owns
- what `OpenClaw` owns
- what `ez-ax` owns
- what counts as complete
- what is still released versus only modeled

This PRD supersedes the previous runtime PRD as the canonical implementation
path, while preserving the benchmark release ceiling defined in
[`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md).

## Source-Of-Truth Order

1. [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
2. this PRD
3. mission, state-model, layout, tooling, evidence, validation, and RAG
   sub-PRDs written beneath this PRD

Precedence rule:

- if this PRD and an older runtime PRD disagree about the canonical
  implementation stack, this PRD wins
- if this PRD and the benchmark release ceiling disagree, the benchmark release
  ceiling wins

## Canonical Stack

The canonical implementation stack is:

- runtime language: Python
- orchestration engine: LangGraph
- model/tool composition layer: LangChain
- browser-facing execution actor: OpenClaw
- E2E browser verification: Playwright Python
- unit and contract test runner: pytest
- async test support: pytest-asyncio
- lint and formatting: ruff
- static typing: mypy

Canonical-stack rule:

- new runtime implementation work should target this stack
- legacy TypeScript contracts may remain as reference artifacts during reset and
  migration, but they are no longer the canonical implementation path

## North Star

Build a deterministic Python runtime in which:

- `OpenClaw` is the only browser-facing actor
- `ez-ax` owns orchestration, checkpointing, typed evidence aggregation, failure
  classification, and release-gate reasoning
- `LangGraph` expresses mission flow, state transitions, retries, and stop
  decisions
- `LangChain` supports model and tool composition without owning runtime truth
- repeated runs produce comparable artifacts and reusable lessons

North-star rule:

- the runtime should be designed so a later agent can continue from PRD and RAG
  state only

## Ownership Model

### OpenClaw

Owns:

- browser-facing execution
- actual computer-use interactions
- execution-side observations that can be returned as evidence

Must not own:

- orchestration policy
- release-gate decisions
- final stop-reason classification

### ez-ax

Owns:

- mission selection
- graph progression
- typed evidence normalization
- artifact generation
- release versus modeled distinction
- RAG updates and compression

Must not own:

- direct browser control outside OpenClaw

### LangGraph

Owns:

- runtime state machine
- mission node sequencing
- edge conditions
- stop and retry transitions

Must not own:

- browser control
- screenshot truth by itself

### LangChain

Owns:

- prompt composition
- model invocation
- tool wrappers
- retriever or RAG plumbing where needed

Must not own:

- canonical runtime state
- release gating
- primary execution authority

## Completeness

The Python runtime is complete only when:

- the canonical stack is fully unambiguous
- all runtime missions are explicit
- graph state and transition rules are explicit
- hybrid evidence rules are explicit in Python-runtime terms
- validation and flaky-budget rules are explicit for the Python stack
- repository layout is explicit
- RAG behavior is explicit under the new stack
- autonomous implementation can proceed without hidden architectural choices

Completeness rule:

- "Python exists in the repo" is not enough
- "the canonical Python runtime can be built from PRD and RAG alone" is
  required

## Release Boundary

This PRD does not release a broader benchmark workflow by itself.

Released ceiling remains:

- `pageReadyObserved`

Rule:

- Python-first runtime work may become canonical implementation work without
  changing the released workflow ceiling
- modeled runtime work above `pageReadyObserved` must still be labeled modeled
- release-ceiling articulation:
- the runtime must treat `evidence://action-log/release-ceiling-stop` as
  deterministically satisfied only after `artifacts/action-log/release-ceiling-stop.jsonl`
  contains a JSON line with `event='release-ceiling-stop'`, `mission_name='page_ready_observation'`,
  and an ISO-8601 `ts`; the release-ceiling validator must fail loudly (see
  [`docs/product/prd-openclaw-e2e-validation.md`](./prd-openclaw-e2e-validation.md))
  whenever that artifact is missing or malformed, and the failure must reference the
  concrete artifact path, the typed fields, and the release-ceiling PRDs
  (`docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-evidence-model.md`,
  `docs/product/prd-python-validation-contract.md`) so downstream lessons
  can replay it

## Phase Map

### Phase 0 — Canonical Runtime Redefinition

Goal:

- declare the canonical Python stack
- define ownership boundaries
- define the reset direction

Primary milestone:

- Python-first implementation path is explicit and unambiguous

Primary anchor:

- `pythonRuntimeContractApproved`

Done when:

- this PRD exists
- reset direction is explicit
- the roadmap and current RAG can safely point to the Python-first path

### Phase 1 — Runtime Reset Planning

Goal:

- define how the repo moves from the legacy scaffold to the Python-first stack

Primary milestone:

- reset scope is explicit enough that implementation does not guess what to keep
  or archive

Primary anchor:

- `pythonResetPlanApproved`

Done when:

- reset PRD exists
- keep/archive/delete/new-create decisions are explicit

### Phase 2 — Mission Definition

Goal:

- define all runtime missions in Python-first terms

Primary milestone:

- no runtime-critical mission is left implied

Primary anchor:

- `runtimeMissionMapApproved`

### Phase 3 — Graph Definition

Goal:

- define LangGraph state and transition rules

Primary milestone:

- implementation can build the graph without inventing orchestration semantics

Primary anchor:

- `langGraphStateModelApproved`

### Phase 4 — Validation And Layout Definition

Goal:

- define repository structure, Python tooling, and release-gate validation

Primary milestone:

- implementation choices for layout, tests, linting, and type checking are no
  longer ambiguous

Primary anchor:

- `pythonValidationContractApproved`

## Autonomous Work Loop

Each autonomous task under this PRD must:

1. read `AGENTS.md`, the benchmark PRD, `work-rag.json`, and `rag.json` first,
   then read only the relevant runtime sub-PRDs needed for the current in-bounds
   task
2. declare phase, milestone, anchor, invariant, and next action
3. choose one highest-value in-bounds task
4. perform that task only
5. update `work-rag.json`
6. compact same-scope checkpoint history when it exceeds the active-history
   budget defined by the RAG operations PRD
7. promote any durable lesson into `rag.json`
8. run the smallest trustworthy validation
9. report in the benchmark PRD order: phase/milestone/anchor/invariant/next
    action, changes made, typed evidence, commit hash, checkpoint impact or
    failure-taxonomy impact
11. commit the task
12. stop if the next step would widen scope or blur released versus modeled

## Stop Conditions

Work must stop when:

- a task would treat legacy TypeScript scaffolding as the canonical path
- a task would widen the released workflow ceiling
- a task would make LangChain the orchestration owner
- a task would give browser-facing authority to anything except OpenClaw
- a task would begin Python-first implementation before the reset and mission
  PRDs exist

## Immediate Next Action

The next document to write after this PRD is:

- [`prd-python-runtime-reset.md`](./prd-python-runtime-reset.md)

Reason:

- the canonical stack can now be declared, but the repository reset boundary is
  still not explicit
