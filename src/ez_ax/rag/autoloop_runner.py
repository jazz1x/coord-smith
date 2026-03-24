"""Executable low-attention autoloop runner built on top of Codex CLI."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ez_ax.rag.autoloop_prompt_driver import (
    AutoloopPromptPlan,
    build_autoloop_prompt_plan,
)

DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
DEFAULT_MAX_CYCLES = 25
DEFAULT_OUTPUT_DIR = Path("artifacts/autoloop")


@dataclass(frozen=True, slots=True)
class AutoloopRunSettings:
    codex_bin: str
    project_root: Path
    model: str
    sandbox: str
    max_cycles: int
    output_dir: Path
    dry_run: bool


def build_codex_exec_args(
    *,
    settings: AutoloopRunSettings,
    last_message_path: Path,
) -> tuple[str, ...]:
    return (
        settings.codex_bin,
        "exec",
        "-C",
        str(settings.project_root),
        "-m",
        settings.model,
        "-s",
        settings.sandbox,
        "--color",
        "never",
        "-o",
        str(last_message_path),
        "-",
    )


def build_last_message_path(*, output_dir: Path, cycle_index: int) -> Path:
    return output_dir / f"cycle-{cycle_index:02d}-last-message.md"


def should_stop_after_cycle(*, plan: AutoloopPromptPlan) -> bool:
    return plan.mode == "final_stop_review"


def run_autoloop(*, settings: AutoloopRunSettings) -> int:
    if shutil.which(settings.codex_bin) is None:
        raise FileNotFoundError(f"codex executable not found: {settings.codex_bin}")

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
        command = build_codex_exec_args(
            settings=settings,
            last_message_path=last_message_path,
        )
        print(f"[cycle {cycle_index}] mode={plan.mode}")
        print(f"[cycle {cycle_index}] next_action={plan.next_action}")
        print(f"[cycle {cycle_index}] last_message={last_message_path}")
        if settings.dry_run:
            print(" ".join(command))
        else:
            completed = subprocess.run(
                command,
                input=plan.prompt,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                return completed.returncode

        if should_stop_after_cycle(plan=plan):
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
        description="Run the low-attention autoloop via Codex CLI."
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_CODEX_MODEL,
        help="Codex model to use for each non-interactive cycle.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex executable to invoke.",
    )
    parser.add_argument(
        "--sandbox",
        default="workspace-write",
        help="Codex sandbox mode for exec cycles.",
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
        help="Print the Codex exec command instead of invoking it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = AutoloopRunSettings(
        codex_bin=args.codex_bin,
        project_root=Path.cwd(),
        model=args.model,
        sandbox=args.sandbox,
        max_cycles=args.max_cycles,
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    return run_autoloop(settings=settings)


if __name__ == "__main__":
    raise SystemExit(main())
