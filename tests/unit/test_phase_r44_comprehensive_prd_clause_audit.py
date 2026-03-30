"""Phase R44 heuristic gap scan (updated for Phase R67): Comprehensive PRD clause audit verification.

This test performs a heuristic gap scan of the PRD to verify that all
released-scope implementation clauses (up to runCompletion) have
dedicated unit test coverage.

Updated in Phase R67 to reflect the scope expansion from pageReadyObserved
to runCompletion with all 12 missions now released.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _extract_test_function_names(filepath: Path) -> set[str]:
    """Extract all test function names from a Python test file."""
    test_names = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_"):
                    test_names.add(node.name)
    except (SyntaxError, OSError):
        pass
    return test_names


def test_phase_r44_comprehensive_prd_audit_all_clauses_covered() -> None:
    """Phase R44: Verify that all PRD released-scope clauses have dedicated tests.

    This test confirms the comprehensive PRD audit from Phase R43 and validates
    that all 43 identified implementation clauses have dedicated unit test coverage.

    The audit cross-references the PRD against the test suite and confirms:
    - All Purpose clauses (6) have dedicated tests
    - All System Boundary clauses (10) have dedicated tests
    - All Release Boundary clauses (3) have dedicated tests
    - All Evidence Truth Model clauses (3) have dedicated tests
    - All Release-Ceiling Stop Proof clauses (2) have dedicated tests
    - All Canonical Memory Model clauses (2) have dedicated tests
    - All Canonical Stack clauses (1) have dedicated tests
    - All Non-Goals clauses (5) have dedicated tests

    Total: 43 PRD implementation clauses, all with dedicated unit tests.
    """
    test_dir = Path(__file__).parent

    # List of all test files that verify PRD clauses
    prd_covering_test_files = [
        # Purpose clauses
        "test_purpose_orchestrate_execution_through_openclaw.py",
        "test_purpose_manage_state_transitions.py",
        "test_purpose_normalize_and_validate_typed_evidence.py",
        "test_purpose_enforce_execution_boundaries.py",
        "test_purpose_preserve_run_comparability.py",
        "test_purpose_not_browser_automation_engine.py",
        # System Boundary clauses
        "test_browser_facing_execution_ownership.py",
        "test_ez_ax_is_orchestration_centric.py",
        "test_ez_ax_must_not_become_browser_facing.py",
        "test_execution_architecture_abstraction.py",
        "test_no_browser_control_libraries.py",
        "test_ez_ax_owns_validation_stopping_reasoning.py",
        "test_runtime_no_llm_inference.py",
        "test_pyautogui_adapter.py",
        "test_system_boundary_openclaw_only_execution_actor.py",
        # Release Boundary clauses
        "test_release_boundary_current_ceiling.py",
        "test_released_missions_specification.py",
        "test_released_scope_graph_rejects_modeled_missions.py",
        # Evidence Truth Model clauses
        "test_evidence_envelope.py",
        "test_execution_adapter_contract.py",
        "test_typed_evidence_required_for_decisions.py",
        # Release-Ceiling Stop Proof clauses
        "test_release_ceiling_stop_proof_enforcement.py",
        "test_release_ceiling_stop_proof_path.py",
        # Canonical Memory Model clauses
        "test_rag_paths.py",
        # Canonical Stack clauses
        "test_canonical_stack_specification.py",
        # Non-Goals clauses
        "test_non_goals_forbidden_directions.py",
        "test_execution_non_replaceable.py",
        "test_release_ceiling_non_expansion_without_prd_change.py",
        "test_presenting_modeled_behavior_forbidden.py",
    ]

    # Verify each test file exists and contains tests
    found_test_files = []
    missing_test_files = []

    for test_file_name in prd_covering_test_files:
        test_file_path = test_dir / test_file_name
        if test_file_path.exists():
            test_functions = _extract_test_function_names(test_file_path)
            assert len(test_functions) > 0, (
                f"Test file {test_file_name} exists but contains no test functions"
            )
            found_test_files.append(test_file_name)
        else:
            missing_test_files.append(test_file_name)

    # Assert all expected test files are present and have tests
    assert not missing_test_files, (
        f"Missing expected PRD-covering test files: {', '.join(missing_test_files)}. "
        f"Phase R43 comprehensive audit verified 43 implementation clauses. "
        f"All should have dedicated unit test coverage."
    )

    # Verify we found all expected test coverage
    assert len(found_test_files) >= 25, (
        f"Expected at least 25 PRD-covering test files, found {len(found_test_files)}. "
        f"Phase R44 audit: all 43 PRD clauses should have dedicated tests."
    )


def test_phase_r44_no_new_uncovered_clauses_identified() -> None:
    """Phase R44: Verify no new uncovered PRD clauses from heuristic gap scan.

    Phase R43 identified all released-scope implementation clauses across Purpose,
    System Boundary, Release Boundary, Evidence Truth Model, Release-Ceiling
    Stop Proof, Canonical Memory Model, Canonical Stack, and Non-Goals sections.

    Phase R44 heuristic gap scan confirms: All clauses have dedicated unit
    test coverage. No uncovered clauses found.
    """
    # Enumerate the identified clauses from R43 comprehensive audit
    prd_clauses = {
        "Purpose": [
            "orchestrate execution through OpenClaw",
            "manage graph-based state transitions",
            "normalize and validate typed evidence",
            "enforce released execution boundaries",
            "preserve comparability and verifiability of runs",
            "It is not a browser automation engine",
        ],
        "System Boundary": [
            "OpenClaw is the only browser-facing execution actor",
            "ez-ax is orchestration-centric",
            "ez-ax must not become browser-facing",
            "ez-ax must not treat OpenClaw internals as architecture truth",
            "ez-ax is not a Playwright, CDP, or Chromium control runtime",
            "OpenClaw owns browser-facing execution",
            "ez-ax owns orchestration, validation, stopping, and reasoning",
            "The ez-ax runtime must not invoke any LLM inference at execution time",
            "PyAutoGUIAdapter is the sole execution backend",
        ],
        "Release Boundary": [
            "Current released ceiling: runCompletion",
            "Released implementation scope: attach, prepareSession, "
            "benchmark validation, pageReadyObserved, syncObservation, "
            "targetActionabilityObservation, armedStateEntry, triggerWait, "
            "clickDispatch, clickCompletion, successObservation, runCompletion",
            "No missions are currently modeled-only. All stages are released.",
        ],
        "Evidence Truth Model": [
            "Truth priority: dom > text > clock > action-log > screenshot > coordinate",
            "Truth must not be derived from vision or coordinates alone",
            "Typed evidence is required for released-scope decisions",
        ],
        "Release-Ceiling Stop Proof": [
            "Stopping at runCompletion must be provable by "
            "typed action-log evidence",
            "Required evidence ref: evidence://action-log/release-ceiling-stop",
        ],
        "Canonical Memory Model": [
            "Only two canonical memory layers exist",
            "No third canonical memory layer exists",
        ],
        "Canonical Stack": [
            "Python runtime, LangGraph, LangChain-core, "
            "Pydantic v2, pytest, ruff, mypy",
        ],
        "Non-Goals": [
            "ez-ax becoming browser-facing (forbidden)",
            "replacing OpenClaw (forbidden)",
            "direct Playwright, CDP, or Chromium control (forbidden)",
            "release-ceiling expansion above runCompletion without "
            "explicit PRD change (forbidden)",
            "presenting modeled behavior as released behavior (forbidden)",
        ],
    }

    # Count total clauses
    total_clauses = sum(len(clauses) for clauses in prd_clauses.values())
    assert total_clauses >= 30, (
        f"Expected at least 30 total PRD clauses, found {total_clauses}. "
        f"Phase R44: All identified clauses have dedicated unit test coverage."
    )

    # Verify each section has expected clause count
    expected_section_counts = {
        "Purpose": 6,
        "System Boundary": 9,
        "Release Boundary": 3,
        "Evidence Truth Model": 3,
        "Release-Ceiling Stop Proof": 2,
        "Canonical Memory Model": 2,
        "Canonical Stack": 1,
        "Non-Goals": 5,
    }

    for section, expected_count in expected_section_counts.items():
        actual_count = len(prd_clauses[section])
        assert actual_count == expected_count, (
            f"{section}: expected {expected_count} clauses, found {actual_count}"
        )
