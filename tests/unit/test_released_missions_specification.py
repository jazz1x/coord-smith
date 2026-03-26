"""Test that released missions match PRD specification."""

from ez_ax.missions.names import (
    BROWSER_FACING_MISSIONS,
    MODELED_MISSIONS,
    RELEASED_MISSIONS,
)


def test_released_missions_match_prd_specification() -> None:
    """Verify released scope includes exactly 4 missions from PRD section 'Release Boundary'."""
    # PRD lines 47-53: Released implementation scope includes:
    # - attach_session (PRD: "attach")
    # - prepare_session (PRD: "prepareSession")
    # - benchmark_validation (PRD: "benchmark validation")
    # - page_ready_observation (PRD: "pageReadyObserved")
    expected_released_missions = (
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    )
    assert RELEASED_MISSIONS == expected_released_missions


def test_released_missions_count_matches_prd() -> None:
    """Verify exactly 4 released missions as specified in PRD Release Boundary."""
    # PRD specifies 4 released missions: attach, prepareSession, benchmark validation, pageReadyObserved
    assert len(RELEASED_MISSIONS) == 4


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
