# PRD — OpenClaw E2E Validation

## Purpose

This PRD defines how the `OpenClaw` computer-use runtime is validated through
E2E execution.

## North Star

Validate not only that a run can execute, but that it can be judged, repeated,
and compared with bounded ambiguity.

## Validation Goals

E2E validation must prove:

- actor boundaries are preserved
- evidence aggregation is working
- fallback behavior is explicit
- flaky behavior is observable rather than hidden
- release decisions are grounded in artifacts

## E2E Test Philosophy

The E2E suite should test:

- released-path computer-use observation
- artifact comparability
- deterministic stop and retry behavior
- ambiguity handling
- fallback invocation when primary evidence is insufficient

The E2E suite should not:

- claim release above the current approved workflow ceiling
- confuse a successful click with a trustworthy success classification
- bury flaky runs by treating all retries as green

## Release Gate

Release gate questions:

- did the run stop at the correct boundary?
- was the decision made from acceptable evidence?
- are the artifacts comparable to previous runs?
- were fallback paths bounded and justified?
- are failures diagnosable enough to improve the system?

The release gate is passed only when:

- required evidence exists
- ambiguity is handled explicitly
- stop reasons are typed
- repeated-run artifacts remain comparable enough for review

## Flaky-Budget Policy

The system must explicitly track:

- repeated observation drift
- screenshot-only classifications
- coordinate-dependent actions
- retry frequency
- inconsistent stop reasons across equivalent runs

Policy:

- flakiness is not just a test failure; it is evidence for `rag.json`
- repeated flaky patterns must be promoted into durable lessons

## Required Artifacts

Each E2E validation run should preserve:

- run summary
- checkpoints
- evidence references
- fallback usage markers
- stop reason
- comparison notes versus a prior run when available

## Released Ceiling Stop Validation (Released Scope)

In released scope, the system must stop intentionally at the current approved
ceiling (`runCompletion`) and prove that stop deterministically from
artifacts. (The ceiling was expanded from `pageReadyObserved` to
`runCompletion` on 2026-03-26 — see `docs/prd.md`.)

Goal:

- a reviewer (or validator) can confirm the run stopped intentionally at the
  ceiling boundary without inferring behavior from the absence of later stages

Minimum deterministic validation bundle (released scope):

1. Evidence ref presence (ceiling stop marker):
   - the run MUST include `evidence://action-log/release-ceiling-stop` in the
     `page_ready_observation` execution result evidence refs
2. Evidence ref schema and mission minimums:
   - evidence refs MUST pass released-scope schema validation
   - `page_ready_observation` MUST satisfy the released-scope per-mission
     minimum evidence keys defined in
    [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
3. Action-log artifact resolvability:
   - using the released-scope action-log storage semantics, the validator MUST
     be able to resolve `evidence://action-log/release-ceiling-stop` to a
     concrete artifact file under the run root:
     - `artifacts/action-log/release-ceiling-stop.jsonl`
- if the artifact cannot be read, the validator must record a typed failure
  including the artifact path, the expected fields (`event`, `mission_name`,
  `ts`), and references to `docs/product/prd-openclaw-e2e-validation.md`,
  `docs/product/prd-openclaw-computer-use-runtime.md`, `docs/product/prd-openclaw-evidence-model.md`,
  and `docs/product/prd-python-validation-contract.md` before asserting the ceiling stop,
  ensuring downstream docs and lessons can replay the missing artifact
  scenario with full typed context
  - crosswalk rule: any mission-level stop validation discussion for
    `page_ready_observation` within this doc must always restate the release-
    ceiling artifact path (`artifacts/action-log/release-ceiling-stop.jsonl`),
    the typed fields required (`event`, `mission_name`, `ts`), and every linked
    release-ceiling PRD (`docs/product/prd-openclaw-evidence-model.md`,
    `docs/product/prd-openclaw-computer-use-runtime.md`,
    `docs/product/prd-openclaw-e2e-validation.md`,
    `docs/product/prd-python-validation-contract.md`) so the mission narrative
    stays explicitly tied to the determinism chain when OpenClaw reports the
    ceiling stop.
   - if the artifact file cannot be opened, the validator must record a typed
     failure referencing the missing file before concluding the ceiling stop
     was observed
4. Action-log content confirmation:
   - the resolved artifact MUST contain at least one JSON line whose fields
     confirm an intentional ceiling stop:
     - `event` is `release-ceiling-stop`
     - `mission_name` is `page_ready_observation`
     - `ts` is present as an ISO-8601 timestamp string

Scope rule:

- this validation bundle MUST NOT require any modeled post-ceiling action
  (dispatch/click/success classification) to be present or absent; the released
  ceiling is judged from explicit stop evidence only

## Completion

E2E validation is complete when:

- release gate status can be determined without operator intuition
- flaky behavior is visible and classifiable
- lessons from unstable runs can be promoted into `rag.json`
- milestone or phase summaries can be compressed into `work-rag.json`

## Source Of Truth

- parent runtime PRD:
  [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md)
- evidence model:
  [`docs/product/prd-openclaw-evidence-model.md`](./prd-openclaw-evidence-model.md)
