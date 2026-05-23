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
from coord_smith.missions.evidence_specs import MISSION_EVIDENCE_SPECS

# Derived from MISSION_EVIDENCE_SPECS — mirrors the private constant in
# pyautogui_adapter so the key-derivation logic has a single source.
_FALLBACK_REFS: dict[str, tuple[str, ...]] = {
    name: (
        tuple(sorted(spec.fallback_refs, key=lambda r: "screenshot" not in r))
        if spec.fallback_refs
        else tuple(sorted(spec.primary_refs, key=lambda r: "screenshot" not in r))
    )
    for name, spec in MISSION_EVIDENCE_SPECS.items()
}


class ActionLogWriter:
    """Writes structured JSONL records to the run's action-log directory.

    Owns no pyautogui state; safe to unit-test in isolation.

    The ``run_root`` can be updated mid-run via ``with_run_root`` — the
    returned instance is a new object sharing the same configuration with
    only the path replaced (immutable-style update, no in-place mutation).
    """

    def __init__(self, run_root: Path) -> None:
        self._run_root = run_root

    def with_run_root(self, run_root: Path) -> ActionLogWriter:
        """Return a new writer bound to *run_root*."""
        return ActionLogWriter(run_root)

    # ------------------------------------------------------------------
    # Public path helpers
    # ------------------------------------------------------------------

    def action_log_path(self, key: str) -> Path:
        """Return the JSONL path for *key*, creating parent dirs on demand."""
        path = self._run_root / "artifacts" / "action-log" / f"{key}.jsonl"
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

    def write_action_log(self, *, key: str, mission_name: str) -> None:
        """Append a bare dispatch record (ts / mission_name / event)."""
        ts = datetime.now(tz=UTC).isoformat()
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission_name,
            "event": key,
        }
        path = self.action_log_path(key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

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
            f.write(json.dumps(entry) + "\n")

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
            f.write(json.dumps(entry) + "\n")

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
            f.write(json.dumps(entry) + "\n")

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
            f.write(json.dumps(entry) + "\n")
