"""CLI entrypoint that wires PyAutoGUIAdapter to the released-scope execution graph."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.config.click_recipe import ClickRecipe, load_click_recipe
from ez_ax.graph.released_cli_shim import run_released_scope_from_argv_env
from ez_ax.models.errors import ConfigError, ExecutionTransportError

_DEFAULT_RUN_ROOT = Path("artifacts/run")
ENV_CLICK_RECIPE = "EZAX_CLICK_RECIPE"


def _extract_click_recipe_arg(argv: Sequence[str]) -> tuple[Path | None, list[str]]:
    """Strip --click-recipe from argv and return (recipe_path, remaining argv)."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--click-recipe", dest="click_recipe", type=Path)
    namespace, remaining = parser.parse_known_args(list(argv))
    return namespace.click_recipe, remaining


def _resolve_click_recipe(
    *, cli_path: Path | None, env: dict[str, str] | None = None
) -> ClickRecipe | None:
    """CLI --click-recipe overrides EZAX_CLICK_RECIPE; both optional."""
    env_map = env if env is not None else dict(os.environ)
    path: Path | None = cli_path
    if path is None:
        env_value = env_map.get(ENV_CLICK_RECIPE)
        if env_value:
            path = Path(env_value)
    if path is None:
        return None
    return load_click_recipe(path)


async def _run(
    *,
    argv: Sequence[str] | None = None,
    run_root: Path = _DEFAULT_RUN_ROOT,
) -> int:
    """Instantiate PyAutoGUIAdapter, preflight OS permissions, then run the graph."""
    argv_list = list(argv or [])
    recipe_path, remaining_argv = _extract_click_recipe_arg(argv_list)
    recipe = _resolve_click_recipe(cli_path=recipe_path)
    adapter = PyAutoGUIAdapter(run_root=run_root, click_recipe=recipe)
    adapter.preflight()
    await run_released_scope_from_argv_env(adapter=adapter, argv=remaining_argv)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(_run(argv=argv))
    except ConfigError as exc:
        print(f"ez-ax: config error: {exc}", file=sys.stderr)
        return 3
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
