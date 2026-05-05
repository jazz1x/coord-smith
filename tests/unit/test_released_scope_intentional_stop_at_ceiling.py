"""Test that released scope implements intentional stop at runCompletion ceiling.

PRD Release Boundary (line 61): 'intentional stop at the released ceiling'

The released scope must execute exactly 12 missions from attach_session through
run_completion, and then intentionally stop without attempting any further missions
beyond run_completion. This is the released-scope ceiling enforcement.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from coord_smith.adapters.execution.client import ExecutionResult
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)
from coord_smith.missions.names import RELEASED_MISSIONS


class StrictMissionCountingAdapter:
    """Adapter that tracks exact mission execution and rejects unexpected missions."""

    def __init__(self) -> None:
        self.executed_missions: list[str] = []
        self.call_count: int = 0

    async def execute(self, request: object) -> ExecutionResult:
        """Execute mission, tracking execution order and rejecting missions beyond ceiling."""
        # Cast to proper type for mission_name extraction
        if not hasattr(request, "mission_name"):
            raise AssertionError(f"Request missing mission_name: {request}")

        mission = str(request.mission_name)  # type: ignore[attr-defined]
        self.call_count += 1
        self.executed_missions.append(mission)

        # Verify mission is within released scope
        if mission not in RELEASED_MISSIONS:
            raise AssertionError(
                f"Mission '{mission}' is not in released scope. "
                f"Released missions: {RELEASED_MISSIONS}"
            )

        # Verify we haven't exceeded the mission count
        if self.call_count > len(RELEASED_MISSIONS):
            raise AssertionError(
                f"Execution exceeded released scope ceiling. "
                f"Expected at most {len(RELEASED_MISSIONS)} missions, "
                f"but got {self.call_count} execution requests. "
                f"Missions executed: {self.executed_missions}"
            )

        # Return appropriate evidence for each mission
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

        refs = evidence_map.get(mission)
        if refs is None:
            raise AssertionError(f"Unknown mission: {mission}")

        return ExecutionResult(
            mission_name=mission,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_released_scope_stops_exactly_at_run_completion(
    tmp_path: Path,
) -> None:
    """Verify released scope stops exactly at run_completion (intentional ceiling).

    PRD Release Boundary (line 61): 'intentional stop at the released ceiling'

    This test ensures that:
    1. The released scope executes exactly 12 missions (not more, not less)
    2. The final mission is run_completion
    3. No missions are attempted beyond run_completion
    4. The executor receives exactly 12 execute() calls, no more
    """
    adapter = StrictMissionCountingAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-intentional-stop",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify exactly 12 execute() calls were made
    assert adapter.call_count == 12, (
        f"Expected exactly 12 mission executions at released ceiling, "
        f"but got {adapter.call_count}. "
        f"Missions executed: {adapter.executed_missions}"
    )

    # Verify final executed mission is run_completion
    assert adapter.executed_missions[-1] == "run_completion", (
        f"Final mission must be 'run_completion' (released ceiling), "
        f"but got '{adapter.executed_missions[-1]}'"
    )

    # Verify total execution matches released missions count
    assert len(adapter.executed_missions) == len(RELEASED_MISSIONS), (
        f"Mission count mismatch: expected {len(RELEASED_MISSIONS)}, "
        f"got {len(adapter.executed_missions)}"
    )

    # Verify final state reflects the ceiling
    assert result.state.current_mission == "run_completion", (
        f"Final state should be at run_completion, "
        f"but current_mission is '{result.state.current_mission}'"
    )

    # Verify the result indicates ceiling was reached
    assert result.run.approved_scope_ceiling == "runCompletion", (
        f"Scope ceiling should be runCompletion, "
        f"but got {result.run.approved_scope_ceiling}"
    )


@pytest.mark.asyncio
async def test_released_scope_enforces_no_missions_beyond_ceiling(
    tmp_path: Path,
) -> None:
    """Verify the released scope graph enforces intentional stop.

    PRD Release Boundary (line 61): 'intentional stop at the released ceiling'

    If the adapter incorrectly attempts to execute a mission beyond run_completion,
    the released scope must not allow it. This test documents that the execution
    graph itself prevents execution beyond the ceiling.
    """
    adapter = StrictMissionCountingAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-ceiling-enforcement",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # The fact that we reach here without the adapter raising an error means
    # the execution graph correctly stopped at run_completion.
    # If the graph tried to execute more missions, the adapter would have
    # raised AssertionError about exceeding the ceiling.

    # Verify the graph state confirms it stopped at the ceiling
    assert result.state.current_mission == RELEASED_MISSIONS[-1], (
        f"Released scope must stop at ceiling (run_completion), "
        f"not at {result.state.current_mission}"
    )
