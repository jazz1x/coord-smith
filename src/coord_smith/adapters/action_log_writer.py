"""Action-log writing concern, extracted from PyAutoGUIAdapter (SRP separation).

All writer methods append JSONL records to
``<run_root>/artifacts/action-log/<key>.jsonl``.  The key derivation and the
on-disk format are the public contract defined by ADR-006; byte-identical output
to the original inline methods is an invariant.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.missions.evidence_specs import MISSION_FALLBACK_REFS
from coord_smith.models.errors import ValidationError
from coord_smith.models.identifiers import MissionName

# Imported from missions.evidence_specs — single source of truth shared with
# pyautogui_adapter; no local re-computation.
_FALLBACK_REFS = MISSION_FALLBACK_REFS


class ActionLogWriter:
    """Writes structured JSONL records to the run's action-log directory.

    Owns no pyautogui state; safe to unit-test in isolation.

    All writers serialize with ``ensure_ascii=False`` so a unicode step name
    (permitted by the recipe schema) lands as raw UTF-8 — one encoding policy
    shared with the sibling producers ``seed_action_log_marker`` and
    ``_capture_failure_evidence`` that append to the same action-log files.
    """

    def __init__(self, run_root: Path) -> None:
        self._run_root = run_root

    # ------------------------------------------------------------------
    # Public path helpers
    # ------------------------------------------------------------------

    def action_log_path(self, key: str) -> Path:
        """Return the JSONL path for *key*, creating parent dirs on demand.

        Defense-in-depth: ``key`` is derived from ``step.name`` for per-step
        guard logs (transition / wait_for / signal). ``Step`` rejects names
        with path separators at parse time, but a ``model_construct`` escape
        hatch (test doubles, future transports) bypasses that validator, so
        the write boundary re-checks. A key that escapes the action-log
        directory raises rather than writing outside the run root.
        """
        base = (self._run_root / "artifacts" / "action-log").resolve()
        path = (base / f"{key}.jsonl").resolve()
        # ``path`` must stay strictly inside ``base`` — reject any key that
        # traverses out (``..``) or is absolute. ``Path.is_relative_to`` is
        # the explicit containment check.
        if not path.is_relative_to(base):
            raise ValidationError(
                f"action-log key escapes the run root: key={key!r}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Key derivation
    # ------------------------------------------------------------------

    def action_key_for_mission(self, mission: str) -> str:
        """Return the canonical action-log key for a mission.

        Most mission names map to a past-tense action key
        (``step_dispatch`` -> ``step-dispatched``) held in the evidence
        fallback table.  Missions absent from the table fall back to a
        literal underscore-to-hyphen substitution.
        """
        refs = _FALLBACK_REFS.get(mission)
        if refs is not None:
            for ref in refs:
                kind, key = parse_released_evidence_ref(ref)
                if kind == "action-log":
                    return key
        return mission.replace("_", "-")

    # ------------------------------------------------------------------
    # Writers — byte-identical output to the original inline methods
    # ------------------------------------------------------------------

    def write_action_log(self, *, key: str, mission_name: MissionName) -> None:
        """Append a bare dispatch record (ts / mission_name / event)."""
        ts = datetime.now(tz=UTC).isoformat()
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission_name,
            "event": key,
        }
        path = self.action_log_path(key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_image_match(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        x: int,
        y: int,
    ) -> None:
        """Append a structured image-match record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self.action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "image_template": template,
            "match_confidence": confidence,
            "match_x": x,
            "match_y": y,
        }
        path = self.action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_image_fallback(
        self,
        *,
        mission: str,
        template: str,
        reason: str,
        fallback_x: int,
        fallback_y: int,
    ) -> None:
        """Append a record of an image-primary miss that fell back to coord.

        A ``prefer: image`` step that declares both an ``image`` and a
        ``coord`` silently rides the coord fallback when the template stops
        matching (UI re-skin, template drift). Without this record the
        dispatch looks byte-identical to a coord-only step — no positive
        signal that the template is broken. Emitting an ``image_fallback_used``
        event keeps the silent degradation observable in the typed-evidence
        stream so an auditor (human or LLM) can detect a permanently-stale
        template. See coord_resolver.resolve_step_click_coords.
        """
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self.action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "image_fallback_used": True,
            "image_fallback_template": template,
            "image_fallback_reason": reason,
            "image_fallback_x": fallback_x,
            "image_fallback_y": fallback_y,
        }
        path = self.action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_transition(
        self,
        *,
        mission: str,
        changed: bool,
        change_ratio: float,
        bbox: tuple[int, int, int, int] | None,
        threshold: float,
    ) -> None:
        """Append a page-transition verification record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self.action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "transition_changed": changed,
            "transition_change_ratio": change_ratio,
            "transition_threshold": threshold,
            "transition_bbox": list(bbox) if bbox is not None else None,
        }
        path = self.action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_signal(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None:
        """Append a post-click-signal hit record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self.action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "post_click_signal_template": template,
            "post_click_signal_confidence": confidence,
            "post_click_signal_elapsed_seconds": elapsed,
            "post_click_signal_x": x,
            "post_click_signal_y": y,
        }
        path = self.action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def write_wait_for(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None:
        """Append a pre-click wait_for hit record to the mission action log.

        Symmetric to ``write_signal`` but namespaced with ``wait_for_*``
        keys so a downstream audit can distinguish the pre-click guard from
        the post-click signal.
        """
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self.action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "wait_for_template": template,
            "wait_for_confidence": confidence,
            "wait_for_elapsed_seconds": elapsed,
            "wait_for_x": x,
            "wait_for_y": y,
        }
        path = self.action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
