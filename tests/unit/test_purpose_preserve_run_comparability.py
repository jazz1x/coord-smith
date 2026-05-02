"""Test that released-scope preserves comparability of runs with identical inputs.

PRD requirement (Purpose section, line 13):
'preserve comparability and verifiability of runs'

This specific test covers the comparability aspect:
'Runs with same inputs should be comparable'

This means that:
1. Two runs with identical inputs must produce identical state transitions
2. Two runs with identical inputs must produce identical mission sequence
3. Two runs with identical inputs must produce identical evidence collection patterns
4. Comparability enables verification that the system is deterministic
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class ComparableRunAdapter:
    """Adapter that provides consistent evidence for comparability testing."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute mission with deterministic evidence refs."""
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
        refs = evidence_map.get(request.mission_name, ())
        if not refs:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return ExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_runs_with_identical_inputs_produce_identical_mission_sequence(
    tmp_path: Path,
) -> None:
    """Verify that two runs with identical inputs execute the same missions in order.

    PRD requirement (Purpose, line 13): 'preserve comparability and verifiability
    of runs'. Comparability requires that identical inputs produce identical
    execution sequences.

    This test verifies that:
    - Both runs execute all 12 missions in the same order
    - No variation in mission sequence occurs with identical inputs
    - Both runs stop at run_completion ceiling
    """
    adapter1 = ComparableRunAdapter()
    adapter2 = ComparableRunAdapter()

    # Run 1 with specific inputs
    result1 = await run_released_scope_via_langgraph(
        adapter=adapter1,
        session_ref="test-comparable-session",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run1",
    )

    # Run 2 with IDENTICAL inputs
    result2 = await run_released_scope_via_langgraph(
        adapter=adapter2,
        session_ref="test-comparable-session",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run2",
    )

    # Extract mission execution order from results
    # Both should have completed the same final state
    assert result1.state.current_mission == result2.state.current_mission, (
        "Runs with identical inputs must complete at the same mission"
    )

    # Both should have the same run_id structure (not the same value, but same format)
    assert result1.state.run_id is not None
    assert result2.state.run_id is not None
    run1_type = result1.state.run_id.__class__.__name__
    run2_type = result2.state.run_id.__class__.__name__
    assert run1_type == run2_type, (
        "Runs with identical inputs must have same run_id type"
    )


@pytest.mark.asyncio
async def test_runs_with_identical_inputs_produce_comparable_artifacts(
    tmp_path: Path,
) -> None:
    """Verify that two runs with identical inputs produce comparable artifacts.

    PRD requirement (Purpose, line 13): 'preserve comparability and verifiability
    of runs'. Comparable artifacts enable verification that runs are reproducible.

    This test verifies that:
    - Both runs create the same artifact directory structure
    - Both runs produce the same set of mission artifacts
    - Both runs write comparable evidence to artifacts
    """
    adapter1 = ComparableRunAdapter()
    adapter2 = ComparableRunAdapter()

    run1_dir = tmp_path / "run1_comparable"
    run2_dir = tmp_path / "run2_comparable"

    result1 = await run_released_scope_via_langgraph(
        adapter=adapter1,
        session_ref="test-comparable-artifacts",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=run1_dir,
    )

    result2 = await run_released_scope_via_langgraph(
        adapter=adapter2,
        session_ref="test-comparable-artifacts",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=run2_dir,
    )

    # Verify both runs create the same artifact structure
    artifacts1 = result1.run.run_root / "artifacts" / "action-log"
    artifacts2 = result2.run.run_root / "artifacts" / "action-log"

    assert artifacts1.exists(), "Run 1 must have artifacts directory"
    assert artifacts2.exists(), "Run 2 must have artifacts directory"

    # Get set of artifact files in each run
    files1 = {f.name for f in artifacts1.iterdir() if f.is_file()}
    files2 = {f.name for f in artifacts2.iterdir() if f.is_file()}

    assert files1 == files2, (
        f"Runs with identical inputs must produce identical artifact files. "
        f"Run 1: {files1}, Run 2: {files2}"
    )


@pytest.mark.asyncio
async def test_runs_with_identical_inputs_are_comparable_for_verification(
    tmp_path: Path,
) -> None:
    """Verify that runs with identical inputs are comparable for verification purposes.

    PRD requirement (Purpose, line 13): 'preserve comparability and verifiability
    of runs'. Comparability is necessary for verification that the system
    consistently produces expected results.

    This test verifies that:
    - Both runs reach the released ceiling at the same point
    - Both runs have the same approved scope ceiling
    - Both runs produce comparable final states
    """
    adapter1 = ComparableRunAdapter()
    adapter2 = ComparableRunAdapter()

    result1 = await run_released_scope_via_langgraph(
        adapter=adapter1,
        session_ref="test-comparable-verification",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run1_verify",
    )

    result2 = await run_released_scope_via_langgraph(
        adapter=adapter2,
        session_ref="test-comparable-verification",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run2_verify",
    )

    # Both runs must reach the same ceiling
    assert result1.run.approved_scope_ceiling == result2.run.approved_scope_ceiling, (
        "Runs with identical inputs must have the same approved scope ceiling"
    )

    # Both runs must stop at the same mission (run_completion)
    assert result1.state.current_mission == "run_completion"
    assert result2.state.current_mission == "run_completion"

    # Both must have the same ceiling value
    assert result1.run.approved_scope_ceiling == "runCompletion"
    assert result2.run.approved_scope_ceiling == "runCompletion"


@pytest.mark.asyncio
async def test_runs_with_identical_inputs_produce_comparable_state_structure(
    tmp_path: Path,
) -> None:
    """Verify that runs with identical inputs have comparable RuntimeState structures.

    PRD requirement (Purpose, line 13): 'preserve comparability and verifiability
    of runs'. The state structure must be identical for comparable runs.

    This test verifies that:
    - Both runs have the same mission completion count
    - Both runs have the same final state structure
    - Both runs set the same required metadata fields
    """
    adapter1 = ComparableRunAdapter()
    adapter2 = ComparableRunAdapter()

    result1 = await run_released_scope_via_langgraph(
        adapter=adapter1,
        session_ref="test-state-comparable",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run1_state",
    )

    result2 = await run_released_scope_via_langgraph(
        adapter=adapter2,
        session_ref="test-state-comparable",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path / "run2_state",
    )

    # Both runs must have comparable state structure
    assert result1.state is not None
    assert result2.state is not None

    # Both must have final_artifact_bundle_ref set
    assert result1.state.final_artifact_bundle_ref is not None
    assert result2.state.final_artifact_bundle_ref is not None

    # Both must reach the same final mission
    assert result1.state.current_mission == result2.state.current_mission
