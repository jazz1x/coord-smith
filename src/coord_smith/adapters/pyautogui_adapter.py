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

from coord_smith.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from coord_smith.adapters.page_transition import PageTransitionVerifier
from coord_smith.config.click_recipe import (
    ClickRecipe,
    MissionImageClick,
    PostClickSignal,
    Step,
)
from coord_smith.evidence.envelope import parse_released_evidence_ref
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

_FALLBACK_REFS: dict[str, tuple[str, ...]] = {
    "attach_session": (
        "evidence://screenshot/attach-session-fallback",
        "evidence://action-log/attach-session",
    ),
    "prepare_session": (
        "evidence://screenshot/prepare-session-fallback",
        "evidence://action-log/prepare-session",
    ),
    "step_observe": (
        "evidence://screenshot/step-observed",
        "evidence://action-log/step-observed",
    ),
    "step_dispatch": (
        "evidence://screenshot/step-dispatched",
        "evidence://action-log/step-dispatched",
    ),
    "step_capture": (
        "evidence://screenshot/step-captured",
        "evidence://action-log/step-captured",
    ),
    "run_completion": (
        "evidence://screenshot/run-completion-fallback",
        "evidence://action-log/release-ceiling-stop",
    ),
}

_GENERIC_ACTION_LOG_REF = "evidence://action-log/pyautogui-executed"

# Post-click cursor position tolerance (display scaling / animation jitter).
_CLICK_POSITION_TOLERANCE_PX = 2
# Sleep after click so OS event loop flushes the cursor move before we read it.
_POST_CLICK_SETTLE_SECONDS = 0.05


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

    def with_run_root(self, *, run_root: Path) -> PyAutoGUIAdapter:
        """Return a copy of this adapter bound to a different run root."""
        return PyAutoGUIAdapter(run_root=run_root, click_recipe=self._click_recipe)

    def _action_log_path(self, key: str) -> Path:
        path = self._run_root / "artifacts" / "action-log" / f"{key}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _screenshot_path(self, key: str) -> Path:
        path = self._run_root / "artifacts" / "screenshot" / f"{key}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_action_log(self, *, key: str, mission_name: str) -> None:
        ts = datetime.now(tz=UTC).isoformat()
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission_name,
            "event": key,
        }
        path = self._action_log_path(key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

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

    async def _verified_click(self, x: int, y: int) -> None:
        pyautogui.click(x, y)
        await asyncio.sleep(_POST_CLICK_SETTLE_SECONDS)
        actual = pyautogui.position()
        if (
            abs(actual.x - x) > _CLICK_POSITION_TOLERANCE_PX
            or abs(actual.y - y) > _CLICK_POSITION_TOLERANCE_PX
        ):
            raise ClickExecutionUnverified(
                f"click target=({x}, {y}) but cursor at ({actual.x}, {actual.y}) "
                "— likely Accessibility permission missing"
            )

    def _gather_evidence(self, mission: str) -> tuple[str, ...]:
        mission_refs = _FALLBACK_REFS.get(mission)
        if mission_refs is None:
            action_key = mission.replace("_", "-")
            self._write_action_log(key=action_key, mission_name=mission)
            return (_GENERIC_ACTION_LOG_REF,)
        for ref in mission_refs:
            kind, key = parse_released_evidence_ref(ref)
            if kind == "action-log":
                self._write_action_log(key=key, mission_name=mission)
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

    def _locate_image_target(
        self, mission: str, target: MissionImageClick
    ) -> tuple[int, int]:
        """Match a template image against the live screen and return center coords.

        Records the located coordinates and effective confidence to the
        per-mission action-log entry so a later evidence audit can trace
        which template produced which click.
        """
        template_path = Path(target.image)
        if not template_path.exists():
            raise ImageTemplateNotFound(
                f"image template not found for mission '{mission}': {template_path}"
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
        self._write_image_match_log(
            mission=mission,
            template=str(template_path),
            confidence=target.confidence,
            x=cx,
            y=cy,
        )
        return (cx, cy)

    def _action_key_for_mission(self, mission: str) -> str:
        """Return the canonical action-log key for a mission.

        Most mission names map to a past-tense action key
        (``step_dispatch`` -> ``step-dispatched``) which is held in the
        evidence fallback table. Missions absent from the table fall back to
        a literal underscore-to-hyphen substitution.
        """
        refs = _FALLBACK_REFS.get(mission)
        if refs is not None:
            for ref in refs:
                kind, key = parse_released_evidence_ref(ref)
                if kind == "action-log":
                    return key
        return mission.replace("_", "-")

    def _write_image_match_log(
        self, *, mission: str, template: str, confidence: float, x: int, y: int
    ) -> None:
        """Append a structured image-match record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self._action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "image_template": template,
            "match_confidence": confidence,
            "match_x": x,
            "match_y": y,
        }
        path = self._action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _write_transition_log(
        self,
        *,
        mission: str,
        changed: bool,
        change_ratio: float,
        bbox: tuple[int, int, int, int] | None,
        threshold: float,
    ) -> None:
        """Append a page-transition verification record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self._action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "transition_changed": changed,
            "transition_change_ratio": change_ratio,
            "transition_threshold": threshold,
            "transition_bbox": list(bbox) if bbox is not None else None,
        }
        path = self._action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

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
        """Append a post-click-signal hit record to the mission action log."""
        ts = datetime.now(tz=UTC).isoformat()
        action_key = self._action_key_for_mission(mission)
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission,
            "event": action_key,
            "post_click_signal_template": template,
            "post_click_signal_confidence": confidence,
            "post_click_signal_elapsed_seconds": elapsed,
            "post_click_signal_x": x,
            "post_click_signal_y": y,
        }
        path = self._action_log_path(action_key)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    async def wait_for_image(
        self,
        *,
        path: str,
        timeout: float = 5.0,
        interval: float = 0.1,
        confidence: float = 0.9,
    ) -> tuple[int, int]:
        """Poll ``locateCenterOnScreen`` until the template appears or timeout elapses.

        Returns the matched center coordinates. Raises ``ImageWaitTimeout``
        when the template never appears within ``timeout`` seconds.
        ``interval`` controls polling cadence; smaller values increase CPU.
        """
        deadline = time.monotonic() + timeout
        last_exc: Exception | None = None
        while True:
            try:
                located = pyautogui.locateCenterOnScreen(
                    path, confidence=confidence
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

    async def _await_post_click_signal(
        self, *, mission: str, signal: PostClickSignal
    ) -> None:
        """Poll for the configured post-click image and log the outcome."""
        signal_path = Path(signal.image)
        if not signal_path.exists():
            raise ImageTemplateNotFound(
                f"post-click signal template not found for mission "
                f"'{mission}': {signal_path}"
            )
        start = time.monotonic()
        x, y = await self.wait_for_image(
            path=str(signal_path),
            timeout=signal.timeout,
            interval=signal.interval,
            confidence=signal.confidence,
        )
        elapsed = time.monotonic() - start
        self._write_signal_log(
            mission=mission,
            template=str(signal_path),
            confidence=signal.confidence,
            elapsed=elapsed,
            x=x,
            y=y,
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
        if not isinstance(step_data, dict):
            raise ConfigError(
                "step_dispatch payload must include a 'step' dict "
                "(serialized Step model)"
            )
        step = Step.model_validate(step_data)
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
        can stay focused on exception interception."""
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
        await self._verified_click(ix, iy)

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
        entry: dict[str, object] = {
            "ts": datetime.now(tz=UTC).isoformat(),
            "mission_name": "step_dispatch",
            "event": "step-dispatch-failed",
            "step_idx": step_idx,
            "step_name": step_name,
            "error_class": error_class,
            "error_message": str(error),
            "screenshot": str(png_path) if png_path.exists() else None,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _resolve_step_click_coords(self, step: Step) -> tuple[int, int] | None:
        """Resolve a step's click coordinates using prefer + fallback chain.

        Three regimes, in order of precedence:

        1. **Both image and coord declared** — ``step.prefer`` decides the
           primary; if the primary fails (image not matched, coord
           out-of-bounds), the fallback is tried. If both fail, the
           primary's typed exception is re-raised so the caller sees a
           real diagnosis instead of a silent no-op.
        2. **Single target declared** — image-only or coord-only. The
           target's typed exception (if any) propagates directly; no
           silent swallowing.
        3. **Neither declared** — returns None. The Step Pydantic
           validator normally rejects this, but ``Step.model_construct``
           bypasses validation, so a graceful no-op is the safe
           behavior.
        """
        if step.image is None and step.coord is None:
            return None

        # Single-target regime — no fallback chain, exceptions propagate.
        if step.image is not None and step.coord is None:
            return self._locate_image_for_step(step)
        if step.coord is not None and step.image is None:
            return (step.coord.x, step.coord.y)

        # Dual-target regime — primary then fallback, both swallow once.
        primary_kind: str = step.prefer or "image"

        def _try_image() -> tuple[int, int] | None:
            try:
                return self._locate_image_for_step(step)
            except (ImageTemplateNotFound, ImageMatchConfidenceLow):
                return None

        def _try_coord() -> tuple[int, int] | None:
            assert step.coord is not None
            return (step.coord.x, step.coord.y)

        primary, fallback = (
            (_try_image, _try_coord)
            if primary_kind == "image"
            else (_try_coord, _try_image)
        )
        result = primary()
        if result is not None:
            return result
        result = fallback()
        if result is not None:
            return result
        # Both failed — synthesize a typed error so the caller learns
        # something actionable. We re-run the image attempt without the
        # try-swallow so its exception (the more specific of the two)
        # surfaces.
        return self._locate_image_for_step(step)

    def _locate_image_for_step(self, step: Step) -> tuple[int, int]:
        """Locate the step's image template via the existing helper.

        Raises ``ImageTemplateNotFound`` / ``ImageMatchConfidenceLow``
        directly — the caller decides whether to swallow (dual-target
        fallback) or propagate (single-target).
        """
        assert step.image is not None
        target = MissionImageClick(
            image=step.image,
            confidence=step.confidence
            if step.confidence is not None
            else 0.9,
            region=step.region,
            grayscale=step.grayscale if step.grayscale is not None else False,
        )
        return self._locate_image_target(step.name, target)
