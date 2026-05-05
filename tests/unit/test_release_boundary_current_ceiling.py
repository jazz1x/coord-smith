"""Test that the current released ceiling is runCompletion.

PRD requirement (Release Boundary section, lines 43-45):
'Current released ceiling: - `runCompletion`'

This verifies that runCompletion is the ceiling for all released-scope
execution, and that all 12 missions are executed up to and including this point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coord_smith.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)


class CeilingTrackingAdapter:
    """Adapter that tracks which missions are executed to verify ceiling enforcement."""

    def __init__(self) -> None:
        self.executed_missions: list[str] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute mission and track execution."""
        self.executed_missions.append(request.mission_name)

        # Provide appropriate evidence based on mission
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
            "sync_observation": (
                "evidence://clock/server-time-synced",
                "evidence://action-log/sync-observed",
            ),
            "target_actionability_observation": (
                "evidence://dom/target-actionable",
                "evidence://action-log/target-actionable-observed",
            ),
            "armed_state_entry": (
                "evidence://text/armed-state-entered",
                "evidence://action-log/armed-state",
            ),
            "trigger_wait": (
                "evidence://clock/trigger-received",
                "evidence://action-log/trigger-wait-complete",
            ),
            "click_dispatch": (
                "evidence://action-log/click-dispatched",
                "evidence://dom/click-target-clicked",
            ),
            "click_completion": (
                "evidence://dom/click-effect-confirmed",
                "evidence://action-log/click-completed",
            ),
            "success_observation": (
                "evidence://dom/success-observed",
                "evidence://action-log/success-observation",
            ),
            "run_completion": (
                "evidence://action-log/release-ceiling-stop",
            ),
        }

        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return ExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_current_released_ceiling_is_run_completion(
    tmp_path: Path,
) -> None:
    """Verify the current released ceiling is runCompletion.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `runCompletion`'

    This test confirms that the released-scope execution stops exactly at
    run_completion and does not proceed beyond the ceiling.
    """
    adapter = CeilingTrackingAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-ceiling",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify the final mission is at the ceiling
    assert adapter.executed_missions[-1] == "run_completion"
    assert result.state.current_mission == "run_completion"


@pytest.mark.asyncio
async def test_released_ceiling_run_completion_not_exceeded(
    tmp_path: Path,
) -> None:
    """Verify runCompletion ceiling is not exceeded in released scope.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `runCompletion`'

    All 12 missions including run_completion should be executed in the
    released scope. The ceiling is absolute.
    """
    adapter = CeilingTrackingAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-ceiling-enforcement",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify all 12 released missions executed, not more
    expected_missions = {
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    }
    assert set(adapter.executed_missions) == expected_missions
    assert len(adapter.executed_missions) == 12


@pytest.mark.asyncio
async def test_released_ceiling_stops_at_run_completion(
    tmp_path: Path,
) -> None:
    """Verify execution stops at runCompletion ceiling.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `runCompletion`'

    The ceiling is absolute: once run_completion completes,
    no further missions are attempted.
    """
    adapter = CeilingTrackingAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-stop-after-ceiling",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify the graph stopped at the ceiling mission
    assert result.run.approved_scope_ceiling == "runCompletion"
    assert result.state.current_mission == "run_completion"
    # Verify no attempt to move beyond the ceiling
    assert len(adapter.executed_missions) == 12
    assert adapter.executed_missions[-1] == "run_completion"
