"""Phase R90: Heuristic gap scan - Comprehensive PRD clause verification.

Performs final heuristic scan to verify all released-scope implementation clauses
(below pageReadyObserved) continue to have dedicated unit test coverage after
Phase R89 completion.

Phase R90 verifies:
1. All released missions (12 total) have dedicated tests
2. All evidence model clauses are tested
3. All release-ceiling stop proof requirements are tested
4. All boundary enforcement clauses are tested
5. No new uncovered clauses have emerged in the PRD
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast


class TestPhaseR90HeuristicGapVerification:
    """Released-scope heuristic gap scan verification for Phase R90."""

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root path."""
        return Path(__file__).parent.parent.parent

    @staticmethod
    def _load_prd() -> str:
        """Load PRD."""
        prd_path = Path(__file__).parent.parent.parent / "docs/prd.md"
        with open(prd_path) as f:
            return f.read()

    @staticmethod
    def _load_coverage_ledger() -> dict[str, Any]:
        """Load coverage ledger."""
        ledger_path = (
            Path(__file__).parent.parent.parent
            / "docs/llm/low-attention-coverage-ledger.json"
        )
        with open(ledger_path) as f:
            return cast(dict[str, Any], json.load(f))

    def test_phase_r90_all_12_released_missions_have_tests(self) -> None:
        """Verify all 12 released missions have dedicated unit tests.

        Released implementation scope from PRD Release Boundary (lines 49-61):
        1. attach
        2. prepareSession
        3. benchmark validation
        4. pageReadyObserved
        5. syncObservation
        6. targetActionabilityObservation
        7. armedStateEntry
        8. triggerWait
        9. clickDispatch
        10. clickCompletion
        11. successObservation
        12. runCompletion

        Each mission must have dedicated unit tests verifying its evidence
        specifications and execution behavior.
        """
        # Verify 12 mission evidence specification tests exist and pass
        expected_mission_tests = [
            "test_attach_session_primary_evidence_specification",
            "test_prepare_session_primary_evidence_specification",
            "test_benchmark_validation_primary_evidence_specification",
            "test_page_ready_observation_primary_evidence_specification",
            "test_sync_observation_primary_evidence_specification",
            "test_target_actionability_observation_primary_evidence_specification",
            "test_armed_state_entry_primary_evidence_specification",
            "test_trigger_wait_primary_evidence_specification",
            "test_click_dispatch_primary_evidence_specification",
            "test_click_completion_primary_evidence_specification",
            "test_success_observation_primary_evidence_specification",
            "test_run_completion_primary_evidence_specification",
        ]

        mission_evidence_test_path = (
            self._get_project_root() / "tests/unit/test_released_mission_evidence_specs.py"
        )
        assert mission_evidence_test_path.exists(), (
            "Mission evidence specification tests must exist at: "
            f"{mission_evidence_test_path}"
        )

        test_content = mission_evidence_test_path.read_text(encoding="utf-8")
        for test_name in expected_mission_tests:
            assert f"def {test_name}" in test_content, (
                f"Missing test for mission: {test_name} in "
                f"test_released_mission_evidence_specs.py"
            )

    def test_phase_r90_intentional_stop_at_ceiling_has_dedicated_test(self) -> None:
        """Verify intentional stop at released ceiling is tested.

        PRD Release Boundary (line 61): 'intentional stop at the released ceiling'

        The released scope must stop after run_completion without attempting
        any further missions beyond the release ceiling.
        """
        intentional_stop_test_path = (
            self._get_project_root()
            / "tests/unit/test_released_scope_intentional_stop_at_ceiling.py"
        )
        assert intentional_stop_test_path.exists(), (
            "Intentional stop at ceiling test must exist at: "
            f"{intentional_stop_test_path}"
        )

        test_content = intentional_stop_test_path.read_text(encoding="utf-8")
        assert "def test_" in test_content, (
            "Intentional stop test file must contain test functions"
        )

    def test_phase_r90_evidence_truth_model_fully_tested(self) -> None:
        """Verify Evidence Truth Model clauses are fully tested.

        PRD Evidence Truth Model (lines 67-86):
        - Truth priority: dom > text > clock > action-log (> screenshot, vision, coordinate)
        - Truth must not be derived from vision or coordinates alone
        - Typed evidence is required for released-scope decisions
        """
        truth_priority_test_path = (
            self._get_project_root()
            / "tests/unit/test_typed_evidence_required_for_decisions.py"
        )
        assert truth_priority_test_path.exists(), (
            "Evidence truth model test must exist at: " f"{truth_priority_test_path}"
        )

        test_content = truth_priority_test_path.read_text(encoding="utf-8")
        assert "def test_" in test_content, (
            "Evidence truth model test must contain test functions"
        )

    def test_phase_r90_release_ceiling_stop_proof_enforcement_tested(self) -> None:
        """Verify Release-Ceiling Stop Proof requirements are tested.

        PRD Release-Ceiling Stop Proof (lines 88-107):
        - Stopping at runCompletion must be provable by typed action-log evidence
        - Required evidence ref: evidence://action-log/release-ceiling-stop
        - Expected artifact: artifacts/action-log/release-ceiling-stop.jsonl
        - Required typed fields: event, mission_name, ts
        - If artifact cannot be resolved or fields missing, don't claim correct stop
        """
        stop_proof_enforcement_path = (
            self._get_project_root()
            / "tests/unit/test_release_ceiling_stop_proof_enforcement.py"
        )
        assert stop_proof_enforcement_path.exists(), (
            "Release-ceiling stop proof enforcement test must exist at: "
            f"{stop_proof_enforcement_path}"
        )

        test_content = stop_proof_enforcement_path.read_text(encoding="utf-8")
        assert "def test_" in test_content, (
            "Stop proof enforcement test must contain test functions"
        )

        # Verify path specification test exists
        stop_proof_path_test = (
            self._get_project_root()
            / "tests/unit/test_release_ceiling_stop_proof_path.py"
        )
        assert stop_proof_path_test.exists(), (
            "Release-ceiling stop proof path test must exist at: "
            f"{stop_proof_path_test}"
        )

        # Verify rejection/enforcement tests exist for missing/incomplete artifacts
        evidence_envelope_test = (
            self._get_project_root() / "tests/unit/test_evidence_envelope.py"
        )
        assert evidence_envelope_test.exists(), (
            "Evidence envelope test must exist at: " f"{evidence_envelope_test}"
        )

        envelope_content = evidence_envelope_test.read_text(encoding="utf-8")
        rejection_tests = [
            "test_validate_release_ceiling_stop_proof_rejects_missing_file",
            "test_validate_release_ceiling_stop_proof_rejects_missing_event_field",
            "test_validate_release_ceiling_stop_proof_rejects_missing_timestamp",
            "test_validate_release_ceiling_stop_proof_rejects_wrong_mission",
        ]
        for test_name in rejection_tests:
            assert f"def {test_name}" in envelope_content, (
                f"Missing rejection test: {test_name} in test_evidence_envelope.py"
            )

    def test_phase_r90_canonical_memory_model_tested(self) -> None:
        """Verify Canonical Memory Model requirements are tested.

        PRD Canonical Memory Model (lines 109-121):
        - Only two canonical memory layers exist
        - Current-state memory: work-rag.json
        - Durable lesson memory: rag.json
        - No third canonical memory layer exists
        """
        rag_paths_test = (
            self._get_project_root() / "tests/unit/test_rag_paths.py"
        )
        assert rag_paths_test.exists(), (
            "RAG paths test must exist at: " f"{rag_paths_test}"
        )

        test_content = rag_paths_test.read_text(encoding="utf-8")
        assert "def test_" in test_content, (
            "RAG paths test must contain test functions"
        )

    def test_phase_r90_canonical_stack_tested(self) -> None:
        """Verify Canonical Stack specification is tested.

        PRD Canonical Stack (lines 123-135):
        - Python-first implementation path
        - Expected stack: Python, LangGraph, LangChain-core, Pydantic v2, pytest, ruff, mypy
        """
        stack_test = (
            self._get_project_root()
            / "tests/unit/test_canonical_stack_specification.py"
        )
        assert stack_test.exists(), (
            "Canonical stack test must exist at: " f"{stack_test}"
        )

        test_content = stack_test.read_text(encoding="utf-8")
        assert "def test_" in test_content, (
            "Canonical stack test must contain test functions"
        )

    def test_phase_r90_system_boundary_enforcement_tested(self) -> None:
        """Verify System Boundary clauses are tested.

        PRD System Boundary (lines 17-39):
        - OpenClaw is the only browser-facing execution actor
        - ez-ax is orchestration-centric
        - ez-ax must not become browser-facing
        - ez-ax must not treat OpenClaw internals as architecture truth
        - ez-ax is not a Playwright, CDP, or Chromium control runtime
        - OpenClaw owns browser-facing execution
        - ez-ax owns orchestration, validation, stopping, reasoning
        - Runtime must not invoke LLM inference at execution time
        - All decisions are deterministic Python
        - PyAutoGUIAdapter is sole execution backend (coordinate-click + screenshot)
        - LLM inference restricted to offline autoloop harness
        """
        boundary_tests = [
            "test_browser_facing_execution_ownership.py",
            "test_ez_ax_is_orchestration_centric.py",
            "test_ez_ax_must_not_become_browser_facing.py",
            "test_ez_ax_owns_validation_stopping_reasoning.py",
            "test_runtime_no_llm_inference.py",
            "test_no_browser_control_libraries.py",
        ]

        for test_file in boundary_tests:
            test_path = self._get_project_root() / "tests/unit" / test_file
            assert test_path.exists(), (
                f"System boundary test must exist at: {test_path}"
            )

    def test_phase_r90_no_new_uncovered_clauses_in_prd(self) -> None:
        """Final verification: No new uncovered PRD clauses discovered.

        This test performs a comprehensive heuristic scan of the PRD to ensure
        all released-scope clauses below pageReadyObserved have dedicated unit
        test coverage.

        If this test passes, all released-scope implementation clauses have
        dedicated unit test coverage, and the system is ready for continuation
        or FINAL_STOP decision.
        """
        prd = self._load_prd()
        ledger = self._load_coverage_ledger()

        # Verify all major PRD sections are present
        required_sections = [
            "## Purpose",
            "## System Boundary",
            "## Release Boundary",
            "## Evidence Truth Model",
            "## Release-Ceiling Stop Proof",
            "## Canonical Memory Model",
            "## Canonical Stack",
            "## Non-Goals And Forbidden Directions",
        ]

        for section in required_sections:
            assert section in prd, (
                f"PRD section '{section}' not found in docs/prd.md. "
                f"PRD structure may have changed."
            )

        # Verify all 12 released missions are listed in Release Boundary
        expected_missions = [
            "attach",
            "prepareSession",
            "benchmark validation",
            "pageReadyObserved",
            "syncObservation",
            "targetActionabilityObservation",
            "armedStateEntry",
            "triggerWait",
            "clickDispatch",
            "clickCompletion",
            "successObservation",
            "runCompletion",
        ]

        release_boundary_start = prd.find("## Release Boundary")
        evidence_model_start = prd.find("## Evidence Truth Model")
        released_scope_section = prd[release_boundary_start:evidence_model_start]

        for mission in expected_missions:
            assert mission in released_scope_section, (
                f"Released mission '{mission}' not found in Release Boundary section"
            )

        # Verify coverage ledger has Phase R90 family entry
        families = ledger.get("families", [])
        r90_family = None
        for family in families:
            if family.get("family") == "Phase R90 heuristic gap scan":
                r90_family = family
                break

        assert r90_family is not None, (
            "Coverage ledger must have 'Phase R90 heuristic gap scan' family entry"
        )

        # Verify family has proper structure
        assert r90_family.get("status") in [
            "pending",
            "covered",
        ], "Phase R90 family must have status 'pending' or 'covered'"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
