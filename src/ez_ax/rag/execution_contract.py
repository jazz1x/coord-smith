"""Machine-readable execution-contract helpers for low-attention continuation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

EXECUTION_CONTRACT_PATH = Path("docs/llm/low-attention-execution-contract.json")


@dataclass(frozen=True, slots=True)
class LowAttentionExecutionContract:
    active_phase: str
    active_milestone: str
    active_anchor: str
    active_invariant: str
    scope_ceiling: str
    canonical_inputs: tuple[str, ...]
    anchor_contract_families: tuple[str, ...]
    heuristic_family_ladder: tuple[str, ...]
    seeded_slice_requirements: tuple[str, ...]
    final_stop_requirements: tuple[str, ...]


def load_execution_contract(
    *, contract_path: Path = EXECUTION_CONTRACT_PATH
) -> LowAttentionExecutionContract:
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
    return LowAttentionExecutionContract(
        active_phase=_require_str(payload, "active_phase"),
        active_milestone=_require_str(payload, "active_milestone"),
        active_anchor=_require_str(payload, "active_anchor"),
        active_invariant=_require_str(payload, "active_invariant"),
        scope_ceiling=_require_str(payload, "scope_ceiling"),
        canonical_inputs=_require_str_tuple(payload, "canonical_inputs"),
        anchor_contract_families=_require_str_tuple(
            payload,
            "anchor_contract_families",
        ),
        heuristic_family_ladder=_require_str_tuple(payload, "heuristic_family_ladder"),
        seeded_slice_requirements=_require_str_tuple(
            payload,
            "seeded_slice_requirements",
        ),
        final_stop_requirements=_require_str_tuple(
            payload,
            "final_stop_requirements",
        ),
    )


def _require_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"execution contract '{key}' must be a non-empty string")
    return value


def _require_str_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"execution contract '{key}' must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(
            f"execution contract '{key}' entries must be non-empty strings"
        )
    return tuple(value)
