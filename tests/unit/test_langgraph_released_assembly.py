from __future__ import annotations

import warnings

from ez_ax.graph.langgraph_released import (
    RELEASED_NODE_SEQUENCE,
    build_released_scope_state_graph,
)


def test_build_released_scope_state_graph_assembles_node_sequence() -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")

    compiled = build_released_scope_state_graph()
    graph = compiled.get_graph()

    nodes = set(graph.nodes.keys())
    for node in RELEASED_NODE_SEQUENCE:
        assert node in nodes

    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert ("__start__", RELEASED_NODE_SEQUENCE[0]) in edges
    assert (RELEASED_NODE_SEQUENCE[-1], "__end__") in edges
