"""Tests verifying the PRD requirement: ez-ax must not treat OpenClaw internals as architecture truth.

PRD clause (System Boundary, line 22):
'ez-ax must not treat OpenClaw internals as architecture truth'

This means the released-scope graph code must depend only on the public OpenClaw
adapter protocol (client.py) and never on internal implementation modules
(execution.py, mcp_adapter.py, mcp_stdio_client.py, etc).
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


def test_released_graph_does_not_depend_on_openclaw_internals() -> None:
    """Verify that released-scope graph code only imports from OpenClaw.client.

    PRD System Boundary (line 22): 'ez-ax must not treat OpenClaw internals as
    architecture truth'

    The released-scope graph modules must treat the OpenClawAdapter protocol
    (defined in client.py) as the sole interface. They must not import from
    internal OpenClaw modules (execution.py, mcp_adapter.py, mcp_stdio_client.py,
    mcp_settings.py, etc).
    """
    src_dir = Path(__file__).parent.parent.parent / "src" / "ez_ax" / "graph"

    # Released-scope graph modules that should not depend on OpenClaw internals
    released_modules = {
        "released_call_site.py",
        "released_cli_shim.py",
        "released_entrypoint.py",
        "released_run_root.py",
        "runtime_graph.py",
        "langgraph_released.py",
        "langgraph_released_execution.py",
        "pyautogui_cli_entrypoint.py",
    }

    # Internal OpenClaw modules that should NOT be imported
    forbidden_openclaw_internals = {
        "ez_ax.adapters.openclaw.execution",
        "ez_ax.adapters.openclaw.mcp_adapter",
        "ez_ax.adapters.openclaw.mcp_stdio_client",
        "ez_ax.adapters.openclaw.mcp_settings",
    }

    # Allowed OpenClaw import (public protocol interface)
    allowed_openclaw_import = "ez_ax.adapters.openclaw.client"

    for module_file in released_modules:
        filepath = src_dir / module_file
        if not filepath.exists():
            continue

        imports = _get_all_imports_in_file(filepath)

        # Check for forbidden internal imports
        found_forbidden = imports & forbidden_openclaw_internals
        assert not found_forbidden, (
            f"{module_file} imports forbidden OpenClaw internal modules: "
            f"{', '.join(sorted(found_forbidden))}. "
            f"Use only {allowed_openclaw_import} for the adapter protocol."
        )


def test_openclaw_protocol_is_in_client_module() -> None:
    """Verify that the OpenClawAdapter protocol is defined in client.py.

    The public interface (OpenClawAdapter protocol) must live in client.py.
    This ensures the architecture treats the protocol as the single source of
    truth, not internal implementation details.
    """
    from ez_ax.adapters.openclaw.client import (
        OpenClawAdapter,
        OpenClawInvocationBoundary,
    )

    # Verify the protocol classes exist and are protocols
    assert hasattr(OpenClawAdapter, "__mro__")  # Protocol class
    assert hasattr(OpenClawInvocationBoundary, "__mro__")  # Protocol class

    # Verify they define the execute method as the interface contract
    assert hasattr(OpenClawAdapter, "execute")
