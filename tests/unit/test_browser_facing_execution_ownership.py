"""Test that OpenClaw owns all browser-facing execution in released-scope.

PRD clause (System Boundary, line 27):
'OpenClaw owns browser-facing execution'

This means the released-scope graph delegates ALL browser-facing operations
exclusively to the OpenClaw adapter. No other component performs browser
operations directly.
"""

from __future__ import annotations

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph
from ez_ax.missions.names import RELEASED_MISSIONS


class TrackingExecutionAdapter:
    """Adapter that tracks which browser operations (missions) are delegated to it."""

    def __init__(self) -> None:
        self.requests: list[ExecutionRequest] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Track the request and return valid evidence."""
        self.requests.append(request)
        evidence_map: dict[str, tuple[str, ...]] = {
            "attach_session": (
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ),
            "prepare_session": (
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
            "benchmark_validation": (
                "evidence://action-log/enter-target-page",
                "evidence://dom/target-page-entered",
            ),
            "page_ready_observation": (
                "evidence://dom/page-shell-ready",
                "evidence://action-log/page-ready-observed",
            ),
            "sync_observation": (
                "evidence://clock/server-time-synced",
                "evidence://action-log/sync-observed",
            ),
            "target_actionability_observation": (
                "evidence://dom/target-actionable",
                "evidence://action-log/target-actionable-observed",
            ),
            "armed_state_entry": (
                "evidence://text/armed-state-entered",
                "evidence://action-log/armed-state",
            ),
            "trigger_wait": (
                "evidence://clock/trigger-received",
                "evidence://action-log/trigger-wait-complete",
            ),
            "click_dispatch": (
                "evidence://action-log/click-dispatched",
                "evidence://dom/click-target-clicked",
            ),
            "click_completion": (
                "evidence://dom/click-effect-confirmed",
                "evidence://action-log/click-completed",
            ),
            "success_observation": (
                "evidence://dom/success-observed",
                "evidence://action-log/success-observation",
            ),
            "run_completion": (
                "evidence://action-log/release-ceiling-stop",
                "evidence://text/fallback-reason",
            ),
        }
        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return ExecutionResult(mission_name=request.mission_name, evidence_refs=refs)


@pytest.mark.asyncio
async def test_released_scope_delegates_all_browser_ops_to_execution_adapter(
    tmp_path,
) -> None:
    """Verify that released-scope graph ONLY calls OpenClaw for browser operations.

    PRD System Boundary (line 27): 'OpenClaw owns browser-facing execution'

    All missions up to the ceiling (pageReadyObserved) are browser-facing
    operations that must be delegated exclusively to the OpenClaw adapter.
    No other component should perform browser operations.
    """
    adapter = TrackingExecutionAdapter()

    # Run the released-scope graph (uses pageReadyObserved ceiling)
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify OpenClaw adapter was called for missions up to runCompletion ceiling
    # runCompletion is at index 11 in RELEASED_MISSIONS, so 12 missions total
    assert len(adapter.requests) == 12

    # Verify missions up to ceiling were delegated to OpenClaw
    called_missions = [request.mission_name for request in adapter.requests]
    expected_missions = list(RELEASED_MISSIONS[:12])  # All 12: up to runCompletion
    assert called_missions == expected_missions


@pytest.mark.asyncio
async def test_released_scope_creates_only_execution_requests(
    tmp_path,
) -> None:
    """Verify that only ExecutionRequest objects are created for browser ops.

    PRD System Boundary (line 27): 'OpenClaw owns browser-facing execution'

    The released-scope graph should only create ExecutionRequest instances
    for browser-facing operations, not other adapter types or direct browser calls.
    """
    adapter = TrackingExecutionAdapter()

    # Run released-scope
    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify all requests were ExecutionRequest instances
    request_types = [type(req).__name__ for req in adapter.requests]
    assert all(
        req_type == "ExecutionRequest" for req_type in request_types
    ), (
        f"Expected only ExecutionRequest instances, but found: "
        f"{set(request_types)}"
    )

    # Verify correct number of requests
    assert len(adapter.requests) == 12


@pytest.mark.asyncio
async def test_released_scope_never_calls_other_adapters(tmp_path) -> None:
    """Verify that released-scope graph does not invoke any other execution adapters.

    PRD System Boundary (line 27): 'OpenClaw owns browser-facing execution'

    Only the OpenClaw adapter provided at runtime should be called. No other
    adapter components or direct browser APIs should be invoked.
    """
    from unittest.mock import patch

    adapter = TrackingExecutionAdapter()

    # Patch any potential non-OpenClaw adapters to ensure they're never called
    with patch("pyautogui.click") as mock_pyautogui_click:
        # Note: in released-scope, PyAutoGUIAdapter should not be used;
        # only the provided adapter (OpenClaw) should be called
        await run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="test-session",
            expected_auth_state="logged-in",
            target_page_url="https://example.com/target",
            site_identity="example.com",
            base_dir=tmp_path,
        )

        # PyAutoGUI should not be called in released-scope
        # (it's only used by PyAutoGUIAdapter, which is not part of released execution)
        mock_pyautogui_click.assert_not_called()

    # Verify OpenClaw was called exactly as expected
    assert len(adapter.requests) == 12
