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
