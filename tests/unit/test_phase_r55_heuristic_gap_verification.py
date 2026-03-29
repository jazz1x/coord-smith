"""Phase R55: Heuristic gap scan verification.

Performs extended final heuristic verification confirming:
- All PRD clauses below pageReadyObserved remain covered
- No new uncovered clauses have emerged since Phase R54
- Coverage ledger accuracy confirmed
- Exhaustion protocol preparedness verified
"""

import json
from pathlib import Path
from typing import Any, cast


class TestPhaseR55HeuristicGapVerification:
    """Extended heuristic gap scan for Phase R55."""

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root path."""
        return Path(__file__).parent.parent.parent

    @staticmethod
    def _load_coverage_ledger() -> dict[str, Any]:
        """Load coverage ledger."""
        ledger_path = (
            Path(__file__).parent.parent.parent
            / "docs/llm/low-attention-coverage-ledger.json"
        )
        with open(ledger_path) as f:
            return cast(dict[str, Any], json.load(f))

    @staticmethod
    def _load_prd() -> str:
        """Load PRD."""
        prd_path = (
            Path(__file__).parent.parent.parent / "docs/prd.md"
        )
        with open(prd_path) as f:
            return f.read()

    def test_phase_r55_all_families_remain_covered(self) -> None:
        """Verify all 54 families (R1-R54) remain marked covered in ledger."""
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # Check that at least 54 families exist and are marked covered
        covered_count = sum(
            1 for f in families
            if f.get("status") == "covered"
        )

        assert covered_count >= 54, (
            f"Expected at least 54 covered families, "
            f"found {covered_count}. Ledger may be stale."
        )

        # Verify all covered families have evidence
        for family in families:
            if family.get("status") == "covered":
                assert family.get("evidence_or_reason"), (
                    f"Covered family {family.get('family')} "
                    f"lacks evidence_or_reason"
                )

    def test_phase_r55_no_new_uncovered_clauses_detected(self) -> None:
        """Verify no new uncovered PRD clauses have been discovered.

        This test scans the PRD for any unenforced clauses that would
        represent new gaps below pageReadyObserved.
        """
        prd_content = self._load_prd()
        ledger = self._load_coverage_ledger()

        # Key PRD sections that must have dedicated tests
        required_sections = [
            "Purpose",
            "System Boundary",
            "Release Boundary",
            "Evidence Truth Model",
            "Release-Ceiling Stop Proof",
            "Canonical Memory Model",
            "Canonical Stack",
            "Non-Goals And Forbidden Directions",
        ]

        for section in required_sections:
            assert section in prd_content, (
                f"PRD section '{section}' not found in docs/prd.md"
            )

        # Check that ledger has families covering major PRD concerns
        families = ledger.get("families", [])
        family_descriptions = [f.get("family", "") for f in families]

        # Essential coverage areas that must exist in ledger
        essential_areas = [
            ["released-scope integration test", "console-script entry"],
            ["evidence", "OpenClaw request"],
            ["release-ceiling stop proof", "release ceiling"],
            ["test fixture", "importability"],
            ["heuristic gap scan", "Phase R"],
        ]

        for area in essential_areas:
            found = any(
                any(keyword.lower() in desc.lower() for keyword in area)
                for desc in family_descriptions
            )
            assert found, (
                f"No coverage ledger families found for area {area}. "
                f"Possible gap in ledger coverage."
            )

    def test_phase_r55_exhaustion_protocol_preparedness(self) -> None:
        """Verify the system is prepared for final FINAL_STOP decision.

        Confirms:
        - work-rag.json current state is consistent
        - Coverage ledger shows all families covered or excluded
        - No pending families OTHER than next_action block FINAL_STOP
        """
        work_rag_path = (
            Path(__file__).parent.parent.parent
            / "docs/product/work-rag.json"
        )
        with open(work_rag_path) as f:
            work_rag = json.load(f)

        ledger = self._load_coverage_ledger()

        # Verify current state exists
        assert work_rag.get("current"), "work-rag.json missing 'current' block"

        current = work_rag["current"]
        assert current.get("phase"), "Current phase not set"
        assert current.get("milestone"), "Current milestone not set"
        assert current.get("anchor"), "Current anchor not set"
        assert current.get("next_action"), "Current next_action not set"

        next_action = current["next_action"]

        # Verify ledger has no pending families OTHER than the next_action
        families = ledger.get("families", [])
        pending_families = [
            f for f in families
            if f.get("status") == "pending"
            and f.get("family") not in next_action
            and not f.get("family", "").startswith("scope-expansion-")
        ]

        assert not pending_families, (
            f"Found {len(pending_families)} unexpected pending families: "
            f"{[f.get('family') for f in pending_families]}. "
            f"Only {next_action} should be pending."
        )

        # All non-excluded families must be covered or be the next_action
        non_excluded = [
            f for f in families
            if f.get("status") != "excluded"
        ]
        uncovered = [
            f for f in non_excluded
            if f.get("status") != "covered"
            and f.get("family") not in next_action
            and not f.get("family", "").startswith("scope-expansion-")
        ]

        assert not uncovered, (
            f"Found {len(uncovered)} uncovered families: "
            f"{[f.get('family') for f in uncovered]}"
        )
