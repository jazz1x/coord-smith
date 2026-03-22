"""Typed transition artifacts for comparable checkpoint reporting."""

from dataclasses import dataclass

from ez_ax.missions.names import ALL_MISSIONS
from ez_ax.models.failure import (
    TransitionFailureCode,
    TransitionStopReason,
    failure_code_for_stop_reason,
)


@dataclass(frozen=True, slots=True)
class TransitionArtifact:
    """Comparable transition record derived from graph precondition decisions."""

    predecessor_mission: str | None
    target_mission: str
    allowed: bool
    stop_reason: TransitionStopReason
    failure_code: TransitionFailureCode
    detail: str | None = None


def build_transition_artifact(
    *,
    predecessor_mission: str | None,
    target_mission: str,
    allowed: bool,
    stop_reason: TransitionStopReason,
    detail: str | None = None,
) -> TransitionArtifact:
    """Create a typed transition artifact with stable failure taxonomy code."""

    if predecessor_mission is not None:
        if not isinstance(predecessor_mission, str):
            msg = "TransitionArtifact predecessor_mission must be a string"
            raise TypeError(msg)
        if not predecessor_mission:
            msg = "TransitionArtifact predecessor_mission must be non-empty"
            raise ValueError(msg)
        if not predecessor_mission.strip():
            msg = "TransitionArtifact predecessor_mission must not be whitespace-only"
            raise ValueError(msg)
        if predecessor_mission != predecessor_mission.strip():
            msg = (
                "TransitionArtifact predecessor_mission must not have leading or "
                "trailing whitespace"
            )
            raise ValueError(msg)
    if not isinstance(target_mission, str):
        msg = "TransitionArtifact target_mission must be a string"
        raise TypeError(msg)
    if not target_mission:
        msg = "TransitionArtifact target_mission must be non-empty"
        raise ValueError(msg)
    if not target_mission.strip():
        msg = "TransitionArtifact target_mission must not be whitespace-only"
        raise ValueError(msg)
    if target_mission != target_mission.strip():
        msg = (
            "TransitionArtifact target_mission must not have leading or trailing "
            "whitespace"
        )
        raise ValueError(msg)
    if allowed and stop_reason != "none":
        msg = "Allowed transition artifacts must use stop_reason='none'."
        raise ValueError(msg)
    if not allowed and stop_reason == "none":
        msg = "Disallowed transition artifacts must not use stop_reason='none'."
        raise ValueError(msg)
    if predecessor_mission is not None and predecessor_mission not in ALL_MISSIONS:
        msg = f"Unknown mission name: {predecessor_mission}"
        raise ValueError(msg)
    if target_mission not in ALL_MISSIONS and stop_reason != "unknown_target_mission":
        msg = f"Unknown mission name: {target_mission}"
        raise ValueError(msg)
    return TransitionArtifact(
        predecessor_mission=predecessor_mission,
        target_mission=target_mission,
        allowed=allowed,
        stop_reason=stop_reason,
        failure_code=failure_code_for_stop_reason(stop_reason),
        detail=detail,
    )
