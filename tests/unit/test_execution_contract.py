from __future__ import annotations

from ez_ax.rag.execution_contract import load_execution_contract


def test_load_execution_contract_exposes_active_phase_and_inputs() -> None:
    contract = load_execution_contract()

    assert contract.active_phase == "Phase R3 — Fresh Python Bootstrap"
    assert "docs/llm/low-attention-execution-contract.json" in contract.canonical_inputs
    assert contract.final_stop_requirements
