# PRD — OpenClaw Hybrid Evidence Model

## Purpose

This PRD defines what counts as trustworthy runtime evidence in the
`OpenClaw` computer-use architecture.

## North Star

Use hybrid evidence to maximize determinism without sacrificing real
computer-use robustness.

## Evidence Classes

### Primary Typed Signals

- DOM state
- extracted text
- clock or timing signals
- action logs

Primary rule:

- these should decide state whenever they are available and trustworthy

Primary evidence checklist:

- prefer typed signals when they are present, coherent, and time-stamped
- require fallback evidence to reference the missing or contradictory typed
  signal it is compensating for
- record a typed ambiguity if primary signals disagree before falling back

### Supporting Or Fallback Signals

- screenshot evidence
- vision-model classification tied to a concrete screenshot

Fallback rule:

- use screenshot or vision when primary typed signals are missing, partial, or
  contradictory
- screenshot evidence must remain linked to the step, timestamp, and stop-reason
  candidate it supports

Fallback evidence checklist:

- confirm the primary typed signal gap is explicit (missing, partial, or conflict)
- attach the screenshot or vision classification to the exact step and timestamp
- do not treat fallback evidence as release-grade truth without a typed reason

### Last-Resort Execution Primitives

- coordinates
- screen-relative click targets

Last-resort rule:

- coordinates may execute an action only after a deterministic target has
  already been established
- coordinates do not prove truth about application state by themselves

Last-resort checklist:

- ensure a deterministic target exists before coordinate use
- require pre-action targeting evidence and post-action observation evidence
- never use coordinates to upgrade a modeled stage into released truth

## Truth Hierarchy

Truth hierarchy:

1. typed signal agreement
2. typed signal plus screenshot corroboration
3. screenshot-based fallback classification
4. coordinate-based execution only after prior targeting confidence

Truth rule:

- lower-priority evidence may support but must not silently override a stronger
  higher-priority signal without a typed reason

## Conflict Handling

When evidence conflicts:

- prefer higher-priority typed evidence
- record the conflicting lower-priority evidence
- emit a typed ambiguity or stop reason if the conflict affects decision quality

Conflict must never be handled by:

- ignoring the conflict
- silently choosing the optimistic branch
- converting uncertainty into success

## Screenshot Policy

Screenshots are valuable because they:

- preserve what the computer-use system actually saw
- provide fallback when structured signals are missing
- improve debugging and later lesson extraction

Screenshots are not sufficient because they:

- can be visually ambiguous
- can drift under layout changes
- may require interpretive classification rather than deterministic parsing

Policy:

- screenshots are mandatory as support when a fallback path is used
- screenshots are optional when primary typed signals are already sufficient

## Coordinate Policy

Coordinates are useful because they:

- can execute a final interaction after target confirmation
- may still work when structured selectors are unavailable

Coordinates are risky because they:

- are layout-sensitive
- are resolution-sensitive
- are poor truth sources

Policy:

- coordinates are allowed as execution primitives
- coordinates are not allowed as release-grade state truth by themselves
- coordinate actions should be accompanied by pre-action targeting evidence and
  post-action observation evidence

## Required Evidence Envelope

Each meaningful runtime step should be able to emit:

- step identifier
- phase, milestone, and anchor
- timestamp
- primary typed signals collected
- screenshots or fallback signals collected
- action attempted
- decision taken
- stop reason or continuation reason

## `evidence_refs` Kind Taxonomy (Released Scope)

In released scope (up to `pageReadyObserved`), `evidence_refs` use the kind
taxonomy defined in
[`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
under "`evidence_refs` Schema (Released Scope)".

Mapping rule:

- evidence kinds must be interpreted consistently with the truth hierarchy in
  this PRD so deterministic validation can judge readiness and ceiling-stop
  without operator intuition

Kind mapping:

- `dom`:
  - primary typed signal
  - strongest truth source when coherent
- `text`:
  - primary typed signal
  - strongest truth source when coherent
- `clock`:
  - primary typed signal
  - used for timing normalization and diagnosable time observations
- `action-log`:
  - primary typed signal
  - used to record navigation, attempted actions, and explicit stop markers
  - release-ceiling resolution: when this signal references
    `evidence://action-log/release-ceiling-stop`, the evidence model must link
    to the release-ceiling bundle (`docs/product/prd-openclaw-e2e-validation.md`) and the
    action-log artifact schema (`docs/product/prd-openclaw-computer-use-runtime.md`) so
    validators can confirm the concrete artifact (`artifacts/action-log/release-ceiling-stop.jsonl`)
    contains typed `event`, `mission_name`, and `ts` fields before treating
    the ceiling as observed
  - release-ceiling mission contract: whenever the orchestrator reports the
    mission `page_ready_observation` as its current anchor, evidence refs and
    validators must reiterate the same crosswalk—artifact path, typed fields,
    and PRDs (`docs/product/prd-openclaw-evidence-model.md`,
    `docs/product/prd-openclaw-computer-use-runtime.md`,
    `docs/product/prd-openclaw-e2e-validation.md`,
    `docs/product/prd-python-validation-contract.md`)—so both wiring and
    normalization remain explicitly attached to the typed determinism chain.
  - failure diagnostics: when the release-ceiling artifact cannot be read,
    parsed, or lacks the expected typed fields, the evidence model should
    surface a typed failure that explicitly references
    `artifacts/action-log/release-ceiling-stop.jsonl`, mentions the expected
    field names (`event`, `mission_name`, `ts`), and links back to
    `docs/product/prd-openclaw-e2e-validation.md`,
    `docs/product/prd-openclaw-computer-use-runtime.md`,
    `docs/product/prd-openclaw-evidence-model.md`, and
    `docs/product/prd-python-validation-contract.md` so future reviewers understand the
    determinism contract without inferring an intentional stop from missing
    artifacts
- `screenshot`:
  - supporting or fallback signal
  - must be accompanied by a typed fallback reason when used as the minimum set
- `coordinate`:
  - last-resort execution primitive
  - never a released-grade truth source by itself

## Completeness

The evidence model is complete when:

- every major step has a declared preferred truth source
- fallback paths are explicit
- conflicts are typed
- screenshot use is bounded
- coordinate use is bounded
- later agents can inspect an artifact and understand why a decision was made

## Source Of Truth

- parent runtime PRD:
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
