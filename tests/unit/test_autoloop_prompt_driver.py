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
            }
        ]
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

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
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

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
    )

    assert plan.mode == "implementation"
    assert "docs_sufficiency_coverage_ledger_contract" in plan.prompt
    assert "Primary file group: src/ez_ax/validation/bootstrap.py" in plan.prompt
    assert "machine-readable source of truth" in plan.prompt


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

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
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

    plan = build_autoloop_prompt_plan(
        work_rag_path=work_rag,
        coverage_ledger_path=coverage_ledger,
    )

    assert plan.mode == "final_stop_review"
    assert "coverage ledger has no pending family" in plan.prompt
    assert "stop-state consistency gate" in plan.prompt
