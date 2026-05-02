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

_DEFAULT_RUN_ROOT = Path("artifacts/runs/default")
ENV_CLICK_RECIPE = "EZAX_CLICK_RECIPE"

_USAGE = """\
Usage: ez-ax [--click-recipe PATH] \\
             --session-ref STR --expected-auth-state STR \\
             --target-page-url URL --site-identity STR

Options:
  --click-recipe PATH   JSON recipe mapping mission_name -> {x, y} coords.
                        Also accepts the EZAX_CLICK_RECIPE env var.
                        Required for actual browser clicks when no external
                        caller injects payload coords.
  --session-ref         Required. Session identifier (env: EZAX_SESSION_REF).
  --expected-auth-state Required. (env: EZAX_EXPECTED_AUTH_STATE).
  --target-page-url     Required. (env: EZAX_TARGET_PAGE_URL).
  --site-identity       Required. (env: EZAX_SITE_IDENTITY).

Exit codes:
  0 normal      1 runtime error     2 permission preflight failed
  3 recipe load error (missing / invalid JSON / schema)

See README §Click Recipes and §Permissions (macOS) for details.
"""


def _wants_help(argv: Sequence[str]) -> bool:
    return any(a in ("-h", "--help") for a in argv)


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
    await adapter.preflight()
    await run_released_scope_from_argv_env(
        adapter=adapter, argv=remaining_argv, env=dict(os.environ)
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    if _wants_help(argv_list):
        print(_USAGE)
        return 0
    try:
        return asyncio.run(_run(argv=argv_list))
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
