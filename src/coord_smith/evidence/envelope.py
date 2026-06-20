"""Released-scope evidence ref parsing + priority-gate enforcement.

The runtime evidence contract is the raw ``evidence://{kind}/{key}`` ref string
(produced by the adapter, consumed by the graph's priority gate). This module
owns parsing those refs and enforcing the truth hierarchy
``dom > text > clock > action-log > screenshot > coordinate``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from coord_smith.adapters.execution.client import ExecutionResult

EvidenceKind = Literal["dom", "text", "clock", "action-log", "screenshot", "coordinate"]
EVIDENCE_PRIORITY_ORDER: tuple[EvidenceKind, ...] = (
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
    from coord_smith.models.errors import FlowError

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
