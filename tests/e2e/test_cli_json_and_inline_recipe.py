"""E2E verification of --recipe-json / --recipe-yaml / --recipe-stdin / --json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coord_smith.graph.pyautogui_cli_entrypoint import main


def test_main_dry_run_with_recipe_json(tmp_path: Path) -> None:
    argv = [
        "--dry-run",
        "--recipe-json",
        '{"version": 1, "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}]}',
        "--session-ref", "demo",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://example.com",
        "--site-identity", "example",
    ]
    exit_code = main(argv=argv)
    assert exit_code == 0


def test_main_dry_run_with_recipe_yaml(tmp_path: Path) -> None:
    argv = [
        "--dry-run",
        "--recipe-yaml",
        "version: 1\nsteps:\n  - name: click-buy\n    coord: {x: 800, y: 500}",
        "--session-ref", "demo",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://example.com",
        "--site-identity", "example",
    ]
    exit_code = main(argv=argv)
    assert exit_code == 0


def test_main_dry_run_json_emits_run_json_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = [
        "--dry-run",
        "--recipe-json",
        '{"version": 1, "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}]}',
        "--session-ref", "demo",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://example.com",
        "--site-identity", "example",
        "--json",
    ]
    exit_code = main(argv=argv)
    assert exit_code == 0
    captured = capsys.readouterr()
    # The log line goes to stderr; the run.json content goes to stdout.
    assert captured.out
    data = json.loads(captured.out)
    assert data["status"] == "success"
    assert data["exit_code"] == 0
    assert data["step_count"] == 1


def test_main_dry_run_invalid_inline_recipe_exits_3() -> None:
    argv = [
        "--dry-run",
        "--recipe-json",
        '{"version": 1, "steps": [{"name": "click-buy"}]}',
        "--session-ref", "demo",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://example.com",
        "--site-identity", "example",
    ]
    exit_code = main(argv=argv)
    assert exit_code == 3


def test_main_recipe_json_and_click_recipe_mutual_conflict() -> None:
    """Both --recipe-json and --click-recipe present: --recipe-json wins."""
    argv = [
        "--dry-run",
        "--recipe-json",
        '{"version": 1, "steps": [{"name": "click-buy", "coord": {"x": 800, "y": 500}}]}',
        "--click-recipe", "/nonexistent/path.yaml",
        "--session-ref", "demo",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://example.com",
        "--site-identity", "example",
    ]
    exit_code = main(argv=argv)
    assert exit_code == 0
