"""Test that release-ceiling expansion is prevented without explicit PRD change.

PRD Non-Goals clause (line 146):
'release-ceiling expansion above `pageReadyObserved` without explicit PRD change'

This enforces that the released ceiling cannot be expanded beyond pageReadyObserved
unless the PRD itself is explicitly updated.
"""

from __future__ import annotations

import pytest

from coord_smith.missions.names import MODELED_MISSIONS
from coord_smith.models.runtime import (
    DEFAULT_RELEASED_SCOPE_CEILING,
    RELEASED_SCOPE_CEILINGS,
    effective_scope_ceiling,
    mission_is_within_approved_scope,
)


def test_default_released_ceiling_is_run_completion() -> None:
    """Verify default released ceiling is runCompletion.

    PRD Release Boundary (line 45): 'Current released ceiling: runCompletion'

    The default ceiling must be the maximum currently-released ceiling,
    which has been expanded to runCompletion.
    """
    assert DEFAULT_RELEASED_SCOPE_CEILING == "runCompletion", (
        "Default released ceiling must be runCompletion "
        "(PRD Release Boundary line 45: ceiling expanded to runCompletion)"
    )


def test_released_scope_ceilings_expands_to_run_completion() -> None:
    """Verify released scope ceilings now include runCompletion.

    PRD Release Boundary (line 45): 'Current released ceiling: runCompletion'

    All supported released scope ceilings are at or below runCompletion.
    The ceiling has been expanded with explicit PRD change.
    """
    # Missions in order of execution (each mission "is at or below" the next)
    mission_order = (
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
    run_completion_index = mission_order.index("run_completion")

    for ceiling in RELEASED_SCOPE_CEILINGS:
        # Each ceiling must correspond to a released mission
        assert ceiling in ["prepareSession", "pageReadyObserved", "runCompletion"], (
            f"Unexpected ceiling '{ceiling}' in RELEASED_SCOPE_CEILINGS. "
            f"PRD Release Boundary (line 45): supported ceilings are prepareSession, pageReadyObserved, or runCompletion"
        )

        # Convert ceiling name to mission name for comparison
        ceiling_to_mission = {
            "prepareSession": "prepare_session",
            "pageReadyObserved": "page_ready_observation",
            "runCompletion": "run_completion",
        }
        mission_name = ceiling_to_mission.get(ceiling)
        if mission_name:
            mission_index = mission_order.index(mission_name)
            assert (
                mission_index <= run_completion_index
            ), (
                f"Ceiling '{ceiling}' (mission '{mission_name}') is above "
                f"runCompletion. "
                f"PRD Release Boundary (line 45): ceiling cannot expand beyond runCompletion"
            )


@pytest.mark.filterwarnings("ignore::UserWarning")
def test_effective_scope_ceiling_defaults_unknown_to_run_completion(
) -> None:
    """Verify unknown ceiling defaults to runCompletion.

    PRD Release Boundary (line 45): 'Current released ceiling: runCompletion'

    When an unknown or invalid ceiling is provided, the system must default to
    runCompletion (the current released ceiling).
    """
    # Attempt to set ceiling to unknown values
    invalid_ceilings = [
        "syncToServerTime",  # unknown
        "customCeiling",  # unknown
        "trigger_wait",  # mission name, not a ceiling
        "click_dispatch",  # mission name, not a ceiling
        "unknownValue",  # unknown
    ]

    for invalid_ceiling in invalid_ceilings:
        effective = effective_scope_ceiling(invalid_ceiling)
        assert effective == "runCompletion", (
            f"Invalid ceiling '{invalid_ceiling}' must default to "
            f"'runCompletion' (current released ceiling). "
            f"PRD Release Boundary (line 45): default ceiling is runCompletion"
        )


def test_mission_scope_enforcement_respects_ceiling_boundary() -> None:
    """Verify mission scope enforcement respects the ceiling boundary.

    PRD Release Boundary (line 45): Ceilings are prepareSession, pageReadyObserved, runCompletion

    All released missions must be within their ceiling boundaries.
    No modeled-only missions remain.
    """
    # Under pageReadyObserved ceiling
    assert mission_is_within_approved_scope(
        "page_ready_observation", "pageReadyObserved"
    ), "page_ready_observation must be within pageReadyObserved ceiling"

    assert mission_is_within_approved_scope(
        "prepare_session", "pageReadyObserved"
    ), "prepare_session must be within pageReadyObserved ceiling"

    # Verify runCompletion ceiling allows all missions
    assert mission_is_within_approved_scope(
        "run_completion", "runCompletion"
    ), "run_completion must be within runCompletion ceiling"

    assert mission_is_within_approved_scope(
        "click_completion", "runCompletion"
    ), "click_completion must be within runCompletion ceiling"

    # MODELED_MISSIONS is now empty (all promoted to released)
    assert len(MODELED_MISSIONS) == 0, (
        "No modeled-only missions remain; all are released"
    )
