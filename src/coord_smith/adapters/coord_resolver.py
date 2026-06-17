"""Click-coordinate resolver — extracted from PyAutoGUIAdapter (B-CA-4 wave 2).

A coord-smith Step declares its click target as:

- an ``image`` template path (matched on the live screen via
  ``pyautogui.locateCenterOnScreen``), OR
- a fixed ``coord: { x, y }`` pair, OR
- BOTH, with ``prefer`` choosing the primary and the other as
  the implicit fallback.

Resolving the actual ``(x, y)`` from those declarations is a
self-contained concern: take a Step, return coords, raise typed
errors on failure. It does not need OS-cursor state, screenshot
capture, or per-step guards — it only needs to call
``locateCenterOnScreen`` and write a per-match log entry on
success.

This module owns that concern so the adapter's main file (which
was 892 lines pre-B-CA-4 and 865 lines after the step_guards
extraction) stays focused on the click + screenshot primitives.

The free functions take a ``CoordResolverCollaborator`` Protocol
to access the two adapter facilities they need:
``_assert_template_exists`` (existence-check helper) and the
match-log writer. Adapter satisfies it naturally; test doubles
can too.

Coordinate priority order (ADR-003, unchanged):

    payload(OpenClaw)  >  step.coord  >  step.image  >  no-click

This module sits at "step.coord vs step.image" — the payload
override is applied upstream in the adapter's
``_execute_step_dispatch`` before this resolver runs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pyautogui

from coord_smith.config.click_recipe import (
    DEFAULT_IMAGE_CONFIDENCE,
    DEFAULT_IMAGE_GRAYSCALE,
    MissionImageClick,
    Step,
)
from coord_smith.models.errors import (
    ConfigError,
    ImageMatchConfidenceLow,
    ImageTemplateNotFound,
)


class CoordResolverCollaborator(Protocol):
    """Minimal facilities the resolver needs from its host.

    The adapter satisfies this Protocol; tests can supply a
    double. Keeps the resolver decoupled from pyautogui_adapter
    at the type level.
    """

    def _assert_template_exists(
        self, image: str, *, owner: str, role: str
    ) -> Path: ...

    @property
    def _log(self) -> _MatchLogger: ...


class _MatchLogger(Protocol):
    """Minimal slice of ActionLogWriter the resolver uses."""

    def write_image_match(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        x: int,
        y: int,
    ) -> None: ...


def locate_image_target(
    mission: str,
    target: MissionImageClick,
    *,
    collaborator: CoordResolverCollaborator,
) -> tuple[int, int]:
    """Match a template image against the live screen; return centre coords.

    Records the located coordinates + effective confidence to the
    per-mission action-log entry so a later evidence audit can
    trace which template produced which click.

    Raises:
        ImageTemplateNotFound: ``target.image`` does not exist on disk.
        ImageMatchConfidenceLow: template never matched at
            ``target.confidence`` threshold (or pyautogui's
            ``ImageNotFoundException`` fired).
    """
    template_path = collaborator._assert_template_exists(
        target.image,
        owner=f"mission '{mission}'",
        role="image",
    )
    _not_matched = (
        f"image template not matched for mission '{mission}' "
        f"at confidence>={target.confidence}: {template_path}"
    )
    try:
        located = pyautogui.locateCenterOnScreen(
            str(template_path),
            confidence=target.confidence,
            region=target.region,
            grayscale=target.grayscale,
        )
    except pyautogui.ImageNotFoundException as exc:
        raise ImageMatchConfidenceLow(_not_matched) from exc
    if located is None:
        raise ImageMatchConfidenceLow(_not_matched)
    cx, cy = int(located.x), int(located.y)
    collaborator._log.write_image_match(
        mission=mission,
        template=str(template_path),
        confidence=target.confidence,
        x=cx,
        y=cy,
    )
    return (cx, cy)


def locate_image_for_step(
    step: Step,
    *,
    collaborator: CoordResolverCollaborator,
) -> tuple[int, int]:
    """Locate the step's image template via :func:`locate_image_target`.

    Wraps the step's image-related fields into the
    ``MissionImageClick`` shape the matcher expects. Defaults
    apply: ``confidence`` → 0.9 if unset, ``grayscale`` → False.

    Raises ``ConfigError`` if called on a Step with ``image=None``
    (schema-unreachable; the Pydantic validator rejects this
    construction. The check is defense-in-depth for
    ``Step.model_construct`` paths that bypass validation.)
    """
    if step.image is None:  # pragma: no cover — schema-enforced
        raise ConfigError(
            f"Step '{step.name}' reached locate_image_for_step "
            "with image=None — violates the Step schema invariant"
        )
    target = MissionImageClick(
        image=step.image,
        confidence=step.confidence
        if step.confidence is not None
        else DEFAULT_IMAGE_CONFIDENCE,
        region=step.region,
        grayscale=step.grayscale
        if step.grayscale is not None
        else DEFAULT_IMAGE_GRAYSCALE,
    )
    return locate_image_target(step.name, target, collaborator=collaborator)


def locate_image_or_none(
    step: Step,
    *,
    collaborator: CoordResolverCollaborator,
) -> tuple[tuple[int, int] | None, BaseException | None]:
    """Attempt image match; return ``(coords, captured_error)``.

    Explicit Result-style return — the caller pattern-matches
    on which slot is populated:

    - ``(coords, None)`` — match succeeded; use coords.
    - ``(None, exc)`` — match failed; ``exc`` is the typed
      dispatch error preserved for diagnostic re-raise.

    Only ``ImageTemplateNotFound`` and ``ImageMatchConfidenceLow``
    are captured. OS-level failures (e.g.
    ``ScreenCaptureUnavailable``) propagate immediately — those
    are "match could not run at all" and the caller cannot
    recover by trying the coord fallback.
    """
    if step.image is None:
        return (None, None)
    try:
        return (locate_image_for_step(step, collaborator=collaborator), None)
    except (ImageTemplateNotFound, ImageMatchConfidenceLow) as exc:
        return (None, exc)


def coord_or_none(step: Step) -> tuple[int, int] | None:
    """Return the step's declared coord, or ``None`` if absent.

    Trivial helper paired with :func:`locate_image_or_none` so
    the resolver's pattern-match reads symmetrically. No
    collaborator needed — pure function of the Step.
    """
    if step.coord is None:
        return None
    return (step.coord.x, step.coord.y)


def resolve_step_click_coords(
    step: Step,
    *,
    collaborator: CoordResolverCollaborator,
) -> tuple[int, int] | None:
    """Resolve a step's click coordinates using prefer + fallback chain.

    Three regimes, in order of precedence:

    1. **Both image and coord declared** — ``step.prefer`` decides the
       primary; if the primary fails (image not matched), the
       fallback is tried. If both fail, the primary's typed
       exception is re-raised (preserved from the original
       attempt, not synthesized by re-running) so the caller sees
       the most specific diagnosis.
    2. **Single target declared** — image-only or coord-only. The
       target's typed exception (if any) propagates directly; no
       silent swallowing.
    3. **Neither declared** — returns ``None``. The Step Pydantic
       validator normally rejects this, but ``Step.model_construct``
       bypasses validation, so a graceful no-op is the safe
       behaviour.

    Implementation notes:

    - The image branch returns ``(coords, captured_error)`` so the
      dual-target failure path can re-raise the *original* error
      instance with full traceback — no re-running of the matcher
      (which would lose context and double the cost on a failing
      run). See ADR for the Result-style refactor history
      (B-ROP-2 closure).
    - Evaluation is lazy: when the primary succeeds, the
      fallback is NOT invoked. Image matching has a real side
      effect (screenshot + OpenCV call); ``prefer: coord``
      callers explicitly opt out of paying that cost on the
      happy path.
    """
    if step.image is None and step.coord is None:
        return None

    # Single-target regime — no fallback chain, exceptions propagate.
    if step.image is not None and step.coord is None:
        return locate_image_for_step(step, collaborator=collaborator)
    if step.coord is not None and step.image is None:
        coord_result = coord_or_none(step)
        assert coord_result is not None  # noqa: S101 — schema-guaranteed
        return coord_result

    # Dual-target regime — pattern-match on (primary, fallback).
    primary_kind: str = step.prefer or "image"

    if primary_kind == "image":
        image_coords, image_error = locate_image_or_none(
            step, collaborator=collaborator
        )
        if image_coords is not None:
            return image_coords
        coord_coords = coord_or_none(step)
        if coord_coords is not None:
            return coord_coords
        # Both failed — re-raise the captured image error.
        if image_error is not None:
            raise image_error
    else:
        # ``prefer: coord`` — coord goes first.
        coord_coords = coord_or_none(step)
        if coord_coords is not None:
            return coord_coords
        image_coords, image_error = locate_image_or_none(
            step, collaborator=collaborator
        )
        if image_coords is not None:
            return image_coords
        if image_error is not None:
            raise image_error

    # Defensive: schema-unreachable — both targets are absent.
    raise ConfigError(
        f"Step '{step.name}': dual-target resolve produced no "
        "coordinates and no diagnostic error — violates the Step "
        "schema's prefer/target invariant"
    )
