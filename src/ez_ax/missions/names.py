"""Canonical runtime mission names."""

from typing import Final

RELEASED_MISSIONS: Final[tuple[str, ...]] = (
    "attach_session",
    "prepare_session",
    "benchmark_validation",
    "page_ready_observation",
)

MODELED_MISSIONS: Final[tuple[str, ...]] = (
    "sync_observation",
    "target_actionability_observation",
    "armed_state_entry",
    "trigger_wait",
    "click_dispatch",
    "click_completion",
    "success_observation",
    "run_completion",
)

PRIMARY_CONTROL_MISSIONS: Final[tuple[str, ...]] = (
    "release_gate_evaluation",
    "retry_or_stop_decision",
)

RAG_MISSIONS: Final[tuple[str, ...]] = (
    "work_rag_update",
    "work_rag_compression",
    "lesson_promotion",
)

VALIDATION_MISSIONS: Final[tuple[str, ...]] = (
    "e2e_replay_or_comparison",
    "python_validation_execution",
)

CONTROL_MISSIONS: Final[tuple[str, ...]] = (
    *PRIMARY_CONTROL_MISSIONS,
    *RAG_MISSIONS,
    *VALIDATION_MISSIONS,
)

BROWSER_FACING_MISSIONS: Final[tuple[str, ...]] = (
    *RELEASED_MISSIONS,
    *MODELED_MISSIONS,
)

ALL_MISSIONS: Final[tuple[str, ...]] = (
    *RELEASED_MISSIONS,
    *MODELED_MISSIONS,
    *CONTROL_MISSIONS,
)


def mission_is_browser_facing(mission_name: str) -> bool:
    return mission_name in BROWSER_FACING_MISSIONS


def released_anchor_for_mission(mission_name: str) -> str | None:
    if mission_name not in ALL_MISSIONS:
        msg = f"Unknown mission name: {mission_name}"
        raise ValueError(msg)
    if mission_name == "prepare_session":
        return "prepareSession"
    if mission_name == "page_ready_observation":
        return "pageReadyObserved"
    return None
