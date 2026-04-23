"""PyAutoGUI OS-level coordinate-click adapter implementing ExecutionAdapter."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pyautogui
from PIL import UnidentifiedImageError

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.models.errors import (
    AccessibilityPermissionDenied,
    ClickCoordinatesOutOfBounds,
    ClickExecutionUnverified,
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

    def __init__(self, *, run_root: Path) -> None:
        self._run_root = run_root

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

        Performs a no-op moveTo roundtrip (cursor to its current position) to
        detect missing Accessibility permission, and one screenshot call to
        detect missing Screen Recording permission. Either failure raises a
        typed ExecutionTransportError; the entrypoint is expected to catch
        and exit with a human-readable message.
        """
        try:
            start = pyautogui.position()
        except Exception as exc:  # pragma: no cover — position() rarely fails
            raise AccessibilityPermissionDenied(
                f"pyautogui.position() failed: {exc!r}"
            ) from exc
        pyautogui.moveTo(start.x, start.y, duration=0)
        time.sleep(_POST_CLICK_SETTLE_SECONDS)
        after = pyautogui.position()
        if (
            abs(after.x - start.x) > _CLICK_POSITION_TOLERANCE_PX
            or abs(after.y - start.y) > _CLICK_POSITION_TOLERANCE_PX
        ):
            raise AccessibilityPermissionDenied(
                "pyautogui.moveTo did not reach target — Accessibility permission "
                "likely missing for the host terminal app"
            )
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

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute a mission using OS-level coordinate click and screenshot."""
        mission = request.mission_name
        payload = request.payload

        x = payload.get("x")
        y = payload.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            ix, iy = int(x), int(y)
            self._validate_bounds(ix, iy)
            self._verified_click(ix, iy)

        evidence_refs = self._gather_evidence(mission)
        return ExecutionResult(
            mission_name=mission,
            evidence_refs=evidence_refs,
        )
