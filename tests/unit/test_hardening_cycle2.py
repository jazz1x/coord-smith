"""Regression tests for adversarial hardening CYCLE 2 (solo pass).

Cycle 2 ran on the main thread (multi-agent fan-out was rate-limited). It
re-verified cycle-1 fixes and hunted deeper. See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import dataclasses

import pytest
from PIL import Image

from coord_smith.adapters.page_transition import PageTransitionVerifier
from coord_smith.models.runtime import RuntimeState

# ---------------------------------------------------------------------------
# transition-region-fully-offscreen — empty clamp must raise, not silently
# report "no change" (which would fail every click forever)
# ---------------------------------------------------------------------------


def test_fully_offscreen_region_raises_not_silent_nochange() -> None:
    size = (100, 100)
    baseline = Image.new("RGB", size, color="white")
    post = Image.new("RGB", size, color="black")  # a real, total change
    verifier = PageTransitionVerifier()
    # Region entirely past the frame → empty clamp.
    with pytest.raises(ValueError, match="entirely outside"):
        verifier.verify_changed(
            baseline=baseline, post=post, region=(500, 500, 50, 50)
        )


def test_partially_offscreen_region_still_works() -> None:
    """A region partly on-screen is clamped and compared normally (not raised)."""
    size = (100, 100)
    baseline = Image.new("RGB", size, color="white")
    post = baseline.copy()
    for x in range(90, 100):
        for y in range(10):
            post.putpixel((x, y), (0, 0, 0))
    verifier = PageTransitionVerifier()
    # Region (90,0,50,10) runs 40px off the right edge; in-bounds 10x10.
    result = verifier.verify_changed(
        baseline=baseline, post=post, threshold=0.5, region=(90, 0, 50, 10)
    )
    assert result.change_ratio == pytest.approx(1.0)
    assert result.changed is True


# ---------------------------------------------------------------------------
# stale-runtimestate-scaffold-fields — dead fields with false hardcoded values
# removed (re-evaluated from cycle-1 WONTFIX after confirming 0 readers)
# ---------------------------------------------------------------------------


def test_runtimestate_has_no_dead_scaffold_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(RuntimeState)}
    for dead in ("current_phase", "current_anchor", "highest_reached_stage",
                 "run_status"):
        assert dead not in field_names, f"{dead} should have been removed"


def test_runtimestate_keeps_live_fields() -> None:
    field_names = {f.name for f in dataclasses.fields(RuntimeState)}
    for live in ("run_id", "current_mission", "approved_scope_ceiling",
                 "release_status", "session_ref", "site_identity",
                 "step_results", "mission_state"):
        assert live in field_names


def test_runtimestate_constructs_with_run_id_only() -> None:
    state = RuntimeState(run_id="r1")
    assert state.current_mission  # defaulted from ALL_MISSIONS[0]
    assert state.approved_scope_ceiling == "runCompletion"
