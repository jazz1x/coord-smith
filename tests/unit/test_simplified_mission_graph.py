"""Unit tests for the simplified six-mission released graph.

Validates the per-run / per-step split documented in
``docs/prd-multi-step-flow-recipe.md`` §2.4 D2 — the registry is six
missions; the graph topology dynamically materializes ``observe →
dispatch → capture`` triples for each step in the recipe.
"""

from __future__ import annotations

from pathlib import Path

from coord_smith.config.click_recipe import Step, StepCoord
from coord_smith.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from coord_smith.graph.released_call_site import ReleasedRunContext
from coord_smith.graph.runtime_graph import (
    FORWARD_MISSION_SEQUENCE,
    build_runtime_graph_plan,
)
from coord_smith.missions.names import (
    ALL_MISSIONS,
    BROWSER_FACING_MISSIONS,
    RELEASED_MISSIONS,
)

# ---- registry shape ---------------------------------------------------


def test_released_missions_has_exactly_six_entries() -> None:
    """The released set is six: 3 per-run + 3 per-step."""
    assert len(RELEASED_MISSIONS) == 6


def test_released_missions_contains_canonical_six() -> None:
    """The six canonical missions are present and ordered per-run-first."""
    assert RELEASED_MISSIONS == (
        "attach_session",
        "prepare_session",
        "step_observe",
        "step_dispatch",
        "step_capture",
        "run_completion",
    )


def test_all_missions_equals_released_missions() -> None:
    """Every mission is released — no modeled / control-only tier."""
    assert ALL_MISSIONS == RELEASED_MISSIONS


def test_browser_facing_missions_equals_released_missions() -> None:
    """All released missions are browser-facing (no non-browser tier)."""
    assert BROWSER_FACING_MISSIONS == RELEASED_MISSIONS


def test_forward_mission_sequence_aligns_with_released_missions() -> None:
    """The forward sequence used by transition validation matches the registry."""
    assert FORWARD_MISSION_SEQUENCE == RELEASED_MISSIONS


# ---- plan node naming ------------------------------------------------


def test_runtime_graph_plan_has_six_released_nodes() -> None:
    """``build_runtime_graph_plan`` exposes six suffixed node names."""
    plan = build_runtime_graph_plan()
    assert len(plan.released_nodes) == 6
    assert plan.released_nodes == tuple(
        f"{name}_node" for name in RELEASED_MISSIONS
    )


def test_runtime_graph_plan_ceiling_is_runcompletion() -> None:
    """The plan's ceiling is ``runCompletion`` — the only valid ceiling."""
    plan = build_runtime_graph_plan()
    assert plan.approved_scope_ceiling == "runCompletion"


# ---- topology derivation per step count -----------------------------


class _FakeAdapter:
    async def execute(self, request: object) -> object:  # pragma: no cover
        raise RuntimeError("compile-time fake; should not execute")


def _build_test_graph(steps: list[Step], tmp_path: Path):
    return build_released_scope_execution_graph(
        adapter=_FakeAdapter(),  # type: ignore[arg-type]
        run=ReleasedRunContext(run_root=tmp_path),
        session_ref="s",
        expected_auth_state="authenticated",
        target_page_url="https://example.com",
        site_identity="example",
        recipe_steps=steps,
    )


def test_zero_step_topology_skips_step_block(tmp_path: Path) -> None:
    """N=0 → graph skips the per-step trio entirely."""
    compiled = _build_test_graph(steps=[], tmp_path=tmp_path)
    nodes = set(compiled.nodes)
    assert "attach_session_node" in nodes
    assert "prepare_session_node" in nodes
    assert "run_completion_node" in nodes
    assert not any(name.startswith("step_observe_") for name in nodes)
    assert not any(name.startswith("step_dispatch_") for name in nodes)
    assert not any(name.startswith("step_capture_") for name in nodes)


def test_one_step_topology_materializes_single_observe_dispatch_capture(
    tmp_path: Path,
) -> None:
    """N=1 → exactly one of each per-step node, indexed at 0."""
    compiled = _build_test_graph(
        steps=[Step(name="only", coord=StepCoord(x=1, y=2))],
        tmp_path=tmp_path,
    )
    nodes = set(compiled.nodes)
    assert "step_observe_0_node" in nodes
    assert "step_dispatch_0_node" in nodes
    assert "step_capture_0_node" in nodes
    assert "step_observe_1_node" not in nodes


def test_three_step_topology_materializes_nine_per_step_nodes(
    tmp_path: Path,
) -> None:
    """N=3 → 9 per-step nodes (observe/dispatch/capture × 3)."""
    compiled = _build_test_graph(
        steps=[
            Step(name="a", coord=StepCoord(x=1, y=1)),
            Step(name="b", coord=StepCoord(x=2, y=2)),
            Step(name="c", coord=StepCoord(x=3, y=3)),
        ],
        tmp_path=tmp_path,
    )
    nodes = set(compiled.nodes)
    for idx in range(3):
        assert f"step_observe_{idx}_node" in nodes
        assert f"step_dispatch_{idx}_node" in nodes
        assert f"step_capture_{idx}_node" in nodes
    assert "step_observe_3_node" not in nodes
