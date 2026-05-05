"""Test that OpenClaw is the only browser-facing execution actor.

PRD System Boundary section (line 19):
'`OpenClaw` is the only browser-facing execution actor'

This clause requires:
1. All browser-facing operations are exclusively delegated to OpenClaw
2. No alternate browser execution mechanisms exist
3. The released-scope graph enforces OpenClaw-only execution
"""

from __future__ import annotations

import ast
from pathlib import Path

from coord_smith.adapters.execution.client import ExecutionRequest, ExecutionResult
from coord_smith.graph.langgraph_released_execution import (
    run_released_scope_via_langgraph,
)


class SingleExecutionPathAdapter:
    """Adapter that enforces and tracks that it is the only execution mechanism."""

    def __init__(self) -> None:
        self.execution_calls: list[ExecutionRequest] = []

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Record this as the sole execution call."""
        self.execution_calls.append(request)

        # Return appropriate evidence based on mission
        # Each mission needs primary and fallback evidence per the spec
        evidence_map: dict[str, tuple[str, ...]] = {
            "attach_session": (
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ),
            "prepare_session": (
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
            "benchmark_validation": (
                "evidence://dom/target-page-entered",
                "evidence://action-log/enter-target-page",
            ),
            "page_ready_observation": (
                "evidence://dom/page-shell-ready",
                "evidence://action-log/page-ready-observed",
            ),
            "sync_observation": (
                "evidence://clock/server-time-synced",
                "evidence://action-log/sync-observed",
            ),
            "target_actionability_observation": (
                "evidence://dom/target-actionable",
                "evidence://action-log/target-actionable-observed",
            ),
            "armed_state_entry": (
                "evidence://text/armed-state-entered",
                "evidence://action-log/armed-state",
            ),
            "trigger_wait": (
                "evidence://clock/trigger-received",
                "evidence://action-log/trigger-wait-complete",
            ),
            "click_dispatch": (
                "evidence://dom/click-target-clicked",
                "evidence://action-log/click-dispatched",
            ),
            "click_completion": (
                "evidence://dom/click-effect-confirmed",
                "evidence://action-log/click-completed",
            ),
            "success_observation": (
                "evidence://dom/success-observed",
                "evidence://action-log/success-observation",
            ),
            "run_completion": (
                "evidence://action-log/release-ceiling-stop",
            ),
        }
        refs = evidence_map.get(request.mission_name, ())
        return ExecutionResult(mission_name=request.mission_name, evidence_refs=refs)


def test_openclaw_is_sole_execution_mechanism(tmp_path: Path) -> None:
    """Verify OpenClaw is the exclusive execution actor.

    PRD System Boundary (line 19):
    '`OpenClaw` is the only browser-facing execution actor'

    This test confirms:
    1. The released-scope graph delegates ALL execution to the provided adapter
    2. NO internal browser-facing mechanisms exist
    3. The adapter parameter is the ONLY execution path
    """
    adapter = SingleExecutionPathAdapter()

    import asyncio

    asyncio.run(
        run_released_scope_via_langgraph(
            adapter=adapter,
            session_ref="test-session",
            expected_auth_state="logged-in",
            target_page_url="https://example.com",
            site_identity="example.com",
            base_dir=tmp_path,
        )
    )

    # Verify the adapter was the SOLE execution path
    assert len(adapter.execution_calls) == 12, (
        "OpenClaw (via adapter) must be the only execution actor. "
        "Expected exactly 12 mission executions through the adapter."
    )

    # Verify all 12 missions were executed in order
    mission_names = [call.mission_name for call in adapter.execution_calls]
    expected_sequence = [
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
        "sync_observation",
        "target_actionability_observation",
        "armed_state_entry",
        "trigger_wait",
        "click_dispatch",
        "click_completion",
        "success_observation",
        "run_completion",
    ]
    assert mission_names == expected_sequence, (
        f"OpenClaw must execute all missions in sequence. "
        f"Expected: {expected_sequence}, Got: {mission_names}"
    )


def test_no_alternate_browser_execution_paths_exist() -> None:
    """Verify the released-scope runtime has no alternate browser execution paths.

    PRD System Boundary (line 19):
    '`OpenClaw` is the only browser-facing execution actor'

    This test scans the released-scope runtime source to confirm:
    1. No direct browser library imports (Playwright, Selenium, etc.)
    2. No alternate execution mechanisms
    3. All browser operations are routed through the ExecutionAdapter interface
    """
    # Get the released-scope runtime path
    runtime_path = (
        Path(__file__).parent.parent.parent
        / "src/coord_smith/graph/langgraph_released_execution.py"
    )

    with open(runtime_path) as f:
        source = f.read()

    # Parse the source code
    tree = ast.parse(source)

    # Forbidden imports that would indicate alternate browser execution paths
    forbidden_imports = {
        "playwright",
        "selenium",
        "pyppeteer",
        "cdp",
        "chromium",
        "webdriver",
    }

    found_forbidden_imports = set()

    # Check all imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.lower()
                for forbidden in forbidden_imports:
                    if forbidden in module:
                        found_forbidden_imports.add(module)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module = node.module.lower()
                for forbidden in forbidden_imports:
                    if forbidden in module:
                        found_forbidden_imports.add(module)

    assert not found_forbidden_imports, (
        "Released-scope runtime must not import alternate browser execution libraries. "
        f"Found forbidden imports: {found_forbidden_imports}. "
        "OpenClaw (via ExecutionAdapter) is the only permitted browser execution mechanism."
    )


def test_execution_adapter_is_required_parameter() -> None:
    """Verify the ExecutionAdapter is a required parameter with no fallback.

    PRD System Boundary (line 19):
    '`OpenClaw` is the only browser-facing execution actor'

    This test confirms:
    1. The released-scope runtime cannot be instantiated without an adapter
    2. There is no built-in fallback execution mechanism
    3. OpenClaw (via adapter) is mandatory, not optional
    """
    # Import the function signature
    from inspect import Parameter, signature

    from coord_smith.graph.langgraph_released_execution import (
        run_released_scope_via_langgraph,
    )

    sig = signature(run_released_scope_via_langgraph)
    params = sig.parameters

    # Verify adapter is a required parameter (no default value)
    assert "adapter" in params, (
        "run_released_scope_via_langgraph must have an 'adapter' parameter"
    )

    adapter_param = params["adapter"]
    assert adapter_param.default == Parameter.empty, (
        "The 'adapter' parameter must be required (no default). "
        "This ensures OpenClaw is the ONLY execution mechanism available."
    )
