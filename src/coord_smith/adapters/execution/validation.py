"""Validation and builder functions for execution requests and results."""

from __future__ import annotations

import json

from coord_smith.adapters.execution.contracts import (
    ExecutionRequest,
    ExecutionResult,
    _payload_json_default,
)
from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.missions.evidence_specs import MISSION_EVIDENCE_SPECS
from coord_smith.missions.names import ALL_MISSIONS, mission_is_browser_facing
from coord_smith.models.errors import ConfigError
from coord_smith.models.identifiers import MissionName, parse_mission_name
from coord_smith.models.runtime import (
    effective_scope_ceiling,
    format_scope_ceiling_detail,
    mission_is_within_approved_scope,
)


def validate_execution_mission_name(mission_name: MissionName) -> None:
    """Reject non-browser-facing missions for OpenClaw execution requests."""

    if not isinstance(mission_name, str):
        msg = "OpenClaw mission_name must be a string"
        raise TypeError(msg)
    if not mission_name:
        msg = "OpenClaw mission_name must be non-empty"
        raise ValueError(msg)
    if not mission_name.strip():
        msg = "OpenClaw mission_name must not be whitespace-only"
        raise ValueError(msg)
    if mission_name != mission_name.strip():
        msg = "OpenClaw mission_name must not have leading or trailing whitespace"
        raise ValueError(msg)
    if mission_name not in ALL_MISSIONS:
        msg = f"Unknown mission name: {mission_name}"
        raise ValueError(msg)
    if not mission_is_browser_facing(mission_name):
        msg = (
            f"Mission '{mission_name}' is not browser-facing and cannot run on OpenClaw"
        )
        raise ValueError(msg)


def validate_execution_request(request: ExecutionRequest) -> None:
    """Validate an execution request before handing it to OpenClaw."""

    validate_execution_mission_name(request.mission_name)
    if not isinstance(request.payload, dict):
        msg = "OpenClaw execution request payload must be a dict"
        raise TypeError(msg)
    for key in request.payload:
        if not isinstance(key, str):
            msg = "OpenClaw execution request payload keys must be strings"
            raise TypeError(msg)
        if not key:
            msg = "OpenClaw execution request payload keys must be non-empty"
            raise ValueError(msg)
        if not key.strip():
            msg = "OpenClaw execution request payload keys must not be whitespace-only"
            raise ValueError(msg)
        if key != key.strip():
            msg = (
                "OpenClaw execution request payload keys must not have leading or "
                "trailing whitespace"
            )
            raise ValueError(msg)
    try:
        json.dumps(
            request.payload, allow_nan=False, default=_payload_json_default
        )
    except (TypeError, ValueError) as exc:
        msg = "OpenClaw execution request payload must be JSON-serializable"
        raise TypeError(msg) from exc

    required_keys: tuple[str, ...]
    if request.mission_name == "prepare_session":
        required_keys = ("target_page_url", "site_identity")
    elif request.mission_name == "attach_session":
        required_keys = ("session_ref", "expected_auth_state")
    else:
        # step_observe / step_dispatch / step_capture / run_completion carry
        # structured payloads (step_idx + step dict / step_count int) whose
        # shape is validated downstream (adapter + validate_execution_result).
        required_keys = ()

    for key in required_keys:
        if key not in request.payload:
            msg = (
                "OpenClaw execution request payload is missing required key "
                f"'{key}' for mission '{request.mission_name}'"
            )
            raise ValueError(msg)
        value = request.payload[key]
        if not isinstance(value, str):
            msg = (
                "OpenClaw execution request payload value must be a string for "
                f"key '{key}' (mission '{request.mission_name}')"
            )
            raise TypeError(msg)
        if not value:
            msg = (
                "OpenClaw execution request payload value must be non-empty for "
                f"key '{key}' (mission '{request.mission_name}')"
            )
            raise ValueError(msg)
        if not value.strip():
            msg = (
                "OpenClaw execution request payload value must not be whitespace-only "
                f"for key '{key}' (mission '{request.mission_name}')"
            )
            raise ValueError(msg)
        if value != value.strip():
            msg = (
                "OpenClaw execution request payload value must not have leading or "
                "trailing whitespace for "
                f"key '{key}' (mission '{request.mission_name}')"
            )
            raise ValueError(msg)


def validate_execution_request_within_scope(
    request: ExecutionRequest, approved_scope_ceiling: str
) -> None:
    """Validate an execution request against the approved scope ceiling."""

    validate_execution_request(request)
    effective_ceiling = effective_scope_ceiling(approved_scope_ceiling)
    if not mission_is_within_approved_scope(
        request.mission_name, approved_scope_ceiling=effective_ceiling
    ):
        ceiling_detail = format_scope_ceiling_detail(approved_scope_ceiling)
        msg = (
            f"Mission '{request.mission_name}' is outside approved scope ceiling "
            f"{ceiling_detail}"
        )
        raise ValueError(msg)


def validate_execution_result(result: ExecutionResult) -> None:
    """Validate a typed execution result returned by OpenClaw."""

    validate_execution_mission_name(result.mission_name)
    if not isinstance(result.evidence_refs, tuple):
        msg = "OpenClaw execution result evidence_refs must be a tuple"
        raise TypeError(msg)
    if not result.evidence_refs:
        msg = "OpenClaw execution result evidence_refs must be non-empty"
        raise ValueError(msg)
    for ref in result.evidence_refs:
        if not isinstance(ref, str):
            msg = "OpenClaw execution result evidence_refs entries must be strings"
            raise TypeError(msg)
        if not ref:
            msg = "OpenClaw execution result evidence_refs entries must be non-empty"
            raise ValueError(msg)
        if not ref.strip():
            msg = (
                "OpenClaw execution result evidence_refs entries must not be "
                "whitespace-only"
            )
            raise ValueError(msg)
        if ref != ref.strip():
            msg = (
                "OpenClaw execution result evidence_refs entries must not have "
                "leading or trailing whitespace"
            )
            raise ValueError(msg)
    if len(set(result.evidence_refs)) != len(result.evidence_refs):
        msg = "OpenClaw execution result evidence_refs entries must be unique"
        raise ValueError(msg)

    for ref in result.evidence_refs:
        try:
            parse_released_evidence_ref(ref)
        except (TypeError, ValueError) as exc:
            msg = (
                "OpenClaw execution result evidence_refs entries must match "
                "'evidence://{kind}/{key}' released-scope schema: "
                f"got '{ref}'"
            )
            raise ValueError(msg) from exc

    observed = set(result.evidence_refs)

    # Derive required_sets from the single source of truth in
    # MISSION_EVIDENCE_SPECS rather than re-declaring inline.
    spec = MISSION_EVIDENCE_SPECS.get(result.mission_name)
    if spec is not None:
        if spec.fallback_refs:
            required_sets: tuple[frozenset[str], ...] = (
                spec.primary_refs,
                spec.fallback_refs,
            )
        else:
            required_sets = (spec.primary_refs,)
    else:
        required_sets = ()

    if required_sets and not any(
        required.issubset(observed) for required in required_sets
    ):

        def format_missing(required: frozenset[str]) -> str:
            missing = sorted(required - observed)
            return ", ".join(missing) if missing else "none"

        primary_missing = format_missing(required_sets[0]) if required_sets else "none"
        fallback_missing = (
            format_missing(required_sets[1]) if len(required_sets) > 1 else "none"
        )
        msg = (
            "OpenClaw execution result evidence_refs missing required minimum keys "
            f"for mission '{result.mission_name}': "
            f"primary missing [{primary_missing}]; "
            f"fallback missing [{fallback_missing}]"
        )
        raise ValueError(msg)


def validate_execution_result_within_scope(
    result: ExecutionResult, approved_scope_ceiling: str
) -> None:
    """Validate an execution result against the approved scope ceiling."""

    validate_execution_result(result)
    effective_ceiling = effective_scope_ceiling(approved_scope_ceiling)
    if not mission_is_within_approved_scope(
        result.mission_name, approved_scope_ceiling=effective_ceiling
    ):
        ceiling_detail = format_scope_ceiling_detail(approved_scope_ceiling)
        msg = (
            f"Mission '{result.mission_name}' is outside approved scope ceiling "
            f"{ceiling_detail}"
        )
        raise ValueError(msg)


def validate_execution_roundtrip_within_scope(
    *,
    request: ExecutionRequest,
    result: ExecutionResult,
    approved_scope_ceiling: str,
) -> None:
    """Validate an OpenClaw request/result pair for comparable typed evidence."""

    validate_execution_request_within_scope(
        request, approved_scope_ceiling=approved_scope_ceiling
    )
    validate_execution_result_within_scope(
        result, approved_scope_ceiling=approved_scope_ceiling
    )
    if request.mission_name != result.mission_name:
        msg = (
            "OpenClaw execution result mission_name must match request mission_name: "
            f"request='{request.mission_name}', result='{result.mission_name}'."
        )
        raise ValueError(msg)


def build_execution_request(
    *, mission_name: str, payload: dict[str, object]
) -> ExecutionRequest:
    """Build a validated OpenClaw execution request.

    ``mission_name`` is a raw string boundary input; it is parsed to
    ``MissionName`` via ``parse_mission_name`` before construction so the
    returned dataclass carries the typed identifier.
    """
    try:
        typed_name = parse_mission_name(mission_name)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    request = ExecutionRequest(mission_name=typed_name, payload=payload)
    validate_execution_request(request)
    return request


def build_execution_request_within_scope(
    *, mission_name: str, payload: dict[str, object], approved_scope_ceiling: str
) -> ExecutionRequest:
    """Build a validated OpenClaw execution request constrained to released scope."""
    try:
        typed_name = parse_mission_name(mission_name)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    request = ExecutionRequest(mission_name=typed_name, payload=payload)
    validate_execution_request_within_scope(
        request, approved_scope_ceiling=approved_scope_ceiling
    )
    return request


def build_execution_result(
    *, mission_name: str, evidence_refs: tuple[str, ...]
) -> ExecutionResult:
    """Build a validated OpenClaw execution result."""
    try:
        typed_name = parse_mission_name(mission_name)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    result = ExecutionResult(
        mission_name=typed_name, evidence_refs=evidence_refs
    )
    validate_execution_result(result)
    return result


def build_execution_result_within_scope(
    *, mission_name: str, evidence_refs: tuple[str, ...], approved_scope_ceiling: str
) -> ExecutionResult:
    """Build a validated OpenClaw execution result constrained to released scope."""
    try:
        typed_name = parse_mission_name(mission_name)
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc
    result = ExecutionResult(
        mission_name=typed_name, evidence_refs=evidence_refs
    )
    validate_execution_result_within_scope(
        result, approved_scope_ceiling=approved_scope_ceiling
    )
    return result
