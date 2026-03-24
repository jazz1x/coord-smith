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


def test_build_autoloop_prompt_plan_uses_implementation_mode_for_concrete_slice(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action="Run pytest for tests/unit/test_modeled_mcp_entrypoint.py",
    )

    plan = build_autoloop_prompt_plan(work_rag_path=work_rag)

    assert plan.mode == "implementation"
    assert "execute that slice" in plan.prompt
    assert "Current next_action" in plan.prompt


def test_build_autoloop_prompt_plan_uses_continuation_seed_mode_for_final_stop(
    tmp_path: Path,
) -> None:
    work_rag = _write_work_rag(
        tmp_path,
        next_action="FINAL_STOP - queue exhausted",
    )

    plan = build_autoloop_prompt_plan(work_rag_path=work_rag)

    assert plan.mode == "continuation_seed"
    assert "continuation-seeding mode" in plan.prompt
    assert "stop-state consistency gate" in plan.prompt
