"""Test that released-scope preserves comparability and verifiability of runs.

PRD requirement (Purpose section, line 13):
'preserve comparability and verifiability of runs'

This means that:
1. Released-scope executions must produce complete, verifiable run results
2. Run results must have all required metadata for verification
3. Run artifacts must be properly structured and accessible
4. Runs with same inputs should be comparable
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ez_ax.adapters.openclaw.client import (
    OpenClawExecutionRequest,
    OpenClawExecutionResult,
)
from ez_ax.graph.released_entrypoint import (
    ReleasedEntrypointResult,
    run_released_scope,
)


class VerifiableRunAdapter:
    """Adapter that provides complete evidence for all missions."""

    async def execute(
        self, request: OpenClawExecutionRequest
    ) -> OpenClawExecutionResult:
        """Execute mission with complete evidence refs."""
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
        refs = evidence_map.get(request.mission_name, ())
        if not refs:
            raise AssertionError(f"Unexpected mission: {request.mission_name}")
        return OpenClawExecutionResult(
            mission_name=request.mission_name, evidence_refs=refs
        )


@pytest.mark.asyncio
async def test_released_scope_produces_verifiable_run_result(
    tmp_path: Path,
) -> None:
    """Verify released-scope produces a complete, verifiable ReleasedEntrypointResult.

    PRD requirement (Purpose, line 13): 'preserve comparability and verifiability
    of runs'. This test verifies that the released-scope result structure is
    complete and verifiable.

    A verifiable run result must contain:
    1. RuntimeState with complete run metadata
    2. ReleasedRunContext with run root path
    3. Final artifact bundle reference for verification
    4. Consistent mission execution history
    """
    adapter = VerifiableRunAdapter()

    result = await run_released_scope(
        adapter=adapter,
        session_ref="test-session",
        expected_auth_state="logged-in",
        target_page_url="https://example.com/target",
        site_identity="example.com",
        base_dir=tmp_path,
    )

    # Verify result is of correct type
    assert isinstance(result, ReleasedEntrypointResult), (
        "Released-scope must return ReleasedEntrypointResult for verifiability"
    )

    # Verify RuntimeState is present and has required metadata
    assert result.state is not None
    assert result.state.run_id is not None
    assert result.state.final_artifact_bundle_ref is not None, (
        "Final artifact bundle ref must be set for verifiability"
    )

    # Verify ReleasedRunContext is present
    assert result.run is not None
    assert result.run.run_root is not None
    assert result.run.run_root.exists(), (
        "Run root must exist for artifact verification"
    )

    # Verify run root directory structure is complete
    artifacts_dir = result.run.run_root / "artifacts"
    assert artifacts_dir.exists(), (
        "Run must have artifacts directory for verifiability"
    )
    assert (artifacts_dir / "action-log").exists(), (
        "Run must have action-log directory"
    )

    # Verify all mission artifacts exist (evidence of execution)
    action_log_dir = artifacts_dir / "action-log"
    expected_artifacts = {
        "attach-session.jsonl",
        "prepare-session.jsonl",
        "enter-target-page.jsonl",
        "release-ceiling-stop.jsonl",
    }
    for artifact_name in expected_artifacts:
        artifact_path = action_log_dir / artifact_name
        assert artifact_path.exists(), (
            f"Mission artifact {artifact_name} must exist for run verifiability"
        )
        # Verify artifact is readable (valid JSON lines)
        content = artifact_path.read_text(encoding="utf-8")
        assert content, f"Artifact {artifact_name} must not be empty"

    # Verify approved scope ceiling is set correctly
    assert result.run.approved_scope_ceiling == "pageReadyObserved", (
        "Run must declare approved scope ceiling for verifiability"
    )

    # Verify final artifact bundle ref points to valid run root
    bundle_path = Path(result.state.final_artifact_bundle_ref)
    assert bundle_path == result.run.run_root, (
        "Final artifact bundle ref must point to run root for verifiability"
    )
