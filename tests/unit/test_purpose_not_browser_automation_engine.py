"""Test that coord-smith is not a browser automation engine.

PRD requirement (Purpose section, line 15):
'It is not a browser automation engine.'

This means that:
1. The released-scope runtime does not perform browser control operations
2. The runtime does not import or use browser automation libraries
3. Browser operations are delegated to OpenClaw, not performed internally
4. The runtime is orchestration-centric, not browser-control-centric
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest


def _get_project_root() -> Path:
    """Get project root directory."""
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path.cwd()


def _get_all_python_files(directory: Path) -> list[Path]:
    """Get all Python files in a directory recursively."""
    return list(directory.rglob("*.py"))


def _get_imports_from_file(file_path: Path) -> set[str]:
    """Extract all imports from a Python file."""
    imports: set[str] = set()
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
    except (SyntaxError, OSError):
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)

    return imports


def test_released_scope_runtime_does_not_import_browser_automation_libraries() -> None:
    """Verify that released-scope runtime code never imports browser automation libs.

    Browser automation libraries include Playwright, Selenium, Pyppeteer, etc.
    The runtime should not import these because it is not a browser automation engine.
    """
    project_root = _get_project_root()
    src_dir = project_root / "src"

    if not src_dir.exists():
        pytest.skip("src directory not found")

    browser_automation_libraries = {
        "playwright",
        "selenium",
        "pyppeteer",
        "webdriver",
        "wdio",
        "protractor",
    }

    found_imports: set[str] = set()

    for py_file in _get_all_python_files(src_dir):
        imports = _get_imports_from_file(py_file)
        for lib in browser_automation_libraries:
            if any(imp.startswith(lib) for imp in imports):
                found_imports.add(lib)

    assert not found_imports, (
        f"Runtime code must not import browser automation libraries. "
        f"Found imports: {found_imports}"
    )


def test_runtime_graph_does_not_import_browser_automation_libraries() -> None:
    """Verify that the runtime graph modules do not import browser automation libs.

    The runtime should focus on orchestration and state transitions, delegating
    all browser operations to the OpenClaw adapter.
    """
    project_root = _get_project_root()
    graph_dir = project_root / "src" / "coord_smith" / "graph"

    if not graph_dir.exists():
        pytest.skip("graph directory not found")

    browser_automation_libraries = {
        "playwright",
        "selenium",
        "pyppeteer",
    }

    found_imports: dict[str, set[str]] = {}

    for py_file in _get_all_python_files(graph_dir):
        imports = _get_imports_from_file(py_file)
        for lib in browser_automation_libraries:
            if any(imp.startswith(lib) for imp in imports):
                if py_file.name not in found_imports:
                    found_imports[py_file.name] = set()
                found_imports[py_file.name].add(lib)

    assert not found_imports, (
        f"Runtime graph code must not import browser automation libraries. "
        f"Found in {found_imports}"
    )


def test_released_scope_delegates_browser_ops_through_adapter() -> None:
    """Verify that released-scope execution is orchestration-centric.

    The released scope should:
    - Define and manage mission sequences
    - Track state through graph transitions
    - Delegate all browser operations to OpenClaw adapter
    - Never perform browser automation directly
    """
    project_root = _get_project_root()
    released_entrypoint = (
        project_root / "src" / "coord_smith" / "graph" / "released_entrypoint.py"
    )

    if not released_entrypoint.exists():
        pytest.skip("released_entrypoint.py not found")

    with open(released_entrypoint, encoding="utf-8") as f:
        content = f.read()

    # Verify the entrypoint uses an adapter for browser operations
    assert "adapter" in content.lower(), (
        "Released entrypoint must use adapter for browser operations"
    )

    # Verify no direct browser library imports
    browser_libs = ["playwright", "selenium", "pyppeteer"]
    for lib in browser_libs:
        assert f"import {lib}" not in content, (
            f"Released entrypoint must not directly import {lib}"
        )


def test_purpose_confirms_orchestration_over_browser_automation() -> None:
    """Verify that the architecture demonstrates orchestration, not browser automation.

    Evidence that runtime is orchestration-centric:
    1. Missions are defined as orchestration concepts
    2. State management tracks mission progress
    3. OpenClaw is the sole executor of browser operations
    4. Runtime itself contains no browser control logic
    """
    from coord_smith.graph.released_entrypoint import run_released_scope

    # Verify that the runtime accepts an adapter (orchestration pattern)
    # rather than implementing browser control directly
    assert callable(run_released_scope), (
        "Runtime must be callable for orchestration"
    )

    # Check function signature includes adapter parameter
    sig = inspect.signature(run_released_scope)
    assert "adapter" in sig.parameters, (
        "Released scope must accept adapter parameter for orchestration delegation"
    )
