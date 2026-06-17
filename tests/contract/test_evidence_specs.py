"""Contract: MISSION_EVIDENCE_SPECS is the single source of truth.

These tests verify four properties:

1. manifest_covers_all_released_missions — every name in RELEASED_MISSIONS has
   a corresponding entry in MISSION_EVIDENCE_SPECS.
2. action_log_refs_are_valid — every action_log_ref in the manifest parses
   cleanly via parse_released_evidence_ref.
3. screenshot_refs_are_valid — every non-None screenshot_ref parses cleanly.
4. adapter_refs_match_manifest — _FALLBACK_REFS in PyAutoGUIAdapter is derived
   exactly from the manifest; no ref string appears in the adapter that is not
   in the manifest (drift guard).
"""

from __future__ import annotations

import pytest

from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.missions.evidence_specs import MISSION_EVIDENCE_SPECS
from coord_smith.missions.names import RELEASED_MISSIONS


def test_manifest_covers_all_released_missions() -> None:
    """MISSION_EVIDENCE_SPECS must have an entry for every released mission."""
    missing = set(RELEASED_MISSIONS) - set(MISSION_EVIDENCE_SPECS)
    assert not missing, f"MISSION_EVIDENCE_SPECS missing released missions: {sorted(missing)}"


def test_manifest_has_no_extra_missions() -> None:
    """MISSION_EVIDENCE_SPECS must not declare missions outside RELEASED_MISSIONS."""
    extra = set(MISSION_EVIDENCE_SPECS) - set(RELEASED_MISSIONS)
    assert not extra, f"MISSION_EVIDENCE_SPECS has undeclared mission names: {sorted(extra)}"


@pytest.mark.parametrize("mission_name", list(MISSION_EVIDENCE_SPECS))
def test_action_log_refs_are_valid(mission_name: str) -> None:
    """Each action_log_ref must parse cleanly as a released evidence ref."""
    spec = MISSION_EVIDENCE_SPECS[mission_name]
    kind, key = parse_released_evidence_ref(spec.action_log_ref)
    assert kind == "action-log", (
        f"{mission_name}: action_log_ref kind must be 'action-log', got {kind!r}"
    )
    assert key, f"{mission_name}: action_log_ref key must be non-empty"


@pytest.mark.parametrize(
    "mission_name",
    [name for name, s in MISSION_EVIDENCE_SPECS.items() if s.screenshot_ref is not None],
)
def test_screenshot_refs_are_valid(mission_name: str) -> None:
    """Each non-None screenshot_ref must parse cleanly as a released evidence ref."""
    spec = MISSION_EVIDENCE_SPECS[mission_name]
    assert spec.screenshot_ref is not None
    kind, key = parse_released_evidence_ref(spec.screenshot_ref)
    assert kind == "screenshot", (
        f"{mission_name}: screenshot_ref kind must be 'screenshot', got {kind!r}"
    )
    assert key, f"{mission_name}: screenshot_ref key must be non-empty"


def test_adapter_refs_match_manifest() -> None:
    """_FALLBACK_REFS in PyAutoGUIAdapter must contain only refs from the manifest.

    Imports the module-level dict after derivation.  Any hand-typed ref that
    slipped back in (drift) would appear in _FALLBACK_REFS but not in the
    manifest's union of all refs.
    """
    from coord_smith.adapters.pyautogui_adapter import (  # type: ignore[attr-defined]
        _FALLBACK_REFS,
    )

    # Build the full set of all refs declared in the manifest.
    manifest_all_refs: set[str] = set()
    for spec in MISSION_EVIDENCE_SPECS.values():
        manifest_all_refs.add(spec.action_log_ref)
        if spec.screenshot_ref is not None:
            manifest_all_refs.add(spec.screenshot_ref)
        manifest_all_refs.update(spec.primary_refs)
        manifest_all_refs.update(spec.fallback_refs)

    adapter_all_refs: set[str] = set()
    for refs in _FALLBACK_REFS.values():
        adapter_all_refs.update(refs)

    drift = adapter_all_refs - manifest_all_refs
    assert not drift, (
        f"_FALLBACK_REFS contains refs not present in MISSION_EVIDENCE_SPECS: {sorted(drift)}"
    )

    # Also assert every mission in manifest has a _FALLBACK_REFS entry.
    missing_missions = set(MISSION_EVIDENCE_SPECS) - set(_FALLBACK_REFS)
    assert not missing_missions, (
        f"_FALLBACK_REFS missing missions from manifest: {sorted(missing_missions)}"
    )
