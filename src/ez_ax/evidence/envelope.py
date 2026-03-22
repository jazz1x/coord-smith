"""Evidence envelope model for comparable artifacts."""

import re
from dataclasses import dataclass
from typing import Literal

EvidenceKind = Literal["dom", "text", "clock", "action-log", "screenshot", "coordinate"]

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

    kind = match.group("kind")
    key = match.group("key")
    return kind, key  # type: ignore[return-value]
