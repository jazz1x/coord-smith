"""Executable low-attention autoloop runner built on top of Claude Code CLI.

The runner delegates code-writing to the ``claude`` binary (Claude Code:
https://docs.anthropic.com/en/docs/claude-code).  Install it globally and
ensure it is on PATH before invoking this module.  Use ``--dry-run`` to
preview prompts without requiring the binary.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import (
    AutoloopPromptPlan,
    build_autoloop_prompt_plan,
)

DEFAULT_CLAUDE_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_CYCLES = 25
DEFAULT_OUTPUT_DIR = Path("artifacts/autoloop")


@dataclass(frozen=True, slots=True)
class AutoloopRunSettings:
    claude_bin: str
    project_root: Path
    model: str
    max_cycles: int
    output_dir: Path
    dry_run: bool


def build_claude_exec_args(
    *,
    settings: AutoloopRunSettings,
) -> tuple[str, ...]:
    return (
        settings.claude_bin,
        "--print",
        "--model",
        settings.model,
        "--permission-mode",
        "bypassPermissions",
    )


def build_last_message_path(*, output_dir: Path, cycle_index: int) -> Path:
    return output_dir / f"cycle-{cycle_index:02d}-last-message.md"


def build_validation_commands(*, project_root: Path) -> tuple[tuple[str, ...], ...]:
    """Return the deterministic validation commands run before each claude cycle."""
    python_exe = sys.executable
    return (
        (python_exe, "-m", "pytest", "tests/unit/", "-q"),
        (python_exe, "-m", "mypy", "src/ez_ax/"),
        (python_exe, "-m", "ruff", "check", "src/ez_ax/"),
    )


def _requires_e2e_validation(*, next_action: str) -> bool:
    lowered = next_action.lower()
    return "e2e" in lowered or "real-environment" in lowered


def build_cycle_validation_commands(
    *, project_root: Path, next_action: str
) -> tuple[tuple[str, ...], ...]:
    base_commands = list(build_validation_commands(project_root=project_root))
    if _requires_e2e_validation(next_action=next_action):
        python_exe = sys.executable
        base_commands.insert(1, (python_exe, "-m", "pytest", "tests/e2e/", "-q"))
    return tuple(base_commands)


def run_validation_gate(*, project_root: Path, next_action: str) -> int:
    """Run pytest, mypy, ruff directly; return 0 if all clean, else first nonzero."""
    for command in build_cycle_validation_commands(
        project_root=project_root,
        next_action=next_action,
    ):
        result = subprocess.run(command, cwd=str(project_root), check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


def should_stop_after_cycle(
    *, plan: AutoloopPromptPlan, project_root: Path
) -> bool:
    """Return True if the phase is complete and auto_seed should be called.

    Checks both the pre-cycle plan mode and the on-disk next_action after
    Claude has run.  This catches the common pattern where Claude declares
    FINAL_STOP during an implementation cycle (writing 'FINAL_STOP — …' to
    work-rag) without the runner ever entering final_stop_review mode.
    """
    if plan.mode == "final_stop_review":
        return True
    work_rag_path = project_root / "docs/product/work-rag.json"
    try:
        payload = json.loads(work_rag_path.read_text(encoding="utf-8"))
        next_action: object = payload.get("current", {}).get("next_action", "")
        return isinstance(next_action, str) and next_action.startswith("FINAL_STOP")
    except Exception:
        return False


def _next_phase_name(current_phase: str) -> str | None:
    """Return 'Phase R(N+1)' given 'Phase RN — ...' or None if unparseable."""
    match = re.search(r"Phase R(\d+)", current_phase)
    if not match:
        return None
    return f"Phase R{int(match.group(1)) + 1}"


def auto_seed_next_phase(*, project_root: Path) -> bool:
    """Add next-phase definition family to coverage ledger when phase completes.

    Reads active_phase from coverage-ledger.json, derives the next phase
    number, appends a pending family, and updates work-rag next_action.
    Returns True if a new family was seeded, False if already present or
    the phase name could not be parsed.
    """
    ledger_path = project_root / "docs/llm/low-attention-coverage-ledger.json"
    work_rag_path = project_root / "docs/product/work-rag.json"
    execution_contract_path = (
        project_root / "docs/llm/low-attention-execution-contract.json"
    )

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    # Advance active_phase to match the highest-numbered phase already in families.
    # Claude sometimes adds families without updating active_phase, which causes the
    # idempotency check to block seeding of the next phase after it.
    highest_phase = ledger.get("active_phase", "")
    for fam in ledger["families"]:
        m = re.search(r"Phase R(\d+)", fam["family"])
        if m:
            candidate = f"Phase R{m.group(1)}"
            hm = re.search(r"Phase R(\d+)", highest_phase)
            if not hm or int(m.group(1)) > int(hm.group(1)):
                highest_phase = candidate

    current_phase = highest_phase
    next_phase = _next_phase_name(current_phase)
    if next_phase is None:
        return False

    family_name = f"{next_phase} heuristic gap scan"
    if any(f["family"] == family_name for f in ledger["families"]):
        return False  # already seeded

    phase_num = re.sub(r"[^0-9]", "", next_phase)
    next_anchor = f"r{phase_num}HeuristicScanBound"
    next_milestone = (
        f"{next_phase} first PRD-backed uncovered clause implemented and tested"
    )

    # Advance active_phase immediately so subsequent seedings increment correctly
    ledger["active_phase"] = f"{next_phase} — heuristic scan"
    ledger["active_milestone"] = next_milestone
    ledger["active_anchor"] = next_anchor

    ledger["families"].append(
        {
            "family": family_name,
            "status": "pending",
            "evidence_or_reason": (
                f"{current_phase} complete; {next_phase} heuristic scan needed."
            ),
            "next_slice_hint": (
                "Read docs/prd.md and list all released-scope implementation "
                "clauses (below runCompletion). Cross-reference with "
                "tests/unit/ to find the first clause that has no dedicated "
                "unit test. Write one focused pytest function for it, run "
                "pytest to confirm it passes, mark this family covered in "
                "docs/llm/low-attention-coverage-ledger.json, update "
                "docs/product/work-rag.json current.next_action to the next "
                f"pending family (or 'FINAL_STOP — {next_phase} complete' if "
                "none remain), and commit."
            ),
            "first_validation": "python -m pytest tests/unit/ -q",
            "mypy_target": "src/",
            "ruff_target": "src/",
            "done_when": [
                "at least one new pytest function added for an uncovered PRD clause",
                "pytest tests/unit/ -q passes",
                f"coverage-ledger.json '{family_name}' status set to covered",
                "work-rag.json next_action updated",
                "committed",
            ],
            "template_id": "",
        }
    )
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Keep execution-contract.json consistent so the prompt driver sees the new phase
    if execution_contract_path.exists():
        contract = json.loads(
            execution_contract_path.read_text(encoding="utf-8")
        )
        contract["active_phase"] = f"{next_phase} — heuristic scan"
        contract["active_milestone"] = next_milestone
        contract["active_anchor"] = next_anchor
        contract["anchor_contract_families"] = [family_name]
        execution_contract_path.write_text(
            json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    work_rag = json.loads(work_rag_path.read_text(encoding="utf-8"))
    work_rag["current"]["next_action"] = family_name
    work_rag_path.write_text(
        json.dumps(work_rag, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Update current-state.md so Claude does not read stale FINAL_STOP context
    current_state_path = project_root / "docs/current-state.md"
    if current_state_path.exists():
        content = current_state_path.read_text(encoding="utf-8")
        content = re.sub(
            r"(## Current Interpretation\n).*?(\n## )",
            (
                f"\\1\n{current_phase} complete. Phase transition in progress: "
                f"`{family_name}` is the active task.\n"
                "\\2"
            ),
            content,
            flags=re.DOTALL,
        )
        content = re.sub(
            r"The current next action is:.*",
            f"The current next action is: `{family_name}`",
            content,
        )
        current_state_path.write_text(content, encoding="utf-8")

    return True


def run_autoloop(*, settings: AutoloopRunSettings) -> int:
    if shutil.which(settings.claude_bin) is None:
        raise FileNotFoundError(f"claude executable not found: {settings.claude_bin}")

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    previous_signature: tuple[str, str] | None = None
    cycle_index = 1

    while settings.max_cycles == 0 or cycle_index <= settings.max_cycles:
        plan = build_autoloop_prompt_plan()
        signature = (plan.mode, plan.next_action)
        if previous_signature == signature and plan.mode != "final_stop_review":
            print(
                "autoloop halted: next prompt plan repeated without progress; "
                "inspect the last cycle output before rerunning.",
                file=sys.stderr,
            )
            return 2

        last_message_path = build_last_message_path(
            output_dir=settings.output_dir,
            cycle_index=cycle_index,
        )
        command = build_claude_exec_args(settings=settings)
        print(f"[cycle {cycle_index}] mode={plan.mode}")
        print(f"[cycle {cycle_index}] next_action={plan.next_action}")
        print(f"[cycle {cycle_index}] last_message={last_message_path}")
        if not settings.dry_run:
            gate_rc = run_validation_gate(
                project_root=settings.project_root,
                next_action=plan.next_action,
            )
            if gate_rc != 0:
                print(
                    f"[cycle {cycle_index}] validation gate failed; "
                    "fix errors before next claude cycle.",
                    file=sys.stderr,
                )
                return gate_rc
        if settings.dry_run:
            print(" ".join(command))
            print(f"[cycle {cycle_index}] prompt={plan.prompt}", file=sys.stderr)
        else:
            completed = subprocess.run(
                command,
                input=plan.prompt,
                text=True,
                capture_output=True,
                check=False,
                cwd=str(settings.project_root),
            )
            last_message_path.write_text(completed.stdout)
            print(completed.stdout, end="")
            if completed.returncode != 0:
                return completed.returncode

        if should_stop_after_cycle(plan=plan, project_root=settings.project_root):
            print(
                f"[cycle {cycle_index}] FINAL_STOP honored; halting autoloop.",
                file=sys.stderr,
            )
            return 0

        previous_signature = signature
        cycle_index += 1

    print(
        "autoloop paused: configured max cycles reached before final stop review.",
        file=sys.stderr,
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the low-attention autoloop via Claude Code CLI."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_CLAUDE_MODEL,
        help="Claude model to use for each non-interactive cycle.",
    )
    parser.add_argument(
        "--claude-bin",
        default="claude",
        help="Claude Code executable to invoke.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=DEFAULT_MAX_CYCLES,
        help="Maximum number of cycles to run. Use 0 for no fixed limit.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where per-cycle last-message files are stored.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Claude exec command instead of invoking it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = AutoloopRunSettings(
        claude_bin=args.claude_bin,
        project_root=Path.cwd(),
        model=args.model,
        max_cycles=args.max_cycles,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    return run_autoloop(settings=settings)


if __name__ == "__main__":
    raise SystemExit(main())
