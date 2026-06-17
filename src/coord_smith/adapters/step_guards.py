"""Step-level pre/post-click guard helpers — extracted from PyAutoGUIAdapter (B-CA-4).

A "step" in a coord-smith recipe (see ``config/click_recipe.py``)
can declare two image-polling guards that sit on either side of
the actual click:

- ``wait_for`` runs BEFORE the click. It polls
  ``locateCenterOnScreen`` for an anchor template; if the template
  never appears within ``timeout``, the click is not dispatched
  (typed ``ImageWaitTimeout`` raised, ``phase=pre_click``).
- ``post_click_signal`` runs AFTER the click. Same polling
  primitive, but the timeout means the click happened but the
  expected outcome (e.g. success toast) did not appear
  (``phase=post_click``).

Both guards share a fixed shape: existence-check the template path,
start a timer, poll, log the outcome with template / confidence /
elapsed / matched coordinates. This module owns that shape so the
adapter's main concern stays "OS-level click execution +
screenshot capture" rather than "orchestrate all per-step
guards" (Clean Architecture audit B-CA-4 / CA-A2).

The two runners depend on a small ``StepGuardCollaborator``
``Protocol`` (existence check + image polling + log writers). The
canonical collaborator is the adapter; a test double works
equally well. This keeps the module testable without a live
``pyautogui`` import.

## Phase tagging (also extracted from the adapter)

``failure.jsonl`` records which sub-phase of a step produced the
typed exception. The constants and ``tag_phase`` helper live here
because phase labels are an artifact of step-level orchestration
— they have nothing to do with the OS click primitive.

The phase enum is **public contract** (see ADR-004 + ADR-006):
external orchestrators read ``run.json.failure.phase`` and
``failure.jsonl.phase`` to disambiguate the same ``error_class``
across phases (the headline case: ``ImageWaitTimeout`` raised
inside ``wait_for`` vs inside ``post_click_signal``).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Literal, Protocol

from coord_smith.config.click_recipe import PostClickSignal, WaitFor

# ---- Phase labels (public contract — failure.jsonl.phase) ----

PhaseName = Literal["pre_click", "dispatch", "post_click"]
"""Step sub-phase that produced a typed exception.

Public enum surfaced via ``run.json.failure.phase`` and
``failure.jsonl.phase``. Renaming any value is a public-API change
(coord-smith would need a SemVer minor bump + caller migration).
"""

PHASE_PRE_CLICK: PhaseName = "pre_click"
PHASE_DISPATCH: PhaseName = "dispatch"
PHASE_POST_CLICK: PhaseName = "post_click"

# Module-private attribute key under which the phase tag rides on
# a caught exception instance. Read back by the adapter's failure
# evidence writer.
_PHASE_ATTR = "_coord_smith_phase"


def tag_phase(exc: BaseException, phase: PhaseName) -> BaseException:
    """Attach a ``PhaseName`` tag to a caught exception in-place.

    The adapter wraps each step sub-phase in ``try``/``except`` and
    calls this helper to brand the exception before re-raising, so
    the failure-evidence writer can record the sub-phase even
    though the exception class might appear in multiple phases
    (e.g. ``ImageWaitTimeout`` from ``wait_for`` vs
    ``post_click_signal``).

    Returns the same exception instance (for fluent re-raise style).
    """
    setattr(exc, _PHASE_ATTR, phase)
    return exc


def read_phase(exc: BaseException, *, default: PhaseName = PHASE_DISPATCH) -> PhaseName:
    """Read a previously-tagged ``PhaseName`` off an exception.

    Returns ``default`` (``"dispatch"``) when the exception was
    never tagged — the legacy / pre-step-guards code path. The
    adapter's failure writer uses this to populate
    ``failure.jsonl.phase`` without crashing on untagged
    exceptions.
    """
    value: PhaseName = getattr(exc, _PHASE_ATTR, default)
    # Defensive narrowing — setattr accepts anything, but the only
    # writer is ``tag_phase`` so the value is always a ``PhaseName``.
    return value


# ---- Collaborator protocol (decouples step_guards from adapter) --


class StepGuardCollaborator(Protocol):
    """Minimal facilities the guard runners need from the adapter.

    The adapter satisfies this Protocol; a test double can too.
    Methods are intentionally name-private (``_method``) to mirror
    the adapter's current surface — the Protocol is a contract,
    not a stylistic suggestion to rename adapter methods.
    """

    def _assert_template_exists(
        self, image: str, *, owner: str, role: str
    ) -> Path: ...

    async def wait_for_image(
        self,
        *,
        path: str,
        timeout: float,
        interval: float,
        confidence: float,
        region: tuple[int, int, int, int] | None = None,
    ) -> tuple[int, int]: ...

    def _write_wait_for_log(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None: ...

    def _write_signal_log(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None: ...


# ---- Pre/post-click guard runners (free functions) --------------


async def run_pre_click_wait_for(
    *,
    mission: str,
    wait_for: WaitFor,
    collaborator: StepGuardCollaborator,
) -> None:
    """Pre-click anchor poll. Replaces ``adapter._await_pre_click_wait_for``.

    Runs *before* the click, gating whether dispatch happens at all.
    Honors ``WaitFor.region`` so callers can scope the search to a
    known panel area.

    Raises:
        ImageTemplateNotFound: ``wait_for.image`` doesn't exist on disk.
        ImageWaitTimeout: anchor template never matched within
            ``wait_for.timeout`` seconds. Caller (the adapter's
            dispatch wrapper) tags this with
            :data:`PHASE_PRE_CLICK` before re-raising.
    """
    wait_path = collaborator._assert_template_exists(
        wait_for.image,
        owner=f"mission '{mission}'",
        role="pre-click wait_for",
    )
    start = time.monotonic()
    x, y = await collaborator.wait_for_image(
        path=str(wait_path),
        timeout=wait_for.timeout,
        interval=wait_for.interval,
        confidence=wait_for.confidence,
        region=wait_for.region,
    )
    elapsed = time.monotonic() - start
    collaborator._write_wait_for_log(
        mission=mission,
        template=str(wait_path),
        confidence=wait_for.confidence,
        elapsed=elapsed,
        x=x,
        y=y,
    )


async def run_post_click_signal(
    *,
    mission: str,
    signal: PostClickSignal,
    collaborator: StepGuardCollaborator,
) -> None:
    """Post-click outcome poll. Replaces ``adapter._await_post_click_signal``.

    Runs *after* the click and the post-click settle window. A
    timeout here means the click happened but the expected outcome
    (a success toast, a state change indicator) did not appear —
    semantically distinct from a ``wait_for`` timeout even when
    both raise the same ``ImageWaitTimeout`` class.

    Raises:
        ImageTemplateNotFound: ``signal.image`` doesn't exist on disk.
        ImageWaitTimeout: signal template never matched within
            ``signal.timeout`` seconds. Caller tags with
            :data:`PHASE_POST_CLICK` before re-raising.
    """
    signal_path = collaborator._assert_template_exists(
        signal.image,
        owner=f"mission '{mission}'",
        role="post-click signal",
    )
    start = time.monotonic()
    x, y = await collaborator.wait_for_image(
        path=str(signal_path),
        timeout=signal.timeout,
        interval=signal.interval,
        confidence=signal.confidence,
    )
    elapsed = time.monotonic() - start
    collaborator._write_signal_log(
        mission=mission,
        template=str(signal_path),
        confidence=signal.confidence,
        elapsed=elapsed,
        x=x,
        y=y,
    )
