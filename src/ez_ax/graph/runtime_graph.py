"""Deterministic graph plan for the bootstrap scaffold."""

from dataclasses import dataclass

from ez_ax.missions.names import CONTROL_MISSIONS, MODELED_MISSIONS, RELEASED_MISSIONS
from ez_ax.models.checkpoint import TransitionCheckpointCollection
from ez_ax.models.failure import (
    TransitionFailureCode,
    TransitionStopReason,
    failure_code_for_stop_reason,
)
from ez_ax.models.runtime import (
    RuntimeState,
    format_scope_ceiling_detail,
    mission_is_within_approved_scope,
)
from ez_ax.models.transition import TransitionArtifact, build_transition_artifact


@dataclass(frozen=True, slots=True)
class RuntimeGraphPlan:
    """Static graph plan pinned to the current PRD set."""

    released_nodes: tuple[str, ...]
    modeled_nodes: tuple[str, ...]
    control_nodes: tuple[str, ...]
    approved_scope_ceiling: str


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    """Typed decision emitted by graph transition precondition checks."""

    allowed: bool
    stop_reason: TransitionStopReason
    detail: str | None = None

    @property
    def failure_code(self) -> TransitionFailureCode:
        """Expose typed failure taxonomy code at decision level."""

        return failure_code_for_stop_reason(self.stop_reason)


FORWARD_MISSION_SEQUENCE: tuple[str, ...] = (*RELEASED_MISSIONS, *MODELED_MISSIONS)


def _node_name(mission_name: str) -> str:
    return f"{mission_name}_node"


def _expected_predecessor(target_mission: str) -> str | None:
    index = FORWARD_MISSION_SEQUENCE.index(target_mission)
    if index == 0:
        return None
    return FORWARD_MISSION_SEQUENCE[index - 1]


def evaluate_forward_transition(
    *,
    current_mission: str | None,
    target_mission: str,
    approved_scope_ceiling: str,
    required_evidence_ready: bool,
) -> TransitionDecision:
    """Validate forward mission progression against typed preconditions."""

    if target_mission not in FORWARD_MISSION_SEQUENCE:
        return TransitionDecision(
            allowed=False,
            stop_reason="unknown_target_mission",
            detail=f"Unknown target mission: {target_mission}",
        )
    if not mission_is_within_approved_scope(
        mission_name=target_mission, approved_scope_ceiling=approved_scope_ceiling
    ):
        ceiling_detail = format_scope_ceiling_detail(approved_scope_ceiling)
        return TransitionDecision(
            allowed=False,
            stop_reason="mission_out_of_scope",
            detail=(
                f"Target mission '{target_mission}' is outside approved scope ceiling "
                f"{ceiling_detail}"
            ),
        )
    if not required_evidence_ready:
        return TransitionDecision(
            allowed=False,
            stop_reason="missing_required_evidence",
            detail=f"Required evidence is missing for mission '{target_mission}'",
        )

    expected_predecessor = _expected_predecessor(target_mission)
    if expected_predecessor is None:
        if current_mission is None:
            return TransitionDecision(allowed=True, stop_reason="none")
        return TransitionDecision(
            allowed=False,
            stop_reason="missing_predecessor_checkpoint",
            detail=f"Expected no predecessor before '{target_mission}'",
        )
    if current_mission != expected_predecessor:
        return TransitionDecision(
            allowed=False,
            stop_reason="missing_predecessor_checkpoint",
            detail=(
                f"Expected predecessor '{expected_predecessor}' "
                f"for '{target_mission}', "
                f"got '{current_mission}'"
            ),
        )
    return TransitionDecision(allowed=True, stop_reason="none")


def transition_artifact_from_decision(
    *,
    predecessor_mission: str | None,
    target_mission: str,
    decision: TransitionDecision,
) -> TransitionArtifact:
    """Build a comparable transition artifact from graph transition context."""

    return build_transition_artifact(
        predecessor_mission=predecessor_mission,
        target_mission=target_mission,
        allowed=decision.allowed,
        stop_reason=decision.stop_reason,
        detail=decision.detail,
    )


def append_transition_checkpoint(
    *,
    collection: TransitionCheckpointCollection,
    predecessor_mission: str | None,
    target_mission: str,
    decision: TransitionDecision,
) -> TransitionCheckpointCollection:
    """Append a transition decision into ordered checkpoint collection."""

    artifact = transition_artifact_from_decision(
        predecessor_mission=predecessor_mission,
        target_mission=target_mission,
        decision=decision,
    )
    return collection.append(artifact)


def evaluate_and_record_forward_transition(
    *,
    state: RuntimeState,
    target_mission: str,
    required_evidence_ready: bool,
    current_mission: str | None = None,
) -> TransitionDecision:
    """Evaluate a forward transition and record its artifact in runtime state."""

    latest_checkpoint = state.transition_checkpoints.transitions

    # First transition constraint: predecessor_mission must be None if
    # state.current_mission is a released mission
    if not latest_checkpoint:
        # Empty checkpoint collection = first transition
        # Determine what predecessor_mission would be
        if current_mission is None:
            # If current_mission param is omitted, check state.current_mission
            # only if it's a released mission (not a validation/control mission)
            if state.current_mission in RELEASED_MISSIONS:
                implied_predecessor = state.current_mission
            else:
                implied_predecessor = None
        else:
            # If current_mission param is explicit, check if it's released
            if current_mission in RELEASED_MISSIONS:
                implied_predecessor = current_mission
            else:
                implied_predecessor = None

        if implied_predecessor is not None:
            msg = (
                "First transition artifact must not declare a "
                "predecessor mission."
            )
            raise ValueError(msg)
        predecessor_mission = None
    else:
        # Subsequent transitions: use current_mission parameter or
        # extract from latest checkpoint
        if current_mission is None:
            predecessor_mission = latest_checkpoint[-1].target_mission
        else:
            predecessor_mission = current_mission
    decision = evaluate_forward_transition(
        current_mission=predecessor_mission,
        target_mission=target_mission,
        approved_scope_ceiling=state.approved_scope_ceiling,
        required_evidence_ready=required_evidence_ready,
    )
    state.transition_checkpoints = append_transition_checkpoint(
        collection=state.transition_checkpoints,
        predecessor_mission=predecessor_mission,
        target_mission=target_mission,
        decision=decision,
    )
    return decision


def build_runtime_graph_plan() -> RuntimeGraphPlan:
    """Return the canonical node ordering for the bootstrap graph."""

    return RuntimeGraphPlan(
        released_nodes=tuple(_node_name(name) for name in RELEASED_MISSIONS),
        modeled_nodes=tuple(_node_name(name) for name in MODELED_MISSIONS),
        control_nodes=tuple(_node_name(name) for name in CONTROL_MISSIONS),
        approved_scope_ceiling="runCompletion",
    )
