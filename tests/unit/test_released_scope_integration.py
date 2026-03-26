"""Integration test: full released-scope graph from attach through pageReadyObserved."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class FakeOpenClawAdapter:
    def __init__(self) -> None:
        self.requests: list[OpenClawExecutionRequest] = []

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
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
                "evidence://action-log/release-ceiling-stop",
            ),
        }
        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return OpenClawExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_full_released_scope_graph_runs_all_four_missions(
    tmp_path: Path,
) -> None:
    adapter = FakeOpenClawAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    executed_missions = [r.mission_name for r in adapter.requests]
    assert executed_missions == [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]


@pytest.mark.asyncio
async def test_full_released_scope_graph_stops_at_page_ready_observed(
    tmp_path: Path,
) -> None:
    adapter = FakeOpenClawAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    assert result.state.current_mission == "page_ready_observation"
    assert "evidence://action-log/release-ceiling-stop" in (
        result.state.mission_state.evidence_refs or ()
    )


@pytest.mark.asyncio
async def test_full_released_scope_graph_creates_action_log_artifact(
    tmp_path: Path,
) -> None:
    adapter = FakeOpenClawAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    action_log_dir = result.run.run_root / "artifacts" / "action-log"
    release_ceiling_stop = action_log_dir / "release-ceiling-stop.jsonl"
    assert release_ceiling_stop.exists()

    content = json.loads(release_ceiling_stop.read_text(encoding="utf-8").strip())
    assert content["event"] == "release-ceiling-stop"
    assert content["mission_name"] == "page_ready_observation"
    assert "ts" in content


@pytest.mark.asyncio
async def test_full_released_scope_graph_run_context_has_correct_ceiling(
    tmp_path: Path,
) -> None:
    adapter = FakeOpenClawAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    assert result.run.approved_scope_ceiling == "pageReadyObserved"
