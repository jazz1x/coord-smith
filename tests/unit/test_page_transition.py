"""Tests for PageTransitionVerifier visual diff logic."""
from __future__ import annotations

from PIL import Image

from ez_ax.adapters.page_transition import (
    PageTransitionResult,
    PageTransitionVerifier,
)


def _solid(size: tuple[int, int], color: str) -> Image.Image:
    return Image.new("RGB", size, color=color)


def test_identical_frames_report_no_change() -> None:
    base = _solid((100, 100), "white")
    post = _solid((100, 100), "white")
    result = PageTransitionVerifier().verify_changed(baseline=base, post=post)
    assert result.changed is False
    assert result.change_ratio == 0.0
    assert result.bbox is None


def test_full_color_swap_reports_change() -> None:
    base = _solid((100, 100), "white")
    post = _solid((100, 100), "black")
    result = PageTransitionVerifier().verify_changed(baseline=base, post=post)
    assert result.changed is True
    assert result.change_ratio == 1.0
    assert result.bbox == (0, 0, 100, 100)


def test_local_change_below_threshold_reports_unchanged() -> None:
    base = _solid((100, 100), "white")
    post = base.copy()
    # 5x5 black square = 25 pixels of bbox out of 10000 = 0.25% < 1% threshold.
    post.paste("black", (10, 10, 15, 15))
    result = PageTransitionVerifier().verify_changed(
        baseline=base, post=post, threshold=0.01
    )
    assert result.changed is False
    assert result.change_ratio < 0.01


def test_local_change_above_threshold_reports_changed() -> None:
    base = _solid((100, 100), "white")
    post = base.copy()
    # 30x30 black square = bbox area 900 / 10000 = 9% > 1% threshold.
    post.paste("black", (10, 10, 40, 40))
    result = PageTransitionVerifier().verify_changed(
        baseline=base, post=post, threshold=0.01
    )
    assert result.changed is True
    assert result.change_ratio >= 0.05
    assert result.bbox == (10, 10, 40, 40)


def test_region_restricts_comparison_area() -> None:
    base = _solid((100, 100), "white")
    post = base.copy()
    # Paint outside the region: should not register as a change.
    post.paste("black", (60, 60, 70, 70))
    result = PageTransitionVerifier().verify_changed(
        baseline=base,
        post=post,
        threshold=0.01,
        region=(0, 0, 50, 50),
    )
    assert result.changed is False
    assert result.change_ratio == 0.0


def test_region_returns_absolute_bbox_offset_by_origin() -> None:
    base = _solid((100, 100), "white")
    post = base.copy()
    # Paint inside the region; absolute bbox should be offset by region origin.
    post.paste("black", (60, 60, 90, 90))
    result = PageTransitionVerifier().verify_changed(
        baseline=base,
        post=post,
        threshold=0.0,
        region=(50, 50, 50, 50),
    )
    assert result.changed is True
    assert result.bbox == (60, 60, 90, 90)


def test_size_mismatch_reports_full_change() -> None:
    base = _solid((100, 100), "white")
    post = _solid((200, 200), "white")
    result = PageTransitionVerifier().verify_changed(baseline=base, post=post)
    assert result.changed is True
    assert result.change_ratio == 1.0
    assert result.bbox is None


def test_capture_baseline_returns_independent_copy() -> None:
    original = _solid((10, 10), "red")
    baseline = PageTransitionVerifier().capture_baseline(original)
    assert baseline is not original
    # Mutating the original must not affect the captured baseline.
    original.paste("blue", (0, 0, 5, 5))
    assert baseline.getpixel((0, 0)) == (255, 0, 0)


def test_result_dataclass_is_frozen() -> None:
    result = PageTransitionResult(changed=True, change_ratio=0.5, bbox=(0, 0, 1, 1))
    import pytest

    with pytest.raises((AttributeError, Exception)):
        result.changed = False  # type: ignore[misc]
