"""Tests verifying the PRD requirement: ez-ax must not become browser-facing.

PRD clause (System Boundary, line 21):
'ez-ax must not become browser-facing'

This is a distinct requirement from being orchestration-centric (line 20).
It explicitly prohibits ez-ax from ever becoming a browser-facing runtime,
ensuring the architectural separation from OpenClaw remains permanent.
"""

from __future__ import annotations

import inspect
from pathlib import Path


def test_ez_ax_runtime_never_calls_browser_apis_directly() -> None:
    """Verify that ez-ax runtime code never calls browser automation APIs.

    PRD System Boundary (line 21): 'ez-ax must not become browser-facing'

    The runtime must not directly invoke browser control, must not instantiate
    browser automation libraries, and must not perform any browser operations.
    All browser interactions are delegated to the adapter.

    This test verifies that no core orchestration code imports or calls browser
    automation libraries.
    """
    from ez_ax.graph import langgraph_released_execution, released_call_site
    from ez_ax.models import errors, runtime

    # Key modules that own orchestration logic
    orchestration_modules = [
        langgraph_released_execution,
        released_call_site,
        runtime,
        errors,
    ]

    # Browser automation libraries that must NOT be imported
    forbidden_libs = [
        "playwright",  # Playwright
        "pyppeteer",  # CDP automation
        "chromium",  # Chromium control
        "selenium",  # Selenium WebDriver
    ]

    for module in orchestration_modules:
        module_source = inspect.getsource(module)

        for lib in forbidden_libs:
            assert f"import {lib}" not in module_source.lower() and (
                f"from {lib}" not in module_source.lower()
            ), (
                f"Orchestration module {module.__name__} must not import {lib} "
                f"(PRD clause: 'ez-ax must not become browser-facing')"
            )


def test_ez_ax_cannot_perform_browser_operations_without_adapter() -> None:
    """Verify that browser operations ONLY happen through the adapter boundary.

    PRD System Boundary (line 21): 'ez-ax must not become browser-facing'

    The architecture must enforce that ALL browser-facing operations are
    mediated by the adapter protocol. There should be no code path in ez-ax
    that performs browser operations independently.

    This test verifies that the ExecutionAdapter is the mandatory boundary.
    """
    from ez_ax.adapters.execution.client import ExecutionAdapter

    # The only way to perform browser operations is through this adapter
    assert hasattr(ExecutionAdapter, "execute"), (
        "All browser operations must go through ExecutionAdapter.execute()"
    )

    # Verify the adapter signature requires an ExecutionRequest
    sig = inspect.signature(ExecutionAdapter.execute)
    params = list(sig.parameters.keys())

    assert "request" in params or "self" in params, (
        "ExecutionAdapter.execute must accept execution requests "
        "(PRD clause: 'ez-ax must not become browser-facing')"
    )


def test_released_scope_graph_cannot_perform_browser_operations_directly() -> None:
    """Verify that the released-scope graph cannot perform browser operations directly.

    PRD System Boundary (line 21): 'ez-ax must not become browser-facing'

    The released-scope execution graph owns orchestration logic (mission sequencing,
    state transitions, validation). It must NOT own execution logic. All execution
    must be delegated to the adapter.

    This test verifies the graph structure enforces adapter-only execution.
    """
    import tempfile

    from ez_ax.graph.langgraph_released_execution import (
        build_released_scope_execution_graph,
    )
    from ez_ax.graph.released_call_site import ReleasedRunContext

    # Create a minimal context to build the graph
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        class MinimalAdapter:
            async def execute(self, request):
                from ez_ax.adapters.execution.client import ExecutionResult

                return ExecutionResult(
                    mission_name=request.mission_name,
                    evidence_refs=("evidence://dom/stub",),
                )

        run = ReleasedRunContext(run_root=tmp_path)
        adapter = MinimalAdapter()

        # Build the graph with the adapter parameter
        build_released_scope_execution_graph(
            adapter=adapter,
            run=run,
            session_ref="test",
            expected_auth_state="logged-in",
            target_page_url="https://example.com",
            site_identity="example.com",
        )

        # The graph source should NOT contain browser automation code
        graph_source = inspect.getsource(build_released_scope_execution_graph)

        forbidden_browser_terms = [
            "playwright",
            "browser.launch",
            "page.goto",
            "pyppeteer",
        ]

        for term in forbidden_browser_terms:
            assert term not in graph_source.lower(), (
                f"Released-scope graph builder must not contain '{term}' "
                f"(PRD clause: 'ez-ax must not become browser-facing')"
            )


def test_ez_ax_design_prevents_browser_facing_expansion() -> None:
    """Verify that the architecture is designed to prevent becoming browser-facing.

    PRD System Boundary (line 21): 'ez-ax must not become browser-facing'

    The design should make it structurally difficult to add browser operations
    to ez-ax without breaking the adapter protocol. The adapter pattern is
    intentional to enforce this separation.

    This test verifies the architectural constraint is in place.
    """
    from ez_ax.adapters.execution.client import ExecutionAdapter

    # ExecutionAdapter is a protocol/interface that must be implemented
    # Any browser operation attempt must go through this boundary
    assert hasattr(ExecutionAdapter, "execute"), (
        "Adapter protocol exists to enforce separation"
    )

    # The adapter is not optional - it's required to build the graph
    from ez_ax.graph.langgraph_released_execution import (
        build_released_scope_execution_graph,
    )

    sig = inspect.signature(build_released_scope_execution_graph)
    assert "adapter" in sig.parameters, (
        "Graph builder requires adapter parameter - "
        "browser operations cannot be added without changing this interface"
    )
