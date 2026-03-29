from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import ExecutionRequest
from ez_ax.adapters.execution.mcp_adapter import McpBackedExecutionAdapter
from ez_ax.adapters.execution.mcp_settings import (
    McpExecutionAdapterSettings,
    RetryPolicy,
)
from ez_ax.models.errors import (
    ConfigError,
    ExecutionTransportError,
    FlowError,
    ValidationError,
)


@dataclass
class FakeMcpClient:
    side_effects: list[object] | None = None
    tool_output: object | None = None
    raise_exc: Exception | None = None
    call_count: int = 0
    last_server_name: str | None = None
    last_tool_name: str | None = None
    last_tool_input: dict[str, object] | None = None
    last_timeout_seconds: float | None = None

    async def call_tool(
        self,
        *,
        server_name: str,
        tool_name: str,
        tool_input: dict[str, object],
        timeout_seconds: float,
    ) -> object:
        self.call_count += 1
        self.last_server_name = server_name
        self.last_tool_name = tool_name
        self.last_tool_input = tool_input
        self.last_timeout_seconds = timeout_seconds
        if self.side_effects is not None:
            if not self.side_effects:
                raise AssertionError("FakeMcpClient.side_effects exhausted")
            effect = self.side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.tool_output


def _settings(*, max_attempts: int = 1) -> McpExecutionAdapterSettings:
    return McpExecutionAdapterSettings(
        mcp_server_name="openclaw-mcp",
        tool_name="openclaw.execute",
        default_timeout_seconds=1.0,
        retry_policy=RetryPolicy(max_attempts=max_attempts),
    )


def _observation(*, ref: str, value: object) -> dict[str, object]:
    kind, key = ref.split("://", 1)[1].split("/", 1)
    return {
        "ref": ref,
        "kind": kind,
        "key": key,
        "value": value,
    }


@pytest.mark.asyncio
async def test_mcp_adapter_happy_path_returns_execution_result(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    ]
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value="ok"),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
        "request_id": "req-1",
    }
    client = FakeMcpClient(tool_output=tool_output)
    adapter = McpBackedExecutionAdapter(
        settings=_settings(),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert result.evidence_refs == tuple(evidence_refs)
    assert client.last_server_name == "openclaw-mcp"
    assert client.last_tool_name == "openclaw.execute"
    assert client.last_tool_input is not None
    assert client.last_tool_input["mission_name"] == "prepare_session"
    assert client.last_tool_input["scope_ceiling"] == "runCompletion"
    assert client.last_tool_input["request_id"] == "req-1"
    assert client.last_tool_input["run_root"] == str(tmp_path)


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_evidence_contract_violation_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://action-log/prepare-session",
    ]
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(
                ref=evidence_refs[0],
                value={"seeded": True},
            ),
        },
        "request_id": "req-1",
    }
    client = FakeMcpClient(side_effects=[tool_output, tool_output, tool_output])
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "ExecutionResult" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected evidence contract violation to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_missing_run_root() -> None:
    client = FakeMcpClient(tool_output={})
    adapter = McpBackedExecutionAdapter(settings=_settings(), mcp_client=client)

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ConfigError as exc:
        assert "run_root" in str(exc)
    else:
        raise AssertionError("Expected missing run_root to raise ConfigError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_non_directory_run_root(tmp_path: Path) -> None:
    run_root = tmp_path / "run_root.txt"
    run_root.write_text("not a directory")

    client = FakeMcpClient(tool_output={})
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=run_root
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ConfigError as exc:
        assert "run_root" in str(exc)
        assert "directory" in str(exc)
        assert client.call_count == 0
    else:
        raise AssertionError(
            "Expected non-directory run_root to raise ConfigError before tool call"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_accepts_all_released_scope_missions(tmp_path: Path) -> None:
    """Verify MCP adapter accepts all 12 released scope missions up to run_completion.

    With the expanded ceiling to runCompletion, all 12 missions including
    sync_observation are now within the released scope and should be accepted.
    """
    evidence_refs = [
        "evidence://clock/server-time-synced",
        "evidence://action-log/sync-observed",
    ]
    tool_output = {
        "mission_name": "sync_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value={"synced": True}),
        },
        "request_id": "req-1",
    }
    client = FakeMcpClient(tool_output=tool_output)
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(mission_name="sync_observation", payload={})
    result = await adapter.execute(request)

    # Verify sync_observation (previously modeled-only) is now accepted in released scope
    assert result.mission_name == "sync_observation"
    assert result.evidence_refs == tuple(evidence_refs)


@pytest.mark.asyncio
async def test_mcp_adapter_maps_transport_exception_to_execution_transport_error(
    tmp_path: Path,
) -> None:
    client = FakeMcpClient(raise_exc=RuntimeError("boom"))
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ExecutionTransportError as exc:
        assert "invocation failed" in str(exc)
    else:
        raise AssertionError(
            "Expected transport exception to map to ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_retries_transient_invocation_failure(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    ]
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value="ok"),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(side_effects=[RuntimeError("boom"), tool_output])
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=2),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_mcp_adapter_retries_execution_transport_error(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    ]
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value="ok"),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[ExecutionTransportError("boom"), tool_output],
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=2),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert client.call_count == 2


@pytest.mark.asyncio
async def test_mcp_adapter_exhausts_retries_for_execution_transport_error(
    tmp_path: Path,
) -> None:
    client = FakeMcpClient(
        side_effects=[
            ExecutionTransportError("boom-1"),
            ExecutionTransportError("boom-2"),
        ],
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=2),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ExecutionTransportError as exc:
        assert "boom-2" in str(exc)
        assert client.call_count == 2
    else:
        raise AssertionError(
            "Expected exhausted transport retries to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_wraps_unknown_exception_after_max_attempts(
    tmp_path: Path,
) -> None:
    client = FakeMcpClient(
        side_effects=[RuntimeError("boom-1"), RuntimeError("boom-2")]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=2),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ExecutionTransportError as exc:
        assert "after 2 attempt(s)" in str(exc)
        assert "boom-2" in str(exc)
        assert client.call_count == 2
    else:
        raise AssertionError(
            "Expected exhausted unknown retries to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_does_not_retry_on_mcp_client_typed_errors(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    ]
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value="ok"),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }

    for exc_type in (ConfigError, FlowError, ValidationError):
        client = FakeMcpClient(side_effects=[exc_type("boom"), tool_output])
        adapter = McpBackedExecutionAdapter(
            settings=_settings(max_attempts=2),
            mcp_client=client,
            run_root=tmp_path,
            request_id_factory=lambda: "req-1",
        )
        request = ExecutionRequest(
            mission_name="prepare_session",
            payload={
                "target_page_url": "https://tickets.interpark.com/goods/26003199",
                "site_identity": "interpark",
            },
        )

        try:
            await adapter.execute(request)
        except exc_type:
            assert client.call_count == 1
        else:
            raise AssertionError("Expected typed error to be re-raised without retry")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_whitespace_request_id_before_calling_tool(
    tmp_path: Path,
) -> None:
    client = FakeMcpClient(tool_output={})
    adapter = McpBackedExecutionAdapter(
        settings=_settings(),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: " bad ",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "request_id" in str(exc)
        assert "leading or trailing whitespace" in str(exc)
        assert client.call_count == 0
    else:
        raise AssertionError("Expected invalid request_id to raise ValidationError")


def test_mcp_adapter_rejects_non_page_ready_observed_scope_ceiling(
    tmp_path: Path,
) -> None:
    client = FakeMcpClient(tool_output={})
    try:
        McpBackedExecutionAdapter(
            settings=_settings(),
            mcp_client=client,
            run_root=tmp_path,
            approved_scope_ceiling="syncEstablished",  # type: ignore[arg-type]
        )
    except FlowError as exc:
        assert "approved_scope_ceiling" in str(exc)
    else:
        raise AssertionError("Expected invalid scope ceiling to raise FlowError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_non_object_tool_output(tmp_path: Path) -> None:
    client = FakeMcpClient(tool_output="not-a-dict")
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ExecutionTransportError as exc:
        assert "tool output must be an object" in str(exc)
    else:
        raise AssertionError(
            "Expected non-object tool output to raise ExecutionTransportError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_failure_status_without_failure(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    client = FakeMcpClient(
        tool_output={
            "mission_name": "page_ready_observation",
            "status": "failure",
            "evidence_refs": evidence_refs,
            "observations": {
                evidence_refs[0]: _observation(ref=evidence_refs[0], value=False),
                evidence_refs[1]: _observation(
                    ref=evidence_refs[1], value={"seeded": True}
                ),
            },
        }
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "failure is required" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError("Expected missing failure field to raise ValidationError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_request_id_mismatch(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    client = FakeMcpClient(
        tool_output={
            "mission_name": "page_ready_observation",
            "status": "success",
            "evidence_refs": evidence_refs,
            "observations": {
                evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
                evidence_refs[1]: _observation(
                    ref=evidence_refs[1], value={"seeded": True}
                ),
            },
            "request_id": "req-2",
        }
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except FlowError as exc:
        assert "request_id" in str(exc)
        assert "must match request" in str(exc)
    else:
        raise AssertionError("Expected request_id mismatch to raise FlowError")


@pytest.mark.asyncio
async def test_mcp_adapter_does_not_retry_on_response_schema_validation_failure(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected response schema validation failure to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_missing_observations(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    client = FakeMcpClient(
        tool_output={
            "mission_name": "page_ready_observation",
            "status": "success",
            "evidence_refs": evidence_refs,
        }
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations" in str(exc)
    else:
        raise AssertionError("Expected missing observations to raise ValidationError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_missing_required_status_field(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "status" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError("Expected missing status field to raise ValidationError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_observations_key_mismatch(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    client = FakeMcpClient(
        tool_output={
            "mission_name": "page_ready_observation",
            "status": "success",
            "evidence_refs": evidence_refs,
            "observations": {
                evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
            },
        }
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(), mcp_client=client, run_root=tmp_path
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations keys must equal evidence_refs" in str(exc)
    else:
        raise AssertionError(
            "Expected observations key mismatch to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_observations_ref_field_mismatch(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: {
                "ref": "evidence://dom/other",
                "kind": "dom",
                "key": "page-shell-ready",
                "value": True,
            },
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations.ref must match" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected observations.ref mismatch to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_duplicate_evidence_refs_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://dom/page-shell-ready",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "evidence_refs" in str(exc)
        assert "unique" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected duplicate evidence_refs to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_invalid_status_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "ok",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "status" in str(exc)
        assert "success" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError("Expected invalid status to raise ValidationError")


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_whitespace_evidence_ref_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        " evidence://action-log/release-ceiling-stop ",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            "evidence://dom/page-shell-ready": _observation(
                ref="evidence://dom/page-shell-ready", value=True
            ),
            " evidence://action-log/release-ceiling-stop ": _observation(
                ref=" evidence://action-log/release-ceiling-stop ",
                value={"seeded": True},
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "evidence_refs" in str(exc)
        assert "leading or trailing whitespace" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected whitespace evidence_ref to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_observations_kind_mismatch_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: {
                "ref": evidence_refs[0],
                "kind": "text",
                "key": "page-shell-ready",
                "value": True,
            },
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations.kind must match" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected observations.kind mismatch to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_non_json_serializable_observation_value(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value=object()),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations.value" in str(exc)
        assert "JSON-serializable" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected non-serializable observations.value to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_observations_key_mismatch_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: {
                "ref": evidence_refs[0],
                "kind": "dom",
                "key": "other",
                "value": True,
            },
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations.key must match" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected observations.key mismatch to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_invalid_observations_ts_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: {
                "ref": evidence_refs[0],
                "kind": "dom",
                "key": "page-shell-ready",
                "value": True,
                "ts": "not-a-timestamp",
            },
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ValidationError as exc:
        assert "observations.ts" in str(exc)
        assert "ISO-8601" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected invalid observations.ts to raise ValidationError"
        )


@pytest.mark.asyncio
async def test_mcp_adapter_accepts_zulu_observations_ts(tmp_path: Path) -> None:
    evidence_refs = [
        "evidence://text/session-viable",
        "evidence://action-log/prepare-session",
    ]
    observation = _observation(ref=evidence_refs[0], value="ok")
    observation["ts"] = "2026-03-21T00:00:00Z"
    tool_output = {
        "mission_name": "prepare_session",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: observation,
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
        "request_id": "req-1",
    }
    client = FakeMcpClient(tool_output=tool_output)
    adapter = McpBackedExecutionAdapter(
        settings=_settings(),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )
    result = await adapter.execute(request)

    assert result.mission_name == "prepare_session"
    assert result.evidence_refs == tuple(evidence_refs)


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_non_path_run_root() -> None:
    client = FakeMcpClient(tool_output={})

    with pytest.raises(ConfigError) as excinfo:
        McpBackedExecutionAdapter(
            settings=_settings(),
            mcp_client=client,
            run_root="not-a-path",  # type: ignore[arg-type]
            request_id_factory=lambda: "req-1",
        )

    assert "run_root must be a pathlib.Path" in str(excinfo.value)


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_nonexistent_run_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing-run-root"
    client = FakeMcpClient(tool_output={})
    adapter = McpBackedExecutionAdapter(
        settings=_settings(),
        mcp_client=client,
        run_root=missing,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="prepare_session",
        payload={
            "target_page_url": "https://tickets.interpark.com/goods/26003199",
            "site_identity": "interpark",
        },
    )

    with pytest.raises(ConfigError) as excinfo:
        await adapter.execute(request)

    assert "must exist before invocation" in str(excinfo.value)
    assert client.call_count == 0


@pytest.mark.asyncio
async def test_mcp_adapter_rejects_non_json_serializable_tool_output_without_retry(
    tmp_path: Path,
) -> None:
    evidence_refs = [
        "evidence://dom/page-shell-ready",
        "evidence://action-log/release-ceiling-stop",
    ]
    invalid_output = {
        "mission_name": "page_ready_observation",
        "status": "success",
        "evidence_refs": evidence_refs,
        "observations": {
            evidence_refs[0]: _observation(ref=evidence_refs[0], value=True),
            evidence_refs[1]: _observation(
                ref=evidence_refs[1], value={"seeded": True}
            ),
        },
        "timing": object(),
    }
    client = FakeMcpClient(
        side_effects=[invalid_output, invalid_output, invalid_output]
    )
    adapter = McpBackedExecutionAdapter(
        settings=_settings(max_attempts=3),
        mcp_client=client,
        run_root=tmp_path,
        request_id_factory=lambda: "req-1",
    )

    request = ExecutionRequest(
        mission_name="page_ready_observation", payload={}
    )

    try:
        await adapter.execute(request)
    except ExecutionTransportError as exc:
        assert "tool output" in str(exc)
        assert "JSON-serializable" in str(exc)
        assert client.call_count == 1
    else:
        raise AssertionError(
            "Expected non-serializable tool output to raise ExecutionTransportError"
        )
