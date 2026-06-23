"""Programmatic Python API for coord-smith.

This module exposes a high-level ``run_click_recipe`` coroutine so that
external callers (including LLM agents and orchestrators other than
OpenClaw) can invoke coord-smith without spawning a subprocess or writing
a recipe file to disk.

The API preserves all coord-smith invariants:

- LLM-free runtime (no model calls inside the graph)
- Browser-internals forbidden
- Coordinate priority fixed (payload → coord → image → no-click)
- Per-host advisory lock
- Evidence envelope (run.json + action-log JSONL + screenshots)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from coord_smith.adapters.execution.client import ExecutionAdapter
from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.cli_logging import configure_logging, get_logger
from coord_smith.config.click_recipe import ClickRecipe, load_click_recipe
from coord_smith.graph.host_lock import HostBusyError, acquire_host_lock
from coord_smith.graph.pyautogui_cli_entrypoint import _activate_target_window
from coord_smith.graph.released_entrypoint import run_released_scope
from coord_smith.models.errors import (
    AccessibilityPermissionDenied,
    ConfigError,
    ScreenCapturePermissionDenied,
)
from coord_smith.models.identifiers import (
    ExpectedAuthState as ExpectedAuthStateIdentifier,
)
from coord_smith.models.identifiers import (
    SessionRef as SessionRefIdentifier,
)
from coord_smith.models.identifiers import (
    SiteIdentity as SiteIdentityIdentifier,
)
from coord_smith.models.identifiers import (
    TargetPageUrl as TargetPageUrlIdentifier,
)
from coord_smith.models.identifiers import (
    parse_expected_auth_state,
    parse_session_ref,
    parse_site_identity,
    parse_target_page_url,
)
from coord_smith.reporting.run_summary import RunSummary, RunSummaryWriter

_log = get_logger("api")

RunStatus = Literal["success", "failure", "interrupted", "host_busy"]

RecipeInput = ClickRecipe | dict[str, Any] | str | Path


@dataclass(frozen=True, slots=True)
class RunResult:
    """Structured result of a programmatic coord-smith run.

    Mirrors the on-disk ``run.json`` envelope so callers can inspect the
    outcome without re-reading the file. ``run_json_path`` points to the
    flushed summary (inside ``artifacts/runs/<run_id>/`` on success, or
    ``<base_dir>/run.json`` when no run root was created).
    """

    status: RunStatus
    exit_code: int
    run_json_path: Path
    run_id: str | None
    step_count: int
    failure: dict[str, Any] | None
    elapsed_seconds: float
    summary: RunSummary

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict matching ``run.json``."""
        return self.summary.to_json()


def _resolve_recipe(recipe: RecipeInput) -> ClickRecipe:
    """Normalize a recipe input into a ``ClickRecipe`` model."""
    try:
        if isinstance(recipe, ClickRecipe):
            return recipe
        if isinstance(recipe, Path):
            return load_click_recipe(recipe)
        if isinstance(recipe, str):
            # If the string looks like a file path, load it; otherwise parse as YAML.
            maybe_path = Path(recipe)
            if maybe_path.suffix in (".yaml", ".yml", ".json") or maybe_path.is_file():
                return load_click_recipe(maybe_path)
            data = yaml.safe_load(recipe)
            return ClickRecipe.model_validate(data)
        # dict
        return ClickRecipe.model_validate(recipe)
    except ValidationError as exc:
        raise ConfigError(f"invalid recipe: {exc}") from exc


def _resolve_inputs(
    *,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
) -> tuple[
    SessionRefIdentifier,
    ExpectedAuthStateIdentifier,
    TargetPageUrlIdentifier,
    SiteIdentityIdentifier,
]:
    """Validate the four released-scope inputs through boundary parsers."""
    return (
        parse_session_ref(session_ref),
        parse_expected_auth_state(expected_auth_state),
        parse_target_page_url(target_page_url),
        parse_site_identity(site_identity),
    )


async def run_click_recipe(
    recipe: RecipeInput,
    *,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    target_window: str | None = None,
    dry_run: bool = False,
    base_dir: str | Path | None = None,
    log_level: str | None = None,
    _adapter_factory: Callable[..., ExecutionAdapter] | None = None,
) -> RunResult:
    """Run a click recipe programmatically and return a structured result.

    This is the canonical Python entrypoint for using coord-smith as an
    independent library or LLM-callable tool. It does not spawn a subprocess
    and accepts the recipe as a model, dict, YAML string, or file path.

    Args:
        recipe: A ``ClickRecipe``, ``dict``, YAML/JSON ``str``, or ``Path``
            to a recipe file.
        session_ref: Session identifier.
        expected_auth_state: Expected authentication state.
        target_page_url: Target page URL.
        site_identity: Site identity.
        target_window: Optional macOS app name to activate before dispatch.
        dry_run: If True, validate the recipe and inputs without clicking.
        base_dir: Directory for ``artifacts/`` and ``run.json``. Defaults to
            the current working directory.
        log_level: Optional log level (DEBUG/INFO/WARNING/ERROR). Defaults to
            ``COORDSMITH_LOG_LEVEL`` env var or INFO.

    Returns:
        A ``RunResult`` describing the outcome, including the flushed
        ``run.json`` path and the in-memory summary.

    Note:
        ``_adapter_factory`` is an internal hook for tests that need to
        inject a mock execution adapter. Production callers should leave it
        as ``None`` (the default PyAutoGUI adapter).

    Raises:
        Does not raise on runtime failures; all outcomes are captured in the
        returned ``RunResult``. Propagates only unexpected internal errors.
    """
    configure_logging(level=log_level)
    resolved_base = Path(base_dir).resolve() if base_dir else Path(".").resolve()

    writer = RunSummaryWriter(base_dir=resolved_base)
    status: RunStatus = "failure"
    exit_code = 1
    run_id: str | None = None
    try:
        recipe_model = _resolve_recipe(recipe)
        (
            session_ref_id,
            expected_auth_state_id,
            target_page_url_id,
            site_identity_id,
        ) = _resolve_inputs(
            session_ref=session_ref,
            expected_auth_state=expected_auth_state,
            target_page_url=target_page_url,
            site_identity=site_identity,
        )

        if dry_run:
            step_count = len(recipe_model.steps) if recipe_model.steps else 0
            writer.set_pending_step_count(step_count)
            _log.info(
                "dry-run OK — recipe + inputs valid, %d step(s) resolved.",
                step_count,
            )
            path, summary = writer.flush(
                status="success", exit_code=0, step_count_override=step_count
            )
            return RunResult(
                status="success",
                exit_code=0,
                run_json_path=path,
                run_id=None,
                step_count=step_count,
                failure=None,
                elapsed_seconds=summary.elapsed_seconds,
                summary=summary,
            )

        adapter_factory = _adapter_factory or PyAutoGUIAdapter
        adapter = adapter_factory(
            run_root=resolved_base, click_recipe=recipe_model
        )
        with acquire_host_lock(base_dir=resolved_base):
            if target_window:
                await _activate_target_window(target_window)
            await adapter.preflight()
            recipe_steps = (
                list(recipe_model.steps)
                if recipe_model.steps is not None
                else None
            )
            result = await run_released_scope(
                adapter=adapter,
                session_ref=session_ref_id,
                expected_auth_state=expected_auth_state_id,
                target_page_url=target_page_url_id,
                site_identity=site_identity_id,
                base_dir=resolved_base,
                recipe_steps=recipe_steps,
                on_run_root_created=writer.set_own_run_root,
            )
            status = "success"
            exit_code = 0
            run_id = result.run.run_root.name
    except KeyboardInterrupt:
        _log.warning("interrupted by user / supervisor (KeyboardInterrupt)")
        status = "interrupted"
        exit_code = 1
        run_id = writer._own_run_root.name if writer._own_run_root else None
    except ConfigError as exc:
        _log.error("config error: %s", exc)
        status = "failure"
        exit_code = 3
        run_id = writer._own_run_root.name if writer._own_run_root else None
    except HostBusyError as exc:
        _log.error("host busy: %s", exc)
        status = "host_busy"
        exit_code = 4
        run_id = None
    except (
        AccessibilityPermissionDenied,
        ScreenCapturePermissionDenied,
    ) as exc:
        _log.error(
            "permission preflight failed (%s): %s",
            type(exc).__name__,
            exc,
        )
        _log.error(
            "grant macOS Accessibility + Screen Recording permission to "
            "the host terminal app and retry."
        )
        status = "failure"
        exit_code = 2
        run_id = writer._own_run_root.name if writer._own_run_root else None
    except Exception as exc:  # noqa: BLE001 — API captures all runtime failures
        _log.error("runtime error (%s): %s", type(exc).__name__, exc)
        status = "failure"
        exit_code = 1
        run_id = writer._own_run_root.name if writer._own_run_root else None

    path, summary = writer.flush(status=status, exit_code=exit_code)
    elapsed = summary.elapsed_seconds
    return RunResult(
        status=status,
        exit_code=exit_code,
        run_json_path=path,
        run_id=run_id,
        step_count=summary.step_count,
        failure=summary.failure,
        elapsed_seconds=elapsed,
        summary=summary,
    )


def run_click_recipe_sync(
    recipe: RecipeInput,
    *,
    session_ref: str,
    expected_auth_state: str,
    target_page_url: str,
    site_identity: str,
    target_window: str | None = None,
    dry_run: bool = False,
    base_dir: str | Path | None = None,
    log_level: str | None = None,
    _adapter_factory: Callable[..., ExecutionAdapter] | None = None,
) -> RunResult:
    """Synchronous wrapper around :func:`run_click_recipe`."""
    return asyncio.run(
        run_click_recipe(
            recipe=recipe,
            session_ref=session_ref,
            expected_auth_state=expected_auth_state,
            target_page_url=target_page_url,
            site_identity=site_identity,
            target_window=target_window,
            dry_run=dry_run,
            base_dir=base_dir,
            log_level=log_level,
            _adapter_factory=_adapter_factory,
        )
    )
