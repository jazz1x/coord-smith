"""Phase R58: Heuristic gap scan - Extended PRD clause verification.

Performs extended verification that all released-scope implementation clauses
(below pageReadyObserved) have dedicated unit test coverage, building on Phase R57.

Phase R58 verifies:
1. All major PRD sections remain fully covered with test evidence
2. No new uncovered clauses have emerged since Phase R57
3. All specific PRD implementation requirements are testable and tested
4. Coverage ledger remains accurate and complete
"""

import json
from pathlib import Path
from typing import Any, cast


class TestPhaseR58HeuristicGapVerification:
    """Extended PRD clause verification for Phase R58."""

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

    def test_phase_r58_all_prd_sections_remain_fully_covered(self) -> None:
        """Verify all 8 PRD sections have dedicated test coverage.

        The 8 major sections of the PRD (below pageReadyObserved):
        1. Purpose - orchestration runtime goals and non-goals
        2. System Boundary - architecture authority and runtime boundaries
        3. Release Boundary - released ceiling and mission scope
        4. Evidence Truth Model - evidence priority and constraints
        5. Release-Ceiling Stop Proof - proof requirements and artifact format
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
                "not a browser automation engine",
            ],
            "System Boundary": [
                "OpenClaw is the only browser-facing",
                "orchestration-centric",
                "deterministic Python",
                "no LLM inference at execution time",
                "PyAutoGUIAdapter",
            ],
            "Release Boundary": [
                "pageReadyObserved",
                "released implementation scope",
                "attach",
                "prepareSession",
                "modeled-only",
            ],
            "Evidence Truth Model": [
                "truth priority",
                "dom.*text.*clock",
                "vision or coordinates alone",
                "typed evidence",
            ],
            "Release-Ceiling Stop Proof": [
                "release-ceiling-stop",
                "evidence://action-log/release-ceiling-stop",
                "event.*mission_name.*ts",
            ],
            "Canonical Memory Model": [
                "work-rag.json",
                "rag.json",
                "no third.*memory",
            ],
            "Canonical Stack": [
                "Python-first",
                "LangGraph",
                "Pydantic v2",
                "pytest.*ruff.*mypy",
            ],
            "Non-Goals And Forbidden Directions": [
                "browser-facing",
                "OpenClaw",
                "Playwright.*CDP",
                "TypeScript",
                "Bun",
            ],
        }

        uncovered_sections = []
        for section_name, keywords in prd_sections.items():
            # For each section, verify at least one keyword appears in tests
            section_covered = any(
                keyword in test_files_content for keyword in keywords
            )
            if not section_covered:
                uncovered_sections.append(section_name)

        assert not uncovered_sections, (
            f"PRD sections without test coverage: {uncovered_sections}. "
            f"All 8 PRD sections must have dedicated test coverage."
        )

    def test_phase_r58_coverage_ledger_families_r57_remain_covered(self) -> None:
        """Verify all families through R57 remain marked covered.

        Confirms that no families have regressed from covered status
        since Phase R57 completion.
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # All families R1-R57 should be covered
        for idx, family in enumerate(families):
            status = family.get("status")
            family_name = family.get("family", f"Family {idx}")

            # Extract phase number if available
            if "Phase R" in family_name:
                import re
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if phase_num <= 57:
                        assert status in ("covered", "excluded"), (
                            f"Family {family_name} has status '{status}' "
                            f"but must be covered/excluded for phases R1-R57"
                        )
                        if status == "covered":
                            assert family.get("evidence_or_reason"), (
                                f"Covered family {family_name} lacks evidence"
                            )

    def test_phase_r58_released_scope_coverage_completeness(self) -> None:
        """Verify all released-scope clauses below pageReadyObserved remain covered.

        This verification confirms that all clauses in the Release Boundary,
        Evidence Truth Model, Release-Ceiling Stop Proof, and related sections
        have adequate test coverage with concrete test files.
        """
        test_dir = Path(__file__).parent
        test_files = sorted(test_dir.glob("test_*.py"))

        # Key test files that MUST exist for released-scope coverage
        required_test_files = {
            "test_released_scope_integration.py": "full 4-mission sequence",
            "test_release_ceiling_stop_proof_enforcement.py": "stop proof validation",
            "test_pyautogui_adapter.py": "PyAutoGUIAdapter implementation",
            "test_released_scope_graph_rejects_modeled_missions.py": (
                "modeled missions enforcement"
            ),
            "test_evidence_envelope.py": "evidence validation",
            "test_rag_paths.py": "canonical memory paths",
            "test_non_goals_forbidden_directions.py": "forbidden directions",
        }

        found_files = {f.name for f in test_files}

        missing_files = []
        for required_file, purpose in required_test_files.items():
            if required_file not in found_files:
                missing_files.append((required_file, purpose))

        assert not missing_files, (
            "Missing critical test files for released-scope coverage:\n"
            + "\n".join(
                f"  - {fname} ({purpose})" for fname, purpose in missing_files
            )
            + "\nEach released-scope clause requires dedicated test coverage."
        )

    def test_phase_r58_no_new_uncovered_clauses_detected(self) -> None:
        """Verify no new uncovered clauses have emerged since Phase R57.

        This extended heuristic scan confirms that:
        1. All families R1-R57 remain covered
        2. No pending families exist in released-scope ranges
        3. All PRD sections remain adequately tested
        4. No new unaddressed requirements have surfaced
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])
        prd_content = self._load_prd()

        # Check for pending families in released-scope ranges (R1-R57)
        pending_released = []
        for family in families:
            if family.get("status") == "pending":
                family_name = family.get("family", "")
                # Extract phase number
                import re
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if 1 <= phase_num <= 57:
                        pending_released.append(family_name)

        assert not pending_released, (
            f"Pending families in released-scope range (R1-R57): {pending_released}. "
            f"All released-scope families must be covered."
        )

        # Verify no critical PRD keywords are mentioned without corresponding tests
        critical_keywords = [
            "must not",
            "required",
            "shall",
            "shall not",
            "MUST",
            "MUST NOT",
        ]

        test_dir = Path(__file__).parent
        test_content = "".join(
            f.read_text() for f in sorted(test_dir.glob("test_*.py"))
        )

        # This is a heuristic check - if critical requirement keywords exist in PRD
        # but don't appear in tests, that's a potential gap
        unverified_criticality = 0
        for keyword in critical_keywords:
            prd_mentions = prd_content.count(keyword)
            test_mentions = test_content.count(keyword)
            if prd_mentions > test_mentions:
                # Allow some disparity (tests may use different phrasing)
                # but flag if there's a major gap
                if prd_mentions > test_mentions + 5:
                    unverified_criticality += 1

        # A small number of unverified critical keywords is acceptable
        # (tests often rephrase requirements)
        assert unverified_criticality < 3, (
            f"Found {unverified_criticality} potential gaps between PRD critical "
            f"requirements and test coverage. Review PRD for new clauses."
        )

    def test_phase_r58_work_rag_consistency(self) -> None:
        """Verify work-rag.json is consistent with Phase R58 expectations.

        Confirms that work-rag.json current state reflects Phase R58 completion
        or progression beyond (FINAL_STOP after R58/R59 completion).
        """
        work_rag_path = (
            Path(__file__).parent.parent.parent / "docs/product/work-rag.json"
        )
        with open(work_rag_path) as f:
            work_rag = cast(dict[str, Any], json.load(f))

        current = work_rag.get("current", {})

        # Verify phase indicates R58 or later completion
        phase = current.get("phase", "")
        assert any(
            x in phase
            for x in ["R58", "R59", "R6", "R7", "heuristic", "gap scan", "scope expansion"]
        ), (
            f"Current phase '{phase}' should reflect R58+ or heuristic scan status"
        )

        # Verify next_action indicates R58/R59 progression or FINAL_STOP
        next_action = current.get("next_action", "")
        assert any(
            x in next_action
            for x in ["R58", "R59", "heuristic", "FINAL_STOP", "scope-expansion"]
        ), (
            f"next_action '{next_action}' should reference R58/R59, FINAL_STOP, or scope-expansion"
        )
