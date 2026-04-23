"""Real-binary integration tests for PyAutoGUIAdapter.

These tests invoke pyautogui without mocks. They require:
- macOS Accessibility permission for the host terminal app (mouse control)
- macOS Screen Recording permission for the host terminal app (screenshot)
- A real display (not headless CI)

Marker: `real`. Default pytest invocation skips them (`addopts = -m 'not real'`
in pyproject.toml). Run with `uv run pytest -m real` on a permission-granted
local machine.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.pyautogui_adapter import PyAutoGUIAdapter

pytestmark = pytest.mark.real


def test_preflight_succeeds_on_permission_granted_host() -> None:
    """preflight() must return without raising when permissions are granted."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        adapter = PyAutoGUIAdapter(run_root=Path(tmp))
        adapter.preflight()  # raises on permission failure; silence = pass


def test_screenshot_produces_real_png_file(tmp_path: Path) -> None:
    """_capture_screenshot must write a valid PNG (magic bytes 89 50 4e 47)."""
    adapter = PyAutoGUIAdapter(run_root=tmp_path)
    adapter._capture_screenshot("real-integration-smoke")

    path = tmp_path / "artifacts" / "screenshot" / "real-integration-smoke.png"
    assert path.is_file(), f"screenshot not written at {path}"
    assert path.stat().st_size > 1000, "screenshot suspiciously small"
    with path.open("rb") as f:
        magic = f.read(8)
    assert magic == b"\x89PNG\r\n\x1a\n", f"not a valid PNG: {magic.hex()}"
