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
from coord_smith.adapters.coord_resolver import (
    coord_or_none,
    locate_image_for_step,
    locate_image_or_none,
    locate_image_target,
    resolve_step_click_coords,
)
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
    MissionImageClick,
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

    def _screenshot_path(self, key: str) -> Path:
        path = self._run_root / "artifacts" / "screenshot" / f"{key}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _capture_screenshot(self, key: str) -> None:
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
        path = self._screenshot_path(key)
        screenshot.save(str(path))

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

    def _gather_evidence(self, mission: MissionName) -> tuple[str, ...]:
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
                self._capture_screenshot(key)
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
        # Warmup: prime the CG event pump before the real probe.
        pyautogui.moveTo(start.x, start.y, duration=0)
        await asyncio.sleep(_POST_CLICK_SETTLE_SECONDS)
        screen = pyautogui.size()
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

    def _locate_image_target(
        self, mission: str, target: MissionImageClick
    ) -> tuple[int, int]:
        """Delegate to :func:`coord_resolver.locate_image_target`.

        Kept as an adapter method so existing call sites (image
        matching from inside ``_locate_image_for_step``) need no
        edits. Body moved to ``adapters/coord_resolver.py`` (B-CA-4).
        """
        return locate_image_target(mission, target, collaborator=self)

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
                    f"post-click signal '{path}' not found within "
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
        result = PageTransitionVerifier().verify_changed(
            baseline=baseline,
            post=post,
            threshold=threshold,
            region=region,
        )
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

        evidence_refs = self._gather_evidence(mission)
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

        try:
            await self._dispatch_with_step(step)
        except (
            ImageTemplateNotFound,
            ImageMatchConfidenceLow,
            ClickCoordinatesOutOfBounds,
            ClickExecutionUnverified,
            PageTransitionNotDetected,
            ImageWaitTimeout,
        ) as exc:
            self._capture_failure_evidence(
                step_idx=step_idx, step_name=step.name, error=exc
            )
            raise

    async def _dispatch_with_step(self, step: Step) -> None:
        """Inner click logic — separated so the failure-capture wrapper above
        can stay focused on exception interception.

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
    ) -> None:
        """Write a failure screenshot + action-log record before re-raising.

        Best-effort: any failure to capture the screen (e.g. screen-recording
        permission denied) is swallowed silently — the original error is the
        one that matters for the caller. The record path follows the
        convention ``runs/<id>/artifacts/failure/<idx>-<step>-<error>.png``
        and the action-log file is ``runs/<id>/artifacts/action-log/failure.jsonl``.
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
        try:
            shot = pyautogui.screenshot()
            if isinstance(shot, PILImage):
                shot.save(str(png_path))
        except Exception:
            # Capture failure is itself non-fatal — we still write the log
            # entry below so the caller knows the run failed even when the
            # screen could not be photographed.
            pass

        log_path = (
            self._run_root
            / "artifacts"
            / "action-log"
            / "failure.jsonl"
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Phase tag attached by ``_dispatch_with_step`` via
        # ``step_guards.tag_phase``. Default ``"dispatch"`` covers
        # legacy / pre-step-guards paths so the field is always
        # present and callers don't need a presence check.
        phase = read_phase(error)
        entry: dict[str, object] = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "mission_name": "step_dispatch",
            "event": "step-dispatch-failed",
            "step_idx": step_idx,
            "step_name": step_name,
            "phase": phase,
            "error_class": error_class,
            "error_message": str(error),
            "screenshot": str(png_path) if png_path.exists() else None,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _locate_image_or_none(
        self, step: Step
    ) -> tuple[tuple[int, int] | None, BaseException | None]:
        """Delegate to :func:`coord_resolver.locate_image_or_none`."""
        return locate_image_or_none(step, collaborator=self)

    def _coord_or_none(self, step: Step) -> tuple[int, int] | None:
        """Delegate to :func:`coord_resolver.coord_or_none`."""
        return coord_or_none(step)

    def _resolve_step_click_coords(self, step: Step) -> tuple[int, int] | None:
        """Delegate to :func:`coord_resolver.resolve_step_click_coords`.

        Body moved to ``adapters/coord_resolver.py`` (B-CA-4 wave 2)
        — see that module for the prefer/fallback chain semantics.
        """
        return resolve_step_click_coords(step, collaborator=self)

    def _locate_image_for_step(self, step: Step) -> tuple[int, int]:
        """Delegate to :func:`coord_resolver.locate_image_for_step`."""
        return locate_image_for_step(step, collaborator=self)
