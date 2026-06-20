"""Regression tests for adversarial hardening CYCLE 1.

Each test pins a confirmed cycle-1 finding (3-lens hunt → adversarial verify)
so the fix cannot silently regress. See tmp/cycles/CYCLE-LOG.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from coord_smith.adapters.page_transition import PageTransitionVerifier
from coord_smith.config.click_recipe import (
    ClickRecipe,
    Step,
    StepCoord,
    load_click_recipe,
)
from coord_smith.models.errors import ConfigError
from coord_smith.reporting.run_summary import RunSummaryWriter

# ---------------------------------------------------------------------------
# per-step-screenshot-collision — success-path screenshots keyed by step_idx
# ---------------------------------------------------------------------------


def test_screenshot_path_prefixes_step_idx(tmp_path: Path) -> None:
    from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter

    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    p0 = adapter._screenshot_path("step-dispatched", step_idx=0)
    p1 = adapter._screenshot_path("step-dispatched", step_idx=1)
    assert p0 != p1
    assert p0.name == "00-step-dispatched.png"
    assert p1.name == "01-step-dispatched.png"


def test_screenshot_path_no_idx_keeps_flat_name(tmp_path: Path) -> None:
    from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter

    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    p = adapter._screenshot_path("attach-session")
    assert p.name == "attach-session.png"


# ---------------------------------------------------------------------------
# stale-run-root-attribution — a no-root invocation must not inherit a prior
# (or concurrent) run's directory identity. Cycle 9 replaced the mtime-based
# _find_latest_run_root gate with an ownership model: the writer only writes
# into the root it was explicitly handed via set_own_run_root.
# ---------------------------------------------------------------------------


def test_no_claimed_root_writes_degenerate_not_prior_root(tmp_path: Path) -> None:
    """An invocation that never claimed a run root (set_own_run_root never
    called — host-busy / config error / interrupt before the graph created a
    root) writes a degenerate base_dir/run.json and never attributes a prior or
    concurrent run's root."""
    runs = tmp_path / "artifacts" / "runs"
    runs.mkdir(parents=True)
    prior = runs / "20260101-oldrun"
    prior.mkdir()
    prior_summary = prior / "run.json"
    prior_summary.write_text(
        json.dumps({"run_id": "20260101-oldrun", "status": "success"}),
        encoding="utf-8",
    )

    writer = RunSummaryWriter(base_dir=tmp_path)  # never set_own_run_root
    target = writer.flush(status="host_busy", exit_code=4)

    assert target == tmp_path / "run.json"  # degenerate, NOT inside prior
    assert json.loads(prior_summary.read_text(encoding="utf-8"))["status"] == (
        "success"
    )  # prior run's outcome untouched


def test_claimed_run_root_is_used(tmp_path: Path) -> None:
    """When the invocation claims its run root (set_own_run_root), flush writes
    run.json into that root regardless of any other dirs under artifacts/runs."""
    own = tmp_path / "artifacts" / "runs" / "20260618-current"
    own.mkdir(parents=True)
    writer = RunSummaryWriter(base_dir=tmp_path)
    writer.set_own_run_root(own)
    target = writer.flush(status="success", exit_code=0)
    assert target == own / "run.json"
    assert json.loads(target.read_text(encoding="utf-8"))["run_id"] == own.name


# ---------------------------------------------------------------------------
# transition-region clamp + change_ratio denominator
# ---------------------------------------------------------------------------


def test_offscreen_region_denominator_uses_inbounds_area() -> None:
    """A region extending past the frame edge must not dilute change_ratio
    with the off-screen area: the denominator is the clamped in-bounds area."""
    size = (100, 100)
    baseline = Image.new("RGB", size, color="white")
    post = baseline.copy()
    # Change every pixel of the in-bounds slice the region covers: the region
    # starts at x=80 and declares width 100 (runs to x=180, 80px off-screen).
    # In-bounds slice is x in [80,100) × y in [0,50) = 20*50 = 1000 px.
    for x in range(80, 100):
        for y in range(50):
            post.putpixel((x, y), (0, 0, 0))

    verifier = PageTransitionVerifier()
    # Declared region (80, 0, 100, 50): declared area 100*50 = 5000, but the
    # real in-bounds crop is 20*50 = 1000. All 1000 in-bounds pixels changed.
    result = verifier.verify_changed(
        baseline=baseline, post=post, threshold=0.5, region=(80, 0, 100, 50)
    )
    # With the clamp the denominator is 1000 → ratio 1.0. Without it, the
    # denominator would be the declared 5000 → 1000/5000 = 0.2 < 0.5 and the
    # real full-region change would be falsely suppressed.
    assert result.change_ratio == pytest.approx(1.0)
    assert result.changed is True


# ---------------------------------------------------------------------------
# coord-only-step-accepts-dead-image-fields — reject image params w/o image
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"region": (0, 0, 10, 10)},
        {"confidence": 0.8},
        {"grayscale": True},
    ],
)
def test_coord_only_step_rejects_image_fields(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011
        Step(name="x", coord=StepCoord(x=1, y=1), **kwargs)  # type: ignore[arg-type]


def test_image_step_still_accepts_image_fields() -> None:
    step = Step(name="x", image="t.png", confidence=0.8, grayscale=True)
    assert step.confidence == 0.8


# ---------------------------------------------------------------------------
# both-shapes-missions-image-resolved — a valid steps+missions recipe must not
# hard-fail on the superseded missions block's templates
# ---------------------------------------------------------------------------


def test_both_shapes_skips_superseded_missions_image_check(tmp_path: Path) -> None:
    # steps is the live source (valid coord step); missions block references a
    # nonexistent template but is superseded — loading must succeed.
    recipe_text = """
version: 1
steps:
  - name: live-step
    coord: { x: 10, y: 20 }
missions:
  legacy_click:
    image: does-not-exist.png
    confidence: 0.9
"""
    path = tmp_path / "recipe.yaml"
    path.write_text(recipe_text, encoding="utf-8")
    with pytest.warns(DeprecationWarning):
        recipe = load_click_recipe(path)
    assert recipe.steps is not None
    assert recipe.steps[0].name == "live-step"


def test_missions_only_still_existence_checks(tmp_path: Path) -> None:
    # When missions is the LIVE source (no steps), a missing template must
    # still hard-fail — the fix must not disable real checks.
    recipe_text = """
version: 1
missions:
  legacy_click:
    image: does-not-exist.png
    confidence: 0.9
"""
    path = tmp_path / "recipe.yaml"
    path.write_text(recipe_text, encoding="utf-8")
    with pytest.raises(ConfigError), pytest.warns(DeprecationWarning):
        load_click_recipe(path)


# ---------------------------------------------------------------------------
# version Literal[1] already covered in test_adversarial_hardening; here we
# assert the both-shapes helper directly for clarity
# ---------------------------------------------------------------------------


def test_steps_mirror_missions_detects_derived_vs_authored() -> None:
    from coord_smith.config.click_recipe import _steps_mirror_missions

    derived = ClickRecipe.model_validate(
        {"version": 1, "missions": {"m1": {"x": 1, "y": 2}}}
    )
    # Legacy-only: steps were derived from missions → mirror.
    assert _steps_mirror_missions(derived.steps, derived.missions) is True
