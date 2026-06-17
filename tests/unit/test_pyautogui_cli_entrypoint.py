"""Tests for PyAutoGUI CLI entrypoint wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import _run


async def test_run_instantiates_pyautogui_adapter(tmp_path: Path) -> None:
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_run,
    ):
        exit_code = await _run(base_dir=tmp_path)

    assert exit_code == 0
    mock_run.assert_called_once()
    adapter = mock_run.call_args.kwargs["adapter"]
    assert isinstance(adapter, PyAutoGUIAdapter)


async def test_run_passes_run_root_to_adapter(tmp_path: Path) -> None:
    captured: list[PyAutoGUIAdapter] = []

    async def _capture(**kwargs: object) -> MagicMock:
        captured.append(kwargs["adapter"])  # type: ignore[arg-type]
        return MagicMock()

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            side_effect=_capture,
        ),
    ):
        await _run(base_dir=tmp_path)

    assert captured[0]._run_root == tmp_path


async def test_run_passes_argv_to_graph(tmp_path: Path) -> None:
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_run,
    ):
        await _run(
            argv=["--session-ref", "s", "--expected-auth-state", "a"],
            base_dir=tmp_path,
        )

    call_argv = mock_run.call_args.kwargs["argv"]
    assert "--session-ref" in call_argv
    assert "s" in call_argv


def test_main_returns_exit_code_2_when_preflight_fails(tmp_path: Path) -> None:
    """Preflight ExecutionTransportError should produce exit 2 with stderr message."""
    from coord_smith.graph.pyautogui_cli_entrypoint import main
    from coord_smith.models.errors import AccessibilityPermissionDenied

    with patch.object(
        PyAutoGUIAdapter,
        "preflight",
        new_callable=AsyncMock,
        side_effect=AccessibilityPermissionDenied("no permission"),
    ):
        exit_code = main(argv=[])

    assert exit_code == 2


def test_main_handles_keyboard_interrupt_with_exit_1(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ctrl-C / SIGINT raises KeyboardInterrupt which inherits from
    BaseException, NOT Exception. Without an explicit handler the
    bare ``except Exception`` below would miss it and Python would
    exit 130 with a traceback — invisible to OpenClaw, no diagnostic
    log line, no recoverable diagnostic. main() must catch it
    deterministically and emit a recognizable log record.
    """
    import logging

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    with (
        patch.object(
            PyAutoGUIAdapter,
            "preflight",
            new_callable=AsyncMock,
            side_effect=KeyboardInterrupt(),
        ),
        caplog.at_level(logging.WARNING, logger="coord_smith.cli"),
    ):
        exit_code = main(argv=[])

    assert exit_code == 1, (
        "KeyboardInterrupt must map to a deterministic exit code "
        "(not Python's default 130) so the caller can react"
    )
    assert any(
        "interrupted" in record.getMessage().lower()
        for record in caplog.records
    ), "log records must include a recognizable interrupt marker"


def test_extract_known_flags_returns_path_dry_run_and_strips(tmp_path: Path) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _extract_known_flags

    recipe_path, dry_run, target_window, remaining = _extract_known_flags(
        [
            "--session-ref", "s", "--click-recipe", "/tmp/r.json",
            "--dry-run", "--site-identity", "x",
        ]
    )
    assert recipe_path == Path("/tmp/r.json")
    assert dry_run is True
    assert target_window is None
    assert "--click-recipe" not in remaining
    assert "/tmp/r.json" not in remaining
    assert "--dry-run" not in remaining
    assert "--session-ref" in remaining


def test_extract_known_flags_dry_run_defaults_false(tmp_path: Path) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _extract_known_flags

    recipe_path, dry_run, target_window, remaining = _extract_known_flags(
        ["--session-ref", "s"]
    )
    assert recipe_path is None
    assert dry_run is False
    assert target_window is None
    assert remaining == ["--session-ref", "s"]


def test_extract_known_flags_captures_target_window(tmp_path: Path) -> None:
    """--target-window NAME is stripped from argv and surfaced separately."""
    from coord_smith.graph.pyautogui_cli_entrypoint import _extract_known_flags

    recipe_path, dry_run, target_window, remaining = _extract_known_flags(
        ["--session-ref", "s", "--target-window", "Google Chrome"]
    )
    assert recipe_path is None
    assert dry_run is False
    assert target_window == "Google Chrome"
    assert "--target-window" not in remaining
    assert "Google Chrome" not in remaining
    assert "--session-ref" in remaining


def test_resolve_target_window_cli_overrides_env() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_target_window

    result = _resolve_target_window(
        cli_value="Safari",
        env={"COORDSMITH_TARGET_WINDOW": "Google Chrome"},
    )
    assert result == "Safari"


def test_resolve_target_window_uses_env_when_no_cli() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_target_window

    result = _resolve_target_window(
        cli_value=None,
        env={"COORDSMITH_TARGET_WINDOW": "Google Chrome"},
    )
    assert result == "Google Chrome"


def test_resolve_target_window_returns_none_when_neither_set() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_target_window

    result = _resolve_target_window(cli_value=None, env={})
    assert result is None


def test_resolve_target_window_treats_empty_env_as_unset() -> None:
    """An empty COORDSMITH_TARGET_WINDOW must not be treated as a real value."""
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_target_window

    result = _resolve_target_window(
        cli_value=None, env={"COORDSMITH_TARGET_WINDOW": ""}
    )
    assert result is None


async def test_activate_target_window_non_darwin_is_noop_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """On non-macOS platforms, activation is a no-op that emits a
    WARNING-level log record."""
    import logging

    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli.platform, "system", return_value="Linux"),
        caplog.at_level(logging.WARNING, logger="coord_smith.cli"),
    ):
        ok = await cli._activate_target_window("Google Chrome", settle_seconds=0.0)

    assert ok is False
    assert any(
        "macOS-only" in record.getMessage() for record in caplog.records
    )


async def test_activate_target_window_calls_osascript_on_darwin() -> None:
    """On macOS, _activate_target_window runs osascript with the right script."""
    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli.platform, "system", return_value="Darwin"),
        patch.object(cli.subprocess, "run") as mock_run,
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        ok = await cli._activate_target_window(
            "Google Chrome", settle_seconds=0.0
        )

    assert ok is True
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0][0] == "osascript"
    assert args[0][1] == "-e"
    assert 'tell application "Google Chrome" to activate' in args[0][2]
    assert kwargs.get("check") is True
    mock_sleep.assert_not_called()  # settle_seconds=0.0


async def test_activate_target_window_uses_asyncio_sleep_not_time_sleep() -> None:
    """The settle pause must use asyncio.sleep, not time.sleep — a 1 s
    time.sleep inside an async coroutine blocks the entire event loop
    for that second."""
    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli.platform, "system", return_value="Darwin"),
        patch.object(cli.subprocess, "run"),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_async_sleep,
    ):
        await cli._activate_target_window("Safari", settle_seconds=0.5)

    mock_async_sleep.assert_awaited_once_with(0.5)


async def test_activate_target_window_returns_false_on_osascript_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-zero osascript exit must be swallowed and reported via a
    WARNING-level log record."""
    import logging
    import subprocess

    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli.platform, "system", return_value="Darwin"),
        patch.object(
            cli.subprocess,
            "run",
            side_effect=subprocess.CalledProcessError(
                1, ["osascript"], stderr=b"missing app"
            ),
        ),
        caplog.at_level(logging.WARNING, logger="coord_smith.cli"),
    ):
        ok = await cli._activate_target_window(
            "NonExistentApp", settle_seconds=0.0
        )

    assert ok is False
    err = "\n".join(record.getMessage() for record in caplog.records)
    assert "activation failed" in err


async def test_run_activates_target_window_before_preflight(tmp_path: Path) -> None:
    """When --target-window is set, activation runs before preflight."""
    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    call_order: list[str] = []

    async def _record_activate(name: str, **_kw: object) -> bool:
        call_order.append(f"activate:{name}")
        return True

    async def _record_preflight(self: object) -> None:
        call_order.append("preflight")

    with (
        patch.object(cli, "_activate_target_window", side_effect=_record_activate),
        patch.object(
            PyAutoGUIAdapter, "preflight", new=_record_preflight
        ),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await cli._run(
            argv=["--target-window", "Google Chrome"], base_dir=tmp_path
        )

    assert call_order[0] == "activate:Google Chrome"
    assert call_order[1] == "preflight"


async def test_run_skips_activation_when_target_window_unset(tmp_path: Path) -> None:
    """Without --target-window and without env override, no activation."""
    from coord_smith.graph import pyautogui_cli_entrypoint as cli

    with (
        patch.object(cli, "_activate_target_window") as mock_activate,
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
        patch.dict("os.environ", {}, clear=False),
    ):
        # Strip env var if present
        import os as _os

        _os.environ.pop("COORDSMITH_TARGET_WINDOW", None)
        await cli._run(base_dir=tmp_path)

    mock_activate.assert_not_called()


def test_main_version_flag_returns_zero_and_prints_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from coord_smith import __version__
    from coord_smith.graph.pyautogui_cli_entrypoint import main

    for flag in ["-V", "--version"]:
        exit_code = main(argv=[flag])
        captured = capsys.readouterr()
        assert exit_code == 0, flag
        assert __version__ in captured.out, flag


def test_resolve_click_recipe_cli_wins_over_env(tmp_path: Path) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    cli_recipe = tmp_path / "cli.json"
    cli_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 1, "y": 2}}}', encoding="utf-8"
    )
    env_recipe = tmp_path / "env.json"
    env_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 99, "y": 99}}}', encoding="utf-8"
    )

    recipe = _resolve_click_recipe(
        cli_path=cli_recipe, env={"COORDSMITH_CLICK_RECIPE": str(env_recipe)}
    )
    assert recipe is not None
    assert recipe.coords_for("click_dispatch") == (1, 2)


def test_resolve_click_recipe_uses_env_when_no_cli(tmp_path: Path) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    env_recipe = tmp_path / "env.json"
    env_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 11, "y": 22}}}', encoding="utf-8"
    )

    recipe = _resolve_click_recipe(
        cli_path=None, env={"COORDSMITH_CLICK_RECIPE": str(env_recipe)}
    )
    assert recipe is not None
    assert recipe.coords_for("click_dispatch") == (11, 22)


def test_resolve_click_recipe_returns_none_when_neither_set() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    assert _resolve_click_recipe(cli_path=None, env={}) is None


def test_main_returns_exit_code_3_on_config_error(tmp_path: Path) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import main

    # Point at a non-existent recipe file -> ConfigError -> exit 3
    missing = tmp_path / "missing.json"
    exit_code = main(argv=["--click-recipe", str(missing)])
    assert exit_code == 3


def test_main_prints_usage_for_help_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import main

    for flag in ["-h", "--help"]:
        exit_code = main(argv=[flag])
        captured = capsys.readouterr()
        assert exit_code == 0, flag
        assert "Usage: coord-smith" in captured.out, flag
        assert "--click-recipe" in captured.out, flag


def test_main_recipe_schema_emits_json_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--recipe-schema`` dumps the Pydantic JSON Schema to stdout.

    Designed for autonomous agents that paste the schema into a
    prompt — must be valid JSON, must declare ``$defs`` / ``properties``
    (the standard JSON Schema vocabulary), and must reference our
    own field names (``steps``, ``version``).
    """
    import json

    from coord_smith.graph.pyautogui_cli_entrypoint import main

    exit_code = main(argv=["--recipe-schema"])
    out = capsys.readouterr().out

    assert exit_code == 0
    schema = json.loads(out)
    # Schema is a dict at the top-level, with object semantics.
    assert isinstance(schema, dict)
    assert schema.get("type") == "object" or "$defs" in schema
    # Properties pin our canonical recipe fields — if the JSON schema
    # generator drops these, the agent contract is silently broken.
    properties = schema.get("properties", {})
    assert "steps" in properties or "$defs" in schema
    assert "version" in properties


def test_resolve_log_level_verbose_wins() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _resolve_log_level

    assert _resolve_log_level(["--verbose"]) == "DEBUG"
    assert _resolve_log_level(["-v"]) == "DEBUG"
    assert _resolve_log_level(["--quiet"]) == "WARNING"
    assert _resolve_log_level(["-q"]) == "WARNING"
    # When both are present, verbose wins (more useful default).
    assert _resolve_log_level(["--verbose", "--quiet"]) == "DEBUG"
    # No verbosity flags → None → defer to env / default.
    assert _resolve_log_level([]) is None


def test_strip_verbosity_flags_removes_cli_only_flags() -> None:
    from coord_smith.graph.pyautogui_cli_entrypoint import _strip_verbosity_flags

    remaining = _strip_verbosity_flags(
        [
            "--session-ref", "s",
            "--verbose",
            "--target-page-url", "https://x",
            "-q",
            "--recipe-schema",
            "--site-identity", "z",
        ]
    )
    assert "--verbose" not in remaining
    assert "-q" not in remaining
    assert "--recipe-schema" not in remaining
    # Real session-graph flags pass through.
    assert "--session-ref" in remaining
    assert "--target-page-url" in remaining
    assert "--site-identity" in remaining


async def test_run_passes_os_environ_as_env_to_graph(tmp_path: Path) -> None:
    """env=dict(os.environ) must reach run_released_scope_from_argv_env."""
    sentinel = "test-session-ref-value"

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_run,
        patch.dict("os.environ", {"COORDSMITH_SESSION_REF": sentinel}),
    ):
        await _run(base_dir=tmp_path)

    call_env = mock_run.call_args.kwargs["env"]
    assert call_env is not None, "env kwarg must be passed"
    assert call_env.get("COORDSMITH_SESSION_REF") == sentinel
