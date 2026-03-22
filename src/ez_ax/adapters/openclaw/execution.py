"""Released-scope OpenClaw execution wrapper for deterministic boundary validation."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from ez_ax.adapters.openclaw.client import (
    OpenClawAdapter,
    OpenClawExecutionResult,
    build_openclaw_execution_request_within_scope,
    validate_openclaw_execution_roundtrip_within_scope,
)
from ez_ax.evidence.envelope import parse_released_evidence_ref
from ez_ax.missions.names import ALL_MISSIONS
from ez_ax.models.errors import AppError, ExecutionTransportError, ValidationError

_KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _require_run_root_dir(*, run_root: object) -> Path:
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


def _is_iso8601_timestamp(value: str) -> bool:
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
            f"Failed to read release ceiling stop action-log artifact: path='{path}'; "
            "expected typed fields event/mission_name/ts; "
            "see docs/product/prd-openclaw-e2e-validation.md, "
            "docs/product/prd-openclaw-computer-use-runtime.md, "
            "docs/product/prd-openclaw-evidence-model.md, and "
            "docs/product/prd-python-validation-contract.md"
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
        if payload.get("mission_name") != "page_ready_observation":
            continue
        ts = payload.get("ts")
        if isinstance(ts, str) and _is_iso8601_timestamp(ts):
            return

    msg = (
        "Release ceiling stop action-log artifact did not contain a confirming event: "
        "expected at least one JSON line with "
        "event='release-ceiling-stop', mission_name='page_ready_observation', and "
        "ISO-8601 ts; "
        f"path='{path}'; "
        "see docs/product/prd-openclaw-e2e-validation.md, "
        "docs/product/prd-openclaw-computer-use-runtime.md, "
        "docs/product/prd-openclaw-evidence-model.md, and "
        "docs/product/prd-python-validation-contract.md"
    )
    raise ValidationError(msg)


async def execute_openclaw_within_scope(
    *,
    adapter: OpenClawAdapter,
    mission_name: str,
    payload: dict[str, object],
    approved_scope_ceiling: str,
    run_root: Path | None = None,
) -> OpenClawExecutionResult:
    """Execute OpenClaw with released-scope boundary validation.

    This wrapper hardens request/result contracts and optionally validates action-log
    artifacts under the provided run root.
    """

    try:
        request = build_openclaw_execution_request_within_scope(
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

    if not isinstance(candidate, OpenClawExecutionResult):
        msg = (
            "OpenClaw adapter returned an invalid result type: "
            f"expected OpenClawExecutionResult, got {type(candidate)!r}"
        )
        raise ValidationError(msg)

    result = candidate
    try:
        validate_openclaw_execution_roundtrip_within_scope(
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
