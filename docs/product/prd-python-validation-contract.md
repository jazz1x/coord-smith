# PRD — Python Validation Contract

## Purpose

This PRD defines the canonical validation contract for the Python-first runtime.

It exists so an autonomous agent can determine:

- which validation tools are canonical
- when unit, contract, or E2E validation is required
- what pre-commit should enforce
- how flaky behavior is interpreted
- how release-gate evidence is preserved

This PRD should be read beneath:

1. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
2. [`prd-runtime-missions.md`](./prd-runtime-missions.md)
3. [`prd-langgraph-state-model.md`](./prd-langgraph-state-model.md)
4. [`prd-python-runtime-layout.md`](./prd-python-runtime-layout.md)
5. [`docs/product/prd-openclaw-e2e-validation.md`](./prd-openclaw-e2e-validation.md)
6. [`docs/product/prd-openclaw-evidence-model.md`](./prd-openclaw-evidence-model.md)

Precedence rule:

- if a validation rule in this PRD conflicts with benchmark release limits, the
  benchmark PRD wins
- if a validation rule in this PRD conflicts with the existing OpenClaw E2E
  contract, the stricter rule wins until explicitly revised

## Canonical Validation Stack

The canonical validation stack is:

- `ruff check`
- `ruff format --check`
- `mypy`
- `pytest`
- `pytest-asyncio`
- Playwright Python for E2E
- `pre-commit`

Validation-stack rule:

- once Python runtime implementation begins, this is the stack that defines a
  trustworthy task closure

## Transitional Rule

During reset and before Python runtime code exists:

- legacy repository validation may still run as a transitional integrity check
- transitional validation does not redefine the canonical Python validation
  stack

Transitional rule:

- transition-era checks may confirm the repo is not broken, but they do not
  replace the Python validation contract

## Validation Levels

The runtime recognizes:

- unit validation
- contract validation
- E2E validation
- release-gate validation

Validation-level rule:

- every task should run the smallest trustworthy validation set for its scope

## Unit Validation

Use unit validation for:

- pure helpers
- parsing logic
- shaping logic
- deterministic transformations

Expected tools:

- `pytest`

Unit-validation rule:

- unit tests should not require browser execution or hidden environment state

## Contract Validation

Use contract validation for:

- mission inputs and outputs
- graph transition rules
- evidence envelopes
- stop-reason models
- artifact bundle shapes

Expected tools:

- `pytest`
- `pytest-asyncio` when async boundaries exist
- `mypy` when type guarantees are part of the contract

Contract-validation rule:

- contract tests should fail loudly when ownership boundaries blur

## E2E Validation

Use E2E validation for:

- released-path execution
- OpenClaw execution plus Playwright verification
- artifact comparison and replay confidence

Expected tools:

- `pytest`
- Playwright Python

E2E-validation rule:

- the initial release-grade E2E focus remains the released path through
  `pageReadyObserved`

## Release-Gate Validation

Release-gate validation must consider:

- required tests passed
- required artifacts were produced
- typed stop reasons remain attributable
- flaky budget was not exceeded
- released and modeled behavior were not conflated

Release-gate rule:

- passing tests alone is not enough for a release-grade claim
- release-ceiling claims require typed artifact verification: if a release-ceiling action-log artifact (`artifacts/action-log/release-ceiling-stop.jsonl`) is referenced, release-gate validation must confirm it exists, mention the typed fields it must contain (`event`, `mission_name`, `ts`), and record a typed failure pointing at the missing artifact before a ceiling claim can proceed. Cross-reference [`docs/product/prd-openclaw-e2e-validation.md`](./prd-openclaw-e2e-validation.md) for the released ceiling bundle, [`docs/product/prd-openclaw-computer-use-runtime.md`](./prd-openclaw-computer-use-runtime.md) for the typed artifact schema, [`docs/product/prd-openclaw-evidence-model.md`](./prd-openclaw-evidence-model.md) for the release-ceiling evidence semantics, and the validation contract itself so the release-gate bundle restates the full determinism chain.

## Pre-Commit Contract

`pre-commit` should enforce the fastest trustworthy subset of:

- formatting checks
- lint checks
- type checks where affordable
- fast unit or contract tests where affordable

Pre-commit rule:

- pre-commit should catch obvious breakage early without becoming a full E2E
  substitute

## Flaky Policy

Flaky behavior must be treated as evidence, not annoyance.

When flakiness appears:

- preserve the failed artifact or summary
- record the pattern in `rag.json` when reusable
- avoid silently normalizing repeated uncertain outcomes

Flaky-policy rule:

- repeated unexplained flakiness blocks honest release claims

## Artifact Preservation

Validation should preserve or reference:

- test output
- type-check output
- lint output
- E2E report output
- comparable runtime artifacts when relevant

Artifact-preservation rule:

- a validation claim should remain inspectable by a future agent

## Minimum Trustworthy Validation By Change Type

Docs-only PRD or RAG changes:

- validate affected structured files
- run the lightest repository integrity check that remains honest

Docs-only command examples:

- `python3 -m json.tool docs/product/work-rag.json > /tmp/work-rag.json.check`
- `python3 -m json.tool docs/product/rag.json > /tmp/rag.json.check`
- `git diff --check`

Pure Python helper changes:

- unit tests
- lint and type checks for affected scope

Mission, graph, evidence, or artifact changes:

- contract tests
- affected unit tests
- type checks

Released-path execution changes:

- contract tests
- affected unit tests
- relevant E2E validation
- release-gate review where applicable

Change-type rule:

- if a task skips expected validation, the skip reason must be explicit and
  preserved

## Low-Attention Validation Floor

Lower-capacity autonomous agents must choose validation using the following
floor rules:

- docs-only change:
  validate every changed structured artifact and run `git diff --check`
- test-only change:
  run the changed test target directly
- Python behavior or contract change:
  run at least one focused test plus the narrowest applicable lint or type check
- mixed change touching docs and Python behavior:
  treat it as a Python behavior change, not as docs-only work

Validation-floor rule:

- a lower-capacity agent may broaden validation beyond this floor, but may not
  go below it
- if even the validation floor cannot be run honestly, the task must stop

## Paused-State Validation Search Order

When autonomous work is in a clean paused state and needs one bounded
resume-search pass, validation discovery must prefer the narrowest attributable
signal first.

Required search order:

1. rerun or identify one focused `pytest` target tied to the active anchor
2. if no focused test failure exists, run or identify one focused `mypy` target
   for the active file group when typing is part of the contract
3. if no focused type failure exists, run or identify one focused `ruff check`
   target for the active file group
4. only if all focused validation surfaces are clean may the agent switch to
   finding one exact unenforced PRD clause

Paused-state validation rule:

- repo-wide validation sweeps are not the default paused-state search method for
  lower-capacity agents
- broad cleanup work discovered from repo-wide `ruff` or `pytest` runs must not
  displace a smaller attributable contract slice
- the chosen validation artifact must be small enough to anchor one honest
  follow-on commit

## Stop Conditions

Stop when:

- no honest validation path exists for the current claim
- required artifacts are missing
- flaky behavior prevents an attributable conclusion

## Completeness

This validation contract is complete only when:

- a future agent knows which Python tools are canonical
- pre-commit expectations are explicit
- unit, contract, E2E, and release-gate roles are distinct
- validation can be chosen without guessing

## Immediate Next Action

The next document to write after this PRD is:

- `docs/product/prd-python-rag-operations.md`

Reason:

- once validation closure is explicit, the next highest-value task is to define
  how durable work memory and lesson promotion operate during Python-first
  implementation
