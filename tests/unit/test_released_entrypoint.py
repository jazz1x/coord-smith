from __future__ import annotations

import inspect
import json
import warnings
from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.released_entrypoint import run_released_scope
from ez_ax.models.errors import ConfigError


class FakeOpenClawAdapter:
    def __init__(self) -> None:
        self.requests: list[OpenClawExecutionRequest] = []

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        self.requests.append(request)
        if request.mission_name == "attach_session":
            return OpenClawExecutionResult(
                mission_name="attach_session",
                evidence_refs=(
                    "evidence://text/session-attached",
                    "evidence://text/auth-state-confirmed",
                    "evidence://action-log/attach-session",
                ),
            )
        if request.mission_name == "prepare_session":
            return OpenClawExecutionResult(
                mission_name="prepare_session",
                evidence_refs=(
                    "evidence://text/session-viable",
                    "evidence://action-log/prepare-session",
                ),
            )
        if request.mission_name == "benchmark_validation":
            return OpenClawExecutionResult(
                mission_name="benchmark_validation",
                evidence_refs=(
                    "evidence://action-log/enter-target-page",
                    "evidence://dom/target-page-entered",
                ),
            )
        if request.mission_name == "page_ready_observation":
            return OpenClawExecutionResult(
                mission_name="page_ready_observation",
                evidence_refs=(
                    "evidence://dom/page-shell-ready",
                    "evidence://action-log/release-ceiling-stop",
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
    adapter = FakeOpenClawAdapter()

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
    assert result.run.approved_scope_ceiling == "pageReadyObserved"
    assert run_root == tmp_path / "artifacts" / "runs" / result.state.run_id
    assert (run_root / "artifacts" / "action-log").is_dir()
    assert (run_root / "artifacts" / "action-log" / "attach-session.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "prepare-session.jsonl").exists()
    assert (run_root / "artifacts" / "action-log" / "enter-target-page.jsonl").exists()
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
    assert stop_event["mission_name"] == "page_ready_observation"
    assert isinstance(stop_event["ts"], str) and stop_event["ts"]

    assert [req.mission_name for req in adapter.requests] == [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]


@pytest.mark.asyncio
async def test_run_released_scope_rejects_non_directory_base_dir(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeOpenClawAdapter()
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
    adapter = FakeOpenClawAdapter()

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
    adapter = FakeOpenClawAdapter()

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
    adapter = FakeOpenClawAdapter()

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
