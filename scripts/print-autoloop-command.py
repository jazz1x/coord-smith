#!/usr/bin/env python3
"""Print the next low-attention autoloop prompt for the current repo state."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def main() -> int:
    from ez_ax.rag.autoloop_prompt_driver import build_autoloop_prompt_plan

    plan = build_autoloop_prompt_plan()
    print(f"mode: {plan.mode}")
    print(f"next_action: {plan.next_action}")
    print()
    print(plan.prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
