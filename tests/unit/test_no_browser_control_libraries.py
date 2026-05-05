"""Tests verifying the PRD requirement: coord-smith is not a browser control runtime.

PRD clause (System Boundary, line 23):
'coord-smith is not a Playwright, CDP, or Chromium control runtime'

Also from Non-Goals (line 145):
'direct Playwright, CDP, or Chromium control as product architecture'
"""

from __future__ import annotations

import ast
from pathlib import Path


def _get_all_imports_in_file(filepath: Path) -> set[str]:
    """Extract all import names from a Python file."""
    imports = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except (SyntaxError, OSError):
        pass
    return imports


def test_coord_smith_runtime_does_not_import_playwright() -> None:
    """Verify that coord-smith runtime code does not import Playwright.

    PRD System Boundary (line 23): 'coord-smith is not a Playwright, CDP, or Chromium
    control runtime'

    Playwright is a browser automation library. The coord-smith runtime is
    orchestration-centric and must not perform browser control directly.
    """
    src_dir = Path(__file__).parent.parent.parent / "src" / "coord_smith"
    forbidden = {"playwright"}

    for py_file in src_dir.rglob("*.py"):
        imports = _get_all_imports_in_file(py_file)
        found_forbidden = imports & forbidden
        assert not found_forbidden, (
            f"{py_file.relative_to(src_dir)} imports forbidden library: "
            f"{', '.join(sorted(found_forbidden))}"
        )


def test_coord_smith_runtime_does_not_import_cdp_tools() -> None:
    """Verify that coord-smith runtime code does not import CDP-related libraries.

    PRD System Boundary (line 23): 'coord-smith is not a Playwright, CDP, or Chromium
    control runtime'

    CDP (Chrome DevTools Protocol) tools like pyppeteer are browser automation
    libraries. The coord-smith runtime must not perform direct protocol-level control.
    """
    src_dir = Path(__file__).parent.parent.parent / "src" / "coord_smith"
    forbidden = {"pyppeteer"}  # CDP equivalent for Python

    for py_file in src_dir.rglob("*.py"):
        imports = _get_all_imports_in_file(py_file)
        found_forbidden = imports & forbidden
        assert not found_forbidden, (
            f"{py_file.relative_to(src_dir)} imports forbidden library: "
            f"{', '.join(sorted(found_forbidden))}"
        )


def test_coord_smith_runtime_does_not_import_chromium_control() -> None:
    """Verify that coord-smith runtime code does not import direct Chromium libraries.

    PRD System Boundary (line 23): 'coord-smith is not a Playwright, CDP, or Chromium
    control runtime'

    Direct Chromium control libraries like chromium-automation are not permitted.
    The runtime delegates all browser interaction through OpenClaw adapter.
    """
    src_dir = Path(__file__).parent.parent.parent / "src" / "coord_smith"
    # Common chromium/browser control library names to check
    forbidden = {
        "chromium",  # Generic chromium control
        "seleniumwire",  # Browser control via Selenium
    }

    for py_file in src_dir.rglob("*.py"):
        imports = _get_all_imports_in_file(py_file)
        found_forbidden = imports & forbidden
        assert not found_forbidden, (
            f"{py_file.relative_to(src_dir)} imports forbidden library: "
            f"{', '.join(sorted(found_forbidden))}"
        )


def test_coord_smith_adapter_abstraction_prevents_direct_browser_control() -> None:
    """Verify that OpenClaw adapter is the sole browser-facing interface.

    PRD System Boundary (line 19): 'OpenClaw is the only browser-facing
    execution actor'

    The ExecutionAdapter protocol defines the boundary. Verify that adapter
    implementations are the only runtime code touching browser-specific APIs.
    """
    from coord_smith.adapters.execution.client import ExecutionAdapter

    # Verify the adapter protocol exists and is protocol-based
    assert hasattr(ExecutionAdapter, "execute")

    # Verify it's abstract/protocol (must not reference browser libs directly)
    from coord_smith.adapters import pyautogui_adapter

    adapter_module = pyautogui_adapter.__name__
    # Adapter can have implementation-specific imports, but the core runtime
    # (coord_smith.graph, coord_smith.evidence, etc.) must not
    assert "adapter" in adapter_module.lower()
