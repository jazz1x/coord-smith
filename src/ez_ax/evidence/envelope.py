"""Evidence envelope model for comparable artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from ez_ax.adapters.execution.client import ExecutionResult

EvidenceKind = Literal["dom", "text", "clock", "action-log", "screenshot", "coordinate"]
EvidencePriority = Literal[
    "dom", "text", "clock", "action-log", "screenshot", "coordinate"
]
EVIDENCE_PRIORITY_ORDER: tuple[EvidencePriority, ...] = (
    "dom",
    "text",
    "clock",
    "action-log",
    "screenshot",
    "coordinate",
)

EVIDENCE_REF_PATTERN = re.compile(
    r"^evidence://"
    r"(?P<kind>dom|text|clock|action-log|screenshot|coordinate)"
    r"/"
    r"(?P<key>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    """Normalized evidence item aligned to the hybrid evidence PRD."""

    kind: EvidenceKind
    ref: str
    primary: bool


def parse_released_evidence_ref(ref: str) -> tuple[EvidenceKind, str]:
    """Parse a released-scope evidence ref (`evidence://{kind}/{key}`) into kind+key."""

    if not isinstance(ref, str):
        msg = "Evidence ref must be a string"
        raise TypeError(msg)
    if not ref:
        msg = "Evidence ref must be non-empty"
        raise ValueError(msg)
    if not ref.strip():
        msg = "Evidence ref must not be whitespace-only"
        raise ValueError(msg)
    if ref != ref.strip():
        msg = "Evidence ref must not have leading or trailing whitespace"
        raise ValueError(msg)

    match = EVIDENCE_REF_PATTERN.match(ref)
    if match is None:
        msg = (
            "Evidence ref must match 'evidence://{kind}/{key}' released-scope schema: "
            f"got '{ref}'"
        )
        raise ValueError(msg)

    kind = cast(EvidenceKind, match.group("kind"))
    key = match.group("key")
    return kind, key


def load_action_log_artifact(
    artifact_path: str | Path,
) -> list[dict[str, object]]:
    """Load action-log JSONL artifact from disk and validate typed fields.

    Args:
        artifact_path: Path to .jsonl artifact (relative or absolute)

    Returns:
        List of parsed JSON objects from the artifact

    Raises:
        FileNotFoundError: If artifact does not exist
        ValueError: If artifact cannot be parsed or contains invalid JSON
        TypeError: If artifact_path is not a string or Path
    """
    if not isinstance(artifact_path, (str, Path)):
        msg = "artifact_path must be a string or Path"
        raise TypeError(msg)

    path = Path(artifact_path)
    if not path.exists():
        msg = f"Action-log artifact not found: {path}"
        raise FileNotFoundError(msg)

    if not path.is_file():
        msg = f"Action-log artifact path is not a file: {path}"
        raise ValueError(msg)

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        msg = f"Action-log artifact is not valid UTF-8: {path}"
        raise ValueError(msg) from exc

    lines = content.strip().split("\n")
    if not lines or not lines[0]:
        msg = f"Action-log artifact is empty: {path}"
        raise ValueError(msg)

    parsed_objects: list[dict[str, object]] = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                msg = (
                    f"Action-log artifact line {line_no} is not a JSON object: "
                    f"{path}:{line_no}"
                )
                raise ValueError(msg)
            parsed_objects.append(obj)
        except json.JSONDecodeError as exc:
            msg = (
                f"Action-log artifact contains invalid JSON at line {line_no}: "
                f"{path}:{line_no}"
            )
            raise ValueError(msg) from exc

    if not parsed_objects:
        msg = f"Action-log artifact contains no valid JSON objects: {path}"
        raise ValueError(msg)

    return parsed_objects


def enforce_evidence_priority(
    observed_refs: set[str],
) -> str:
    """Return the highest-priority evidence kind from observed refs.

    Enforces truth hierarchy: dom > text > clock > action-log > screenshot > coordinate

    Args:
        observed_refs: Set of evidence refs (e.g., {"evidence://dom/foo", ...})

    Returns:
        The highest-priority kind found in observed_refs

    Raises:
        ValueError: If observed_refs is empty or contains invalid refs
        TypeError: If observed_refs is not a set or set-like
    """
    if not observed_refs:
        msg = "observed_refs must be non-empty"
        raise ValueError(msg)

    observed_kinds: set[EvidenceKind] = set()
    for ref in observed_refs:
        try:
            kind, _ = parse_released_evidence_ref(ref)
            observed_kinds.add(kind)
        except (TypeError, ValueError) as exc:
            msg = f"Invalid evidence ref in observed_refs: {ref}"
            raise ValueError(msg) from exc

    for priority_kind in EVIDENCE_PRIORITY_ORDER:
        if priority_kind in observed_kinds:
            return priority_kind

    msg = "No valid evidence kind found in observed_refs"
    raise ValueError(msg)


_WEAK_EVIDENCE_KINDS: frozenset[EvidenceKind] = frozenset({"screenshot", "coordinate"})


def enforce_evidence_priority_gate(result: ExecutionResult) -> EvidenceKind:
    """Enforce evidence priority; reject results with only weak evidence.

    Raises:
        FlowError: If highest-priority kind is screenshot or coordinate
                   (action-log or higher is required).
    """
    from ez_ax.models.errors import FlowError

    if not result.evidence_refs:
        raise FlowError(
            f"Evidence priority gate failed for mission '{result.mission_name}': "
            "evidence_refs is empty"
        )

    try:
        refs = set(result.evidence_refs)
        top_kind = cast(EvidenceKind, enforce_evidence_priority(refs))
    except ValueError as exc:
        raise FlowError(
            f"Evidence priority gate failed for mission "
            f"'{result.mission_name}': {exc}"
        ) from exc

    if top_kind in _WEAK_EVIDENCE_KINDS:
        raise FlowError(
            f"Evidence priority gate failed for mission '{result.mission_name}': "
            f"highest evidence kind '{top_kind}' is insufficient "
            "(minimum required: action-log)"
        )

    return top_kind


def validate_release_ceiling_stop_proof(
    artifact_path: str | Path,
) -> None:
    """Validate that release-ceiling-stop artifact exists with required typed fields.

    The release-ceiling-stop proof must contain at least one JSON line with:
    - event: "release-ceiling-stop"
    - mission_name: "run_completion"
    - ts: ISO-8601 timestamp

    Args:
        artifact_path: Path to release-ceiling-stop.jsonl artifact

    Raises:
        FileNotFoundError: If artifact does not exist
        ValueError: If artifact lacks required fields or valid JSON lines
        TypeError: If artifact_path is not a string or Path
    """
    if not isinstance(artifact_path, (str, Path)):
        msg = "artifact_path must be a string or Path"
        raise TypeError(msg)

    path = Path(artifact_path)

    if not path.exists():
        msg = (
            f"Release-ceiling-stop artifact not found: {path}\n"
            f"Required artifact: artifacts/action-log/release-ceiling-stop.jsonl\n"
            f"Expected fields: event, mission_name, ts (ISO-8601)"
        )
        raise FileNotFoundError(msg)

    try:
        artifacts = load_action_log_artifact(path)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        msg = (
            f"Release-ceiling-stop artifact cannot be read or parsed: {path}\n"
            f"Expected typed fields: event, mission_name, ts (ISO-8601)"
        )
        raise ValueError(msg) from exc

    for artifact_dict in artifacts:
        if not isinstance(artifact_dict, dict):
            continue

        event = artifact_dict.get("event")
        mission = artifact_dict.get("mission_name")
        ts = artifact_dict.get("ts")

        if (
            event == "release-ceiling-stop"
            and mission == "run_completion"
            and isinstance(ts, str)
            and ts
        ):
            return

    msg = (
        f"Release-ceiling-stop artifact {path} missing required entry.\n"
        f"Expected at least one JSON line with:\n"
        f"  event: 'release-ceiling-stop'\n"
        f"  mission_name: 'run_completion'\n"
        f"  ts: ISO-8601 timestamp"
    )
    raise ValueError(msg)
