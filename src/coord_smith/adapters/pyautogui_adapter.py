"""PyAutoGUI OS-level coordinate-click adapter implementing ExecutionAdapter."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pyautogui
from PIL import UnidentifiedImageError
from PIL.Image import Image as PILImage

from coord_smith.adapters.action_log_writer import ActionLogWriter
from coord_smith.adapters.coord_resolver import resolve_step_click_coords
from coord_smith.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from coord_smith.adapters.page_transition import PageTransitionVerifier
from coord_smith.adapters.step_guards import (
    PHASE_DISPATCH,
    PHASE_POST_CLICK,
    PHASE_PRE_CLICK,
    PhaseName,
    read_phase,
    run_post_click_signal,
    run_pre_click_wait_for,
    tag_phase,
)
from coord_smith.config.click_recipe import (
    ClickRecipe,
    PostClickSignal,
    Step,
    WaitFor,
)
from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.missions.evidence_specs import MISSION_FALLBACK_REFS
from coord_smith.models.errors import (
    AccessibilityPermissionDenied,
    ClickCoordinatesOutOfBounds,
    ClickExecutionUnverified,
    ConfigError,
    ImageMatchConfidenceLow,
    ImageTemplateNotFound,
    ImageWaitTimeout,
    PageTransitionNotDetected,
    ScreenCapturePermissionDenied,
    ScreenCaptureUnavailable,
)
from coord_smith.models.identifiers import MissionName

# Imported from missions.evidence_specs — single source of truth.
# Each tuple is ordered screenshot-first for backwards-compatible artifact
# ordering.  Missions with empty fallback_refs use their primary screenshot +
# action-log pair instead (step_observe / step_dispatch / step_capture).
_FALLBACK_REFS = MISSION_FALLBACK_REFS

_GENERIC_ACTION_LOG_REF = "evidence://action-log/pyautogui-executed"

# Post-click cursor position tolerance (display scaling / animation jitter).
_CLICK_POSITION_TOLERANCE_PX = 2
# Default sleep after a low-level cursor probe (preflight / non-step cases).
# Step-driven clicks override this via ``Step.settle_ms``. The 50 ms value
# is intentionally tight here — preflight only verifies that the OS event
# pump flushed the cursor move, not that an entire SPA finished rendering.
_POST_CLICK_SETTLE_SECONDS = 0.05

# Phase labels + tagging helper live in adapters/step_guards.py
# (extracted per B-CA-4). The aliases below preserve internal
# call-site syntax (``_tag_phase`` / ``_PHASE_*``); the values
# are imported above. The phase enum is public contract — see
# step_guards.PhaseName + ADR-004.
_PHASE_PRE_CLICK = PHASE_PRE_CLICK
_PHASE_DISPATCH = PHASE_DISPATCH
_PHASE_POST_CLICK = PHASE_POST_CLICK


def _tag_phase(exc: BaseException, phase: PhaseName) -> BaseException:
    """Thin alias for :func:`step_guards.tag_phase`.

    Kept as a module-level name so existing call sites in
    ``_dispatch_with_step`` and ``_capture_failure_evidence`` need
    no edits beyond the imports above. New code should call
    ``step_guards.tag_phase`` directly.
    """
    return tag_phase(exc, phase)


def _payload_override_coords(
    payload: dict[str, object],
) -> tuple[int, int] | None:
    """Extract a caller-injected ``(x, y)`` click override from the payload.

    ADR-003 coordinate priority level 1: when the caller (OpenClaw) supplies
    runtime-computed coordinates they override the recipe entirely. The
    override is honored only when BOTH ``x`` and ``y`` are present and are
    ``int`` (``bool`` excluded — it is an ``int`` subclass but never a valid
    pixel coordinate). A partial override (one axis present, or a non-int
    value) raises ``ConfigError`` rather than silently falling through to the
    recipe: a half-specified override is always a caller mistake, and masking
    it would click the wrong place with no signal.
    """
    has_x = "x" in payload
    has_y = "y" in payload
    if not has_x and not has_y:
        return None
    x = payload.get("x")
    y = payload.get("y")
    if (
        isinstance(x, int)
        and not isinstance(x, bool)
        and isinstance(y, int)
        and not isinstance(y, bool)
    ):
        return (x, y)
    raise ConfigError(
        "payload coordinate override must supply BOTH integer 'x' and 'y' "
        f"(got x={x!r}, y={y!r}); a partial or non-integer override is a "
        "caller error, not a fall-through to the recipe coords"
    )


class PyAutoGUIAdapter:
    """OS-level coordinate-click adapter implementing ExecutionAdapter protocol.

    Uses pyautogui.click() and pyautogui.screenshot() exclusively.
    Contains no LLM inference; all navigation is coordinate-driven.

    All OS-level failures raise typed ExecutionTransportError subclasses.
    Silent no-ops (e.g. macOS Accessibility permission missing) are detected
    via post-click cursor position verification and raised as
    ClickExecutionUnverified rather than returning a bogus success.
    """

    def __init__(
        self,
        *,
        run_root: Path,
        click_recipe: ClickRecipe | None = None,
    ) -> None:
        pyautogui.FAILSAFE = True
        self._run_root = run_root
        self._click_recipe = click_recipe
        self._log = ActionLogWriter(run_root)

    def with_run_root(self, *, run_root: Path) -> PyAutoGUIAdapter:
        """Return a copy of this adapter bound to a different run root."""
        return PyAutoGUIAdapter(run_root=run_root, click_recipe=self._click_recipe)

    def _action_log_path(self, key: str) -> Path:
        return self._log.action_log_path(key)

    def _screenshot_path(self, key: str, *, step_idx: int | None = None) -> Path:
        """Resolve the on-disk screenshot path for an evidence *key*.

        For per-step missions (``step_observe`` / ``step_dispatch`` /
        ``step_capture``) the same evidence key recurs on every step
        iteration, so the filename is prefixed with the zero-padded
        ``step_idx`` to keep each step's frame distinct on disk. Without
        the prefix every step would overwrite the previous step's PNG,
        leaving only the final step's frame — an auditor reading per-step
        screenshot evidence would get the wrong frame for every earlier
        step. The failure path already keys by ``step_idx`` (see
        ``_capture_failure_evidence``); this restores the same per-step
        identity on the success path. The logical evidence ref
        (``evidence://screenshot/<key>``) is unchanged — only the on-disk
        filename gains the prefix.
        """
        filename = f"{step_idx:02d}-{key}.png" if step_idx is not None else f"{key}.png"
        path = self._run_root / "artifacts" / "screenshot" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _capture_screenshot(self, key: str, *, step_idx: int | None = None) -> None:
        """Capture a screenshot or raise a typed error.

        macOS screencapture with denied Screen Recording permission yields a
        zero-byte file, which PIL rejects as UnidentifiedImageError. That is
        mapped to ScreenCapturePermissionDenied so the failure is visible to
        the caller instead of being swallowed.
        """
        try:
            screenshot = pyautogui.screenshot()
        except UnidentifiedImageError as exc:
            raise ScreenCapturePermissionDenied(
                "screenshot refused by OS (grant Screen Recording permission "
                "to the host terminal app and retry)"
            ) from exc
        except Exception as exc:
            raise ScreenCaptureUnavailable(
                f"pyautogui.screenshot failed: {exc!r}"
            ) from exc
        path = self._screenshot_path(key, step_idx=step_idx)
        try:
            screenshot.save(str(path))
        except Exception as exc:
            # The capture succeeded but writing it to disk failed (ENOSPC,
            # read-only artifacts dir, PIL encode error). Route it through the
            # SAME typed channel as a capture failure so the per-step
            # failure-evidence net catches it and run.json gets a populated
            # failure block instead of failure=null — otherwise a successful
            # click whose post-click save fails becomes an unattributed crash.
            raise ScreenCaptureUnavailable(
                f"screenshot save to {path} failed: {exc!r}"
            ) from exc

    def _validate_bounds(self, x: int, y: int) -> None:
        size = pyautogui.size()
        if not (0 <= x < size.width and 0 <= y < size.height):
            raise ClickCoordinatesOutOfBounds(
                f"click target ({x}, {y}) outside screen bounds "
                f"({size.width}x{size.height})"
            )

    async def _verified_click(
        self, x: int, y: int, *, settle_seconds: float | None = None
    ) -> None:
        """Click and verify the OS actually moved the cursor.

        ``settle_seconds`` controls the pause between the click call and the
        cursor-position read used to detect silent permission failures. The
        same delay is honored by callers (e.g. ``_dispatch_with_step``)
        before they snap the post-click frame for transition diff, so step
        recipes get one consistent settle knob.

        When ``settle_seconds`` is ``None`` the legacy 50 ms constant is
        used. Step-driven clicks always pass ``step.settle_ms / 1000.0``;
        the ``None`` default exists for non-step callers (preflight,
        ad-hoc tests).
        """
        delay = _POST_CLICK_SETTLE_SECONDS if settle_seconds is None else settle_seconds
        pyautogui.click(x, y)
        if delay > 0:
            await asyncio.sleep(delay)
        actual = pyautogui.position()
        if (
            abs(actual.x - x) > _CLICK_POSITION_TOLERANCE_PX
            or abs(actual.y - y) > _CLICK_POSITION_TOLERANCE_PX
        ):
            raise ClickExecutionUnverified(
                f"click target=({x}, {y}) but cursor at ({actual.x}, {actual.y}) "
                "— likely Accessibility permission missing"
            )

    def _gather_evidence(
        self, mission: MissionName, *, step_idx: int | None = None
    ) -> tuple[str, ...]:
        mission_refs = _FALLBACK_REFS.get(mission)
        if mission_refs is None:
            action_key = mission.replace("_", "-")
            self._log.write_action_log(key=action_key, mission_name=mission)
            return (_GENERIC_ACTION_LOG_REF,)
        for ref in mission_refs:
            kind, key = parse_released_evidence_ref(ref)
            if kind == "action-log":
                self._log.write_action_log(key=key, mission_name=mission)
            elif kind == "screenshot":
                # step_idx is threaded only for per-step missions; per-run
                # missions (attach/prepare/run_completion) run once and pass
                # None, keeping their flat <key>.png filename.
                self._capture_screenshot(key, step_idx=step_idx)
        return mission_refs

    async def preflight(self) -> None:
        """Fail-loudly smoke test for OS permissions before any mission runs.

        Accessibility check: move the cursor by ±10 px on the X axis and
        verify the new position matches. The probe direction is chosen at
        runtime: +10 px when there is room to the right, −10 px when the
        cursor is near the right screen edge (avoids boundary clipping that
        would produce a false AccessibilityPermissionDenied). If the cursor
        does not move, macOS Accessibility permission is missing for the
        host terminal app and pyautogui is silently no-opping. Restores
        the original position.

        The cold-start probe is preceded by a no-op moveTo to the current
        position so the CoreGraphics event pump is warm by the time the
        real probe fires; on macOS the very first moveTo after a
        fresh pyautogui import can be dropped even when permission is
        actually granted, producing a flaky preflight failure. The warmup
        is genuinely no-op for permission detection (it targets the start
        position) and adds a single settle interval.

        Screen Recording check: take one screenshot. UnidentifiedImageError
        is the canonical macOS zero-byte symptom and maps to
        ScreenCapturePermissionDenied.
        """
        try:
            start = pyautogui.position()
        except Exception as exc:  # pragma: no cover — position() rarely fails
            raise AccessibilityPermissionDenied(
                f"pyautogui.position() failed: {exc!r}"
            ) from exc
        screen = pyautogui.size()
        # Warmup: prime the CG event pump before the real probe.
        #
        # A cursor parked at a FAILSAFE corner would make this first moveTo
        # raise FailSafeException — pyautogui's failSafeCheck inspects the
        # CURRENT position before moving. FAILSAFE is a DISPATCH safety hatch
        # (slam the cursor into a corner to abort a runaway recipe), NOT a
        # preflight concern: a 10px permission probe is not a dispatch. So if
        # the cursor sits at a corner, relocate it to screen-centre with the
        # check momentarily suppressed, then IMMEDIATELY restore FAILSAFE=True —
        # it is True for the probe below and for every actual click. Without
        # this, a corner-parked cursor on a fully-permitted host crashes
        # preflight as a generic exit-1 instead of yielding the permission
        # verdict (exit 2) preflight exists to produce.
        try:
            pyautogui.moveTo(start.x, start.y, duration=0)
        except pyautogui.FailSafeException:
            pyautogui.FAILSAFE = False
            try:
                pyautogui.moveTo(screen.width // 2, screen.height // 2, duration=0)
            finally:
                pyautogui.FAILSAFE = True
            start = pyautogui.position()
        await asyncio.sleep(_POST_CLICK_SETTLE_SECONDS)
        probe_delta = 10 if start.x + 10 < screen.width else -10
        probe_x = start.x + probe_delta
        probe_y = start.y
        pyautogui.moveTo(probe_x, probe_y, duration=0)
        await asyncio.sleep(_POST_CLICK_SETTLE_SECONDS)
        after = pyautogui.position()
        if (
            abs(after.x - probe_x) > _CLICK_POSITION_TOLERANCE_PX
            or abs(after.y - probe_y) > _CLICK_POSITION_TOLERANCE_PX
        ):
            # Best-effort restore before raising.
            pyautogui.moveTo(start.x, start.y, duration=0)
            raise AccessibilityPermissionDenied(
                "pyautogui.moveTo did not reach target — Accessibility permission "
                "likely missing for the host terminal app"
            )
        pyautogui.moveTo(start.x, start.y, duration=0)
        # Screen capture smoke — raises typed error if refused.
        try:
            image = pyautogui.screenshot()
        except UnidentifiedImageError as exc:
            raise ScreenCapturePermissionDenied(
                "preflight screenshot refused — grant Screen Recording permission"
            ) from exc
        except Exception as exc:
            raise ScreenCaptureUnavailable(
                f"preflight screenshot failed: {exc!r}"
            ) from exc
        if not isinstance(image, PILImage):
            raise ScreenCaptureUnavailable(
                "preflight screenshot returned unexpected type: "
                f"expected PIL.Image, got {type(image)!r}"
            )
        if image.size == (0, 0):
            raise ScreenCaptureUnavailable("preflight screenshot returned empty image")

    def _assert_template_exists(
        self, image: str, *, owner: str, role: str
    ) -> Path:
        """Defense-in-depth existence check for an image template path.

        Paths that flow through ``load_click_recipe._resolve`` are
        already typed ``ResolvedImagePath`` (see
        ``coord_smith.models.identifiers``) and have been
        existence-checked at recipe load time. But Step / WaitFor /
        PostClickSignal instances can also be constructed directly
        via Pydantic's ``model_construct`` (test fixtures, future
        external-caller payloads, hand-built ad-hoc dispatches) —
        those bypass the resolver. We re-check here so a malformed
        construction surfaces ``ImageTemplateNotFound`` with a clear
        owner/role attribution instead of an opaque OpenCV error.

        ``owner`` identifies the mission or step (for log readability);
        ``role`` distinguishes "click target" / "wait_for anchor" /
        "post-click signal" in the error message.
        """
        path = Path(image)
        if not path.exists():
            raise ImageTemplateNotFound(
                f"{role} template not found for {owner}: {path}"
            )
        return path

    def _write_transition_log(
        self,
        *,
        mission: str,
        changed: bool,
        change_ratio: float,
        bbox: tuple[int, int, int, int] | None,
        threshold: float,
    ) -> None:
        self._log.write_transition(
            mission=mission,
            changed=changed,
            change_ratio=change_ratio,
            bbox=bbox,
            threshold=threshold,
        )

    def _write_signal_log(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None:
        self._log.write_signal(
            mission=mission,
            template=template,
            confidence=confidence,
            elapsed=elapsed,
            x=x,
            y=y,
        )

    async def wait_for_image(
        self,
        *,
        path: str,
        timeout: float = 5.0,
        interval: float = 0.1,
        confidence: float = 0.9,
        region: tuple[int, int, int, int] | None = None,
        role: str = "image",
    ) -> tuple[int, int]:
        """Poll ``locateCenterOnScreen`` until the template appears or timeout elapses.

        Returns the matched center coordinates. Raises ``ImageWaitTimeout``
        when the template never appears within ``timeout`` seconds.
        ``interval`` controls polling cadence; smaller values increase CPU.
        ``region`` (optional ``(left, top, width, height)``) restricts the
        search rectangle on each poll — used by ``Step.wait_for`` when the
        anchor element has a known screen location.
        """
        deadline = time.monotonic() + timeout
        last_exc: Exception | None = None
        while True:
            try:
                located = pyautogui.locateCenterOnScreen(
                    path, confidence=confidence, region=region
                )
            except pyautogui.ImageNotFoundException as exc:
                located = None
                last_exc = exc
            if located is not None:
                return (int(located.x), int(located.y))
            if time.monotonic() >= deadline:
                msg = (
                    f"{role} '{path}' not found within "
                    f"{timeout:.2f}s at confidence>={confidence}"
                )
                if last_exc is not None:
                    raise ImageWaitTimeout(msg) from last_exc
                raise ImageWaitTimeout(msg)
            await asyncio.sleep(interval)

    def _verify_page_transition(
        self,
        *,
        mission: str,
        baseline: PILImage,
        threshold: float,
        region: tuple[int, int, int, int] | None,
    ) -> None:
        """Capture a post-click frame and compare against the baseline."""
        try:
            post = pyautogui.screenshot()
        except Exception as exc:
            raise ScreenCaptureUnavailable(
                f"post-click screenshot failed: {exc!r}"
            ) from exc
        if not isinstance(post, PILImage):
            raise ScreenCaptureUnavailable(
                "post-click screenshot returned unexpected type: "
                f"expected PIL.Image, got {type(post)!r}"
            )
        try:
            result = PageTransitionVerifier().verify_changed(
                baseline=baseline,
                post=post,
                threshold=threshold,
                region=region,
            )
        except ValueError as exc:
            # An entirely-off-screen transition_region leaves an empty crop
            # (see PageTransitionVerifier.verify_changed). Surface it as a
            # typed dispatch failure with the real cause named, instead of the
            # generic "below threshold" message — the region is the bug, not a
            # missing page change. Still PageTransitionNotDetected so the
            # failure-evidence path fires and the phase tag stays 'post_click'.
            raise PageTransitionNotDetected(
                f"transition verification for mission '{mission}' could not "
                f"run: {exc}"
            ) from exc
        self._write_transition_log(
            mission=mission,
            changed=result.changed,
            change_ratio=result.change_ratio,
            bbox=result.bbox,
            threshold=threshold,
        )
        if not result.changed:
            raise PageTransitionNotDetected(
                f"page transition below threshold for mission '{mission}': "
                f"change_ratio={result.change_ratio:.4f} < {threshold:.4f}"
            )

    def _write_wait_for_log(
        self,
        *,
        mission: str,
        template: str,
        confidence: float,
        elapsed: float,
        x: int,
        y: int,
    ) -> None:
        self._log.write_wait_for(
            mission=mission,
            template=template,
            confidence=confidence,
            elapsed=elapsed,
            x=x,
            y=y,
        )

    async def _await_pre_click_wait_for(
        self, *, mission: str, wait_for: WaitFor
    ) -> None:
        """Delegate to :func:`step_guards.run_pre_click_wait_for`.

        Kept on the adapter as a stable internal entry point —
        ``_dispatch_with_step`` calls ``self._await_pre_click_wait_for``
        and gets the step-guards behaviour through this one-line
        delegation. The body that used to live here moved to
        ``adapters/step_guards.py`` (B-CA-4).
        """
        await run_pre_click_wait_for(
            mission=mission, wait_for=wait_for, collaborator=self
        )

    async def _await_post_click_signal(
        self, *, mission: str, signal: PostClickSignal
    ) -> None:
        """Delegate to :func:`step_guards.run_post_click_signal`."""
        await run_post_click_signal(
            mission=mission, signal=signal, collaborator=self
        )

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute a mission using OS-level coordinate click and screenshot.

        Dispatch table:

        * ``step_dispatch`` — perform the actual click using
          ``payload['step']`` (an image-or-coord step decoded from a Step
          model). Honors ``prefer`` for primary/fallback ordering when both
          ``image`` and ``coord`` are declared, and applies any declared
          ``verify_transition`` / ``post_click_signal`` post-click guards.
        * ``step_observe`` / ``step_capture`` / ``attach_session`` /
          ``prepare_session`` / ``run_completion`` — no click; emit the
          per-mission evidence pair (action-log + screenshot) and return.
        """
        mission = request.mission_name
        payload = request.payload

        if mission == "step_dispatch":
            await self._execute_step_dispatch(payload)

        # Per-step missions carry step_idx in the payload; thread it so each
        # step's success-path screenshot is keyed distinctly on disk instead
        # of overwriting the previous step's frame. Per-run missions have no
        # step_idx and keep the flat filename.
        step_idx_obj = payload.get("step_idx")
        step_idx = step_idx_obj if isinstance(step_idx_obj, int) else None
        # A screenshot/evidence-gather failure on a non-dispatch mission must
        # still write a failure.jsonl record — otherwise run.json reports
        # status=failure with failure=null and no attribution. (step_dispatch
        # captures its own failures inside _execute_step_dispatch.) Per-step
        # missions (observe pre-click, capture post-click) attribute to the
        # gather node + phase; per-run missions (attach_session / prepare_
        # session / run_completion, step_idx=None) attribute to the mission with
        # step_idx=-1 so even a setup/teardown screenshot failure is captured.
        try:
            evidence_refs = self._gather_evidence(mission, step_idx=step_idx)
        except ScreenCaptureUnavailable as exc:
            if step_idx is not None:
                step_obj = payload.get("step")
                step_name = step_obj.name if isinstance(step_obj, Step) else ""
                # step_dispatch reaches this gather only AFTER _execute_step_
                # dispatch's own click + guards succeeded, so a post-dispatch
                # evidence-capture failure is post-click, NOT a click failure —
                # without this it would default to phase='dispatch' and tell the
                # caller the click failed when it actually landed.
                gather_phase: PhaseName | None = {
                    "step_observe": _PHASE_PRE_CLICK,
                    "step_dispatch": _PHASE_POST_CLICK,
                    "step_capture": _PHASE_POST_CLICK,
                }.get(mission)
                self._capture_failure_evidence(
                    step_idx=step_idx,
                    step_name=step_name,
                    error=exc,
                    mission=mission,
                    phase=gather_phase,
                )
            else:
                self._capture_failure_evidence(
                    step_idx=-1, step_name="", error=exc, mission=mission
                )
            raise
        return ExecutionResult(
            mission_name=mission,
            evidence_refs=evidence_refs,
        )

    async def _execute_step_dispatch(self, payload: dict[str, object]) -> None:
        """Perform a click for a single step from a multi-step recipe.

        Resolves the click target from ``payload['step']`` (the serialized
        Step model). When both ``image`` and ``coord`` are declared, the
        ``prefer`` field decides the primary attempt and the other becomes
        the fallback. ``verify_transition`` and ``post_click_signal`` apply
        to the dispatched click when present on the step.

        On any typed dispatch failure (image-not-matched, out-of-bounds,
        click-unverified, transition-not-detected, signal-timeout), a
        diagnostic screenshot of the current screen plus a structured
        action-log record are written to the run's ``failure/`` directory
        BEFORE the exception propagates. This gives the caller (e.g.
        OpenClaw) a self-contained record of what the screen looked like
        at the moment of failure.
        """
        step_data = payload.get("step")
        # Producer (released_call_site.py) passes the Step instance
        # directly to avoid an in-process model_dump → dict →
        # model_validate round-trip (parse-don't-validate: the model
        # was already parsed at recipe load time, no benefit in
        # re-parsing it across an in-process boundary). The dict path
        # is retained so external tests / future transports that
        # serialise across an actual process boundary still work.
        if isinstance(step_data, Step):
            step = step_data
        elif isinstance(step_data, dict):
            step = Step.model_validate(step_data)
        else:
            raise ConfigError(
                "step_dispatch payload must include a 'step' entry: "
                "either a Step instance (in-process) or a dict "
                "(serialised Step model)"
            )
        step_idx_obj = payload.get("step_idx")
        step_idx = int(step_idx_obj) if isinstance(step_idx_obj, int) else -1

        # Coordinate priority level 1 (ADR-003): a caller (OpenClaw) may
        # inject runtime-computed coords into the payload. When BOTH x and y
        # are present and integral, they override the recipe's step.coord /
        # step.image entirely. Partial (x without y, or non-int) is rejected
        # rather than silently half-applied — a partial override is always a
        # caller bug, and falling through to the recipe would mask it.
        payload_coords = _payload_override_coords(payload)

        try:
            await self._dispatch_with_step(step, payload_coords=payload_coords)
        except (
            ImageTemplateNotFound,
            ImageMatchConfidenceLow,
            ClickCoordinatesOutOfBounds,
            ClickExecutionUnverified,
            PageTransitionNotDetected,
            ImageWaitTimeout,
            ScreenCaptureUnavailable,
            pyautogui.FailSafeException,
        ) as exc:
            # ScreenCaptureUnavailable is included so a capture failure during
            # a verify_transition step still writes a failure.jsonl record
            # (the diagnostic screenshot itself may not be capturable, but the
            # structured log entry is — see _capture_failure_evidence, which
            # writes the entry even when the screenshot grab fails). Honors
            # the documented "any typed dispatch failure writes evidence"
            # contract. Permission errors are intentionally NOT caught here:
            # they must reach main()'s exit-2 handler, not be recorded as a
            # per-step dispatch failure.
            #
            # FailSafeException is the FAILSAFE=True emergency abort (user
            # slams the cursor into a screen corner). It is NOT an AppError,
            # so without this branch it would escape the failure-evidence net
            # and produce run.json with failure=null — indistinguishable from
            # an arbitrary crash. Capturing it here records the step/phase and
            # error_class=FailSafeException before re-raising unchanged (still
            # exit 1); the caller can now see the run aborted at a specific
            # step rather than vanishing without attribution.
            self._capture_failure_evidence(
                step_idx=step_idx, step_name=step.name, error=exc
            )
            raise

    async def _dispatch_with_step(
        self, step: Step, *, payload_coords: tuple[int, int] | None = None
    ) -> None:
        """Inner click logic — separated so the failure-capture wrapper above
        can stay focused on exception interception.

        ``payload_coords`` carries an optional caller-injected ``(x, y)``
        override (ADR-003 priority level 1). When present it is clicked
        directly and recipe-side coord/image resolution is skipped; the
        pre-/post-click guards still run as declared. When ``None`` the
        coords resolve from the recipe step (``step.coord`` / ``step.image``).

        Ordering: pre-click ``wait_for`` guard (if declared) →
        resolve click coords → optional ``verify_transition`` baseline →
        click → optional post-click verification → optional
        ``post_click_signal`` poll. ``wait_for`` runs *before* coord
        resolution so timing-sensitive templates (e.g. an anchor element
        that animates in) get a chance to appear before the matcher even
        looks at the click target.

        Each phase is wrapped to tag any escaping exception with a
        phase label (``pre_click`` / ``dispatch`` / ``post_click``) so
        the failure-capture wrapper above can record which sub-phase
        fired. The same typed exception class can originate from
        multiple phases (e.g. ``ImageWaitTimeout`` from ``wait_for`` vs
        ``post_click_signal``); the phase tag is what disambiguates
        them for callers reading ``failure.jsonl``.
        """
        if step.wait_for is not None:
            try:
                await self._await_pre_click_wait_for(
                    mission=step.name, wait_for=step.wait_for
                )
            except BaseException as exc:
                # Mutate the exception in place (attach phase tag) and
                # re-raise with a bare ``raise``. This preserves
                # Python's implicit ``__context__`` chain — using
                # ``raise X from exc.__cause__`` would null out the
                # chain whenever the inner raise was a plain
                # ``raise SomethingError(...)`` (no explicit cause),
                # which is the common case in this codebase.
                _tag_phase(exc, _PHASE_PRE_CLICK)
                raise

        # --- dispatch phase: coord resolution + click execution -----
        try:
            # Payload override (ADR-003 level 1) wins over recipe resolution.
            if payload_coords is not None:
                coords: tuple[int, int] | None = payload_coords
            else:
                coords = self._resolve_step_click_coords(step)
            if coords is None:
                return  # step had no resolvable target — execution is a no-op

            baseline_frame: PILImage | None = None
            if step.verify_transition:
                try:
                    shot = pyautogui.screenshot()
                except Exception as exc:
                    raise ScreenCaptureUnavailable(
                        f"baseline screenshot failed: {exc!r}"
                    ) from exc
                if not isinstance(shot, PILImage):
                    raise ScreenCaptureUnavailable(
                        "baseline screenshot returned unexpected type: "
                        f"expected PIL.Image, got {type(shot)!r}"
                    )
                baseline_frame = shot

            ix, iy = coords
            self._validate_bounds(ix, iy)
            settle_seconds = step.settle_ms / 1000.0
            await self._verified_click(ix, iy, settle_seconds=settle_seconds)
        except BaseException as exc:
            # See pre_click branch above — mutate-and-bare-raise
            # preserves the implicit ``__context__`` chain.
            _tag_phase(exc, _PHASE_DISPATCH)
            raise

        # --- post-click phase: transition diff + signal poll --------
        try:
            if baseline_frame is not None:
                self._verify_page_transition(
                    mission=step.name,
                    baseline=baseline_frame,
                    threshold=step.transition_threshold,
                    region=step.transition_region,
                )

            if step.post_click_signal is not None:
                await self._await_post_click_signal(
                    mission=step.name, signal=step.post_click_signal
                )
        except BaseException as exc:
            # See pre_click branch above — mutate-and-bare-raise
            # preserves the implicit ``__context__`` chain.
            _tag_phase(exc, _PHASE_POST_CLICK)
            raise

    def _capture_failure_evidence(
        self,
        *,
        step_idx: int,
        step_name: str,
        error: Exception,
        mission: str = "step_dispatch",
        phase: PhaseName | None = None,
    ) -> None:
        """Write a failure screenshot + action-log record before re-raising.

        Best-effort: any failure to capture the screen (e.g. screen-recording
        permission denied) is swallowed silently — the original error is the
        one that matters for the caller. The record path follows the
        convention ``runs/<id>/artifacts/failure/<idx>-<step>-<error>.png``
        and the action-log file is ``runs/<id>/artifacts/action-log/failure.jsonl``.

        ``mission`` names the node that failed so an evidence-gather failure in
        ``step_observe`` / ``step_capture`` self-describes (``step-observe-
        failed`` / ``step-capture-failed``) instead of masquerading as a
        dispatch failure. ``phase`` overrides the read-from-exception phase for
        those non-dispatch nodes (whose exceptions are never phase-tagged by the
        dispatch guards); when ``None`` the phase is read from the exception
        (dispatch path, tagged) and defaults to ``dispatch``.
        """
        error_class = type(error).__name__
        # Sanitize fragments so the filename is portable.
        safe_step = step_name.replace("/", "-").replace(" ", "_") or "step"
        idx_label = f"{step_idx:02d}" if step_idx >= 0 else "xx"
        png_path = (
            self._run_root
            / "artifacts"
            / "failure"
            / f"{idx_label}-{safe_step}-{error_class}.png"
        )
        png_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = png_path.parent / f"{png_path.name}.tmp"
        screenshot_saved = False
        try:
            shot = pyautogui.screenshot()
            if isinstance(shot, PILImage):
                # Atomic: save to a temp file then rename, so a mid-write I/O
                # error (e.g. ENOSPC after the PNG header flushes) never leaves a
                # truncated file at png_path that a bare .exists() check would
                # advertise as valid evidence. Mirrors _atomic_write_json.
                # format is explicit because the .tmp suffix hides the PNG
                # extension PIL would otherwise infer.
                shot.save(str(tmp_path), format="PNG")
                tmp_path.replace(png_path)
                screenshot_saved = True
        except Exception:
            # Capture failure is itself non-fatal — we still write the log
            # entry below so the caller knows the run failed even when the
            # screen could not be photographed. Any partial temp file is left
            # out of the record (screenshot stays null); clean it up.
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

        log_path = (
            self._run_root
            / "artifacts"
            / "action-log"
            / "failure.jsonl"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Phase: dispatch tags the exception via ``step_guards.tag_phase``
        # (default ``"dispatch"``). observe/capture nodes never reach those
        # guards, so the caller passes an explicit ``phase`` for them.
        resolved_phase = phase if phase is not None else read_phase(error)
        # Event self-describes the failing node: step_dispatch -> step-dispatch-
        # failed, step_observe -> step-observe-failed, etc.
        event = f"{mission.replace('_', '-')}-failed"
        entry: dict[str, object] = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "mission_name": mission,
            "event": event,
            "step_idx": step_idx,
            "step_name": step_name,
            "phase": resolved_phase,
            "error_class": error_class,
            "error_message": str(error),
            "screenshot": str(png_path) if screenshot_saved else None,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _resolve_step_click_coords(self, step: Step) -> tuple[int, int] | None:
        """Delegate to :func:`coord_resolver.resolve_step_click_coords`.

        Body moved to ``adapters/coord_resolver.py`` (B-CA-4 wave 2)
        — see that module for the prefer/fallback chain semantics.
        Kept as an instance method so test fixtures and the
        ``_dispatch_with_step`` call site need no edits.
        """
        return resolve_step_click_coords(step, collaborator=self)
