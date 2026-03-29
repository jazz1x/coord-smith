"""Test that released missions match PRD specification."""

from ez_ax.missions.names import (
    BROWSER_FACING_MISSIONS,
    MODELED_MISSIONS,
    RELEASED_MISSIONS,
)


def test_released_missions_match_prd_specification() -> None:
    """Verify released scope includes all 12 missions from PRD section 'Release Boundary'."""
    # PRD lines 47-60: Released implementation scope includes all 12 missions:
    # - attach_session (PRD: "attach")
    # - prepare_session (PRD: "prepareSession")
    # - benchmark_validation (PRD: "benchmark validation")
    # - page_ready_observation (PRD: "pageReadyObserved")
    # - sync_observation (PRD: "syncObservation")
    # - target_actionability_observation (PRD: "targetActionabilityObservation")
    # - armed_state_entry (PRD: "armedStateEntry")
    # - trigger_wait (PRD: "triggerWait")
    # - click_dispatch (PRD: "clickDispatch")
    # - click_completion (PRD: "clickCompletion")
    # - success_observation (PRD: "successObservation")
    # - run_completion (PRD: "runCompletion")
    expected_released_missions = (
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    )
    assert RELEASED_MISSIONS == expected_released_missions


def test_released_missions_count_matches_prd() -> None:
    """Verify exactly 12 released missions as specified in PRD Release Boundary."""
    # PRD specifies 12 released missions covering full pipeline from attach to runCompletion
    assert len(RELEASED_MISSIONS) == 12


def test_released_missions_are_browser_facing() -> None:
    """Verify all released missions are marked as browser-facing (authority boundary)."""
    # PRD System Boundary: "OpenClaw is the only browser-facing execution actor"
    # Released missions are handed to OpenClaw, so they must be browser-facing
    for mission in RELEASED_MISSIONS:
        assert mission in BROWSER_FACING_MISSIONS


def test_released_missions_not_modeled() -> None:
    """Verify no released missions are in the modeled-only set."""
    # PRD Release Boundary clearly separates released from modeled stages
    released_set = set(RELEASED_MISSIONS)
    modeled_set = set(MODELED_MISSIONS)
    intersection = released_set & modeled_set
    assert (
        not intersection
    ), f"Released and modeled missions must be disjoint, but found: {intersection}"


def test_released_scope_includes_intentional_stop_clause() -> None:
    """Verify 'intentional stop at released ceiling' is part of released scope specification.

    PRD Release Boundary (lines 47-61):
    'Released implementation scope:
    - attach
    - prepareSession
    - benchmark validation
    - pageReadyObserved
    - syncObservation
    - targetActionabilityObservation
    - armedStateEntry
    - triggerWait
    - clickDispatch
    - clickCompletion
    - successObservation
    - runCompletion
    - intentional stop at the released ceiling'

    The released scope is defined as 12 missions that execute sequentially from
    attach to runCompletion, followed by an intentional stop (no further execution
    beyond runCompletion).

    This test documents that the released scope specification includes both:
    1. All 12 missions executed in sequence
    2. An intentional stop that prevents execution beyond runCompletion
    """
    # The 12 released missions must exist and be in the correct order
    assert len(RELEASED_MISSIONS) == 12, (
        "Released scope must contain exactly 12 missions before the intentional stop"
    )

    # The final mission must be runCompletion (the released ceiling)
    assert RELEASED_MISSIONS[-1] == "run_completion", (
        "Released scope final mission must be 'run_completion' at the ceiling"
    )

    # Verify the missions proceed in the expected order with runCompletion as the final,
    # establishing the "intentional stop at the released ceiling" requirement
    expected_sequence_end = [
        "success_observation",
        "run_completion",
    ]
    actual_sequence_end = list(RELEASED_MISSIONS[-2:])
    assert actual_sequence_end == expected_sequence_end, (
        f"Released scope must end with success_observation -> run_completion sequence; "
        f"expected {expected_sequence_end}, got {actual_sequence_end}"
    )


def test_released_scope_marks_boundary_at_page_ready_observation() -> None:
    """Verify page_ready_observation marks the boundary within released scope.

    PRD Release Boundary (lines 47-61): Lists all 12 released missions in order:
    1. attach
    2. prepareSession
    3. benchmark validation
    4. pageReadyObserved        <- boundary marker
    5. syncObservation          <- first mission below boundary
    ... (7 more missions)
    12. runCompletion

    page_ready_observation is the 4th mission in the released scope and marks
    the boundary: earlier missions (attach, prepare, benchmark) handle pre-flight
    setup; later missions (sync onwards) handle execution and observational phases.

    This explicit boundary marking helps structure the released execution pipeline.
    """
    # Verify page_ready_observation exists and is at the correct position (index 3)
    expected_position = 3
    actual_mission = RELEASED_MISSIONS[expected_position]
    assert actual_mission == "page_ready_observation", (
        f"page_ready_observation must be at position {expected_position} "
        f"(4th in the 1-indexed list); found {actual_mission} instead"
    )

    # Verify missions before the boundary (setup phase)
    setup_missions = list(RELEASED_MISSIONS[:expected_position])
    expected_setup = [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
    ]
    assert setup_missions == expected_setup, (
        f"Missions before page_ready_observation must be setup phase; "
        f"expected {expected_setup}, got {setup_missions}"
    )

    # Verify missions after the boundary (execution and observation phase)
    execution_missions = list(RELEASED_MISSIONS[expected_position + 1 :])
    expected_execution_start = [
        "sync_observation",
        "target_actionability_observation",
    ]
    assert (
        execution_missions[: len(expected_execution_start)] == expected_execution_start
    ), (
        f"Missions after page_ready_observation must start with execution phase; "
        f"expected {expected_execution_start}, got {execution_missions[:2]}"
    )
