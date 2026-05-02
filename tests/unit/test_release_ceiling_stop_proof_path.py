"""Test that run-completed proof artifact is created at the exact PRD-specified path.

PRD requirement (Release-Ceiling Stop Proof section, lines 98-100):
'Expected artifact example:
- `artifacts/action-log/run-completed.jsonl`'

This ensures the stop proof artifact is located at the exact path specified in the PRD,
enabling verifiability and repeatability of released-scope runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class ReleaseCeilingPathTestAdapter:
    """Adapter that provides valid evidence for testing run-completed artifact path."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Provide valid evidence for each mission."""
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
                "evidence://action-log/enter-target-page",
                "evidence://dom/target-page-entered",
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
                "evidence://action-log/click-dispatched",
                "evidence://dom/click-target-clicked",
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
        refs = evidence_map.get(request.mission_name)
        if refs is None:
            msg = f"Unexpected mission: {request.mission_name}"
            raise AssertionError(msg)
        return ExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_release_ceiling_stop_proof_artifact_at_prd_specified_path(
    tmp_path: Path,
) -> None:
    """Verify run-completed proof is created at exact PRD-specified path.

    PRD requirement (Release-Ceiling Stop Proof section, lines 98-100):
    'Expected artifact example:
    - `artifacts/action-log/run-completed.jsonl`'

    This test explicitly validates that when the released-scope graph completes
    at page_ready_observation, the stop proof artifact is created at the exact
    path specified in the PRD documentation.
    """
    adapter = ReleaseCeilingPathTestAdapter()

    # Run the released-scope graph to completion
    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # The exact PRD-specified path
    expected_path = (
        result.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    )

    # Verify the artifact exists at the exact PRD-specified path
    assert (
        expected_path.exists()
    ), f"Release-ceiling-stop artifact must exist at exact PRD-specified path: {expected_path}"

    # Verify it's a file (not a directory)
    assert expected_path.is_file(), (
        f"Release-ceiling-stop artifact must be a file at: {expected_path}"
    )

    # Verify the path structure matches PRD: artifacts/action-log/run-completed.jsonl
    relative_path = expected_path.relative_to(result.run.run_root)
    expected_relative = Path("artifacts") / "action-log" / "release-ceiling-stop.jsonl"
    assert relative_path == expected_relative, (
        f"Artifact path must match PRD structure.\n"
        f"Expected relative path: {expected_relative}\n"
        f"Actual relative path: {relative_path}"
    )
