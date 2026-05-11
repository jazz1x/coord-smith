"""Unit tests for the Step / WaitFor / StepCoord DSL.

Validates the new multi-step recipe schema introduced in
docs/prd-multi-step-flow-recipe.md §2.4 D1. These tests are pure schema
validation — no pyautogui mocks needed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from coord_smith.config.click_recipe import (
    PostClickSignal,
    Step,
    StepCoord,
    WaitFor,
)

# ---- Happy paths -----------------------------------------------------


def test_step_with_coord_only_resolves_prefer_to_coord() -> None:
    """A step declaring only coord defaults prefer to 'coord'."""
    step = Step(name="click-buy", coord=StepCoord(x=100, y=200))
    assert step.image is None
    assert step.coord == StepCoord(x=100, y=200)
    assert step.prefer == "coord"


def test_step_with_image_only_resolves_prefer_to_image() -> None:
    """A step declaring only image defaults prefer to 'image'."""
    step = Step(name="click-buy", image="templates/buy.png")
    assert step.image == "templates/buy.png"
    assert step.coord is None
    assert step.prefer == "image"


def test_step_with_both_defaults_prefer_to_image() -> None:
    """When both image and coord are set, default prefer is 'image' (정합성)."""
    step = Step(
        name="click-buy",
        image="templates/buy.png",
        coord=StepCoord(x=100, y=200),
    )
    assert step.prefer == "image"


def test_step_prefer_coord_override_is_respected() -> None:
    """Recipe author can flip the priority per step via prefer='coord'."""
    step = Step(
        name="click-buy",
        image="templates/buy.png",
        coord=StepCoord(x=100, y=200),
        prefer="coord",
    )
    assert step.prefer == "coord"


def test_step_with_image_and_image_match_params() -> None:
    """Image-match parameters (region, confidence, grayscale) coexist with image."""
    step = Step(
        name="select-seat",
        image="templates/seat.png",
        region=(200, 300, 800, 600),
        confidence=0.85,
        grayscale=True,
    )
    assert step.region == (200, 300, 800, 600)
    assert step.confidence == 0.85
    assert step.grayscale is True


def test_step_with_wait_for_pre_click_guard() -> None:
    """A step can declare a pre-click WaitFor signal."""
    step = Step(
        name="select-seat",
        image="templates/seat.png",
        wait_for=WaitFor(image="templates/loaded.png", timeout=10.0),
    )
    assert step.wait_for is not None
    assert step.wait_for.image == "templates/loaded.png"
    assert step.wait_for.timeout == 10.0


def test_step_with_post_click_signal() -> None:
    """A step can declare a post-click signal poll."""
    step = Step(
        name="confirm",
        image="templates/confirm.png",
        post_click_signal=PostClickSignal(
            image="templates/loading.png", timeout=3.0
        ),
    )
    assert step.post_click_signal is not None
    assert step.post_click_signal.image == "templates/loading.png"


def test_step_with_verify_transition_post_click_diff() -> None:
    """A step can enable post-click pixel-diff verification."""
    step = Step(
        name="next",
        image="templates/next.png",
        verify_transition=True,
        transition_threshold=0.05,
        transition_region=(0, 100, 1920, 800),
    )
    assert step.verify_transition is True
    assert step.transition_threshold == 0.05
    assert step.transition_region == (0, 100, 1920, 800)


def test_step_settle_ms_defaults_to_300() -> None:
    """settle_ms defaults to 300 ms — chosen to absorb React/DOM render latency
    before verify_transition reads the post-click frame. The legacy 50 ms
    constant was tight enough that web UI updates often completed *after* the
    settle window."""
    step = Step(name="click", image="x.png")
    assert step.settle_ms == 300


def test_step_settle_ms_can_be_overridden() -> None:
    """Recipe author can dial settle_ms up for heavy SPAs or down for native UI."""
    fast = Step(name="instant-toggle", image="x.png", settle_ms=50)
    slow = Step(name="heavy-spa", image="x.png", settle_ms=800)
    assert fast.settle_ms == 50
    assert slow.settle_ms == 800


def test_step_settle_ms_accepts_zero() -> None:
    """settle_ms=0 disables the post-click pause — used by tests and synchronous
    native UI where any sleep is wasted."""
    step = Step(name="x", image="x.png", settle_ms=0)
    assert step.settle_ms == 0


def test_step_settle_ms_rejects_negative() -> None:
    """Negative settle_ms is nonsensical and must be rejected at schema time."""
    with pytest.raises(ValidationError):
        Step(name="x", image="x.png", settle_ms=-1)


def test_step_settle_ms_rejects_above_ceiling() -> None:
    """settle_ms upper bound (10 s) prevents accidental run hangs from a typo'd
    value (e.g. someone writing seconds instead of ms)."""
    with pytest.raises(ValidationError):
        Step(name="x", image="x.png", settle_ms=10_001)


# ---- Validation failure paths ---------------------------------------


def test_step_without_image_or_coord_fails_validation() -> None:
    """A step that declares neither image nor coord is invalid."""
    with pytest.raises(ValidationError) as exc_info:
        Step(name="empty")
    assert "must declare at least one of 'image' or 'coord'" in str(exc_info.value)


def test_step_with_prefer_image_but_no_image_fails_validation() -> None:
    """prefer='image' but no image declared is a recipe authoring mistake."""
    with pytest.raises(ValidationError) as exc_info:
        Step(name="x", coord=StepCoord(x=1, y=2), prefer="image")
    assert "prefer='image' but no image declared" in str(exc_info.value)


def test_step_with_prefer_coord_but_no_coord_fails_validation() -> None:
    """prefer='coord' but no coord declared is a recipe authoring mistake."""
    with pytest.raises(ValidationError) as exc_info:
        Step(name="x", image="x.png", prefer="coord")
    assert "prefer='coord' but no coord declared" in str(exc_info.value)


def test_step_with_invalid_prefer_value_fails_validation() -> None:
    """prefer must be one of the allowed Literal values."""
    with pytest.raises(ValidationError):
        Step(
            name="x",
            image="x.png",
            coord=StepCoord(x=1, y=2),
            prefer="random",  # type: ignore[arg-type]
        )


def test_step_confidence_out_of_range_fails_validation() -> None:
    """confidence must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        Step(name="x", image="x.png", confidence=1.5)


def test_step_transition_threshold_out_of_range_fails_validation() -> None:
    """transition_threshold must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        Step(name="x", image="x.png", transition_threshold=2.0)


# ---- WaitFor and helper models --------------------------------------


def test_wait_for_defaults_match_post_click_signal_shape() -> None:
    """WaitFor defaults are aligned with PostClickSignal so authors carry one
    mental model for both pre- and post-click image polling."""
    wait = WaitFor(image="x.png")
    assert wait.confidence == 0.9
    assert wait.timeout == 5.0
    assert wait.interval == 0.1
    assert wait.region is None


def test_wait_for_with_region_restricts_search_area() -> None:
    """WaitFor accepts an optional region for faster, scoped searches."""
    wait = WaitFor(image="x.png", region=(100, 100, 500, 500))
    assert wait.region == (100, 100, 500, 500)


def test_step_coord_requires_int_fields() -> None:
    """StepCoord x and y must be integers (pixel coordinates)."""
    with pytest.raises(ValidationError):
        StepCoord(x=10.5, y=20)  # type: ignore[arg-type]
