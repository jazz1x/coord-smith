"""Small runtime summary helpers."""

from ez_ax.graph.runtime_graph import (
    RuntimeGraphPlan,
    TransitionDecision,
    transition_artifact_from_decision,
)
from ez_ax.models.transition import TransitionArtifact


def summarize_graph_plan(plan: RuntimeGraphPlan) -> str:
    """Render a compact summary of the current bootstrap graph plan."""

    return (
        f"released={len(plan.released_nodes)} "
        f"modeled={len(plan.modeled_nodes)} "
        f"control={len(plan.control_nodes)} "
        f"ceiling={plan.approved_scope_ceiling}"
    )


def summarize_transition_decision(
    *,
    predecessor_mission: str | None,
    target_mission: str,
    decision: TransitionDecision,
) -> str:
    """Render a compact typed summary for transition diagnostics."""

    artifact = transition_artifact_from_decision(
        predecessor_mission=predecessor_mission,
        target_mission=target_mission,
        decision=decision,
    )
    return summarize_transition_artifact(artifact)


def summarize_transition_artifact(artifact: TransitionArtifact) -> str:
    """Render a compact summary for a comparable transition artifact."""

    predecessor = artifact.predecessor_mission or "none"
    detail = artifact.detail or "none"
    if artifact.allowed:
        return (
            f"predecessor={predecessor} target={artifact.target_mission} "
            f"allowed=true stop_reason={artifact.stop_reason} "
            f"failure_code={artifact.failure_code}"
        )
    return (
        f"predecessor={predecessor} target={artifact.target_mission} "
        f"allowed=false stop_reason={artifact.stop_reason} "
        f"failure_code={artifact.failure_code} detail={detail}"
    )
