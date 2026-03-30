"""Tests for PyAutoGUI CLI entrypoint wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter
from ez_ax.graph.pyautogui_cli_entrypoint import _run


async def test_run_instantiates_pyautogui_adapter(tmp_path: Path) -> None:
    with patch(
        "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ) as mock_run:
        exit_code = await _run(run_root=tmp_path)

    assert exit_code == 0
    mock_run.assert_called_once()
    adapter = mock_run.call_args.kwargs["adapter"]
    assert isinstance(adapter, PyAutoGUIAdapter)


async def test_run_passes_run_root_to_adapter(tmp_path: Path) -> None:
    captured: list[PyAutoGUIAdapter] = []

    async def _capture(**kwargs: object) -> MagicMock:
        captured.append(kwargs["adapter"])  # type: ignore[arg-type]
        return MagicMock()

    with patch(
        "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
        side_effect=_capture,
    ):
        await _run(run_root=tmp_path)

    assert captured[0]._run_root == tmp_path


async def test_run_passes_argv_to_graph(tmp_path: Path) -> None:
    with patch(
        "ez_ax.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
        new_callable=AsyncMock,
        return_value=MagicMock(),
    ) as mock_run:
        await _run(
            argv=["--session-ref", "s", "--expected-auth-state", "a"],
            run_root=tmp_path,
        )

    call_argv = mock_run.call_args.kwargs["argv"]
    assert "--session-ref" in call_argv
    assert "s" in call_argv
