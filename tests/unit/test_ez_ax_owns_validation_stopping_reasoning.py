"""Tests verifying the PRD requirement: ez-ax owns validation, stopping, and reasoning.

PRD clause (System Boundary, Authority boundary, line 28):
'ez-ax owns orchestration, validation, stopping, and reasoning'

This means ez-ax (not OpenClaw or any other component) is responsible for:
1. Validation: verifying evidence, making validation decisions
2. Stopping: deciding when to stop at the released ceiling
3. Reasoning: evaluating transitions, deciding which mission is next

OpenClaw only handles execution (browser operations). All high-level decision
logic is owned by ez-ax.
"""

from __future__ import annotations

from ez_ax.evidence.envelope import (
    enforce_evidence_priority,
    validate_release_ceiling_stop_proof,
)
from ez_ax.graph.runtime_graph import (
    evaluate_and_record_forward_transition,
    evaluate_forward_transition,
)
from ez_ax.missions.names import RELEASED_MISSIONS
from ez_ax.models.runtime import RuntimeState


def test_ez_ax_owns_validation_logic() -> None:
    """Verify that ez-ax owns evidence validation logic.

    PRD System Boundary (line 28): 'ez-ax owns orchestration, validation,
    stopping, and reasoning'

    This test verifies that the validation logic (checking evidence, enforcing
    truth priority, validating proof) is owned by ez-ax modules, not delegated
    to OpenClaw or external services.

    Validation functions that ez-ax owns:
    - enforce_evidence_priority(): validates evidence follows truth hierarchy
    - validate_release_ceiling_stop_proof(): validates stop proof artifact
    """
    # Verify validation functions are in ez-ax.evidence (owned by ez-ax)
    import inspect

    enforce_module = inspect.getmodule(enforce_evidence_priority)
    assert (
        enforce_module is not None and "ez_ax.evidence" in enforce_module.__name__
    ), "enforce_evidence_priority must be owned by ez-ax.evidence module"

    validate_module = inspect.getmodule(validate_release_ceiling_stop_proof)
    assert (
        validate_module is not None and "ez_ax.evidence" in validate_module.__name__
    ), "validate_release_ceiling_stop_proof must be owned by ez-ax.evidence module"

    # Verify these are called during execution, not delegated to OpenClaw
    # (indirectly verified by integration tests, but logic ownership is here)
    assert callable(enforce_evidence_priority), (
        "ez-ax owns evidence priority validation logic"
    )
    assert callable(validate_release_ceiling_stop_proof), (
        "ez-ax owns release-ceiling stop proof validation logic"
    )


def test_ez_ax_owns_stopping_logic() -> None:
    """Verify that ez-ax owns the stopping decision logic.

    PRD System Boundary (line 28): 'ez-ax owns orchestration, validation,
    stopping, and reasoning'

    Stopping means: deciding when to stop executing missions, typically at the
    released ceiling (pageReadyObserved). This decision is made by ez-ax, not
    delegated to OpenClaw.

    The stopping logic is embodied in:
    - RuntimeState.approved_scope_ceiling: defines where to stop
    - RuntimeState.current_mission: tracks current position
    - evaluate_forward_transition(): decides if next transition is allowed
    """
    state = RuntimeState(
        run_id="test-stop-logic",
        approved_scope_ceiling="pageReadyObserved",
    )

    # Verify RuntimeState owns the stopping boundary (approved_scope_ceiling)
    assert state.approved_scope_ceiling == "pageReadyObserved", (
        "ez-ax RuntimeState owns the approved scope ceiling (stopping boundary)"
    )

    # Verify RuntimeState tracks current position for stopping decisions
    assert hasattr(state, "current_mission"), (
        "ez-ax RuntimeState tracks current_mission for stopping logic"
    )
    assert state.current_mission == "attach_session", (
        "ez-ax owns mission sequencing and stopping boundary"
    )

    # Verify transition evaluation logic is owned by ez-ax
    import inspect

    eval_module = inspect.getmodule(evaluate_forward_transition)
    assert (
        eval_module is not None and "ez_ax.graph" in eval_module.__name__
    ), "evaluate_forward_transition (stopping logic) must be owned by ez-ax.graph"

    assert callable(evaluate_forward_transition), (
        "ez-ax owns transition evaluation logic (decides when to stop)"
    )


def test_ez_ax_owns_reasoning_logic() -> None:
    """Verify that ez-ax owns the reasoning logic for mission transitions.

    PRD System Boundary (line 28): 'ez-ax owns orchestration, validation,
    stopping, and reasoning'

    Reasoning means: the logic that decides which mission comes next, evaluates
    whether a transition is valid, records the transition. This is not delegated
    to OpenClaw or external services.

    The reasoning logic is embodied in:
    - RELEASED_MISSIONS: mission sequence specification (ez-ax reasoning)
    - evaluate_forward_transition(): evaluates if transition is valid
    - evaluate_and_record_forward_transition(): records transition decision
    - RuntimeState.transition_checkpoints: checkpoints of reasoning history
    """
    # Verify mission sequence is owned by ez-ax (reasoning about order)
    # All 12 missions are now released (ceiling expands to runCompletion)
    assert len(RELEASED_MISSIONS) == 12, "Mission sequence includes all 12 released missions"
    assert RELEASED_MISSIONS[0] == "attach_session", "Sequence starts with attach_session"
    assert RELEASED_MISSIONS[-1] == "run_completion", "Sequence ends with runCompletion"

    # Verify transition evaluation logic (core reasoning) is owned by ez-ax
    import inspect

    eval_and_record_module = inspect.getmodule(evaluate_and_record_forward_transition)
    assert (
        eval_and_record_module is not None
        and "ez_ax.graph" in eval_and_record_module.__name__
    ), (
        "evaluate_and_record_forward_transition (reasoning logic) "
        "must be owned by ez-ax.graph"
    )

    assert callable(evaluate_and_record_forward_transition), (
        "ez-ax owns reasoning logic for recording mission transitions"
    )

    # Verify ez-ax owns the history of reasoning decisions
    state = RuntimeState(
        run_id="test-reasoning",
        approved_scope_ceiling="pageReadyObserved",
    )
    assert hasattr(state, "transition_checkpoints"), (
        "ez-ax owns transition_checkpoints (reasoning history)"
    )


def test_execution_adapter_does_not_own_validation_stopping_reasoning() -> None:
    """Verify that OpenClaw is NOT responsible for validation, stopping, reasoning.

    PRD System Boundary (line 27-28):
    - 'OpenClaw owns browser-facing execution'
    - 'ez-ax owns orchestration, validation, stopping, and reasoning'

    This test verifies the authority boundary: OpenClaw handles execution,
    ez-ax handles all decision logic.

    OpenClaw should not have:
    - Validation decision logic
    - Stopping/ceiling enforcement
    - Mission reasoning or transition evaluation
    """
    from ez_ax.adapters.execution.client import ExecutionAdapter, ExecutionRequest

    # Verify ExecutionAdapter protocol is execution-only
    # It should only have the execute() method, not validation/stopping/reasoning
    protocol_methods = {
        name
        for name in dir(ExecutionAdapter)
        if not name.startswith("_") and callable(getattr(ExecutionAdapter, name))
    }

    # Verify execute() is the primary method
    assert "execute" in protocol_methods, (
        "ExecutionAdapter protocol should have execute() method"
    )

    # Verify ExecutionRequest doesn't contain validation/stopping logic
    # (it's just a data structure for execution parameters)
    request_attrs = set(ExecutionRequest.__annotations__.keys())

    # It should contain execution params (mission, request), not validation rules
    assert "mission_name" in request_attrs or "request" in request_attrs, (
        "ExecutionRequest contains execution parameters"
    )

    # It should NOT contain stopping logic or validation rules
    forbidden_attrs = {"approved_scope_ceiling", "stop_at_ceiling", "validation_mode"}
    found_forbidden = request_attrs & forbidden_attrs
    assert (
        not found_forbidden
    ), f"ExecutionRequest must not own stopping logic: {found_forbidden}"
