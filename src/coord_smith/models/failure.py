"""Typed failure taxonomy models for graph transition decisions."""

from typing import Final, Literal

TransitionStopReason = Literal[
    "none",
    "unknown_target_mission",
    "mission_out_of_scope",
    "missing_required_evidence",
    "missing_predecessor_checkpoint",
]

TransitionFailureCode = Literal[
    "NONE",
    "GRAPH_UNKNOWN_TARGET_MISSION",
    "GRAPH_MISSION_OUT_OF_SCOPE",
    "GRAPH_MISSING_REQUIRED_EVIDENCE",
    "GRAPH_MISSING_PREDECESSOR_CHECKPOINT",
]

STOP_REASON_TO_FAILURE_CODE: Final[
    dict[TransitionStopReason, TransitionFailureCode]
] = {
    "none": "NONE",
    "unknown_target_mission": "GRAPH_UNKNOWN_TARGET_MISSION",
    "mission_out_of_scope": "GRAPH_MISSION_OUT_OF_SCOPE",
    "missing_required_evidence": "GRAPH_MISSING_REQUIRED_EVIDENCE",
    "missing_predecessor_checkpoint": "GRAPH_MISSING_PREDECESSOR_CHECKPOINT",
}


def failure_code_for_stop_reason(
    stop_reason: TransitionStopReason,
) -> TransitionFailureCode:
    """Map a typed stop reason to a stable failure taxonomy code."""

    return STOP_REASON_TO_FAILURE_CODE[stop_reason]
