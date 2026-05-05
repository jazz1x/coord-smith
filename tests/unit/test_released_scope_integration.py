"""Integration test: full released-scope graph from attach through runCompletion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from coord_smith.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)


class FakeExecutionAdapter:
    def __init__(self, run_root: Path | None = None) -> None:
        self.requests: list[ExecutionRequest] = []
        self._run_root = run_root

    def with_run_root(self, *, run_root: Path) -> FakeExecutionAdapter:
        """Bind run_root for artifact creation."""
        self._run_root = run_root
        return self

    def _write_action_log(self, *, key: str, mission_name: str) -> None:
        """Write action-log artifact to disk."""
        if self._run_root is None:
            return
        ts = datetime.now(tz=UTC).isoformat()
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission_name,
            "event": key,
        }
        path = self._run_root / "artifacts" / "action-log" / f"{key}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
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
            ),
        }
        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        # Write action-log artifacts for each action-log ref
        for ref in refs:
            if ref.startswith("evidence://action-log/"):
                action_key = ref[len("evidence://action-log/") :]
                self._write_action_log(key=action_key, mission_name=request.mission_name)
        return ExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_full_released_scope_graph_runs_all_twelve_missions(
    tmp_path: Path,
) -> None:
    adapter = FakeExecutionAdapter()

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
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    ]


@pytest.mark.asyncio
async def test_full_released_scope_graph_stops_at_run_completion(
    tmp_path: Path,
) -> None:
    adapter = FakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    assert result.state.current_mission == "run_completion"
    assert "evidence://action-log/release-ceiling-stop" in (
        result.state.mission_state.evidence_refs or ()
    )


@pytest.mark.asyncio
async def test_full_released_scope_graph_creates_action_log_artifact(
    tmp_path: Path,
) -> None:
    adapter = FakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    action_log_dir = result.run.run_root / "artifacts" / "action-log"
    run_completed = action_log_dir / "release-ceiling-stop.jsonl"
    assert run_completed.exists()

    content = json.loads(run_completed.read_text(encoding="utf-8").splitlines()[0])
    assert content["event"] == "release-ceiling-stop"
    assert content["mission_name"] == "run_completion"
    assert "ts" in content


@pytest.mark.asyncio
async def test_full_released_scope_graph_run_context_has_correct_ceiling(
    tmp_path: Path,
) -> None:
    adapter = FakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    assert result.run.approved_scope_ceiling == "runCompletion"
