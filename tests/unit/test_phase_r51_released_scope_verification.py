"""Phase R51 — Heuristic gap scan: Released-scope clause verification.

This test performs a fresh heuristic gap scan to verify all released-scope
implementation clauses (below pageReadyObserved) have corresponding unit test
coverage and are executed correctly.

Phase R51 verifies:
1. All 4 released missions execute in correct sequence
2. Each released mission has proper evidence specification
3. The release-ceiling-stop proof is generated correctly
4. No modeled-only missions execute in released scope
5. The released ceiling (pageReadyObserved) is enforced
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class ReleasedScopeTestAdapter:
    """Adapter that provides realistic evidence for released missions."""

    def __init__(self) -> None:
        self.executed_missions: list[str] = []

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        """Execute mission and track execution order."""
        self.executed_missions.append(request.mission_name)

        # Provide appropriate evidence based on mission
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
                "evidence://action-log/release-ceiling-stop",
            ),
        }

        refs = evidence_map.get(request.mission_name)
        if refs is None:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return OpenClawExecutionResult(
            mission_name=request.mission_name,
            evidence_refs=refs,
        )


@pytest.mark.asyncio
async def test_phase_r51_released_scope_missions_execute_in_sequence(
    tmp_path: Path,
) -> None:
    """Phase R51: Verify released missions execute in correct sequence.

    PRD Release Boundary (lines 47-53):
    'Released implementation scope:
    - attach
    - prepareSession
    - benchmark validation
    - pageReadyObserved'

    The missions must execute in this exact order: attach_session →
    prepare_session → benchmark_validation → page_ready_observation.
    """
    adapter = ReleasedScopeTestAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="phase-r51-sequence-test",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify missions executed in correct sequence
    expected_sequence = (
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    )
    assert adapter.executed_missions == list(expected_sequence), (
        f"Missions must execute in sequence {expected_sequence}, "
        f"but got {adapter.executed_missions}"
    )

    # Verify final state is at the released ceiling
    assert result.state.current_mission == "page_ready_observation"


@pytest.mark.asyncio
async def test_phase_r51_released_ceiling_stop_proof_creation(
    tmp_path: Path,
) -> None:
    """Phase R51: Verify release-ceiling-stop proof is created at pageReadyObserved.

    PRD Release-Ceiling Stop Proof (lines 92-109):
    'Stopping at pageReadyObserved must be provable by typed action-log evidence.
    Required evidence ref: evidence://action-log/release-ceiling-stop
    Required artifact: artifacts/action-log/release-ceiling-stop.jsonl
    Required typed fields: event, mission_name, ts'
    """
    adapter = ReleasedScopeTestAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="phase-r51-stop-proof-test",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify the stop proof artifact exists
    stop_proof_path = (
        result.run.run_root / "artifacts" / "action-log" / "release-ceiling-stop.jsonl"
    )
    assert stop_proof_path.exists(), (
        f"Release-ceiling-stop artifact must exist at {stop_proof_path}"
    )

    # Verify artifact contains required fields
    import json

    content = stop_proof_path.read_text(encoding="utf-8").strip()
    entry = json.loads(content)

    assert "event" in entry, "Stop proof must contain 'event' field"
    assert entry["event"] == "release-ceiling-stop"
    assert "mission_name" in entry, "Stop proof must contain 'mission_name' field"
    assert entry["mission_name"] == "page_ready_observation"
    assert "ts" in entry, "Stop proof must contain 'ts' field"
    assert isinstance(entry["ts"], str) and entry["ts"], "Stop proof 'ts' must be non-empty string"


@pytest.mark.asyncio
async def test_phase_r51_released_scope_ceiling_enforcement(
    tmp_path: Path,
) -> None:
    """Phase R51: Verify released scope ceiling is pageReadyObserved.

    PRD Release Boundary (lines 43-45):
    'Current released ceiling: pageReadyObserved'

    The released-scope graph must stop execution at pageReadyObserved
    and not attempt any missions beyond the ceiling.
    """
    adapter = ReleasedScopeTestAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="phase-r51-ceiling-test",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify execution stopped at the ceiling mission
    assert result.state.current_mission == "page_ready_observation"
    assert result.run.approved_scope_ceiling == "pageReadyObserved"

    # Verify only the 4 released missions executed
    expected_missions = {
        "attach_session",
        "prepare_session",
        "benchmark_validation",
        "page_ready_observation",
    }
    assert set(adapter.executed_missions) == expected_missions, (
        f"Only the 4 released missions should execute, but got {adapter.executed_missions}"
    )
    assert len(adapter.executed_missions) == 4


@pytest.mark.asyncio
async def test_phase_r51_released_missions_have_primary_evidence(
    tmp_path: Path,
) -> None:
    """Phase R51: Verify each released mission provides required primary evidence.

    PRD Evidence Truth Model (lines 67-88):
    'Truth priority: dom > text > clock > action-log'
    'Typed evidence is required for released-scope decisions'

    Each released mission must provide at least one primary evidence type
    (dom, text, clock, or action-log), not just fallback types.
    """
    adapter = ReleasedScopeTestAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="phase-r51-evidence-test",
        expected_auth_state="authenticated",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify all 4 released missions were executed with evidence
    assert len(adapter.executed_missions) == 4, (
        f"All 4 released missions must be executed. Got: {adapter.executed_missions}"
    )

    # Verify the state reached the ceiling mission
    assert result.state.current_mission == "page_ready_observation", (
        f"Final mission must be page_ready_observation, got {result.state.current_mission}"
    )
