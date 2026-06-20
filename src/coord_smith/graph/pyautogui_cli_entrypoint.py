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
from coord_smith.config.released_inputs import resolve_released_scope_inputs
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
from coord_smith.reporting.run_summary import RunSummaryWriter
from coord_smith.reporting.run_summary_lifecycle import RunSummaryLifecycle

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
  3 config error (recipe missing / invalid YAML or JSON / schema; a required
    session/auth/url/site input absent; an invalid --cleanup bound; a failed
    --target-window activation (bad / non-running app name — a hard fail, not a
    silent best-effort); or a malformed payload coord override). The
    'config error: <message>' stderr line names the exact cause.
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


# Every option flag coord-smith accepts, across all parse stages. A token
# that starts with '-', is not a bare '-'/'--', and is not in this set is a
# typo (e.g. --click-recipie) — argparse's parse_known_args would silently
# drop it, making a fat-fingered run look like a successful no-op. Rejecting
# it up front mirrors the recipe layer's extra="forbid" strictness.
_KNOWN_FLAGS = frozenset({
    "-h", "--help",
    "-V", "--version",
    "--recipe-schema",
    "--verbose", "-v", "--quiet", "-q",
    "--click-recipe",
    "--dry-run",
    "--target-window",
    "--session-ref",
    "--expected-auth-state",
    "--target-page-url",
    "--site-identity",
    "--cleanup",
    "--max-runs",
    "--max-age-days",
})


def _reject_unknown_flags(argv: Sequence[str]) -> None:
    """Raise ``ConfigError`` (→ exit 3) on the first unrecognized option flag.

    A flag-shaped token (`-x` / `--long`) that is not a known coord-smith flag
    is almost always a typo. argparse's ``parse_known_args`` would discard it
    silently — so a misspelled ``--click-recipe`` yields exit 0 with zero
    clicks, indistinguishable from an intended smoke target. Fail loudly
    instead, naming the offending flag. ``--max-runs=5`` style ``flag=value``
    tokens are split on ``=`` so the flag part is checked.
    """
    for tok in argv:
        if not tok.startswith("-") or tok in ("-", "--"):
            continue  # positional or stdin sentinel, not a flag
        if _is_negative_number(tok):
            continue  # a value like '-1' / '-3.5' (e.g. --max-runs -1), not a flag
        flag = tok.split("=", 1)[0]
        if flag not in _KNOWN_FLAGS:
            raise ConfigError(
                f"unknown flag: {flag!r}. Run 'coord-smith --help' for the "
                "accepted flags. (A misspelled flag is dropped silently by the "
                "parser, so coord-smith rejects unknown flags up front.)"
            )


def _is_negative_number(tok: str) -> bool:
    """True when ``tok`` is a negative numeric literal (e.g. ``-1``, ``-3.5``).

    Such tokens are option *values* (``--max-runs -1``), not flags, so the
    unknown-flag guard must not reject them.
    """
    try:
        float(tok)
    except ValueError:
        return False
    return True


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
        # The operator EXPLICITLY asked to focus this window. If activation
        # fails on macOS (typo'd app name, app not running, osascript
        # timeout), proceeding would click whatever happens to be frontmost —
        # a silent wrong-target for coord recipes. Fail loudly (ConfigError →
        # exit 3) naming the window instead of warning-and-continuing. This is
        # distinct from the Linux/Windows no-op above, which is a documented
        # unsupported-platform warning, not a requested-but-failed activation.
        raise ConfigError(
            f"--target-window activation failed for {name!r} "
            f"({type(exc).__name__}: {exc}). The app may be misspelled or not "
            "running. Fix the window name or omit --target-window."
        ) from exc
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
    summary_writer: RunSummaryWriter | None = None,
) -> int:
    """Instantiate PyAutoGUIAdapter, preflight OS permissions, then run the graph.

    ``--dry-run`` is a pure validator: it confirms the recipe parses, every
    referenced template resolves on disk, and the four required inputs are
    present, then exits 0 — WITHOUT preflight, the host lock, or any click.
    It deliberately does NOT require OS permissions, so an orchestrator (e.g.
    OpenClaw) or CI can cheaply validate a generated recipe on a host that
    has not been granted Accessibility / Screen Recording. A missing input
    surfaces as exit 3 (config error), the same as a real run.

    ``--target-window`` (macOS) activates the named app immediately before
    preflight + dispatch so the target window is front-most when
    ``pyautogui.screenshot()`` runs. See ``docs/architecture-boundaries.md``
    §Window Ownership for caller responsibilities.
    """
    argv_list = list(argv or [])
    recipe_path, dry_run, target_window, remaining_argv = _extract_known_flags(
        argv_list
    )
    recipe = _resolve_click_recipe(cli_path=recipe_path)

    if dry_run:
        # --dry-run is a PURE, no-permission validator: it confirms the recipe
        # parses + every template resolves (done in _resolve_click_recipe
        # above) and the four required inputs are present, then exits 0 —
        # WITHOUT preflight, the host lock, or window activation. An LLM
        # caller (or CI) pre-validating a generated recipe must not need
        # Accessibility/Screen-Recording permission, and a missing input must
        # surface as the documented config error (exit 3), not a misdirecting
        # "grant permission" (exit 2). Preflight is a real-run concern; a
        # dry-run touches neither the cursor nor the shared foreground, so it
        # needs no lock.
        resolve_released_scope_inputs(argv=remaining_argv, env=dict(os.environ))
        step_count = len(recipe.steps) if recipe and recipe.steps else 0
        _log.info(
            "dry-run OK — recipe + inputs valid, %d step(s) resolved.",
            step_count,
        )
        # Stash the count so main()'s try/finally writes a run.json with
        # step_count matching the log line (the writer's empirical recovery
        # would return 0 — no run root is created on dry-run).
        if summary_writer is not None:
            summary_writer.set_pending_step_count(step_count)
        return 0

    # Validate the four required released-scope inputs BEFORE adapter / lock /
    # preflight, mirroring the dry-run branch above. Otherwise, on a host
    # without Accessibility (the default first-run state), preflight raises
    # first and a missing input is misreported as exit 2 "grant permission"
    # instead of exit 3 "supply --session-ref" — routing an automated caller
    # (OpenClaw) down the wrong recovery branch (the exit code is an ADR-006
    # caller contract). resolve_released_scope_inputs is a pure parse of
    # argv+env; the shim re-parses it downstream (idempotent). A missing input
    # therefore fails fast, before acquiring the host lock for a doomed run.
    resolve_released_scope_inputs(argv=remaining_argv, env=dict(os.environ))

    adapter = PyAutoGUIAdapter(run_root=base_dir, click_recipe=recipe)
    # Acquire the per-host advisory lock BEFORE preflight so a busy
    # neighbour does not get blamed for a permission failure. The
    # lock guards against pyautogui's process-global cursor/screen
    # (see graph/host_lock.py docstring).
    with acquire_host_lock(base_dir=base_dir):
        # Activate the target window INSIDE the lock: it steals foreground
        # focus and sleeps ~1s, which would disrupt an already-running
        # invocation if done before this run owns the host. Only the lock
        # holder should touch the shared foreground.
        target_window = _resolve_target_window(cli_value=target_window)
        if target_window:
            await _activate_target_window(target_window)
        await adapter.preflight()
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


_CLEANUP_COFLAG_PREFIXES = (
    "--click-recipe",
    "--session-ref",
    "--expected-auth-state",
    "--target-page-url",
    "--site-identity",
    "--target-window",
    "--dry-run",
)


def _run_cleanup(base_dir: Path, argv: Sequence[str]) -> int:
    """Execute ``coord-smith --cleanup`` end-to-end.

    Reads the bounds from argv, runs ``cleanup_runs`` while holding
    the per-host advisory lock (so a concurrent click run cannot
    have its directory deleted from under it — see ADR-005 +
    docs/architecture-boundaries.md §Host Exclusivity), and logs
    the summary at INFO level.

    Returns:
        0 — success, all targeted runs removed (or no runs to remove)
        1 — partial failure (CleanupReport.errors > 0; some
            directories could not be deleted, e.g. permission denied)
        3 — bad argument (negative bound — handled upstream as
            ConfigError before this function runs)
        4 — host busy (another coord-smith process holds the lock;
            HostBusyError propagates to main's handler)

    Co-flags (``--click-recipe`` and session args) are silently
    ignored when paired with ``--cleanup``; we emit a WARNING-level
    log so the operator notices the misuse without aborting the
    cleanup pass.
    """
    co_flags = [a for a in argv if a.split("=", 1)[0] in _CLEANUP_COFLAG_PREFIXES]
    if co_flags:
        _log.warning(
            "--cleanup: ignoring co-passed flags %s — cleanup runs "
            "in isolation and does not dispatch clicks",
            co_flags,
        )

    max_runs, max_age_days = _extract_cleanup_bounds(argv)
    # Acquire the host lock so a concurrent click run cannot have
    # its run root removed mid-flight. cleanup_runs sorts by mtime
    # and could otherwise classify an active run as "stale" under
    # a tight --max-runs bound.
    with acquire_host_lock(base_dir=base_dir):
        report = cleanup_runs(
            base_dir=base_dir, max_runs=max_runs, max_age_days=max_age_days
        )
    _log.info("cleanup: %s", report.summary_line())
    if report.errors > 0:
        _log.warning(
            "cleanup: %d directory deletion error(s); see prior log records",
            report.errors,
        )
        return 1
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

    # Reject typo'd flags before any work — a silently-dropped --click-recipe
    # would otherwise run as a no-op and report success. Maps to exit 3.
    try:
        _reject_unknown_flags(argv_list)
    except ConfigError as exc:
        _log.error("config error: %s", exc)
        return 3

    if _wants_cleanup(argv_list):
        # ``--cleanup`` is an operator command, not a click run.
        # It DOES acquire the per-host advisory lock (so a concurrent
        # click run cannot have its dir deleted mid-flight — see
        # ADR-005), but it does NOT write the run.json envelope
        # (cleanup is not a "run" in the dispatch sense — see
        # _run_cleanup docstring).
        try:
            return _run_cleanup(Path(".").resolve(), argv_list)
        except ConfigError as exc:
            _log.error("config error: %s", exc)
            return 3
        except HostBusyError as exc:
            # Same back-off semantics as a click run: exit 4 signals
            # to the operator to retry after another invocation
            # releases the lock.
            _log.error("host busy: %s", exc)
            return 4

    # base_dir resolves to an absolute path so the per-host advisory
    # lock and the run.json target both refer to the same filesystem
    # location regardless of which directory coord-smith was invoked
    # from. ``Path(".")`` alone would let two callers with different
    # cwd's silently bypass the lock — same machine, same artifacts/
    # tree under the resolved path, different relative strings.
    # See docs/architecture-boundaries.md §Host Exclusivity.
    base_dir = Path(".").resolve()
    # ``RunSummaryLifecycle`` is the dispatch-run bracket: it
    # constructs the RunSummaryWriter on entry, exposes
    # ``set_outcome(...)`` so each except branch declares its
    # result without managing the writer directly, and flushes
    # run.json on exit (regardless of exception). Extracted in
    # B-CA-5 so main() carries one concern (CLI routing) instead
    # of two (CLI routing + reporting lifecycle).
    with RunSummaryLifecycle(base_dir=base_dir) as summary:
        try:
            exit_code = asyncio.run(
                _run(
                    argv=argv_list,
                    base_dir=base_dir,
                    summary_writer=summary.writer,
                )
            )
            summary.set_outcome(
                status="success" if exit_code == 0 else "failure",
                exit_code=exit_code,
            )
            return exit_code
        except KeyboardInterrupt:
            # User or supervisor (Ctrl-C, SIGINT) requested stop.
            # ``except Exception`` below does NOT catch
            # KeyboardInterrupt (BaseException subclass), so we
            # handle it explicitly. The caller (OpenClaw) sees a
            # deterministic exit code + stderr line + a run.json
            # with status="interrupted" instead of Python's
            # silent exit 130.
            _log.warning(
                "interrupted by user / supervisor (KeyboardInterrupt)"
            )
            summary.set_outcome(status="interrupted", exit_code=1)
            return 1
        except ConfigError as exc:
            _log.error("config error: %s", exc)
            summary.set_outcome(status="failure", exit_code=3)
            return 3
        except HostBusyError as exc:
            # Another coord-smith process holds the per-host lock.
            # Exit 4 is documented in --help so callers (e.g.
            # OpenClaw) can back off and retry instead of treating
            # this as a generic runtime error.
            _log.error("host busy: %s", exc)
            summary.set_outcome(status="host_busy", exit_code=4)
            return 4
        except (AccessibilityPermissionDenied, ScreenCapturePermissionDenied) as exc:
            # Permission-class transport errors raised by preflight
            # or screen capture. The "grant permission and retry"
            # hint is genuinely actionable here. Other
            # ExecutionTransportError subclasses
            # (ImageMatchConfidenceLow, PageTransitionNotDetected,
            # etc.) are runtime dispatch failures — they fall
            # through to the generic handler below and return exit
            # code 1 because the screen state / template / network
            # is the issue, not host permissions.
            _log.error(
                "permission preflight failed (%s): %s",
                type(exc).__name__,
                exc,
            )
            _log.error(
                "grant macOS Accessibility + Screen Recording permission to "
                "the host terminal app and retry."
            )
            summary.set_outcome(status="failure", exit_code=2)
            return 2
        except Exception as exc:  # noqa: BLE001
            _log.error("runtime error (%s): %s", type(exc).__name__, exc)
            summary.set_outcome(status="failure", exit_code=1)
            return 1


if __name__ == "__main__":
    sys.exit(main())
