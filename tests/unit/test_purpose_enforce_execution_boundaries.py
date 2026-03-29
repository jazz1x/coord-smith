"""Test that released-scope enforces released execution boundaries.

PRD requirement (Purpose section, line 12):
'enforce released execution boundaries'

This means that:
1. Only released missions (attach, prepare, benchmark, page-ready) are executed
2. Modeled-only stages are never executed in released scope
3. Execution stops at pageReadyObserved ceiling
4. No missions beyond the released scope are attempted
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class BoundaryEnforcingAdapter:
    """Adapter that tracks which missions are executed."""

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
                "evidence://action-log/run-completed",
                "evidence://text/run-summary",
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
async def test_released_scope_executes_only_released_missions(
    tmp_path: Path,
) -> None:
    """Verify released scope executes only the 4 released missions.

    Modeled-only stages like syncToServerTime, armed state, trigger wait,
    click dispatch, etc. must not be executed.
    """
    adapter = BoundaryEnforcingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-boundary",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify ONLY released missions are executed
    released_missions = {
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
    assert set(adapter.executed_missions) == released_missions


@pytest.mark.asyncio
async def test_released_scope_stops_at_page_ready_observed_boundary(
    tmp_path: Path,
) -> None:
    """Verify released scope stops at pageReadyObserved ceiling.

    No post-ready workflow stages (syncToServerTime, armed state, etc.)
    are executed after page-ready observation.
    """
    adapter = BoundaryEnforcingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-ceiling",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # The last mission executed must be run_completion (the ceiling)
    assert adapter.executed_missions[-1] == "run_completion"

    # No mission beyond the ceiling should be executed
    assert len(adapter.executed_missions) == 12


@pytest.mark.asyncio
async def test_released_scope_does_not_execute_modeled_only_stages(
    tmp_path: Path,
) -> None:
    """Verify that released scope includes 12 missions up to run_completion.

    With the expanded ceiling to runCompletion, the released scope now includes
    all 12 missions including:
    - sync_observation
    - target_actionability_observation
    - armed_state_entry
    - trigger_wait
    - click_dispatch
    - click_completion
    - success_observation
    - run_completion

    These are now part of the released scope (not modeled-only anymore).
    """
    adapter = BoundaryEnforcingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-modeled",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify all 12 released missions are executed
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
    assert set(adapter.executed_missions) == expected_missions, (
        f"Released scope should execute all 12 missions. Got: {adapter.executed_missions}"
    )
    assert len(adapter.executed_missions) == 12


@pytest.mark.asyncio
async def test_released_scope_enforces_exact_boundary_at_page_ready(
    tmp_path: Path,
) -> None:
    """Verify released scope respects the exact boundary at pageReadyObserved.

    After page_ready_observation completes, no further missions are attempted.
    This enforces the released ceiling.
    """
    adapter = BoundaryEnforcingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-exact",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify exact boundary enforcement
    expected_sequence = [
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
    ]
    assert adapter.executed_missions == expected_sequence

    # No additional missions should be attempted
    assert len(adapter.executed_missions) == 12
