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
- how to seed exactly one next slice before true stop when the phase remains
  active

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
- modeled-only helper entrypoints that still invoke the released sequence and
  stop at `pageReadyObserved` without claiming higher-stage release

Disallowed surfaces:

- any modeled mission above `pageReadyObserved`
- broad repo-wide cleanup
- arbitrary third-tier search expansion not explicitly documented here

## Anchor And Milestone Mapping

This queue is not autonomous authority by itself; it is the concrete execution
projection for the active phase / milestone / anchor.

Active mapping:

- `phase`: `Phase R3 — Fresh Python Bootstrap`
- `milestone`: `Low-attention autonomous continuation remains unambiguous under the Python-first PRD contract`
- `anchor`: `pythonRuntimeBootstrapCreated`

Queue interpretation rule:

- queue items cover only one execution family at a time
- queue exhaustion does not prove milestone completion by itself
- if one required anchor family still lacks a deterministic slice-generation
  path, continuation seeding must run before final stop
- if one required anchor family is still `pending` in the active coverage
  ledger, final stop is invalid

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
  canonical queue-extension heuristic pass before continuation seeding
- after the heuristic pass is exhausted, the agent must run exactly one
  continuation-seeding pass before accepting final stop
- doc-only edits whose only purpose is to restate or align `FINAL_STOP` are not
  valid queue items unless the user explicitly requested stop-state cleanup

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
- `next_if_clean`: Item 19
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/released_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-scope entrypoint contract determinism only
- it remains below `pageReadyObserved`
- it does not widen browser-facing or modeled-stage behavior

### Item 19 — Released MCP Required-Field Schema Violation

- `file_group`: `src/ez_ax/adapters/openclaw/mcp_adapter.py`
- `tests`: `tests/unit/test_openclaw_mcp_adapter.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_adapter.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced required-field schema-violation clause remains without
    guesswork
- `next_if_clean`: Item 20
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/adapters/openclaw/mcp_adapter.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released MCP response schema enforcement only
- it remains below `pageReadyObserved`
- it does not widen browser-facing or modeled-stage behavior

### Item 20 — Canonical RAG Path Helpers

- `file_group`: `src/ez_ax/rag/paths.py`
- `tests`: `tests/unit/test_rag_paths.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_rag_paths.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced `rag/` helper clause remains without guesswork
- `next_if_clean`: Item 21
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/rag/paths.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface owns canonical `work-rag.json` and `rag.json` access helpers for
  low-attention continuation
- it is directly backed by the runtime-layout `rag/` ownership clause and stays
  below `pageReadyObserved`
- it hardens autonomous continuation memory without widening browser-facing or
  modeled-stage behavior

### Item 21 — Typed Error Hierarchy Contract

- `file_group`: `src/ez_ax/models/errors.py`
- `tests`: `tests/unit/test_error_hierarchy.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_error_hierarchy.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced typed-error clause remains without guesswork
- `next_if_clean`: Item 22
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/models/errors.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens released-scope typed orchestration error mapping only
- it remains below `pageReadyObserved`
- it does not widen browser-facing or modeled-stage behavior

### Item 22 — Mission Anchor Mapping Contract

- `file_group`: `src/ez_ax/missions/names.py`
- `tests`: `tests/unit/test_mission_anchor_mapping.py`
- `first_prd`: `docs/product/prd-runtime-missions.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_mission_anchor_mapping.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced mission-anchor clause remains without guesswork
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/missions/names.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens known mission-name and released-anchor mapping used below
  `pageReadyObserved`
- it remains below the released ceiling
- it preserves orchestration determinism without widening workflow release

### Item 23 — Modeled MCP Entrypoint Helper

- `file_group`: `src/ez_ax/graph/modeled_mcp_entrypoint.py`
- `tests`: `tests/unit/test_modeled_mcp_entrypoint.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_modeled_mcp_entrypoint.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced modeled-helper clause remains without guesswork
- `next_if_clean`: Item 24
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/modeled_mcp_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface is explicitly modeled-only but still stops at the released
  ceiling `pageReadyObserved`
- it hardens MCP-backed helper orchestration without widening browser-facing
  authority
- it does not present modeled behavior as released behavior

### Item 24 — Modeled MCP CLI Summary Entrypoint

- `file_group`: `src/ez_ax/graph/modeled_mcp_cli_entrypoint.py`
- `tests`: `tests/unit/test_modeled_mcp_cli_entrypoint.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_modeled_mcp_cli_entrypoint.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced modeled CLI-helper clause remains without guesswork
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/modeled_mcp_cli_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface is explicitly modeled-only but persists only a summary for runs
  that already stop at `pageReadyObserved`
- it hardens deterministic run-summary shaping without widening released scope
- it remains Python-first and OpenClaw-boundary preserving

### Item 25 — Modeled MCP Argv+Env Composition Entrypoint

- `file_group`: `src/ez_ax/graph/modeled_mcp_entrypoint.py`
- `tests`: `tests/unit/test_modeled_mcp_entrypoint_argv_env.py`
- `first_prd`: `docs/product/prd-python-runtime-layout.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_modeled_mcp_entrypoint_argv_env.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced user-facing entrypoint input-resolution clause remains
    without guesswork for the modeled argv+env helper
- `next_if_clean`: Item 26
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/graph/modeled_mcp_entrypoint.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface is modeled-only but still invokes the released-scope sequence
  and stops at `pageReadyObserved`
- it directly exercises the explicit runtime-layout clause that any user-facing
  entrypoint calling `run_released_scope` must resolve released inputs in
  deterministic CLI-then-env order and fail fast when required values are
  missing
- it hardens deterministic entrypoint composition without widening browser-
  facing authority or presenting modeled behavior as released behavior

### Item 26 — MCP Stdio Configuration Contract for Injected Client Acquisition

- `file_group`: `src/ez_ax/config/mcp_stdio.py`
- `tests`: `tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
- `first_prd`: `docs/product/prd-python-mcp-client-acquisition.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced MCP stdio acquisition contract clause remains for released
    graph injection shaping
- `next_if_clean`: final stop
- `next_if_fail`:
  - fix the smallest safe one-commit slice in `src/ez_ax/config/mcp_stdio.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface is in-scope for the explicit MCP-client acquisition PRD and feeds
  released graph-path injection only
- it remains below `pageReadyObserved`
- it does not introduce concrete transport behavior into released wiring

## Final Queue Stop

The documented low-attention implementation queue is exhausted only when:

- every documented queue item reached `done_when` honestly, and
- no exact unenforced clause remains without guesswork for any documented queue
  item

Exhaustion protocol gate order:

1. run exactly one bounded resume-search pass below `pageReadyObserved`
2. run exactly one queue-extension heuristic pass for the exhaustion cycle
3. run one final exact gap re-evaluation pass
4. run one continuation-seeding pass
5. run one stop-state consistency gate

Queue-extension heuristic gate:

- after the documented queue is exhausted, lower-capacity autonomous
  implementation may perform exactly one canonical queue-extension heuristic
  pass
  for that exhaustion cycle
- that pass may inspect multiple documented candidates in deterministic order,
  but may add at most one new queue item total
- the new queue item must come from a released-scope support surface already
  described by an exact `must` clause in the governing PRD set
- the new queue item must remain one-task-per-commit safe
- if the heuristic pass yields no valid candidate without guesswork, final stop
  stands honestly

Heuristic candidate catalog:

- the queue-extension heuristic pass may draw only from this catalog and must
  inspect it in order until one valid queue item is found or the catalog is
  exhausted:
  1. `src/ez_ax/config/mcp_stdio.py`
     - `first_prd`: `docs/product/prd-python-mcp-client-acquisition.md`
     - `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
     - why still in-bounds: released-scope MCP stdio configuration feeding the
       released graph path only
  2. `src/ez_ax/adapters/openclaw/mcp_settings.py`
     - `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
     - `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_settings.py`
     - why still in-bounds: released-scope OpenClaw MCP settings contract only
  3. `src/ez_ax/config/settings.py`
     - `first_prd`: `docs/product/prd-python-runtime-layout.md`
     - `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_runtime_settings.py`
     - why still in-bounds: released-scope runtime settings shaping only
  4. `tests/unit/test_langgraph_released_assembly.py`
     - `first_prd`: `docs/product/prd-python-langgraph-runtime.md`
     - `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_langgraph_released_assembly.py`
     - why still in-bounds: released graph assembly verification below the
       release ceiling
  5. `tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
     - `first_prd`: `docs/product/prd-python-mcp-client-acquisition.md`
     - `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_mcp_stdio_released_graph_injection.py`
     - why still in-bounds: released-scope graph injection verification only
- catalog use is deterministic and bounded; ad hoc tertiary discovery remains
  disallowed

Heuristic pass procedure:

1. start at candidate 1 and do not skip ahead without recording why the earlier
   candidate was clean and gap-free
2. for each candidate, run `first_validation`
3. if `first_validation` fails, the candidate becomes the next one-commit task
   and the heuristic pass stops
4. if `first_validation` passes, run the narrowest focused mypy target for the
   candidate when typing is relevant
5. if focused mypy passes, run the narrowest focused `ruff check`
6. only after focused validation is clean may the agent read the candidate's
   `first_prd` for one exact unenforced clause
7. if one exact clause is found, add one queue item and stop the heuristic pass
8. if no exact failing artifact and no exact clause are found honestly, advance
   to the next documented candidate

Heuristic pass output requirement:

- a successful heuristic pass must record:
  - the selected candidate
  - the exact PRD clause or failing validation artifact
  - one primary file group
  - one minimum honest validation command for the follow-on slice
- a failed heuristic pass must record that every documented heuristic candidate
  was scanned in order and none yielded an exact in-bounds next slice

Cycle-reset rule:

- if the heuristic pass adds one valid queue item and that queue item later
  closes honestly with validation, `work-rag` update, and commit, the next
  queue exhaustion starts a new exhaustion cycle
- each new honest exhaustion cycle reopens exactly one canonical queue-
  extension heuristic pass
- if continuation seeding adds one valid queue item and that queue item later
  closes honestly with validation, `work-rag` update, and commit, the next
  queue exhaustion also starts a new exhaustion cycle

Continuation-seeding pass:

- this pass is mandatory while the current phase and milestone still authorize
  low-attention continuation below `pageReadyObserved`
- it may add at most one new queue item total for the exhaustion cycle
- it must prefer:
  1. omitted same-family helper surfaces already on disk
  2. omitted same-anchor support surfaces already imported by active queue
     items
  3. one docs-sufficiency slice that makes the next implementation task
     mechanically nameable
- a valid seeded queue item must name:
  - `file_group`
  - `tests`
  - `first_prd`
  - `first_validation`
  - `done_when`
  - `next_if_clean`
  - `next_if_fail`
- if no seeded queue item can be named honestly, the pass must record that the
  active phase / milestone context, queue PRD, and helper families were
  checked and yielded no new exact in-bounds slice

Seeding-family checklist:

- released graph / call-site family
- released entrypoint / CLI / input family
- released OpenClaw transport-boundary family
- released evidence / reporting / comparability family
- typed mission / error / memory helper family
- modeled helper entrypoint family that still stops at `pageReadyObserved`
- docs-sufficiency family for lower-capacity continuation

Coverage-ledger requirement:

- the active continuation state must keep one explicit status for each family:
  `covered`, `excluded`, or `pending`
- continuation seeding must target the earliest `pending` family first
- queue exhaustion cannot overrule a `pending` family status

Stop-state consistency gate:

- before accepting `FINAL_STOP`, compare:
  - `docs/current-state.md`
  - `docs/product/work-rag.json`
  - this queue PRD
  - `docs/llm/repo-autonomous-loop-adapter.yaml`
- `FINAL_STOP` is stale if any of those sources still names one exact in-bounds
  continuation surface below `pageReadyObserved`
- as part of this gate, run one bounded adjacent-surface completion check for
  same-family helper surfaces already present on disk, including:
  - `*_entrypoint.py`
  - `*_cli_entrypoint.py`
  - `*_argv.py`
  - `*_argv_env.py`
  - colocated focused tests for those helpers
- if that adjacent-surface check finds one valid PRD-backed candidate with a
  deterministic focused validation target, the queue must be reopened with one
  new item instead of accepting `FINAL_STOP`

Final-stop rule:

- after this queue is exhausted and the exhaustion protocol gate order is also
  exhausted, lower-capacity autonomous implementation must stop
- final stop is invalid if any documented heuristic candidate for the current
  exhaustion cycle has not yet completed the full validation-plus-clause scan
- final stop is invalid if continuation seeding has not yet attempted to create
  one new queue item for the active phase / milestone / anchor
- final stop is also invalid if the stop-state consistency gate has not yet
  compared all required continuation sources or has not yet run the bounded
  adjacent-surface completion check
- reopening autonomous implementation requires either:
  - one new explicit in-bounds contract gap, or
  - one explicit PRD update that extends this implementation queue

### Item 27 — Transport-Neutral OpenClaw Adapter Contract

- `file_group`: `src/ez_ax/adapters/openclaw/client.py`
- `tests`: `tests/unit/test_openclaw_adapter_contract.py`
- `first_prd`: `docs/product/prd-openclaw-computer-use-runtime.md`
- `first_validation`: `.venv/bin/python -m pytest -q tests/unit/test_openclaw_adapter_contract.py`
- `done_when`:
  - focused pytest, mypy, and ruff are clean
  - no exact unenforced injected-boundary clause remains without guesswork for
    the transport-neutral OpenClaw adapter contract
  - MCP-specific phrasing is not required to describe the canonical OpenClaw
    execution boundary below `pageReadyObserved`
- `next_if_clean`: rerun the active coverage-ledger check and reopen the next
  exact in-bounds follow-on slice only if one still exists
- `next_if_fail`:
  - fix the smallest safe one-commit slice in
    `src/ez_ax/adapters/openclaw/client.py`
  - validate with the failing pytest target plus the narrowest applicable type
    or lint check

Why in-bounds:

- this surface hardens the canonical injected OpenClaw boundary without
  widening browser-facing authority
- it remains below `pageReadyObserved`
- it demotes MCP to an optional modeled/reference transport rather than
  architecture truth
