"""Prompt helpers for chaining low-attention autonomous runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ez_ax.rag.coverage_ledger import COVERAGE_LEDGER_PATH, first_pending_family
from ez_ax.rag.paths import WORK_RAG_PATH
from ez_ax.rag.slice_templates import get_slice_template_by_id, match_slice_template


@dataclass(frozen=True, slots=True)
class AutoloopPromptPlan:
    mode: str
    next_action: str
    prompt: str


def _load_next_action(*, work_rag_path: Path) -> str:
    payload = json.loads(work_rag_path.read_text(encoding="utf-8"))
    current = payload.get("current")
    if not isinstance(current, dict):
        raise ValueError("work-rag current block must be an object")

    next_action = current.get("next_action")
    if not isinstance(next_action, str):
        raise ValueError("work-rag current.next_action must be a string")
    if not next_action.strip():
        raise ValueError("work-rag current.next_action must be non-empty")
    return next_action


def _implementation_prompt(*, next_action: str) -> str:
    template = match_slice_template(next_action=next_action)
    if template is not None:
        return (
            "Use $ez-ax-low-attention-autoloop. Read AGENTS.md, docs/prd.md, "
            "docs/execution-model.md, docs/current-state.md, "
            "docs/product/work-rag.json, docs/product/rag.json, "
            "docs/llm/repo-autonomous-loop-adapter.yaml, and "
            "docs/llm/low-attention-slice-templates.json in order. Quote the "
            "exact on-disk docs/product/work-rag.json current.next_action "
            "verbatim. Then execute the matched deterministic slice template "
            f"`{template.id}` for family `{template.family}`. Primary file "
            f"group: {template.file_group}. Supporting files: "
            f"{', '.join(template.supporting_files)}. First PRD: "
            f"{template.first_prd}. Validation sequence: "
            f"{template.first_validation}; {template.mypy_target}; "
            f"{template.ruff_target}. Done when: "
            f"{'; '.join(template.done_when)}. next_if_clean: "
            f"{template.next_if_clean}. next_if_fail: {template.next_if_fail}. "
            f"Current next_action: {next_action}"
        )
    return (
        "Use $ez-ax-low-attention-autoloop. Read AGENTS.md, docs/prd.md, "
        "docs/execution-model.md, docs/current-state.md, "
        "docs/product/work-rag.json, docs/product/rag.json, and "
        "docs/llm/repo-autonomous-loop-adapter.yaml in order. Quote the exact "
        "on-disk docs/product/work-rag.json current.next_action verbatim. "
        "It currently names a concrete slice, so execute that slice and keep "
        "looping across consecutive one-commit tasks in the same session. "
        f"Current next_action: {next_action}"
    )


def _template_prompt(
    *,
    template_id: str,
    next_action: str,
    family: str | None = None,
) -> str:
    template = get_slice_template_by_id(template_id=template_id)
    if template is None:
        raise ValueError(f"unknown slice template id: {template_id}")
    resolved_family = family or template.family
    return (
        "Use $ez-ax-low-attention-autoloop. Read AGENTS.md, docs/prd.md, "
        "docs/execution-model.md, docs/current-state.md, "
        "docs/product/work-rag.json, docs/product/rag.json, "
        "docs/llm/repo-autonomous-loop-adapter.yaml, "
        "docs/llm/low-attention-coverage-ledger.json, and "
        "docs/llm/low-attention-slice-templates.json in order. Quote the "
        "exact on-disk docs/product/work-rag.json current.next_action "
        "verbatim. Then treat docs/llm/low-attention-coverage-ledger.json as "
        "the machine-readable source of truth for the active pending family "
        f"and execute template `{template.id}` for family `{resolved_family}`. "
        f"Primary file group: {template.file_group}. Supporting files: "
        f"{', '.join(template.supporting_files)}. First PRD: "
        f"{template.first_prd}. Validation sequence: "
        f"{template.first_validation}; {template.mypy_target}; "
        f"{template.ruff_target}. Done when: {'; '.join(template.done_when)}. "
        f"next_if_clean: {template.next_if_clean}. next_if_fail: "
        f"{template.next_if_fail}. Current next_action: {next_action}"
    )


def _continuation_seed_prompt(*, next_action: str) -> str:
    return (
        "Use $ez-ax-low-attention-autoloop. The current cycle is in "
        "continuation-seeding mode, not terminal stop mode. First execute the "
        "current next_action exactly as written. Then, if needed, run the "
        "documented stop-state consistency gate across docs/current-state.md, "
        "docs/product/work-rag.json, "
        "docs/product/prd-low-attention-implementation-queue.md, and "
        "docs/llm/repo-autonomous-loop-adapter.yaml, including the bounded "
        "adjacent-surface completion check. Produce exactly one one-commit-safe "
        "seeded slice: either add one explicit PRD-backed queue item for an "
        "omitted in-bounds surface, or add one docs-sufficiency improvement "
        "that makes the next lower-capacity implementation slice "
        "deterministically nameable from the canonical sources. Update "
        "docs/current-state.md, "
        "docs/product/prd-low-attention-implementation-queue.md, "
        "docs/llm/repo-autonomous-loop-adapter.yaml, docs/product/work-rag.json, "
        "and docs/product/rag.json only as needed by that one slice, then "
        "commit once. Current next_action: "
        f"{next_action}"
    )


def _final_stop_review_prompt(*, next_action: str) -> str:
    return (
        "Use $ez-ax-low-attention-autoloop. Read AGENTS.md, docs/prd.md, "
        "docs/execution-model.md, docs/current-state.md, "
        "docs/product/work-rag.json, docs/product/rag.json, "
        "docs/llm/repo-autonomous-loop-adapter.yaml, "
        "and docs/llm/low-attention-coverage-ledger.json in order. Quote the "
        "exact on-disk docs/product/work-rag.json current.next_action verbatim. "
        "The machine-readable coverage ledger has no pending family, so do not "
        "run generic continuation seeding. Instead, run the documented "
        "stop-state consistency gate and honor FINAL_STOP only if no exact "
        "in-bounds slice is reopened by canonical sources. Current next_action: "
        f"{next_action}"
    )


def build_autoloop_prompt_plan(
    *,
    work_rag_path: Path = WORK_RAG_PATH,
    coverage_ledger_path: Path = COVERAGE_LEDGER_PATH,
) -> AutoloopPromptPlan:
    next_action = _load_next_action(work_rag_path=work_rag_path)
    pending_family = first_pending_family(ledger_path=coverage_ledger_path)
    if pending_family is not None and pending_family.template_id:
        return AutoloopPromptPlan(
            mode="implementation",
            next_action=next_action,
            prompt=_template_prompt(
                template_id=pending_family.template_id,
                next_action=next_action,
                family=pending_family.family,
            ),
        )

    if next_action.startswith("FINAL_STOP"):
        return AutoloopPromptPlan(
            mode="final_stop_review",
            next_action=next_action,
            prompt=_final_stop_review_prompt(next_action=next_action),
        )

    if "continuation-seeding pass" in next_action:
        return AutoloopPromptPlan(
            mode="continuation_seed",
            next_action=next_action,
            prompt=_continuation_seed_prompt(next_action=next_action),
        )

    return AutoloopPromptPlan(
        mode="implementation",
        next_action=next_action,
        prompt=_implementation_prompt(next_action=next_action),
    )
