from __future__ import annotations

import json
from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import build_autoloop_prompt_plan


def _write_work_rag(tmp_path: Path, *, next_action: str) -> Path:
    path = tmp_path / "work-rag.json"
    payload = {
        "current": {
            "goal": "goal",
            "phase": "phase",
            "milestone": "milestone",
            "anchor": "anchor",
            "invariant": "invariant",
            "next_action": next_action,
            "approved_scope_ceiling": "pageReadyObserved",
            "references": [],
        },
        "history": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_coverage_ledger(
    tmp_path: Path,
    *,
    status: str,
    template_id: str = "",
    first_validation: str = "pytest tests/ -q",
    mypy_target: str = "mypy src/",
    ruff_target: str = "ruff check src/",
    done_when: list[str] | None = None,
) -> Path:
    path = tmp_path / "low-attention-coverage-ledger.json"
    payload = {
        "families": [
            {
                "family": "docs-sufficiency family for lower-capacity continuation",
                "status": status,
                "evidence_or_reason": "reason",
                "next_slice_hint": "hint",
                "template_id": template_id,
                "first_validation": first_validation,
                "mypy_target": mypy_target,
                "ruff_target": ruff_target,
                "done_when": done_when or ["validation clean", "committed"],
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_execution_contract(tmp_path: Path) -> Path:
    path = tmp_path / "low-attention-execution-contract.json"
    payload = {
        "active_phase": "Phase",
        "active_milestone": "Milestone",
        "active_anchor": "Anchor",
        "active_invariant": "Invariant",
        "scope_ceiling": "pageReadyObserved",
        "canonical_inputs": ["AGENTS.md", "docs/prd.md"],
        "anchor_contract_families": ["family-a"],
        "heuristic_family_ladder": ["ladder-a"],
        "seeded_slice_requirements": ["seed-a"],
        "final_stop_requirements": ["stop-a", "stop-b"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_autoloop_prompt_plan_uses_implementation_mode_for_concrete_slice(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action="Run pytest for tests/unit/test_modeled_mcp_entrypoint.py",
    )
    coverage_ledger = _write_coverage_ledger(tmp_path, status="covered")
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "implementation"
    assert "execute that slice" in plan.prompt
    assert "Current next_action" in plan.prompt


def test_build_autoloop_prompt_plan_expands_matched_slice_template(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action=(
            "Seed the earliest pending family from the active coverage ledger "
            "before honoring FINAL_STOP: close the docs-sufficiency family gap "
            "by adding one deterministic bootstrap/docs-sufficiency slice "
            "definition that makes future coverage-ledger maintenance "
            "mechanically nameable."
        ),
    )
    coverage_ledger = _write_coverage_ledger(
        tmp_path,
        status="pending",
        template_id="docs_sufficiency_coverage_ledger_contract",
    )
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "implementation"
    assert "docs_sufficiency_coverage_ledger_contract" in plan.prompt
    assert "Primary file group: src/ez_ax/validation/bootstrap.py" in plan.prompt
    assert "machine-readable source of truth" in plan.prompt
    assert "phase `Phase`" in plan.prompt


def test_build_autoloop_prompt_plan_prefers_pending_coverage_ledger_over_final_stop(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action="FINAL_STOP - queue exhausted",
    )
    coverage_ledger = _write_coverage_ledger(
        tmp_path,
        status="pending",
        template_id="docs_sufficiency_coverage_ledger_contract",
    )
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "implementation"
    assert "low-attention-coverage-ledger.json" in plan.prompt
    assert "docs_sufficiency_coverage_ledger_contract" in plan.prompt


def test_build_autoloop_prompt_plan_uses_final_stop_review_when_no_pending_family(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action="FINAL_STOP - queue exhausted",
    )
    coverage_ledger = _write_coverage_ledger(tmp_path, status="covered")
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "final_stop_review"
    assert "coverage ledger has no pending family" in plan.prompt
    assert "stop-state consistency gate" in plan.prompt
    assert "stop-a; stop-b" in plan.prompt


def test_build_autoloop_prompt_plan_pending_family_prompt_includes_validation_sequence(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(tmp_path, next_action="hint")
    coverage_ledger = _write_coverage_ledger(
        tmp_path,
        status="pending",
        template_id="",
        first_validation="pytest tests/unit/ -q",
        mypy_target="mypy src/ez_ax/",
        ruff_target="ruff check src/ez_ax/",
        done_when=["prd updated", "pytest clean", "committed"],
    )
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "implementation"
    assert "Validation sequence:" in plan.prompt
    assert "pytest tests/unit/ -q" in plan.prompt
    assert "mypy src/ez_ax/" in plan.prompt
    assert "ruff check src/ez_ax/" in plan.prompt
    assert "Done when:" in plan.prompt
    assert "prd updated" in plan.prompt
    assert "pytest clean" in plan.prompt
    assert "committed" in plan.prompt


def test_build_autoloop_prompt_plan_uses_continuation_seed_mode_for_seed_pass(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action=(
            "Run one mandatory continuation-seeding pass for the active phase / "
            "milestone / anchor before honoring FINAL_STOP."
        ),
    )
    coverage_ledger = _write_coverage_ledger(tmp_path, status="covered")
    execution_contract = _write_execution_contract(tmp_path)

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
        execution_contract_path=execution_contract,
    )

    assert plan.mode == "continuation_seed"
    assert "continuation-seeding mode, not terminal stop mode" in plan.prompt
    assert "Produce exactly one one-commit-safe seeded slice" in plan.prompt
