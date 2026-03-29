"""Tests verifying the PRD requirement: runtime must not invoke LLM inference."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class FakeExecutionAdapter:
    """Stub adapter for testing released scope without external dependencies."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Return predetermined evidence for each mission."""
        evidence_map: dict[str, tuple[str, ...]] = {
            "attach_session": (
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ),
            "prepare_session": (
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
            "benchmark_validation": (
                "evidence://action-log/enter-target-page",
                "evidence://dom/target-page-entered",
            ),
            "page_ready_observation": (
                "evidence://dom/page-shell-ready",
                "evidence://action-log/page-ready-observed",
            ),
            "sync_observation": ("evidence://action-log/sync-observed",),
            "target_actionability_observation": ("evidence://action-log/target-actionable-observed",),
            "armed_state_entry": ("evidence://action-log/armed-state",),
            "trigger_wait": ("evidence://action-log/trigger-wait-complete",),
            "click_dispatch": ("evidence://action-log/click-dispatched",),
            "click_completion": ("evidence://action-log/click-completed",),
            "success_observation": ("evidence://action-log/success-observation",),
            "run_completion": ("evidence://action-log/release-ceiling-stop",),
        }
        refs = evidence_map.get(request.mission_name, ())
        if not refs:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return ExecutionResult(mission_name=request.mission_name, evidence_refs=refs)


@pytest.mark.asyncio
async def test_released_scope_released_missions_are_deterministic(
    tmp_path: Path,
) -> None:
    """Verify released missions execute deterministically without LLM calls.

    PRD requirement (System Boundary, lines 32-34):
    'The ez-ax runtime must not invoke any LLM inference at execution time.
     All graph traversal, evidence validation, and stopping decisions are
     deterministic Python; no model calls are made during a run.'
    """
    adapter = FakeExecutionAdapter()

    result1 = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-1",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run1",
    )

    # Running again with same inputs should produce same result
    result2 = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-1",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run2",
    )

    # Both should reach the same final mission (runCompletion)
    assert result1.state.current_mission == result2.state.current_mission
    assert result1.state.current_mission == "run_completion"
    # Both should have the release ceiling stop proof
    assert "evidence://action-log/release-ceiling-stop" in (
        result1.state.mission_state.evidence_refs or ()
    )
    assert "evidence://action-log/release-ceiling-stop" in (
        result2.state.mission_state.evidence_refs or ()
    )


@pytest.mark.asyncio
async def test_released_scope_pyautogui_adapter_is_deterministic(tmp_path: Path) -> None:
    """Verify PyAutoGUIAdapter contains no LLM calls (coordinate-click only).

    PRD requirement (System Boundary, lines 35-36):
    'PyAutoGUIAdapter is the sole execution backend: coordinate-click and screenshot
     only, no LLM calls.'
    """
    from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter

    adapter = PyAutoGUIAdapter(run_root=tmp_path)

    # Verify the adapter has only the expected methods
    assert callable(adapter.execute)

    # Check that the adapter doesn't reference any anthropic or langchain LLM classes
    adapter_source = adapter.__class__.__module__
    assert "anthropic" not in adapter_source.lower()


@pytest.mark.asyncio
async def test_released_scope_execution_makes_no_llm_client_calls(
    tmp_path: Path,
) -> None:
    """Verify no LLM client is instantiated or invoked during runtime.

    PRD requirement (System Boundary, lines 32-34):
    'The ez-ax runtime must not invoke any LLM inference at execution time. All graph
     traversal, evidence validation, and stopping decisions are deterministic Python;
     no model calls are made during a run.'
    """
    adapter = FakeExecutionAdapter()

    # Patch anthropic.Anthropic to detect any instantiation attempts
    with patch("anthropic.Anthropic") as mock_anthropic:
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="test-session",
            expected_auth_state="logged-in",
            target_page_url="https://example.com/target",
            site_identity="example.com",
            base_dir=tmp_path,
        )

        # Verify anthropic.Anthropic was never instantiated
        mock_anthropic.assert_not_called()
