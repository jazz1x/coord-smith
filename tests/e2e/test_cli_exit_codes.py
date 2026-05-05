"""E2E verification of CLI exit codes 0, 1, 2, and 3.

Exit code contract (from pyautogui_cli_entrypoint.py):
  0 — normal success
  1 — unhandled runtime error
  2 — ExecutionTransportError (preflight permission denied)
  3 — ConfigError (missing / invalid recipe)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from coord_smith.adapters.pyautogui_adapter import PyAutoGUIAdapter
from coord_smith.graph.pyautogui_cli_entrypoint import main
from coord_smith.models.errors import AccessibilityPermissionDenied


def test_main_exits_0_on_successful_run(tmp_path: Path) -> None:
    """Full CLI run with mocked pyautogui must exit 0."""
    from PIL import Image

    def fake_screenshot() -> Image.Image:
        return Image.new("RGB", (800, 600), color="white")

    FakeSize = type("Point", (), {"width": 1920, "height": 1080})
    FakePos = type("Point", (), {"x": 0, "y": 0})

    argv = [
        "--session-ref", "session-cli-e2e",
        "--expected-auth-state", "authenticated",
        "--target-page-url", "https://tickets.interpark.com/goods/26003199",
        "--site-identity", "interpark",
    ]

    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch("pyautogui.screenshot", side_effect=fake_screenshot),
        patch("pyautogui.click"),
        patch("pyautogui.position", return_value=FakePos()),
        patch("pyautogui.size", return_value=FakeSize()),
    ):
        exit_code = main(argv=argv)

    assert exit_code == 0, f"Expected exit 0, got {exit_code}"


def test_main_exits_2_on_accessibility_permission_denied() -> None:
    """Preflight AccessibilityPermissionDenied must produce exit 2."""
    with patch.object(
        PyAutoGUIAdapter,
        "preflight",
        new_callable=AsyncMock,
        side_effect=AccessibilityPermissionDenied("no accessibility permission"),
    ):
        exit_code = main(argv=[])

    assert exit_code == 2, f"Expected exit 2, got {exit_code}"


def test_main_exits_3_on_missing_recipe_file(tmp_path: Path) -> None:
    """A --click-recipe path that does not exist must produce exit 3."""
    missing = tmp_path / "nonexistent-recipe.json"
    exit_code = main(argv=["--click-recipe", str(missing)])
    assert exit_code == 3, f"Expected exit 3, got {exit_code}"


def test_main_exits_1_on_unhandled_runtime_error() -> None:
    """An unhandled exception from the run must produce exit 1."""
    with (
        patch.object(PyAutoGUIAdapter, "preflight", new_callable=AsyncMock),
        patch(
            "coord_smith.graph.pyautogui_cli_entrypoint.run_released_scope_from_argv_env",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected failure"),
        ),
    ):
        exit_code = main(argv=[])

    assert exit_code == 1, f"Expected exit 1, got {exit_code}"
