"""Transport-neutral injected boundary contract for OpenClaw execution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.missions.names import ALL_MISSIONS, mission_is_browser_facing
from coord_smith.models.errors import AppError, ExecutionTransportError, ValidationError
from coord_smith.models.runtime import (
    effective_scope_ceiling,
    format_scope_ceiling_detail,
    mission_is_within_approved_scope,
)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Typed execution request passed to OpenClaw."""

    mission_name: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Typed execution result returned by OpenClaw."""

    mission_name: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.mission_name, str) or not self.mission_name.strip():
            raise ValidationError(
                "ExecutionResult.mission_name must be a non-empty string"
            )
        if not isinstance(self.evidence_refs, tuple):
            raise ValidationError("ExecutionResult.evidence_refs must be a tuple")
        for ref in self.evidence_refs:
            try:
                parse_released_evidence_ref(ref)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"ExecutionResult.evidence_refs contains invalid ref: '{ref}'"
                ) from exc


class ExecutionBoundary(Protocol):
    """Transport-neutral injected boundary for OpenClaw execution."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult: ...


class ExecutionAdapter(ExecutionBoundary, Protocol):
    """Canonical alias for the injected OpenClaw execution boundary."""


def validate_execution_mission_name(mission_name: str) -> None:
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

    required_sets: tuple[set[str], ...]
    if result.mission_name == "prepare_session":
        primary = {
            "evidence://text/session-viable",
            "evidence://action-log/prepare-session",
        }
        fallback = {
            "evidence://screenshot/prepare-session-fallback",
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
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "page_ready_observation":
        primary = {
            "evidence://dom/page-shell-ready",
            "evidence://action-log/page-ready-observed",
        }
        fallback = {
            "evidence://screenshot/page-shell-ready-fallback",
            "evidence://action-log/page-ready-observed",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "sync_observation":
        primary = {
            "evidence://clock/server-time-synced",
            "evidence://action-log/sync-observed",
        }
        fallback = {
            "evidence://screenshot/sync-fallback",
            "evidence://action-log/sync-observed",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "target_actionability_observation":
        primary = {
            "evidence://dom/target-actionable",
            "evidence://action-log/target-actionable-observed",
        }
        fallback = {
            "evidence://screenshot/target-actionable-fallback",
            "evidence://action-log/target-actionable-observed",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "armed_state_entry":
        primary = {
            "evidence://text/armed-state-entered",
            "evidence://action-log/armed-state",
        }
        fallback = {
            "evidence://screenshot/armed-state-fallback",
            "evidence://action-log/armed-state",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "trigger_wait":
        primary = {
            "evidence://clock/trigger-received",
            "evidence://action-log/trigger-wait-complete",
        }
        fallback = {
            "evidence://screenshot/trigger-wait-fallback",
            "evidence://action-log/trigger-wait-complete",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "click_dispatch":
        primary = {
            "evidence://action-log/click-dispatched",
            "evidence://dom/click-target-clicked",
        }
        fallback = {
            "evidence://screenshot/click-dispatched-fallback",
            "evidence://action-log/click-dispatched",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "click_completion":
        primary = {
            "evidence://dom/click-effect-confirmed",
            "evidence://action-log/click-completed",
        }
        fallback = {
            "evidence://screenshot/click-completed-fallback",
            "evidence://action-log/click-completed",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "success_observation":
        primary = {
            "evidence://dom/success-observed",
            "evidence://action-log/success-observation",
        }
        fallback = {
            "evidence://screenshot/success-observation-fallback",
            "evidence://action-log/success-observation",
        }
        required_sets = (primary, fallback)
    elif result.mission_name == "run_completion":
        primary = {
            "evidence://action-log/release-ceiling-stop",
        }
        fallback = {
            "evidence://screenshot/run-completion-fallback",
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
    """Build a validated OpenClaw execution request."""

    request = ExecutionRequest(mission_name=mission_name, payload=payload)
    validate_execution_request(request)
    return request


def build_execution_request_within_scope(
    *, mission_name: str, payload: dict[str, object], approved_scope_ceiling: str
) -> ExecutionRequest:
    """Build a validated OpenClaw execution request constrained to released scope."""

    request = ExecutionRequest(mission_name=mission_name, payload=payload)
    validate_execution_request_within_scope(
        request, approved_scope_ceiling=approved_scope_ceiling
    )
    return request


def build_execution_result(
    *, mission_name: str, evidence_refs: tuple[str, ...]
) -> ExecutionResult:
    """Build a validated OpenClaw execution result."""

    result = ExecutionResult(
        mission_name=mission_name, evidence_refs=evidence_refs
    )
    validate_execution_result(result)
    return result


def build_execution_result_within_scope(
    *, mission_name: str, evidence_refs: tuple[str, ...], approved_scope_ceiling: str
) -> ExecutionResult:
    """Build a validated OpenClaw execution result constrained to released scope."""

    result = ExecutionResult(
        mission_name=mission_name, evidence_refs=evidence_refs
    )
    validate_execution_result_within_scope(
        result, approved_scope_ceiling=approved_scope_ceiling
    )
    return result


_KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _require_run_root_dir(*, run_root: object) -> Path:
    """Validate that run_root is a Path that exists and is a directory."""
    if not isinstance(run_root, Path):
        msg = "run_root must be a pathlib.Path"
        raise ValidationError(msg)
    if not run_root.exists():
        msg = f"run_root must exist: run_root='{run_root}'"
        raise ValidationError(msg)
    if not run_root.is_dir():
        msg = f"run_root must be a directory: run_root='{run_root}'"
        raise ValidationError(msg)
    return run_root


def action_log_artifact_path(*, run_root: Path, key: str) -> Path:
    """Return the released-scope action-log artifact path for an evidence ref key."""

    run_root = _require_run_root_dir(run_root=run_root)
    if not isinstance(key, str):
        msg = "key must be a string"
        raise ValidationError(msg)
    if not key:
        msg = "key must be non-empty"
        raise ValidationError(msg)
    if not key.strip():
        msg = "key must not be whitespace-only"
        raise ValidationError(msg)
    if key != key.strip():
        msg = "key must not have leading or trailing whitespace"
        raise ValidationError(msg)
    if _KEBAB_PATTERN.match(key) is None:
        msg = f"key must be kebab-case (lowercase): key='{key}'"
        raise ValidationError(msg)

    return run_root / "artifacts" / "action-log" / f"{key}.jsonl"


def _is_iso8601_timestamp(value: str) -> bool:
    """Check if a value is a valid ISO-8601 timestamp string."""
    if not isinstance(value, str):
        return False
    if not value:
        return False
    if value != value.strip():
        return False
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return True


def validate_action_log_evidence_refs_resolvable(
    *, evidence_refs: tuple[str, ...], run_root: Path
) -> None:
    """Validate released-scope action-log refs can be resolved under the run root."""

    run_root = _require_run_root_dir(run_root=run_root)

    for ref in evidence_refs:
        try:
            kind, key = parse_released_evidence_ref(ref)
        except (TypeError, ValueError) as exc:
            msg = (
                "Invalid evidence ref while resolving action-log artifacts: "
                f"ref='{ref}'"
            )
            raise ValidationError(msg) from exc
        if kind != "action-log":
            continue
        path = action_log_artifact_path(run_root=run_root, key=key)
        if not path.exists():
            msg = (
                "Action-log evidence ref did not resolve to a run-bundled artifact: "
                f"ref='{ref}', expected_path='{path}'"
            )
            raise ValidationError(msg)
        if not path.is_file():
            msg = (
                "Action-log evidence ref did not resolve to a file artifact: "
                f"ref='{ref}', expected_path='{path}'"
            )
            raise ValidationError(msg)


def validate_action_log_artifacts_have_minimum_schema(
    *, evidence_refs: tuple[str, ...], run_root: Path
) -> None:
    """Validate action-log artifacts contain at least one schema-valid JSON line."""

    run_root = _require_run_root_dir(run_root=run_root)

    for ref in evidence_refs:
        try:
            kind, key = parse_released_evidence_ref(ref)
        except (TypeError, ValueError) as exc:
            msg = (
                f"Invalid evidence ref while validating action-log schema: ref='{ref}'"
            )
            raise ValidationError(msg) from exc
        if kind != "action-log":
            continue
        path = action_log_artifact_path(run_root=run_root, key=key)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            msg = f"Failed to read action-log artifact: ref='{ref}', path='{path}'"
            raise ValidationError(msg) from exc

        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            ts = payload.get("ts")
            mission_name = payload.get("mission_name")
            event = payload.get("event")
            if not (isinstance(ts, str) and _is_iso8601_timestamp(ts)):
                continue
            if not (isinstance(mission_name, str) and mission_name.strip()):
                continue
            if mission_name != mission_name.strip():
                continue
            if mission_name not in ALL_MISSIONS:
                continue
            if not (isinstance(event, str) and event.strip()):
                continue
            if event != event.strip():
                continue
            if _KEBAB_PATTERN.match(event) is None:
                continue
            detail = payload.get("detail")
            if detail is not None:
                if not isinstance(detail, str):
                    continue
                if detail != detail.strip():
                    continue
            break
        else:
            msg = (
                "Action-log artifact did not contain a schema-valid JSON line: "
                "expected at least one JSON object line with non-empty "
                "ISO-8601 ts, known mission_name, and normalized kebab-case event; "
                f"ref='{ref}', path='{path}'"
            )
            raise ValidationError(msg)


def validate_action_log_artifacts_contain_ref_events(
    *, evidence_refs: tuple[str, ...], run_root: Path, expected_mission_name: str
) -> None:
    """Validate each action-log ref has a line with matching event+mission."""

    run_root = _require_run_root_dir(run_root=run_root)

    if not isinstance(expected_mission_name, str):
        msg = "expected_mission_name must be a string"
        raise ValidationError(msg)
    if not expected_mission_name:
        msg = "expected_mission_name must be non-empty"
        raise ValidationError(msg)
    if not expected_mission_name.strip():
        msg = "expected_mission_name must not be whitespace-only"
        raise ValidationError(msg)
    if expected_mission_name != expected_mission_name.strip():
        msg = "expected_mission_name must not have leading or trailing whitespace"
        raise ValidationError(msg)
    if expected_mission_name not in ALL_MISSIONS:
        msg = f"expected_mission_name is not a known mission: '{expected_mission_name}'"
        raise ValidationError(msg)

    for ref in evidence_refs:
        try:
            kind, key = parse_released_evidence_ref(ref)
        except (TypeError, ValueError) as exc:
            msg = f"Invalid evidence ref while matching action-log events: ref='{ref}'"
            raise ValidationError(msg) from exc
        if kind != "action-log":
            continue
        path = action_log_artifact_path(run_root=run_root, key=key)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            msg = (
                "Failed to read action-log artifact while matching event: "
                f"ref='{ref}', path='{path}'"
            )
            raise ValidationError(msg) from exc

        found = False
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            ts = payload.get("ts")
            if not (isinstance(ts, str) and _is_iso8601_timestamp(ts)):
                continue
            mission_name = payload.get("mission_name")
            if mission_name != expected_mission_name:
                continue
            event = payload.get("event")
            if event != key:
                continue
            found = True
            break

        if not found:
            msg = (
                "Action-log artifact did not contain a matching event for evidence ref:"
                f"ref='{ref}', expected_event='{key}', "
                f"expected_mission_name='{expected_mission_name}', "
                f"path='{path}'"
            )
            raise ValidationError(msg)


def validate_release_ceiling_stop_action_log(
    *, evidence_refs: tuple[str, ...], run_root: Path
) -> None:
    """Validate the released ceiling stop marker is confirmed by action-log content."""

    if "evidence://action-log/release-ceiling-stop" not in evidence_refs:
        return

    run_root = _require_run_root_dir(run_root=run_root)

    path = action_log_artifact_path(run_root=run_root, key="release-ceiling-stop")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        msg = (
            f"Failed to read release-ceiling-stop action-log artifact: path='{path}'; "
            "expected typed fields event/mission_name/ts"
        )
        raise ValidationError(msg) from exc

    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("event") != "release-ceiling-stop":
            continue
        if payload.get("mission_name") != "run_completion":
            continue
        ts = payload.get("ts")
        if isinstance(ts, str) and _is_iso8601_timestamp(ts):
            return

    msg = (
        "Release-ceiling-stop action-log artifact did not contain a confirming event: "
        "expected at least one JSON line with "
        "event='release-ceiling-stop', mission_name='run_completion', and "
        "ISO-8601 ts; "
        f"path='{path}'"
    )
    raise ValidationError(msg)


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
