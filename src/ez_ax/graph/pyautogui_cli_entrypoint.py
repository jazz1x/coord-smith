"""CLI entrypoint that wires PyAutoGUIAdapter to the released-scope execution graph."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.graph.released_cli_shim import run_released_scope_from_argv_env
from ez_ax.models.errors import ExecutionTransportError

_DEFAULT_RUN_ROOT = Path("artifacts/run")


async def _run(
    *,
    argv: Sequence[str] | None = None,
    run_root: Path = _DEFAULT_RUN_ROOT,
) -> int:
    """Instantiate PyAutoGUIAdapter, preflight OS permissions, then run the graph."""
    adapter = PyAutoGUIAdapter(run_root=run_root)
    adapter.preflight()
    await run_released_scope_from_argv_env(adapter=adapter, argv=list(argv or []))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(_run(argv=argv))
    except ExecutionTransportError as exc:
        print(
            f"ez-ax: preflight failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        print(
            "ez-ax: grant macOS Accessibility + Screen Recording permission to "
            "the host terminal app and retry.",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ez-ax: fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
