# PRD — Python Runtime PRD Roadmap

## Purpose

This document defines the PRD checklist and authoring order required to move the
project from the current OpenClaw runtime PRD set to a Python-first canonical
implementation path.

It exists to answer one question:

- what PRDs must exist before the repository can honestly claim that the
  Python + LangGraph + LangChain + Python-test-stack direction is ready for
  autonomous implementation work?

## Authoring Direction

This roadmap follows the same direction already established in the repository:

- documentation first
- one main PRD plus focused sub-PRDs
- explicit released versus modeled separation
- typed evidence and typed stop reasons
- RAG-backed autonomous continuation
- task-by-task validation and commit closure

Rule:

- no Python-first implementation work should become the canonical path until the
  PRDs below are written and internally consistent

## North Star

Create a PRD set that is sufficient for an autonomous agent to build the
Python-first runtime without hidden context.

That means the final PRD set must define:

- the canonical stack
- all missions
- state transitions
- evidence flow
- validation and release gates
- repository layout
- RAG operating rules
- stop conditions

## Completion Test

The Python-first PRD set is complete only if all of the following are true:

- an agent can tell that Python is the canonical implementation path
- an agent can tell what LangGraph owns and what LangChain owns
- an agent can tell what OpenClaw owns and what ez-ax owns
- every mission has a goal, input, output, done-when rule, and stop condition
- graph transitions are explicit
- the Python test stack is explicit
- released versus modeled behavior is still explicit
- `work-rag.json` and `rag.json` remain sufficient for autonomous continuation

## Required PRDs

### 1. Main Runtime PRD

File:

- `docs/product/prd-python-langgraph-runtime.md`

Purpose:

- declare Python + LangGraph + LangChain as the canonical implementation path
- define top-level purpose, north star, completeness, release philosophy, and
  autonomous-work contract

Must answer:

- why Python is the canonical stack
- why LangGraph is the orchestration layer
- why LangChain is the model/tool layer
- why OpenClaw remains the only browser-facing actor
- what "complete" means for the Python runtime

Done when:

- the canonical stack is unambiguous
- source-of-truth precedence versus existing PRDs is explicit
- phase map for the Python runtime exists

### 2. Runtime Mission Map PRD

File:

- `docs/product/prd-runtime-missions.md`

Purpose:

- define every mission the runtime must perform

Each mission must include:

- mission name
- goal
- required input
- produced output
- evidence expectation
- done-when
- stop condition
- release status

Minimum mission set:

- attach session
- prepare session
- benchmark validation
- page ready observation
- sync observation
- target actionability observation
- armed-state entry
- trigger wait
- click dispatch
- click completion
- success observation
- run completion
- release-gate evaluation
- RAG compression
- lesson promotion
- E2E replay or comparison

Done when:

- no runtime-critical mission is left implied
- every mission can be referenced by future implementation tasks

### 3. LangGraph State Model PRD

File:

- `docs/product/prd-langgraph-state-model.md`

Purpose:

- define the graph state, node contract, edge rules, retry rules, and stop
  semantics

Must include:

- global state shape
- mission-local state shape
- edge preconditions
- stop-reason model
- retry model
- release-gate transitions

Done when:

- a future agent can implement the graph without inventing transition logic

### 4. Python Runtime Layout PRD

File:

- `docs/product/prd-python-runtime-layout.md`

Purpose:

- define the Python repository structure and package boundaries

Must include:

- package layout
- where graph code lives
- where adapter code lives
- where evidence normalization lives
- where validation lives
- where RAG management lives
- where tests live

Done when:

- repository layout decisions do not need to be guessed during implementation

### 5. LangChain Tooling Policy PRD

File:

- `docs/product/prd-langchain-tooling-policy.md`

Purpose:

- define the exact role of LangChain and the boundaries it must not cross

Must include:

- prompt and tool composition role
- retriever or RAG integration role
- what LangChain must not own
- how LangChain interacts with LangGraph state

Done when:

- LangChain is clearly subordinate to the runtime architecture instead of
  becoming an ambiguous catch-all

### 6. Hybrid Evidence PRD Refresh

File:

- existing `docs/product/prd-openclaw-evidence-model.md`, or a Python-specific
  successor if needed

Purpose:

- restate the hybrid evidence model in Python-runtime terms

Must include:

- typed signal priority
- screenshot fallback rules
- coordinate last-resort rules
- evidence conflict handling
- evidence envelope shape expectations

Done when:

- the Python runtime can consume evidence rules without reinterpretation

### 7. Python E2E Validation PRD

File:

- either replace or extend
  `docs/product/prd-openclaw-e2e-validation.md`

Purpose:

- define the canonical Python test stack and release gate

Must include:

- `pytest`
- `pytest-asyncio`
- Playwright Python for E2E
- `mypy`
- `ruff`
- flaky-budget policy
- artifact-preservation policy

Done when:

- an agent can choose the correct Python validation tool for each task

### 8. Python RAG Operations PRD

File:

- `docs/product/prd-python-rag-operations.md`

Purpose:

- define how `work-rag.json` and `rag.json` operate once Python-first
  implementation begins

Must include:

- when to update each file
- when to compress
- when to promote a lesson
- how to reference Python evidence and tests

Done when:

- RAG behavior remains stable after the implementation stack changes

## Recommended Authoring Order

The recommended order is:

1. `prd-python-langgraph-runtime.md`
2. `prd-runtime-missions.md`
3. `prd-langgraph-state-model.md`
4. `prd-python-runtime-layout.md`
5. `prd-langchain-tooling-policy.md`
6. hybrid evidence PRD refresh
7. Python E2E validation PRD
8. Python RAG operations PRD

Order rule:

- do not write lower-level implementation PRDs before the main runtime PRD and
  mission map exist

## Autonomous-Readiness Checklist

The Python-first direction is not ready for autonomous implementation until the
answer to each item is "yes":

- is the canonical Python stack explicit?
- are all missions explicit?
- is the LangGraph state model explicit?
- is the repository layout explicit?
- is the LangChain role explicit?
- is the Python test stack explicit?
- is the hybrid evidence model still explicit?
- are `work-rag.json` and `rag.json` still sufficient after the stack shift?
- can each autonomous task still end with validation, RAG updates, and a commit?

## Immediate Next Action

The next document to write is:

- `docs/product/prd-python-langgraph-runtime.md`

Reason:

- without that document, the repository still has no canonical PRD declaring the
  Python-first direction as the primary implementation path
