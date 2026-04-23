# AGENTS

Codex and other repository agents should use this file as the operational entrypoint.

## Bootstrap Preflight

Before reading the layered entrypoints, fresh checkouts must run:

1. `uv sync --extra dev`  — installs runtime + dev deps declared in `pyproject.toml`
2. `uv run pytest -q`     — expected: 744 passed, 1 skipped

If pytest collection fails with `ModuleNotFoundError: PIL|pyautogui`, step 1 did not complete.

## Primary Entrypoint

All agents must begin with the layered document system in this exact order:

1. [docs/prd.md](docs/prd.md)
2. [docs/core-loop.md](docs/core-loop.md) (quick reference — read this first)
3. [docs/current-state.md](docs/current-state.md)

For detailed rules on exhaustion protocols, continuation seeding, and stop
decisions, read [docs/execution-model.md](docs/execution-model.md) only when
the current task involves queue exhaustion or stop decisions.

Meaning of the layers:

- PRD defines invariant system truth
- Core Loop defines the minimal operating reference for autonomous work
- Current State defines where work currently continues

Entrypoint rule:

- agents must use the layered documents above as the primary entrypoint
- legacy product documents under `docs/product/` remain reference material and
  supporting source documents
- agents must not use legacy documents as the primary entrypoint when the
  layered docs already cover boundary, operating method, and current state

## Priority Order

1. Follow repository-specific instructions in this file.
2. Follow the layered entrypoint documents in this order:
   - [docs/prd.md](docs/prd.md)
   - [docs/execution-model.md](docs/execution-model.md)
   - [docs/current-state.md](docs/current-state.md)
3. Follow [docs/product/prd-e2e-orchestration.md](docs/product/prd-e2e-orchestration.md) as a legacy reference product and autonomous-work contract beneath the layered entrypoint.
4. Follow the Python-first runtime PRD set when the task concerns canonical runtime architecture:
   - [docs/product/prd-python-langgraph-runtime.md](docs/product/prd-python-langgraph-runtime.md)
   - [docs/product/prd-python-runtime-reset.md](docs/product/prd-python-runtime-reset.md)
   - [docs/product/prd-runtime-missions.md](docs/product/prd-runtime-missions.md)
   - [docs/product/prd-langgraph-state-model.md](docs/product/prd-langgraph-state-model.md)
   - [docs/product/prd-python-runtime-layout.md](docs/product/prd-python-runtime-layout.md)
   - [docs/product/prd-low-attention-implementation-queue.md](docs/product/prd-low-attention-implementation-queue.md)
   - [docs/product/prd-langchain-tooling-policy.md](docs/product/prd-langchain-tooling-policy.md)
   - [docs/product/prd-python-validation-contract.md](docs/product/prd-python-validation-contract.md)
   - [docs/product/prd-python-rag-operations.md](docs/product/prd-python-rag-operations.md)
5. Follow the OpenClaw evidence and E2E PRDs when the task concerns hybrid evidence or execution validation:
   - [docs/product/prd-openclaw-evidence-model.md](docs/product/prd-openclaw-evidence-model.md)
   - [docs/product/prd-openclaw-e2e-validation.md](docs/product/prd-openclaw-e2e-validation.md)
6. Follow the remaining repository base configuration files such as `pyproject.toml`, `.pre-commit-config.yaml`, and `.gitignore`.
7. For Python code writing, review, or refactoring, follow `.claude/python-engineering.md` unless it conflicts with higher-priority repository sources.
8. Housekeeping direction (ceiling integrity, FINAL_STOP semantics, bootstrap): [docs/prd-direction-realignment.md](docs/prd-direction-realignment.md) and its runbook [docs/prd-direction-realignment-impl.md](docs/prd-direction-realignment-impl.md).

## Current Repository State

This repository currently centers on a Python-first documentation-led bootstrap model:

- `AGENTS.md`
- the benchmark PRD
- the Python-first runtime PRD set
- the OpenClaw evidence and E2E PRDs
- `work-rag.json`
- `rag.json`
- `pyproject.toml`
- `.pre-commit-config.yaml`
- `src/ez_ax/` Python scaffold
- `tests/` Python scaffold

Legacy runtime code status:

- legacy TypeScript runtime code has been removed from the active repository
- active runtime work should extend the Python scaffold rather than recreate any
  removed TypeScript structure

Legacy non-regression policy:

- do not recreate `package.json`, `bun.lock`, `tsconfig.json`, or `biome.json`
  as active canonical toolchain files
- do not add new TypeScript runtime source under `src/` or any alternate
  TypeScript package root
- do not add Bun-based runtime validation as the canonical path
- do not reintroduce deleted TypeScript contracts as active implementation
  dependencies
- if a historical TypeScript artifact must exist for reference, it must be
  clearly archived outside the active Python runtime path and must not be
  presented as canonical

Operational rule:

- do not assume that removed source files, tests, scripts, or auxiliary documents still exist
- do not reference deleted documentation as if it were still part of the active repository state
- future work must be derived from the active PRD set, the two RAG files, and the remaining base configuration
- if the repository contains no active runtime code, do not recreate legacy
  TypeScript structure as a convenience path
- if a proposed change would restore the removed TypeScript execution path, stop
  and treat it as a policy violation unless the PRD explicitly changes

## Agent Expectations

- Keep `OpenClaw` as the only browser-facing execution actor.
- Keep `ez-ax` orchestration-centric.
- Prefer event-based waits over sleep-based timing.
- Prefer typed evidence over intuition.
- Do not introduce anti-detection logic.
- Do not describe modeled behavior as released behavior.
- Before starting work, identify the current phase, milestone, anchor, and stop condition from the PRD.
- Do not change anything above the current approved anchor unless the PRD explicitly allows it.
- Use relevant available skills actively when they fit the current task.
- If a self-RAG, testing, validation, or documentation-structure skill is available for the session, prefer using it.
- At the start of meaningful work, briefly state which skill is being used and why.
- Skills are execution aids, not scope authority. If a skill conflicts with the PRD, follow the PRD.

## Working Rules

When starting or reporting work, explicitly state:

- phase
- milestone
- anchor
- invariant
- next action

When the PRD and any remembered prior repository state differ:

- follow the PRD
- follow the currently existing files in the repository
- ignore deleted or historical project structure

Low-attention reading rule:

- always read `AGENTS.md`, `docs/prd.md`, `docs/core-loop.md`,
  `docs/current-state.md`, `docs/product/work-rag.json`, and
  `docs/product/rag.json`
- read `docs/execution-model.md` only when the current task involves queue
  exhaustion or stop decisions
- read runtime, state-model, validation, layout, mission, and OpenClaw PRDs only
  when the current task touches those domains

Autonomous task completion rule:

- each autonomous task must end with applicable validation, required RAG updates, and a git commit before the next autonomous task begins
- if a task cannot be validated or committed honestly, it must not be reported as fully complete

Task-close compression rule:

- every autonomous task close must update `work-rag.json` current state and add
  exactly one new checkpoint or summary entry when meaningful work occurred
- if more than three entries accumulate in `work-rag.json` history for the
  active phase-milestone pair, compress the oldest same-scope entries into one
  milestone summary and keep only the latest two raw checkpoints
- prefer keeping at most the latest two raw checkpoints for the active
  phase-milestone pair unless an older checkpoint is uniquely required for safe
  continuation
- promote only reusable lessons into `rag.json`; transient step logs must stay
  out of durable lesson memory

## Source Of Truth

- Primary layered source of truth:
  [docs/prd.md](docs/prd.md)
  [docs/execution-model.md](docs/execution-model.md)
  [docs/current-state.md](docs/current-state.md)
- Legacy benchmark reference beneath the layered entrypoint:
  [docs/product/prd-e2e-orchestration.md](docs/product/prd-e2e-orchestration.md)
- Canonical Python-first runtime architecture source of truth when implementation planning or reset work is in scope:
  [docs/product/prd-python-langgraph-runtime.md](docs/product/prd-python-langgraph-runtime.md)
  [docs/product/prd-python-runtime-reset.md](docs/product/prd-python-runtime-reset.md)
  [docs/product/prd-runtime-missions.md](docs/product/prd-runtime-missions.md)
  [docs/product/prd-langgraph-state-model.md](docs/product/prd-langgraph-state-model.md)
  [docs/product/prd-python-runtime-layout.md](docs/product/prd-python-runtime-layout.md)
  [docs/product/prd-langchain-tooling-policy.md](docs/product/prd-langchain-tooling-policy.md)
  [docs/product/prd-python-validation-contract.md](docs/product/prd-python-validation-contract.md)
  [docs/product/prd-python-rag-operations.md](docs/product/prd-python-rag-operations.md)
- OpenClaw evidence and execution validation source of truth:
  [docs/product/prd-openclaw-evidence-model.md](docs/product/prd-openclaw-evidence-model.md)
  [docs/product/prd-openclaw-e2e-validation.md](docs/product/prd-openclaw-e2e-validation.md)

## RAG Discipline

- Keep [`docs/product/work-rag.json`](docs/product/work-rag.json) as the canonical current-tense work record.
- Keep [`docs/product/rag.json`](docs/product/rag.json) as the durable lesson and trial-and-error record.
- Update `work-rag.json` during meaningful work whenever goal, phase, milestone, anchor, invariant, or next action changes.
- Compress `work-rag.json` at milestone completion and again at phase completion.
- Promote reusable mistakes, flaky patterns, false assumptions, and boundary-confusion lessons into `rag.json`.
- When reading `rag.json`, prioritize lessons tagged for the active Python-first implementation path before historical cutover or reset lessons.
- When promoting a new lesson, tag it so a future agent can tell whether it is for active implementation work or historical transition context.
- Do not use `rag.json` as a duplicate step log.
- If the PRD set and the two RAG files are not sufficient for safe autonomous continuation, improve the docs before widening implementation work.

## Guardrail

Planned or modeled features must not be presented as implemented or released.

Legacy cutover guardrail:

- the active canonical implementation path is Python-only
- reintroducing legacy TypeScript runtime or Bun-first execution as an active
  path is forbidden unless the PRD set is explicitly rewritten first
