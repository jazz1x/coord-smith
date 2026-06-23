"""Transport contracts: dataclasses, Protocols, and JSON serialization helper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from coord_smith.evidence.envelope import parse_released_evidence_ref
from coord_smith.models.errors import ValidationError
from coord_smith.models.identifiers import MissionName


def _payload_json_default(value: object) -> Any:
    """``json.dumps`` ``default=`` callback that knows how to serialize
    Pydantic models inside an ``ExecutionRequest`` payload.

    The in-process producer (``released_call_site.py``) passes Step
    instances directly to avoid an eager ``model_dump → dict →
    model_validate`` round-trip on the consumer side (the adapter).
    The transport-neutral JSON-serializability contract is still
    honoured: a future external transport can ``json.dumps`` the
    payload using this default, getting the same shape it would
    have got from ``step.model_dump(mode="json")``.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(
        f"object of type {type(value).__name__!r} is not JSON-serializable "
        "inside an ExecutionRequest payload"
    )


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Typed execution request passed to OpenClaw."""

    mission_name: MissionName
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Typed execution result returned by OpenClaw."""

    mission_name: MissionName
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

    async def preflight(self) -> None:
        """Validate that the runtime can execute (permissions, environment)."""
        ...


class ExecutionAdapter(ExecutionBoundary, Protocol):
    """Canonical alias for the injected OpenClaw execution boundary."""
