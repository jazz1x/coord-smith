"""Canonical runtime mission names.

The released-scope graph defines a small, fixed set of missions. The legacy
twelve-mission lifecycle that orbited a single click event has been folded
into a per-run / per-step split:

* ``attach_session``, ``prepare_session``, ``run_completion`` — per-run
  setup and teardown, executed exactly once per ``coord-smith`` invocation.
* ``step_observe``, ``step_dispatch``, ``step_capture`` — per-step lifecycle,
  executed N times for an N-step recipe (``Step`` list).

The previous control-only and modeled mission tiers (``release_gate_evaluation``,
``retry_or_stop_decision``, ``work_rag_*``, ``lesson_promotion``,
``e2e_replay_or_comparison``, ``python_validation_execution``) are
permanently removed; see ``docs/prd-multi-step-flow-recipe.md`` §2.4 D2 and
``docs/prd.md`` §Non-Goals.
"""

from typing import Final

RELEASED_MISSIONS: Final[tuple[str, ...]] = (
    "attach_session",
    "prepare_session",
    "step_observe",
    "step_dispatch",
    "step_capture",
    "run_completion",
)

# All missions are released; no modeled / control-only tier exists.
ALL_MISSIONS: Final[tuple[str, ...]] = RELEASED_MISSIONS
BROWSER_FACING_MISSIONS: Final[tuple[str, ...]] = RELEASED_MISSIONS


def mission_is_browser_facing(mission_name: str) -> bool:
    """Whether the given mission name is browser-facing.

    Retained as a public helper because adapters and tests use it as a guard
    against accidentally feeding non-browser names into browser-facing
    pipelines. With every mission now both released and browser-facing, this
    collapses to a simple membership check.
    """
    return mission_name in BROWSER_FACING_MISSIONS


def released_anchor_for_mission(mission_name: str) -> str | None:
    """Return the human-readable anchor name for a released mission, if any.

    Anchors are short camelCase labels used in cross-mission diagnostics
    (release ceiling messages, scope reports). Only the missions that
    represent a meaningful run-level checkpoint carry one; the per-step
    missions (``step_*``) do not, since their meaning is bound to a step
    index rather than a fixed run-level anchor.
    """
    if mission_name not in ALL_MISSIONS:
        msg = f"Unknown mission name: {mission_name}"
        raise ValueError(msg)
    if mission_name == "prepare_session":
        return "prepareSession"
    if mission_name == "run_completion":
        return "runCompletion"
    return None
