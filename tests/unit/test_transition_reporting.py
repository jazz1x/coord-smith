from ez_ax.graph.runtime_graph import build_runtime_graph_plan, evaluate_forward_transition
from ez_ax.models.failure import failure_code_for_stop_reason
from ez_ax.models.transition import build_transition_artifact
from ez_ax.reporting.summary import (
    summarize_graph_plan,
    summarize_transition_artifact,
    summarize_transition_decision,
)


def test_failure_code_mapping_for_out_of_scope_stop_reason() -> None:
    code = failure_code_for_stop_reason("mission_out_of_scope")
    assert code == "GRAPH_MISSION_OUT_OF_SCOPE"


def test_failure_code_mapping_for_missing_predecessor_stop_reason() -> None:
    code = failure_code_for_stop_reason("missing_predecessor_checkpoint")
    assert code == "GRAPH_MISSING_PREDECESSOR_CHECKPOINT"


def test_failure_code_mapping_for_missing_required_evidence() -> None:
    code = failure_code_for_stop_reason("missing_required_evidence")
    assert code == "GRAPH_MISSING_REQUIRED_EVIDENCE"


def test_failure_code_mapping_for_unknown_target() -> None:
    code = failure_code_for_stop_reason("unknown_target_mission")
    assert code == "GRAPH_UNKNOWN_TARGET_MISSION"


def test_failure_code_mapping_for_mission_out_of_scope() -> None:
    code = failure_code_for_stop_reason("mission_out_of_scope")
    assert code == "GRAPH_MISSION_OUT_OF_SCOPE"


def test_failure_code_mapping_for_none_stop_reason() -> None:
    code = failure_code_for_stop_reason("none")
    assert code == "NONE"


def test_failure_code_mapping_for_unknown_target_is_stable() -> None:
    code = failure_code_for_stop_reason("unknown_target_mission")
    assert code == "GRAPH_UNKNOWN_TARGET_MISSION"


def test_graph_plan_summary_reports_counts_and_ceiling() -> None:
    plan = build_runtime_graph_plan()

    summary = summarize_graph_plan(plan)

    assert f"released={len(plan.released_nodes)}" in summary
    assert f"modeled={len(plan.modeled_nodes)}" in summary
    assert f"control={len(plan.control_nodes)}" in summary
    assert f"ceiling={plan.approved_scope_ceiling}" in summary


def test_transition_summary_emits_failure_code() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="page_ready_observation",
        target_mission="sync_observation",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=page_ready_observation" in summary
    assert "target=sync_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=mission_out_of_scope" in summary
    assert "failure_code=GRAPH_MISSION_OUT_OF_SCOPE" in summary


def test_transition_summary_includes_detail_for_out_of_scope() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="page_ready_observation",
        target_mission="sync_observation",
        decision=decision,
    )

    assert "allowed=false" in summary
    assert "target=sync_observation" in summary
    assert "stop_reason=mission_out_of_scope" in summary
    assert "failure_code=GRAPH_MISSION_OUT_OF_SCOPE" in summary
    assert "predecessor=page_ready_observation" in summary
    assert (
        "detail=Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'"
        in summary
    )


def test_transition_summary_includes_prepare_session_predecessor_on_out_of_scope_target() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="sync_observation",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=prepare_session" in summary
    assert "target=sync_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=mission_out_of_scope" in summary
    assert "failure_code=GRAPH_MISSION_OUT_OF_SCOPE" in summary
    assert (
        "detail=Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'" in summary
    )


def test_transition_summary_includes_none_predecessor_for_out_of_scope_target() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="sync_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="sync_observation",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=none" in summary
    assert "target=sync_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=mission_out_of_scope" in summary
    assert "failure_code=GRAPH_MISSION_OUT_OF_SCOPE" in summary
    assert (
        "detail=Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'" in summary
    )


def test_transition_artifact_captures_predecessor_and_target() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        allowed=False,
        stop_reason="missing_required_evidence",
        detail="missing dom signal",
    )

    summary = summarize_transition_artifact(artifact)

    assert "predecessor=prepare_session" in summary
    assert "target=benchmark_validation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "detail=missing dom signal" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary


def test_transition_artifact_summary_reports_none_predecessor() -> None:
    artifact = build_transition_artifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=True,
        stop_reason="none",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=true" in summary
    assert "predecessor=none" in summary
    assert "target=attach_session" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "detail=" not in summary


def test_transition_artifact_summary_omits_detail_on_success() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        allowed=True,
        stop_reason="none",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=true" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "predecessor=prepare_session" in summary
    assert "target=benchmark_validation" in summary
    assert "detail=" not in summary


def test_transition_artifact_summary_ignores_detail_on_success() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        allowed=True,
        stop_reason="none",
        detail="extra detail should be ignored",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=true" in summary
    assert "predecessor=prepare_session" in summary
    assert "target=benchmark_validation" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "detail=" not in summary


def test_transition_artifact_summary_reports_none_detail_on_failure() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        allowed=False,
        stop_reason="missing_required_evidence",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=false" in summary
    assert "predecessor=prepare_session" in summary
    assert "target=benchmark_validation" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "detail=none" in summary


def test_transition_artifact_summary_reports_none_detail_with_none_predecessor() -> None:
    artifact = build_transition_artifact(
        predecessor_mission=None,
        target_mission="attach_session",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=false" in summary
    assert "predecessor=none" in summary
    assert "target=attach_session" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert "detail=none" in summary


def test_transition_artifact_summary_includes_missing_predecessor_detail() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        allowed=False,
        stop_reason="missing_predecessor_checkpoint",
        detail="Expected predecessor 'attach_session' for 'prepare_session', got 'None'",
    )

    summary = summarize_transition_artifact(artifact)

    assert "allowed=false" in summary
    assert "predecessor=attach_session" in summary
    assert "target=prepare_session" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'attach_session' for 'prepare_session', got 'None'"
        in summary
    )


def test_transition_artifact_summary_reports_out_of_scope_failure_code() -> None:
    artifact = build_transition_artifact(
        predecessor_mission="prepare_session",
        target_mission="sync_observation",
        allowed=False,
        stop_reason="mission_out_of_scope",
        detail="Target mission 'sync_observation' is outside approved scope ceiling 'pageReadyObserved'",
    )

    summary = summarize_transition_artifact(artifact)

    assert "predecessor=prepare_session" in summary
    assert "target=sync_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=mission_out_of_scope" in summary
    assert "failure_code=GRAPH_MISSION_OUT_OF_SCOPE" in summary
    assert (
        "detail=Target mission 'sync_observation' is outside approved scope ceiling "
        "'pageReadyObserved'" in summary
    )


def test_transition_summary_reports_none_predecessor_on_first_mission() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="attach_session",
        decision=decision,
    )

    assert "allowed=true" in summary
    assert "predecessor=none" in summary
    assert "target=attach_session" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "detail=" not in summary


def test_transition_summary_includes_missing_evidence_detail_for_attach_session() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="attach_session",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=none" in summary
    assert "target=attach_session" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary
    assert "detail=Required evidence is missing for mission 'attach_session'" in summary


def test_transition_summary_includes_detail_for_first_mission_with_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="attach_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="attach_session",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=prepare_session" in summary
    assert "target=attach_session" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert "detail=Expected no predecessor before 'attach_session'" in summary


def test_transition_summary_reports_failure_code_for_missing_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="attach_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert "predecessor=attach_session" in summary
    assert "target=benchmark_validation" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "allowed=false" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'prepare_session' for 'benchmark_validation', "
        "got 'attach_session'" in summary
    )


def test_transition_summary_includes_detail_for_missing_predecessor() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="prepare_session",
        decision=decision,
    )

    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "allowed=false" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert "predecessor=none" in summary
    assert "target=prepare_session" in summary
    assert (
        "detail=Expected predecessor 'attach_session' for 'prepare_session', got 'None'"
        in summary
    )


def test_transition_summary_includes_detail_for_missing_evidence() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert "allowed=false" in summary
    assert "predecessor=prepare_session" in summary
    assert "target=benchmark_validation" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary
    assert (
        "detail=Required evidence is missing for mission 'benchmark_validation'"
        in summary
    )


def test_transition_summary_includes_missing_evidence_detail_for_prepare_session() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    summary = summarize_transition_decision(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=decision,
    )

    assert "allowed=false" in summary
    assert "predecessor=attach_session" in summary
    assert "target=prepare_session" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary
    assert (
        "detail=Required evidence is missing for mission 'prepare_session'"
        in summary
    )


def test_transition_summary_reports_failure_code_for_unknown_target() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert "predecessor=prepare_session" in summary
    assert "target=nonexistent_transition_target" in summary
    assert "stop_reason=unknown_target_mission" in summary
    assert "allowed=false" in summary
    assert "failure_code=GRAPH_UNKNOWN_TARGET_MISSION" in summary


def test_transition_summary_includes_detail_for_unknown_target() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="nonexistent_transition_target",
        decision=decision,
    )

    assert "predecessor=prepare_session" in summary
    assert "target=nonexistent_transition_target" in summary
    assert "allowed=false" in summary
    assert "stop_reason=unknown_target_mission" in summary
    assert "failure_code=GRAPH_UNKNOWN_TARGET_MISSION" in summary
    assert "detail=Unknown target mission: nonexistent_transition_target" in summary


def test_transition_summary_reports_success_stop_reason_and_code() -> None:
    decision = evaluate_forward_transition(
        current_mission="attach_session",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="attach_session",
        target_mission="prepare_session",
        decision=decision,
    )

    assert "allowed=true" in summary
    assert "predecessor=attach_session" in summary
    assert "target=prepare_session" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "detail=" not in summary


def test_transition_summary_reports_page_ready_observed_success_path() -> None:
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="benchmark_validation",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert "predecessor=benchmark_validation" in summary
    assert "target=page_ready_observation" in summary
    assert "allowed=true" in summary
    assert "stop_reason=none" in summary
    assert "failure_code=NONE" in summary
    assert "detail=" not in summary


def test_transition_summary_includes_missing_evidence_detail_for_page_ready_observation() -> None:
    decision = evaluate_forward_transition(
        current_mission="benchmark_validation",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=False,
    )

    summary = summarize_transition_decision(
        predecessor_mission="benchmark_validation",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert "predecessor=benchmark_validation" in summary
    assert "target=page_ready_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_required_evidence" in summary
    assert "failure_code=GRAPH_MISSING_REQUIRED_EVIDENCE" in summary
    assert (
        "detail=Required evidence is missing for mission 'page_ready_observation'"
        in summary
    )


def test_transition_summary_includes_missing_predecessor_detail_for_page_ready_observation() -> None:
    decision = evaluate_forward_transition(
        current_mission="prepare_session",
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="prepare_session",
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert "predecessor=prepare_session" in summary
    assert "target=page_ready_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'benchmark_validation' for 'page_ready_observation', "
        "got 'prepare_session'" in summary
    )


def test_transition_summary_includes_none_predecessor_for_page_ready_observation() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="page_ready_observation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="page_ready_observation",
        decision=decision,
    )

    assert "predecessor=none" in summary
    assert "target=page_ready_observation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'benchmark_validation' for 'page_ready_observation', "
        "got 'None'" in summary
    )


def test_transition_summary_includes_none_predecessor_for_benchmark_validation() -> None:
    decision = evaluate_forward_transition(
        current_mission=None,
        target_mission="benchmark_validation",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission=None,
        target_mission="benchmark_validation",
        decision=decision,
    )

    assert "predecessor=none" in summary
    assert "target=benchmark_validation" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'prepare_session' for 'benchmark_validation', "
        "got 'None'" in summary
    )


def test_transition_summary_includes_incorrect_predecessor_for_prepare_session() -> None:
    decision = evaluate_forward_transition(
        current_mission="page_ready_observation",
        target_mission="prepare_session",
        approved_scope_ceiling="pageReadyObserved",
        required_evidence_ready=True,
    )

    summary = summarize_transition_decision(
        predecessor_mission="page_ready_observation",
        target_mission="prepare_session",
        decision=decision,
    )

    assert decision.allowed is False
    assert "predecessor=page_ready_observation" in summary
    assert "target=prepare_session" in summary
    assert "allowed=false" in summary
    assert "stop_reason=missing_predecessor_checkpoint" in summary
    assert "failure_code=GRAPH_MISSING_PREDECESSOR_CHECKPOINT" in summary
    assert (
        "detail=Expected predecessor 'attach_session' for 'prepare_session', "
        "got 'page_ready_observation'" in summary
    )
