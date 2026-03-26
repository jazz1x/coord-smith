"""Test that ez-ax orchestrates execution through OpenClaw.

PRD Purpose section (line 9):
'orchestrate execution through `OpenClaw`'

This means:
1. All execution is delegated to OpenClaw
2. OpenClaw adapter is the sole execution mechanism
3. Each mission execution results in an OpenClaw call
4. Released-scope graph wires mission nodes to OpenClaw execution
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class ExecutionTrackingAdapter:
    """Adapter that tracks all OpenClaw execution calls."""

    def __init__(self) -> None:
        self.calls: list[OpenClawExecutionRequest] = []
        self.call_count = 0

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        """Track each execution and provide evidence."""
        self.calls.append(request)
        self.call_count += 1

        # Provide evidence refs based on mission
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
                "evidence://action-log/release-ceiling-stop",
            ),
        }
        refs = evidence_map.get(request.mission_name, ())
        if not refs:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return OpenClawExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_released_scope_delegates_all_execution_to_openclaw(
    tmp_path: Path,
) -> None:
    """Verify that released-scope orchestrates all mission execution through OpenClaw.

    PRD Purpose (line 9): 'orchestrate execution through `OpenClaw`'

    This test verifies that:
    1. Each mission node calls the OpenClaw adapter
    2. The adapter.execute() is the sole execution mechanism
    3. All four released missions are executed via OpenClaw
    """
    adapter = ExecutionTrackingAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify all four missions were orchestrated through OpenClaw
    assert adapter.call_count == 4, (
        f"All 4 released missions must be orchestrated through OpenClaw. "
        f"Expected 4 calls, got {adapter.call_count}"
    )

    # Verify the missions were called in the correct order
    executed_missions = [call.mission_name for call in adapter.calls]
    expected_sequence = [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]
    assert executed_missions == expected_sequence, (
        f"Missions must be orchestrated in correct order through OpenClaw. "
        f"Expected: {expected_sequence}, Got: {executed_missions}"
    )


@pytest.mark.asyncio
async def test_each_released_mission_execution_goes_through_openclaw_adapter(
    tmp_path: Path,
) -> None:
    """Verify that each released mission execution delegates to OpenClaw.execute().

    PRD Purpose (line 9): 'orchestrate execution through `OpenClaw`'

    This test verifies that the OpenClawExecutionRequest is properly formed
    and passed to the adapter for each mission.
    """
    adapter = ExecutionTrackingAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify each call has a properly formed request
    for i, call in enumerate(adapter.calls):
        assert isinstance(call, OpenClawExecutionRequest), (
            f"Call {i} must be an OpenClawExecutionRequest. Got {type(call)}"
        )
        assert call.mission_name is not None, (
            f"Call {i} must have a mission_name"
        )
        assert call.payload is not None, (
            f"Call {i} ({call.mission_name}) must have a payload"
        )

    # Verify attach_session call includes session_ref in payload
    attach_call = adapter.calls[0]
    assert attach_call.mission_name == "attach_session"
    assert attach_call.payload.get("session_ref") == "test-session", (
        "attach_session orchestration must pass session_ref through OpenClaw"
    )

    # Verify prepare_session call includes target_page_url in payload
    prepare_call = adapter.calls[1]
    assert prepare_call.mission_name == "prepare_session"
    assert prepare_call.payload.get("target_page_url") == "https://example.com/target", (
        "prepare_session orchestration must pass target_page_url through OpenClaw"
    )

    # Verify benchmark_validation call includes target_page_url in payload
    benchmark_call = adapter.calls[2]
    assert benchmark_call.mission_name == "benchmark_validation"
    assert benchmark_call.payload.get("target_page_url") == "https://example.com/target", (
        "benchmark_validation orchestration must pass target_page_url through OpenClaw"
    )

    # Verify page_ready_observation call is empty payload (no additional params)
    page_ready_call = adapter.calls[3]
    assert page_ready_call.mission_name == "page_ready_observation"
    assert page_ready_call.payload == {}, (
        "page_ready_observation orchestration must have empty payload"
    )


@pytest.mark.asyncio
async def test_released_scope_execution_graph_wires_to_openclaw_adapter(
    tmp_path: Path,
) -> None:
    """Verify that the released-scope execution graph is wired to use the OpenClaw adapter.

    PRD Purpose (line 9): 'orchestrate execution through `OpenClaw`'

    This test verifies that:
    1. The graph nodes call the provided OpenClaw adapter
    2. No internal execution mechanism exists
    3. The adapter is the sole execution path
    """
    # Create a strict adapter that fails if called unexpectedly
    class StrictAdapter:
        """Adapter that must be called exactly for the 4 released missions."""

        def __init__(self) -> None:
            self.call_count = 0

        async def execute(
            self, request: OpenClawExecutionRequest
        ) -> OpenClawExecutionResult:
            """Increment counter and return evidence."""
            self.call_count += 1
            if request.mission_name not in [
                "attach_session",
                "prepare_session",
                "benchmark_validation",
                "page_ready_observation",
            ]:
                raise AssertionError(
                    f"Adapter received unexpected mission: {request.mission_name}"
                )

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
                    "evidence://action-log/release-ceiling-stop",
                ),
            }
            refs = evidence_map.get(request.mission_name, ())
            return OpenClawExecutionResult(
                mission_name=request.mission_name, evidence_refs=refs
            )

    adapter = StrictAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify the graph called the adapter exactly 4 times (once per mission)
    assert adapter.call_count == 4, (
        f"Released-scope graph must orchestrate exactly 4 missions through OpenClaw. "
        f"Got {adapter.call_count} calls"
    )
