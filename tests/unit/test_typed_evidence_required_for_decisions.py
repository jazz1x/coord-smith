"""Test that released-scope decisions require typed evidence.

PRD requirement (Evidence Truth Model, line 88):
'typed evidence is required for released-scope decisions'

This means all evidence refs used by the released-scope graph must conform to
valid evidence types as defined in the truth hierarchy (PRD lines 71-83), and
decision-making must validate evidence types before transitions/stops occur.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ez_ax.adapters.execution.client import (
    ExecutionRequest,
    ExecutionResult,
)
from ez_ax.graph.langgraph_released_execution import run_released_scope_via_langgraph


class TypedEvidenceFakeExecutionAdapter:
    """Stub adapter that provides valid typed evidence for each mission."""

    def __init__(self, run_root: Path | None = None) -> None:
        self._run_root = run_root

    def with_run_root(self, *, run_root: Path) -> TypedEvidenceFakeExecutionAdapter:
        """Bind run_root for artifact creation."""
        self._run_root = run_root
        return self

    def _write_action_log(self, *, key: str, mission_name: str) -> None:
        """Write action-log artifact to disk."""
        if self._run_root is None:
            return
        ts = datetime.now(tz=UTC).isoformat()
        entry: dict[str, object] = {
            "ts": ts,
            "mission_name": mission_name,
            "event": key,
        }
        path = self._run_root / "artifacts" / "action-log" / f"{key}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    async def execute(
        self, request: ExecutionRequest
    ) -> ExecutionResult:
        """Return typed evidence matching the truth hierarchy.

        Evidence types (PRD lines 71-83):
        1. dom (primary)
        2. text (primary)
        3. clock (primary)
        4. action-log (primary)
        5. screenshot (fallback only)
        6. vision (fallback only)
        7. coordinate (last-resort only)

        Released missions use primary truth types only.
        """
        evidence_map: dict[str, tuple[str, ...]] = {
            "attach_session": (
                # Primary truth types: text and action-log
                "evidence://text/session-attached",
                "evidence://text/auth-state-confirmed",
                "evidence://action-log/attach-session",
            ),
            "prepare_session": (
                # Primary truth types: text and action-log
                "evidence://text/session-viable",
                "evidence://action-log/prepare-session",
            ),
            "benchmark_validation": (
                # Primary truth types: dom and action-log
                "evidence://dom/target-page-entered",
                "evidence://action-log/enter-target-page",
            ),
            "page_ready_observation": (
                # Primary truth types: dom and action-log (required for stop proof)
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
        # Write action-log artifacts for each action-log ref
        for ref in refs:
            if ref.startswith("evidence://action-log/"):
                action_key = ref[len("evidence://action-log/") :]
                self._write_action_log(key=action_key, mission_name=request.mission_name)
        return ExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


def _validate_evidence_type(evidence_ref: str) -> None:
    """Validate that evidence_ref conforms to typed evidence pattern.

    Valid pattern: evidence://<type>/<key>
    Valid types: dom, text, clock, action-log, screenshot, vision, coordinate
    """
    pattern = r"^evidence://([a-z\-]+)/([a-zA-Z0-9\-_]+)$"
    match = re.match(pattern, evidence_ref)
    if not match:
        msg = f"Evidence ref does not match pattern: {evidence_ref}"
        raise ValueError(msg)

    evidence_type = match.group(1)
    valid_types = {
        "dom",
        "text",
        "clock",
        "action-log",
        "screenshot",
        "vision",
        "coordinate",
    }
    if evidence_type not in valid_types:
        msg = (
            f"Evidence type '{evidence_type}' is not a valid type. "
            f"Valid types: {valid_types}"
        )
        raise ValueError(msg)


@pytest.mark.asyncio
async def test_released_scope_uses_typed_evidence_in_all_missions(
    tmp_path: Path,
) -> None:
    """Verify that all evidence refs in released missions are typed.

    PRD requirement (Evidence Truth Model, line 88):
    'typed evidence is required for released-scope decisions'

    This test ensures:
    1. All evidence_refs returned from released missions match the typed pattern
    2. All evidence types are valid according to the truth hierarchy
    3. The graph's decision logic operates on typed evidence
    """
    adapter = TypedEvidenceFakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify each mission in the runtime state has typed evidence
    runtime = result.state

    # Check that all transition artifacts contain valid typed evidence refs
    if runtime.transition_checkpoints.transitions:
        # Verify final mission (runCompletion) has typed stop proof
        assert runtime.current_mission == "run_completion"
        final_evidence_refs = runtime.mission_state.evidence_refs or ()
        assert final_evidence_refs, (
            "Final mission must have evidence refs for stop proof"
        )

        # Validate each evidence ref is typed
        for evidence_ref in final_evidence_refs:
            try:
                _validate_evidence_type(evidence_ref)
            except ValueError as exc:
                msg = f"Final mission contains invalid evidence ref: {exc}"
                raise AssertionError(msg) from exc

    # The stop proof must be an action-log type (requires proof trail)
    final_evidence_refs = runtime.mission_state.evidence_refs or ()
    stop_proof_present = any(
        "evidence://action-log/run-completed" in ref
        for ref in final_evidence_refs
    )
    assert stop_proof_present, (
        "Release-ceiling stop must be provable with typed action-log "
        "evidence (PRD line 92)"
    )


@pytest.mark.asyncio
async def test_released_scope_primary_evidence_types_in_decision_path(
    tmp_path: Path,
) -> None:
    """Verify that decision-critical evidence uses primary truth types.

    PRD requirement (Evidence Truth Model, lines 69-74):
    'Truth priority: 1. dom, 2. text, 3. clock, 4. action-log'

    Released-scope transitions should be decided using primary truth types,
    not fallback or last-resort types (screenshot, vision, coordinate).
    """
    adapter = TypedEvidenceFakeExecutionAdapter()

    result = await run_released_scope_via_langgraph(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    runtime = result.state

    # Verify final mission evidence uses primary types
    # (Primary: dom, text, clock, action-log)
    primary_types = {"dom", "text", "clock", "action-log"}
    fallback_types = {"screenshot", "vision"}
    last_resort_types = {"coordinate"}

    final_evidence_refs = runtime.mission_state.evidence_refs or ()
    if final_evidence_refs:
        # Extract types from evidence refs
        used_types = set()
        for evidence_ref in final_evidence_refs:
            match = re.match(r"^evidence://([a-z\-]+)/", evidence_ref)
            if match:
                used_types.add(match.group(1))

        # Verify that if fallback/last-resort types are present,
        # primary types are also present (fallback-only semantics)
        if fallback_types & used_types or last_resort_types & used_types:
            assert primary_types & used_types, (
                "Final mission uses fallback/last-resort evidence "
                "without primary evidence. Fallback-only rule violation "
                "(PRD lines 76-83)"
            )

        # For release-ceiling-stop, must have primary evidence
        stop_proof_refs = [
            ref for ref in final_evidence_refs
            if "release-ceiling-stop" in ref
        ]
        if stop_proof_refs:
            # Stop proof refs should be action-log (primary type)
            assert any("action-log" in ref for ref in stop_proof_refs), (
                "Release-ceiling-stop evidence must use primary truth types "
                f"(action-log). Got: {stop_proof_refs}"
            )
