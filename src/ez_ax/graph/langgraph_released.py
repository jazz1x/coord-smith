"""LangGraph released-scope assembly scaffold (up to runCompletion).

This module assembles a released-scope LangGraph with no browser execution.
It exists to keep the canonical stack contract unambiguous while preserving the
released workflow ceiling.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypedDict

from ez_ax.models.runtime import RuntimeState

if TYPE_CHECKING:
    from langgraph.graph import StateGraph
    from langgraph.graph.state import CompiledStateGraph


class ReleasedGraphState(TypedDict):
    runtime: RuntimeState


ReleasedNode = Callable[[ReleasedGraphState], Awaitable[ReleasedGraphState]]

RELEASED_NODE_SEQUENCE: tuple[str, ...] = (
    "attach_session_node",
    "prepare_session_node",
    "benchmark_validation_node",
    "page_ready_observation_node",
)


def build_released_scope_state_graph() -> CompiledStateGraph[
    ReleasedGraphState, None, ReleasedGraphState, ReleasedGraphState
]:
    """Return a compiled released-scope LangGraph (assembly-only).

    This builder does not embed any execution policy.
    """

    # Import inside the builder to keep LangGraph a leaf dependency and avoid
    # importing it when not assembling graphs.
    from langgraph.graph import END, START, StateGraph

    graph: StateGraph[ReleasedGraphState, None, ReleasedGraphState, ReleasedGraphState]
    graph = StateGraph(ReleasedGraphState)

    async def no_op(state: ReleasedGraphState) -> ReleasedGraphState:
        return state

    for name in RELEASED_NODE_SEQUENCE:
        graph.add_node(name, no_op)

    graph.add_edge(START, RELEASED_NODE_SEQUENCE[0])
    for predecessor, target in zip(
        RELEASED_NODE_SEQUENCE, RELEASED_NODE_SEQUENCE[1:], strict=False
    ):
        graph.add_edge(predecessor, target)
    graph.add_edge(RELEASED_NODE_SEQUENCE[-1], END)

    return graph.compile()
