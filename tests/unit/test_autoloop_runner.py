from __future__ import annotations

from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import AutoloopPromptPlan
from ez_ax.rag.autoloop_runner import (
    AutoloopRunSettings,
    build_codex_exec_args,
    build_last_message_path,
    should_stop_after_cycle,
)


def test_build_codex_exec_args_includes_prompt_stdin_and_output_path() -> None:
    settings = AutoloopRunSettings(
        codex_bin="codex",
        project_root=Path("/repo"),
        model="gpt-5.4-mini",
        sandbox="workspace-write",
        max_cycles=5,
        output_dir=Path("/repo/artifacts/autoloop"),
        dry_run=False,
    )

    command = build_codex_exec_args(
        settings=settings,
        last_message_path=Path("/repo/artifacts/autoloop/cycle-01-last-message.md"),
    )

    assert command[-1] == "-"
    assert "-o" in command
    assert "workspace-write" in command


def test_build_last_message_path_uses_zero_padded_cycle() -> None:
    path = build_last_message_path(
        output_dir=Path("/repo/artifacts/autoloop"),
        cycle_index=3,
    )

    assert path.name == "cycle-03-last-message.md"


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

    assert should_stop_after_cycle(plan=final_plan) is True
    assert should_stop_after_cycle(plan=implementation_plan) is False
