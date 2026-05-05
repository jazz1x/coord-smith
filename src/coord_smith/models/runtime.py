"""Core runtime state models for the Python scaffold."""

import warnings
from dataclasses import dataclass, field
from typing import Literal

from coord_smith.missions.names import (
    ALL_MISSIONS,
    CONTROL_MISSIONS,
    MODELED_MISSIONS,
    RELEASED_MISSIONS,
)
from coord_smith.models.checkpoint import TransitionCheckpointCollection
from coord_smith.models.transition import TransitionArtifact

RunStatus = Literal["idle", "running", "stopped", "completed", "escalated"]
ReleaseStatus = Literal["released", "modeled", "control-only"]

RELEASED_SCOPE_CEILINGS: tuple[str, ...] = (
    "prepareSession",
    "pageReadyObserved",
    "runCompletion",
)
DEFAULT_RELEASED_SCOPE_CEILING: Literal["runCompletion"] = "runCompletion"

# Ceiling name → terminal released mission name.  Indices are derived from
# RELEASED_MISSIONS at call time so they stay correct when the tuple changes.
# Keys must remain in lock-step with RELEASED_SCOPE_CEILINGS; values must be
# valid RELEASED_MISSIONS entries.  Validated at import time below.
_CEILING_TERMINAL_MISSION: dict[str, str] = {
    "prepareSession": "prepare_session",
    "pageReadyObserved": "page_ready_observation",
    "runCompletion": "run_completion",
}
assert _CEILING_TERMINAL_MISSION.keys() == set(RELEASED_SCOPE_CEILINGS), (
    f"_CEILING_TERMINAL_MISSION keys {set(_CEILING_TERMINAL_MISSION.keys())} "
    f"must match RELEASED_SCOPE_CEILINGS {set(RELEASED_SCOPE_CEILINGS)}"
)
_invalid_terminals = [
    v for v in _CEILING_TERMINAL_MISSION.values() if v not in RELEASED_MISSIONS
]
assert not _invalid_terminals, (
    f"_CEILING_TERMINAL_MISSION values must all be valid RELEASED_MISSIONS entries; "
    f"invalid: {_invalid_terminals}"
)
del _invalid_terminals


def effective_scope_ceiling(approved_scope_ceiling: str) -> str:
    """Normalize unknown ceilings to the released ceiling."""

    if approved_scope_ceiling not in RELEASED_SCOPE_CEILINGS:
        warnings.warn(
            f"Unknown scope ceiling '{approved_scope_ceiling}'; "
            f"defaulting to '{DEFAULT_RELEASED_SCOPE_CEILING}'",
            UserWarning,
            stacklevel=2,
        )
        return DEFAULT_RELEASED_SCOPE_CEILING
    return approved_scope_ceiling


def format_scope_ceiling_detail(approved_scope_ceiling: str) -> str:
    """Format ceiling details with defaulting diagnostics when needed."""

    effective = effective_scope_ceiling(approved_scope_ceiling)
    if approved_scope_ceiling == effective:
        return f"'{effective}'"
    return (
        f"'{effective}' (input '{approved_scope_ceiling}' defaulted to '{effective}')"
    )


@dataclass(slots=True)
class MissionState:
    """Mission-local state slice for the active mission."""

    mission_name: str
    attempt_count: int = 0
    checkpoint: str | None = None
    stop_reason: str | None = None
    evidence_refs: tuple[str, ...] = ()


def mission_lifecycle(mission_name: str) -> ReleaseStatus:
    """Return lifecycle status for a canonical mission name."""

    if mission_name in RELEASED_MISSIONS:
        return "released"
    if mission_name in MODELED_MISSIONS:
        return "modeled"
    if mission_name in CONTROL_MISSIONS:
        return "control-only"
    msg = f"Unknown mission name: {mission_name}"
    raise ValueError(msg)


def mission_is_within_approved_scope(
    mission_name: str, approved_scope_ceiling: str
) -> bool:
    """Check whether mission execution is allowed under current released ceiling."""

    if mission_name not in ALL_MISSIONS:
        return False

    if mission_name in CONTROL_MISSIONS:
        return True
    if mission_name in MODELED_MISSIONS:
        return False

    if mission_name not in RELEASED_MISSIONS:
        return False

    approved_scope_ceiling = effective_scope_ceiling(approved_scope_ceiling)

    terminal = _CEILING_TERMINAL_MISSION[approved_scope_ceiling]
    max_index = RELEASED_MISSIONS.index(terminal)
    mission_index = RELEASED_MISSIONS.index(mission_name)
    return mission_index <= max_index


@dataclass(slots=True)
class RuntimeState:
    """Global state slice aligned to the LangGraph PRD."""

    run_id: str
    run_status: RunStatus = "idle"
    current_phase: str = "Phase 4 — Validation And Layout Definition"
    current_mission: str = ALL_MISSIONS[0]
    current_anchor: str = "pythonRuntimeBootstrapCreated"
    highest_reached_stage: str = "none"
    approved_scope_ceiling: str = "runCompletion"
    release_status: ReleaseStatus = "released"
    session_ref: str | None = None
    site_identity: str | None = None
    target_page: str | None = None
    final_artifact_bundle_ref: str | None = None
    transition_checkpoints: TransitionCheckpointCollection = field(
        default_factory=TransitionCheckpointCollection
    )
    mission_state: MissionState = field(
        default_factory=lambda: MissionState(mission_name=ALL_MISSIONS[0])
    )

    def set_current_mission(self, mission_name: str) -> None:
        """Move to a mission only when it respects the approved scope ceiling."""

        if mission_name not in ALL_MISSIONS:
            msg = f"Unknown mission name: {mission_name}"
            raise ValueError(msg)
        effective_ceiling = effective_scope_ceiling(self.approved_scope_ceiling)
        if not mission_is_within_approved_scope(
            mission_name=mission_name,
            approved_scope_ceiling=effective_ceiling,
        ):
            ceiling_detail = format_scope_ceiling_detail(self.approved_scope_ceiling)
            msg = (
                f"Mission '{mission_name}' is outside approved scope ceiling "
                f"{ceiling_detail}"
            )
            raise ValueError(msg)
        self.current_mission = mission_name
        self.release_status = mission_lifecycle(mission_name)
        self.mission_state = MissionState(mission_name=mission_name)

    def record_transition_artifact(self, artifact: TransitionArtifact) -> None:
        """Record one typed transition artifact into ordered checkpoint state."""

        self.transition_checkpoints = self.transition_checkpoints.append(artifact)
