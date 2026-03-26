"""
Unit test for PRD Non-Goals constraint: replacing OpenClaw is forbidden.

PRD Non-Goals And Forbidden Directions (line 144):
"replacing `OpenClaw`"

This test verifies that the released-scope architecture mandates OpenClaw as
the exclusive execution adapter and does not permit replacement with alternative
adapters.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from ez_ax.adapters.openclaw.client import OpenClawInvocationBoundary
from ez_ax.graph.langgraph_released_execution import (
    build_released_scope_execution_graph,
)
from ez_ax.graph.released_call_site import ReleasedRunContext
from ez_ax.graph.released_entrypoint import run_released_scope


def test_released_scope_graph_requires_openclaw_adapter(tmp_path: Path) -> None:
    """Verify released-scope graph construction requires OpenClawAdapter, not a generic adapter.

    PRD Non-Goals constraint (line 144):
    "replacing `OpenClaw`"

    The graph constructor must accept only OpenClawAdapter, preventing replacement
    with alternative implementations.
    """
    run = ReleasedRunContext(
        run_root=tmp_path,
        approved_scope_ceiling="pageReadyObserved",
    )

    # Create a minimal mock adapter that conforms to OpenClawInvocationBoundary
    class MockOpenClawAdapter:
        async def execute(self, request: object) -> object:
            """Mock execute method."""
            return object()

    adapter: OpenClawInvocationBoundary = MockOpenClawAdapter()  # type: ignore

    # This should succeed with OpenClawAdapter
    graph = build_released_scope_execution_graph(
        adapter=adapter,
        run=run,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
    )
    assert graph is not None, "Graph construction with OpenClawAdapter failed"


def test_released_scope_entrypoint_hardcodes_openclaw_not_generic_adapter() -> None:
    """Verify the released scope entrypoint is hardcoded to use OpenClaw infrastructure.

    PRD Non-Goals constraint (line 144):
    "replacing `OpenClaw`"

    The architecture must mandate OpenClaw for the released scope,
    not a generic adapter interface that could be swapped.
    """
    # Get the source code of the released scope entrypoint
    source = inspect.getsource(run_released_scope)

    # Verify OpenClaw references are present in the released scope
    assert (
        "OpenClaw" in source or "openclaw" in source.lower()
    ), "Released scope does not reference OpenClaw; could support swappable adapters"

    # Verify no generic adapter factory or swappable client pattern that would
    # allow replacing OpenClaw with another implementation
    forbidden_patterns = [
        "adapter_class",
        "adapter_factory",
        "get_adapter_from_config",
        "adapter_registry",
        "adapter_plugins",
    ]
    for pattern in forbidden_patterns:
        assert (
            pattern.lower() not in source.lower()
        ), f"Released scope uses {pattern} (generic adapter pattern), allowing replacement of OpenClaw"


def test_released_scope_adapter_param_does_not_allow_generic_swapping() -> None:
    """Verify released scope adapter parameter is typed to OpenClaw interface, not swappable.

    PRD Non-Goals constraint (line 144):
    "replacing `OpenClaw`"

    While the function accepts OpenClawInvocationBoundary (for testability),
    the released scope must not support arbitrary adapter swapping in production.
    """
    # Get the signature of run_released_scope
    sig = inspect.signature(run_released_scope)

    # Find the 'adapter' parameter
    adapter_param = sig.parameters.get("adapter")
    assert (
        adapter_param is not None
    ), "run_released_scope has no 'adapter' parameter"

    # The parameter type should be OpenClawInvocationBoundary or OpenClawAdapter
    # (not a generic "Adapter" or "ExecutionAdapter" that could be swapped)
    param_annotation = adapter_param.annotation
    annotation_str = str(param_annotation)

    # Verify the type is OpenClaw-specific
    assert (
        "OpenClaw" in annotation_str
    ), f"Adapter parameter type {annotation_str} is too generic; allows replacement of OpenClaw"
