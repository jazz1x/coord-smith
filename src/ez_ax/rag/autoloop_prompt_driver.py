"""Prompt helpers for chaining low-attention autonomous runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ez_ax.rag.paths import WORK_RAG_PATH


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


def build_autoloop_prompt_plan(
    *, work_rag_path: Path = WORK_RAG_PATH
) -> AutoloopPromptPlan:
    next_action = _load_next_action(work_rag_path=work_rag_path)
    is_continuation_seed = (
        next_action.startswith("FINAL_STOP")
        or "continuation-seeding pass" in next_action
    )
    if is_continuation_seed:
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
