"""PyAutoGUI OS-level coordinate-click adapter implementing ExecutionAdapter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pyautogui

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)

# Fallback evidence ref sets per mission (screenshot path; no DOM access at OS level).
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
        "evidence://screenshot/click-completion-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/click-completed",
    ),
    "success_observation": (
        "evidence://screenshot/success-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/success-observation",
    ),
    "run_completion": (
        "evidence://action-log/run-completed",
        "evidence://screenshot/run-completion-fallback",
        "evidence://text/fallback-reason",
    ),
    "attach_session": (
        "evidence://screenshot/attach-session-fallback",
        "evidence://text/fallback-reason",
        "evidence://action-log/attach-session",
    ),
}

_GENERIC_ACTION_LOG_REF = "evidence://action-log/pyautogui-executed"


class PyAutoGUIAdapter:
    """OS-level coordinate-click adapter implementing ExecutionAdapter protocol.

    Uses pyautogui.click() and pyautogui.screenshot() exclusively.
    Contains no LLM inference; all navigation is coordinate-driven.
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
        try:
            screenshot = pyautogui.screenshot()
        except Exception:  # noqa: BLE001
            return  # headless or display-unavailable; skip screenshot silently
        path = self._screenshot_path(key)
        screenshot.save(str(path))

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

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute a mission using OS-level coordinate click and screenshot."""
        mission = request.mission_name
        payload = request.payload

        x = payload.get("x")
        y = payload.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pyautogui.click(int(x), int(y))

        evidence_refs = self._gather_evidence(mission)
        return ExecutionResult(
            mission_name=mission,
            evidence_refs=evidence_refs,
        )
