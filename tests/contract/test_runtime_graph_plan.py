import pytest

from ez_ax.graph.runtime_graph import (
    append_transition_checkpoint,
    build_runtime_graph_plan,
    evaluate_and_record_forward_transition,
    evaluate_forward_transition,
    transition_artifact_from_decision,
)
from ez_ax.models.checkpoint import TransitionCheckpointCollection
from ez_ax.models.runtime import RuntimeState
from ez_ax.models.transition import build_transition_artifact


def test_graph_plan_includes_all_released_missions() -> None:
    plan = build_runtime_graph_plan()

    # All 12 missions are now released (pageReadyObserved is still the graph plan ceiling,
    # but RELEASED_MISSIONS includes all 12)
    assert "attach_session_node" in plan.released_nodes
    assert "page_ready_observation_node" in plan.released_nodes
    assert "sync_observation_node" in plan.released_nodes
    assert "run_completion_node" in plan.released_nodes

    # No modeled-only missions exist
    assert len(plan.modeled_nodes) == 0
    assert plan.approved_scope_ceiling == "pageReadyObserved"


def test_forward_transition_allows_released_linear_progression() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_allows_first_mission_without_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_allows_attach_under_prepare_session_ceiling() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="prepareSession",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_allows_prepare_session_under_prepare_session_ceiling() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="prepareSession",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_accepts_released_under_default_ceiling() -> (
    None
):
    # unknownCeiling now defaults to runCompletion, so sync_observation is allowed
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="unknownCeiling",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"


def test_forward_transition_rejects_benchmark_validation_under_prepare_session_ceiling() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="prepareSession",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        decision.detail
        == "Target mission 'benchmark_validation' is outside approved scope ceiling "
        "'prepareSession'"
    )


def test_forward_transition_rejects_predecessor_on_first_mission() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert decision.detail == "Expected no predecessor before 'attach_session'"


def test_forward_transition_rejects_missing_evidence_on_first_mission() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail == "Required evidence is missing for mission 'attach_session'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_detail() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="attach_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail == "Required evidence is missing for mission 'attach_session'"
    )


def test_transition_artifact_from_decision_preserves_success_detail_none() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="attach_session",
        decision=decision,
    )

    assert artifact.allowed is True
    assert artifact.stop_reason == "none"
    assert artifact.failure_code == "NONE"
    assert artifact.detail is None


def test_transition_artifact_from_decision_preserves_success_detail_none_for_prepare_session() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is True
    assert artifact.stop_reason == "none"
    assert artifact.failure_code == "NONE"
    assert artifact.detail is None


def test_transition_artifact_from_decision_preserves_success_detail_none_for_benchmark() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is True
    assert artifact.stop_reason == "none"
    assert artifact.failure_code == "NONE"
    assert artifact.detail is None


def test_transition_artifact_from_decision_preserves_success_detail_none_for_page_ready() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="benchmark_validation",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is True
    assert artifact.stop_reason == "none"
    assert artifact.failure_code == "NONE"
    assert artifact.detail is None


def test_transition_artifact_from_decision_preserves_missing_evidence_with_incorrect_predecessor_for_attach_session() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="attach_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail == "Required evidence is missing for mission 'attach_session'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_with_incorrect_predecessor_for_prepare_session() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="page_ready_observation",
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail == "Required evidence is missing for mission 'prepare_session'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_with_incorrect_predecessor_for_page_ready() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_with_incorrect_predecessor_for_benchmark() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="attach_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_transition_artifact_from_decision_preserves_missing_predecessor_for_attach_session() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="attach_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert artifact.detail == "Expected no predecessor before 'attach_session'"


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_missing_evidence() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="page_ready_observation",
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_missing_evidence_and_none_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_unknown_target_detail() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.predecessor_mission == "prepare_session"
    assert artifact.target_mission == "nonexistent_transition_target"
    assert artifact.stop_reason == "unknown_target_mission"
    assert artifact.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert artifact.detail == "Unknown target mission: nonexistent_transition_target"


def test_transition_artifact_from_decision_preserves_unknown_target_detail_with_missing_evidence() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "unknown_target_mission"
    assert artifact.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert artifact.detail == "Unknown target mission: nonexistent_transition_target"


def test_transition_artifact_from_decision_preserves_unknown_target_detail_with_missing_evidence_and_none_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "unknown_target_mission"
    assert artifact.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert artifact.detail == "Unknown target mission: nonexistent_transition_target"


def test_transition_artifact_from_decision_preserves_out_of_scope_detail() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="page_ready_observation",
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_missing_predecessor_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_transition_artifact_from_decision_preserves_prepare_session_missing_evidence_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail == "Required evidence is missing for mission 'prepare_session'"
    )


def test_transition_artifact_from_decision_preserves_benchmark_missing_evidence_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_transition_artifact_from_decision_preserves_page_ready_missing_evidence_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="benchmark_validation",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_transition_artifact_from_decision_preserves_none_predecessor_detail() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail
        == "Expected predecessor 'attach_session' for 'prepare_session', got 'None'"
    )


def test_transition_artifact_from_decision_preserves_unknown_target_detail_with_none_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "unknown_target_mission"
    assert artifact.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert artifact.detail == "Unknown target mission: nonexistent_transition_target"


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_none_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_prepare_session_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_benchmark_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="benchmark_validation",
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_out_of_scope_detail_with_attach_session_predecessor() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="attach_session",
        target_mission="sync_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "mission_out_of_scope"
    assert artifact.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        artifact.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_detail_with_none_predecessor_for_page_ready() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_detail_with_none_predecessor_for_prepare_session() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail == "Required evidence is missing for mission 'prepare_session'"
    )


def test_transition_artifact_from_decision_preserves_missing_predecessor_detail_with_none_predecessor_for_benchmark() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail == "Expected predecessor 'prepare_session' for "
        "'benchmark_validation', got 'None'"
    )


def test_transition_artifact_from_decision_preserves_incorrect_predecessor_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="attach_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail == "Expected predecessor 'prepare_session' for "
        "'benchmark_validation', got 'attach_session'"
    )


def test_transition_artifact_from_decision_preserves_none_predecessor_for_page_ready_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'None'"
    )


def test_transition_artifact_from_decision_preserves_incorrect_predecessor_for_prepare_session_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="page_ready_observation",
        target_mission="prepare_session",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail
        == "Expected predecessor 'attach_session' for 'prepare_session', "
        "got 'page_ready_observation'"
    )


def test_transition_artifact_from_decision_preserves_incorrect_predecessor_for_page_ready_detail() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission="prepare_session",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_predecessor_checkpoint"
    assert artifact.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        artifact.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_transition_artifact_from_decision_preserves_missing_evidence_detail_with_none_predecessor_for_benchmark() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    artifact = transition_artifact_from_decision(
        predecessor_mission=None,
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert artifact.allowed is False
    assert artifact.stop_reason == "missing_required_evidence"
    assert artifact.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        artifact.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_forward_transition_rejects_unknown_target_with_no_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert decision.detail == "Unknown target mission: nonexistent_transition_target"


def test_forward_transition_rejects_unknown_target_with_no_predecessor_missing_evidence() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert decision.detail == "Unknown target mission: nonexistent_transition_target"


def test_forward_transition_unknown_target_precedes_missing_evidence() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert decision.detail == "Unknown target mission: nonexistent_transition_target"


def test_forward_transition_allows_prepare_session_to_benchmark_validation() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_allows_benchmark_validation_to_page_ready() -> None:
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None


def test_forward_transition_rejects_missing_predecessor_checkpoint() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail == "Expected predecessor 'prepare_session' for "
        "'benchmark_validation', got 'attach_session'"
    )


def test_forward_transition_rejects_missing_predecessor_when_current_none() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail
        == "Expected predecessor 'attach_session' for 'prepare_session', got 'None'"
    )


def test_forward_transition_rejects_incorrect_predecessor_for_prepare_session() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail
        == "Expected predecessor 'attach_session' for 'prepare_session', "
        "got 'page_ready_observation'"
    )


def test_forward_transition_rejects_missing_predecessor_for_page_ready_none() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'None'"
    )


def test_forward_transition_rejects_incorrect_predecessor_for_page_ready() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_forward_transition_missing_evidence_precedes_missing_predecessor_on_none() -> (
    None
):
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_forward_transition_rejects_missing_required_evidence() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_forward_transition_rejects_missing_evidence_for_prepare_session() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail == "Required evidence is missing for mission 'prepare_session'"
    )


def test_forward_transition_rejects_missing_predecessor_for_page_ready() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        decision.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_forward_transition_rejects_missing_required_evidence_for_page_ready() -> None:
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_forward_transition_out_of_scope_precedes_missing_evidence() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        decision.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_forward_transition_missing_evidence_precedes_missing_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        decision.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_forward_transition_rejects_modeled_target_beyond_released_ceiling() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        decision.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_forward_transition_rejects_unknown_target_from_released_mission() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert decision.detail == "Unknown target mission: nonexistent_transition_target"


def test_append_transition_checkpoint_builds_ordered_collection() -> None:
    first = append_transition_checkpoint(
        collection=TransitionCheckpointCollection(),
        predecessor_mission=None,
        target_mission="attach_session",
        decision=evaluate_forward_transition(
            current_mission=None,
            target_mission="attach_session",
            approved_scope_ceiling="pageReadyObserved",
            required_evidence_ready=True,
        ),
    )
    second_decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    updated = append_transition_checkpoint(
        collection=first,
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=second_decision,
    )

    assert second_decision.detail is None
    assert len(updated.transitions) == 2
    assert updated.transitions[0].detail is None
    assert updated.transitions[0].failure_code == "NONE"
    assert updated.transitions[-1].target_mission == "prepare_session"
    assert updated.transitions[-1].detail is None
    assert updated.transitions[-1].failure_code == "NONE"


def test_append_transition_checkpoint_preserves_continuity_across_three_successes() -> (
    None
):
    first = append_transition_checkpoint(
        collection=TransitionCheckpointCollection(),
        predecessor_mission=None,
        target_mission="attach_session",
        decision=evaluate_forward_transition(
            current_mission=None,
            target_mission="attach_session",
            approved_scope_ceiling="pageReadyObserved",
            required_evidence_ready=True,
        ),
    )
    second = append_transition_checkpoint(
        collection=first,
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=evaluate_forward_transition(
            current_mission="attach_session",
            target_mission="prepare_session",
            approved_scope_ceiling="pageReadyObserved",
            required_evidence_ready=True,
        ),
    )
    third_decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )
    third = append_transition_checkpoint(
        collection=second,
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        decision=third_decision,
    )

    assert len(third.transitions) == 3
    assert third.transitions[0].target_mission == "attach_session"
    assert third.transitions[1].predecessor_mission == "attach_session"
    assert third.transitions[1].target_mission == "prepare_session"
    assert third.transitions[2].predecessor_mission == "prepare_session"
    assert third.transitions[2].target_mission == "benchmark_validation"
    assert third_decision.failure_code == "NONE"
    assert third_decision.detail is None
    assert third.transitions[2].detail is None
    assert third.transitions[2].failure_code == "NONE"


def test_evaluate_and_record_forward_transition_updates_runtime_state() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission
    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None
    assert state.transition_checkpoints.transitions[-1].failure_code == "NONE"


def test_evaluate_and_record_preserves_continuity_across_three_successes() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    first_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    second_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert first_decision.allowed is True
    assert first_decision.stop_reason == "none"
    assert first_decision.failure_code == "NONE"
    assert first_decision.detail is None
    assert second_decision.allowed is True
    assert second_decision.stop_reason == "none"
    assert second_decision.failure_code == "NONE"
    assert second_decision.detail is None
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[0].target_mission == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[2].detail is None
    assert state.transition_checkpoints.transitions[2].failure_code == "NONE"


def test_evaluate_and_record_derives_predecessor_from_state_when_omitted() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    first_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    second_decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert first_decision.allowed is True
    assert first_decision.stop_reason == "none"
    assert first_decision.failure_code == "NONE"
    assert first_decision.detail is None
    assert second_decision.allowed is True
    assert second_decision.stop_reason == "none"
    assert second_decision.failure_code == "NONE"
    assert second_decision.detail is None
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[2].failure_code == "NONE"
    assert state.transition_checkpoints.transitions[2].detail is None


def test_evaluate_and_record_failure_after_success_keeps_continuity() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        required_evidence_ready=False,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "missing_required_evidence"
    assert failure_decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        failure_decision.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_evaluate_and_record_missing_evidence_at_page_ready_keeps_continuity() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_prepare = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    success_benchmark = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        required_evidence_ready=False,
    )

    assert success_prepare.allowed is True
    assert success_prepare.stop_reason == "none"
    assert success_prepare.failure_code == "NONE"
    assert success_prepare.detail is None
    assert success_benchmark.allowed is True
    assert success_benchmark.stop_reason == "none"
    assert success_benchmark.failure_code == "NONE"
    assert success_benchmark.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "missing_required_evidence"
    assert failure_decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        failure_decision.detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )
    assert len(state.transition_checkpoints.transitions) == 4
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "benchmark_validation"
    )
    assert (
        state.transition_checkpoints.transitions[3].predecessor_mission
        == "benchmark_validation"
    )
    assert (
        state.transition_checkpoints.transitions[3].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[3].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[3].detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_evaluate_and_record_missing_evidence_after_omitted_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="benchmark_validation",
        required_evidence_ready=False,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "missing_required_evidence"
    assert failure_decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert (
        failure_decision.detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_evaluate_and_record_out_of_scope_failure_after_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="sync_observation",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "mission_out_of_scope"
    assert failure_decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        failure_decision.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_out_of_scope_missing_evidence_stays_out_of_scope() -> None:
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="sync_observation",
        required_evidence_ready=False,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "mission_out_of_scope"
    assert failure_decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        failure_decision.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_out_of_scope_after_omitted_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="sync_observation",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "mission_out_of_scope"
    assert failure_decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert (
        failure_decision.detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_unknown_target_failure_after_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "unknown_target_mission"
    assert failure_decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert (
        failure_decision.detail
        == "Unknown target mission: nonexistent_transition_target"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_unknown_target_after_omitted_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="nonexistent_transition_target",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "unknown_target_mission"
    assert failure_decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert (
        failure_decision.detail
        == "Unknown target mission: nonexistent_transition_target"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_missing_predecessor_failure_after_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_mission = state.current_mission
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "missing_predecessor_checkpoint"
    assert failure_decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert (
        failure_decision.detail == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_evaluate_and_record_missing_predecessor_after_omitted_success_keeps_continuity() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_mission = state.current_mission
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )

    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    failure_decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert failure_decision.allowed is False
    assert failure_decision.stop_reason == "missing_predecessor_checkpoint"
    assert failure_decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[1].predecessor_mission
        == "attach_session"
    )
    assert (
        state.transition_checkpoints.transitions[1].target_mission == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[2].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[2].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[2].detail
        == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_failure() -> None:
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission
    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="sync_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="sync_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_with_inferred_predecessor_and_missing_evidence() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="sync_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_with_inferred_predecessor_after_prepare_session() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="sync_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_with_inferred_predecessor_and_missing_evidence_after_prepare_session() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="sync_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_out_of_scope_with_missing_evidence() -> (
    None
):
    state = RuntimeState(run_id="run-001", approved_scope_ceiling="pageReadyObserved")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="sync_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "mission_out_of_scope"
    assert decision.failure_code == "GRAPH_MISSION_OUT_OF_SCOPE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "sync_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSION_OUT_OF_SCOPE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_failure() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_benchmark() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_page_ready() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="prepare_session",
            target_mission="benchmark_validation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 4
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_prepare_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_attach_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="attach_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_attach_session_after_success() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="attach_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="prepare_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_for_prepare_session_with_explicit_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="prepare_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_inferred_predecessor_for_benchmark() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="benchmark_validation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_inferred_predecessor_for_page_ready() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="prepare_session",
            target_mission="benchmark_validation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="page_ready_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 4
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_inferred_predecessor_for_attach_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="attach_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_inferred_predecessor_for_attach_session_without_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="attach_session",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_with_inferred_predecessor_for_attach_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="attach_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected no predecessor before 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_attach_session_with_explicit_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="attach_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "attach_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected no predecessor before 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_evidence_with_incorrect_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="benchmark_validation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'benchmark_validation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_failure() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'prepare_session' for 'benchmark_validation', "
        "got 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'prepare_session' for 'benchmark_validation', "
        "got 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_with_inferred_predecessor_for_page_ready() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_allows_prepare_session_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_allows_prepare_session_with_explicit_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_allows_benchmark_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_allows_benchmark_with_explicit_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_allows_page_ready_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="prepare_session",
            target_mission="benchmark_validation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 4
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_allows_page_ready_with_explicit_current_mission() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="prepare_session",
            target_mission="benchmark_validation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert len(state.transition_checkpoints.transitions) == 4
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert state.transition_checkpoints.transitions[-1].detail is None


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_prepare_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="page_ready_observation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="page_ready_observation",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'attach_session' for 'prepare_session', "
        "got 'page_ready_observation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_prepare_session_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="page_ready_observation",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="prepare_session",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'attach_session' for 'prepare_session', "
        "got 'page_ready_observation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_benchmark() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'prepare_session' for 'benchmark_validation', "
        "got 'attach_session'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_page_ready_with_missing_evidence() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_required_evidence"
    assert decision.failure_code == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_REQUIRED_EVIDENCE"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Required evidence is missing for mission 'page_ready_observation'"
    )


def test_evaluate_and_record_forward_transition_records_missing_predecessor_for_page_ready() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "missing_predecessor_checkpoint"
    assert decision.failure_code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "page_ready_observation"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Expected predecessor 'benchmark_validation' for "
        "'page_ready_observation', got 'prepare_session'"
    )


def test_evaluate_and_record_forward_transition_records_unknown_target_failure() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="nonexistent_transition_target",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_forward_transition_records_unknown_target_with_inferred_predecessor() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="nonexistent_transition_target",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_forward_transition_records_unknown_target_with_inferred_predecessor_after_prepare_session() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission="attach_session",
            target_mission="prepare_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="nonexistent_transition_target",
        required_evidence_ready=True,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert len(state.transition_checkpoints.transitions) == 3
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_forward_transition_records_unknown_target_with_inferred_predecessor_and_missing_evidence() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission=None,
        target_mission="nonexistent_transition_target",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_forward_transition_records_unknown_target_with_missing_evidence() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_mission = state.current_mission

    decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="nonexistent_transition_target",
        required_evidence_ready=False,
    )

    assert decision.allowed is False
    assert decision.stop_reason == "unknown_target_mission"
    assert decision.failure_code == "GRAPH_UNKNOWN_TARGET_MISSION"
    assert len(state.transition_checkpoints.transitions) == 2
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "nonexistent_transition_target"
    )
    assert state.current_mission == initial_mission
    assert (
        state.transition_checkpoints.transitions[-1].failure_code
        == "GRAPH_UNKNOWN_TARGET_MISSION"
    )
    assert (
        state.transition_checkpoints.transitions[-1].detail
        == "Unknown target mission: nonexistent_transition_target"
    )


def test_evaluate_and_record_forward_transition_propagates_order_violation() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="prepare_session",
            target_mission="benchmark_validation",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value) == "Transition order violation: expected predecessor "
        "'attach_session', got 'prepare_session'."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions


def test_evaluate_and_record_order_violation_after_success_keeps_count_unchanged() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="benchmark_validation",
            target_mission="page_ready_observation",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value) == "Transition order violation: expected predecessor "
        "'prepare_session', got 'benchmark_validation'."
    )
    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert (
        state.transition_checkpoints.transitions[-1].target_mission == "prepare_session"
    )


def test_evaluate_and_record_omitted_mission_uses_checkpoint_over_stale_state() -> None:
    state = RuntimeState(run_id="run-001")
    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )
    success_decision = evaluate_and_record_forward_transition(
        state=state,
        current_mission="attach_session",
        target_mission="prepare_session",
        required_evidence_ready=True,
    )
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    state.current_mission = "benchmark_validation"

    decision = evaluate_and_record_forward_transition(
        state=state,
        target_mission="benchmark_validation",
        required_evidence_ready=True,
    )

    assert success_decision.allowed is True
    assert success_decision.stop_reason == "none"
    assert success_decision.failure_code == "NONE"
    assert success_decision.detail is None
    assert decision.allowed is True
    assert decision.stop_reason == "none"
    assert decision.failure_code == "NONE"
    assert decision.detail is None
    assert len(state.transition_checkpoints.transitions) == initial_count + 1
    assert state.transition_checkpoints.transitions[:-1] == initial_transitions
    assert (
        state.transition_checkpoints.transitions[-1].predecessor_mission
        == "prepare_session"
    )
    assert (
        state.transition_checkpoints.transitions[-1].target_mission
        == "benchmark_validation"
    )
    assert (
        state.current_mission
        == state.transition_checkpoints.transitions[-1].target_mission
    )


def test_evaluate_and_record_omitted_mission_empty_checkpoints_uses_state_fallback() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.current_mission = "attach_session"
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            target_mission="prepare_session",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions


def test_evaluate_and_record_explicit_mission_empty_checkpoints_preserves_state() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="prepare_session",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions


def test_evaluate_and_record_explicit_mission_empty_checkpoints_guard_precedes_missing() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="prepare_session",
            required_evidence_ready=False,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions


def test_evaluate_and_record_omitted_mission_empty_checkpoints_guard_precedes_unknown() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            target_mission="nonexistent_transition_target",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage


def test_evaluate_and_record_omitted_empty_guard_precedes_unknown_missing() -> None:
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            target_mission="nonexistent_transition_target",
            required_evidence_ready=False,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status


def test_evaluate_and_record_explicit_mission_empty_checkpoints_guard_precedes_unknown() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="nonexistent_transition_target",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage


def test_evaluate_and_record_explicit_empty_guard_precedes_unknown_missing() -> None:
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="nonexistent_transition_target",
            required_evidence_ready=False,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage


def test_evaluate_and_record_omitted_empty_checkpoints_guard_precedes_out_of_scope() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            target_mission="sync_observation",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status


def test_evaluate_and_record_explicit_empty_checkpoints_guard_precedes_out_of_scope() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="sync_observation",
            required_evidence_ready=True,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage


def test_evaluate_and_record_explicit_empty_guard_precedes_out_of_scope_missing() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            current_mission="attach_session",
            target_mission="sync_observation",
            required_evidence_ready=False,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage


def test_evaluate_and_record_omitted_empty_guard_precedes_out_of_scope_missing() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    initial_count = len(state.transition_checkpoints.transitions)
    initial_transitions = state.transition_checkpoints.transitions
    initial_mission = state.current_mission
    initial_run_status = state.run_status
    initial_highest_reached_stage = state.highest_reached_stage

    with pytest.raises(ValueError) as exc_info:
        evaluate_and_record_forward_transition(
            state=state,
            target_mission="sync_observation",
            required_evidence_ready=False,
        )

    assert (
        str(exc_info.value)
        == "First transition artifact must not declare a predecessor mission."
    )
    assert len(state.transition_checkpoints.transitions) == initial_count
    assert state.transition_checkpoints.transitions == initial_transitions
    assert state.current_mission == initial_mission
    assert state.run_status == initial_run_status
    assert state.highest_reached_stage == initial_highest_reached_stage
