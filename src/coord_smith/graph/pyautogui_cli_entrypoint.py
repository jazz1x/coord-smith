"""CLI entrypoint that wires PyAutoGUIAdapter to the released-scope execution graph."""

from __future__ import annotations

import argparse
import asyncio
import os
import platform
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from coord_smith import __version__
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.cli_logging import configure_logging, get_logger
from coord_smith.config.click_recipe import ClickRecipe, load_click_recipe
from coord_smith.graph.host_lock import HostBusyError, acquire_host_lock
from coord_smith.graph.released_cli_shim import run_released_scope_from_argv_env
from coord_smith.graph.run_cleanup import (
    DEFAULT_MAX_AGE_DAYS,
    DEFAULT_MAX_RUNS,
    cleanup_runs,
)
from coord_smith.models.errors import (
    AccessibilityPermissionDenied,
    ConfigError,
    ScreenCapturePermissionDenied,
)
from coord_smith.reporting.run_summary import RunStatus, RunSummaryWriter

ENV_CLICK_RECIPE = "COORDSMITH_CLICK_RECIPE"

_log = get_logger("cli")

_USAGE = """\
Usage: coord-smith [OPTIONS] --session-ref STR --expected-auth-state STR \\
             --target-page-url URL --site-identity STR

A deterministic OS-level click executor for autonomous agents (e.g. OpenClaw).
Reads a click recipe, runs the released-scope LangGraph, and writes typed
evidence artifacts (action-log JSONL + screenshots) under artifacts/runs/.

Options:
  --click-recipe PATH   YAML or JSON recipe (preferred: YAML). Also accepts the
                        COORDSMITH_CLICK_RECIPE env var. Required for actual
                        clicks when no external caller injects payload coords.
  --target-window NAME  macOS app name (e.g. "Google Chrome") to activate
                        before dispatch. coord-smith captures the whole
                        screen; if the target window is not foreground at
                        click time, the locate fails. This option runs
                        `osascript -e 'tell application "<name>" to activate'`
                        before preflight. macOS only; ignored elsewhere.
                        Env: COORDSMITH_TARGET_WINDOW.
  --dry-run             Validate the recipe and run the graph without
                        dispatching any real click. Exit 0 if everything
                        loads and resolves cleanly.
  --recipe-schema       Emit the JSON Schema for ClickRecipe to stdout and
                        exit 0. Useful when an external agent needs the
                        schema to validate or generate a recipe without
                        spawning a Python interpreter.
  --cleanup             Prune artifacts/runs/ to fit retention bounds and
                        exit 0. Use with --max-runs N (default 100) and
                        --max-age-days N (default 14). Run roots
                        containing a `.keep` sentinel file are never
                        removed.
  --max-runs N          Retention bound used by --cleanup (default 100).
  --max-age-days N      Retention bound used by --cleanup (default 14).
  --verbose, -v         Set log level to DEBUG (overrides
                        COORDSMITH_LOG_LEVEL).
  --quiet, -q           Set log level to WARNING (overrides
                        COORDSMITH_LOG_LEVEL).
  --session-ref         Required. Session identifier (env: COORDSMITH_SESSION_REF).
  --expected-auth-state Required. (env: COORDSMITH_EXPECTED_AUTH_STATE).
  --target-page-url     Required. (env: COORDSMITH_TARGET_PAGE_URL).
  --site-identity       Required. (env: COORDSMITH_SITE_IDENTITY).
  -V, --version         Print the package version and exit.
  -h, --help            Show this message and exit.

Examples:
  # Smoke target — no clicks, just verify env + permissions + writeable run root.
  coord-smith --session-ref demo --expected-auth-state authenticated \\
              --target-page-url https://example.com --site-identity example

  # Multi-step recipe (clicks the steps in order).
  coord-smith --click-recipe ./flow.yaml \\
              --session-ref demo --expected-auth-state authenticated \\
              --target-page-url https://example.com --site-identity example

  # Validate a recipe without clicking.
  coord-smith --dry-run --click-recipe ./flow.yaml \\
              --session-ref demo --expected-auth-state authenticated \\
              --target-page-url https://example.com --site-identity example

Exit codes:
  0 normal
  1 runtime error (typed dispatch failure OR caught KeyboardInterrupt /
    SIGINT — distinguished from a crash by run.json.status="interrupted")
  2 permission preflight failed
  3 recipe load error (missing / invalid YAML or JSON / schema)
  4 host busy (another coord-smith process holds the per-host lock)

Platform: macOS only at present. Linux / Windows preflight is not implemented;
the adapter assumes macOS Accessibility + Screen Recording permissions for
the host terminal app. See README §Permissions for setup.
"""


def _wants_help(argv: Sequence[str]) -> bool:
    return any(a in ("-h", "--help") for a in argv)


def _wants_version(argv: Sequence[str]) -> bool:
    return any(a in ("-V", "--version") for a in argv)


def _extract_known_flags(
    argv: Sequence[str],
) -> tuple[Path | None, bool, str | None, list[str]]:
    """Strip CLI-only flags.

    Returns ``(recipe_path, dry_run, target_window, remaining_argv)``. The
    remaining argv is forwarded to the released-scope shim, which only parses
    session/auth/url/site-identity. Anything we want the shim NOT to see
    (``--click-recipe``, ``--dry-run``, ``--target-window``) must be peeled
    off here.

    Verbosity flags (``--verbose`` / ``--quiet``) and ``--recipe-schema``
    are handled separately in :func:`main` — they bypass ``_run`` and so
    do not need to be stripped from the shim's argv.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--click-recipe", dest="click_recipe", type=Path)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    parser.add_argument("--target-window", dest="target_window", type=str)
    namespace, remaining = parser.parse_known_args(list(argv))
    return (
        namespace.click_recipe,
        namespace.dry_run,
        namespace.target_window,
        remaining,
    )


def _wants_recipe_schema(argv: Sequence[str]) -> bool:
    return any(a == "--recipe-schema" for a in argv)


def _resolve_log_level(argv: Sequence[str]) -> str | None:
    """``--verbose`` / ``-v`` → DEBUG; ``--quiet`` / ``-q`` → WARNING.

    Returns ``None`` if neither flag is present so the env var
    (``COORDSMITH_LOG_LEVEL``) or the default INFO can take over.
    Order of precedence when both flags appear: ``--verbose`` wins
    over ``--quiet`` (more useful default in debugging contexts).
    """
    has_verbose = any(a in ("--verbose", "-v") for a in argv)
    has_quiet = any(a in ("--quiet", "-q") for a in argv)
    if has_verbose:
        return "DEBUG"
    if has_quiet:
        return "WARNING"
    return None


def _strip_verbosity_flags(argv: Sequence[str]) -> list[str]:
    """Remove ``--verbose`` / ``-v`` / ``--quiet`` / ``-q`` /
    ``--recipe-schema`` so the released-scope shim does not see
    them. These flags are handled at the CLI boundary.

    Note: ``--cleanup`` and its bounds (``--max-runs`` / ``--max-age-days``)
    are not stripped here — the cleanup path short-circuits in
    ``main()`` before the shim is reached, so the shim never sees
    them.
    """
    consumed = {"--verbose", "-v", "--quiet", "-q", "--recipe-schema"}
    return [a for a in argv if a not in consumed]


def _resolve_target_window(
    *, cli_value: str | None, env: dict[str, str] | None = None
) -> str | None:
    """CLI --target-window overrides COORDSMITH_TARGET_WINDOW; both optional."""
    if cli_value:
        return cli_value
    env_map = env if env is not None else dict(os.environ)
    env_value = env_map.get("COORDSMITH_TARGET_WINDOW")
    return env_value or None


async def _activate_target_window(
    name: str, *, settle_seconds: float = 1.0
) -> bool:
    """Activate the named macOS application via osascript.

    Best-effort: returns True if osascript ran successfully, False otherwise.
    Sleeps ``settle_seconds`` to let the system finish the activation handoff
    before the caller proceeds to screenshot. Linux / Windows: no-op (returns
    False).

    Async because the caller (`_run`) runs inside ``asyncio.run`` and we
    don't want to block the event loop for a full second on the settle
    nap. ``time.sleep`` would do exactly that.

    The caller is responsible for keeping the activated window front for the
    duration of the run; this helper only triggers a one-shot activation,
    not a continuous focus guard.
    """
    if platform.system() != "Darwin":
        _log.warning(
            "--target-window is currently macOS-only; "
            "no activation attempted on this platform."
        )
        return False
    script = f'tell application "{name}" to activate'
    try:
        # ``subprocess.run`` itself blocks but is fast (<200 ms typically)
        # and runs once per invocation; we accept the brief block rather
        # than pulling in ``asyncio.create_subprocess_exec`` for a single
        # one-shot call. The long pause is the settle, which we now
        # ``await asyncio.sleep`` properly.
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        _log.warning(
            "target-window activation failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        return False
    if settle_seconds > 0:
        await asyncio.sleep(settle_seconds)
    return True


def _resolve_click_recipe(
    *, cli_path: Path | None, env: dict[str, str] | None = None
) -> ClickRecipe | None:
    """CLI --click-recipe overrides COORDSMITH_CLICK_RECIPE; both optional."""
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
    base_dir: Path = Path("."),
) -> int:
    """Instantiate PyAutoGUIAdapter, preflight OS permissions, then run the graph.

    ``--dry-run`` short-circuits after recipe load + preflight: it confirms
    the recipe parses, every referenced template resolves on disk, and the
    host has the required OS permissions, then exits cleanly without
    executing any click. Used by orchestrators (e.g. OpenClaw) to validate
    a recipe before committing the user's screen to a real run.

    ``--target-window`` (macOS) activates the named app immediately before
    preflight + dispatch so the target window is front-most when
    ``pyautogui.screenshot()`` runs. See ``docs/architecture-boundaries.md``
    §Window Ownership for caller responsibilities.
    """
    argv_list = list(argv or [])
    recipe_path, dry_run, target_window, remaining_argv = _extract_known_flags(
        argv_list
    )
    target_window = _resolve_target_window(cli_value=target_window)
    if target_window:
        await _activate_target_window(target_window)
    recipe = _resolve_click_recipe(cli_path=recipe_path)
    adapter = PyAutoGUIAdapter(run_root=base_dir, click_recipe=recipe)
    # Acquire the per-host advisory lock BEFORE preflight so a busy
    # neighbour does not get blamed for a permission failure. The
    # lock guards against pyautogui's process-global cursor/screen
    # (see graph/host_lock.py docstring). ``dry_run`` still holds
    # the lock — a parallel dry-run probe would still trigger the
    # real preflight cursor movements that race with another run.
    with acquire_host_lock(base_dir=base_dir):
        await adapter.preflight()
        if dry_run:
            step_count = len(recipe.steps) if recipe and recipe.steps else 0
            _log.info(
                "dry-run OK — preflight passed, %d step(s) resolved.",
                step_count,
            )
            return 0
        recipe_steps = (
            list(recipe.steps) if recipe is not None and recipe.steps else None
        )
        await run_released_scope_from_argv_env(
            adapter=adapter,
            argv=remaining_argv,
            env=dict(os.environ),
            base_dir=base_dir,
            recipe_steps=recipe_steps,
        )
    return 0


def _wants_cleanup(argv: Sequence[str]) -> bool:
    return any(a == "--cleanup" for a in argv)


def _extract_cleanup_bounds(
    argv: Sequence[str],
) -> tuple[int, int]:
    """Pull ``--max-runs`` / ``--max-age-days`` out of argv.

    Returns ``(max_runs, max_age_days)`` with their respective
    defaults when the flags are absent. Invalid integer values raise
    ``ConfigError`` so the CLI maps to exit code 3 (caller fed
    nonsense; recipe-style error).
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--max-runs", dest="max_runs", type=int, default=DEFAULT_MAX_RUNS
    )
    parser.add_argument(
        "--max-age-days",
        dest="max_age_days",
        type=int,
        default=DEFAULT_MAX_AGE_DAYS,
    )
    try:
        namespace, _ = parser.parse_known_args(list(argv))
    except SystemExit as exc:
        # argparse exits the process on integer parse failure; we
        # convert to a typed error the main() handler can render
        # with exit code 3 instead of exiting underneath us.
        raise ConfigError(
            f"--cleanup bounds must be integers (argparse rejected with code "
            f"{exc.code})"
        ) from exc
    if namespace.max_runs < 0:
        raise ConfigError(
            f"--max-runs must be >= 0, got {namespace.max_runs}"
        )
    if namespace.max_age_days < 0:
        raise ConfigError(
            f"--max-age-days must be >= 0, got {namespace.max_age_days}"
        )
    return namespace.max_runs, namespace.max_age_days


def _run_cleanup(base_dir: Path, argv: Sequence[str]) -> int:
    """Execute ``coord-smith --cleanup`` end-to-end.

    Reads the bounds from argv, runs ``cleanup_runs``, and prints
    the summary at INFO level. Returns 0 on success, 3 on bad
    arguments.
    """
    max_runs, max_age_days = _extract_cleanup_bounds(argv)
    report = cleanup_runs(
        base_dir=base_dir, max_runs=max_runs, max_age_days=max_age_days
    )
    _log.info("cleanup: %s", report.summary_line())
    return 0


def _emit_recipe_schema() -> int:
    """Print the ClickRecipe Pydantic JSON Schema to stdout.

    Designed for autonomous agents that attach the schema to their
    prompt without spawning a Python interpreter:

        coord-smith --recipe-schema > /tmp/recipe-schema.json

    The output is the standard ``model_json_schema()`` produced by
    Pydantic v2 — JSON-RFC-compliant and stable across patch
    releases (schema version is the ``ClickRecipe.version`` field,
    not the JSON Schema dialect).
    """
    import json as _json  # local — keep top-level imports lean

    print(_json.dumps(ClickRecipe.model_json_schema(), indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else sys.argv[1:]
    if _wants_help(argv_list):
        print(_USAGE)
        return 0
    if _wants_version(argv_list):
        print(f"coord-smith {__version__}")
        return 0
    if _wants_recipe_schema(argv_list):
        return _emit_recipe_schema()

    # Configure the coord_smith logger BEFORE any other work so the
    # first diagnostic line (if any) lands through the configured
    # handler. CLI flags > COORDSMITH_LOG_LEVEL > default INFO.
    configure_logging(level=_resolve_log_level(argv_list))
    argv_list = _strip_verbosity_flags(argv_list)

    if _wants_cleanup(argv_list):
        # ``--cleanup`` is an operator command, not a click run.
        # It does not need the host lock, the run.json envelope,
        # or the released-scope graph — short-circuit here so we
        # don't write a spurious run.json for a cleanup pass.
        try:
            return _run_cleanup(Path(".").resolve(), argv_list)
        except ConfigError as exc:
            _log.error("config error: %s", exc)
            return 3

    # base_dir resolves to an absolute path so the per-host advisory
    # lock and the run.json target both refer to the same filesystem
    # location regardless of which directory coord-smith was invoked
    # from. ``Path(".")`` alone would let two callers with different
    # cwd's silently bypass the lock — same machine, same artifacts/
    # tree under the resolved path, different relative strings.
    # See docs/architecture-boundaries.md §Host Exclusivity.
    base_dir = Path(".").resolve()
    summary_writer = RunSummaryWriter(base_dir=base_dir)
    exit_code: int = 1
    status: RunStatus = "failure"
    try:
        exit_code = asyncio.run(_run(argv=argv_list, base_dir=base_dir))
        status = "success" if exit_code == 0 else "failure"
        return exit_code
    except KeyboardInterrupt:
        # User or supervisor (Ctrl-C, SIGINT) requested stop. ``except
        # Exception`` below does NOT catch ``KeyboardInterrupt`` because
        # it inherits from ``BaseException`` — handle it explicitly so
        # the caller (OpenClaw) sees a deterministic exit code and a
        # stderr line instead of the Python default exit 130 with a
        # bare traceback. Exit 1 (runtime error) is documented; we
        # don't introduce a new code for this rare path.
        _log.warning(
            "interrupted by user / supervisor (KeyboardInterrupt)"
        )
        exit_code, status = 1, "interrupted"
        return exit_code
    except ConfigError as exc:
        _log.error("config error: %s", exc)
        exit_code, status = 3, "failure"
        return exit_code
    except HostBusyError as exc:
        # Another coord-smith process holds the per-host lock. Exit 4
        # is documented in --help so callers (e.g. OpenClaw) can back
        # off and retry instead of treating this as a generic runtime
        # error.
        _log.error("host busy: %s", exc)
        exit_code, status = 4, "host_busy"
        return exit_code
    except (AccessibilityPermissionDenied, ScreenCapturePermissionDenied) as exc:
        # Permission-class transport errors raised by preflight or screen
        # capture. The "grant permission and retry" hint is genuinely
        # actionable here. Other ExecutionTransportError subclasses
        # (ImageMatchConfidenceLow, PageTransitionNotDetected, etc.) are
        # runtime dispatch failures — they fall through to the generic
        # handler below and return exit code 1, because the screen state
        # / template / network is the issue, not host permissions.
        _log.error(
            "permission preflight failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        _log.error(
            "grant macOS Accessibility + Screen Recording permission to "
            "the host terminal app and retry."
        )
        exit_code, status = 2, "failure"
        return exit_code
    except Exception as exc:  # noqa: BLE001
        _log.error("runtime error (%s): %s", type(exc).__name__, exc)
        exit_code, status = 1, "failure"
        return exit_code
    finally:
        # Best-effort write of run.json so the caller (OpenClaw) has
        # a single-file summary regardless of which exit path fired.
        # ``status`` and ``exit_code`` carry whatever the relevant
        # branch set; default "failure" / 1 covers any path that
        # forgot to update them.
        summary_writer.flush(status=status, exit_code=exit_code)


if __name__ == "__main__":
    sys.exit(main())
