"""Visual page-transition verification for post-click confirmation.

The PyAutoGUI adapter's ``_verified_click`` only confirms that the OS allowed
the cursor to reach the target pixel — it does **not** confirm that the page
itself responded (button pressed, navigation occurred, modal opened, …).
Without DOM access (browser-internal tools are forbidden by the runtime PRD),
the only deterministic signal available is a visual change in the captured
screenshot.

``PageTransitionVerifier`` compares a baseline screenshot taken just before a
click to a follow-up screenshot taken after the click settles. The change is
quantified by the bounding-box area of the pixel-level difference relative to
the comparison region. A configurable threshold (default 1 percent) decides
whether the transition counts as detected. The verifier is intentionally
simple: no perceptual hashing, no anti-aliasing tolerance — production-grade
nuance is reserved for future verifiers if real-world tuning demands it.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageChops

Region = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class PageTransitionResult:
    """Outcome of a single visual comparison.

    ``change_ratio`` is the fraction of pixels inside the comparison region
    that differ between the two frames, computed as the bounding-box area of
    the diff divided by the region area. ``bbox`` is the pixel diff bounding
    box in absolute screen coordinates, or ``None`` when the frames are
    pixel-identical.
    """

    changed: bool
    change_ratio: float
    bbox: Region | None


class PageTransitionVerifier:
    """Compare two screenshots and decide whether a visual transition occurred."""

    def capture_baseline(self, screenshot: Image.Image) -> Image.Image:
        """Return a defensive copy of the supplied baseline frame.

        The baseline is copied so the caller can release the original
        screenshot resource (e.g., close a file handle) without affecting
        the later comparison.
        """
        return screenshot.copy()

    def verify_changed(
        self,
        *,
        baseline: Image.Image,
        post: Image.Image,
        threshold: float = 0.01,
        region: Region | None = None,
    ) -> PageTransitionResult:
        """Compare ``baseline`` to ``post`` and return a structured result.

        ``threshold`` is the minimum change ratio required to declare a
        transition (default 1 percent). ``region`` restricts the comparison
        to ``(left, top, width, height)``; when ``None`` the full frames
        are compared. Mismatched frame sizes are treated as a full change.
        """
        if baseline.size != post.size:
            return PageTransitionResult(
                changed=True, change_ratio=1.0, bbox=None
            )

        if region is None:
            base_view = baseline
            post_view = post
            region_origin = (0, 0)
            region_size = baseline.size
        else:
            left, top, width, height = region
            box = (left, top, left + width, top + height)
            base_view = baseline.crop(box)
            post_view = post.crop(box)
            region_origin = (left, top)
            region_size = (width, height)

        diff = ImageChops.difference(base_view, post_view)
        bbox_local = diff.getbbox()
        if bbox_local is None:
            return PageTransitionResult(changed=False, change_ratio=0.0, bbox=None)

        bx1, by1, bx2, by2 = bbox_local
        bbox_area = max(0, (bx2 - bx1) * (by2 - by1))
        region_area = max(1, region_size[0] * region_size[1])
        change_ratio = bbox_area / region_area
        absolute_bbox: Region = (
            bx1 + region_origin[0],
            by1 + region_origin[1],
            bx2 + region_origin[0],
            by2 + region_origin[1],
        )
        return PageTransitionResult(
            changed=change_ratio >= threshold,
            change_ratio=change_ratio,
            bbox=absolute_bbox,
        )
