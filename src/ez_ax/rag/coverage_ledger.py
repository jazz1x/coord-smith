"""Structured coverage-ledger helpers for low-attention continuation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

COVERAGE_LEDGER_PATH = Path("docs/llm/low-attention-coverage-ledger.json")
ALLOWED_COVERAGE_STATUS = {"covered", "excluded", "pending"}


@dataclass(frozen=True, slots=True)
class CoverageLedgerEntry:
    family: str
    status: str
    evidence_or_reason: str
    next_slice_hint: str
    template_id: str


def load_coverage_ledger(
    *, ledger_path: Path = COVERAGE_LEDGER_PATH
) -> tuple[CoverageLedgerEntry, ...]:
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    families = payload.get("families")
    if not isinstance(families, list):
        raise ValueError("coverage ledger must contain a families list")

    normalized: list[CoverageLedgerEntry] = []
    for family in families:
        if not isinstance(family, dict):
            raise ValueError("coverage ledger entries must be objects")
        status = _require_str(family, "status")
        if status not in ALLOWED_COVERAGE_STATUS:
            raise ValueError("coverage ledger status must be covered/excluded/pending")
        normalized.append(
            CoverageLedgerEntry(
                family=_require_str(family, "family"),
                status=status,
                evidence_or_reason=_require_str(family, "evidence_or_reason"),
                next_slice_hint=_require_str(family, "next_slice_hint"),
                template_id=_require_optional_str(family, "template_id"),
            )
        )
    return tuple(normalized)


def first_pending_family(
    *, ledger_path: Path = COVERAGE_LEDGER_PATH
) -> CoverageLedgerEntry | None:
    for family in load_coverage_ledger(ledger_path=ledger_path):
        if family.status == "pending":
            return family
    return None


def _require_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"coverage ledger '{key}' must be a non-empty string")
    return value


def _require_optional_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"coverage ledger '{key}' must be a string")
    return value
