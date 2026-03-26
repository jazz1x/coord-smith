from __future__ import annotations

import json
from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import AutoloopPromptPlan
from ez_ax.rag.autoloop_runner import (
    AutoloopRunSettings,
    auto_seed_next_phase,
    build_claude_exec_args,
    build_last_message_path,
    build_validation_commands,
    should_stop_after_cycle,
)


def test_build_claude_exec_args_includes_model_and_permission_mode() -> None:
    settings = AutoloopRunSettings(
        claude_bin="claude",
        project_root=Path("/repo"),
        model="claude-haiku-4-5-20251001",
        max_cycles=5,
        output_dir=Path("/repo/artifacts/autoloop"),
        dry_run=False,
    )

    command = build_claude_exec_args(settings=settings)

    assert "--print" in command
    assert "--model" in command
    assert "claude-haiku-4-5-20251001" in command
    assert "--permission-mode" in command
    assert "bypassPermissions" in command


def test_build_last_message_path_uses_zero_padded_cycle() -> None:
    path = build_last_message_path(
        output_dir=Path("/repo/artifacts/autoloop"),
        cycle_index=3,
    )

    assert path.name == "cycle-03-last-message.md"


def test_build_validation_commands_includes_pytest_mypy_ruff() -> None:
    commands = build_validation_commands(project_root=Path("/repo"))

    flat = [token for cmd in commands for token in cmd]
    assert "pytest" in flat
    assert "mypy" in flat
    assert "ruff" in flat


def test_should_stop_after_cycle_only_for_final_stop_review() -> None:
    final_plan = AutoloopPromptPlan(
        mode="final_stop_review",
        next_action="FINAL_STOP",
        prompt="prompt",
    )
    implementation_plan = AutoloopPromptPlan(
        mode="implementation",
        next_action="do work",
        prompt="prompt",
    )

    project_root = Path("/repo")
    assert (
        should_stop_after_cycle(plan=final_plan, project_root=project_root) is True
    )
    assert (
        should_stop_after_cycle(plan=implementation_plan, project_root=project_root)
        is False
    )


def _write_autoloop_fixtures(
    tmp_path: Path, *, active_phase: str, include_execution_contract: bool = False
) -> None:
    ledger = {
        "version": 2,
        "active_phase": active_phase,
        "active_milestone": "milestone",
        "active_anchor": "anchor",
        "families": [
            {
                "family": "some covered family",
                "status": "covered",
                "evidence_or_reason": "done",
                "next_slice_hint": "",
                "first_validation": "",
                "mypy_target": "",
                "ruff_target": "",
                "done_when": [],
                "template_id": "",
            }
        ],
    }
    (tmp_path / "docs" / "llm").mkdir(parents=True)
    (tmp_path / "docs" / "llm" / "low-attention-coverage-ledger.json").write_text(
        json.dumps(ledger), encoding="utf-8"
    )
    work_rag = {"current": {"next_action": "FINAL_STOP_REVIEW"}}
    (tmp_path / "docs" / "product").mkdir(parents=True)
    (tmp_path / "docs" / "product" / "work-rag.json").write_text(
        json.dumps(work_rag), encoding="utf-8"
    )
    if include_execution_contract:
        contract = {
            "version": 3,
            "active_phase": active_phase,
            "active_milestone": "milestone",
            "active_anchor": "anchor",
            "active_invariant": "invariant",
            "scope_ceiling": "pageReadyObserved",
            "canonical_inputs": ["docs/core-loop.md"],
            "extended_inputs_when_needed": [],
            "anchor_contract_families": ["some covered family"],
            "heuristic_family_ladder": ["ladder"],
            "seeded_slice_requirements": ["req"],
            "final_stop_requirements": ["req"],
        }
        (tmp_path / "docs" / "llm" / "low-attention-execution-contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )


def test_auto_seed_next_phase_adds_pending_family(tmp_path: Path) -> None:
    _write_autoloop_fixtures(tmp_path, active_phase="Phase R5 — Integration")

    seeded = auto_seed_next_phase(project_root=tmp_path)

    assert seeded is True
    ledger = json.loads(
        (tmp_path / "docs/llm/low-attention-coverage-ledger.json").read_text()
    )
    families = {f["family"] for f in ledger["families"]}
    assert "Phase R6 heuristic gap scan" in families


def test_auto_seed_next_phase_updates_work_rag_next_action(tmp_path: Path) -> None:
    _write_autoloop_fixtures(tmp_path, active_phase="Phase R5 — Integration")

    auto_seed_next_phase(project_root=tmp_path)

    work_rag = json.loads(
        (tmp_path / "docs/product/work-rag.json").read_text()
    )
    assert work_rag["current"]["next_action"] == "Phase R6 heuristic gap scan"


def test_auto_seed_next_phase_advances_phase_on_each_call(tmp_path: Path) -> None:
    # Each call advances active_phase, so successive calls seed R6, R7, R8...
    _write_autoloop_fixtures(tmp_path, active_phase="Phase R5 — Integration")

    first = auto_seed_next_phase(project_root=tmp_path)   # seeds R6
    second = auto_seed_next_phase(project_root=tmp_path)  # seeds R7 (active_phase now R6)

    assert first is True
    assert second is True
    ledger = json.loads(
        (tmp_path / "docs/llm/low-attention-coverage-ledger.json").read_text()
    )
    families = {f["family"] for f in ledger["families"]}
    assert "Phase R6 heuristic gap scan" in families
    assert "Phase R7 heuristic gap scan" in families


def test_auto_seed_next_phase_updates_current_state_when_present(
    tmp_path: Path,
) -> None:
    _write_autoloop_fixtures(tmp_path, active_phase="Phase R5 — Integration")
    current_state = tmp_path / "docs" / "current-state.md"
    current_state.write_text(
        "# State\n\n## Current Interpretation\n\nPhase R5 complete.\n\n"
        "## Next\n\nThe current next action is: `FINAL_STOP_REVIEW`\n",
        encoding="utf-8",
    )

    auto_seed_next_phase(project_root=tmp_path)

    content = current_state.read_text()
    assert "FINAL_STOP" not in content
    assert "Phase R6 heuristic gap scan" in content


def test_auto_seed_next_phase_updates_execution_contract_when_present(
    tmp_path: Path,
) -> None:
    _write_autoloop_fixtures(
        tmp_path, active_phase="Phase R5 — Integration", include_execution_contract=True
    )

    auto_seed_next_phase(project_root=tmp_path)

    contract = json.loads(
        (tmp_path / "docs/llm/low-attention-execution-contract.json").read_text()
    )
    assert contract["active_phase"] == "Phase R6 — heuristic scan"
    assert contract["anchor_contract_families"] == ["Phase R6 heuristic gap scan"]


def test_auto_seed_next_phase_returns_false_for_unparseable_phase(
    tmp_path: Path,
) -> None:
    _write_autoloop_fixtures(tmp_path, active_phase="Unknown Phase Format")

    result = auto_seed_next_phase(project_root=tmp_path)

    assert result is False
