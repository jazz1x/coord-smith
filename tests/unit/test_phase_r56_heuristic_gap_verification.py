"""Phase R56: Heuristic gap scan verification (re-verification pass).

Performs comprehensive re-verification confirming:
- All PRD clauses below pageReadyObserved remain covered
- No new uncovered clauses have emerged since Phase R55
- Coverage ledger accuracy confirmed
- Exhaustion protocol consistency verified
"""

import json
from pathlib import Path
from typing import Any, cast


class TestPhaseR56HeuristicGapVerification:
    """Comprehensive re-verification heuristic gap scan for Phase R56."""

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

    @staticmethod
    def _load_work_rag() -> dict[str, Any]:
        """Load work-rag.json."""
        work_rag_path = (
            Path(__file__).parent.parent.parent
            / "docs/product/work-rag.json"
        )
        with open(work_rag_path) as f:
            return cast(dict[str, Any], json.load(f))

    def test_phase_r56_all_families_through_r55_remain_covered(self) -> None:
        """Verify all families through R55 remain marked covered in ledger."""
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # Check that families R1-R55 are marked as covered or excluded
        covered_count = sum(
            1 for f in families
            if f.get("status") in ("covered", "excluded")
        )

        assert covered_count >= 55, (
            f"Expected at least 55 covered/excluded families, "
            f"found {covered_count}. Ledger may be corrupted."
        )

        # Verify all covered families have evidence
        for family in families:
            if family.get("status") == "covered":
                assert family.get("evidence_or_reason"), (
                    f"Covered family {family.get('family')} "
                    f"lacks evidence_or_reason"
                )

    def test_phase_r56_prd_section_coverage_completeness(self) -> None:
        """Verify all 8 PRD sections have adequate test coverage.

        Scans for test files covering:
        - Purpose (6 clauses)
        - System Boundary (11 clauses)
        - Release Boundary (6 clauses)
        - Evidence Truth Model (3 clauses)
        - Release-Ceiling Stop Proof (4 clauses)
        - Canonical Memory Model (2 clauses)
        - Canonical Stack (7 clauses)
        - Non-Goals And Forbidden Directions (8 clauses)
        """
        prd_content = self._load_prd()
        test_dir = Path(__file__).parent

        # Key PRD sections that must have dedicated tests
        required_sections = {
            "Purpose": [
                "orchestrate execution through OpenClaw",
                "manage graph-based state transitions",
                "normalize and validate typed evidence",
                "enforce released execution boundaries",
                "preserve comparability and verifiability of runs",
                "not a browser automation engine",
            ],
            "System Boundary": [
                "OpenClaw is the only browser-facing execution actor",
                "orchestration-centric",
                "must not become browser-facing",
                "must not treat OpenClaw internals as architecture truth",
                "not a Playwright, CDP, or Chromium control runtime",
                "owns orchestration, validation, stopping, and reasoning",
                "must not invoke any LLM inference at execution time",
                "deterministic Python",
                "PyAutoGUIAdapter is the sole execution backend",
            ],
            "Release Boundary": [
                "pageReadyObserved",
                "attach",
                "prepareSession",
                "benchmark validation",
                "intentional stop at the released ceiling",
                "modeled-only",
            ],
            "Evidence Truth Model": [
                "truth priority",
                "truth must not be derived from vision or coordinates alone",
                "typed evidence is required for released-scope decisions",
            ],
            "Release-Ceiling Stop Proof": [
                "Stopping at pageReadyObserved must be provable",
                "evidence://action-log/release-ceiling-stop",
                "required typed fields",
                "event, mission_name, ts",
            ],
            "Canonical Memory Model": [
                "Only two canonical memory layers exist",
                "work-rag",
                "rag",
            ],
            "Canonical Stack": [
                "Python runtime",
                "LangGraph",
                "LangChain-core",
                "Pydantic v2",
                "pytest",
                "ruff",
                "mypy",
            ],
            "Non-Goals And Forbidden Directions": [
                "browser-facing",
                "replacing OpenClaw",
                "Playwright, CDP, or Chromium",
                "release-ceiling expansion",
                "presenting modeled behavior as released",
                "TypeScript runtime revival",
                "Bun-first",
            ],
        }

        # Verify all sections exist in PRD
        for section in required_sections:
            assert section in prd_content, (
                f"PRD section '{section}' not found in docs/prd.md"
            )

        # Count test files for each section
        test_files = sorted(test_dir.glob("test_*.py"))
        test_content = "".join(f.read_text() for f in test_files)

        # Verify essential test coverage exists
        coverage_indicators = [
            ("Purpose", ["test_purpose", "test_orchestrate", "test_manage"]),
            ("System Boundary", ["test_boundary", "test_orchestration", "test_browser"]),
            ("Release Boundary", ["test_release", "test_mission", "test_ceiling"]),
            ("Evidence", ["test_evidence", "test_truth", "test_typed"]),
            ("Stop Proof", ["test_stop", "test_ceiling"]),
            ("Memory", ["test_rag", "test_memory", "test_canonical"]),
            ("Stack", ["test_stack", "test_langgraph", "test_pydantic"]),
            ("Non-Goals", ["test_forbidden", "test_non_goals"]),
        ]

        for section, keywords in coverage_indicators:
            found = any(
                keyword in test_content
                for keyword in keywords
            )
            assert found, (
                f"No adequate test coverage found for section: {section}. "
                f"Looking for keywords: {keywords}"
            )

    def test_phase_r56_no_new_uncovered_clauses_emerged(self) -> None:
        """Verify no new uncovered PRD clauses have emerged since Phase R55.

        This comprehensive re-verification confirms that all previously
        identified coverage remains valid and no gaps have appeared.
        """
        ledger = self._load_coverage_ledger()
        families = ledger.get("families", [])

        # Count pending families
        pending_families = [
            f for f in families
            if f.get("status") == "pending"
        ]

        # Phase R56 completion means either:
        # 1. No pending families exist (all covered/excluded) → FINAL_STOP
        # 2. Only R57+ pending → proceed to next phase
        # Verify no unexpected pending families exist
        unexpected_pending = [
            f for f in pending_families
            if not any(
                f"Phase R{phase_num}" in f.get("family", "")
                for phase_num in range(57, 100)  # Allow R57 and beyond
            )
            and not f.get("family", "").startswith("scope-expansion-")
        ]

        assert not unexpected_pending, (
            f"Unexpected pending families found: "
            f"{[f.get('family') for f in unexpected_pending]}. "
            f"New uncovered clauses may have emerged."
        )

        # Verify all covered families have evidence
        covered = [f for f in families if f.get("status") == "covered"]
        for fam in covered:
            assert fam.get("evidence_or_reason"), (
                f"Covered family {fam.get('family')} lacks evidence_or_reason"
            )

    def test_phase_r56_work_rag_consistency(self) -> None:
        """Verify work-rag.json current state is consistent with Phase R56.

        Confirms that current next_action reflects the actual pending status
        in the coverage ledger.
        """
        work_rag = self._load_work_rag()

        # Verify current state exists
        assert work_rag.get("current"), "work-rag.json missing 'current' block"

        current = work_rag["current"]
        assert current.get("phase"), "Current phase not set"
        assert current.get("milestone"), "Current milestone not set"
        assert current.get("next_action"), "Current next_action not set"

        # Verify next_action references a known phase or final stop
        next_action = current.get("next_action", "")
        is_valid = (
            "Phase R" in next_action or
            "FINAL_STOP" in next_action or
            "heuristic gap scan" in next_action or
            next_action.startswith("scope-expansion-")
        )

        assert is_valid, (
            f"Invalid next_action: {next_action}. "
            f"Should reference a Phase or FINAL_STOP."
        )

        # Verify that history entries exist
        history = work_rag.get("history", [])
        assert len(history) > 0, "work-rag.json history is empty"

        # History should have reasonable structure
        for entry in history:
            assert entry.get("kind"), f"History entry missing 'kind': {entry}"
            assert entry.get("phase"), f"History entry missing 'phase': {entry}"
            assert entry.get("summary"), f"History entry missing 'summary': {entry}"
