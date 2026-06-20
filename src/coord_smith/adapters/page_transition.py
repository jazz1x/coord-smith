"""Visual page-transition verification for post-click confirmation.

The PyAutoGUI adapter's ``_verified_click`` only confirms that the OS allowed
the cursor to reach the target pixel — it does **not** confirm that the page
itself responded (button pressed, navigation occurred, modal opened, …).
Without DOM access (browser-internal tools are forbidden by the runtime PRD),
the only deterministic signal available is a visual change in the captured
screenshot.

``PageTransitionVerifier`` compares a baseline screenshot taken just before a
click to a follow-up screenshot taken after the click settles. The change is
quantified by the count of pixels that actually differ relative to the
comparison region. A configurable threshold (default 1 percent) decides
whether the transition counts as detected. The verifier is intentionally
simple: no perceptual hashing, no anti-aliasing tolerance — production-grade
nuance is reserved for future verifiers if real-world tuning demands it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops

Region = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class PageTransitionResult:
    """Outcome of a single visual comparison.

    ``change_ratio`` is the fraction of pixels inside the comparison region
    that actually differ between the two frames (changed-pixel count divided
    by region area).

    ``bbox`` is the pixel-diff bounding box in absolute screen coordinates,
    or ``None`` when the frames are pixel-identical. NOTE: its 4-tuple is
    ``(left, top, right, bottom)`` — PIL ``getbbox`` corner-pair semantics —
    NOT the ``(left, top, width, height)`` extent form used by the *input*
    ``region`` parameter. The two share the ``Region`` alias for brevity but
    are distinct conventions; a consumer converting bbox to width/height must
    compute ``right - left`` / ``bottom - top``. Logged verbatim as
    ``transition_bbox`` (see ``ActionLogWriter.write_transition``).
    """

    changed: bool
    change_ratio: float
    # See class docstring: (left, top, right, bottom), not (l, t, w, h).
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
            # Clamp the requested box to the actual frame bounds. A region
            # that extends past the screen edge (or starts off-screen) yields
            # a smaller *real* crop than its declared width×height; using the
            # declared area as the change_ratio denominator would dilute the
            # ratio and spuriously suppress a real transition. Intersect with
            # (0, 0, W, H) so the denominator reflects the in-bounds area.
            frame_w, frame_h = baseline.size
            clamped_left = max(0, min(left, frame_w))
            clamped_top = max(0, min(top, frame_h))
            clamped_right = max(clamped_left, min(left + width, frame_w))
            clamped_bottom = max(clamped_top, min(top + height, frame_h))
            region_size = (
                clamped_right - clamped_left,
                clamped_bottom - clamped_top,
            )
            if region_size[0] <= 0 or region_size[1] <= 0:
                # The requested region lies ENTIRELY off-screen — the clamp
                # leaves an empty rectangle. Without this guard the empty crop
                # diffs to "no change" and the caller gets a spurious
                # PageTransitionNotDetected on every click, indistinguishable
                # from a real no-transition. Surface the authoring error
                # explicitly instead of silently failing the click forever.
                raise ValueError(
                    "transition_region "
                    f"{region!r} is entirely outside the {baseline.size} "
                    "frame; nothing to compare. Fix the region coordinates."
                )
            box = (clamped_left, clamped_top, clamped_right, clamped_bottom)
            base_view = baseline.crop(box)
            post_view = post.crop(box)
            region_origin = (clamped_left, clamped_top)

        diff = ImageChops.difference(base_view, post_view)
        bbox_local = diff.getbbox()
        if bbox_local is None:
            return PageTransitionResult(changed=False, change_ratio=0.0, bbox=None)

        # change_ratio is the fraction of pixels that actually differ, not the
        # bounding-box coverage. Two tiny scattered changes (a cursor blink +
        # a focus ring) span a huge bbox but change almost no pixels — using
        # bbox area would report ~1.0 and falsely "detect" a transition. Count
        # the genuinely-changed pixels: a pixel "changed" if ANY band differs.
        # ``np.asarray`` of the multi-band diff reduces over the channel axis
        # so a 1-step move in a single channel still counts (a luminance
        # ``convert("L")`` could round it to 0). numpy is already present via
        # opencv-python, the runtime's image dependency.
        diff_arr = np.asarray(diff)
        if diff_arr.ndim == 3:
            changed_mask = diff_arr.any(axis=2)
        else:
            changed_mask = diff_arr != 0
        changed_pixels = int(changed_mask.sum())
        region_area = max(1, region_size[0] * region_size[1])
        change_ratio = changed_pixels / region_area
        bx1, by1, bx2, by2 = bbox_local
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
