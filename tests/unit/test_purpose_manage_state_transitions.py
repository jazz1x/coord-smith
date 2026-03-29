"""Test that released-scope manages graph-based state transitions.

PRD requirement (Purpose section, line 10):
'manage graph-based state transitions'

This means that:
1. The released-scope graph defines proper state transitions between missions
2. Each transition follows the expected sequence: attach → prepare → benchmark
3. State transitions must be deterministic and repeatable
4. The runtime records and enforces correct transition ordering
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class TransitionTrackingAdapter:
    """Adapter that tracks state transitions through missions."""

    def __init__(self) -> None:
        self.executed_missions: list[str] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute mission and track transitions."""
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
        return ExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_released_scope_defines_proper_state_transition_sequence(
    tmp_path: Path,
) -> None:
    """Verify released-scope missions execute in correct transition order.

    Released scope enforces: attach → prepare → benchmark → page_ready.
    """
    adapter = TransitionTrackingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-123",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify missions executed in correct state transition order
    expected_sequence = [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]
    assert adapter.executed_missions == expected_sequence


@pytest.mark.asyncio
async def test_state_transitions_are_deterministic(tmp_path: Path) -> None:
    """Verify that running the released scope twice produces same transition sequence.

    State transitions must be repeatable and deterministic.
    """
    sequences = []

    for i in range(2):
        adapter = TransitionTrackingAdapter()
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref=f"test-session-{i}",
            expected_auth_state="authenticated",
            target_page_url="https://example.com/target",
            site_identity="example.com",
            base_dir=tmp_path / f"run-{i}",
        )
        sequences.append(adapter.executed_missions)

    # Both runs should have identical transition sequences
    assert sequences[0] == sequences[1]
    assert len(sequences[0]) == 4  # All 4 missions in sequence


@pytest.mark.asyncio
async def test_state_transitions_respect_predecessor_requirements(
    tmp_path: Path,
) -> None:
    """Verify each mission is only attempted after its predecessor succeeds.

    The graph must enforce that:
    - prepare_session only runs after attach_session succeeds
    - benchmark_validation only runs after prepare_session succeeds
    - page_ready_observation only runs after benchmark_validation succeeds
    """
    adapter = TransitionTrackingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-pred",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    missions = adapter.executed_missions

    # Verify predecessor requirements
    assert missions.index("attach_session") < missions.index("prepare_session")
    assert missions.index("prepare_session") < missions.index("benchmark_validation")
    assert missions.index("benchmark_validation") < missions.index(
        "page_ready_observation"
    )


@pytest.mark.asyncio
async def test_graph_transitions_follow_released_mission_definition(
    tmp_path: Path,
) -> None:
    """Verify that state transitions match the defined released mission list.

    The released scope must transition through exactly the 4 released missions
    in the proper order, demonstrating management of graph-based state.
    """
    adapter = TransitionTrackingAdapter()
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session-graph",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Released scope manages state transitions through all 4 released missions
    assert len(adapter.executed_missions) == 4
    assert adapter.executed_missions[0] == "attach_session"
    assert adapter.executed_missions[1] == "prepare_session"
    assert adapter.executed_missions[2] == "benchmark_validation"
    assert adapter.executed_missions[3] == "page_ready_observation"
