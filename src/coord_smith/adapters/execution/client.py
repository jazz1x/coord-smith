"""Transport-neutral injected boundary contract for OpenClaw execution.

This module is a re-export shim + orchestration wrapper.

Public symbols are forwarded from the focused sub-modules so that all
existing ``from coord_smith.adapters.execution.client import X`` callers
continue to work without modification:

- contracts.py   — dataclasses, Protocols, _payload_json_default
- validation.py  — validate_*_ / build_*_ functions
- artifact_io.py — action-log path helpers + JSONL schema checks
"""

from __future__ import annotations

from pathlib import Path

# --- artifact_io re-exports ---
from coord_smith.adapters.execution.artifact_io import (
    action_log_artifact_path,
    validate_action_log_artifacts_contain_ref_events,
    validate_action_log_artifacts_have_minimum_schema,
    validate_action_log_evidence_refs_resolvable,
    validate_release_ceiling_stop_action_log,
)

# --- contracts re-exports ---
from coord_smith.adapters.execution.contracts import (
    ExecutionAdapter,
    ExecutionBoundary,
    ExecutionRequest,
    ExecutionResult,
)

# --- validation re-exports ---
from coord_smith.adapters.execution.validation import (
    build_execution_request,
    build_execution_request_within_scope,
    build_execution_result,
    build_execution_result_within_scope,
    validate_execution_mission_name,
    validate_execution_request,
    validate_execution_request_within_scope,
    validate_execution_result,
    validate_execution_result_within_scope,
    validate_execution_roundtrip_within_scope,
)
from coord_smith.models.errors import AppError, ExecutionTransportError, ValidationError

__all__ = [
    # contracts
    "ExecutionAdapter",
    "ExecutionBoundary",
    "ExecutionRequest",
    "ExecutionResult",
    # validation
    "build_execution_request",
    "build_execution_request_within_scope",
    "build_execution_result",
    "build_execution_result_within_scope",
    "validate_execution_mission_name",
    "validate_execution_request",
    "validate_execution_request_within_scope",
    "validate_execution_result",
    "validate_execution_result_within_scope",
    "validate_execution_roundtrip_within_scope",
    # artifact_io
    "action_log_artifact_path",
    "validate_action_log_artifacts_contain_ref_events",
    "validate_action_log_artifacts_have_minimum_schema",
    "validate_action_log_evidence_refs_resolvable",
    "validate_release_ceiling_stop_action_log",
    # orchestration
    "execute_within_scope",
]


async def execute_within_scope(
    *,
    adapter: ExecutionAdapter,
    mission_name: str,
    payload: dict[str, object],
    approved_scope_ceiling: str,
    run_root: Path | None = None,
) -> ExecutionResult:
    """Execute OpenClaw with released-scope boundary validation.

    This wrapper hardens request/result contracts and optionally validates action-log
    artifacts under the provided run root.
    """

    from coord_smith.adapters.execution.artifact_io import _require_run_root_dir

    try:
        request = build_execution_request_within_scope(
            mission_name=mission_name,
            payload=payload,
            approved_scope_ceiling=approved_scope_ceiling,
        )
    except (TypeError, ValueError) as exc:
        msg = f"Invalid OpenClaw execution request within released scope: {exc}"
        raise ValidationError(msg) from exc

    try:
        candidate = await adapter.execute(request)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        msg = f"OpenClaw adapter execution failed: {exc}"
        raise ExecutionTransportError(msg) from exc

    if not isinstance(candidate, ExecutionResult):
        msg = (
            "OpenClaw adapter returned an invalid result type: "
            f"expected ExecutionResult, got {type(candidate)!r}"
        )
        raise ValidationError(msg)

    result = candidate
    try:
        validate_execution_roundtrip_within_scope(
            request=request,
            result=result,
            approved_scope_ceiling=approved_scope_ceiling,
        )
    except (TypeError, ValueError) as exc:
        msg = f"Invalid OpenClaw execution result within released scope: {exc}"
        raise ValidationError(msg) from exc
    if run_root is not None:
        run_root = _require_run_root_dir(run_root=run_root)
        validate_action_log_evidence_refs_resolvable(
            evidence_refs=result.evidence_refs,
            run_root=run_root,
        )
        validate_action_log_artifacts_have_minimum_schema(
            evidence_refs=result.evidence_refs,
            run_root=run_root,
        )
        validate_action_log_artifacts_contain_ref_events(
            evidence_refs=result.evidence_refs,
            run_root=run_root,
            expected_mission_name=mission_name,
        )
        validate_release_ceiling_stop_action_log(
            evidence_refs=result.evidence_refs,
            run_root=run_root,
        )
    return result
