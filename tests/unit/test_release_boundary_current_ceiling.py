"""Test that the current released ceiling is pageReadyObserved.

PRD requirement (Release Boundary section, lines 43-45):
'Current released ceiling: - `pageReadyObserved`'

This verifies that pageReadyObserved is the ceiling for all released-scope
execution, and that no execution occurs beyond this point.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class CeilingTrackingAdapter:
    """Adapter that tracks which missions are executed to verify ceiling enforcement."""

    def __init__(self) -> None:
        self.executed_missions: list[str] = []

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
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
                "evidence://action-log/release-ceiling-stop",
            ),
        }

        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return OpenClawExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_current_released_ceiling_is_page_ready_observed(
    tmp_path: Path,
) -> None:
    """Verify the current released ceiling is pageReadyObserved.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `pageReadyObserved`'

    This test confirms that the released-scope execution stops exactly at
    page_ready_observation and does not proceed beyond the ceiling.
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
    assert adapter.executed_missions[-1] == "page_ready_observation"
    assert result.state.current_mission == "page_ready_observation"


@pytest.mark.asyncio
async def test_released_ceiling_page_ready_observation_not_exceeded(
    tmp_path: Path,
) -> None:
    """Verify pageReadyObserved ceiling is not exceeded in released scope.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `pageReadyObserved`'

    No missions beyond page_ready_observation should be executed in the
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

    # Verify only the 4 released missions executed, not more
    expected_missions = {
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    }
    assert set(adapter.executed_missions) == expected_missions
    assert len(adapter.executed_missions) == 4


@pytest.mark.asyncio
async def test_released_ceiling_stops_after_page_ready_observation(
    tmp_path: Path,
) -> None:
    """Verify execution stops immediately after pageReadyObserved.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: - `pageReadyObserved`'

    The ceiling is absolute: once page_ready_observation completes,
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
    assert result.run.approved_scope_ceiling == "pageReadyObserved"
    assert result.state.current_mission == "page_ready_observation"
    # Verify no attempt to move beyond the ceiling
    assert len(adapter.executed_missions) == 4
    assert adapter.executed_missions[-1] == "page_ready_observation"
