from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.released_cli_shim import run_released_scope_from_argv_env


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
                    "evidence://action-log/release-ceiling-stop",
                ),
            )
        raise AssertionError(f"Unexpected mission: {request.mission_name}")


@pytest.mark.asyncio
async def test_released_cli_shim_prefers_cli_args_over_env(tmp_path: Path) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    argv = [
        "--session-ref",
        "cli-session",
        "--expected-auth-state",
        "cli-auth",
        "--target-page-url",
        "https://cli.invalid/goods/1",
        "--site-identity",
        "cli-site",
    ]
    env = {
        "EZAX_SESSION_REF": "env-session",
        "EZAX_EXPECTED_AUTH_STATE": "env-auth",
        "EZAX_TARGET_PAGE_URL": "https://env.invalid/goods/2",
        "EZAX_SITE_IDENTITY": "env-site",
    }

    result = await run_released_scope_from_argv_env(
        adapter=adapter,
        argv=argv,
        env=env,
        base_dir=tmp_path,
    )

    assert result.state.final_artifact_bundle_ref is not None
    assert [req.mission_name for req in adapter.requests] == [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    ]
    attach_payload = adapter.requests[0].payload
    assert attach_payload["session_ref"] == "cli-session"
    assert attach_payload["expected_auth_state"] == "cli-auth"
    prepare_payload = adapter.requests[1].payload
    assert prepare_payload["target_page_url"] == "https://cli.invalid/goods/1"
    assert prepare_payload["site_identity"] == "cli-site"


@pytest.mark.asyncio
async def test_released_cli_shim_rejects_missing_inputs_before_artifacts(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_from_argv_env(
            adapter=adapter,
            argv=[],
            env={},
            base_dir=tmp_path,
        )
    except ValueError as exc:
        assert "Missing:" in str(exc)
    else:
        raise AssertionError("Expected missing released inputs to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
async def test_released_cli_shim_rejects_whitespace_wrapped_inputs_before_artifacts(
    tmp_path: Path,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    argv = [
        "--session-ref",
        " cli-session ",
        "--expected-auth-state",
        "cli-auth",
        "--target-page-url",
        "https://cli.invalid/goods/1",
        "--site-identity",
        "cli-site",
    ]

    try:
        await run_released_scope_from_argv_env(
            adapter=adapter,
            argv=argv,
            env={},
            base_dir=tmp_path,
        )
    except ValueError as exc:
        assert "session_ref" in str(exc)
        assert "leading or trailing whitespace" in str(exc)
    else:
        raise AssertionError("Expected wrapped-whitespace session_ref to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argv", "expected_label"),
    [
        (
            [
                "--session-ref",
                "cli-session",
                "--expected-auth-state",
                " auth ",
                "--target-page-url",
                "https://cli.invalid/goods/1",
                "--site-identity",
                "cli-site",
            ],
            "expected_auth_state",
        ),
        (
            [
                "--session-ref",
                "cli-session",
                "--expected-auth-state",
                "cli-auth",
                "--target-page-url",
                " https://cli.invalid/goods/1 ",
                "--site-identity",
                "cli-site",
            ],
            "target_page_url",
        ),
        (
            [
                "--session-ref",
                "cli-session",
                "--expected-auth-state",
                "cli-auth",
                "--target-page-url",
                "https://cli.invalid/goods/1",
                "--site-identity",
                " cli-site ",
            ],
            "site_identity",
        ),
    ],
)
async def test_released_cli_shim_rejects_whitespace_wrapped_fields_before_artifacts(
    tmp_path: Path,
    argv: list[str],
    expected_label: str,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    try:
        await run_released_scope_from_argv_env(
            adapter=adapter,
            argv=argv,
            env={},
            base_dir=tmp_path,
        )
    except ValueError as exc:
        message = str(exc)
        assert expected_label in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped input to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("env", "expected_label"),
    [
        ({"EZAX_EXPECTED_AUTH_STATE": " auth "}, "expected_auth_state"),
        ({"EZAX_TARGET_PAGE_URL": " https://cli.invalid/goods/1 "}, "target_page_url"),
        ({"EZAX_SITE_IDENTITY": " cli-site "}, "site_identity"),
    ],
)
async def test_released_cli_shim_rejects_whitespace_wrapped_env_values_before_artifacts(
    tmp_path: Path,
    env: dict[str, str],
    expected_label: str,
) -> None:
    warnings.filterwarnings("ignore", message="Core Pydantic V1 functionality*")
    adapter = FakeExecutionAdapter()

    full_env = {
        "EZAX_SESSION_REF": "cli-session",
        "EZAX_EXPECTED_AUTH_STATE": "cli-auth",
        "EZAX_TARGET_PAGE_URL": "https://cli.invalid/goods/1",
        "EZAX_SITE_IDENTITY": "cli-site",
    }
    full_env.update(env)

    try:
        await run_released_scope_from_argv_env(
            adapter=adapter,
            argv=[],
            env=full_env,
            base_dir=tmp_path,
        )
    except ValueError as exc:
        message = str(exc)
        assert expected_label in message
        assert "leading or trailing whitespace" in message
    else:
        raise AssertionError("Expected whitespace-wrapped env input to be rejected")

    assert adapter.requests == []
    assert not (tmp_path / "artifacts").exists()
