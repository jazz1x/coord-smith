# PRD — Low-Attention Implementation Queue

## Purpose

This PRD defines the approved low-attention implementation queue for
lower-capacity autonomous agents working below the released ceiling
`pageReadyObserved`.

It exists so an agent can determine, without guesswork:

- which released-scope file groups are still approved for continued hardening
- what the first validation command is for each file group
- which PRD to scan first for an exact contract gap
- when to implement a one-commit slice versus advance to the next queue item
- when the queue is honestly exhausted

This PRD is subordinate to:

1. [`prd-e2e-orchestration.md`](./prd-e2e-orchestration.md)
2. [`prd-python-langgraph-runtime.md`](./prd-python-langgraph-runtime.md)
3. [`prd-python-runtime-layout.md`](./prd-python-runtime-layout.md)
4. [`prd-python-validation-contract.md`](./prd-python-validation-contract.md)
5. [`prd-python-rag-operations.md`](./prd-python-rag-operations.md)

Precedence rule:

- if this queue would authorize work above `pageReadyObserved`, the benchmark
  PRD wins and this queue is invalid
- if this queue conflicts with a more specific PRD for a file group, the more
  specific PRD wins

## Scope

This queue covers only released-scope or released-scope-adjacent Python-first
surfaces whose hardening can still improve deterministic work below
`pageReadyObserved`.

Allowed surfaces:

- released-scope graph sequencing and call sites
- released-scope run-root and input resolution
- released-scope MCP/OpenClaw adapter and CLI/config entry surfaces
- released-scope reporting or summary surfaces that do not imply modeled-stage
  workflow release

Disallowed surfaces:

- any modeled mission above `pageReadyObserved`
- broad repo-wide cleanup
- arbitrary third-tier search expansion not explicitly documented here

## Queue Execution Rule

For each queue item, the lower-capacity agent must:

1. run the `first_validation` command
2. if it fails, implement exactly one smallest safe one-commit fix in the named
   file group
3. if it passes, run focused `mypy` for the same file group
4. if focused `mypy` passes, run focused `ruff check` for the same file group
5. if all focused validation passes, scan the `first_prd` for one exact
   unenforced clause tied to that file group
6. if no exact gap is found honestly, move to `next_if_clean`

Queue rule:

- each queue item is one autonomous search surface, not a bundle of related
  refactors
- the agent must not skip ahead unless the current queue item reaches its
  `next_if_clean` condition honestly
- after the documented queue is exhausted, the agent may run exactly one
  canonical queue-extension heuristic pass before accepting final stop

## Queue Items

### Item 1 — Released MCP Stdio CLI Inputs

- `file_group`: `src/ez_ax/config/mcp_stdio_cli.py`
- `tests`: `tests/unit/test_modeled_mcp_entrypoint_argv.py`
- `first_prd`: `docs/product/prd-python-mcp-client-acquisition.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_modeled_mcp_entrypoint_argv.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced clause remains in the MCP acquisition PRD for this file
    group without guesswork
- `next_if_clean`: Item 2
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/config/mcp_stdio_cli.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface resolves released-scope MCP constructor inputs only
- it does not release modeled-stage workflow behavior

### Item 2 — Released Graph Assembly Entrypoint

- `file_group`: `src/ez_ax/graph/langgraph_released.py`
- `tests`: `tests/unit/test_released_entrypoint.py`
- `first_prd`: `docs/product/prd-python-langgraph-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_entrypoint.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope clause remains for graph assembly without
    guesswork
- `next_if_clean`: Item 3
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/graph/langgraph_released.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface assembles released-scope graph behavior only
- it remains below `pageReadyObserved`

### Item 3 — Released CLI Shim

- `file_group`: `src/ez_ax/graph/released_cli_shim.py`
- `tests`: `tests/unit/test_released_cli_shim.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_cli_shim.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope CLI clause remains without guesswork
- `next_if_clean`: Item 4
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/graph/released_cli_shim.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface is only a released-scope invocation shim
- it does not widen workflow authority

### Item 4 — Released Input Resolution

- `file_group`: `src/ez_ax/config/released_inputs.py`
- `tests`: `tests/unit/test_released_inputs.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_inputs.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope input-resolution clause remains without
    guesswork
- `next_if_clean`: Item 5
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/config/released_inputs.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface only resolves released-scope inputs for attach / prepare / page
  readiness entry surfaces
- it does not widen the released ceiling

### Item 5 — Released-Scope Reporting Summary

- `file_group`: `src/ez_ax/reporting/summary.py`
- `tests`: `tests/unit/test_transition_reporting.py`
- `first_prd`: `docs/product/prd-e2e-orchestration.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_transition_reporting.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope reporting clause remains without
    guesswork
- `next_if_clean`: Item 6
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/reporting/summary.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface summarizes released-scope transitions and diagnostics only
- it does not imply modeled-stage release

### Item 6 — Released-Scope Entrypoint Wrapper

- `file_group`: `src/ez_ax/graph/released_entrypoint.py`
- `tests`: `tests/unit/test_released_entrypoint.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_entrypoint.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope entrypoint clause remains without
    guesswork
- `next_if_clean`: Item 7
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/graph/released_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface wraps the already-approved released execution sequence only
- it stays below `pageReadyObserved`
- it does not introduce modeled-stage workflow behavior

### Item 7 — Released-Scope Checkpoint Comparability

- `file_group`: `src/ez_ax/models/checkpoint.py`
- `tests`: `tests/unit/test_transition_checkpoint_collection.py`
- `first_prd`: `docs/product/prd-e2e-orchestration.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_transition_checkpoint_collection.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released-scope checkpoint-comparability clause remains
    without guesswork
- `next_if_clean`: Item 8
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/models/checkpoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface preserves released-scope checkpoint coherence and comparability
  only
- it does not widen execution beyond `pageReadyObserved`

### Item 8 — Layered Entrypoint Bootstrap Assets

- `file_group`: `src/ez_ax/validation/bootstrap.py`
- `tests`: `tests/unit/test_bootstrap_assets.py`
- `first_prd`: `AGENTS.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_bootstrap_assets.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced bootstrap-asset clause remains for the official layered
    doc entrypoint without guesswork
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/validation/bootstrap.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens the official layered-doc bootstrap entrypoint for
  lower-capacity continuation
- it does not widen execution above `pageReadyObserved`
- it preserves autonomous implementation safety without changing product
  architecture

### Item 9 — Released Evidence Envelope

- `file_group`: `src/ez_ax/evidence/envelope.py`
- `tests`: `tests/unit/test_evidence_envelope.py`
- `first_prd`: `docs/product/prd-openclaw-evidence-model.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_evidence_envelope.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced evidence-envelope clause remains without guesswork
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/evidence/envelope.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface normalizes released-scope evidence refs and kinds only
- it stays below `pageReadyObserved`
- it preserves the typed evidence contract without releasing modeled behavior

### Item 10 — Released OpenClaw Adapter Boundary

- `file_group`: `src/ez_ax/adapters/openclaw/client.py`
- `tests`: `tests/unit/test_openclaw_adapter_contract.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_adapter_contract.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced OpenClaw adapter clause remains without guesswork
- `next_if_clean`: Item 11
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/adapters/openclaw/client.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface validates released-scope OpenClaw request/response boundaries only
- it stays below `pageReadyObserved`
- it does not imply modeled-stage workflow behavior

### Item 11 — Bootstrap AutoLoop Entry Skill Asset

- `file_group`: `src/ez_ax/validation/bootstrap.py`
- `tests`: `tests/unit/test_bootstrap_assets.py`
- `first_prd`: `docs/execution-model.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_bootstrap_assets.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced bootstrap-asset clause remains for the continuous
    low-attention entry skill without guesswork
- `next_if_clean`: Item 12
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/validation/bootstrap.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens bootstrap continuity for lower-capacity autonomous
  looping under the released ceiling
- it stays below `pageReadyObserved`
- it does not widen browser-facing or modeled-stage behavior

### Item 12 — Released Call-Site Determinism

- `file_group`: `src/ez_ax/graph/released_call_site.py`
- `tests`: `tests/unit/test_released_call_site.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_call_site.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released call-site clause remains without guesswork
- `next_if_clean`: Item 13
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/graph/released_call_site.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-scope orchestration call-site boundaries only
- it remains below `pageReadyObserved`

### Item 13 — Released Run-Root Determinism

- `file_group`: `src/ez_ax/graph/released_run_root.py`
- `tests`: `tests/unit/test_released_run_root.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_run_root.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released run-root clause remains without guesswork
- `next_if_clean`: Item 14
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/graph/released_run_root.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-scope run-root handling only
- it remains below `pageReadyObserved`

### Item 14 — Released Execution Sequencing

- `file_group`: `src/ez_ax/graph/langgraph_released_execution.py`
- `tests`: `tests/unit/test_langgraph_released_execution.py`
- `first_prd`: `docs/product/prd-python-langgraph-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_langgraph_released_execution.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released execution sequencing clause remains without
    guesswork
- `next_if_clean`: Item 15
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/langgraph_released_execution.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-path sequencing only
- it remains below `pageReadyObserved`

### Item 15 — Released Action-Log Wrapper Contract

- `file_group`: `src/ez_ax/adapters/openclaw/execution.py`
- `tests`: `tests/unit/test_openclaw_execution_wrapper.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_execution_wrapper.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released action-log wrapper clause remains without
    guesswork
- `next_if_clean`: Item 16
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/adapters/openclaw/execution.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released evidence/action-log validation only
- it remains below `pageReadyObserved`

### Item 16 — Released MCP Response Envelope Contract

- `file_group`: `src/ez_ax/adapters/openclaw/mcp_adapter.py`
- `tests`: `tests/unit/test_openclaw_mcp_adapter.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_adapter.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released MCP response-envelope clause remains without
    guesswork
- `next_if_clean`: Item 17
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/adapters/openclaw/mcp_adapter.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released MCP response validation boundaries only
- it remains below `pageReadyObserved`

### Item 17 — Released MCP Stdio Acquisition Contract

- `file_group`: `src/ez_ax/adapters/openclaw/mcp_stdio_client.py`
- `tests`: `tests/unit/test_openclaw_mcp_stdio_client.py`
- `first_prd`: `docs/product/prd-python-mcp-client-acquisition.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_stdio_client.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released MCP stdio acquisition clause remains without
    guesswork
- `next_if_clean`: Item 18
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/adapters/openclaw/mcp_stdio_client.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released MCP acquisition boundaries only
- it remains below `pageReadyObserved`
- it does not release modeled-stage workflow behavior

### Item 18 — Released Entrypoint Signature Contract

- `file_group`: `src/ez_ax/graph/released_entrypoint.py`
- `tests`: `tests/unit/test_released_entrypoint.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_released_entrypoint.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced released entrypoint signature clause remains without
    guesswork
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/released_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-scope entrypoint contract determinism only
- it remains below `pageReadyObserved`
- it does not widen browser-facing or modeled-stage behavior

## Final Queue Stop

The documented low-attention implementation queue is exhausted only when:

- every documented queue item reached `done_when` honestly, and
- no exact unenforced clause remains without guesswork for any documented queue
  item

Exhaustion protocol gate order:

1. run exactly one bounded resume-search pass below `pageReadyObserved`
2. run exactly one queue-extension heuristic pass for the exhaustion cycle
3. run one final exact gap re-evaluation pass

Queue-extension heuristic gate:

- after the documented queue is exhausted, lower-capacity autonomous
  implementation may perform exactly one canonical queue-extension heuristic
  pass
  for that exhaustion cycle
- that pass may add at most one new queue item
- the new queue item must come from a released-scope support surface already
  described by an exact `must` clause in the governing PRD set
- the new queue item must remain one-task-per-commit safe
- if the heuristic pass yields no valid candidate without guesswork, final stop
  stands honestly

Heuristic candidate catalog:

- the queue-extension heuristic pass may draw only from this catalog:
  - `src/ez_ax/graph/released_call_site.py`
  - `src/ez_ax/graph/released_run_root.py`
  - `src/ez_ax/graph/langgraph_released_execution.py`
  - `src/ez_ax/adapters/openclaw/execution.py`
  - `src/ez_ax/adapters/openclaw/mcp_adapter.py`
  - `src/ez_ax/adapters/openclaw/mcp_stdio_client.py`
- catalog use is deterministic and bounded; ad hoc tertiary discovery remains
  disallowed

Cycle-reset rule:

- if the heuristic pass adds one valid queue item and that queue item later
  closes honestly with validation, `work-rag` update, and commit, the next
  queue exhaustion starts a new exhaustion cycle
- each new honest exhaustion cycle reopens exactly one canonical queue-
  extension heuristic pass

Final-stop rule:

- after this queue is exhausted and the exhaustion protocol gate order is also
  exhausted, lower-capacity autonomous implementation must stop
- reopening autonomous implementation requires either:
  - one new explicit in-bounds contract gap, or
  - one explicit PRD update that extends this implementation queue
