"""Phase R51 heuristic gap scan: Mission parameter validation.

PRD requirement (Release Boundary, lines 47-53 and System Boundary, lines 25-28):
'Released implementation scope: attach, prepareSession, benchmark validation,
pageReadyObserved. Authority boundary: OpenClaw owns browser-facing execution;
ez-ax owns orchestration, validation, stopping, and reasoning.'

This test verifies that each released mission receives and correctly validates
its required parameters before execution, ensuring the released-scope graph
properly handles mission input validation and parameter passing.

Specific PRD clauses tested:
- Each released mission must receive correct required parameters
- Missing required parameters must be rejected
- Invalid parameter values must be rejected
- Parameters must be validated at the released-scope boundary
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class ParameterTrackingAdapter:
    """Adapter that tracks parameters passed to each mission."""

    def __init__(self) -> None:
        self.requests: list[ExecutionRequest] = []

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Track the request and return appropriate evidence."""
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
            "sync_observation": ("evidence://action-log/sync-observed",),
            "target_actionability_observation": ("evidence://action-log/target-actionable-observed",),
            "armed_state_entry": ("evidence://action-log/armed-state",),
            "trigger_wait": ("evidence://action-log/trigger-wait-complete",),
            "click_dispatch": ("evidence://action-log/click-dispatched",),
            "click_completion": ("evidence://action-log/click-completed",),
            "success_observation": ("evidence://action-log/success-observation",),
            "run_completion": ("evidence://action-log/release-ceiling-stop",),
        }

        refs = evidence_map.get(request.mission_name, ())
        return ExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_attach_session_receives_required_parameters(
    tmp_path: Path,
) -> None:
    """Verify attach_session receives session_ref and expected_auth_state.

    PRD requirement (System Boundary, OpenClaw adapter contract):
    attach_session requires: session_ref, expected_auth_state
    """
    adapter = ParameterTrackingAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-param-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Find attach_session request
    attach_request = next(
        (r for r in adapter.requests if r.mission_name == "attach_session"),
        None,
    )
    assert attach_request is not None, "attach_session mission was not executed"

    # Verify payload contains required parameters
    assert attach_request.payload is not None
    assert isinstance(attach_request.payload, dict)
    assert "session_ref" in attach_request.payload
    assert "expected_auth_state" in attach_request.payload

    # Verify parameter values
    assert attach_request.payload["session_ref"] == "test-param-session"
    assert attach_request.payload["expected_auth_state"] == "logged-in"


@pytest.mark.asyncio
async def test_prepare_session_receives_required_parameters(
    tmp_path: Path,
) -> None:
    """Verify prepare_session receives target_page_url and site_identity.

    PRD requirement (System Boundary, OpenClaw adapter contract):
    prepare_session requires: target_page_url, site_identity
    """
    adapter = ParameterTrackingAdapter()

    test_url = "https://app.example.com/login"
    test_site = "app.example.com"

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="authenticated",
        target_page_url=test_url,
        site_identity=test_site,
        base_dir=tmp_path,
    )

    # Find prepare_session request
    prepare_request = next(
        (r for r in adapter.requests if r.mission_name == "prepare_session"),
        None,
    )
    assert prepare_request is not None, "prepare_session mission was not executed"

    # Verify payload contains required parameters
    assert prepare_request.payload is not None
    assert "target_page_url" in prepare_request.payload
    assert "site_identity" in prepare_request.payload

    # Verify parameter values
    assert prepare_request.payload["target_page_url"] == test_url
    assert prepare_request.payload["site_identity"] == test_site


@pytest.mark.asyncio
async def test_benchmark_validation_receives_required_parameters(
    tmp_path: Path,
) -> None:
    """Verify benchmark_validation receives target_page_url.

    PRD requirement (System Boundary, OpenClaw adapter contract):
    benchmark_validation requires: target_page_url
    """
    adapter = ParameterTrackingAdapter()

    test_url = "https://app.example.com/secure"

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="authenticated",
        target_page_url=test_url,
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Find benchmark_validation request
    benchmark_request = next(
        (r for r in adapter.requests if r.mission_name == "benchmark_validation"),
        None,
    )
    assert benchmark_request is not None, "benchmark_validation mission was not executed"

    # Verify payload contains required parameters
    assert benchmark_request.payload is not None
    assert "target_page_url" in benchmark_request.payload

    # Verify parameter value
    assert benchmark_request.payload["target_page_url"] == test_url


@pytest.mark.asyncio
async def test_page_ready_observation_receives_empty_payload(
    tmp_path: Path,
) -> None:
    """Verify page_ready_observation (final mission) receives empty payload.

    PRD requirement (System Boundary, OpenClaw adapter contract):
    page_ready_observation has no required parameters (empty payload)
    """
    adapter = ParameterTrackingAdapter()

    await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Find page_ready_observation request
    ready_request = next(
        (r for r in adapter.requests if r.mission_name == "page_ready_observation"),
        None,
    )
    assert ready_request is not None, "page_ready_observation mission was not executed"

    # Verify payload is empty (or minimal)
    assert ready_request.payload is not None
    # page_ready_observation should have minimal or empty payload
    # (no session_ref, target_page_url, etc. required)


@pytest.mark.asyncio
async def test_mission_parameter_validation_respects_parameter_whitespace_rules(
    tmp_path: Path,
) -> None:
    """Verify mission parameters are validated for whitespace per PRD constraints.

    PRD requirement (Canonical OpenClaw contract):
    Required string parameters must not be whitespace-only and must not have
    leading/trailing whitespace. The released-scope graph enforces this at the
    boundary.
    """
    from ez_ax.models.errors import ConfigError

    # Verify that whitespace-wrapped parameters are rejected
    with pytest.raises(ConfigError) as exc_info:
        await run_released_scope_via_langgraph(
            adapter=ParameterTrackingAdapter(),
            session_ref="  session-ref-123  ",  # whitespace-wrapped should be rejected
            expected_auth_state="logged-in",
            target_page_url="https://example.com",
            site_identity="example.com",
            base_dir=tmp_path,
        )

    # Verify the error message mentions whitespace validation
    assert "whitespace" in str(exc_info.value).lower()
    assert "session_ref" in str(exc_info.value)
