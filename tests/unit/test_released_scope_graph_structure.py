"""Test that released-scope graph structure matches PRD specification.

PRD requirement (Release Boundary, lines 47-61):
'Released implementation scope:
- attach
- prepareSession
- benchmark validation
- pageReadyObserved
- syncObservation
- targetActionabilityObservation
- armedStateEntry
- triggerWait
- clickDispatch
- clickCompletion
- successObservation
- runCompletion
- intentional stop at the released ceiling'

This test validates the graph structure enforces these 12 missions in sequence
with an intentional END node (stop) after runCompletion.
"""

from __future__ import annotations

from pathlib import Path

from coord_smith.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from coord_smith.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext


class StubExecutionAdapter:
    """Minimal adapter for graph structure testing."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Return stub evidence."""
        return ExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=("evidence://dom/stub",),
        )


def test_released_scope_graph_has_exactly_twelve_released_missions(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph contains exactly 12 mission nodes.

    PRD requirement (Release Boundary, lines 47-61): The released scope
    includes exactly 12 missions: attach, prepareSession, benchmark validation,
    pageReadyObserved, syncObservation, targetActionabilityObservation,
    armedStateEntry, triggerWait, clickDispatch, clickCompletion,
    successObservation, runCompletion (plus intentional stop).

    This test validates the compiled graph's nodes correspond to these
    12 released missions.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )

    compiled = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/test",
        site_identity="example.com",
    )

    # Get graph structure from compiled graph
    graph_obj = compiled.get_graph()
    all_node_ids = set(node.id for node in graph_obj.nodes.values())

    # The 12 released mission nodes must be present
    mission_nodes = {
        node_id for node_id in all_node_ids
        if any(mission in node_id for mission in [
            "attach",
            "prepare",
            "benchmark",
            "page_ready",
            "sync_observation",
            "target_actionability",
            "armed_state",
            "trigger_wait",
            "click_dispatch",
            "click_completion",
            "success_observation",
            "run_completion",
        ])
    }

    # Must have exactly 12 mission-related nodes for the 12 released missions
    assert len(mission_nodes) == 12, (
        f"Released-scope graph must have exactly 12 mission nodes; "
        f"found {len(mission_nodes)}: {mission_nodes}. "
        f"All nodes: {all_node_ids}"
    )


def test_released_scope_graph_enforces_intentional_stop_at_ceiling(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph has intentional END node from run_completion.

    PRD requirement (Release Boundary, lines 59-61):
    'runCompletion - intentional stop at the released ceiling'

    This validates that run_completion mission edges to END,
    preventing any further mission execution beyond the released ceiling.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )

    compiled = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/test",
        site_identity="example.com",
    )

    # Get graph structure from compiled graph
    graph_obj = compiled.get_graph()
    edges = graph_obj.edges

    # Look for an edge that goes to END (__end__ in langgraph)
    has_end_edge = any(
        edge.target == "__end__" for edge in edges
    )

    assert has_end_edge, (
        f"Released-scope graph must have an edge to END node (__end__); "
        f"edges found: {[(e.source, e.target) for e in edges]}"
    )


def test_released_scope_graph_sequences_missions_correctly(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph sequences missions in correct order.

    PRD requirement (Release Boundary, lines 47-61): Missions must flow:
    attach -> prepareSession -> benchmark validation -> pageReadyObserved ->
    syncObservation -> targetActionabilityObservation -> armedStateEntry ->
    triggerWait -> clickDispatch -> clickCompletion -> successObservation ->
    runCompletion

    This test validates edges reflect this sequence.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )

    compiled = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/test",
        site_identity="example.com",
    )

    # Get graph structure from compiled graph
    graph_obj = compiled.get_graph()
    edges = graph_obj.edges

    # Extract edges as (source, target) tuples for easier analysis
    edge_pairs = [(e.source, e.target) for e in edges]

    # Check for expected sequence edges (full 12-mission sequence)
    expected_sequences = [
        ("attach_session_node", "prepare_session_node"),
        ("prepare_session_node", "benchmark_validation_node"),
        ("benchmark_validation_node", "page_ready_observation_node"),
        ("page_ready_observation_node", "sync_observation_node"),
        ("sync_observation_node", "target_actionability_observation_node"),
        ("target_actionability_observation_node", "armed_state_entry_node"),
        ("armed_state_entry_node", "trigger_wait_node"),
        ("trigger_wait_node", "click_dispatch_node"),
        ("click_dispatch_node", "click_completion_node"),
        ("click_completion_node", "success_observation_node"),
        ("success_observation_node", "run_completion_node"),
    ]

    for expected_source, expected_target in expected_sequences:
        found = any(
            src == expected_source and tgt == expected_target
            for src, tgt in edge_pairs
        )
        assert found, (
            f"Expected edge {expected_source} -> {expected_target} not found in: "
            f"{edge_pairs}"
        )
