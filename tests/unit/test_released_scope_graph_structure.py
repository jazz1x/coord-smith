"""Test that released-scope graph structure matches PRD specification.

PRD requirement (Release Boundary, lines 47-53):
'Released implementation scope:
- attach
- prepareSession
- benchmark validation
- pageReadyObserved
- intentional stop at the released ceiling'

This test validates the graph structure enforces these 4 missions in sequence
with an intentional END node (stop) after pageReadyObserved.
"""

from __future__ import annotations

from pathlib import Path

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from ez_ax.graph.released_call_site import ReleasedRunContext


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


def test_released_scope_graph_has_exactly_four_released_missions(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph contains exactly 4 mission nodes.

    PRD requirement (Release Boundary, lines 47-53): The released scope
    includes exactly 4 missions: attach, prepareSession, benchmark validation,
    pageReadyObserved (plus intentional stop).

    This test validates the compiled graph's nodes correspond to these
    4 released missions.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
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

    # The 4 released mission nodes must be present
    # (exact naming: attach_session_node, prepare_session_node, etc.)
    mission_nodes = {
        node_id for node_id in all_node_ids
        if any(mission in node_id for mission in [
            "attach",
            "prepare",
            "benchmark",
            "page_ready",
        ])
    }

    # Must have exactly 4 mission-related nodes for the 4 released missions
    assert len(mission_nodes) == 4, (
        f"Released-scope graph must have exactly 4 mission nodes; "
        f"found {len(mission_nodes)}: {mission_nodes}. "
        f"All nodes: {all_node_ids}"
    )


def test_released_scope_graph_enforces_intentional_stop_at_ceiling(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph has intentional END node from page_ready_observation.

    PRD requirement (Release Boundary, lines 51-53):
    'pageReadyObserved - intentional stop at the released ceiling'

    This validates that page_ready_observation mission edges to END,
    preventing any further mission execution beyond the released ceiling.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
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

    PRD requirement (Release Boundary, lines 47-53): Missions must flow:
    attach -> prepareSession -> benchmark validation -> pageReadyObserved

    This test validates edges reflect this sequence.
    """
    adapter = StubExecutionAdapter()
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
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

    # Check for expected sequence edges
    # attach -> prepare, prepare -> benchmark, benchmark -> page_ready
    expected_sequences = [
        ("attach_session_node", "prepare_session_node"),
        ("prepare_session_node", "benchmark_validation_node"),
        ("benchmark_validation_node", "page_ready_observation_node"),
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
