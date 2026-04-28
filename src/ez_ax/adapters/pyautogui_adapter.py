"""PyAutoGUI OS-level coordinate-click adapter implementing ExecutionAdapter."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pyautogui
from PIL import UnidentifiedImageError
from PIL.Image import Image as PILImage

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.adapters.page_transition import PageTransitionVerifier
from ez_ax.config.click_recipe import (
    ClickRecipe,
    MissionClick,
    MissionImageClick,
    PostClickSignal,
)
from ez_ax.models.errors import (
    AccessibilityPermissionDenied,
    ClickCoordinatesOutOfBounds,
    ClickExecutionUnverified,
    ImageMatchConfidenceLow,
    ImageTemplateNotFound,
    ImageWaitTimeout,
    PageTransitionNotDetected,
    ScreenCapturePermissionDenied,
    ScreenCaptureUnavailable,
)

_FALLBACK_REFS: dict[str, tuple[str, ...]] = {
    "prepare_session": (
        "evidence://screenshot/prepare-session-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/prepare-session",
    ),
    "benchmark_validation": (
        "evidence://action-log/enter-target-page",
        "evidence://screenshot/target-page-entered-fallback",
        "evidence://text/fallback-reason",
    ),
    "page_ready_observation": (
        "evidence://screenshot/page-shell-ready-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/page-ready-observed",
    ),
    "sync_observation": (
        "evidence://screenshot/sync-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/sync-observed",
    ),
    "target_actionability_observation": (
        "evidence://screenshot/target-actionable-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/target-actionable-observed",
    ),
    "armed_state_entry": (
        "evidence://screenshot/armed-state-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/armed-state",
    ),
    "trigger_wait": (
        "evidence://screenshot/trigger-wait-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/trigger-wait-complete",
    ),
    "click_dispatch": (
        "evidence://screenshot/click-dispatched-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/click-dispatched",
    ),
    "click_completion": (
        "evidence://screenshot/click-completed-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/click-completed",
    ),
    "success_observation": (
        "evidence://screenshot/success-observation-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/success-observation",
    ),
    "run_completion": (
        "evidence://screenshot/run-completion-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/release-ceiling-stop",
    ),
    "attach_session": (
        "evidence://screenshot/attach-session-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/attach-session",
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

    def _verified_click(self, x: int, y: int) -> None:
        pyautogui.click(x, y)
        time.sleep(_POST_CLICK_SETTLE_SECONDS)
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
            if ref.startswith("evidence://action-log/"):
                action_key = ref[len("evidence://action-log/") :]
                self._write_action_log(key=action_key, mission_name=mission)
            elif ref.startswith("evidence://screenshot/"):
                screenshot_key = ref[len("evidence://screenshot/") :]
                self._capture_screenshot(screenshot_key)
        return mission_refs

    def preflight(self) -> None:
        """Fail-loudly smoke test for OS permissions before any mission runs.

        Accessibility check: move the cursor by +10 px on the X axis and
        verify the new position matches. If the cursor does not move, macOS
        Accessibility permission is missing for the host terminal app and
        pyautogui is silently no-opping. Restores the original position.

        The cold-start probe is preceded by a no-op moveTo to the current
        position so the CoreGraphics event pump is warm by the time the
        real +10 px probe fires; on macOS the very first moveTo after a
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
        time.sleep(_POST_CLICK_SETTLE_SECONDS)
        probe_x = start.x + 10
        probe_y = start.y
        pyautogui.moveTo(probe_x, probe_y, duration=0)
        time.sleep(_POST_CLICK_SETTLE_SECONDS)
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
        if image is None or image.size == (0, 0):
            raise ScreenCaptureUnavailable("preflight screenshot returned empty image")

    def _resolve_click_coords(
        self, mission: str, payload: dict[str, object]
    ) -> tuple[int, int] | None:
        """Resolve click coordinates: payload > recipe(coord) > recipe(image) > None.

        Payload-provided coords (typically from an external caller like
        OpenClaw) take precedence. Otherwise, the static per-mission recipe
        is consulted: a coordinate target returns its fixed pixel pair, while
        an image target is matched against the live screen via
        ``pyautogui.locateCenterOnScreen`` (OpenCV-backed). Returning None
        means this mission performs no click.
        """
        px = payload.get("x")
        py = payload.get("y")
        if (
            not isinstance(px, bool)
            and isinstance(px, (int, float))
            and not isinstance(py, bool)
            and isinstance(py, (int, float))
        ):
            return (int(px), int(py))
        if self._click_recipe is not None:
            coord = self._click_recipe.coords_for(mission)
            if coord is not None:
                return coord
            image_target = self._click_recipe.image_target_for(mission)
            if image_target is not None:
                return self._locate_image_target(mission, image_target)
        return None

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
        try:
            located = pyautogui.locateCenterOnScreen(
                str(template_path),
                confidence=target.confidence,
                region=target.region,
                grayscale=target.grayscale,
            )
        except pyautogui.ImageNotFoundException as exc:
            raise ImageMatchConfidenceLow(
                f"image template not matched for mission '{mission}' "
                f"at confidence>={target.confidence}: {template_path}"
            ) from exc
        if located is None:
            raise ImageMatchConfidenceLow(
                f"image template not matched for mission '{mission}' "
                f"at confidence>={target.confidence}: {template_path}"
            )
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
        (``click_dispatch`` -> ``click-dispatched``) which is held in the
        evidence fallback table. Missions absent from the table fall back to
        a literal underscore-to-hyphen substitution.
        """
        refs = _FALLBACK_REFS.get(mission)
        if refs is not None:
            for ref in refs:
                if ref.startswith("evidence://action-log/"):
                    return ref[len("evidence://action-log/") :]
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

    def wait_for_image(
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
            time.sleep(interval)

    def _mission_target(
        self, mission: str
    ) -> MissionClick | MissionImageClick | None:
        """Return the per-mission recipe entry that drives transition/signal options."""
        if self._click_recipe is None:
            return None
        return self._click_recipe.missions.get(mission)

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
            return
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

    def _await_post_click_signal(
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
        x, y = self.wait_for_image(
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
        """Execute a mission using OS-level coordinate click and screenshot."""
        mission = request.mission_name
        payload = request.payload

        coords = self._resolve_click_coords(mission, payload)
        target = self._mission_target(mission)

        baseline_frame: PILImage | None = None
        if (
            coords is not None
            and target is not None
            and target.verify_transition
        ):
            try:
                shot = pyautogui.screenshot()
            except Exception as exc:
                raise ScreenCaptureUnavailable(
                    f"baseline screenshot failed: {exc!r}"
                ) from exc
            if isinstance(shot, PILImage):
                baseline_frame = shot

        if coords is not None:
            ix, iy = coords
            self._validate_bounds(ix, iy)
            self._verified_click(ix, iy)

        if baseline_frame is not None and target is not None:
            self._verify_page_transition(
                mission=mission,
                baseline=baseline_frame,
                threshold=target.transition_threshold,
                region=target.transition_region,
            )

        if (
            coords is not None
            and target is not None
            and target.post_click_signal is not None
        ):
            self._await_post_click_signal(
                mission=mission, signal=target.post_click_signal
            )

        evidence_refs = self._gather_evidence(mission)
        return ExecutionResult(
            mission_name=mission,
            evidence_refs=evidence_refs,
        )
