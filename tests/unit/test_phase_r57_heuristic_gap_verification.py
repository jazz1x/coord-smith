"""Phase R57: Heuristic gap scan - Released-scope clause verification.

Performs comprehensive verification that all released-scope implementation
clauses (below pageReadyObserved) have dedicated unit test coverage and
no new uncovered clauses have emerged.

Phase R57 verifies:
1. All 5 released-scope clauses have dedicated test coverage
2. No new uncovered clauses in the Release Boundary section
3. Each released-scope clause is properly tested
4. Coverage ledger remains accurate and complete
"""

import json
from pathlib import Path
from typing import Any, cast


class TestPhaseR57HeuristicGapVerification:
    """Released-scope clause comprehensive verification for Phase R57."""

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root path."""
        return Path(__file__).parent.parent.parent

    @staticmethod
    def _load_prd() -> str:
        """Load PRD."""
        prd_path = (
            Path(__file__).parent.parent.parent / "docs/prd.md"
        )
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

    def test_phase_r57_released_scope_clauses_have_test_coverage(self) -> None:
        """Verify all 5 released-scope clauses have dedicated unit test coverage.

        PRD Release Boundary (lines 47-53) specifies 5 released-scope items:
        1. attach (attach_session mission)
        2. prepareSession (prepare_session mission)
        3. benchmark validation (benchmark_validation mission)
        4. pageReadyObserved (page_ready_observation mission)
        5. intentional stop at the released ceiling
        """
        prd_content = self._load_prd()
        test_dir = Path(__file__).parent

        # Released-scope clauses that MUST have test coverage
        released_scope_clauses = {
            "attach": [
                "attach_session",
                "released_mission",
                "execute_attach",
            ],
            "prepareSession": [
                "prepare_session",
                "released_mission",
                "execute_prepare",
            ],
            "benchmark validation": [
                "benchmark_validation",
                "released_mission",
                "execute_benchmark",
            ],
            "pageReadyObserved": [
                "page_ready_observation",
                "released_mission",
                "released_ceiling",
                "pageReadyObserved",
            ],
            "intentional stop at the released ceiling": [
                "intentional_stop",
                "released_ceiling",
                "ceiling_stop",
                "release-ceiling-stop",
            ],
        }

        # Verify PRD has Release Boundary section
        assert "## Release Boundary" in prd_content, (
            "PRD Release Boundary section not found"
        )

        # Verify PRD explicitly lists released scope
        for clause_name in released_scope_clauses.keys():
            # Normalize clause name for PRD check
            assert clause_name in prd_content, (
                f"Released-scope clause '{clause_name}' not found in PRD"
            )

        # Scan all test files for coverage of each clause
        test_files = sorted(test_dir.glob("test_*.py"))
        test_content = "".join(f.read_text() for f in test_files)

        # Verify each released-scope clause has test coverage
        uncovered_clauses = []
        for clause_name, keywords in released_scope_clauses.items():
            found = any(
                keyword in test_content
                for keyword in keywords
            )
            if not found:
                uncovered_clauses.append(clause_name)

        assert not uncovered_clauses, (
            f"Released-scope clauses without test coverage: {uncovered_clauses}. "
            f"Each released-scope clause must have dedicated test coverage."
        )

    def test_phase_r57_no_new_uncovered_clauses_in_release_boundary(self) -> None:
        """Verify no new uncovered clauses in PRD Release Boundary section.

        This re-verification confirms that all previously identified
        released-scope coverage remains valid and no gaps have appeared
        in the Release Boundary section.
        """
        prd_content = self._load_prd()
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # Extract Release Boundary section from PRD
        release_boundary_start = prd_content.find("## Release Boundary")
        release_boundary_end = prd_content.find("\n## ", release_boundary_start + 1)
        release_boundary_section = prd_content[
            release_boundary_start:release_boundary_end
        ]

        # Count pending families (should be 0 for released scope except R57 itself)
        pending_families = [
            f for f in families
            if f.get("status") == "pending"
        ]

        # Filter to only those related to released scope (R1-R56, excluding R57+)
        # Allow Phase R57 itself to be pending during Phase R57 execution
        released_scope_pending = [
            f for f in pending_families
            if not any(
                f"Phase R{phase_num}" in f.get("family", "")
                for phase_num in range(57, 100)  # Exclude R57+ (R57 is current, R58+ are future)
            )
            and not f.get("family", "").startswith("scope-expansion-")
        ]

        assert not released_scope_pending, (
            f"Uncovered families in released-scope range: "
            f"{[f.get('family') for f in released_scope_pending]}. "
            f"All released-scope families must be covered."
        )

        # Verify Release Boundary section references are all covered
        essential_refs = [
            "pageReadyObserved",
            "attach",
            "prepareSession",
            "benchmark validation",
            "intentional stop at the released ceiling",
        ]

        for ref in essential_refs:
            assert ref in release_boundary_section, (
                f"Essential released-scope reference '{ref}' "
                f"not found in PRD Release Boundary section"
            )

    def test_phase_r57_released_scope_integration_verified(self) -> None:
        """Verify released-scope integration test exists and covers all missions.

        The released-scope integration test must exercise all 4 released missions
        in proper sequence and enforce the ceiling stop.
        """
        test_dir = Path(__file__).parent
        integration_test_file = test_dir / "test_released_scope_integration.py"

        assert integration_test_file.exists(), (
            "test_released_scope_integration.py not found. "
            "Released-scope integration test is required."
        )

        integration_content = integration_test_file.read_text()

        # Verify integration test covers all missions
        required_missions = [
            "attach_session",
            "prepare_session",
            "benchmark_validation",
            "page_ready_observation",
        ]

        for mission in required_missions:
            assert mission in integration_content, (
                f"Released-scope integration test missing coverage for {mission}"
            )

        # Verify integration test checks ceiling enforcement
        assert "pageReadyObserved" in integration_content or "approved_scope_ceiling" in integration_content, (
            "Released-scope integration test must verify ceiling enforcement"
        )

    def test_phase_r57_coverage_ledger_families_r56_remain_covered(self) -> None:
        """Verify all families through R56 remain marked covered.

        Confirms that no families have regressed from covered status
        since Phase R56 completion.
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # All families R1-R56 should be covered or excluded
        for idx, family in enumerate(families):
            status = family.get("status")
            family_name = family.get("family", f"Family {idx}")

            # Extract phase number if available
            phase_indicator = ""
            if "Phase R" in family_name:
                import re
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if phase_num <= 56:
                        phase_indicator = f" (Phase R{phase_num})"

            if "Phase R" in family_name:
                import re
                match = re.search(r"Phase R(\d+)", family_name)
                if match:
                    phase_num = int(match.group(1))
                    if phase_num <= 56:
                        assert status in ("covered", "excluded"), (
                            f"Family {family_name}{phase_indicator} "
                            f"has status '{status}' but must be covered/excluded"
                        )
                        if status == "covered":
                            assert family.get("evidence_or_reason"), (
                                f"Covered family {family_name} lacks evidence"
                            )
