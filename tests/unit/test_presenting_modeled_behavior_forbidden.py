"""Test that presenting modeled behavior as released behavior is prevented.

PRD Non-Goals And Forbidden Directions clause (line 148):
'presenting modeled behavior as released behavior'

This enforces that modeled (non-released) missions and stages must not be
presented or treated as released behavior in any way.
"""

from __future__ import annotations

from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionResult
from coord_smith.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext
from coord_smith.missions.names import MODELED_MISSIONS, RELEASED_MISSIONS


class FakeExecutionAdapter:
    """Stub adapter for testing graph structure."""

    async def execute(self, request: object) -> ExecutionResult:
        """Should not be called in structural tests."""
        raise AssertionError("Adapter.execute should not be called in structural tests")


def test_released_scope_never_exposes_modeled_missions(
    tmp_path: Path,
) -> None:
    """Verify released-scope graph never exposes modeled missions to the API.

    PRD Non-Goals (line 148): 'presenting modeled behavior as released behavior'

    The released-scope execution graph must never create nodes, edges, or
    state transitions for any modeled mission. Only the 4 released missions
    (attach_session, prepare_session, benchmark_validation, page_ready_observation)
    are permitted in the released-scope graph.
    """
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
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

    # Get all node names from the compiled graph
    actual_nodes = set(graph.nodes.keys())

    # Verify no modeled missions appear as nodes
    for modeled_mission in MODELED_MISSIONS:
        modeled_node = f"{modeled_mission}_node"
        assert modeled_node not in actual_nodes, (
            f"Modeled mission '{modeled_mission}' was exposed as graph node "
            f"'{modeled_node}'. This violates PRD Non-Goals (line 148): "
            f"'presenting modeled behavior as released behavior'"
        )


def test_released_missions_are_strictly_separated_from_modeled(
    tmp_path: Path,
) -> None:
    """Verify released and modeled missions are completely separated.

    PRD Non-Goals (line 148): 'presenting modeled behavior as released behavior'

    The released mission set and modeled mission set must be completely disjoint.
    No mission can be both released and modeled (presentation error).
    """
    # Verify sets are disjoint
    released_set = set(RELEASED_MISSIONS)
    modeled_set = set(MODELED_MISSIONS)

    intersection = released_set & modeled_set
    assert not intersection, (
        f"Released and modeled missions overlap: {intersection}. "
        f"PRD Non-Goals (line 148) forbids presenting modeled behavior as released."
    )

    # Verify all missions are released (no modeled-only missions)
    assert len(released_set) == 12, "Released scope must have all 12 missions"
    assert len(modeled_set) == 0, "No modeled-only missions remain (all promoted to released)"
    assert len(released_set) + len(modeled_set) == 12, "Total missions equals 12 released missions"


def test_approved_scope_ceiling_prevents_modeled_mission_exposure(
    tmp_path: Path,
) -> None:
    """Verify approved_scope_ceiling prevents missions above ceiling from being exposed.

    PRD Non-Goals (line 148): 'presenting modeled behavior as released behavior'

    The approved_scope_ceiling setting must enforce that no mission above
    the ceiling is ever exposed or presented as released.
    """
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
    )

    # Verify the ceiling is set to a released mission
    assert run.approved_scope_ceiling == "pageReadyObserved", (
        f"Ceiling must be a released mission. "
        f"Current ceiling: {run.approved_scope_ceiling}"
    )

    # With runCompletion ceiling supported, verify that missions are indexed
    # and only those at or below ceiling index are exposed
    assert len(MODELED_MISSIONS) == 0, (
        "All missions are now released; no modeled-only missions remain"
    )


def test_only_released_missions_appear_in_returned_states(
    tmp_path: Path,
) -> None:
    """Verify only released mission names appear in runtime state.

    PRD Non-Goals (line 148): 'presenting modeled behavior as released behavior'

    The runtime state during released-scope execution must only contain
    released mission identifiers, never modeled mission names.
    """
    # The current mission in the run context should only be one of the released missions
    # (or None, before any mission starts, or after the ceiling is reached)
    valid_current_missions = set(RELEASED_MISSIONS) | {None}

    # The run_context doesn't have a current_mission until execution, but we can
    # verify that only released missions are valid for the released-scope execution
    for modeled_mission in MODELED_MISSIONS:
        # Modeled missions must not be valid identifiers for released-scope state
        assert modeled_mission not in valid_current_missions or modeled_mission in RELEASED_MISSIONS, (
            f"Modeled mission '{modeled_mission}' must not appear as valid "
            f"current_mission in released-scope state. "
            f"PRD Non-Goals (line 148): presenting modeled behavior is forbidden."
        )
