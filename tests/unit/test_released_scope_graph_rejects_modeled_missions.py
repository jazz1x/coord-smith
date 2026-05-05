"""Test that released-scope graph enforces released mission boundary and rejects modeled missions."""

from __future__ import annotations

from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionResult
from coord_smith.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext
from coord_smith.missions.names import MODELED_MISSIONS, RELEASED_MISSIONS


class FakeExecutionAdapter:
    """Minimal adapter for testing graph structure."""

    async def execute(self, request: object) -> ExecutionResult:
        """Should not be called in structural tests."""
        raise AssertionError("Adapter.execute should not be called in structural tests")


def test_released_scope_graph_contains_only_released_mission_nodes(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph only adds released missions as nodes."""
    # PRD Release Boundary (lines 47-61): All 12 missions are released:
    # attach, prepareSession, benchmark validation, pageReadyObserved,
    # syncObservation, targetActionabilityObservation, armedStateEntry,
    # triggerWait, clickDispatch, clickCompletion, successObservation, runCompletion

    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )
    adapter = FakeExecutionAdapter()

    graph = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
    )

    # Compiled graph exposes node names via graph.nodes (for inspection)
    # We verify the exact sequence of node names
    expected_node_sequence = [
        "attach_session_node",
        "prepare_session_node",
        "benchmark_validation_node",
        "page_ready_observation_node",
        "sync_observation_node",
        "target_actionability_observation_node",
        "armed_state_entry_node",
        "trigger_wait_node",
        "click_dispatch_node",
        "click_completion_node",
        "success_observation_node",
        "run_completion_node",
    ]

    # The compiled graph structure should only include these 12 nodes
    # (plus implicit START and END nodes handled by LangGraph)
    actual_nodes = list(graph.nodes.keys())

    # Verify all released missions are present
    for expected_node in expected_node_sequence:
        assert expected_node in actual_nodes, (
            f"Released mission node {expected_node} not found in graph. "
            f"Actual nodes: {actual_nodes}"
        )

    # Verify NO modeled missions are present (should be empty now)
    for modeled_mission in MODELED_MISSIONS:
        # Modeled missions would appear as nodes like "sync_observation_node", etc.
        modeled_node_name = f"{modeled_mission}_node"
        assert modeled_node_name not in actual_nodes, (
            f"Modeled mission {modeled_mission} was added as node {modeled_node_name} "
            f"to released-scope graph. This violates PRD Release Boundary: "
            f"modeled-only stages must not be treated as released behavior."
        )


def test_released_scope_graph_enforces_correct_mission_sequence(
    tmp_path: Path,
) -> None:
    """Verify the graph wires missions in the correct released sequence."""
    # PRD Release Boundary specifies the order:
    # 1. attach_session (attach)
    # 2. prepare_session (prepareSession)
    # 3. benchmark_validation (benchmark validation)
    # 4. page_ready_observation (pageReadyObserved)
    # 5. sync_observation (syncObservation)
    # 6. target_actionability_observation (targetActionabilityObservation)
    # 7. armed_state_entry (armedStateEntry)
    # 8. trigger_wait (triggerWait)
    # 9. click_dispatch (clickDispatch)
    # 10. click_completion (clickCompletion)
    # 11. success_observation (successObservation)
    # 12. run_completion (runCompletion) - release ceiling

    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )
    adapter = FakeExecutionAdapter()

    compiled_graph = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
    )

    # Access the underlying StateGraph via get_graph()
    graph = compiled_graph.get_graph()

    # Verify the nodes form the correct sequence
    expected_node_sequence = [
        "attach_session_node",
        "prepare_session_node",
        "benchmark_validation_node",
        "page_ready_observation_node",
        "sync_observation_node",
        "target_actionability_observation_node",
        "armed_state_entry_node",
        "trigger_wait_node",
        "click_dispatch_node",
        "click_completion_node",
        "success_observation_node",
        "run_completion_node",
    ]

    # Get the actual edges from the underlying graph
    # graph.edges returns a list of (source, target) tuples
    actual_edges = list(graph.edges)

    # Build expected edges from the sequence
    expected_edges = [
        (expected_node_sequence[i], expected_node_sequence[i + 1])
        for i in range(len(expected_node_sequence) - 1)
    ]

    for expected_edge in expected_edges:
        # Check the edge exists (ignoring LangGraph's internal representation)
        found = False
        for edge in actual_edges:
            # Edges in LangGraph are Edge objects with source and target attributes
            edge_source = getattr(edge, "source", None)
            edge_target = getattr(edge, "target", None)
            if edge_source == expected_edge[0] and edge_target == expected_edge[1]:
                found = True
                break
        assert found, (
            f"Expected edge {expected_edge} not found in graph. "
            f"Actual edges: {[(e.source, e.target) for e in actual_edges]}. "
            f"This violates the PRD Release Boundary mission sequence."
        )


def test_released_scope_missions_match_prd_definition(
    tmp_path: Path,
) -> None:
    """Verify RELEASED_MISSIONS constant matches PRD Release Boundary specification."""
    # PRD lines 47-53 define the released scope:
    # - attach (attach_session)
    # - prepareSession (prepare_session)
    # - benchmark validation (benchmark_validation)
    # - pageReadyObserved (page_ready_observation)

    # All 12 missions are now released (ceiling expands to runCompletion)
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

    actual_missions = set(RELEASED_MISSIONS)

    assert actual_missions == expected_missions, (
        f"RELEASED_MISSIONS must match PRD Release Boundary specification. "
        f"Expected: {expected_missions}, Actual: {actual_missions}"
    )


def test_released_scope_execution_graph_edges_final_mission_to_end(
    tmp_path: Path,
) -> None:
    """Verify released-scope execution graph edges run_completion to END.

    PRD Release Boundary (line 61): "intentional stop at the released ceiling"
    This test verifies that the graph structure enforces this stop by having
    run_completion_node edge to END (__end__), not to any other mission.
    """
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="runCompletion",
    )
    adapter = FakeExecutionAdapter()

    compiled_graph = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
    )

    # Get the underlying StateGraph to inspect edges
    graph = compiled_graph.get_graph()

    # Collect edges from the graph
    edges = graph.edges

    # Find outgoing edges from run_completion_node
    outgoing_edges = [
        edge for edge in edges if str(edge[0]) == "run_completion_node"
    ]

    assert len(outgoing_edges) > 0, (
        "run_completion_node has no outgoing edges. "
        "This violates PRD Release Boundary: intentional stop at released ceiling."
    )

    assert len(outgoing_edges) == 1, (
        f"run_completion_node has {len(outgoing_edges)} outgoing edges. "
        f"Should have exactly 1 edge to END. Actual edges: {outgoing_edges}. "
        f"This violates PRD Release Boundary: run_completion is the final mission."
    )

    # Verify the single outgoing edge goes to END (__end__)
    target_node = outgoing_edges[0][1]
    assert str(target_node) == "__end__", (
        f"run_completion_node edges to {target_node}, not __end__. "
        f"This violates PRD Release Boundary: intentional stop at released ceiling."
    )
