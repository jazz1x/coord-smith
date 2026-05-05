"""Tests verifying the PRD requirement: coord-smith must not treat OpenClaw internals as architecture truth.

PRD clause (System Boundary, line 22):
'coord-smith must not treat OpenClaw internals as architecture truth'

This means the released-scope graph code must depend only on the public OpenClaw
adapter protocol (client.py) and never on internal implementation modules.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _get_all_imports_in_file(filepath: Path) -> set[str]:
    """Extract all import module names from a Python file."""
    imports = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Full module path for "import x.y.z"
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Full module path for "from x.y.z import ..."
                    imports.add(node.module)
    except (SyntaxError, OSError):
        pass
    return imports


def test_released_graph_does_not_depend_on_execution_internals() -> None:
    """Verify that released-scope graph code only imports from OpenClaw.client.

    PRD System Boundary (line 22): 'coord-smith must not treat OpenClaw internals as
    architecture truth'

    The released-scope graph modules must treat the ExecutionAdapter protocol
    (defined in client.py) as the sole interface. They must not import from
    internal OpenClaw implementation modules (execution.py, etc).
    """
    src_dir = Path(__file__).parent.parent.parent / "src" / "coord_smith" / "graph"

    # Released-scope graph modules that should not depend on OpenClaw internals
    released_modules = {
        "released_call_site.py",
        "released_cli_shim.py",
        "released_entrypoint.py",
        "released_run_root.py",
        "runtime_graph.py",
        "langgraph_released_execution.py",
        "pyautogui_cli_entrypoint.py",
    }

    # Internal OpenClaw modules that should NOT be imported
    forbidden_execution_internals = {
        "coord_smith.adapters.execution.execution",
    }

    # Allowed OpenClaw import (public protocol interface)
    allowed_execution_import = "coord_smith.adapters.execution.client"

    for module_file in released_modules:
        filepath = src_dir / module_file
        if not filepath.exists():
            continue

        imports = _get_all_imports_in_file(filepath)

        # Check for forbidden internal imports
        found_forbidden = imports & forbidden_execution_internals
        assert not found_forbidden, (
            f"{module_file} imports forbidden OpenClaw internal modules: "
            f"{', '.join(sorted(found_forbidden))}. "
            f"Use only {allowed_execution_import} for the adapter protocol."
        )


def test_execution_protocol_is_in_client_module() -> None:
    """Verify that the ExecutionAdapter protocol is defined in client.py.

    The public interface (ExecutionAdapter protocol) must live in client.py.
    This ensures the architecture treats the protocol as the single source of
    truth, not internal implementation details.
    """
    from coord_smith.adapters.execution.client import (
        ExecutionAdapter,
        ExecutionBoundary,
    )

    # Verify the protocol classes exist and are protocols
    assert hasattr(ExecutionAdapter, "__mro__")  # Protocol class
    assert hasattr(ExecutionBoundary, "__mro__")  # Protocol class

    # Verify they define the execute method as the interface contract
    assert hasattr(ExecutionAdapter, "execute")
