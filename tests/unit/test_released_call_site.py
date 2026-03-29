from __future__ import annotations

import json
from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.released_call_site import (
    ReleasedRunContext,
    execute_attach_session_node,
    execute_benchmark_validation_node,
    execute_page_ready_observation_node,
    execute_prepare_session_node,
    execute_run_completion_node,
    execute_sync_observation_node,
    seed_action_log_marker,
)
from ez_ax.models.errors import ConfigError, FlowError, ValidationError
from ez_ax.models.runtime import RuntimeState


class FakeExecutionAdapter:
    def __init__(self, *, result: ExecutionResult) -> None:
        self._result = result
        self.last_request: ExecutionRequest | None = None

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        self.last_request = request
        return self._result


def test_released_run_context_rejects_invalid_scope_ceiling(tmp_path: Path) -> None:
    with pytest.raises(FlowError) as excinfo:
        ReleasedRunContext(
            run_root=tmp_path,
            approved_scope_ceiling="modeled-stage",  # type: ignore[arg-type]
        )

    assert "approved_scope_ceiling" in str(excinfo.value)


def test_released_run_context_rejects_missing_run_root(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-run-root"
    with pytest.raises(ConfigError) as excinfo:
        ReleasedRunContext(run_root=missing_root)

    assert "run_root must exist" in str(excinfo.value)


def test_seed_action_log_marker_rejects_invalid_key(tmp_path: Path) -> None:
    with pytest.raises(ValidationError) as excinfo:
        seed_action_log_marker(
            run_root=tmp_path,
            mission_name="prepare_session",
            key="Not-Kebab",
        )

    assert "kebab-case" in str(excinfo.value)


def test_seed_action_log_marker_rejects_unknown_mission(tmp_path: Path) -> None:
    with pytest.raises(FlowError) as excinfo:
        seed_action_log_marker(
            run_root=tmp_path,
            mission_name="not-a-mission",
            key="prepare-session",
        )

    assert "known mission" in str(excinfo.value)


@pytest.mark.asyncio
async def test_execute_prepare_session_node_wires_execution_wrapper(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="prepare_session",
        evidence_refs=(
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_prepare_session_node(
        state=state,
        adapter=adapter,
        run=run,
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
    )

    assert observed == result
    assert state.current_mission == "prepare_session"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (run_root / "artifacts" / "action-log" / "prepare-session.jsonl").exists()


@pytest.mark.asyncio
async def test_execute_benchmark_validation_node_wires_execution_wrapper(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="benchmark_validation",
        evidence_refs=(
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_benchmark_validation_node(
        state=state,
        adapter=adapter,
        run=run,
        target_page_url="https://tickets.interpark.com/goods/26003199",
    )

    assert observed == result
    assert state.current_mission == "benchmark_validation"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (run_root / "artifacts" / "action-log" / "enter-target-page.jsonl").exists()


@pytest.mark.asyncio
async def test_execute_attach_session_node_wires_execution_wrapper(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="attach_session",
        evidence_refs=(
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_attach_session_node(
        state=state,
        adapter=adapter,
        run=run,
        session_ref="operator-prepared-session",
        expected_auth_state="authenticated",
    )

    assert observed == result
    assert state.current_mission == "attach_session"
    assert state.session_ref == "operator-prepared-session"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (run_root / "artifacts" / "action-log" / "attach-session.jsonl").exists()
    assert adapter.last_request is not None
    assert adapter.last_request.payload == {
        "session_ref": "operator-prepared-session",
        "expected_auth_state": "authenticated",
    }
    payload = json.loads(
        (run_root / "artifacts" / "action-log" / "attach-session.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert payload["event"] == "attach-session"
    assert payload["mission_name"] == "attach_session"
    assert isinstance(payload["ts"], str) and payload["ts"]


@pytest.mark.asyncio
async def test_execute_page_ready_observation_node_wires_execution_wrapper(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="page_ready_observation",
        evidence_refs=(
            "evidence://dom/page-shell-ready",
            "evidence://action-log/page-ready-observed",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_page_ready_observation_node(
        state=state,
        adapter=adapter,
        run=run,
    )

    assert observed == result
    assert state.current_mission == "page_ready_observation"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (
        run_root / "artifacts" / "action-log" / "page-ready-observed.jsonl"
    ).exists()


@pytest.mark.asyncio
async def test_execute_sync_observation_node_wires_execution_wrapper(
    tmp_path: Path,
) -> None:
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="sync_observation",
        evidence_refs=(
            "evidence://dom/sync-check",
            "evidence://action-log/sync-observed",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_sync_observation_node(
        state=state,
        adapter=adapter,
        run=run,
    )

    assert observed == result
    assert state.current_mission == "sync_observation"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (
        run_root / "artifacts" / "action-log" / "sync-observed.jsonl"
    ).exists()


@pytest.mark.asyncio
async def test_execute_run_completion_node_seeds_release_ceiling_stop(
    tmp_path: Path,
) -> None:
    """Verify run_completion_node seeds the release-ceiling-stop marker."""
    run_root = tmp_path
    run = ReleasedRunContext(
        run_root=run_root, approved_scope_ceiling="runCompletion"
    )

    result = ExecutionResult(
        mission_name="run_completion",
        evidence_refs=(
            "evidence://action-log/release-ceiling-stop",
        ),
    )
    adapter = FakeExecutionAdapter(result=result)
    state = RuntimeState(run_id="test-run")

    observed = await execute_run_completion_node(
        state=state,
        adapter=adapter,
        run=run,
    )

    assert observed == result
    assert state.current_mission == "run_completion"
    assert state.mission_state.evidence_refs == result.evidence_refs
    assert (
        run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    ).exists()
    payload = json.loads(
        (run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert payload["event"] == "release-ceiling-stop"
    assert payload["mission_name"] == "run_completion"
