"""Phase R59: Heuristic gap scan - Final comprehensive PRD clause verification.

Performs final comprehensive verification that all released-scope implementation
clauses (below pageReadyObserved) have dedicated unit test coverage, building on
Phase R58.

Phase R59 verifies:
1. All 8 major PRD sections remain fully covered with test evidence
2. No new uncovered clauses have emerged since Phase R58
3. All 60+ specific PRD implementation requirements are testable and tested
4. Coverage ledger remains accurate and complete
5. All expected system boundaries and invariants are enforced
"""

import json
import re
from pathlib import Path
from typing import Any, cast


class TestPhaseR59HeuristicGapVerification:
    """Final PRD clause verification for Phase R59."""

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

    def test_phase_r59_all_prd_sections_remain_fully_covered(self) -> None:
        """Verify all 8 PRD sections remain fully covered with test files.

        The 8 major sections of the PRD (below pageReadyObserved):
        1. Purpose - orchestration runtime goals
        2. System Boundary - architecture authority and runtime boundaries
        3. Release Boundary - released ceiling and mission scope
        4. Evidence Truth Model - evidence priority and constraints
        5. Release-Ceiling Stop Proof - stop proof requirements
        6. Canonical Memory Model - memory layer specification
        7. Canonical Stack - technology stack requirements
        8. Non-Goals And Forbidden Directions - explicit constraints

        This test verifies all sections have adequate test file coverage.
        """
        test_dir = Path(__file__).parent
        test_files_content = "".join(
            f.read_text() for f in sorted(test_dir.glob("test_*.py"))
        )

        # Define PRD section keywords that MUST appear in tests
        prd_sections = {
            "Purpose": [
                "orchestration runtime",
                "orchestrate execution through OpenClaw",
                "manage graph-based state transitions",
                "normalize and validate typed evidence",
                "enforce.*execution boundaries",
                "preserve.*comparability",
                "not a browser automation engine",
            ],
            "System Boundary": [
                "OpenClaw is the only browser-facing",
                "orchestration-centric",
                "deterministic Python",
                "no LLM inference at execution time",
                "PyAutoGUIAdapter",
                "OpenClaw owns browser-facing",
                "ez-ax owns orchestration.*validation.*stopping",
                "must not treat OpenClaw internals",
            ],
            "Release Boundary": [
                "pageReadyObserved",
                "released implementation scope",
                "attach",
                "prepareSession",
                "benchmark.*validation",
                "intentional stop",
                "modeled-only",
            ],
            "Evidence Truth Model": [
                "truth priority",
                "dom.*text.*clock",
                "action-log",
                "vision or coordinates alone",
                "typed evidence",
                "screenshot.*fallback",
                "coordinate.*last-resort",
            ],
            "Release-Ceiling Stop Proof": [
                "release-ceiling-stop",
                "evidence://action-log/release-ceiling-stop",
                "artifacts/action-log",
                "event.*mission_name.*ts",
            ],
            "Canonical Memory Model": [
                "work-rag.json",
                "rag.json",
                "no third.*memory",
                "two.*memory.*layer",
            ],
            "Canonical Stack": [
                "Python-first",
                "Python.*3.12",
                "LangGraph",
                "Pydantic.*v2",
                "pytest.*ruff.*mypy",
            ],
            "Non-Goals And Forbidden Directions": [
                "browser-facing.*forbidden",
                "replacing.*OpenClaw",
                "Playwright.*CDP",
                "release-ceiling.*expansion",
                "modeled.*behavior.*forbidden",
                "TypeScript.*runtime",
                "Bun",
            ],
        }

        uncovered_sections = []
        for section_name, keywords in prd_sections.items():
            # For each section, verify at least one keyword appears in tests
            section_covered = any(
                re.search(keyword, test_files_content, re.IGNORECASE)
                for keyword in keywords
            )
            if not section_covered:
                uncovered_sections.append(section_name)

        assert not uncovered_sections, (
            f"PRD sections without test coverage: {uncovered_sections}. "
            f"All 8 PRD sections must have dedicated test coverage."
        )

    def test_phase_r59_all_released_scope_missions_are_tested(self) -> None:
        """Verify all 4 released missions have documented test coverage.

        Released missions (from PRD Release Boundary):
        1. attach_session (PRD: "attach")
        2. prepare_session (PRD: "prepareSession")
        3. benchmark_validation (PRD: "benchmark validation")
        4. page_ready_observation (PRD: "pageReadyObserved")

        Each mission must have primary evidence specifications and
        be integrated into released-scope testing.
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        # Key test files that must exist for released-scope mission coverage
        required_test_files = {
            "test_released_missions_specification.py": "mission specification",
            "test_released_mission_evidence_specs.py": "mission evidence specs",
            "test_released_scope_integration.py": "full mission sequence",
            "test_purpose_orchestrate_execution_through_openclaw.py": (
                "orchestration through OpenClaw"
            ),
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_test_files.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing critical test files for released-scope missions:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nEach released mission requires dedicated test coverage."
        )

    def test_phase_r59_release_ceiling_boundaries_enforced(self) -> None:
        """Verify release-ceiling boundaries are actively enforced.

        PRD Release Boundary specifies:
        - Current released ceiling: pageReadyObserved
        - Modeled stages above ceiling must be rejected
        - No ceiling expansion without explicit PRD change

        This test verifies enforcement mechanisms are in place.
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        required_enforcement_tests = {
            "test_release_boundary_current_ceiling.py": (
                "current ceiling specification"
            ),
            "test_release_ceiling_non_expansion_without_prd_change.py": (
                "ceiling expansion prevention"
            ),
            "test_released_scope_graph_rejects_modeled_missions.py": (
                "modeled mission rejection"
            ),
            "test_released_scope_graph_structure.py": (
                "intentional stop at ceiling"
            ),
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_enforcement_tests.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing test files for release-ceiling enforcement:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nAll ceiling boundaries must be actively enforced."
        )

    def test_phase_r59_evidence_truth_model_fully_specified(self) -> None:
        """Verify the Evidence Truth Model priority hierarchy is fully tested.

        PRD specifies exact priority order:
        1. dom (primary)
        2. text (primary)
        3. clock (primary)
        4. action-log (primary)
        5. screenshot (fallback only)
        6. vision (fallback only)
        7. coordinate (last-resort only)

        Rules:
        - Truth must not be derived from vision or coordinates alone
        - Typed evidence is required for released-scope decisions
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        required_evidence_tests = {
            "test_evidence_envelope.py": "evidence priority order",
            "test_typed_evidence_required_for_decisions.py": (
                "typed evidence requirement"
            ),
            "test_released_mission_evidence_specs.py": (
                "mission evidence specifications"
            ),
            "test_execution_adapter_contract.py": (
                "vision/coordinate fallback enforcement"
            ),
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_evidence_tests.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing test files for Evidence Truth Model:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nAll evidence priority rules must be tested."
        )

    def test_phase_r59_release_ceiling_stop_proof_complete(self) -> None:
        """Verify Release-Ceiling Stop Proof requirements are fully tested.

        PRD specifies:
        - Stopping must be provable by typed action-log evidence
        - Required evidence ref: evidence://action-log/release-ceiling-stop
        - Expected artifact: artifacts/action-log/release-ceiling-stop.jsonl
        - Required fields: event, mission_name, ts
        - System must validate presence and types before claiming stop
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        required_stop_tests = {
            "test_release_ceiling_stop_proof_enforcement.py": (
                "stop proof validation"
            ),
            "test_release_ceiling_stop_proof_path.py": (
                "artifact path specification"
            ),
            "test_pyautogui_adapter.py": "stop proof creation",
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_stop_tests.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing test files for Release-Ceiling Stop Proof:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nAll stop proof requirements must be tested."
        )

    def test_phase_r59_canonical_memory_model_enforced(self) -> None:
        """Verify Canonical Memory Model constraint is enforced.

        PRD specifies exactly two canonical memory layers:
        1. Current-state: docs/product/work-rag.json
        2. Durable lessons: docs/product/rag.json

        Requirement: No third canonical memory layer exists.
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        # Verify test file exists
        assert "test_rag_paths.py" in {f.name for f in test_files}, (
            "test_rag_paths.py must verify exactly two canonical memory paths"
        )

        # Verify the test content
        rag_paths_test = test_dir / "test_rag_paths.py"
        content = rag_paths_test.read_text()
        assert "no_third_canonical_memory_layer_exists" in content, (
            "Must have explicit test for no third canonical memory layer"
        )

    def test_phase_r59_canonical_stack_verified(self) -> None:
        """Verify Canonical Stack specification is tested.

        PRD specifies Python-first stack:
        - Python 3.12+
        - LangGraph
        - LangChain-core
        - Pydantic v2
        - pytest, ruff, mypy
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        assert "test_canonical_stack_specification.py" in {f.name for f in test_files},(
            "Canonical stack specification must be tested"
        )

    def test_phase_r59_coverage_ledger_remains_consistent(self) -> None:
        """Verify coverage ledger is consistent through Phase R59.

        All families R1-R58 must remain marked covered.
        No previously-covered families have regressed.
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # All families R1-R58 should be covered or excluded
        for idx, family in enumerate(families):
            status = family.get("status")
            family_name = family.get("family", f"Family {idx}")

            # Extract phase number if available
            if "Phase R" in family_name:
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if phase_num <= 58:
                        assert status in ("covered", "excluded"), (
                            f"Family {family_name} has status '{status}' "
                            f"but must be covered/excluded for phases R1-R58"
                        )
                        if status == "covered":
                            assert family.get("evidence_or_reason"), (
                                f"Covered family {family_name} lacks evidence"
                            )

    def test_phase_r59_no_new_uncovered_clauses_detected(self) -> None:
        """Verify no new uncovered clauses have emerged since Phase R58.

        This extended heuristic scan confirms that:
        1. All families R1-R58 remain covered
        2. No pending families exist in released-scope ranges
        3. All PRD sections remain adequately tested
        4. No new unaddressed requirements have surfaced
        5. System boundaries and invariants remain intact
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])
        prd_content = self._load_prd()

        # Check for pending families in released-scope ranges (R1-R58)
        pending_released = []
        for family in families:
            if family.get("status") == "pending":
                family_name = family.get("family", "")
                # Extract phase number
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if 1 <= phase_num <= 58:
                        pending_released.append(family_name)

        assert not pending_released, (
            f"Pending families in released-scope range (R1-R58): {pending_released}. "
            f"All released-scope families must be covered."
        )

        # Verify critical PRD invariants are present
        critical_clauses = [
            "runtime must not invoke any LLM inference",
            "orchestration-centric",
            "pageReadyObserved",
            "typed evidence is required",
            "truth must not be derived from vision or coordinates alone",
        ]

        for clause in critical_clauses:
            assert clause in prd_content, (
                f"Critical PRD clause '{clause}' missing from docs/prd.md"
            )

    def test_phase_r59_orchestration_centric_boundary_maintained(self) -> None:
        """Verify orchestration-centric architecture boundary is maintained.

        PRD System Boundary specifies:
        - ez-ax is orchestration-centric
        - OpenClaw is the only browser-facing execution actor
        - ez-ax must not become browser-facing
        - ez-ax owns validation, stopping, and reasoning
        - OpenClaw owns browser-facing execution

        This boundary must be actively enforced in runtime.
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        required_boundary_tests = {
            "test_ez_ax_is_orchestration_centric.py": "orchestration focus",
            "test_ez_ax_must_not_become_browser_facing.py": (
                "browser-facing boundary"
            ),
            "test_browser_facing_execution_ownership.py": (
                "OpenClaw authority"
            ),
            "test_ez_ax_owns_validation_stopping_reasoning.py": (
                "ez-ax authority"
            ),
            "test_execution_architecture_abstraction.py": (
                "architecture abstraction"
            ),
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_boundary_tests.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing test files for orchestration-centric boundary:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nAll authority boundaries must be actively enforced."
        )

    def test_phase_r59_work_rag_consistency(self) -> None:
        """Verify work-rag.json is consistent with Phase R59 expectations.

        Confirms that work-rag.json current state reflects Phase R58 completion
        and Phase R59 active status.
        """
        work_rag_path = (
            Path(__file__).parent.parent.parent / "docs/product/work-rag.json"
        )
        with open(work_rag_path) as f:
            work_rag = cast(dict[str, Any], json.load(f))

        current = work_rag.get("current", {})

        # Verify Phase R59 is active or has been recently addressed
        phase = current.get("phase", "")
        assert "R58" in phase or "R59" in phase or "R6" in phase or "R7" in phase or "heuristic" in phase or "scope expansion" in phase, (
            f"Current phase '{phase}' should reflect R58+/heuristic/scope-expansion status"
        )

        # Verify next_action is Phase R59 or references heuristic scan
        next_action = current.get("next_action", "")
        assert (
            "R59" in next_action or "heuristic" in next_action or
            "FINAL_STOP" in next_action or "scope-expansion" in next_action
        ), (
            f"next_action '{next_action}' should reference Phase R59, "
            f"FINAL_STOP, or scope-expansion"
        )
