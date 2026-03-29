"""Tests for PyAutoGUIAdapter protocol implementation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from ez_ax.adapters.execution.client import ExecutionRequest
from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter


def test_pyautogui_adapter_has_execute_method() -> None:
    assert callable(getattr(PyAutoGUIAdapter, "execute", None))


async def test_execute_prepare_session_returns_fallback_evidence_refs(
    tmp_path: Path,
) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert "evidence://action-log/prepare-session" in result.evidence_refs
    assert "evidence://screenshot/prepare-session-fallback" in result.evidence_refs
    assert "evidence://text/fallback-reason" in result.evidence_refs


async def test_execute_clicks_when_coordinates_given(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
                "x": 100,
                "y": 200,
            },
        )
        await adapter.execute(request)

    mock_click.assert_called_once_with(100, 200)


async def test_execute_skips_click_without_coordinates(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click") as mock_click,
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        await adapter.execute(request)

    mock_click.assert_not_called()


async def test_execute_writes_action_log_artifact(tmp_path: Path) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
            },
        )
        await adapter.execute(request)

    log_path = tmp_path / "artifacts" / "action-log" / "prepare-session.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["mission_name"] == "prepare_session"
    assert entry["event"] == "prepare-session"
    assert "ts" in entry


async def test_execute_page_ready_observation_writes_release_ceiling_stop(
    tmp_path: Path,
) -> None:
    mock_screenshot = MagicMock()
    with (
        patch("pyautogui.click"),
        patch("pyautogui.screenshot", return_value=mock_screenshot),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)
        request = ExecutionRequest(
            mission_name="page_ready_observation",
            payload={},
        )
        result = await adapter.execute(request)

    assert "evidence://action-log/release-ceiling-stop" in result.evidence_refs
    log_path = tmp_path / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert entry["event"] == "release-ceiling-stop"
    assert entry["mission_name"] == "page_ready_observation"


async def test_pyautogui_adapter_uses_only_click_and_screenshot(tmp_path: Path) -> None:
    """Verify PyAutoGUIAdapter uses only pyautogui.click and screenshot operations.

    PRD requirement (System Boundary, line 35-36):
    'PyAutoGUIAdapter is the sole execution backend: coordinate-click and screenshot
     only, no LLM calls.'

    This test ensures no other pyautogui methods (moveTo, write, press, hotkey, etc.)
    are called during execution, constraining the adapter to coordinate-click and
    screenshot-only operations.
    """
    mock_screenshot = MagicMock()

    # Track which pyautogui methods are called
    called_methods: set[str] = set()

    def track_call(name: str) -> MagicMock:
        def wrapper(*args: object, **kwargs: object) -> object:
            called_methods.add(name)
            if name == "screenshot":
                return mock_screenshot
            return None

        return MagicMock(side_effect=wrapper)

    # Patch all common pyautogui methods to track if they're called
    with patch.multiple(
        "pyautogui",
        click=track_call("click"),
        screenshot=track_call("screenshot"),
        moveTo=track_call("moveTo"),
        write=track_call("write"),
        press=track_call("press"),
        hotkey=track_call("hotkey"),
        scroll=track_call("scroll"),
        locateOnScreen=track_call("locateOnScreen"),
    ):
        adapter = PyAutoGUIAdapter(run_root=tmp_path)

        # Test with coordinates to trigger click
        request_with_coords = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://example.com",
                "site_identity": "example",
                "x": 100,
                "y": 200,
            },
        )
        await adapter.execute(request_with_coords)

        # Test without coordinates
        request_without_coords = ExecutionRequest(
            mission_name="page_ready_observation",
            payload={},
        )
        await adapter.execute(request_without_coords)

    # Verify only click and screenshot were called
    assert "screenshot" in called_methods, "screenshot() should be called"
    assert "click" in called_methods, "click() should be called"

    # Verify no other pyautogui methods were called
    forbidden_methods = {
        "moveTo",
        "write",
        "press",
        "hotkey",
        "scroll",
        "locateOnScreen",
    }
    unwanted_calls = called_methods & forbidden_methods
    assert (
        not unwanted_calls
    ), f"PyAutoGUIAdapter must not call these pyautogui methods: {unwanted_calls}"
