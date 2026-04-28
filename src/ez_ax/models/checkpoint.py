"""Typed checkpoint collection models for transition artifact history."""

from dataclasses import dataclass

from ez_ax.missions.names import ALL_MISSIONS
from ez_ax.models.failure import failure_code_for_stop_reason
from ez_ax.models.transition import TransitionArtifact


@dataclass(frozen=True, slots=True)
class TransitionCheckpointCollection:
    """Ordered transition artifact collection for comparable diagnostics."""

    transitions: tuple[TransitionArtifact, ...] = ()

    def append(self, artifact: TransitionArtifact) -> TransitionCheckpointCollection:
        """Append an artifact while preserving predecessor-target order constraints."""

        if artifact.allowed and artifact.stop_reason != "none":
            msg = "Allowed transition artifacts must use stop_reason='none'."
            raise ValueError(msg)
        if not artifact.allowed and artifact.stop_reason == "none":
            msg = "Disallowed transition artifacts must not use stop_reason='none'."
            raise ValueError(msg)
        expected_failure_code = failure_code_for_stop_reason(artifact.stop_reason)
        if artifact.failure_code != expected_failure_code:
            msg = (
                "Transition artifacts must have failure_code consistent with "
                f"stop_reason: expected '{expected_failure_code}', got "
                f"'{artifact.failure_code}'."
            )
            raise ValueError(msg)
        if (
            artifact.target_mission not in ALL_MISSIONS
            and artifact.stop_reason != "unknown_target_mission"
        ):
            msg = f"Unknown mission name: {artifact.target_mission}"
            raise ValueError(msg)
        if not self.transitions:
            if artifact.predecessor_mission is not None:
                msg = (
                    "First transition artifact must not declare a predecessor mission."
                )
                raise ValueError(msg)
            return TransitionCheckpointCollection(transitions=(artifact,))

        last = self.transitions[-1]
        expected_predecessor = last.target_mission
        if artifact.predecessor_mission is None:
            msg = (
                "Transition artifacts after the first must declare a predecessor "
                "mission."
            )
            raise ValueError(msg)
        if artifact.predecessor_mission not in ALL_MISSIONS:
            msg = f"Unknown mission name: {artifact.predecessor_mission}"
            raise ValueError(msg)
        if artifact.predecessor_mission != expected_predecessor:
            msg = (
                f"Transition order violation: expected predecessor "
                f"'{expected_predecessor}', got '{artifact.predecessor_mission}'."
            )
            raise ValueError(msg)
        previous_targets = {
            transition.target_mission for transition in self.transitions
        }
        if artifact.allowed and artifact.target_mission in previous_targets:
            msg = (
                "Duplicate mission checkpoint: "
                f"'{artifact.target_mission}' was already recorded."
            )
            raise ValueError(msg)
        return TransitionCheckpointCollection(transitions=(*self.transitions, artifact))
