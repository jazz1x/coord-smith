"""Structured low-attention slice templates for deterministic continuation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

SLICE_TEMPLATE_PATH = Path("docs/llm/low-attention-slice-templates.json")


@dataclass(frozen=True, slots=True)
class LowAttentionSliceTemplate:
    id: str
    family: str
    trigger_substrings: tuple[str, ...]
    file_group: str
    supporting_files: tuple[str, ...]
    tests: tuple[str, ...]
    first_prd: str
    first_validation: str
    mypy_target: str
    ruff_target: str
    done_when: tuple[str, ...]
    next_if_clean: str
    next_if_fail: str


def load_slice_templates(
    *, template_path: Path = SLICE_TEMPLATE_PATH
) -> tuple[LowAttentionSliceTemplate, ...]:
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list):
        raise ValueError("slice template registry must contain a templates list")

    normalized: list[LowAttentionSliceTemplate] = []
    for template in templates:
        if not isinstance(template, dict):
            raise ValueError("slice template entries must be objects")
        normalized.append(
            LowAttentionSliceTemplate(
                id=_require_str(template, "id"),
                family=_require_str(template, "family"),
                trigger_substrings=_require_str_tuple(template, "trigger_substrings"),
                file_group=_require_str(template, "file_group"),
                supporting_files=_require_str_tuple(template, "supporting_files"),
                tests=_require_str_tuple(template, "tests"),
                first_prd=_require_str(template, "first_prd"),
                first_validation=_require_str(template, "first_validation"),
                mypy_target=_require_str(template, "mypy_target"),
                ruff_target=_require_str(template, "ruff_target"),
                done_when=_require_str_tuple(template, "done_when"),
                next_if_clean=_require_str(template, "next_if_clean"),
                next_if_fail=_require_str(template, "next_if_fail"),
            )
        )
    return tuple(normalized)


def match_slice_template(
    *, next_action: str, template_path: Path = SLICE_TEMPLATE_PATH
) -> LowAttentionSliceTemplate | None:
    lowered = next_action.casefold()
    for template in load_slice_templates(template_path=template_path):
        matched = any(
            trigger.casefold() in lowered for trigger in template.trigger_substrings
        )
        if matched:
            return template
    return None


def _require_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"slice template '{key}' must be a non-empty string")
    return value


def _require_str_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"slice template '{key}' must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"slice template '{key}' entries must be non-empty strings")
    return tuple(value)
