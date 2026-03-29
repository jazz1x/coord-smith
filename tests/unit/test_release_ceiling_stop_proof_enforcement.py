"""Test that released-scope graph enforces run-completed proof validation.

PRD requirement (Release-Ceiling Stop Proof section, lines 92-109):
'Stopping at runCompletion must be provable by typed action-log evidence.
If this artifact cannot be resolved or the typed fields are missing, the system
must not claim a correct released-ceiling stop.'

This means the released-scope graph must validate that the stop proof artifact
exists with required typed fields before claiming a successful release-ceiling stop.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.evidence.envelope import validate_release_ceiling_stop_proof
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class StopProofValidationAdapter:
    """Adapter that provides valid evidence refs for all missions."""

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Execute mission and provide required evidence refs."""
        evidence_map: dict[str, tuple[str, ...]] = {
            "attach_session": (
                # Required primary evidence for attach_session
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ),
            "prepare_session": (
                # Required primary evidence for prepare_session
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
            "benchmark_validation": (
                # Required primary evidence for benchmark_validation
                "evidence://action-log/enter-target-page",
                "evidence://dom/target-page-entered",
            ),
            "page_ready_observation": (
                # Required primary evidence for page_ready_observation
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
                "evidence://action-log/run-completed",
                "evidence://text/run-summary",
            ),
        }
        refs = evidence_map.get(request.mission_name, ())
        if not refs:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return ExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_released_scope_graph_creates_stop_proof_artifact(
    tmp_path: Path,
) -> None:
    """Verify that the released-scope graph produces a valid run-completed proof.

    PRD requirement (Release-Ceiling Stop Proof section, lines 92-109):
    'Stopping at runCompletion must be provable by typed action-log evidence.
    If this artifact cannot be resolved or the typed fields are missing, the
    system must not claim a correct released-ceiling stop.'

    The released-scope graph must ensure that:
    1. The run-completed.jsonl artifact is created
    2. It contains the required typed fields: event, mission_name, ts
    3. The artifact can be validated using the standard validator

    This test verifies that when the released-scope graph completes at
    run_completion, the stop proof artifact exists and is valid.
    """
    adapter = StopProofValidationAdapter()

    # Run the released-scope graph through run_completion
    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # The released-scope graph must have completed at page_ready_observation.
    # Now verify the stop proof artifact exists.
    stop_proof_path = (
        result.run.run_root / "artifacts" / "action-log" / "run-completed.jsonl"
    )

    # The stop proof artifact MUST exist for the released-ceiling stop to be valid
    assert stop_proof_path.exists(), (
        "Release-ceiling-stop proof artifact must exist. "
        f"Expected: {stop_proof_path}\n"
        f"PRD requirement (lines 92-109): 'Stopping at runCompletion must be "
        f"provable by typed action-log evidence.'"
    )

    # Verify the artifact has the required typed fields by calling the validator
    try:
        validate_release_ceiling_stop_proof(stop_proof_path)
    except (FileNotFoundError, ValueError) as exc:
        raise AssertionError(
            f"Stop proof artifact failed validation: {exc}\n"
            f"PRD requirement: Release-ceiling-stop artifact must contain:\n"
            f"  - event: 'run-completed'\n"
            f"  - mission_name: 'run_completion'\n"
            f"  - ts: ISO-8601 timestamp"
        ) from exc


@pytest.mark.asyncio
async def test_released_scope_graph_validates_stop_proof_required_fields(
    tmp_path: Path,
) -> None:
    """Verify that released-scope stop proof contains all required typed fields.

    PRD requirement (Release-Ceiling Stop Proof section, lines 102-106):
    'Required typed fields:
    - event
    - mission_name
    - ts'

    This test verifies that when the released-scope graph completes at
    run_completion, the stop proof artifact contains all required fields
    with proper types.
    """
    adapter = StopProofValidationAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify the stop proof artifact exists
    stop_proof_path = (
        result.run.run_root / "artifacts" / "action-log" / "run-completed.jsonl"
    )
    assert stop_proof_path.exists(), (
        f"Release-ceiling-stop artifact must exist at: {stop_proof_path}"
    )

    # Validate the artifact has all required fields
    validate_release_ceiling_stop_proof(stop_proof_path)

    # Additional verification: check field types directly
    import json
    content = stop_proof_path.read_text(encoding="utf-8").strip()
    entry = json.loads(content)

    # Verify all required fields are present with correct types
    assert "event" in entry, "Stop proof must contain 'event' field"
    assert entry["event"] == "run-completed", (
        "Stop proof event must be 'run-completed'"
    )

    assert "mission_name" in entry, "Stop proof must contain 'mission_name' field"
    assert entry["mission_name"] == "run_completion", (
        "Stop proof mission_name must be 'run_completion'"
    )

    assert "ts" in entry, "Stop proof must contain 'ts' (timestamp) field"
    assert isinstance(entry["ts"], str), "Stop proof 'ts' must be a string"
    assert entry["ts"], "Stop proof 'ts' must not be empty"
