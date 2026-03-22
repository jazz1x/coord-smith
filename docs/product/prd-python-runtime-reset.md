# PRD — Python Runtime Reset

## Purpose

This PRD defines how the repository should be reset from the current
documentation-first plus legacy TypeScript scaffold state into a Python-first
canonical implementation path.

It exists so an autonomous agent can determine:

- what must be kept
- what may be archived
- what may be deleted
- what must be created fresh
- what must happen before any major Python implementation begins

## Reset Philosophy

The goal is not to erase learning.

The goal is to:

- keep PRD and RAG assets
- keep reusable lessons
- keep only the minimum legacy scaffold needed for reference during transition
- avoid partial migration where canonical and legacy implementation paths remain
  mixed

Reset rule:

- preserve documentation and durable knowledge
- simplify or archive implementation scaffolding that no longer serves the
  canonical path

## Reset Outcome

After reset, the repository should clearly communicate:

- Python is the canonical runtime language
- LangGraph is the orchestration layer
- LangChain is the model/tool composition layer
- OpenClaw is the only browser-facing actor
- the old TypeScript runtime contracts are reference-only or archived

Non-regression outcome:

- the repository must not silently drift back into a mixed Python and
  TypeScript canonical path
- deleted TypeScript runtime assets must stay deleted unless the PRD set is
  explicitly rewritten

## Keep / Archive / Delete / Create

### Keep

Must keep:

- `AGENTS.md`
- benchmark PRD
- runtime PRDs
- evidence and validation PRDs
- roadmap PRD
- `work-rag.json`
- `rag.json`

Reason:

- these are the source-of-truth assets required for autonomous continuation

### Archive

Should archive or explicitly relabel:

- legacy TypeScript boundary contracts that are no longer canonical
- legacy tests whose value is historical reference rather than active execution

Archive rule:

- if a file is kept only for learning or migration reference, label it as
  legacy or reference-only before new implementation grows around it

### Delete

May delete after explicit reset approval:

- legacy implementation files that create ambiguity about the canonical path
- tooling that only exists to support the old canonical stack

Delete rule:

- do not delete learning assets until their value has been preserved in PRD,
  RAG, or explicit archive structure
- once legacy TypeScript implementation assets are removed from the active path,
  do not recreate them as convenience scaffolding

### Create Fresh

Must create fresh:

- Python package root
- LangGraph runtime layout
- LangChain integration layer
- Python validation and quality configuration
- Python E2E structure
- Python pre-commit strategy

## Pre-Implementation Checklist

Before significant Python implementation work begins, the following must exist:

- main Python runtime PRD
- reset PRD
- mission map PRD
- LangGraph state-model PRD
- Python layout PRD
- LangChain tooling policy PRD
- Python validation PRD

If any item is missing, implementation should prefer PRD completion over code.

## Legacy Reintroduction Prohibition

After the Python-first reset crosses into active bootstrap:

- do not restore `package.json`, `bun.lock`, `tsconfig.json`, or `biome.json`
  as active canonical runtime tooling
- do not add new TypeScript runtime code as part of normal implementation
- do not reframe Bun-based validation as the primary implementation contract
- do not depend on archived TypeScript artifacts from inside active Python code

Prohibition rule:

- any change that revives the removed TypeScript execution path is out of bounds
  unless the PRD set is intentionally revised first

## Reset Phases

### Phase R0 — Reset Contract

Goal:

- define the reset rules and protect knowledge assets

Primary anchor:

- `pythonResetPlanApproved`

Done when:

- this PRD exists
- keep/archive/delete/create rules are explicit

### Phase R1 — Canonical Layout Definition

Goal:

- define the future repository shape before moving files

Primary anchor:

- `pythonLayoutApproved`

Done when:

- package layout and tooling layout are explicit in PRD

### Phase R2 — Legacy Isolation

Goal:

- prevent confusion between canonical and legacy assets

Primary anchor:

- `legacyScaffoldIsolated`

Done when:

- legacy implementation assets are either archived, clearly relabeled, or
  removed from the active path

### Phase R3 — Fresh Python Bootstrap

Goal:

- create the initial canonical Python skeleton

Primary anchor:

- `pythonRuntimeBootstrapCreated`

Done when:

- the repo contains the new canonical Python structure and validation entrypoints

## Completeness

The reset is complete only when:

- a future agent does not have to guess which implementation path is canonical
- the repo no longer invites accidental work on the wrong stack
- PRD and RAG assets survive the transition
- the Python stack can start from a clean and explicit foundation

## Judgment Rules

When a reset decision is ambiguous, prefer:

- completeness over incremental patching
- canonical clarity over mixed-path convenience
- preserving durable lessons over preserving low-value scaffold
- a smaller but cleaner reset over a larger but ambiguous transition

## Stop Conditions

Stop when:

- a proposed deletion would remove information not already preserved in PRD,
  RAG, or archive form
- a proposed keep decision would leave the canonical path ambiguous
- a task would mix new Python runtime code with unlabeled legacy canonical
  claims
- a task would recreate a removed TypeScript runtime path without an explicit
  PRD rewrite

## Immediate Next Action

The next document to write after this PRD is:

- `docs/product/prd-runtime-missions.md`

Reason:

- once the reset boundary is explicit, the next highest-value task is to define
  every runtime mission before layout and implementation begin
