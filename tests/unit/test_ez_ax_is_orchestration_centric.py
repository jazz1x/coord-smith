"""Tests verifying the PRD requirement: ez-ax is orchestration-centric.

PRD clause (System Boundary, line 20):
'ez-ax is orchestration-centric'

This verifies that the ez-ax runtime focuses on orchestration—managing mission
sequencing, state transitions, validation, and stopping decisions—rather than
performing browser-facing operations directly.
"""

from __future__ import annotations

from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph
from ez_ax.missions.names import RELEASED_MISSIONS
from ez_ax.models.runtime import RuntimeState


def test_released_scope_runtime_owns_orchestration_logic() -> None:
    """Verify that ez-ax owns orchestration: mission sequencing, state management, transitions.

    PRD System Boundary (line 20): 'ez-ax is orchestration-centric'

    The ez-ax runtime must be focused on orchestration—sequencing missions,
    managing state transitions, validating evidence, and making stopping
    decisions. Execution is delegated to adapters.

    This test verifies that:
    1. The runtime defines the mission sequence (RELEASED_MISSIONS)
    2. The RuntimeState owns the orchestration state (current_mission, mission_state)
    3. The released-scope execution graph manages transitions between missions
    """
    # Mission sequence is defined by ez-ax orchestration
    assert RELEASED_MISSIONS == (
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ), "Mission sequence is part of ez-ax orchestration"

    # RuntimeState owns orchestration state
    state = RuntimeState(
        run_id="test-run-1",
        approved_scope_ceiling="pageReadyObserved",
    )
    assert state.current_mission == "attach_session", "RuntimeState tracks current mission"
    assert hasattr(state, "transition_checkpoints"), "RuntimeState owns transition checkpoints"
    assert hasattr(state, "mission_state"), "RuntimeState owns mission state"
    assert hasattr(state, "set_current_mission"), "RuntimeState manages mission transitions"

    # Verify orchestration functions exist and are owned by ez-ax
    from ez_ax.graph.runtime_graph import (
        evaluate_and_record_forward_transition,
        evaluate_forward_transition,
    )

    assert callable(evaluate_forward_transition), (
        "ez-ax owns transition evaluation (orchestration logic)"
    )
    assert callable(evaluate_and_record_forward_transition), (
        "ez-ax owns transition recording (orchestration logic)"
    )


def test_released_scope_execution_delegates_to_adapter() -> None:
    """Verify that execution is delegated to the adapter, not performed by orchestration.

    PRD System Boundary (line 20): 'ez-ax is orchestration-centric'

    The orchestration runtime must delegate ALL browser-facing execution to the
    adapter. The ez-ax runtime should not perform browser operations.

    This test verifies the separation: orchestration owns sequencing, the adapter
    owns execution.
    """
    from ez_ax.adapters.openclaw.client import (
        OpenClawAdapter,
    )

    # OpenClawAdapter protocol defines the execution boundary
    assert hasattr(OpenClawAdapter, "execute"), (
        "Execution is delegated through OpenClawAdapter protocol"
    )

    # Verify that langgraph_released_execution accepts an adapter parameter
    import inspect

    sig = inspect.signature(run_released_scope_via_langgraph)
    assert "adapter" in sig.parameters, (
        "Released-scope runtime accepts adapter parameter (execution delegation)"
    )


def test_orchestration_logic_does_not_perform_browser_operations() -> None:
    """Verify that core orchestration modules don't contain browser operation code.

    PRD System Boundary (line 20): 'ez-ax is orchestration-centric'

    Core orchestration modules (graph, models, evidence) should not contain
    direct browser control code. They should focus on mission sequencing,
    state management, validation, and stopping logic.

    This test verifies separation: orchestration logic is isolated from execution.
    """
    from ez_ax.evidence import envelope
    from ez_ax.graph import runtime_graph
    from ez_ax.models import runtime

    # Check that orchestration modules don't import browser control libs
    module_names = [
        runtime_graph.__name__,
        runtime.__name__,
        envelope.__name__,
    ]

    forbidden_libs = {
        "playwright",
        "pyppeteer",
        "selenium",
        "chromium",
    }

    import sys

    for module_name in module_names:
        module = sys.modules.get(module_name)
        if module and hasattr(module, "__dict__"):
            for imported_name in module.__dict__:
                # Check if any forbidden lib is imported in this module
                imported_obj = module.__dict__[imported_name]
                obj_module = getattr(imported_obj, "__module__", "")
                for forbidden in forbidden_libs:
                    assert forbidden not in obj_module, (
                        f"Orchestration module {module_name} must not import {forbidden}"
                    )
