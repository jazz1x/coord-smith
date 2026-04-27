"""Modeled MCP-backed OpenClaw adapter (scaffold hardening only).

This module implements a concrete ExecutionAdapter that invokes OpenClaw through
an injected MCP client. It enforces the released-scope envelope contracts from:

- docs/product/prd-openclaw-computer-use-runtime.md

It does not provide a real MCP transport implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol, cast

from ez_ax.adapters.execution.client import (
    ExecutionAdapter,
    ExecutionRequest,
    ExecutionResult,
    validate_execution_request,
    validate_execution_result,
)
from ez_ax.adapters.execution.mcp_settings import McpExecutionAdapterSettings
from ez_ax.evidence.envelope import parse_released_evidence_ref
from ez_ax.models.errors import (
    ConfigError,
    ExecutionTransportError,
    FlowError,
    ValidationError,
)
from ez_ax.models.runtime import (
    effective_scope_ceiling,
    mission_is_within_approved_scope,
)

ReleasedScopeCeiling = Literal["pageReadyObserved", "runCompletion"]
ReleasedResponseStatus = Literal["success", "failure", "pending"]


class McpClient(Protocol):
    """Protocol for an injected MCP client/session handle."""

    async def call_tool(
        self,
        *,
        server_name: str,
        tool_name: str,
        tool_input: dict[str, object],
        timeout_seconds: float,
    ) -> object: ...


def _require_normalized_str(*, label: str, value: object) -> str:
    if not isinstance(value, str):
        msg = f"{label} must be a string"
        raise ValidationError(msg)
    if not value:
        msg = f"{label} must be non-empty"
        raise ValidationError(msg)
    if not value.strip():
        msg = f"{label} must not be whitespace-only"
        raise ValidationError(msg)
    if value != value.strip():
        msg = f"{label} must not have leading or trailing whitespace"
        raise ValidationError(msg)
    return value


def _require_json_serializable(*, label: str, value: object) -> None:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = f"{label} must be JSON-serializable"
        raise ValidationError(msg) from exc


def _require_iso8601_timestamp(*, label: str, value: str) -> None:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        datetime.fromisoformat(value)
    except ValueError as exc:
        msg = f"{label} must be parseable as ISO-8601"
        raise ValidationError(msg) from exc


def _require_existing_run_root(*, run_root: Path) -> None:
    if not run_root.exists():
        msg = (
            f"MCP OpenClaw run_root must exist before invocation: run_root='{run_root}'"
        )
        raise ConfigError(msg)
    if not run_root.is_dir():
        msg = f"MCP OpenClaw run_root must be a directory: run_root='{run_root}'"
        raise ConfigError(msg)


def _require_response_status(value: object) -> ReleasedResponseStatus:
    if value not in ("success", "failure", "pending"):
        msg = "MCP OpenClaw response status must be one of: success | failure | pending"
        raise ValidationError(msg)
    return value


def _parse_evidence_refs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        msg = "MCP OpenClaw response evidence_refs must be an array of strings"
        raise ValidationError(msg)
    if not value:
        msg = "MCP OpenClaw response evidence_refs must be non-empty"
        raise ValidationError(msg)

    normalized: list[str] = []
    for idx, ref in enumerate(value):
        if not isinstance(ref, str):
            msg = "MCP OpenClaw response evidence_refs entries must be strings"
            raise ValidationError(msg)
        if not ref:
            msg = "MCP OpenClaw response evidence_refs entries must be non-empty"
            raise ValidationError(msg)
        if not ref.strip():
            msg = (
                "MCP OpenClaw response evidence_refs entries must not be "
                "whitespace-only"
            )
            raise ValidationError(msg)
        if ref != ref.strip():
            msg = (
                "MCP OpenClaw response evidence_refs entries must not have leading or "
                "trailing whitespace"
            )
            raise ValidationError(msg)
        try:
            parse_released_evidence_ref(ref)
        except (TypeError, ValueError) as exc:
            msg = (
                "MCP OpenClaw response evidence_refs entries must match "
                "'evidence://{kind}/{key}' released-scope schema: "
                f"got '{ref}' (index {idx})"
            )
            raise ValidationError(msg) from exc
        normalized.append(ref)

    if len(set(normalized)) != len(normalized):
        msg = "MCP OpenClaw response evidence_refs entries must be unique"
        raise ValidationError(msg)

    return tuple(normalized)


def _validate_observation_entry(*, ref: str, entry: object) -> None:
    if not isinstance(entry, dict):
        msg = f"MCP OpenClaw observations entry must be an object: ref='{ref}'"
        raise ValidationError(msg)

    observed_ref = _require_normalized_str(
        label="MCP OpenClaw observations.ref", value=entry.get("ref")
    )
    if observed_ref != ref:
        msg = (
            "MCP OpenClaw observations.ref must match its map key: "
            f"key='{ref}', ref='{observed_ref}'"
        )
        raise ValidationError(msg)

    kind, key = parse_released_evidence_ref(ref)

    observed_kind = _require_normalized_str(
        label="MCP OpenClaw observations.kind", value=entry.get("kind")
    )
    if observed_kind != kind:
        msg = (
            "MCP OpenClaw observations.kind must match evidence ref kind: "
            f"ref='{ref}', expected_kind='{kind}', got_kind='{observed_kind}'"
        )
        raise ValidationError(msg)

    observed_key = _require_normalized_str(
        label="MCP OpenClaw observations.key", value=entry.get("key")
    )
    if observed_key != key:
        msg = (
            "MCP OpenClaw observations.key must match evidence ref key: "
            f"ref='{ref}', expected_key='{key}', got_key='{observed_key}'"
        )
        raise ValidationError(msg)

    if "value" not in entry:
        msg = f"MCP OpenClaw observations.value is required: ref='{ref}'"
        raise ValidationError(msg)
    _require_json_serializable(
        label="MCP OpenClaw observations.value", value=entry["value"]
    )

    ts = entry.get("ts")
    if ts is None:
        return
    ts_value = _require_normalized_str(label="MCP OpenClaw observations.ts", value=ts)
    _require_iso8601_timestamp(label="MCP OpenClaw observations.ts", value=ts_value)


def _parse_observations(
    *, evidence_refs: tuple[str, ...], value: object
) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = "MCP OpenClaw response observations must be an object"
        raise ValidationError(msg)

    typed_value = cast(dict[str, object], value)

    for key in typed_value.keys():
        if not isinstance(key, str):
            msg = "MCP OpenClaw response observations keys must be strings"
            raise ValidationError(msg)

    keys = set(typed_value.keys())
    expected = set(evidence_refs)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        msg = (
            "MCP OpenClaw response observations keys must equal evidence_refs set: "
            f"missing={missing}, extra={extra}"
        )
        raise ValidationError(msg)

    for ref in evidence_refs:
        _validate_observation_entry(ref=ref, entry=typed_value[ref])

    _require_json_serializable(
        label="MCP OpenClaw response observations", value=typed_value
    )
    return typed_value


@dataclass(frozen=True, slots=True)
class McpExecutionResponseEnvelope:
    mission_name: str
    status: ReleasedResponseStatus
    evidence_refs: tuple[str, ...]
    observations: dict[str, object]
    failure: object | None = None
    timing: object | None = None
    request_id: str | None = None


def parse_mcp_execution_response_envelope(
    *,
    payload: object,
    expected_mission_name: str,
    expected_request_id: str,
) -> McpExecutionResponseEnvelope:
    if not isinstance(payload, dict):
        msg = "MCP OpenClaw tool output must be an object"
        raise ExecutionTransportError(msg)

    mission_name = _require_normalized_str(
        label="MCP OpenClaw response mission_name", value=payload.get("mission_name")
    )
    if mission_name != expected_mission_name:
        msg = (
            "MCP OpenClaw response mission_name must match request mission_name: "
            f"expected='{expected_mission_name}', got='{mission_name}'"
        )
        raise FlowError(msg)

    status = _require_response_status(payload.get("status"))
    evidence_refs = _parse_evidence_refs(payload.get("evidence_refs"))
    observations = _parse_observations(
        evidence_refs=evidence_refs, value=payload.get("observations")
    )

    request_id = payload.get("request_id")
    if request_id is not None:
        request_id = _require_normalized_str(
            label="MCP OpenClaw response request_id", value=request_id
        )
        if request_id != expected_request_id:
            msg = (
                "MCP OpenClaw response request_id must match request: "
                f"expected='{expected_request_id}', got='{request_id}'"
            )
            raise FlowError(msg)

    failure = payload.get("failure")
    if status == "failure" and failure is None:
        msg = "MCP OpenClaw response failure is required when status == 'failure'"
        raise ValidationError(msg)

    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = "MCP OpenClaw tool output must be JSON-serializable"
        raise ExecutionTransportError(msg) from exc

    return McpExecutionResponseEnvelope(
        mission_name=mission_name,
        status=status,
        evidence_refs=evidence_refs,
        observations=observations,
        failure=failure,
        timing=payload.get("timing"),
        request_id=request_id,
    )


def _default_request_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class McpBackedExecutionAdapter(ExecutionAdapter):
    """Concrete ExecutionAdapter that invokes OpenClaw via an injected MCP client."""

    settings: McpExecutionAdapterSettings
    mcp_client: McpClient
    run_root: Path | None = None
    approved_scope_ceiling: ReleasedScopeCeiling = "runCompletion"
    request_id_factory: Callable[[], str] = field(default=_default_request_id)

    def __post_init__(self) -> None:
        if not isinstance(self.settings, McpExecutionAdapterSettings):
            msg = (
                "McpBackedExecutionAdapter.settings must be "
                "McpExecutionAdapterSettings"
            )
            raise ConfigError(msg)
        if self.run_root is not None and not isinstance(self.run_root, Path):
            msg = (
                "McpBackedExecutionAdapter.run_root must be a pathlib.Path "
                "when provided"
            )
            raise ConfigError(msg)
        if self.approved_scope_ceiling != "runCompletion":
            msg = (
                "McpBackedExecutionAdapter.approved_scope_ceiling must equal "
                "runCompletion"
            )
            raise FlowError(msg)

    def with_run_root(self, *, run_root: Path) -> McpBackedExecutionAdapter:
        """Return a copy of this adapter bound to a released-scope run root."""

        if not isinstance(run_root, Path):
            msg = "McpBackedExecutionAdapter.with_run_root expects a pathlib.Path"
            raise ConfigError(msg)
        return McpBackedExecutionAdapter(
            settings=self.settings,
            mcp_client=self.mcp_client,
            run_root=run_root,
            approved_scope_ceiling=self.approved_scope_ceiling,
            request_id_factory=self.request_id_factory,
        )

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute OpenClaw through MCP with released-scope envelope validation."""

        try:
            validate_execution_request(request)
        except (TypeError, ValueError) as exc:
            msg = f"Invalid ExecutionRequest at MCP boundary: {exc}"
            raise ValidationError(msg) from exc

        ceiling = effective_scope_ceiling(self.approved_scope_ceiling)
        if not mission_is_within_approved_scope(
            request.mission_name, approved_scope_ceiling=ceiling
        ):
            msg = (
                "OpenClaw mission is outside approved scope ceiling "
                f"'{self.approved_scope_ceiling}': mission='{request.mission_name}'"
            )
            raise FlowError(msg)

        if self.run_root is None:
            msg = (
                "MCP OpenClaw adapter requires run_root to be configured before "
                "execution"
            )
            raise ConfigError(msg)
        _require_existing_run_root(run_root=self.run_root)

        request_id = self.request_id_factory()
        request_id = _require_normalized_str(
            label="MCP OpenClaw request_id", value=request_id
        )

        tool_input: dict[str, object] = {
            "mission_name": request.mission_name,
            "payload": request.payload,
            "run_root": str(self.run_root),
            "scope_ceiling": self.approved_scope_ceiling,
            "request_id": request_id,
        }
        _require_json_serializable(label="MCP OpenClaw tool_input", value=tool_input)

        tool_output: object | None = None
        max_attempts = int(self.settings.retry_policy.max_attempts)
        for attempt in range(1, max_attempts + 1):
            try:
                tool_output = await self.mcp_client.call_tool(
                    server_name=self.settings.mcp_server_name,
                    tool_name=self.settings.tool_name,
                    tool_input=tool_input,
                    timeout_seconds=float(self.settings.default_timeout_seconds),
                )
                break
            except (ConfigError, FlowError, ValidationError):
                raise
            except ExecutionTransportError:
                if attempt < max_attempts:
                    continue
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt < max_attempts:
                    continue
                msg = (
                    "MCP OpenClaw invocation failed after "
                    f"{max_attempts} attempt(s): {exc}"
                )
                raise ExecutionTransportError(msg) from exc
        if tool_output is None:
            msg = "MCP OpenClaw invocation did not return a tool output"
            raise ExecutionTransportError(msg)

        envelope = parse_mcp_execution_response_envelope(
            payload=tool_output,
            expected_mission_name=request.mission_name,
            expected_request_id=request_id,
        )
        result = ExecutionResult(
            mission_name=envelope.mission_name,
            evidence_refs=envelope.evidence_refs,
        )
        try:
            validate_execution_result(result)
        except (TypeError, ValueError) as exc:
            msg = f"Invalid ExecutionResult at MCP boundary: {exc}"
            raise ValidationError(msg) from exc
        return result
