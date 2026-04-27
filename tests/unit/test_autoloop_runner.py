from __future__ import annotations

import json
from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import AutoloopPromptPlan
from ez_ax.rag.autoloop_runner import (
    AutoloopRunSettings,
    _atomic_write,
    _next_phase_name,
    _requires_e2e_validation,
    auto_seed_next_phase,
    build_claude_exec_args,
    build_cycle_validation_commands,
    build_last_message_path,
    build_validation_commands,
    parse_args,
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


def test_should_stop_after_cycle_returns_false_on_json_decode_error(
    tmp_path: Path,
) -> None:
    work_rag = tmp_path / "docs" / "product" / "work-rag.json"
    work_rag.parent.mkdir(parents=True)
    work_rag.write_text("not valid json", encoding="utf-8")

    plan = AutoloopPromptPlan(mode="implementation", next_action="do work", prompt="p")
    result = should_stop_after_cycle(plan=plan, project_root=tmp_path)
    assert result is False


def test_should_stop_after_cycle_returns_false_when_file_missing(
    tmp_path: Path,
) -> None:
    plan = AutoloopPromptPlan(mode="implementation", next_action="do work", prompt="p")
    result = should_stop_after_cycle(plan=plan, project_root=tmp_path / "nonexistent")
    assert result is False


def test_atomic_write_writes_content_and_replaces_target(tmp_path: Path) -> None:
    target = tmp_path / "output.json"
    _atomic_write(target, '{"ok": true}')
    assert target.read_text(encoding="utf-8") == '{"ok": true}'


def test_atomic_write_cleans_up_temp_file_on_replace_failure(
    tmp_path: Path,
) -> None:
    """When os.replace fails, the temp file is unlinked and the error re-raises."""
    from unittest.mock import patch

    target = tmp_path / "target.json"

    with patch(
        "ez_ax.rag.autoloop_runner.os.replace",
        side_effect=PermissionError("simulated replace failure"),
    ):
        try:
            _atomic_write(target, "content")
        except PermissionError:
            pass
        else:
            raise AssertionError("Expected PermissionError to propagate")

    assert not target.exists(), "target should not exist after failed replace"
    leftover_tmps = list(tmp_path.glob("*.tmp"))
    assert leftover_tmps == [], f"temp file leaked: {leftover_tmps}"


def test_atomic_write_overwrites_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "output.json"
    target.write_text("old content", encoding="utf-8")
    _atomic_write(target, "new content")
    assert target.read_text(encoding="utf-8") == "new content"


def test_atomic_write_cleans_up_temp_file_on_failure(tmp_path: Path) -> None:
    from unittest.mock import patch

    target = tmp_path / "output.json"
    with patch("os.replace", side_effect=OSError("simulated replace failure")):
        try:
            _atomic_write(target, "content")
        except OSError:
            pass

    leftover_tmps = list(tmp_path.glob("*.tmp"))
    assert leftover_tmps == [], f"temp file not cleaned up: {leftover_tmps}"


# --- _requires_e2e_validation ---


def test_requires_e2e_validation_triggers_on_e2e_keyword() -> None:
    assert _requires_e2e_validation(next_action="run e2e tests") is True
    assert _requires_e2e_validation(next_action="E2E verification") is True


def test_requires_e2e_validation_triggers_on_real_environment_keyword() -> None:
    assert _requires_e2e_validation(next_action="real-environment check") is True
    assert _requires_e2e_validation(next_action="Run Real-Environment path") is True


def test_requires_e2e_validation_false_for_unrelated_action() -> None:
    assert _requires_e2e_validation(next_action="implement feature X") is False
    assert _requires_e2e_validation(next_action="FINAL_STOP — phase complete") is False


# --- build_cycle_validation_commands ---


def test_build_cycle_validation_commands_baseline_has_three_commands(
    tmp_path: Path,
) -> None:
    commands = build_cycle_validation_commands(
        project_root=tmp_path, next_action="implement logging"
    )
    assert len(commands) == 3


def test_build_cycle_validation_commands_e2e_action_inserts_e2e_suite(
    tmp_path: Path,
) -> None:
    commands = build_cycle_validation_commands(
        project_root=tmp_path, next_action="write e2e tests for click flow"
    )
    assert len(commands) == 4
    e2e_cmd = commands[1]
    assert "tests/e2e/" in " ".join(e2e_cmd)


# --- _next_phase_name ---


def test_next_phase_name_increments_phase_number() -> None:
    assert _next_phase_name("Phase R1 — initial") == "Phase R2"
    assert _next_phase_name("Phase R12 — done") == "Phase R13"


def test_next_phase_name_returns_none_for_unparseable_input() -> None:
    assert _next_phase_name("unknown phase") is None
    assert _next_phase_name("") is None


# --- parse_args ---


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.model == "claude-haiku-4-5-20251001"
    assert args.max_cycles == 25
    assert args.dry_run is False


def test_parse_args_dry_run_flag() -> None:
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_custom_model_and_cycles() -> None:
    args = parse_args(["--model", "claude-opus-4-7", "--max-cycles", "5"])
    assert args.model == "claude-opus-4-7"
    assert args.max_cycles == 5
