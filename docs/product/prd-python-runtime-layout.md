# PRD — Python Runtime Layout

## Purpose

This PRD defines the canonical Python repository layout for the reset runtime.

It exists so an autonomous agent can determine, from documentation alone:

- what top-level Python package to create
- where graph code lives
- where OpenClaw adapters live
- where evidence normalization lives
- where validation logic lives
- where RAG logic lives
- where tests and tool configuration live

This PRD should be read beneath:

1. [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
2. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
3. [`prd-runtime-missions.md`](./prd-runtime-missions.md)
4. [`prd-langgraph-state-model.md`](./prd-langgraph-state-model.md)
5. [`prd-python-runtime-reset.md`](./prd-python-runtime-reset.md)

Precedence rule:

- if a layout choice in this PRD conflicts with mission ownership, the mission
  and state-model PRDs win
- if a layout choice in this PRD would blur the canonical Python path with
  legacy reference assets, the reset PRD wins

## Layout Goals

The Python repository layout must be:

- explicit
- minimal
- reset-friendly
- testable
- separable by ownership boundary

Layout rule:

- no directory should exist without a clear ownership reason in the runtime
  architecture

## Canonical Top-Level Shape

The reset repository should converge on this active shape:

- `src/ez_ax/`
- `tests/`
- `docs/product/`
- `.codex/`
- Python tool configuration files at repository root

Top-level rule:

- `docs/product/` remains the source-of-truth documentation area
- `.codex/` remains the local agent-assistance area
- runtime implementation lives under `src/ez_ax/`
- tests live under `tests/`

## Python Package Root

Canonical package root:

- `src/ez_ax/`

Package-root rule:

- the runtime must have one canonical Python package root
- package naming should remain stable enough that later automation and tests do
  not need to guess import paths

## Runtime Package Boundaries

The package should be divided into:

- `src/ez_ax/graph/`
- `src/ez_ax/missions/`
- `src/ez_ax/adapters/`
- `src/ez_ax/evidence/`
- `src/ez_ax/validation/`
- `src/ez_ax/rag/`
- `src/ez_ax/models/`
- `src/ez_ax/config/`
- `src/ez_ax/reporting/`

Boundary rule:

- each package exists to support a distinct ownership boundary from the runtime
  PRD

## `graph/`

`graph/` owns:

- LangGraph assembly
- node registration
- edge registration
- graph entrypoints
- graph-level orchestration helpers

`graph/` must not own:

- direct browser execution
- evidence parsing details
- validation policy definitions

### Released-Scope OpenClaw Wiring Call-Site (Contract)

In released scope (up to `pageReadyObserved`), the first orchestrator/graph
call-site that wires the OpenClaw execution wrapper MUST live under:

- `src/ez_ax/graph/`

Canonical released-scope call-site modules:

- node-level call-sites:
  - `src/ez_ax/graph/released_call_site.py`
- released-scope sequencing entrypoint (still below ceiling):
  - `src/ez_ax/graph/released_entrypoint.py`

Wiring contract:

- node-level call-sites MUST invoke the released-scope OpenClaw wrapper:
  - `src/ez_ax/adapters/openclaw/execution.py::execute_openclaw_within_scope`
- the sequencing entrypoint MUST generate `run_id` and create `run_root`
  (see `prd-langgraph-state-model.md` “Run Root Ownership (Released Scope)”)
- `run_root` MUST already exist before any call-site passes it into
  `execute_openclaw_within_scope` as `run_root=...`
- the graph/orchestrator owns `run_root` creation and lifecycle; OpenClaw is
  passed a reference only for artifact resolution checks, not for ownership

Ceiling rule:

- released-scope call-sites and entrypoints MUST sequence only the released
  missions up through `page_ready_observation` and MUST not invoke any modeled
  mission above `pageReadyObserved`
- crosswalk rule:
- release-ceiling documentation that mentions `page_ready_observation` must
  also call out the release-ceiling artifact (`artifacts/action-log/release-ceiling-stop.jsonl`),
  the typed fields it is expected to contain (`event`, `mission_name`, `ts`),
  and the linked release-ceiling PRDs
  (`docs/product/prd-openclaw-evidence-model.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`,
  `docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-python-validation-contract.md`) so OpenClaw wiring remains
  anchored to the typed determinism chain whenever it handles the release-
  ceiling stop artifact.

### Released-Scope Entrypoint Inputs (Contract)

In released scope (up to `pageReadyObserved`), the orchestrator must receive
operator-prepared session attachment inputs without guesswork.

Contract:

- the released-scope entrypoint function signature remains explicit:
  - `src/ez_ax/graph/released_entrypoint.py::run_released_scope(...)`
  - `session_ref: str`
  - `expected_auth_state: str`
  - `target_page_url: str`
  - `site_identity: str`
- any user-facing entrypoint that calls `run_released_scope` MUST resolve these
  values in a deterministic order and MUST fail fast when required values are
  missing
- **released-scope input-source order** (highest precedence first):
  1. CLI arguments
  2. environment variables
  3. (no fallback) error

Environment variable names (released scope):

- `EZAX_SESSION_REF`
- `EZAX_EXPECTED_AUTH_STATE`
- `EZAX_TARGET_PAGE_URL`
- `EZAX_SITE_IDENTITY`

Scope rule:

- config-file-driven mission input resolution is **modeled-only** unless
  explicitly released by the benchmark PRD; do not add a config file as a
  required released-scope dependency to avoid widening the execution contract
  without evidence

## `missions/`

`missions/` owns:

- mission-level business logic
- mission input/output contracts
- mission-local orchestration helpers

`missions/` must not own:

- graph wiring
- direct OpenClaw transport logic

Mission-package rule:

- mission modules should follow the canonical mission names from
  [`prd-runtime-missions.md`](./prd-runtime-missions.md)

## `adapters/`

`adapters/` owns:

- OpenClaw integration
- external tool wrappers
- transport or protocol translation

Canonical subpackages:

- `src/ez_ax/adapters/openclaw/`
- `src/ez_ax/adapters/langchain/`

Adapter rule:

- browser-facing behavior belongs only in `adapters/openclaw/`
- LangChain adapter code belongs in `adapters/langchain/`, but it remains
  subordinate to graph and mission policy

## `evidence/`

`evidence/` owns:

- evidence envelopes
- evidence normalization
- typed signal parsing
- screenshot fallback interpretation helpers
- comparison-ready evidence shaping

Evidence-package rule:

- `evidence/` normalizes truth inputs, but it does not decide release gates or
  graph progression by itself

## `validation/`

`validation/` owns:

- release-gate helpers
- flaky-budget checks
- validation-entrypoint selection
- comparable artifact checks

Validation-package rule:

- `validation/` evaluates quality and release-readiness; it does not perform
  browser execution

## `rag/`

`rag/` owns:

- `work-rag.json` access helpers
- `rag.json` access helpers
- work-memory updates
- compression helpers
- lesson-promotion helpers

RAG-package rule:

- durable memory operations must be callable without hidden thread context

## `models/`

`models/` owns:

- typed state models
- evidence models
- failure models
- report and artifact models

Model-package rule:

- `models/` is the shared type layer, not a dumping ground for business logic

## `config/`

`config/` owns:

- runtime configuration loading
- environment parsing
- stable config defaults

Config-package rule:

- configuration parsing belongs here, not scattered across missions or adapters

## `reporting/`

`reporting/` owns:

- comparable report rendering
- artifact-bundle shaping
- human-readable runtime summaries

Reporting rule:

- reporting consumes runtime outputs; it does not decide runtime truth

## Test Layout

The canonical test layout should include:

- `tests/unit/`
- `tests/contract/`
- `tests/e2e/`
- `tests/fixtures/`

Test-layout rule:

- tests are organized by validation purpose, not by framework accident

### `tests/unit/`

Owns:

- small deterministic logic tests
- pure helper tests

### `tests/contract/`

Owns:

- mission contract tests
- graph-transition contract tests
- evidence and artifact contract tests

### `tests/e2e/`

Owns:

- OpenClaw-driven released-path verification
- Python Playwright verification
- replay and comparison validation

### `tests/fixtures/`

Owns:

- reusable evidence fixtures
- replay baselines
- synthetic mission inputs that do not depend on hidden runtime state

## Tooling Layout

Canonical root-level tooling files should include:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- any explicit environment example files needed for bootstrap

Tooling-layout rule:

- Python tool configuration should live at root unless a subtool strongly
  requires a different location

## Legacy Isolation Rule

If legacy reference assets remain during reset:

- they must not live inside `src/ez_ax/`
- they must not look like active canonical runtime packages
- they should be clearly archived or labeled as reference-only

## Bootstrap Order

When building from zero code assets, create in this order:

1. root Python tooling files
2. `src/ez_ax/` package root
3. `models/`
4. `graph/`
5. `missions/`
6. `adapters/`
7. `evidence/`
8. `validation/`
9. `rag/`
10. `reporting/`
11. `tests/`

Bootstrap-order rule:

- bootstrap should create structure before implementation depth

## Completeness

This layout PRD is complete only when:

- a future agent can create the Python repository shape without guessing
- ownership boundaries are reflected in package boundaries
- test locations are explicit
- tooling file locations are explicit
- legacy and canonical assets cannot be confused by layout alone

## Immediate Next Action

The next document to write after this PRD is:

- `docs/product/prd-langchain-tooling-policy.md`

Reason:

- once package boundaries are explicit, the next highest-value task is to fix
  what LangChain may and may not own inside that layout
