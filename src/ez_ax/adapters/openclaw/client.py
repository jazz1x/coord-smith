"""OpenClaw adapter protocol for browser-facing execution."""

import json
from dataclasses import dataclass
from typing import Protocol

from ez_ax.evidence.envelope import parse_released_evidence_ref
from ez_ax.missions.names import ALL_MISSIONS, mission_is_browser_facing
from ez_ax.models.runtime import (
    effective_scope_ceiling,
    format_scope_ceiling_detail,
    mission_is_within_approved_scope,
)


@dataclass(frozen=True, slots=True)
class OpenClawExecutionRequest:
    """Typed execution request passed to OpenClaw."""

    mission_name: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class OpenClawExecutionResult:
    """Typed execution result returned by OpenClaw."""

    mission_name: str
    evidence_refs: tuple[str, ...]


class OpenClawAdapter(Protocol):
    """Protocol for the only browser-facing runtime actor."""

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult: ...


def validate_openclaw_mission_name(mission_name: str) -> None:
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


def validate_openclaw_execution_request(request: OpenClawExecutionRequest) -> None:
    """Validate an execution request before handing it to OpenClaw."""

    validate_openclaw_mission_name(request.mission_name)
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
        json.dumps(request.payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        msg = "OpenClaw execution request payload must be JSON-serializable"
        raise TypeError(msg) from exc

    required_keys: tuple[str, ...]
    if request.mission_name == "prepare_session":
        required_keys = ("target_page_url", "site_identity")
    elif request.mission_name == "attach_session":
        required_keys = ("session_ref", "expected_auth_state")
    elif request.mission_name == "benchmark_validation":
        required_keys = ("target_page_url",)
    else:
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


def validate_openclaw_execution_request_within_scope(
    request: OpenClawExecutionRequest, approved_scope_ceiling: str
) -> None:
    """Validate an execution request against the approved scope ceiling."""

    validate_openclaw_execution_request(request)
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


def validate_openclaw_execution_result(result: OpenClawExecutionResult) -> None:
    """Validate a typed execution result returned by OpenClaw."""

    validate_openclaw_mission_name(result.mission_name)
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

    required_sets: tuple[set[str], ...]
    if result.mission_name == "prepare_session":
        primary = {
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        }
        fallback = {
            "evidence://screenshot/prepare-session-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/prepare-session",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "benchmark_validation":
        primary = {
            "evidence://action-log/enter-target-page",
            "evidence://dom/target-page-entered",
        }
        fallback = {
            "evidence://action-log/enter-target-page",
            "evidence://screenshot/target-page-entered-fallback",
            "evidence://text/fallback-reason",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "page_ready_observation":
        primary = {
            "evidence://dom/page-shell-ready",
            "evidence://action-log/release-ceiling-stop",
        }
        fallback = {
            "evidence://screenshot/page-shell-ready-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/release-ceiling-stop",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "attach_session":
        primary = {
            "evidence://text/session-attached",
            "evidence://text/auth-state-confirmed",
            "evidence://action-log/attach-session",
        }
        fallback = {
            "evidence://screenshot/attach-session-fallback",
            "evidence://text/fallback-reason",
            "evidence://action-log/attach-session",
        }
        required_sets = (primary, fallback)
    else:
        required_sets = ()

    if required_sets and not any(
        required.issubset(observed) for required in required_sets
    ):

        def format_missing(required: set[str]) -> str:
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


def validate_openclaw_execution_result_within_scope(
    result: OpenClawExecutionResult, approved_scope_ceiling: str
) -> None:
    """Validate an execution result against the approved scope ceiling."""

    validate_openclaw_execution_result(result)
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


def validate_openclaw_execution_roundtrip_within_scope(
    *,
    request: OpenClawExecutionRequest,
    result: OpenClawExecutionResult,
    approved_scope_ceiling: str,
) -> None:
    """Validate an OpenClaw request/result pair for comparable typed evidence."""

    validate_openclaw_execution_request_within_scope(
        request, approved_scope_ceiling=approved_scope_ceiling
    )
    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling=approved_scope_ceiling
    )
    if request.mission_name != result.mission_name:
        msg = (
            "OpenClaw execution result mission_name must match request mission_name: "
            f"request='{request.mission_name}', result='{result.mission_name}'."
        )
        raise ValueError(msg)


def build_openclaw_execution_request(
    *, mission_name: str, payload: dict[str, object]
) -> OpenClawExecutionRequest:
    """Build a validated OpenClaw execution request."""

    request = OpenClawExecutionRequest(mission_name=mission_name, payload=payload)
    validate_openclaw_execution_request(request)
    return request


def build_openclaw_execution_request_within_scope(
    *, mission_name: str, payload: dict[str, object], approved_scope_ceiling: str
) -> OpenClawExecutionRequest:
    """Build a validated OpenClaw execution request constrained to released scope."""

    request = OpenClawExecutionRequest(mission_name=mission_name, payload=payload)
    validate_openclaw_execution_request_within_scope(
        request, approved_scope_ceiling=approved_scope_ceiling
    )
    return request


def build_openclaw_execution_result(
    *, mission_name: str, evidence_refs: tuple[str, ...]
) -> OpenClawExecutionResult:
    """Build a validated OpenClaw execution result."""

    result = OpenClawExecutionResult(
        mission_name=mission_name, evidence_refs=evidence_refs
    )
    validate_openclaw_execution_result(result)
    return result


def build_openclaw_execution_result_within_scope(
    *, mission_name: str, evidence_refs: tuple[str, ...], approved_scope_ceiling: str
) -> OpenClawExecutionResult:
    """Build a validated OpenClaw execution result constrained to released scope."""

    result = OpenClawExecutionResult(
        mission_name=mission_name, evidence_refs=evidence_refs
    )
    validate_openclaw_execution_result_within_scope(
        result, approved_scope_ceiling=approved_scope_ceiling
    )
    return result
