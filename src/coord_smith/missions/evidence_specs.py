"""Single source of truth for per-mission evidence references.

Both the producer side (PyAutoGUIAdapter fallback refs) and the consumer side
(validate_execution_result) read from MISSION_EVIDENCE_SPECS.  Renaming a ref
or adding a mission is a one-file edit here; neither adapter needs to change.

Architecture note: this module belongs in missions/ (domain layer) rather than
adapters/ so the dependency arrow runs inward — adapters depend on missions,
never the reverse.

Public contract:
  - ``MissionEvidenceSpec`` — frozen dataclass carrying all ref strings for a
    single mission.
  - ``MISSION_EVIDENCE_SPECS`` — dict keyed by mission name, parsed exactly
    once at module load (parse-don't-validate).
  - ``MISSION_FALLBACK_REFS`` — pre-computed mapping of mission name to
    ordered (screenshot-first) evidence ref tuple.  Defined once here so
    neither ``pyautogui_adapter`` nor ``action_log_writer`` need to repeat
    the comprehension.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class MissionEvidenceSpec:
    """Evidence ref declarations for a single released mission.

    Attributes:
        mission_name: Canonical mission name (matches ``RELEASED_MISSIONS``).
        action_log_ref: Primary action-log evidence URI.
        screenshot_ref: Screenshot evidence URI, or ``None`` for missions that
            do not emit a screenshot in their primary path.
        primary_refs: Minimum frozenset that constitutes a valid primary
            evidence envelope for this mission.
        fallback_refs: Minimum frozenset for the fallback envelope.  Empty
            frozenset means no separate fallback path exists for this mission.
    """

    mission_name: str
    action_log_ref: str
    screenshot_ref: str | None
    primary_refs: frozenset[str]
    fallback_refs: frozenset[str]


MISSION_EVIDENCE_SPECS: Final[dict[str, MissionEvidenceSpec]] = {
    "attach_session": MissionEvidenceSpec(
        mission_name="attach_session",
        action_log_ref="evidence://action-log/attach-session",
        screenshot_ref="evidence://screenshot/attach-session-fallback",
        primary_refs=frozenset({
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        }),
        fallback_refs=frozenset({
            "evidence://screenshot/attach-session-fallback",
            "evidence://action-log/attach-session",
        }),
    ),
    "prepare_session": MissionEvidenceSpec(
        mission_name="prepare_session",
        action_log_ref="evidence://action-log/prepare-session",
        screenshot_ref="evidence://screenshot/prepare-session-fallback",
        primary_refs=frozenset({
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        }),
        fallback_refs=frozenset({
            "evidence://screenshot/prepare-session-fallback",
            "evidence://action-log/prepare-session",
        }),
    ),
    "step_observe": MissionEvidenceSpec(
        mission_name="step_observe",
        action_log_ref="evidence://action-log/step-observed",
        screenshot_ref="evidence://screenshot/step-observed",
        primary_refs=frozenset({
            "evidence://action-log/step-observed",
            "evidence://screenshot/step-observed",
        }),
        fallback_refs=frozenset(),
    ),
    "step_dispatch": MissionEvidenceSpec(
        mission_name="step_dispatch",
        action_log_ref="evidence://action-log/step-dispatched",
        screenshot_ref="evidence://screenshot/step-dispatched",
        primary_refs=frozenset({
            "evidence://action-log/step-dispatched",
            "evidence://screenshot/step-dispatched",
        }),
        fallback_refs=frozenset(),
    ),
    "step_capture": MissionEvidenceSpec(
        mission_name="step_capture",
        action_log_ref="evidence://action-log/step-captured",
        screenshot_ref="evidence://screenshot/step-captured",
        primary_refs=frozenset({
            "evidence://action-log/step-captured",
            "evidence://screenshot/step-captured",
        }),
        fallback_refs=frozenset(),
    ),
    "run_completion": MissionEvidenceSpec(
        mission_name="run_completion",
        action_log_ref="evidence://action-log/release-ceiling-stop",
        screenshot_ref="evidence://screenshot/run-completion-fallback",
        primary_refs=frozenset({
            "evidence://action-log/release-ceiling-stop",
        }),
        fallback_refs=frozenset({
            "evidence://screenshot/run-completion-fallback",
            "evidence://action-log/release-ceiling-stop",
        }),
    ),
}

# Pre-computed per-mission ordered evidence ref tuples (screenshot-first).
# Adapters that need to look up fallback refs import this constant directly
# instead of repeating the same comprehension over MISSION_EVIDENCE_SPECS.
# Missions with empty fallback_refs fall back to their primary_refs.
MISSION_FALLBACK_REFS: Final[dict[str, tuple[str, ...]]] = {
    name: (
        tuple(sorted(spec.fallback_refs, key=lambda r: "screenshot" not in r))
        if spec.fallback_refs
        else tuple(sorted(spec.primary_refs, key=lambda r: "screenshot" not in r))
    )
    for name, spec in MISSION_EVIDENCE_SPECS.items()
}
