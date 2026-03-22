# PRD — LangChain Tooling Policy

## Purpose

This PRD defines the allowed role of `LangChain` inside the Python-first
`ez-ax` runtime.

It exists so an autonomous agent can determine:

- what `LangChain` is allowed to own
- what `LangChain` must never own
- how `LangChain` interacts with `LangGraph`
- how `LangChain` interacts with OpenClaw adapters
- how prompt, model, tool, and retrieval composition should behave

This PRD should be read beneath:

1. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
2. [`prd-runtime-missions.md`](./prd-runtime-missions.md)
3. [`prd-langgraph-state-model.md`](./prd-langgraph-state-model.md)
4. [`prd-python-runtime-layout.md`](./prd-python-runtime-layout.md)

Precedence rule:

- if a LangChain behavior in this PRD conflicts with graph ownership, the graph
  and runtime PRDs win
- if a LangChain behavior in this PRD conflicts with OpenClaw-only
  browser-facing authority, the runtime PRD wins

## Policy Goal

Use `LangChain` as a composition layer, not as the runtime authority.

Policy rule:

- `LangChain` may help the runtime think, retrieve, and call tools
- `LangChain` may not become the source of runtime truth

## Allowed Responsibilities

`LangChain` may own:

- prompt assembly
- model invocation wrappers
- tool-call wrappers
- retriever integration for PRD, RAG, and artifact context
- response shaping before graph consumption
- reusable chains for analysis tasks that do not own canonical state

Allowed-responsibility rule:

- LangChain is a subordinate execution aid for graph nodes and missions

## Forbidden Responsibilities

`LangChain` must not own:

- canonical run state
- mission progression decisions
- release-gate decisions
- final stop-reason classification
- direct browser execution
- the sole interpretation of screenshot evidence
- hidden memory that bypasses `work-rag.json` or `rag.json`

Forbidden-responsibility rule:

- if a decision changes graph direction, release status, or stop reason, that
  decision belongs outside LangChain

## Interaction With LangGraph

LangGraph owns:

- graph state
- node transitions
- retries
- stops
- escalations

LangChain supports LangGraph by:

- receiving explicit state slices as input
- returning structured outputs for node consumption
- never mutating canonical graph state on its own

Interaction rule:

- LangChain outputs must be treated as inputs to graph evaluation, not as
  automatic state mutations

## Interaction With OpenClaw

LangChain may:

- help formulate execution requests
- help summarize returned execution evidence
- help rank fallback options for operator-free evaluation

LangChain must not:

- issue browser actions directly
- pretend to be the browser-facing actor
- relabel ambiguous OpenClaw evidence as certain truth

OpenClaw-interaction rule:

- every browser-facing side effect remains attributable to OpenClaw alone

## Prompt Policy

Prompt construction may include:

- current mission context
- relevant state slices
- relevant PRD excerpts
- relevant RAG facts and lessons
- relevant evidence snippets

Prompt construction must avoid:

- leaking unrelated historical clutter
- asking the model to invent undocumented policy
- instructing the model to overrule explicit PRD constraints

Prompt-policy rule:

- prompts should narrow ambiguity, not outsource architecture decisions

## Tool Policy

LangChain tool wrappers may expose:

- retrieval over PRDs
- retrieval over `work-rag.json`
- retrieval over `rag.json`
- artifact comparison helpers
- reporting helpers
- OpenClaw adapter entrypoints mediated by graph policy

Tool-policy rule:

- tools exposed through LangChain must still be callable through explicit graph
  node authority

## Retrieval Policy

Retrieval may use:

- active PRDs
- current work RAG
- durable lesson RAG
- retained comparable artifacts

Retrieval must not use:

- deleted repo structure as if it were active
- hidden conversational memory as a substitute for durable memory

Retrieval-policy rule:

- retrieved context should be durable, inspectable, and attributable

## Output Contract

LangChain outputs consumed by the runtime should be:

- structured
- comparable
- attributable to a prompt and evidence slice
- narrow enough for graph nodes to validate

Output-contract rule:

- free-form narrative may help reporting, but graph-driving outputs should be
  typed or strongly structured

## Failure Handling

When a LangChain call is weak or ambiguous:

- the graph should treat that as input insufficiency, not as silent success
- the runtime may retry only if retry policy allows it
- the runtime may stop or escalate if policy is insufficient

Failure-handling rule:

- a model answer is never a substitute for missing required evidence

## RAG Policy

LangChain may consume:

- `work-rag.json`
- `rag.json`

LangChain must not:

- write durable memory without routing through the RAG mission path
- maintain a shadow memory source that future agents cannot inspect

RAG-policy rule:

- durable knowledge must remain in the canonical files, not inside LangChain
  abstractions

## Completeness

This policy is complete only when:

- LangChain's role is clearly narrower than LangGraph's role
- browser-facing authority remains clearly outside LangChain
- retrieval and prompt use are explicit
- later implementation does not need to guess whether LangChain owns runtime
  truth

## Immediate Next Action

The next document to write after this PRD is:

- `docs/product/prd-python-validation-contract.md`

Reason:

- once LangChain's authority is constrained, the next highest-value task is to
  define the canonical Python validation and release-gate contract
