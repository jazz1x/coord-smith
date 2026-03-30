"""Unit tests for runtime graph transition logic."""

from ez_ax.graph.runtime_graph import (
    RuntimeGraphPlan,
    TransitionDecision,
    _expected_predecessor,
    _node_name,
    append_transition_checkpoint,
    build_runtime_graph_plan,
    evaluate_and_record_forward_transition,
    evaluate_forward_transition,
    transition_artifact_from_decision,
)
from ez_ax.models.checkpoint import TransitionCheckpointCollection
from ez_ax.models.runtime import RuntimeState
from ez_ax.models.transition import TransitionArtifact


def test_build_runtime_graph_plan_returns_complete_structure() -> None:
    """Verify graph plan contains all required node families and ceiling."""
    plan = build_runtime_graph_plan()

    assert isinstance(plan, RuntimeGraphPlan)
    assert len(plan.released_nodes) > 0
    assert len(plan.modeled_nodes) == 0  # All missions are now released
    assert len(plan.control_nodes) > 0
    assert plan.approved_scope_ceiling == "runCompletion"


def test_node_name_formatting() -> None:
    """Verify node naming convention."""
    node = _node_name("attach_session")
    assert node == "attach_session_node"


def test_expected_predecessor_for_second_mission() -> None:
    """Verify predecessor lookup for non-first mission."""
    pred = _expected_predecessor("prepare_session")
    assert pred == "attach_session"


def test_expected_predecessor_for_first_mission() -> None:
    """Verify no predecessor for initial mission."""
    pred = _expected_predecessor("attach_session")
    assert pred is None


def test_transition_decision_success() -> None:
    """Verify successful transition decision structure."""
    decision = TransitionDecision(allowed=True, stop_reason="none")

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.detail is None


def test_transition_decision_failure_with_detail() -> None:
    """Verify failed transition decision includes detail."""
    detail_msg = "Target out of scope"
    decision = TransitionDecision(
        allowed=False, stop_reason="mission_out_of_scope", detail=detail_msg
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.detail == detail_msg


def test_evaluate_forward_transition_allows_first_mission() -> None:
    """Verify first mission (attach_session) is allowed from no predecessor."""
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"


def test_evaluate_forward_transition_rejects_out_of_scope() -> None:
    """Verify transitions above scope ceiling are rejected."""
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"


def test_evaluate_forward_transition_requires_evidence() -> None:
    """Verify missing evidence blocks transition."""
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"


def test_evaluate_forward_transition_enforces_predecessor_order() -> None:
    """Verify wrong predecessor blocks transition."""
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"


def test_transition_artifact_from_decision_captures_decision() -> None:
    """Verify artifact correctly encapsulates decision context."""
    decision = TransitionDecision(allowed=True, stop_reason="none")

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert isinstance(artifact, TransitionArtifact)
    assert artifact.allowed is True
    assert artifact.predecessor_mission == "prepare_session"
    assert artifact.target_mission == "benchmark_validation"


def test_append_transition_checkpoint_extends_collection() -> None:
    """Verify appending creates new collection with checkpoint."""
    initial = TransitionCheckpointCollection()
    decision = TransitionDecision(allowed=True, stop_reason="none")

    extended = append_transition_checkpoint(
        collection=initial,
        predecessor_mission=None,
        target_mission="attach_session",
        decision=decision,
    )

    assert len(extended.transitions) == 1
    assert extended.transitions[0].target_mission == "attach_session"


def test_evaluate_and_record_forward_transition_records_first_allowed_transition() -> (
    None
):
    """Verify first transition evaluated and recorded with None predecessor."""
    state = RuntimeState(run_id="run-001")
    state.set_current_mission("python_validation_execution")  # Not a released mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="attach_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert len(state.transition_checkpoints.transitions) == 1
    checkpoint = state.transition_checkpoints.transitions[0]
    assert checkpoint.target_mission == "attach_session"
    assert checkpoint.predecessor_mission is None


def test_evaluate_and_record_forward_transition_records_second_transition_with_predecessor() -> (
    None
):
    """Verify second transition uses latest checkpoint as predecessor."""
    state = RuntimeState(run_id="run-001")
    state.set_current_mission("python_validation_execution")

    # Record first transition
    evaluate_and_record_forward_transition(
        state=state,
        target_mission="attach_session",
        required_evidence_ready=True,
    )

    # Record second transition (should use attach_session as predecessor)
    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert len(state.transition_checkpoints.transitions) == 2
    second_checkpoint = state.transition_checkpoints.transitions[1]
    assert second_checkpoint.target_mission == "prepare_session"
    assert second_checkpoint.predecessor_mission == "attach_session"


def test_evaluate_and_record_forward_transition_respects_explicit_current_mission() -> (
    None
):
    """Verify explicit current_mission parameter sets predecessor for second transition."""
    state = RuntimeState(run_id="run-001")
    state.set_current_mission("python_validation_execution")

    # Record first transition to set checkpoint
    evaluate_and_record_forward_transition(
        state=state,
        target_mission="attach_session",
        required_evidence_ready=True,
    )

    # Use explicit current_mission to override
    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="prepare_session",
        required_evidence_ready=True,
        current_mission="attach_session",
    )

    assert decision.allowed is True
    second_checkpoint = state.transition_checkpoints.transitions[1]
    assert second_checkpoint.predecessor_mission == "attach_session"


def test_evaluate_and_record_forward_transition_records_blocked_transition() -> (
    None
):
    """Verify blocked transition is still recorded in checkpoint collection."""
    state = RuntimeState(run_id="run-001")
    state.set_current_mission("python_validation_execution")

    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="attach_session",
        required_evidence_ready=False,  # Missing evidence blocks it
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert len(state.transition_checkpoints.transitions) == 1
    checkpoint = state.transition_checkpoints.transitions[0]
    assert checkpoint.allowed is False
