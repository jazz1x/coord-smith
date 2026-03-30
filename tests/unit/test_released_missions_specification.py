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


def test_all_stages_are_released() -> None:
    """Verify all 12 stages in the released scope are released, not modeled.

    PRD Release Boundary (line 63):
    'No missions are currently modeled-only. All stages are released.'

    This test verifies the second part of this clause: "All stages are released."
    It confirms that each mission in the released execution pipeline is truly
    released (not modeled) and is part of the complete, contiguous pipeline from
    attach_session through run_completion with no gaps.
    """
    # Verify that RELEASED_MISSIONS contains all 12 stages (the "All stages"
    # part of "All stages are released")
    assert len(RELEASED_MISSIONS) == 12, (
        f"All 12 stages must be part of the released scope; "
        f"found {len(RELEASED_MISSIONS)} stages instead"
    )

    # Verify each released stage is not in the modeled-only set
    # (no released stage is modeled-only)
    released_set = set(RELEASED_MISSIONS)
    modeled_set = set(MODELED_MISSIONS)
    intersection = released_set & modeled_set
    assert (
        not intersection
    ), f"All released stages must be released only, but found modeled: {intersection}"

    # Verify the pipeline is complete and contiguous from attach to runCompletion
    # with no gaps or missing transitions
    expected_pipeline_start = "attach_session"
    expected_pipeline_end = "run_completion"
    assert RELEASED_MISSIONS[0] == expected_pipeline_start, (
        f"Released stages must start with attach_session; "
        f"found {RELEASED_MISSIONS[0]} instead"
    )
    assert RELEASED_MISSIONS[-1] == expected_pipeline_end, (
        f"Released stages must end with run_completion; "
        f"found {RELEASED_MISSIONS[-1]} instead"
    )

    # Verify all stages are present and accounted for (complete set)
    expected_all_stages = (
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
    assert RELEASED_MISSIONS == expected_all_stages, (
        f"Released scope must contain all expected stages in order; "
        f"expected {expected_all_stages}, got {RELEASED_MISSIONS}"
    )


def test_released_scope_implementation_includes_all_missions_below_page_ready_observation() -> None:
    """Verify all released-scope implementation clauses below pageReadyObserved.

    PRD Release Boundary (lines 47-63): Specifies released implementation scope with
    missions below pageReadyObserved forming the execution and observation phase:
    - syncObservation (line 53)
    - targetActionabilityObservation (line 54)
    - armedStateEntry (line 55)
    - triggerWait (line 56)
    - clickDispatch (line 57)
    - clickCompletion (line 58)
    - successObservation (line 59)
    - runCompletion (line 60)

    These 8 missions must:
    1. All be present in the released scope (not modeled-only)
    2. Execute in the correct sequence after pageReadyObserved
    3. Be complete and contiguous (no gaps in the execution pipeline)
    4. Terminate at runCompletion (the released ceiling)

    This test explicitly verifies the released scope implementation meets these
    requirements for missions below the pageReadyObserved boundary.
    """
    # Find the position of page_ready_observation boundary (index 3)
    page_ready_index = 3
    page_ready_mission = RELEASED_MISSIONS[page_ready_index]
    assert page_ready_mission == "page_ready_observation", (
        "page_ready_observation must be at index 3 to establish the boundary"
    )

    # Extract all missions below the boundary (execution phase)
    missions_below_page_ready = list(RELEASED_MISSIONS[page_ready_index + 1 :])

    # Verify these missions exist and match PRD specification
    expected_below_page_ready = [
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    ]
    assert missions_below_page_ready == expected_below_page_ready, (
        f"Missions below pageReadyObserved must be exactly as specified in PRD; "
        f"expected {expected_below_page_ready}, got {missions_below_page_ready}"
    )

    # Verify all these missions are released (not modeled)
    modeled_set = set(MODELED_MISSIONS)
    for mission in missions_below_page_ready:
        assert mission not in modeled_set, (
            f"Mission '{mission}' (below pageReadyObserved) must be released, "
            f"not modeled-only"
        )

    # Verify the pipeline is contiguous from after pageReadyObserved to runCompletion
    assert missions_below_page_ready[0] == "sync_observation", (
        "Execution phase must begin immediately with sync_observation"
    )
    assert missions_below_page_ready[-1] == "run_completion", (
        "Execution phase must terminate at run_completion (released ceiling)"
    )

    # Verify there are exactly 8 missions below the boundary
    # (12 total missions - 4 setup missions = 8 execution missions)
    assert len(missions_below_page_ready) == 8, (
        f"Released scope must have exactly 8 missions below pageReadyObserved "
        f"(execution phase); found {len(missions_below_page_ready)}"
    )


def test_released_scope_implementation_includes_all_missions_above_page_ready_observation() -> None:
    """Verify all released-scope implementation clauses above pageReadyObserved.

    PRD Release Boundary (lines 47-63): Specifies released implementation scope with
    missions above pageReadyObserved forming the setup and observation phase:
    - attach (line 49)
    - prepareSession (line 50)
    - benchmark validation (line 51)
    - pageReadyObserved (line 52)

    These 4 missions must:
    1. All be present in the released scope (not modeled-only)
    2. Execute in the correct sequence before the pageReadyObserved boundary
    3. Be complete and contiguous (no gaps in the setup pipeline)
    4. End at pageReadyObserved (the boundary marker that separates setup from execution)

    This test explicitly verifies the released scope implementation meets these
    requirements for missions above the pageReadyObserved boundary, providing
    a comprehensive counterpart to the below-boundary verification and ensuring
    the entire 12-mission pipeline is properly structured from attach to runCompletion.
    """
    # Find the position of page_ready_observation boundary (index 3)
    page_ready_index = 3
    page_ready_mission = RELEASED_MISSIONS[page_ready_index]
    assert page_ready_mission == "page_ready_observation", (
        "page_ready_observation must be at index 3 to establish the boundary"
    )

    # Extract all missions above/including the boundary (setup phase + boundary marker)
    missions_above_page_ready = list(RELEASED_MISSIONS[: page_ready_index + 1])

    # Verify these missions exist and match PRD specification
    expected_above_page_ready = [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]
    assert missions_above_page_ready == expected_above_page_ready, (
        f"Missions above/at pageReadyObserved must be exactly as specified in PRD; "
        f"expected {expected_above_page_ready}, got {missions_above_page_ready}"
    )

    # Verify all these missions are released (not modeled)
    modeled_set = set(MODELED_MISSIONS)
    for mission in missions_above_page_ready:
        assert mission not in modeled_set, (
            f"Mission '{mission}' (above pageReadyObserved) must be released, "
            f"not modeled-only"
        )

    # Verify the pipeline is contiguous from attach to pageReadyObserved
    assert missions_above_page_ready[0] == "attach_session", (
        "Setup phase must begin with attach_session"
    )
    assert missions_above_page_ready[-1] == "page_ready_observation", (
        "Setup phase must end at page_ready_observation (the boundary marker)"
    )

    # Verify there are exactly 4 missions above/at the boundary
    # (12 total missions - 8 execution missions = 4 setup missions)
    assert len(missions_above_page_ready) == 4, (
        f"Released scope must have exactly 4 missions above pageReadyObserved "
        f"(setup phase + boundary); found {len(missions_above_page_ready)}"
    )


def test_released_scope_execution_phase_missions_form_contiguous_pipeline() -> None:
    """Verify execution-phase missions (below pageReadyObserved) form a contiguous pipeline.

    PRD Release Boundary (lines 47-63): The released implementation scope below
    pageReadyObserved specifies 8 consecutive missions forming the execution phase:
    - syncObservation (line 53)
    - targetActionabilityObservation (line 54)
    - armedStateEntry (line 55)
    - triggerWait (line 56)
    - clickDispatch (line 57)
    - clickCompletion (line 58)
    - successObservation (line 59)
    - runCompletion (line 60)

    These missions form the execution and observation phase of the released pipeline,
    executing sequentially after the pageReadyObserved boundary marker with no gaps,
    no modeled missions interspersed, and no branching—terminating only at runCompletion.

    This dedicated test verifies that the execution-phase pipeline is properly
    structured as a complete, linear sequence from sync_observation through
    run_completion without interruption or deviation.
    """
    # Identify the execution phase boundary
    page_ready_index = 3
    assert (
        RELEASED_MISSIONS[page_ready_index] == "page_ready_observation"
    ), "Boundary must be at index 3"

    # Extract execution-phase missions (all after page_ready_observation)
    execution_phase_missions = list(RELEASED_MISSIONS[page_ready_index + 1 :])

    # Verify execution phase has exactly 8 missions (no more, no fewer)
    assert len(execution_phase_missions) == 8, (
        f"Execution phase must contain exactly 8 missions (sync through run_completion); "
        f"found {len(execution_phase_missions)}"
    )

    # Verify each execution-phase mission is released, not modeled
    modeled_set = set(MODELED_MISSIONS)
    for mission in execution_phase_missions:
        assert mission not in modeled_set, (
            f"Execution-phase mission '{mission}' must be released, not modeled. "
            f"The execution pipeline must be fully released with no modeled gates."
        )

    # Verify the execution-phase pipeline is a specific, unchanging sequence
    expected_execution_sequence = (
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    )
    assert tuple(execution_phase_missions) == expected_execution_sequence, (
        f"Execution-phase pipeline must follow the exact PRD sequence; "
        f"expected {expected_execution_sequence}, got {tuple(execution_phase_missions)}"
    )

    # Verify the pipeline is contiguous: no gaps, no mission repetition
    assert (
        execution_phase_missions[0] == "sync_observation"
    ), "Execution phase must begin immediately with sync_observation"
    assert (
        execution_phase_missions[-1] == "run_completion"
    ), "Execution phase must terminate at run_completion"

    # Verify no modeled missions can appear between released execution-phase missions
    # (all missions in the execution phase must be released)
    released_set = set(RELEASED_MISSIONS)
    for mission in execution_phase_missions:
        assert mission in released_set, (
            f"Execution-phase mission '{mission}' must be in released missions; "
            f"execution phase cannot include modeled-only missions"
        )
