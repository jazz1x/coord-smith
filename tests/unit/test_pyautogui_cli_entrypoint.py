"""Tests for PyAutoGUI CLI entrypoint wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.graph.pyautogui_cli_entrypoint import _run


async def test_run_instantiates_pyautogui_adapter(tmp_path: Path) -> None:
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
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
            "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            side_effect=_capture,
        ),
    ):
        await _run(base_dir=tmp_path)

    assert captured[0]._run_root == tmp_path


async def test_run_passes_argv_to_graph(tmp_path: Path) -> None:
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
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
    from ez_ax.graph.pyautogui_cli_entrypoint import main
    from ez_ax.models.errors import AccessibilityPermissionDenied

    with patch.object(
        PyAutoGUIAdapter,
        "preflight",
        new_callable=AsyncMock,
        side_effect=AccessibilityPermissionDenied("no permission"),
    ):
        exit_code = main(argv=[])

    assert exit_code == 2


def test_extract_click_recipe_arg_returns_path_and_strips(tmp_path: Path) -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import _extract_click_recipe_arg

    recipe_path, remaining = _extract_click_recipe_arg(
        ["--session-ref", "s", "--click-recipe", "/tmp/r.json", "--site-identity", "x"]
    )
    assert recipe_path == Path("/tmp/r.json")
    assert "--click-recipe" not in remaining
    assert "/tmp/r.json" not in remaining
    assert "--session-ref" in remaining


def test_resolve_click_recipe_cli_wins_over_env(tmp_path: Path) -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    cli_recipe = tmp_path / "cli.json"
    cli_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 1, "y": 2}}}', encoding="utf-8"
    )
    env_recipe = tmp_path / "env.json"
    env_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 99, "y": 99}}}', encoding="utf-8"
    )

    recipe = _resolve_click_recipe(
        cli_path=cli_recipe, env={"EZAX_CLICK_RECIPE": str(env_recipe)}
    )
    assert recipe is not None
    assert recipe.coords_for("click_dispatch") == (1, 2)


def test_resolve_click_recipe_uses_env_when_no_cli(tmp_path: Path) -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    env_recipe = tmp_path / "env.json"
    env_recipe.write_text(
        '{"missions": {"click_dispatch": {"x": 11, "y": 22}}}', encoding="utf-8"
    )

    recipe = _resolve_click_recipe(
        cli_path=None, env={"EZAX_CLICK_RECIPE": str(env_recipe)}
    )
    assert recipe is not None
    assert recipe.coords_for("click_dispatch") == (11, 22)


def test_resolve_click_recipe_returns_none_when_neither_set() -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import _resolve_click_recipe

    assert _resolve_click_recipe(cli_path=None, env={}) is None


def test_main_returns_exit_code_3_on_config_error(tmp_path: Path) -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import main

    # Point at a non-existent recipe file -> ConfigError -> exit 3
    missing = tmp_path / "missing.json"
    exit_code = main(argv=["--click-recipe", str(missing)])
    assert exit_code == 3


def test_main_prints_usage_for_help_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    from ez_ax.graph.pyautogui_cli_entrypoint import main

    for flag in ["-h", "--help"]:
        exit_code = main(argv=[flag])
        captured = capsys.readouterr()
        assert exit_code == 0, flag
        assert "Usage: ez-ax" in captured.out, flag
        assert "--click-recipe" in captured.out, flag


async def test_run_passes_os_environ_as_env_to_graph(tmp_path: Path) -> None:
    """env=dict(os.environ) must reach run_released_scope_from_argv_env."""
    sentinel = "test-session-ref-value"

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ) as mock_run,
        patch.dict("os.environ", {"EZAX_SESSION_REF": sentinel}),
    ):
        await _run(base_dir=tmp_path)

    call_env = mock_run.call_args.kwargs["env"]
    assert call_env is not None, "env kwarg must be passed"
    assert call_env.get("EZAX_SESSION_REF") == sentinel
