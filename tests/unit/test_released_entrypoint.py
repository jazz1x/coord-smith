from __future__ import annotations

import inspect
import json
import warnings
from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.released_entrypoint import run_released_scope
from ez_ax.models.errors import ConfigError


class FakeExecutionAdapter:
    def __init__(self) -> None:
        self.requests: list[ExecutionRequest] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        self.requests.append(request)
        if request.mission_name == "attach_session":
            return ExecutionResult(
                mission_name="attach_session",
                evidence_refs=(
                    "evidence://text/session-attached",
                    "evidence://text/auth-state-confirmed",
                    "evidence://action-log/attach-session",
                ),
            )
        if request.mission_name == "prepare_session":
            return ExecutionResult(
                mission_name="prepare_session",
                evidence_refs=(
                    "evidence://text/session-viable",
                    "evidence://action-log/prepare-session",
                ),
            )
        if request.mission_name == "benchmark_validation":
            return ExecutionResult(
                mission_name="benchmark_validation",
                evidence_refs=(
                    "evidence://action-log/enter-target-page",
                    "evidence://dom/target-page-entered",
                ),
            )
        if request.mission_name == "page_ready_observation":
            return ExecutionResult(
                mission_name="page_ready_observation",
                evidence_refs=(
                    "evidence://dom/page-shell-ready",
                    "evidence://action-log/page-ready-observed",
                ),
            )
        if request.mission_name == "sync_observation":
            return ExecutionResult(
                mission_name="sync_observation",
                evidence_refs=(
                    "evidence://clock/server-time-synced",
                    "evidence://action-log/sync-observed",
                ),
            )
        if request.mission_name == "target_actionability_observation":
            return ExecutionResult(
                mission_name="target_actionability_observation",
                evidence_refs=(
                    "evidence://dom/target-actionable",
                    "evidence://action-log/target-actionable-observed",
                ),
            )
        if request.mission_name == "armed_state_entry":
            return ExecutionResult(
                mission_name="armed_state_entry",
                evidence_refs=(
                    "evidence://text/armed-state-entered",
                    "evidence://action-log/armed-state",
                ),
            )
        if request.mission_name == "trigger_wait":
            return ExecutionResult(
                mission_name="trigger_wait",
                evidence_refs=(
                    "evidence://clock/trigger-received",
                    "evidence://action-log/trigger-wait-complete",
                ),
            )
        if request.mission_name == "click_dispatch":
            return ExecutionResult(
                mission_name="click_dispatch",
                evidence_refs=(
                    "evidence://action-log/click-dispatched",
                    "evidence://dom/click-target-clicked",
                ),
            )
        if request.mission_name == "click_completion":
            return ExecutionResult(
                mission_name="click_completion",
                evidence_refs=(
                    "evidence://dom/click-effect-confirmed",
                    "evidence://action-log/click-completed",
                ),
            )
        if request.mission_name == "success_observation":
            return ExecutionResult(
                mission_name="success_observation",
                evidence_refs=(
                    "evidence://dom/success-observed",
                    "evidence://action-log/success-observation",
                ),
            )
        if request.mission_name == "run_completion":
            return ExecutionResult(
                mission_name="run_completion",
                evidence_refs=(
                    "evidence://action-log/run-completed",
                    "evidence://text/run-summary",
                ),
            )
        raise AssertionError(f"Unexpected mission: {request.mission_name}")


def test_run_released_scope_exposes_explicit_released_input_signature() -> None:
    signature = inspect.signature(run_released_scope)
    params = signature.parameters

    assert list(params) == [
        "adapter",
        "session_ref",
        "expected_auth_state",
        "target_page_url",
        "site_identity",
        "base_dir",
    ]
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        for parameter in params.values()
    )
    assert all(
        parameter.kind
        not in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )
        for parameter in params.values()
    )


@pytest.mark.asyncio
async def test_run_released_scope_sequences_released_missions_and_creates_run_root(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    result = await run_released_scope(
        adapter=adapter,
        session_ref="operator-prepared-session",
        expected_auth_state="authenticated",
        target_page_url="https://tickets.interpark.com/goods/26003199",
        site_identity="interpark",
        base_dir=tmp_path,
    )

    assert result.state.final_artifact_bundle_ref is not None
    run_root = Path(result.state.final_artifact_bundle_ref)
    assert run_root.exists()
    assert result.run.run_root == run_root
    assert result.run.approved_scope_ceiling == "runCompletion"
    assert run_root == tmp_path / "artifacts" / "runs" / result.state.run_id
    assert (run_root / "artifacts" / "action-log").is_dir()
    assert (run_root / "artifacts" / "action-log" / "attach-session.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "prepare-session.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "enter-target-page.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "page-ready-observed.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "sync-observed.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "target-actionable-observed.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "armed-state.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "trigger-wait-complete.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "click-dispatched.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "click-completed.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "success-observation.jsonl").exists()
    assert (
        run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    ).exists()

    release_stop_payload = (
        run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    ).read_text(encoding="utf-8")
    assert release_stop_payload
    first_line = release_stop_payload.splitlines()[0]
    stop_event = json.loads(first_line)
    assert stop_event["event"] == "release-ceiling-stop"
    assert stop_event["mission_name"] == "run_completion"
    assert isinstance(stop_event["ts"], str) and stop_event["ts"]

    assert [req.mission_name for req in adapter.requests] == [
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
async def test_run_released_scope_rejects_non_directory_base_dir(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()
    base_dir = tmp_path / "not-a-dir"
    base_dir.write_text("nope", encoding="utf-8")

    try:
        await run_released_scope(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=base_dir,
        )
    except ConfigError as exc:
        assert "base_dir must be a directory" in str(exc)
    else:
        raise AssertionError("Expected non-directory base_dir to be rejected")


@pytest.mark.asyncio
async def test_run_released_scope_rejects_whitespace_session_ref(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope(
            adapter=adapter,
            session_ref="   ",
            expected_auth_state="authenticated",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "session_ref" in str(exc)
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError("Expected whitespace-only session_ref to be rejected")

    assert [req.mission_name for req in adapter.requests] == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_run_released_scope_rejects_whitespace_expected_auth_state_without_creating_run_root(  # noqa: E501
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope(
            adapter=adapter,
            session_ref="operator-prepared-session",
            expected_auth_state="   ",
            target_page_url="https://tickets.interpark.com/goods/26003199",
            site_identity="interpark",
            base_dir=tmp_path,
        )
    except ConfigError as exc:
        assert "expected_auth_state" in str(exc)
        assert "whitespace-only" in str(exc)
    else:
        raise AssertionError(
            "Expected whitespace-only expected_auth_state to be rejected"
        )

    assert [req.mission_name for req in adapter.requests] == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "expected_label"),
    [
        ({"session_ref": " operator-prepared-session "}, "session_ref"),
        ({"expected_auth_state": " authenticated "}, "expected_auth_state"),
        (
            {"target_page_url": " https://tickets.interpark.com/goods/26003199 "},
            "target_page_url",
        ),
        ({"site_identity": " interpark "}, "site_identity"),
    ],
)
async def test_run_released_scope_rejects_whitespace_wrapped_inputs_before_artifacts(
    tmp_path: Path,
    kwargs: dict[str, str],
    expected_label: str,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    base_kwargs = {
        "adapter": adapter,
        "session_ref": "operator-prepared-session",
        "expected_auth_state": "authenticated",
        "target_page_url": "https://tickets.interpark.com/goods/26003199",
        "site_identity": "interpark",
        "base_dir": tmp_path,
    }
    base_kwargs.update(kwargs)

    try:
        await run_released_scope(**base_kwargs)
    except ConfigError as exc:
        message = str(exc)
        assert expected_label in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped input to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()
