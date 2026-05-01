import pytest

from ez_ax.models.runtime import (
    RuntimeState,
    effective_scope_ceiling,
    format_scope_ceiling_detail,
    mission_is_within_approved_scope,
    mission_lifecycle,
)
from ez_ax.models.transition import build_transition_artifact


def test_runtime_state_defaults_match_bootstrap_contract() -> None:
    state = RuntimeState(run_id="run-001")

    assert state.approved_scope_ceiling == "runCompletion"
    assert state.current_anchor == "pythonRuntimeBootstrapCreated"
    assert state.mission_state.mission_name == state.current_mission
    assert state.release_status == "released"


def test_set_current_mission_updates_release_status_for_control_mission() -> None:
    state = RuntimeState(run_id="run-001")

    state.set_current_mission("python_validation_execution")

    assert state.current_mission == "python_validation_execution"
    assert state.release_status == "control-only"
    assert state.mission_state.mission_name == "python_validation_execution"


def test_set_current_mission_accepts_sync_observation_under_run_completion_ceiling() -> None:
    state = RuntimeState(run_id="run-001")
    state.approved_scope_ceiling = "runCompletion"

    # sync_observation is now released and within runCompletion ceiling
    state.set_current_mission("sync_observation")

    assert state.current_mission == "sync_observation"
    assert state.release_status == "released"
    assert state.mission_state.mission_name == "sync_observation"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_set_current_mission_defaults_unknown_ceiling_to_run_completion() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.approved_scope_ceiling = "unknownCeiling"

    # With unknown ceiling, defaults to runCompletion, allowing all released missions
    state.set_current_mission("sync_observation")

    assert state.current_mission == "sync_observation"
    assert state.release_status == "released"


def test_set_current_mission_allows_page_ready_observation() -> None:
    state = RuntimeState(run_id="run-001")

    state.set_current_mission("page_ready_observation")

    assert state.current_mission == "page_ready_observation"
    assert state.release_status == "released"
    assert state.mission_state.mission_name == "page_ready_observation"


def test_set_current_mission_rejects_unknown_mission_name() -> None:
    state = RuntimeState(run_id="run-001")

    try:
        state.set_current_mission("not_a_real_mission")
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission to be rejected")


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_mission_is_within_scope_defaults_unknown_ceiling_to_run_completion() -> None:
    assert (
        mission_is_within_approved_scope(
            mission_name="attach_session",
            approved_scope_ceiling="unknownCeiling",
        )
        is True
    )
    # sync_observation is now released and within runCompletion default ceiling
    assert (
        mission_is_within_approved_scope(
            mission_name="sync_observation",
            approved_scope_ceiling="unknownCeiling",
        )
        is True
    )
    # run_completion is also within default runCompletion ceiling
    assert (
        mission_is_within_approved_scope(
            mission_name="run_completion",
            approved_scope_ceiling="unknownCeiling",
        )
        is True
    )


def test_mission_is_within_scope_enforces_prepare_session_ceiling() -> None:
    assert (
        mission_is_within_approved_scope(
            mission_name="attach_session",
            approved_scope_ceiling="prepareSession",
        )
        is True
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="prepare_session",
            approved_scope_ceiling="prepareSession",
        )
        is True
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="benchmark_validation",
            approved_scope_ceiling="prepareSession",
        )
        is False
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="page_ready_observation",
            approved_scope_ceiling="prepareSession",
        )
        is False
    )


def test_mission_is_within_scope_enforces_page_ready_observed_ceiling() -> None:
    # Pin the boundary: page_ready_observation is the terminal mission for the
    # pageReadyObserved ceiling.  Anything before it is allowed; anything after
    # it (e.g. sync_observation, run_completion) is rejected.
    assert (
        mission_is_within_approved_scope(
            mission_name="prepare_session",
            approved_scope_ceiling="pageReadyObserved",
        )
        is True
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="page_ready_observation",
            approved_scope_ceiling="pageReadyObserved",
        )
        is True
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="sync_observation",
            approved_scope_ceiling="pageReadyObserved",
        )
        is False
    )
    assert (
        mission_is_within_approved_scope(
            mission_name="run_completion",
            approved_scope_ceiling="pageReadyObserved",
        )
        is False
    )


def test_mission_is_within_approved_scope_rejects_unknown_mission_name() -> None:
    assert (
        mission_is_within_approved_scope(
            mission_name="not_a_real_mission",
            approved_scope_ceiling="pageReadyObserved",
        )
        is False
    )


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_effective_scope_ceiling_defaults_unknown_to_run_completion() -> None:
    assert effective_scope_ceiling("pageReadyObserved") == "pageReadyObserved"
    assert effective_scope_ceiling("prepareSession") == "prepareSession"
    assert effective_scope_ceiling("runCompletion") == "runCompletion"
    assert effective_scope_ceiling("syncEstablished") == "runCompletion"
    assert effective_scope_ceiling("unknownCeiling") == "runCompletion"


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_format_scope_ceiling_detail_includes_defaulting_diagnostics() -> None:
    assert format_scope_ceiling_detail("pageReadyObserved") == "'pageReadyObserved'"
    assert format_scope_ceiling_detail("prepareSession") == "'prepareSession'"
    assert format_scope_ceiling_detail("runCompletion") == "'runCompletion'"
    assert (
        format_scope_ceiling_detail("syncEstablished")
        == "'runCompletion' (input 'syncEstablished' defaulted to 'runCompletion')"
    )


def test_set_current_mission_rejects_page_ready_observation_under_prepare_session_ceiling() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.approved_scope_ceiling = "prepareSession"

    try:
        state.set_current_mission("page_ready_observation")
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
        assert "defaulted to 'pageReadyObserved'" not in str(exc)
    else:
        raise AssertionError("Expected page-ready mission to be rejected")


def test_set_current_mission_rejects_benchmark_validation_under_prepare_session_ceiling() -> (
    None
):
    state = RuntimeState(run_id="run-001")
    state.approved_scope_ceiling = "prepareSession"

    try:
        state.set_current_mission("benchmark_validation")
    except ValueError as exc:
        assert "outside approved scope ceiling" in str(exc)
        assert "'prepareSession'" in str(exc)
    else:
        raise AssertionError("Expected benchmark validation to be rejected")


def test_runtime_state_stores_typed_transition_checkpoint_collection() -> None:
    state = RuntimeState(run_id="run-001")

    assert len(state.transition_checkpoints.transitions) == 0

    state.record_transition_artifact(
        build_transition_artifact(
            predecessor_mission=None,
            target_mission="attach_session",
            allowed=True,
            stop_reason="none",
        )
    )

    assert len(state.transition_checkpoints.transitions) == 1
    assert (
        state.transition_checkpoints.transitions[0].target_mission == "attach_session"
    )


def test_mission_lifecycle_classifies_released_missions() -> None:
    assert mission_lifecycle("attach_session") == "released"
    assert mission_lifecycle("prepare_session") == "released"
    assert mission_lifecycle("benchmark_validation") == "released"
    assert mission_lifecycle("page_ready_observation") == "released"


def test_mission_lifecycle_classifies_additional_released_missions() -> None:
    # All previously-modeled missions are now released
    assert mission_lifecycle("sync_observation") == "released"
    assert mission_lifecycle("target_actionability_observation") == "released"
    assert mission_lifecycle("armed_state_entry") == "released"
    assert mission_lifecycle("trigger_wait") == "released"
    assert mission_lifecycle("click_dispatch") == "released"
    assert mission_lifecycle("click_completion") == "released"
    assert mission_lifecycle("success_observation") == "released"
    assert mission_lifecycle("run_completion") == "released"


def test_mission_lifecycle_classifies_control_only_missions() -> None:
    assert mission_lifecycle("release_gate_evaluation") == "control-only"
    assert mission_lifecycle("retry_or_stop_decision") == "control-only"
    assert mission_lifecycle("work_rag_update") == "control-only"
    assert mission_lifecycle("work_rag_compression") == "control-only"
    assert mission_lifecycle("lesson_promotion") == "control-only"
    assert mission_lifecycle("e2e_replay_or_comparison") == "control-only"
    assert mission_lifecycle("python_validation_execution") == "control-only"


def test_mission_lifecycle_rejects_unknown_mission_name() -> None:
    try:
        mission_lifecycle("not_a_real_mission")
    except ValueError as exc:
        assert "Unknown mission name" in str(exc)
    else:
        raise AssertionError("Expected unknown mission to be rejected")


def test_effective_scope_ceiling_warns_for_unknown_value() -> None:
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = effective_scope_ceiling("totallyUnknownCeiling")

    assert result == "runCompletion"
    assert len(caught) == 1
    assert issubclass(caught[0].category, UserWarning)
    assert "totallyUnknownCeiling" in str(caught[0].message)


def test_effective_scope_ceiling_no_warning_for_known_values() -> None:
    import warnings

    for ceiling in ("prepareSession", "pageReadyObserved", "runCompletion"):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = effective_scope_ceiling(ceiling)
        assert result == ceiling
        assert len(caught) == 0, f"Unexpected warning for known ceiling '{ceiling}'"
