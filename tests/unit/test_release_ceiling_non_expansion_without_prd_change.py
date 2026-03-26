"""Test that release-ceiling expansion is prevented without explicit PRD change.

PRD Non-Goals clause (line 146):
'release-ceiling expansion above `pageReadyObserved` without explicit PRD change'

This enforces that the released ceiling cannot be expanded beyond pageReadyObserved
unless the PRD itself is explicitly updated.
"""

from __future__ import annotations

from ez_ax.missions.names import MODELED_MISSIONS
from ez_ax.models.runtime import (
    DEFAULT_RELEASED_SCOPE_CEILING,
    RELEASED_SCOPE_CEILINGS,
    effective_scope_ceiling,
    mission_is_within_approved_scope,
)


def test_default_released_ceiling_is_page_ready_observed() -> None:
    """Verify default released ceiling is pageReadyObserved.

    PRD Non-Goals (line 146): 'release-ceiling expansion above `pageReadyObserved`
    without explicit PRD change'

    The default ceiling must be the maximum currently-released ceiling.
    """
    assert DEFAULT_RELEASED_SCOPE_CEILING == "pageReadyObserved", (
        "Default released ceiling must be pageReadyObserved "
        "(PRD Non-Goals line 146: ceiling cannot expand without PRD change)"
    )


def test_released_scope_ceilings_does_not_exceed_page_ready_observed() -> None:
    """Verify no released ceiling exists above pageReadyObserved.

    PRD Non-Goals (line 146): 'release-ceiling expansion above `pageReadyObserved`
    without explicit PRD change'

    All supported released scope ceilings must be at or below pageReadyObserved.
    Any new ceiling above pageReadyObserved would require a PRD change.
    """
    # Missions in order of execution (each mission "is at or below" the next)
    mission_order = (
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    )
    page_ready_index = mission_order.index("page_ready_observation")

    for ceiling in RELEASED_SCOPE_CEILINGS:
        # Each ceiling must correspond to a released mission
        assert ceiling == "prepareSession" or ceiling == "pageReadyObserved", (
            f"Unexpected ceiling '{ceiling}' in RELEASED_SCOPE_CEILINGS. "
            f"PRD Non-Goals (line 146): ceiling cannot expand beyond pageReadyObserved"
        )

        # Convert ceiling name to mission name for comparison
        ceiling_to_mission = {
            "prepareSession": "prepare_session",
            "pageReadyObserved": "page_ready_observation",
        }
        mission_name = ceiling_to_mission.get(ceiling)
        if mission_name:
            mission_index = mission_order.index(mission_name)
            assert (
                mission_index <= page_ready_index
            ), (
                f"Ceiling '{ceiling}' (mission '{mission_name}') is above "
                f"pageReadyObserved. "
                f"PRD Non-Goals (line 146): ceiling cannot expand without PRD change"
            )


def test_effective_scope_ceiling_rejects_expansion_above_page_ready_observed(
) -> None:
    """Verify ceiling cannot be expanded above pageReadyObserved without PRD change.

    PRD Non-Goals (line 146): 'release-ceiling expansion above `pageReadyObserved`
    without explicit PRD change'

    When an unknown or invalid ceiling is provided, the system must default to
    pageReadyObserved (or a lower approved ceiling), never expanding above it.
    """
    # Attempt to set ceiling to modeled-only missions (above pageReadyObserved)
    invalid_ceilings_above_page_ready = [
        "syncToServerTime",  # modeled only
        "armed_state_entry",  # modeled only
        "trigger_wait",  # modeled only
        "click_dispatch",  # modeled only
        "success_completion",  # modeled only
    ]

    for invalid_ceiling in invalid_ceilings_above_page_ready:
        effective = effective_scope_ceiling(invalid_ceiling)
        assert effective == "pageReadyObserved", (
            f"Invalid ceiling '{invalid_ceiling}' must default to "
            f"'pageReadyObserved', not expand beyond it. "
            f"PRD Non-Goals (line 146): ceiling cannot expand without PRD change"
        )


def test_mission_scope_enforcement_respects_ceiling_boundary() -> None:
    """Verify mission scope enforcement respects the ceiling boundary.

    PRD Non-Goals (line 146): 'release-ceiling expansion above `pageReadyObserved`
    without explicit PRD change'

    Missions above the released ceiling (modeled missions) must be rejected,
    preventing any form of ceiling expansion.
    """
    # Under pageReadyObserved ceiling (current released ceiling)
    assert mission_is_within_approved_scope(
        "page_ready_observation", "pageReadyObserved"
    ), "page_ready_observation must be within pageReadyObserved ceiling"

    assert mission_is_within_approved_scope(
        "prepare_session", "pageReadyObserved"
    ), "prepare_session must be within pageReadyObserved ceiling"

    # Modeled missions must be rejected at all ceilings
    for modeled_mission in MODELED_MISSIONS:
        for ceiling in ["pageReadyObserved", "prepareSession"]:
            assert not mission_is_within_approved_scope(
                modeled_mission, ceiling
            ), (
                f"Modeled mission '{modeled_mission}' must be rejected under "
                f"'{ceiling}' ceiling. "
                f"PRD Non-Goals (line 146): ceiling cannot expand without PRD change"
            )
