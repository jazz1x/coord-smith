"""Prompt helpers for chaining low-attention autonomous runs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from ez_ax.rag.coverage_ledger import COVERAGE_LEDGER_PATH, first_pending_family
from ez_ax.rag.execution_contract import (
    EXECUTION_CONTRACT_PATH,
    load_execution_contract,
)
from ez_ax.rag.paths import WORK_RAG_PATH
from ez_ax.rag.slice_templates import get_slice_template_by_id, match_slice_template

_HISTORY_COMPRESSION_THRESHOLD = 3


def _history_compression_warning(*, work_rag_path: Path) -> str:
    """Return a compression warning if work-rag history exceeds threshold."""
    payload = json.loads(work_rag_path.read_text(encoding="utf-8"))
    history = payload.get("history")
    if not isinstance(history, list):
        return ""
    count = len(history)
    if count <= _HISTORY_COMPRESSION_THRESHOLD:
        return ""
    return (
        f" COMPRESSION WARNING: work-rag.json history has {count} entries "
        f"(threshold is {_HISTORY_COMPRESSION_THRESHOLD}). Before starting "
        "implementation, compress the oldest same-scope checkpoints into one "
        "summary and keep only the latest 2 raw checkpoints, as required by "
        "docs/core-loop.md."
    )


@dataclass(frozen=True, slots=True)
class AutoloopPromptPlan:
    mode: str
    next_action: str
    prompt: str


def _canonical_input_summary(inputs: tuple[str, ...]) -> str:
    return ", ".join(inputs)


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
            "Read AGENTS.md, docs/prd.md, "
            "docs/core-loop.md, docs/current-state.md, "
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
        "Read AGENTS.md, docs/prd.md, "
        "docs/core-loop.md, docs/current-state.md, "
        "docs/product/work-rag.json, docs/product/rag.json, and "
        "docs/llm/repo-autonomous-loop-adapter.yaml in order. Quote the exact "
        "on-disk docs/product/work-rag.json current.next_action verbatim. "
        "It currently names a concrete slice, so execute that slice and keep "
        "looping across consecutive one-commit tasks in the same session. "
        f"Current next_action: {next_action}"
    )


def _implementation_prompt_with_pending_family(
    *, next_action: str, pending_family_name: str
) -> str:
    return (
        _implementation_prompt(next_action=next_action)
        + " The coverage ledger still has an active pending family "
        f"`{pending_family_name}`, but the concrete work-rag next_action is "
        "more specific than the family label. Complete the concrete "
        "work-rag slice first, then update the coverage ledger and next_action "
        "consistently in the same task close."
    )


def _template_prompt(
    *,
    template_id: str,
    next_action: str,
    family: str | None = None,
    canonical_inputs: tuple[str, ...],
    phase: str,
    milestone: str,
    anchor: str,
    invariant: str,
) -> str:
    template = get_slice_template_by_id(template_id=template_id)
    if template is None:
        raise ValueError(f"unknown slice template id: {template_id}")
    resolved_family = family or template.family
    return (
        "Read canonical inputs in this "
        f"exact order: {_canonical_input_summary(canonical_inputs)}. Restate "
        f"phase `{phase}`, milestone `{milestone}`, anchor `{anchor}`, and "
        f"invariant `{invariant}` before execution. Quote the "
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


def _continuation_seed_prompt(
    *,
    next_action: str,
    canonical_inputs: tuple[str, ...],
    phase: str,
    milestone: str,
    anchor: str,
    invariant: str,
) -> str:
    return (
        "Read canonical inputs in this "
        f"exact order: {_canonical_input_summary(canonical_inputs)}. Restate "
        f"phase `{phase}`, milestone `{milestone}`, anchor `{anchor}`, and "
        f"invariant `{invariant}` before execution. The current cycle is in "
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


def _final_stop_review_prompt(
    *,
    next_action: str,
    canonical_inputs: tuple[str, ...],
    phase: str,
    milestone: str,
    anchor: str,
    invariant: str,
    final_stop_requirements: tuple[str, ...],
) -> str:
    return (
        "Read canonical inputs in this "
        f"exact order: {_canonical_input_summary(canonical_inputs)}. Restate "
        f"phase `{phase}`, milestone `{milestone}`, anchor `{anchor}`, and "
        f"invariant `{invariant}` before execution. Quote the "
        "exact on-disk docs/product/work-rag.json current.next_action verbatim. "
        "The machine-readable coverage ledger has no pending family, so do not "
        "run generic continuation seeding. Instead, run the documented "
        "stop-state consistency gate and honor FINAL_STOP only if no exact "
        "in-bounds slice is reopened by canonical sources and all final-stop "
        f"requirements remain true: {'; '.join(final_stop_requirements)}. "
        "IMPORTANT: when updating docs/product/work-rag.json current.next_action, "
        "the value MUST start with exactly 'FINAL_STOP — ' (if declaring stop) "
        "or with the exact family name (if reopening work). "
        "Current next_action: "
        f"{next_action}"
    )


_PHASE_DEF_RE = re.compile(r"^Define (Phase R\d+) scope and anchor$")


def _pending_family_prompt(
    *,
    pending_family_name: str,
    next_slice_hint: str,
    next_action: str,
    canonical_inputs: tuple[str, ...],
    phase: str,
    milestone: str,
    anchor: str,
    invariant: str,
    first_validation: str,
    mypy_target: str,
    ruff_target: str,
    done_when: tuple[str, ...],
) -> str:
    """Prompt for a pending coverage-ledger family without a slice template."""
    inputs_summary = _canonical_input_summary(canonical_inputs)
    validation_parts = [v for v in [first_validation, mypy_target, ruff_target] if v]
    validation_seq = "; ".join(validation_parts)
    done_summary = "; ".join(done_when)

    phase_def_match = _PHASE_DEF_RE.match(pending_family_name)
    if phase_def_match:
        next_phase_label = phase_def_match.group(1)
        preamble = (
            f"PHASE TRANSITION TASK — DO NOT run the stop-state exhaustion protocol "
            f"and DO NOT output or write FINAL_STOP anywhere. "
            f"docs/current-state.md and other canonical sources currently show the "
            f"PRIOR COMPLETED PHASE's terminal state — that state is stale. "
            f"Your concrete task is to define {next_phase_label}: "
            f"(1) update docs/llm/low-attention-execution-contract.json with "
            f"{next_phase_label} active_phase, active_milestone, active_anchor, "
            f"and 2-4 anchor_contract_families; "
            f"(2) add those 2-4 concrete pending implementation families to "
            f"docs/llm/low-attention-coverage-ledger.json; "
            f"(3) mark `{pending_family_name}` as covered in coverage-ledger.json; "
            f"(4) set docs/product/work-rag.json current.next_action to the first "
            f"new {next_phase_label} family name; "
            f"(5) update docs/current-state.md to reflect the new phase; "
            f"(6) commit once. "
        )
    else:
        preamble = ""

    return (
        preamble
        + f"Read canonical inputs in this exact order: {inputs_summary}. "
        f"Also read docs/prd.md (especially System Boundary section). "
        f"Phase `{phase}`, milestone `{milestone}`, anchor `{anchor}`, "
        f"invariant `{invariant}`. "
        f"Pending family: `{pending_family_name}`. "
        f"Next slice hint: {next_slice_hint}. "
        + (f"Validation sequence: {validation_seq}. " if validation_seq else "")
        + (f"Done when: {done_summary}. " if done_summary else "")
        + f"After completing: in docs/llm/low-attention-coverage-ledger.json "
        f"find the entry whose `family` field equals "
        f"`{pending_family_name}` and set its `status` to `covered`. "
        f"In docs/product/work-rag.json set `current.next_action` to the "
        f"`next_slice_hint` of the first remaining entry with "
        f"`status: pending` in the coverage ledger, or to "
        f"`FINAL_STOP_REVIEW - queue exhausted` if none remain. "
        f"Then commit once. "
        f"Current next_action: {next_action}"
    )


def build_autoloop_prompt_plan(
    *,
    work_rag_path: Path = WORK_RAG_PATH,
    coverage_ledger_path: Path = COVERAGE_LEDGER_PATH,
    execution_contract_path: Path = EXECUTION_CONTRACT_PATH,
) -> AutoloopPromptPlan:
    contract = load_execution_contract(contract_path=execution_contract_path)
    next_action = _load_next_action(work_rag_path=work_rag_path)
    compression_suffix = _history_compression_warning(work_rag_path=work_rag_path)
    pending_family = first_pending_family(ledger_path=coverage_ledger_path)
    explicit_next_action = (
        not next_action.startswith("FINAL_STOP")
        and "continuation-seeding pass" not in next_action
        and "Seed the earliest pending family" not in next_action
        and pending_family is not None
        and not pending_family.template_id
        and next_action != pending_family.family
        and next_action != pending_family.next_slice_hint
    )

    if explicit_next_action:
        assert pending_family is not None
        return AutoloopPromptPlan(
            mode="implementation",
            next_action=next_action,
            prompt=_implementation_prompt_with_pending_family(
                next_action=next_action,
                pending_family_name=pending_family.family,
            )
            + compression_suffix,
        )

    if pending_family is not None and pending_family.template_id:
        return AutoloopPromptPlan(
            mode="implementation",
            next_action=next_action,
            prompt=_template_prompt(
                template_id=pending_family.template_id,
                next_action=next_action,
                family=pending_family.family,
                canonical_inputs=contract.canonical_inputs,
                phase=contract.active_phase,
                milestone=contract.active_milestone,
                anchor=contract.active_anchor,
                invariant=contract.active_invariant,
            )
            + compression_suffix,
        )

    if pending_family is not None:
        return AutoloopPromptPlan(
            mode="implementation",
            next_action=next_action,
            prompt=_pending_family_prompt(
                pending_family_name=pending_family.family,
                next_slice_hint=pending_family.next_slice_hint,
                next_action=next_action,
                canonical_inputs=contract.canonical_inputs,
                phase=contract.active_phase,
                milestone=contract.active_milestone,
                anchor=contract.active_anchor,
                invariant=contract.active_invariant,
                first_validation=pending_family.first_validation,
                mypy_target=pending_family.mypy_target,
                ruff_target=pending_family.ruff_target,
                done_when=pending_family.done_when,
            )
            + compression_suffix,
        )

    if next_action.startswith("FINAL_STOP"):
        return AutoloopPromptPlan(
            mode="final_stop_review",
            next_action=next_action,
            prompt=_final_stop_review_prompt(
                next_action=next_action,
                canonical_inputs=contract.canonical_inputs,
                phase=contract.active_phase,
                milestone=contract.active_milestone,
                anchor=contract.active_anchor,
                invariant=contract.active_invariant,
                final_stop_requirements=contract.final_stop_requirements,
            )
            + compression_suffix,
        )

    if "continuation-seeding pass" in next_action:
        return AutoloopPromptPlan(
            mode="continuation_seed",
            next_action=next_action,
            prompt=_continuation_seed_prompt(
                next_action=next_action,
                canonical_inputs=contract.canonical_inputs,
                phase=contract.active_phase,
                milestone=contract.active_milestone,
                anchor=contract.active_anchor,
                invariant=contract.active_invariant,
            )
            + compression_suffix,
        )

    return AutoloopPromptPlan(
        mode="implementation",
        next_action=next_action,
        prompt=_implementation_prompt(next_action=next_action) + compression_suffix,
    )
