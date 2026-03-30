"""Verify console-script entry points resolve to the correct callables."""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path


def _load_pyproject_scripts() -> dict[str, str]:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    return data.get("project", {}).get("scripts", {})


def test_ez_ax_console_script_callable_resolves() -> None:
    scripts = _load_pyproject_scripts()
    assert "ez-ax" in scripts
    module_path, _, attr = scripts["ez-ax"].rpartition(":")
    mod = importlib.import_module(module_path)
    func = getattr(mod, attr)
    assert callable(func)


def test_ez_ax_autoloop_console_script_callable_resolves() -> None:
    scripts = _load_pyproject_scripts()
    assert "ez-ax-autoloop" in scripts
    module_path, _, attr = scripts["ez-ax-autoloop"].rpartition(":")
    mod = importlib.import_module(module_path)
    func = getattr(mod, attr)
    assert callable(func)


def test_pyproject_scripts_point_to_expected_modules() -> None:
    scripts = _load_pyproject_scripts()
    assert scripts["ez-ax"] == "ez_ax.graph.pyautogui_cli_entrypoint:main"
    assert scripts["ez-ax-autoloop"] == "ez_ax.rag.autoloop_runner:main"
